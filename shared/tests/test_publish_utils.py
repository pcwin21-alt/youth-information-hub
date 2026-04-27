from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SHARED_SRC = REPO_ROOT / "shared" / "src"
if str(SHARED_SRC) not in sys.path:
    sys.path.insert(0, str(SHARED_SRC))

from youth_info_platform.publish_utils import upsert_article_archive, upsert_articles  # noqa: E402


def sample_article(**overrides: object) -> dict[str, object]:
    article: dict[str, object] = {
        "url": "https://example.com/news/1?utm_source=test",
        "title": "청년 정책 기사",
        "source": "테스트신문",
        "published_date": "2026-04-26T09:00:00+09:00",
        "region": "서울",
        "categories": ["복지"],
    }
    article.update(overrides)
    return article


class PublishUtilsArchiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "articles.db"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def fetch_archive_row(self, article_key: str) -> sqlite3.Row:
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT * FROM article_archive WHERE article_key = ?",
                (article_key,),
            ).fetchone()
        assert row is not None
        return row

    def test_article_archive_table_is_created(self) -> None:
        counts = upsert_article_archive(
            self.db_path,
            [sample_article()],
            run_id="run-1",
            seen_at="2026-04-26T23:30:00+09:00",
        )

        with closing(sqlite3.connect(self.db_path)) as connection:
            tables = {
                row[0]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            }

        self.assertIn("article_archive", tables)
        self.assertEqual(counts["inserted"], 1)
        self.assertEqual(counts["updated"], 0)
        self.assertEqual(counts["total"], 1)

    def test_archive_upsert_keeps_one_row_and_increments_seen_count(self) -> None:
        article = sample_article(url="https://example.com/news/duplicate?utm_campaign=a")
        upsert_article_archive(
            self.db_path,
            [article],
            run_id="run-1",
            seen_at="2026-04-26T23:30:00+09:00",
        )
        counts = upsert_article_archive(
            self.db_path,
            [sample_article(url="https://example.com/news/duplicate", title="수정된 제목")],
            run_id="run-2",
            seen_at="2026-04-27T23:30:00+09:00",
        )

        with closing(sqlite3.connect(self.db_path)) as connection:
            row_count = connection.execute("SELECT COUNT(*) FROM article_archive").fetchone()[0]
            row = connection.execute(
                "SELECT title, seen_count, first_seen_at, last_seen_at, last_run_id FROM article_archive"
            ).fetchone()

        self.assertEqual(row_count, 1)
        self.assertEqual(counts["inserted"], 0)
        self.assertEqual(counts["updated"], 1)
        self.assertEqual(row[0], "수정된 제목")
        self.assertEqual(row[1], 2)
        self.assertEqual(row[2], "2026-04-26T23:30:00+09:00")
        self.assertEqual(row[3], "2026-04-27T23:30:00+09:00")
        self.assertEqual(row[4], "run-2")

    def test_upsert_articles_still_writes_final_article_table(self) -> None:
        count = upsert_articles(self.db_path, [sample_article(summary="요약", importance_score=5)])

        with closing(sqlite3.connect(self.db_path)) as connection:
            row = connection.execute("SELECT url, title, summary FROM articles").fetchone()

        self.assertEqual(count, 1)
        self.assertEqual(row[0], "https://example.com/news/1?utm_source=test")
        self.assertEqual(row[1], "청년 정책 기사")
        self.assertEqual(row[2], "요약")

    def test_archive_upsert_does_not_store_unresolved_google_news_date_as_published_date(self) -> None:
        upsert_article_archive(
            self.db_path,
            [
                sample_article(
                    url="https://news.google.com/rss/articles/example?oc=5",
                    published_date="2026-04-25T02:45:17+00:00",
                    title="Youth rent support starts",
                    source="Korea Policy Briefing",
                )
            ],
            run_id="run-google",
            seen_at="2026-04-27T23:30:00+09:00",
        )

        with closing(sqlite3.connect(self.db_path)) as connection:
            row = connection.execute("SELECT published_date FROM article_archive").fetchone()

        self.assertIsNone(row[0])

    def test_db_writer_saves_final_and_filtered_inputs_separately(self) -> None:
        step5_path = Path(self.temp_dir.name) / "step5_summarized.json"
        step2_path = Path(self.temp_dir.name) / "step2_filtered.json"
        status_path = Path(self.temp_dir.name) / "pipeline_status.json"
        step5_path.write_text(
            json.dumps([sample_article(url="https://example.com/final", summary="최종 요약")], ensure_ascii=False),
            encoding="utf-8",
        )
        step2_path.write_text(
            json.dumps([sample_article(url="https://example.com/filtered", title="필터 통과 기사")], ensure_ascii=False),
            encoding="utf-8",
        )
        status_path.write_text(json.dumps({"run_id": "writer-run"}, ensure_ascii=False), encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "public-site" / "scripts" / "db_writer.py"),
                "--input",
                str(step5_path),
                "--archive-input",
                str(step2_path),
                "--status-input",
                str(status_path),
                "--db",
                str(self.db_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        with closing(sqlite3.connect(self.db_path)) as connection:
            final_count = connection.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
            archive_row = connection.execute(
                "SELECT title, last_run_id FROM article_archive WHERE url = ?",
                ("https://example.com/filtered",),
            ).fetchone()

        self.assertIn("db_upserted=1", result.stdout)
        self.assertIn("archive_inserted=1", result.stdout)
        self.assertEqual(final_count, 1)
        self.assertEqual(archive_row[0], "필터 통과 기사")
        self.assertEqual(archive_row[1], "writer-run")


if __name__ == "__main__":
    unittest.main()

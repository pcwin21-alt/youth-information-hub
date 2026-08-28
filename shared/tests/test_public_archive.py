from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path
import unittest


SHARED_SRC = Path(__file__).resolve().parents[1] / "src"
if str(SHARED_SRC) not in sys.path:
    sys.path.insert(0, str(SHARED_SRC))

from youth_info_platform.public_archive import build_public_archive_payload  # noqa: E402


SEOUL = timezone(timedelta(hours=9))


def article(title: str, published_at: str, **overrides: object) -> dict:
    return {
        "url": f"https://example.test/{title}",
        "title": title,
        "source": "테스트 출처",
        "published_date": published_at,
        "source_kind": "news",
        "public_relevance_score": 5,
        "youth_life_signal": True,
        "summary": f"{title} 요약",
        **overrides,
    }


class PublicArchiveTests(unittest.TestCase):
    def test_merges_public_articles_and_deduplicates_by_url(self) -> None:
        now = datetime(2026, 8, 28, 12, tzinfo=SEOUL)
        first = article("첫 기사", "2026-08-27T09:00:00+09:00", url="https://example.test/article-1")
        update = article("첫 기사 수정", "2026-08-27T09:00:00+09:00", url="https://example.test/article-1", summary="수정 요약")
        payload = build_public_archive_payload({}, [first], now=now)
        merged = build_public_archive_payload(payload, [update], now=now)

        self.assertEqual(merged["article_count"], 1)
        self.assertEqual(merged["articles"][0]["title"], "첫 기사 수정")
        self.assertEqual(merged["articles"][0]["summary"], "수정 요약")

    def test_excludes_non_public_and_expired_articles(self) -> None:
        now = datetime(2026, 8, 28, 12, tzinfo=SEOUL)
        visible = article("공개", "2026-08-27T09:00:00+09:00")
        noise = article("제외", "2026-08-27T09:00:00+09:00", is_noise=True)
        old = article("오래된", "2025-08-27T09:00:00+09:00")
        payload = build_public_archive_payload({}, [visible, noise, old], now=now)

        self.assertEqual(payload["article_count"], 1)
        self.assertEqual(payload["articles"][0]["title"], "공개")
        self.assertEqual(payload["retention_days"], 365)

    def test_retains_research_for_ten_year_window(self) -> None:
        now = datetime(2026, 8, 28, 12, tzinfo=SEOUL)
        research = article(
            "청년 연구",
            "2020-01-01T09:00:00+09:00",
            source_kind="research",
            article_type="research",
        )
        payload = build_public_archive_payload({}, [research], now=now)

        self.assertEqual(payload["article_count"], 1)
        self.assertEqual(payload["research_retention_days"], 3650)

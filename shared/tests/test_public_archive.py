from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path
import unittest


SHARED_SRC = Path(__file__).resolve().parents[1] / "src"
if str(SHARED_SRC) not in sys.path:
    sys.path.insert(0, str(SHARED_SRC))

from youth_info_platform.public_archive import (  # noqa: E402
    build_public_archive_payload,
    legacy_db_article_to_public_candidate,
)


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

    def test_legacy_record_requires_real_source_and_current_public_relevance(self) -> None:
        row = {
            "url": "https://news.example.com/youth-policy",
            "title": "청년 주거 지원 정책 신청을 시작합니다",
            "source": "테스트신문",
            "published_date": "2026-08-01T10:00:00+09:00",
            "region": "서울",
            "categories": "주거, 모집",
            "summary": "청년을 위한 주거 지원 신청과 상담을 안내합니다.",
            "importance_score": 55,
            "is_official_source": 0,
        }
        candidate = legacy_db_article_to_public_candidate(row)
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate["source_kind"], "news")
        self.assertTrue(candidate["is_public_interest_article"])

        row["source"] = "새 창 열림"
        self.assertIsNone(legacy_db_article_to_public_candidate(row))

        row["source"] = "테스트신문"
        row["title"] = "청년 후보의 공약 발표"
        self.assertIsNone(legacy_db_article_to_public_candidate(row))

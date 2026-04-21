from __future__ import annotations

import sys
import unittest
from pathlib import Path


SHARED_SRC = Path(__file__).resolve().parents[1] / "src"
if str(SHARED_SRC) not in sys.path:
    sys.path.insert(0, str(SHARED_SRC))

from youth_info_platform.curation import select_articles, summarize_articles  # noqa: E402
from youth_info_platform.editorial import (  # noqa: E402
    DECISION_EXCLUDE,
    DECISION_FEATURE,
    apply_editorial_overrides,
    build_article_identifiers,
)


def make_article(
    *,
    url: str,
    title: str,
    source: str = "테스트신문",
    published_date: str = "2026-04-20T09:00:00+09:00",
) -> dict:
    return {
        "url": url,
        "title": title,
        "source": source,
        "source_name": source,
        "published_date": published_date,
        "categories": ["청년 이슈"],
        "issue_tags": ["청년센터 운영"],
        "location_tags": [],
        "region": "서울",
        "lead_text": "청년 관련 기사 요약",
        "body_text": "청년 정책과 청년 공간 운영을 다룬 기사입니다.",
        "article_type": None,
        "source_kind": "news",
        "is_noise": False,
        "is_official_source": False,
        "related_article_count": 1,
        "pipeline_flags": {},
    }


class EditorialOverrideTests(unittest.TestCase):
    def test_apply_editorial_overrides_marks_matching_article(self) -> None:
        article = make_article(url="https://example.com/a", title="청년 공간 기사")
        identifier = build_article_identifiers(article)[0]
        overrides = {
            identifier: {
                "decision": DECISION_FEATURE,
                "feature_rank": 1,
                "note": "메인 상단 고정",
                "identifiers": [identifier],
            }
        }

        updated = apply_editorial_overrides([article], overrides)

        self.assertEqual(updated[0]["editorial_decision"], DECISION_FEATURE)
        self.assertEqual(updated[0]["editorial_feature_rank"], 1)
        self.assertEqual(updated[0]["editorial_note"], "메인 상단 고정")

    def test_select_articles_respects_feature_and_exclude(self) -> None:
        featured = make_article(
            url="https://example.com/featured",
            title="상단 노출 기사",
            published_date="2026-04-10T09:00:00+09:00",
        )
        regular = make_article(
            url="https://example.com/regular",
            title="일반 기사",
            published_date="2026-04-20T09:00:00+09:00",
        )
        excluded = make_article(
            url="https://example.com/excluded",
            title="배제 기사",
            published_date="2026-04-21T09:00:00+09:00",
        )

        featured["editorial_decision"] = DECISION_FEATURE
        featured["editorial_feature_rank"] = 1
        excluded["editorial_decision"] = DECISION_EXCLUDE

        selected, prepared = select_articles([regular, excluded, featured], limit=2)
        selected_urls = [article["url"] for article in selected]

        self.assertEqual(selected_urls[0], "https://example.com/featured")
        self.assertIn("https://example.com/regular", selected_urls)
        self.assertNotIn("https://example.com/excluded", selected_urls)

        excluded_record = next(article for article in prepared if article["url"] == "https://example.com/excluded")
        self.assertEqual(excluded_record["drop_reason"], "editorial_excluded")

        summarized = summarize_articles(selected)
        self.assertEqual(summarized[0]["display_badges"][0], "상단 노출")


if __name__ == "__main__":
    unittest.main()

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
    DECISION_INCLUDE,
    apply_editorial_overrides,
    build_article_identifiers,
    merge_manual_articles,
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
        "is_public_interest_article": True,
        "public_relevance_score": 6,
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
                "decision": DECISION_INCLUDE,
                "is_highlighted": True,
                "note": "메인 하이라이트",
                "identifiers": [identifier],
            }
        }

        updated = apply_editorial_overrides([article], overrides)

        self.assertEqual(updated[0]["editorial_decision"], DECISION_INCLUDE)
        self.assertTrue(updated[0]["editorial_is_highlighted"])
        self.assertEqual(updated[0]["editorial_note"], "메인 하이라이트")

    def test_select_articles_respects_highlight_include_and_exclude(self) -> None:
        highlighted = make_article(
            url="https://example.com/highlighted",
            title="대표 기사",
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

        highlighted["editorial_decision"] = DECISION_INCLUDE
        highlighted["editorial_is_highlighted"] = True
        excluded["editorial_decision"] = DECISION_EXCLUDE

        selected, prepared = select_articles([regular, excluded, highlighted], limit=2)
        selected_urls = [article["url"] for article in selected]

        self.assertEqual(selected_urls[0], "https://example.com/highlighted")
        self.assertIn("https://example.com/regular", selected_urls)
        self.assertNotIn("https://example.com/excluded", selected_urls)

        excluded_record = next(article for article in prepared if article["url"] == "https://example.com/excluded")
        self.assertEqual(excluded_record["drop_reason"], "editorial_excluded")

        summarized = summarize_articles(selected)
        self.assertEqual(summarized[0]["display_badges"][0], "하이라이트")

    def test_merge_manual_articles_overlays_runtime_article_and_adds_missing_manual(self) -> None:
        runtime_article = make_article(url="https://example.com/runtime", title="런타임 기사")
        runtime_article["article_key"] = "runtime-key"
        manual_override = {
            **runtime_article,
            "editorial_decision": DECISION_INCLUDE,
            "editorial_is_highlighted": True,
            "editorial_note": "운영 포함",
            "is_manual_entry": True,
        }
        manual_only = make_article(url="https://example.com/manual-only", title="수동 기사")
        manual_only["article_key"] = "manual-key"
        manual_only["editorial_decision"] = DECISION_INCLUDE
        manual_only["is_manual_entry"] = True

        merged = merge_manual_articles([runtime_article], [manual_override, manual_only])

        self.assertEqual(len(merged), 2)
        updated_runtime = next(article for article in merged if article["article_key"] == "runtime-key")
        self.assertEqual(updated_runtime["editorial_decision"], DECISION_INCLUDE)
        self.assertTrue(updated_runtime["editorial_is_highlighted"])
        self.assertEqual(updated_runtime["editorial_note"], "운영 포함")
        self.assertFalse(updated_runtime.get("is_manual_entry", False))

        added_manual = next(article for article in merged if article["article_key"] == "manual-key")
        self.assertTrue(added_manual["is_manual_entry"])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import sys
import unittest
from pathlib import Path


SHARED_SRC = Path(__file__).resolve().parents[1] / "src"
if str(SHARED_SRC) not in sys.path:
    sys.path.insert(0, str(SHARED_SRC))

from youth_info_platform.curation import (  # noqa: E402
    has_public_institution_context,
    is_excluded_hub_record,
)


def make_article(*, title: str, lead_text: str) -> dict:
    return {
        "url": "https://example.com/article",
        "title": title,
        "source": "테스트신문",
        "source_name": "테스트신문",
        "published_date": "2026-04-21T09:00:00+09:00",
        "categories": ["청년 이슈"],
        "issue_tags": [],
        "location_tags": [],
        "region": "광주",
        "lead_text": lead_text,
        "body_text": lead_text,
        "article_type": None,
        "source_kind": "news",
        "is_noise": False,
        "is_official_source": False,
        "related_article_count": 1,
        "pipeline_flags": {},
    }


class PoliticalHubInclusionTests(unittest.TestCase):
    def test_public_institution_operational_issue_survives_political_context(self) -> None:
        article = make_article(
            title='광주 청년단체들 "갑질 의혹 구문정 전남광주특별시의원 예비후보 사퇴 촉구한다"',
            lead_text=(
                "광주청년정책네트워크와 광주청년유니온은 구 예비후보가 광주청년센터장으로 "
                "재직하던 시기 정규직과 계약직 퇴사가 이어졌다고 밝혔다."
            ),
        )
        text = " ".join([article["title"], article["lead_text"], article["source"]])

        self.assertTrue(has_public_institution_context(article, text))
        self.assertFalse(is_excluded_hub_record(article, text))

    def test_campaign_promise_article_is_not_excluded(self) -> None:
        article = make_article(
            title="서울시장 예비후보, 청년 주거 공약 발표",
            lead_text="민주당 후보가 청년 월세 지원 확대와 청년 일자리 확충을 약속했다.",
        )
        text = " ".join([article["title"], article["lead_text"], article["source"]])

        self.assertFalse(has_public_institution_context(article, text))
        self.assertFalse(is_excluded_hub_record(article, text))


if __name__ == "__main__":
    unittest.main()

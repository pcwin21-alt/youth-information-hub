from __future__ import annotations

import sys
import unittest
from pathlib import Path


SHARED_SRC = Path(__file__).resolve().parents[1] / "src"
if str(SHARED_SRC) not in sys.path:
    sys.path.insert(0, str(SHARED_SRC))

from youth_info_platform.curation import (  # noqa: E402
    classify_articles,
    has_campaign_political_signal,
    has_public_institution_context,
    has_substantive_promise_signal,
    is_public_interest_article,
    is_excluded_hub_record,
    select_articles,
)


def make_article(*, title: str, lead_text: str, url: str | None = None) -> dict:
    return {
        "url": url or f"https://example.com/{abs(hash(title))}",
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


class HomeSignalTests(unittest.TestCase):
    def test_campaign_political_signal_detected_for_election_article(self) -> None:
        text = "서울시장 후보가 청년 공약 발표와 유세 일정을 공개했다."

        self.assertTrue(has_campaign_political_signal(text))
        self.assertFalse(has_substantive_promise_signal(text))

    def test_substantive_promise_signal_detected_for_policy_rich_campaign_article(self) -> None:
        text = "시장 후보가 청년센터 예산 확대와 청년 지원사업 시행 계획을 공약으로 발표했다."

        self.assertTrue(has_campaign_political_signal(text))
        self.assertTrue(has_substantive_promise_signal(text))

    def test_generic_youth_mention_is_classified_as_weak_signal(self) -> None:
        article = make_article(
            title="청년 관객이 늘어난 지역 축제",
            lead_text="올해 축제 방문객 가운데 청년 비중이 커졌다는 조사 결과가 나왔다.",
        )

        classified = classify_articles([article])[0]

        self.assertTrue(classified["weak_youth_signal"])
        self.assertTrue(classified["is_noise"])

    def test_substantive_promise_can_survive_selection_over_pure_campaign_piece(self) -> None:
        pure_campaign = make_article(
            title="서울시장 후보, 청년 공약 발표하며 유세 총력",
            lead_text="후보와 정당 지도부가 청년층 표심을 잡기 위해 유세를 이어갔다.",
        )
        substantive_promise = make_article(
            title="서울시장 후보, 청년센터 예산 확대·청년 주거 지원 공약 발표",
            lead_text="청년센터 운영 확대와 청년 주거 지원사업 시행 계획을 공약에 담았다.",
        )
        articles = classify_articles([pure_campaign, substantive_promise])

        selected, prepared = select_articles(articles, limit=2)
        selected_urls = {article["url"] for article in selected}
        prepared_by_title = {article["title"]: article for article in prepared}

        self.assertIn(substantive_promise["url"], selected_urls)
        self.assertTrue(
            prepared_by_title[substantive_promise["title"]]["importance_score"]
            > prepared_by_title[pure_campaign["title"]]["importance_score"]
        )

    def test_generic_business_result_story_with_single_youth_mention_is_filtered_from_public_selection(self) -> None:
        article = make_article(
            title="KB금융, 1분기 순이익 1조8924억원…자사주 1426만주 전량 소각",
            lead_text=(
                "KB금융이 실적을 발표했다. 회사는 청년 대상 자산형성 금융상품도 운영 중이라고 밝혔다."
            ),
        )

        classified = classify_articles([article])[0]
        selected, prepared = select_articles([classified], limit=1)

        self.assertFalse(is_public_interest_article(classified))
        self.assertFalse(classified["is_public_interest_article"])
        self.assertLess(classified["public_relevance_score"], 4)
        self.assertEqual(selected, [])
        self.assertEqual(prepared[0]["drop_reason"], "public_relevance_filtered")

    def test_practical_youth_support_article_is_public_interest(self) -> None:
        article = make_article(
            title="한국장학재단, 취업 후 상환 전환 대출 신청 모집",
            lead_text="대학생과 사회초년생이 이용할 수 있는 학자금 전환 대출 신청을 받는다.",
        )

        classified = classify_articles([article])[0]
        selected, _ = select_articles([classified], limit=1)

        self.assertTrue(classified["has_direct_helpful_youth_signal"])
        self.assertTrue(classified["is_public_interest_article"])
        self.assertGreaterEqual(classified["public_relevance_score"], 4)
        self.assertEqual(len(selected), 1)

    def test_editorial_include_can_override_public_relevance_filter(self) -> None:
        article = make_article(
            title="금융지주, 1분기 실적 발표",
            lead_text="기업 실적 기사 말미에 청년 관련 문장이 한 줄 언급됐다.",
        )
        classified = classify_articles([article])[0]
        classified["editorial_decision"] = "include"

        selected, prepared = select_articles([classified], limit=1)

        self.assertFalse(classified["is_public_interest_article"])
        self.assertEqual(len(selected), 1)
        self.assertIsNone(prepared[0]["drop_reason"])

    def test_campaign_attack_story_is_not_public_interest(self) -> None:
        article = make_article(
            title="광주 청년단체, 청년비례 후보 사퇴 촉구",
            lead_text="청년단체가 후보 갑질 의혹을 제기하며 자진 사퇴를 촉구했다.",
        )

        classified = classify_articles([article])[0]

        self.assertTrue(classified["campaign_political"])
        self.assertTrue(classified["campaign_attack"])
        self.assertFalse(classified["is_public_interest_article"])


if __name__ == "__main__":
    unittest.main()

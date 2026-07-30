from __future__ import annotations

import sys
import unittest
from pathlib import Path


SHARED_SRC = Path(__file__).resolve().parents[1] / "src"
if str(SHARED_SRC) not in sys.path:
    sys.path.insert(0, str(SHARED_SRC))

from youth_info_platform.curation import (  # noqa: E402
    classify_articles,
    deduplicate_and_filter,
    has_campaign_political_signal,
    has_public_institution_context,
    has_substantive_promise_signal,
    is_public_interest_article,
    is_excluded_hub_record,
    score_article,
    select_articles,
)
from youth_info_platform.constants import (  # noqa: E402
    CONTENT_DIRECTION_COLUMN,
    CONTENT_DIRECTION_INSIGHT,
    CONTENT_DIRECTION_OFFICIAL_RELEASE,
    CONTENT_DIRECTION_PROMOTION,
    CONTENT_DIRECTION_REPORT,
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

    def test_source_name_youth_keyword_does_not_make_article_relevant(self) -> None:
        article = make_article(
            title="대구 남구센터, 도전지원사업 기업탐방 실시",
            lead_text="대구 남구센터는 외부연계활동의 일환으로 참여자들과 기업탐방 프로그램을 실시했다.",
        )
        article["source"] = "뉴스핌"
        article["source_name"] = "네이버뉴스 청년정책(1주)"
        article["body_text"] = article["lead_text"]

        classified = classify_articles([article])[0]
        selected, prepared = select_articles([classified], limit=1)

        self.assertFalse(classified["has_youth_content_signal"])
        self.assertTrue(classified["missing_youth_content_signal"])
        self.assertTrue(classified["is_noise"])
        self.assertFalse(classified["is_public_interest_article"])
        self.assertEqual(selected, [])
        self.assertEqual(prepared[0]["drop_reason"], "noise_filtered")
        self.assertEqual(deduplicate_and_filter([article]), [])

    def test_source_prefix_youth_keyword_does_not_make_article_relevant(self) -> None:
        article = make_article(
            title="[청년일보] 삼성, 2026년 상반기 GSAT 실시",
            lead_text="삼성전자 관계사가 입사 지원자를 대상으로 직무적성검사를 실시했다.",
        )
        article["source"] = "청년일보"
        article["source_name"] = "청년일보"
        article["body_text"] = article["lead_text"]

        classified = classify_articles([article])[0]

        self.assertFalse(classified["has_youth_content_signal"])
        self.assertTrue(classified["missing_youth_content_signal"])
        self.assertTrue(classified["is_noise"])

    def test_topic_tags_are_assigned_without_ai(self) -> None:
        article = make_article(
            title="파주시, 1분기 청년월세 지원금 지급",
            lead_text="파주시가 청년 주거 안정을 위해 청년월세 지원금 신청자를 모집하고 지원금을 지급했다.",
        )

        classified = classify_articles([article])[0]

        self.assertEqual(classified["topic_tags"], ["주거", "모집"])

    def test_content_direction_is_assigned_without_ai(self) -> None:
        cases = [
            (
                make_article(
                    title="은행, 청년 자립 캠페인 홍보",
                    lead_text="은행이 청년 자립 캠페인 홍보와 이벤트를 진행했다.",
                ),
                CONTENT_DIRECTION_PROMOTION,
            ),
            (
                make_article(
                    title="[칼럼] 청년정책은 왜 현장 언어를 잃었나",
                    lead_text="청년 주거 정책을 현장에서 다시 설계해야 한다는 기고문이다.",
                ),
                CONTENT_DIRECTION_COLUMN,
            ),
            (
                make_article(
                    title="데이터로 본 쉬었음 청년 증가",
                    lead_text="통계와 조사를 바탕으로 청년 고용 실태를 분석했다.",
                ),
                CONTENT_DIRECTION_INSIGHT,
            ),
            (
                make_article(
                    title="청년 월세 지원 접수 시작",
                    lead_text="청년 주거 안정을 위한 월세 지원 신청이 시작됐다.",
                ),
                CONTENT_DIRECTION_REPORT,
            ),
        ]

        classified = classify_articles([article for article, _ in cases])

        self.assertEqual([article["content_direction"] for article in classified], [expected for _, expected in cases])

    def test_official_sources_are_official_release_direction(self) -> None:
        article = make_article(
            title="국무조정실, 청년정책 시행계획 발표",
            lead_text="국무조정실이 청년정책 시행계획 보도자료를 발표했다.",
        )
        article["source_kind"] = "official"

        classified = classify_articles([article])[0]

        self.assertEqual(classified["content_direction"], CONTENT_DIRECTION_OFFICIAL_RELEASE)

    def test_regional_settlement_topic_is_assigned_without_ai(self) -> None:
        article = make_article(
            title="불 꺼진 빈집, 청년의 꿈터로 되살린다",
            lead_text="전남이 인구소멸 위기에 처한 지역에 청년 관계인구 유입 정책을 추진한다.",
        )

        classified = classify_articles([article])[0]

        self.assertIn("지역정착", classified["topic_tags"])

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


class ReferenceDeskPatternTests(unittest.TestCase):
    def test_youth_life_feature_survives_as_public_interest(self) -> None:
        article = make_article(
            title="방 안으로 밀려난 청년들…'은둔'은 어떻게 삶이 됐나",
            lead_text=(
                "청년의 삶이 방 안으로 접혀 들어간 과정을 인터뷰와 르포로 추적했다. "
                "밀린 월세, 구직단념, 고립·은둔 경험을 통해 청년세대의 생활 조건을 보여준다."
            ),
        )

        classified = classify_articles([article])[0]
        selected, prepared = select_articles([classified], limit=1)

        self.assertTrue(classified["youth_life_signal"])
        self.assertTrue(classified["youth_research_signal"])
        self.assertTrue(classified["is_public_interest_article"])
        self.assertEqual(prepared[0]["selection_bucket"], "youth_research_signal")
        self.assertEqual(len(selected), 1)

    def test_youth_data_and_inequality_story_gets_research_bucket(self) -> None:
        article = make_article(
            title="청년은 서울로, 비정규직은 지방으로…평균임금 50만원 차이",
            lead_text=(
                "통계와 조사 결과를 보면 청년층의 수도권 이동과 지방 비정규직 집중이 동시에 진행됐다. "
                "평균임금 격차와 지역 일자리 구조가 청년세대 삶의 조건을 가르고 있다."
            ),
        )

        classified = classify_articles([article])[0]
        selected, prepared = select_articles([classified], limit=1)

        self.assertTrue(classified["youth_life_signal"])
        self.assertTrue(classified["youth_research_signal"])
        self.assertEqual(prepared[0]["selection_bucket"], "youth_research_signal")
        self.assertEqual(len(selected), 1)

    def test_selection_priority_raises_score_without_manual_include(self) -> None:
        base = make_article(
            title="청년 임금격차 조사 결과 발표",
            lead_text="청년층 임금격차와 성과급 보상 차이를 분석한 기사다.",
        )
        prioritized = {**base, "selection_priority": 24}

        base_classified = classify_articles([base])[0]
        prioritized_classified = classify_articles([prioritized])[0]

        self.assertEqual(
            score_article(prioritized_classified),
            score_article(base_classified) + 24,
        )

    def test_actionable_utility_promo_can_survive_without_being_generic_pr(self) -> None:
        article = make_article(
            title="청년 연안여객선 할인권 '바다로' 판매 시작…최대 50% 할인",
            lead_text="청년이 신청해 바로 쓸 수 있는 연안여객선 할인권 바다로 판매가 시작됐다. 대상과 할인율, 이용 기간이 공개됐다.",
        )

        classified = classify_articles([article])[0]
        selected, _ = select_articles([classified], limit=1)

        self.assertTrue(classified["utility_promo_signal"])
        self.assertTrue(classified["is_public_interest_article"])
        self.assertEqual(len(selected), 1)

    def test_local_event_only_story_stays_filtered(self) -> None:
        article = make_article(
            title="광주, 전 세계 청년의 비트로 들썩인다 스트릿컬처 페스타 개막",
            lead_text="지역 축제와 공연 프로그램을 소개하는 행사 기사로, 공연 일정과 참여 팀 안내가 중심이다.",
        )

        classified = classify_articles([article])[0]
        selected, prepared = select_articles([classified], limit=1)

        self.assertFalse(classified["youth_life_signal"])
        self.assertFalse(classified["youth_research_signal"])
        self.assertFalse(classified["is_public_interest_article"])
        self.assertEqual(selected, [])
        self.assertIn(prepared[0]["drop_reason"], {"noise_filtered", "public_relevance_filtered"})


if __name__ == "__main__":
    unittest.main()

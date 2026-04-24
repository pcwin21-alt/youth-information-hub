from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "public-site" / "scripts" / "web_updater.py"
SCRIPT_DIR = str(SCRIPT_PATH.parent)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

spec = importlib.util.spec_from_file_location("test_web_updater_module", SCRIPT_PATH)
web_updater = importlib.util.module_from_spec(spec)
assert spec is not None and spec.loader is not None
spec.loader.exec_module(web_updater)


def make_article(
    *,
    title: str,
    lead_text: str,
    url: str,
    published_date: str = "2026-04-22T09:00:00+09:00",
    importance_score: int = 10,
    clean_score: int = 4,
    editorial_is_highlighted: bool = False,
    region: str = "",
    source_kind: str = "news",
) -> dict:
    return {
        "url": url,
        "title": title,
        "lead_text": lead_text,
        "summary": lead_text,
        "source": "테스트신문",
        "source_name": "테스트신문",
        "published_date": published_date,
        "issue_tags": [],
        "location_tags": [],
        "display_badges": [],
        "is_official_source": False,
        "is_noise": False,
        "article_type": "news",
        "source_kind": source_kind,
        "region": region,
        "governance_scope": None,
        "importance_score": importance_score,
        "clean_score": clean_score,
        "editorial_decision": "default",
        "editorial_is_highlighted": editorial_is_highlighted,
    }


class HomeSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        web_updater.HOME_UPDATE_SNAPSHOT = Path(self.tempdir.name) / "home_update_snapshot.json"
        self.reference_time = "2026-04-22T10:00:00+09:00"

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_campaign_story_stays_out_of_today_but_substantive_promise_can_enter_weekly(self) -> None:
        daily_issue = make_article(
            title="청년센터 운영 확대와 청년 주거 지원 발표",
            lead_text="청년센터 예산 확대와 청년 주거 지원사업 시행 계획을 발표했다.",
            url="https://example.com/daily",
        )
        pure_campaign = make_article(
            title="시장 후보, 청년 공약 앞세워 유세 총력",
            lead_text="후보와 정당 지도부가 청년층 표심을 잡기 위한 유세에 나섰다.",
            url="https://example.com/campaign",
        )
        substantive_promise = make_article(
            title="시장 후보, 청년센터 예산 확대·지원사업 공약 발표",
            lead_text="청년센터 운영 확대와 청년 지원사업 시행 계획을 공약에 담았다.",
            url="https://example.com/substantive",
        )

        today, weekly, _ = web_updater.build_home_curated_lists(
            [daily_issue, pure_campaign, substantive_promise],
            None,
            self.reference_time,
        )

        today_urls = {article["url"] for article in today}
        weekly_urls = {article["url"] for article in weekly}

        self.assertIn(daily_issue["url"], today_urls)
        self.assertNotIn(pure_campaign["url"], today_urls)
        self.assertNotIn(pure_campaign["url"], weekly_urls)
        self.assertNotIn(substantive_promise["url"], today_urls)
        self.assertIn(substantive_promise["url"], weekly_urls)
        self.assertTrue(today_urls.isdisjoint(weekly_urls))

    def test_highlight_article_is_not_duplicated_into_today_or_weekly(self) -> None:
        highlighted = make_article(
            title="대표 하이라이트 기사",
            lead_text="청년 주거 예산 확대와 지원사업 시행 계획을 다룬 기사다.",
            url="https://example.com/highlight",
            editorial_is_highlighted=True,
        )
        today_candidate = make_article(
            title="청년센터 운영 변화 기사",
            lead_text="청년센터 위탁 운영 방식과 예산 변화가 발표됐다.",
            url="https://example.com/today",
        )
        weekly_candidate = make_article(
            title="후보, 청년센터 설치 공약 발표",
            lead_text="청년센터 설치와 운영 확대 계획을 공약으로 발표했다.",
            url="https://example.com/weekly",
        )

        today, weekly, _ = web_updater.build_home_curated_lists(
            [highlighted, today_candidate, weekly_candidate],
            highlighted,
            self.reference_time,
        )

        selected_urls = {article["url"] for article in today + weekly}
        self.assertNotIn(highlighted["url"], selected_urls)
        self.assertIn(today_candidate["url"], {article["url"] for article in today})

    def test_home_page_shows_total_articles_published_today(self) -> None:
        news_today = make_article(
            title="오늘 올라온 청년 기사",
            lead_text="오늘 날짜로 발행된 기사다.",
            url="https://example.com/news-today",
        )
        policy_today = make_article(
            title="오늘 올라온 정책 발표",
            lead_text="오늘 날짜로 발행된 공식 발표다.",
            url="https://example.com/policy-today",
        )
        policy_today["is_official_source"] = True

        older_article = make_article(
            title="어제 올라온 기사",
            lead_text="어제 날짜로 발행된 기사다.",
            url="https://example.com/yesterday",
            published_date="2026-04-21T18:00:00+09:00",
        )
        duplicated_today = dict(news_today)
        duplicated_today["lead_text"] = "같은 기사 중복 레코드"

        page_html = web_updater.build_home_page(
            [news_today],
            [news_today, duplicated_today, policy_today, older_article],
            {"finished_at": self.reference_time},
            {
                "organization_name": "유스사이드(Youthside)",
                "copyright_text": "© 2026 유스사이드 · 박진감",
                "version_text": "v0.3",
                "email": "hello@example.com",
            },
        )

        self.assertIn("오늘 올라온 기사", page_html)
        self.assertIn(">2건<", page_html)
        self.assertNotIn("오늘 메인", page_html)
        self.assertNotIn('<span class="home-glance-label">정책</span>', page_html)
        self.assertNotIn('<span class="home-glance-label">참여·회의</span>', page_html)


    def test_home_page_omits_weekly_section_and_uses_support_credit_badge(self) -> None:
        daily_issue = make_article(
            title="泥?뀈?쇳꽣 ?댁쁺 ?뺣?? 泥?뀈 二쇨굅 吏??諛쒗몴",
            lead_text="泥?뀈?쇳꽣 ?덉궛 ?뺣?? 泥?뀈 二쇨굅 吏?먯궗???쒗뻾 怨꾪쉷??諛쒗몴?덈떎.",
            url="https://example.com/daily-page",
        )
        substantive_promise = make_article(
            title="?쒖옣 ?꾨낫, 泥?뀈?쇳꽣 ?덉궛 ?뺣?쨌吏?먯궗??怨듭빟 諛쒗몴",
            lead_text="泥?뀈?쇳꽣 ?댁쁺 ?뺣?? 泥?뀈 吏?먯궗???쒗뻾 怨꾪쉷??怨듭빟???댁븯??",
            url="https://example.com/weekly-page",
        )

        page_html = web_updater.build_home_page(
            [daily_issue, substantive_promise],
            [daily_issue, substantive_promise],
            {"finished_at": self.reference_time},
            {
                "organization_name": "유스사이드(Youthside)",
                "copyright_text": "© 2026 유스사이드 · 박진감",
                "version_text": "v0.3",
                "email": "hello@example.com",
            },
        )

        self.assertNotIn("이번 주 계속 볼 기사", page_html)
        self.assertIn("이 사이트는 무료로 운영됩니다. 청년들을 응원하기 위해 만들어졌습니다.", page_html)
        self.assertNotIn("유스사이드 preview", page_html)

    def test_news_policy_and_election_pages_are_split_by_campaign_signal(self) -> None:
        general_news = make_article(
            title="청년센터 운영 확대와 청년 주거 지원 발표",
            lead_text="청년센터 예산 확대와 청년 주거 지원사업 시행 계획을 발표했다.",
            url="https://example.com/general-news",
            region="서울",
        )
        pure_campaign = make_article(
            title="시장 후보, 청년 공약 앞세워 유세 총력",
            lead_text="후보와 정당 지도부가 청년층 표심을 잡기 위한 유세에 나섰다.",
            url="https://example.com/campaign-only",
            region="부산",
        )
        substantive_promise = make_article(
            title="시장 후보, 청년센터 예산 확대·지원사업 공약 발표",
            lead_text="청년센터 운영 확대와 청년 지원사업 시행 계획을 공약에 담았다.",
            url="https://example.com/substantive-promise",
            region="광주",
        )
        local_policy = make_article(
            title="부산시 청년정책 시행계획 발표",
            lead_text="부산시가 청년정책 시행계획과 청년센터 운영 확대 방안을 발표했다.",
            url="https://example.com/local-policy",
            region="부산",
        )
        official_policy = make_article(
            title="고용노동부 청년 지원사업 발표",
            lead_text="정부가 청년 고용 지원사업 추진 계획을 발표했다.",
            url="https://example.com/official-policy",
            source_kind="official",
        )
        official_policy["is_official_source"] = True
        official_policy["source"] = "고용노동부"
        official_policy["source_name"] = "고용노동부"

        status = {"finished_at": self.reference_time}

        news_html = web_updater.build_news_page(
            [general_news, pure_campaign, substantive_promise, local_policy],
            status,
        )
        policies_html = web_updater.build_policies_page_compact(
            [general_news, pure_campaign, substantive_promise, local_policy, official_policy],
            status,
        )
        election_html = web_updater.build_election_page(
            [general_news, pure_campaign, substantive_promise, local_policy],
            status,
        )

        self.assertIn(general_news["title"], news_html)
        self.assertIn(local_policy["title"], news_html)
        self.assertNotIn(pure_campaign["title"], news_html)
        self.assertNotIn(substantive_promise["title"], news_html)

        self.assertIn(official_policy["title"], policies_html)
        self.assertIn(local_policy["title"], policies_html)
        self.assertNotIn(pure_campaign["title"], policies_html)
        self.assertNotIn(substantive_promise["title"], policies_html)
        self.assertIn("선거·공약성 기사는 별도 탭에서 봅니다.", policies_html)

        self.assertIn(pure_campaign["title"], election_html)
        self.assertIn(substantive_promise["title"], election_html)
        self.assertIn("선거 기사", election_html)
        self.assertIn("정책 공약", election_html)
        self.assertNotIn(general_news["title"], election_html)

    def test_filter_public_articles_drops_low_value_business_story_but_keeps_manual_include(self) -> None:
        weak_business_story = make_article(
            title="KB금융, 1분기 순이익 1조8924억원…자사주 1426만주 전량 소각",
            lead_text="실적 기사 말미에 청년 자산형성 상품 문장이 한 줄 덧붙었다.",
            url="https://example.com/weak-business",
        )
        practical_story = make_article(
            title="한국장학재단, 취업 후 상환 전환 대출 신청 모집",
            lead_text="대학생과 사회초년생 대상 학자금 전환 대출 신청을 받는다.",
            url="https://example.com/practical-story",
        )

        filtered = web_updater.filter_public_articles([weak_business_story, practical_story])
        filtered_urls = {article["url"] for article in filtered}

        self.assertNotIn(weak_business_story["url"], filtered_urls)
        self.assertIn(practical_story["url"], filtered_urls)

        weak_business_story["editorial_decision"] = "include"
        included_urls = {article["url"] for article in web_updater.filter_public_articles([weak_business_story])}
        self.assertIn(weak_business_story["url"], included_urls)


if __name__ == "__main__":
    unittest.main()

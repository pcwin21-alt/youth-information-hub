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
    topic_tags: list[str] | None = None,
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
        "topic_tags": topic_tags or [],
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

    def test_local_government_marks_cover_every_tracked_metropolitan_region(self) -> None:
        self.assertEqual(len(web_updater.LOCAL_YOUTH_PLAN_REGIONS), 17)
        for region in web_updater.LOCAL_YOUTH_PLAN_REGIONS:
            with self.subTest(region=region["name"]):
                article = make_article(
                    title=f'{region["full_name"]} 청년 정책 공고',
                    lead_text="지역 청년 지원사업 공고입니다.",
                    url=f'https://{region["domain"]}/youth-notice',
                    region=region["full_name"],
                    source_kind="local",
                )
                article["source"] = f'{region["full_name"]} 보도자료'
                article["source_name"] = article["source"]

                mark_html = web_updater.render_publisher_icon(article)

                self.assertIn('publisher-icon--local', mark_html)
                self.assertIn(region["full_name"], mark_html)
                self.assertIn(f'https://{region["domain"]}/favicon.ico', mark_html)

    def test_policy_briefing_release_uses_authority_mark_instead_of_portal_image(self) -> None:
        article = make_article(
            title="청년 일자리 박람회 개최",
            lead_text="청년 일자리 박람회 관련 공식 보도자료입니다.",
            url="https://www.korea.kr/briefing/pressReleaseView.do?newsId=1",
            source_kind="official",
        )
        article.update(
            {
                "source": "고용노동부",
                "source_name": "정책브리핑 정부부처 청년 보도자료",
                "policy_authority": "고용노동부",
                "image_url": "https://www.korea.kr/images/event/korea_logo_2024.jpg",
            }
        )

        media_html = web_updater.render_article_media(article)

        self.assertIn('official-authority-media', media_html)
        self.assertIn('고용노동부', media_html)
        self.assertIn('https://www.moel.go.kr/favicon.ico', media_html)
        self.assertNotIn('korea_logo_2024.jpg', media_html)

    def test_site_relative_home_thumbnail_is_not_resolved_against_publisher_url(self) -> None:
        article = make_article(
            title="홈 썸네일 캐시 확인",
            lead_text="로컬 캐시 썸네일을 확인합니다.",
            url="https://publisher.example.com/article/123",
        )
        article["image_url"] = "assets/article-thumbnails/cache.jpg?v=test"

        media_html = web_updater.render_article_media(article)

        self.assertIn('src="assets/article-thumbnails/cache.jpg?v=test"', media_html)
        self.assertNotIn('publisher.example.com/article/assets', media_html)

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

    def test_old_primary_candidate_stays_out_of_today_list(self) -> None:
        fresh_daily_issue = make_article(
            title="청년센터 운영 예산 확대 발표",
            lead_text="청년센터 운영 예산과 청년 지원사업 시행 계획을 오늘 발표했다.",
            url="https://example.com/fresh-daily",
            published_date="2026-04-22T09:30:00+09:00",
            importance_score=12,
            clean_score=5,
        )
        old_primary_candidate = make_article(
            title='김 총리, 신임 청년보좌역들과 소통..."참신한 청년정책 만들어달라"',
            lead_text="정부 청년보좌역과 청년정책 소통 자리를 열었다.",
            url="https://www.newsis.com/view/NISX20260418_0003596702",
            published_date="2026-04-16T10:00:00+09:00",
            importance_score=80,
            clean_score=6,
        )
        old_primary_candidate["governance_scope"] = "정부"
        old_primary_candidate["_home_primary_candidate"] = True

        today, _, _ = web_updater.build_home_curated_lists(
            [old_primary_candidate, fresh_daily_issue],
            None,
            self.reference_time,
        )

        today_urls = {article["url"] for article in today}
        self.assertIn(fresh_daily_issue["url"], today_urls)
        self.assertNotIn(old_primary_candidate["url"], today_urls)

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

        self.assertIn("오늘 올라온 청년 기사", page_html)
        self.assertIn("오늘 들어온 자료 · 1건", page_html)
        self.assertIn("날짜를 골라 새 자료 보기", page_html)
        self.assertIn("오늘 들어온 자료", page_html)
        self.assertNotIn("오늘의 청년 이슈를 함께 살펴봅니다", page_html)
        self.assertNotIn("시간의 강", page_html)
        self.assertEqual(page_html.count('data-flow-slot data-flow-period-index="0"'), 24)
        self.assertEqual(page_html.count('data-flow-slot'), 168)
        self.assertIn('data-flow-date="6"', page_html)
        self.assertNotIn('flow-cell-count">0</span>', page_html)
        self.assertEqual(page_html.count('data-flow-id="06c509e269c18556"'), 1)
        self.assertNotIn("지금 모집 중인 청년정책", page_html)
        self.assertNotIn("application-policies", page_html)
        self.assertNotIn("오늘 메인", page_html)
        self.assertNotIn('<span class="home-glance-label">정책</span>', page_html)
        self.assertNotIn('<span class="home-glance-label">참여·회의</span>', page_html)

    def test_home_flow_renders_a_complete_calendar_day_in_one_hourly_row(self) -> None:
        articles = []
        for index, published_date in enumerate(
            [
                "2026-04-22T09:00:00+09:00",
                "2026-04-22T03:00:00+09:00",
                "2026-04-21T20:00:00+09:00",
            ]
        ):
            article = make_article(
                title=f"청년정책 현장 기고 {index}",
                lead_text="청년정책 현장을 해설하는 필자의 글이다.",
                url=f"https://example.com/history-{index}",
                published_date=published_date,
            )
            article["article_type"] = "opinion"
            article["content_direction"] = web_updater.CONTENT_DIRECTION_COLUMN
            articles.append(article)

        page_html = web_updater.build_home_page(
            articles,
            articles,
            {"finished_at": self.reference_time},
            {},
        )

        self.assertIn('data-flow-period-index="0"', page_html)
        self.assertIn('data-flow-period-index="1"', page_html)
        self.assertEqual(page_html.count('data-flow-slot'), 168)
        self.assertIn('날짜를 골라 새 자료 보기', page_html)
        self.assertNotIn('여기까지 읽었습니다', page_html)
        self.assertIn('flow-cell empty future current', page_html)
        self.assertIn('flow-cell-note">현재', page_html)
        self.assertIn('flow-cell-note">예정', page_html)

    def test_home_activity_calendar_keeps_date_only_material_out_of_hourly_timeline(self) -> None:
        timed_article = make_article(
            title="시각이 확인된 오늘 기사",
            lead_text="오늘 시각까지 확인된 청년 기사입니다.",
            url="https://example.com/timed",
            published_date="2026-04-22T09:15:00+09:00",
        )
        date_only_article = make_article(
            title="발행일만 확인된 공식자료",
            lead_text="공식 자료의 발행일은 확인됐지만 시각은 없습니다.",
            url="https://example.com/date-only",
            published_date="2026-04-21",
            source_kind="official",
        )
        date_only_article["is_official_source"] = True

        payload = web_updater.build_home_activity_calendar_payload(
            [timed_article, date_only_article],
            self.reference_time,
        )

        timed = next(item for item in payload["items"] if item["url"] == timed_article["url"])
        date_only = next(item for item in payload["items"] if item["url"] == date_only_article["url"])
        self.assertTrue(timed["has_time"])
        self.assertIsNotNone(timed["timestamp"])
        self.assertFalse(date_only["has_time"])
        self.assertIsNone(date_only["timestamp"])
        self.assertEqual(payload["days"]["2026-04-21"]["count"], 1)

    def test_product_home_includes_monthly_archive_without_hourly_timeline(self) -> None:
        article = make_article(
            title="오늘의 청년정책 기사",
            lead_text="오늘 올라온 청년정책 관련 기사입니다.",
            url="https://example.com/product-home",
            published_date="2026-04-22T09:15:00+09:00",
        )
        payload = web_updater.build_home_activity_calendar_payload([article], self.reference_time)

        page_html = web_updater.build_product_home_page(
            [article],
            [article],
            {"finished_at": self.reference_time},
            {},
            payload,
        )

        self.assertIn('data-home-activity', page_html)
        self.assertIn('data-activity-url="home_activity_calendar.json"', page_html)
        self.assertIn('청년정책 AI 브리핑 보러가기', page_html)
        self.assertNotIn('날짜별 기록', page_html)
        self.assertNotIn('data-home-activity-date-records', page_html)
        self.assertLess(page_html.index('id="today-briefing"'), page_html.index('id="activity-calendar"'))
        self.assertNotIn('id="daily-records"', page_html)
        self.assertNotIn('data-home-activity-timeline', page_html)
        self.assertNotIn('data-home-activity-hour-records', page_html)

        script = web_updater.build_page_script()
        self.assertIn('renderDateList(date)', script)
        self.assertIn('data-home-activity-date-list', script)
        self.assertNotIn('function renderTimeline()', script)

    def test_opinion_menu_requires_a_visible_editorial_marker(self) -> None:
        false_positive = make_article(
            title="청년 주거 지원 예산 발표",
            lead_text="정부는 다음 달부터 지원 기준을 바꾼다고 밝혔다.",
            url="https://example.com/general-news",
        )
        false_positive.update(
            article_type="opinion",
            content_direction=web_updater.CONTENT_DIRECTION_COLUMN,
            categories=["의견"],
        )
        actual_column = make_article(
            title="[칼럼] 청년 주거 지원을 다시 설계하려면",
            lead_text="청년 주거 정책의 조건을 짚어 본다.",
            url="https://example.com/column",
        )
        actual_column.update(
            article_type="opinion",
            content_direction=web_updater.CONTENT_DIRECTION_COLUMN,
        )

        self.assertFalse(web_updater.is_opinion_menu_article(false_positive))
        self.assertTrue(web_updater.is_opinion_menu_article(actual_column))

    def test_home_government_trends_keep_youth_officials_and_skip_generic_officials(self) -> None:
        youth_official = make_article(
            title="[보도자료] 청년정책조정위원회 겸 관계장관회의 개최",
            lead_text="청년 지원사업과 주거 대책, 공약 이행 점검을 논의했다.",
            url="https://www.opm.go.kr/opm/news/press-release.do?mode=view&articleNo=1",
            source_kind="official",
        )
        youth_official["is_official_source"] = True
        youth_official["source"] = "국무조정실 보도자료"
        youth_official["source_name"] = "국무조정실 보도자료"
        youth_official["campaign_political"] = True
        youth_official["substantive_promise"] = True

        generic_official = make_article(
            title="[보도자료] 해외 의장 면담",
            lead_text="양국 협력과 의회 교류를 논의했다.",
            url="https://www.opm.go.kr/opm/news/press-release.do?mode=view&articleNo=2",
            source_kind="official",
            published_date="2026-04-22T09:30:00+09:00",
        )
        generic_official["is_official_source"] = True
        generic_official["source"] = "국무조정실 보도자료"
        generic_official["source_name"] = "국무조정실 보도자료"

        page_html = web_updater.build_home_page(
            [youth_official],
            [generic_official, youth_official],
            {"finished_at": self.reference_time},
            {
                "organization_name": "유스사이드(Youthside)",
                "copyright_text": "© 2026 유스사이드 · 박진감",
                "version_text": "v0.3",
                "email": "hello@example.com",
            },
        )
        self.assertIn(youth_official["title"], page_html)
        self.assertIn('href="official.html">관련 자료 보기</a>', page_html)
        self.assertNotIn(generic_official["title"], page_html)

    def test_home_latest_news_uses_published_date_not_importance_score(self) -> None:
        older_high_score = make_article(
            title="청년 주거 지원 오래된 고점수 기사",
            lead_text="청년 주거 지원을 다룬 기사다.",
            url="https://example.com/older-high-score",
            published_date="2026-04-22T08:00:00+09:00",
            importance_score=100,
        )
        newest_low_score = make_article(
            title="청년센터 운영 최신 저점수 기사",
            lead_text="청년센터 운영 변화를 다룬 기사다.",
            url="https://example.com/newest-low-score",
            published_date="2026-04-22T09:45:00+09:00",
            importance_score=1,
        )
        middle_article = make_article(
            title="청년 취업 지원 중간 기사",
            lead_text="청년 취업 지원을 다룬 기사다.",
            url="https://example.com/middle",
            published_date="2026-04-22T09:00:00+09:00",
            importance_score=50,
        )

        page_html = web_updater.build_home_page(
            [older_high_score, newest_low_score, middle_article],
            [older_high_score, newest_low_score, middle_article],
            {"finished_at": self.reference_time},
            {
                "organization_name": "유스사이드(Youthside)",
                "copyright_text": "© 2026 유스사이드 · 박진감",
                "version_text": "v0.3",
                "email": "hello@example.com",
            },
        )

        self.assertIn("오늘 들어온 자료", page_html)
        self.assertIn("언론 기사", page_html)
        self.assertNotIn("오늘 놓치면 안되는 뉴스 5가지", page_html)
        self.assertLess(page_html.index(newest_low_score["title"]), page_html.index(middle_article["title"]))
        self.assertLess(page_html.index(middle_article["title"]), page_html.index(older_high_score["title"]))

    def test_home_glance_counts_total_latest_news_candidates(self) -> None:
        articles = [
            make_article(
                title=f"청년 뉴스 {index}",
                lead_text="청년 정책과 생활 이슈를 다룬 기사입니다.",
                url=f"https://example.com/total-news-{index}",
                published_date=f"2026-04-22T09:{index:02d}:00+09:00",
            )
            for index in range(6)
        ]

        page_html = web_updater.build_home_page(
            articles,
            articles,
            {"finished_at": self.reference_time},
            {
                "organization_name": "유스사이드(Youthside)",
                "copyright_text": "© 2026 유스사이드 · 박진감",
                "version_text": "v0.3",
                "email": "hello@example.com",
            },
        )

        self.assertIn("오늘 들어온 자료 · 6건", page_html)
        self.assertEqual(page_html.count("data-flow-item data-flow-id="), 6)

    def test_home_flow_combines_routed_content_and_excludes_noise_or_campaign(self) -> None:
        visible_news = make_article(
            title="청년 월세 지원 최신 일반 기사",
            lead_text="청년 월세 지원 신청 소식을 다룬 기사다.",
            url="https://example.com/visible-news",
        )
        official = make_article(
            title="메인에 나오면 안 되는 공식 발표",
            lead_text="청년 지원사업 공식 발표다.",
            url="https://example.com/official",
            source_kind="official",
        )
        official["is_official_source"] = True
        official["source_channel"] = "press_release"
        local_plan = make_article(
            title="부산 청년정책 시행계획 공개",
            lead_text="부산광역시 청년정책 시행계획 원문을 공개했다.",
            url="https://example.com/busan-youth-plan",
            source_kind="local",
            region="부산",
        )
        local_plan["source"] = "부산광역시 청년정책"
        local_plan["source_name"] = "부산광역시 청년정책"
        local_plan["source_channel"] = "policy_plan"
        research = make_article(
            title="청년 주거 실태 연구보고서 발간",
            lead_text="청년 주거 여건을 분석한 연구보고서다.",
            url="https://example.com/youth-housing-report",
            source_kind="research",
        )
        research["article_type"] = "report"
        noisy = make_article(
            title="메인에 나오면 안 되는 노이즈 기사",
            lead_text="청년과 무관한 단순 언급 기사다.",
            url="https://example.com/noisy",
        )
        noisy["is_noise"] = True
        opinion = make_article(
            title="청년정책 현장을 다룬 오피니언",
            lead_text="청년 정책에 대한 칼럼이다.",
            url="https://example.com/opinion",
        )
        opinion["article_type"] = "opinion"
        campaign = make_article(
            title="메인에 나오면 안 되는 시장 후보 청년 공약 유세",
            lead_text="후보가 청년 공약을 앞세워 유세에 나섰다.",
            url="https://example.com/campaign",
        )

        page_html = web_updater.build_home_page(
            [visible_news, official, local_plan, research, noisy, opinion, campaign],
            [visible_news, official, local_plan, research, noisy, opinion, campaign],
            {"finished_at": self.reference_time},
            {
                "organization_name": "유스사이드(Youthside)",
                "copyright_text": "© 2026 유스사이드 · 박진감",
                "version_text": "v0.3",
                "email": "hello@example.com",
            },
        )

        self.assertIn(visible_news["title"], page_html)
        self.assertIn(opinion["title"], page_html)
        self.assertIn('href="opinion.html">관련 자료 보기</a>', page_html)
        self.assertIn(official["title"], page_html)
        self.assertIn('href="official.html">관련 자료 보기</a>', page_html)
        self.assertIn(local_plan["title"], page_html)
        self.assertIn('href="local.html">관련 자료 보기</a>', page_html)
        self.assertIn(research["title"], page_html)
        self.assertIn('href="reports.html">관련 자료 보기</a>', page_html)
        self.assertIn('href="news.html">관련 자료 보기</a>', page_html)
        self.assertIn('flow-kind flow-kind--news">언론 기사</span>', page_html)
        self.assertIn('flow-kind flow-kind--official">정부 공식</span>', page_html)
        self.assertIn('flow-kind flow-kind--local-plan">지역 계획</span>', page_html)
        self.assertIn('flow-kind flow-kind--research">연구·리포트</span>', page_html)
        self.assertNotIn(noisy["title"], page_html)
        self.assertNotIn(campaign["title"], page_html)

    def test_home_government_trends_use_government_page_sections_and_skip_local_sources(self) -> None:
        central_press = make_article(
            title="[보도자료] 청년 고용 지원사업 확대 발표",
            lead_text="Central ministry official youth policy release.",
            url="https://www.moel.go.kr/news/enews/report/enewsView.do?news_seq=1",
            source_kind="official",
        )
        central_press["is_official_source"] = True
        central_press["source"] = "고용노동부 보도자료"
        central_press["source_name"] = "고용노동부 보도자료"

        central_policy_news = make_article(
            title="OFFICIAL CENTRAL POLICY NEWS",
            lead_text="Central official youth policy news without notice or press release marker.",
            url="https://www.korea.kr/news/policyNewsView.do?newsId=1",
            source_kind="official",
        )
        central_policy_news["is_official_source"] = True
        central_policy_news["source"] = "Policy Briefing RSS"
        central_policy_news["source_name"] = "Policy Briefing RSS"

        central_announcement_news = make_article(
            title="국방부, 청년 장병 지원 대책 발표",
            lead_text="서울 용산구에서 중앙부처 청년정책 지원 방안을 설명했다.",
            url="https://example.com/central-announcement-news",
            source_kind="news",
            published_date="2026-04-22T11:00:00+09:00",
        )
        central_announcement_news["source"] = "Example Defense News"
        central_announcement_news["source_name"] = "Example Defense News"

        local_press = make_article(
            title="OFFICIAL LOCAL PRESS RELEASE",
            lead_text="Local government youth support press release.",
            url="https://www.busan.go.kr/nbtnewsBU/1",
            source_kind="local",
            region="부산",
        )
        local_press["source"] = "부산광역시 보도자료"
        local_press["source_name"] = "부산광역시 보도자료"
        local_press["source_channel"] = "press_release"

        local_notice = make_article(
            title="OFFICIAL LOCAL WEBSITE NOTICE",
            lead_text="Local government youth program uploaded notice.",
            url="https://www.gg.go.kr/bbs/boardView.do?bsIdx=1",
            source_kind="local",
            region="경기",
        )
        local_notice["source"] = "경기도 공고"
        local_notice["source_name"] = "경기도 공고"
        local_notice["source_channel"] = "announcement"

        government_hub_news = make_article(
            title="GENERAL GOVERNMENT HUB NEWS",
            lead_text="Youth committee coverage from a news outlet.",
            url="https://example.com/government-hub-news",
        )
        government_hub_news["is_hub_candidate"] = True
        government_hub_news["governance_scope"] = "정부"
        government_hub_news["hub_topics"] = ["청년자문단"]
        government_hub_news["governance_activity_types"] = ["회의"]

        regional_hub_news = make_article(
            title="GENERAL REGIONAL HUB NEWS",
            lead_text="Local youth network coverage from a news outlet.",
            url="https://example.com/regional-hub-news",
            region="대구",
        )
        regional_hub_news["is_hub_candidate"] = True
        regional_hub_news["governance_scope"] = "지자체"
        regional_hub_news["hub_topics"] = ["청년네트워크"]
        regional_hub_news["governance_activity_types"] = ["회의"]

        articles = [
            central_press,
            central_policy_news,
            central_announcement_news,
            local_press,
            local_notice,
            government_hub_news,
            regional_hub_news,
        ]
        page_html = web_updater.build_home_page(
            articles,
            articles,
            {"finished_at": self.reference_time},
            {
                "organization_name": "Youthside",
                "copyright_text": "Copyright",
                "version_text": "v0.3",
                "email": "hello@example.com",
            },
        )

        self.assertIn(central_press["title"], page_html)
        self.assertIn(local_press["title"], page_html)
        self.assertIn('href="official.html">관련 자료 보기</a>', page_html)
        self.assertIn('href="local.html">관련 자료 보기</a>', page_html)
        self.assertNotIn(central_policy_news["title"], page_html)
        self.assertIn(local_notice["title"], page_html)
        self.assertNotIn(central_announcement_news["title"], page_html)

    def test_home_categories_and_flow_use_the_current_calendar_day(self) -> None:
        recent_housing = make_article(
            title="청년 월세 신청자 모집",
            lead_text="청년 월세 신청자를 모집한다.",
            url="https://example.com/recent-housing",
            published_date="2026-04-22T09:00:00+09:00",
            topic_tags=["주거", "모집"],
        )
        recent_housing_second = make_article(
            title="청년 주택 지원 접수",
            lead_text="청년 주택 지원 접수를 안내했다.",
            url="https://example.com/recent-housing-second",
            published_date="2026-04-21T12:00:00+09:00",
            topic_tags=["주거"],
        )
        recent_job = make_article(
            title="청년 일자리 안내",
            lead_text="청년 일자리 지원사업을 안내했다.",
            url="https://example.com/recent-job",
            published_date="2026-04-21T11:00:00+09:00",
            topic_tags=["취업"],
        )
        outside_window = make_article(
            title="오래된 청년 자산형성 안내",
            lead_text="오래된 청년 자산형성 지원 안내다.",
            url="https://example.com/old-finance",
            published_date="2026-04-20T08:30:00+09:00",
            topic_tags=["금융"],
        )

        page_html = web_updater.build_home_page(
            [recent_housing, recent_housing_second, recent_job, outside_window],
            [recent_housing, recent_housing_second, recent_job, outside_window],
            {"finished_at": self.reference_time},
            {
                "organization_name": "유스사이드(Youthside)",
                "copyright_text": "© 2026 유스사이드 · 박진감",
                "version_text": "v0.3",
                "email": "hello@example.com",
            },
        )

        self.assertIn('<span class="flow-topic">#주거</span>', page_html)
        self.assertIn('<span class="flow-topic">#취업</span>', page_html)
        self.assertNotIn("최근 48시간 기준입니다.", page_html)


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
        self.assertNotIn('id="about-info"', page_html)
        self.assertNotIn("사이트 소개 보기", page_html)
        self.assertNotIn("무료로 운영하며", page_html)
        self.assertNotIn('>이용 안내</span>', page_html)
        self.assertNotIn('>제작자 연락</a>', page_html)
        self.assertNotIn("유스사이드 preview", page_html)

        footer_html = web_updater.build_footer_note(
            {
                "organization_name": "유스사이드(Youthside)",
                "copyright_text": "© 2026 유스사이드 · 박진감",
                "version_text": "v0.3",
                "email": "hello@example.com",
            }
        )
        self.assertIn("유스사이드 · 박진감", footer_html)
        self.assertIn("청년정책 실무자와 활동가가 변화 판단과 정책제안에 쓸 수 있는 맥락을 제공합니다.", footer_html)
        self.assertIn("관련 사이트", footer_html)

        self.assertIn("청년투게더", footer_html)
        self.assertIn("적재적소 연구소 운영", footer_html)
        self.assertIn("운영 목적 :", footer_html)
        self.assertIn("정보 기준 :", footer_html)
        self.assertIn("확인 안내 :", footer_html)
        self.assertNotIn("v0.3", footer_html)

        self.assertNotIn("youthside-lockup.svg", footer_html)
        self.assertNotIn("youthside-mark.svg", footer_html)
        self.assertNotIn("youthside-wordmark-compass.svg", footer_html)

        original_candidates = web_updater.YOUTHSIDE_FOOTER_IMAGE_CANDIDATES
        try:
            web_updater.YOUTHSIDE_FOOTER_IMAGE_CANDIDATES = ("assets/branding/youth-together-mark.svg",)
            footer_with_image = web_updater.build_footer_note({})
        finally:
            web_updater.YOUTHSIDE_FOOTER_IMAGE_CANDIDATES = original_candidates
        self.assertIn("site-footer-body has-brand-image", footer_with_image)
        self.assertIn("assets/branding/youth-together-mark.svg?v=", footer_with_image)
        self.assertLess(
            footer_with_image.index("site-footer-brand-image"),
            footer_with_image.index("site-footer-info"),
        )

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
            source_kind="local",
            region="부산",
        )
        local_policy["source_channel"] = "press_release"
        official_policy = make_article(
            title="고용노동부 청년 지원사업 발표",
            lead_text="정부가 청년 고용 지원사업 추진 계획을 발표했다.",
            url="https://example.com/official-policy",
            source_kind="official",
        )
        official_policy["is_official_source"] = True
        official_policy["source"] = "고용노동부 보도자료"
        official_policy["source_name"] = "고용노동부 보도자료"
        official_policy["source_channel"] = "press_release"

        status = {"finished_at": self.reference_time}

        news_html = web_updater.build_news_page(
            [general_news, pure_campaign, substantive_promise, local_policy],
            status,
        )
        official_html = web_updater.build_official_page(
            [general_news, pure_campaign, substantive_promise, local_policy, official_policy],
            status,
        )
        election_html = web_updater.build_election_page(
            [general_news, pure_campaign, substantive_promise, local_policy],
            status,
        )

        self.assertIn(general_news["title"], news_html)
        self.assertNotIn(local_policy["title"], news_html)
        self.assertNotIn(pure_campaign["title"], news_html)
        self.assertNotIn(substantive_promise["title"], news_html)

        self.assertIn(official_policy["title"], official_html)
        self.assertNotIn(local_policy["title"], official_html)
        self.assertNotIn(general_news["title"], official_html)
        self.assertNotIn(pure_campaign["title"], official_html)
        self.assertNotIn(substantive_promise["title"], official_html)
        self.assertIn("중앙정부 보도자료", official_html)
        self.assertIn("기본·시행계획", official_html)

        self.assertIn(pure_campaign["title"], election_html)
        self.assertIn(substantive_promise["title"], election_html)
        self.assertIn("선거 기사", election_html)
        self.assertIn("정책 공약", election_html)
        self.assertIn("<h3>선거·공약 필터</h3>", election_html)
        self.assertIn('class="filter-stack filter-stack-map"', election_html)
        self.assertIn('class="filter-control-column"', election_html)
        self.assertIn('class="filter-region-map-svg"', election_html)
        self.assertEqual(election_html.count('class="filter-region-map-region"'), len(web_updater.LOCAL_YOUTH_PLAN_REGIONS))
        self.assertNotIn(general_news["title"], election_html)

    def test_government_trends_includes_all_central_ministries(self) -> None:
        page_html = web_updater.build_official_page([], {"finished_at": self.reference_time})

        self.assertEqual(len(web_updater.CENTRAL_MINISTRY_AUTHORITIES), 19)
        for authority in web_updater.CENTRAL_MINISTRY_AUTHORITIES:
            self.assertIn(f'data-policy-authority="{authority}"', page_html)

        self.assertIn('data-policy-authority="금융위원회"', page_html)
        self.assertIn("청년정책 기본계획·시행계획", page_html)
        self.assertIn('data-official-view-tab="releases"', page_html)
        self.assertIn('data-official-view-tab="plans"', page_html)
        self.assertIn('data-official-view-panel="plans" hidden', page_html)
        self.assertIn('function setOfficialView(activeView)', web_updater.BASE_SCRIPT)

    def test_local_government_trends_page_separates_field_news_from_official_materials(self) -> None:
        local_announcement = make_article(
            title="서울시, 청년 주거 지원 정책 발표",
            lead_text="서울시가 청년 주거 안정을 위한 월세 지원 정책을 발표했다.",
            url="https://example.com/news/youth-policy",
            source_kind="news",
            region="서울",
        )

        local_plan = make_article(
            title=f"Seoul youth policy {web_updater.LOCAL_POLICY_PLAN_KEYWORDS[0]}",
            lead_text="Seoul city published a youth policy plan document.",
            url="https://www.seoul.go.kr/plan/youth-policy",
            source_kind="local",
        )
        local_plan["source"] = "Seoul Metropolitan Government"
        local_plan["source_name"] = "Seoul Metropolitan Government"
        local_plan["region"] = "서울"

        central_policy = make_article(
            title="Central ministry youth policy official announcement",
            lead_text="A central ministry published a youth policy announcement.",
            url="https://www.moel.go.kr/news/youth-policy",
            source_kind="official",
        )
        central_policy["is_official_source"] = True
        central_policy["source"] = "Ministry of Employment and Labor"
        central_policy["source_name"] = "Ministry of Employment and Labor"

        page_html = web_updater.build_local_government_trends_page(
            [local_announcement, local_plan, central_policy],
            {"finished_at": self.reference_time},
        )

        self.assertIn(local_announcement["title"], page_html)
        self.assertNotIn(local_plan["title"], page_html)
        self.assertNotIn(central_policy["title"], page_html)
        self.assertIn('href="local.html"', page_html)
        self.assertIn('href="hub.html"', page_html)
        self.assertIn("지자체의 공식 발표라고 해석하지 않습니다.", page_html)
        self.assertNotIn('class="local-map-region"', page_html)

    def test_purpose_led_navigation_and_local_materials_page_keep_official_boundary(self) -> None:
        local_press = make_article(
            title="부산시 청년 주거 지원사업 발표",
            lead_text="부산광역시가 청년 주거 지원사업을 공식 발표했다.",
            url="https://www.busan.go.kr/youth/press/1",
            source_kind="local",
            region="부산",
        )
        local_press["source"] = "부산광역시 보도자료"
        local_press["source_name"] = "부산광역시 보도자료"
        local_press["source_channel"] = "press_release"
        regional_news = make_article(
            title="부산 청년정책 현장 반응",
            lead_text="지역 현장에서 청년정책 변화에 대한 반응을 전했다.",
            url="https://example.com/busan-youth-news",
            region="부산",
        )

        materials_html = web_updater.build_local_materials_page(
            [local_press, regional_news], {"finished_at": self.reference_time}
        )
        notices_html = web_updater.build_notices_page([], {"finished_at": self.reference_time})
        institution_html = web_updater.build_institution_page()

        labels = dict(web_updater.NAV_ITEMS)
        self.assertEqual(len(labels), 8)
        self.assertEqual(
            web_updater.TOP_NAV_ITEMS,
            [
                ("index.html", "홈"),
                ("news.html", "언론 기사"),
                ("trends.html", "정책 동향"),
                ("opinion.html", "기고·칼럼·오피니언"),
                ("official.html", "정부 부처 자료실"),
                ("local.html", "지자체 자료실"),
                ("reports.html", "논문·연구·리포트"),
                ("tools.html", "정부조사·통계"),
                ("hub.html", "현장 목소리"),
            ],
        )
        self.assertEqual(labels["news.html"], "언론 기사")
        self.assertEqual(labels["trends.html"], "정책 동향")
        self.assertEqual(labels["opinion.html"], "기고·칼럼·오피니언")
        self.assertEqual(labels["official.html"], "정부 부처 자료실")
        self.assertEqual(labels["local.html"], "지자체 자료실")
        self.assertEqual(labels["reports.html"], "논문·연구·리포트")
        self.assertEqual(labels["tools.html"], "정부조사·통계")
        self.assertNotIn("guide.html", labels)
        self.assertEqual(labels["hub.html"], "현장 목소리")
        self.assertNotIn("institution.html", labels)
        self.assertNotIn("index.html#interest-builder", labels)
        self.assertIn(local_press["title"], materials_html)
        self.assertNotIn(regional_news["title"], materials_html)
        self.assertNotIn("자료실 수록 원칙", materials_html)
        self.assertNotIn("수집·갱신 기준", materials_html)
        self.assertIn("공고 확인 원칙", notices_html)
        self.assertIn("기관 분석 레이더", institution_html)
        self.assertIn("현재는 소개용 임시 페이지", institution_html)

    def test_mobile_navigation_uses_three_primary_links_and_full_menu_sheet(self) -> None:
        bottom_nav = web_updater.render_bottom_nav("official.html")
        mobile_menu = web_updater.render_mobile_menu("official.html")

        self.assertEqual(len(web_updater.BOTTOM_NAV_ITEMS), 3)
        self.assertEqual(bottom_nav.count("<a "), 3)
        self.assertIn('data-mobile-menu-open="true"', bottom_nav)
        self.assertIn("<span>전체</span>", bottom_nav)
        self.assertIn('class="active" href="official.html"', bottom_nav)
        self.assertIn(
            'class="active" type="button"',
            web_updater.render_bottom_nav("opinion.html"),
        )
        self.assertEqual(mobile_menu.count('<a class="mobile-menu-link'), 9)
        self.assertIn('data-mobile-menu-close="true"', mobile_menu)
        self.assertIn("@media (max-width: 1180px)", web_updater.DESIGN_OVERHAUL_CSS)
        tablet_rules = web_updater.DESIGN_OVERHAUL_CSS.split("@media (max-width: 1180px)", 1)[1]
        self.assertIn(".side-nav {\n      display: none;", tablet_rules)
        self.assertIn("grid-template-columns: repeat(5", tablet_rules)

    def test_mobile_menu_script_supports_all_triggers_and_keeps_keyboard_focus_in_dialog(self) -> None:
        script = web_updater.MOBILE_MENU_SCRIPT

        self.assertIn("querySelectorAll('[data-mobile-menu-open]')", script)
        self.assertIn("setExpanded", script)
        self.assertIn("event.key !== 'Tab'", script)
        self.assertIn("lastElement.focus()", script)
        self.assertIn("firstElement.focus()", script)

    def test_home_hero_uses_balanced_type_scale_without_redundant_accent_badge(self) -> None:
        css = web_updater.DESIGN_OVERHAUL_CSS

        self.assertIn("Hero 6:3:1 hierarchy", css)
        self.assertIn("grid-template-columns: minmax(0, 7fr) minmax(270px, 3fr);", css)
        self.assertNotIn(".flow-hero .eyebrow {", css)
        self.assertIn("font-size: clamp(2.12rem, 3.4vw, 3.72rem);", css)
        self.assertIn("line-height: 1.04;", css)
        self.assertIn("background: var(--sky);", css)
        mobile_rules = css.split("@media (max-width: 760px)", 1)[1]
        self.assertIn("font-size: clamp(1.6rem, 6.4vw, 2.04rem);", mobile_rules)

    def test_seven_menu_router_separates_news_opinion_research_and_official_sources(self) -> None:
        general_news = make_article(
            title="청년 고용시장 변화 현장 보도",
            lead_text="청년 구직자와 기업의 현장 반응을 취재했다.",
            url="https://example.com/news",
        )
        opinion = make_article(
            title="청년정책, 당사자의 시간을 기준으로 다시 설계해야",
            lead_text="청년정책의 집행 방식을 제안하는 필자의 칼럼이다.",
            url="https://example.com/opinion",
        )
        opinion["article_type"] = "opinion"
        opinion["content_direction"] = web_updater.CONTENT_DIRECTION_COLUMN
        research = make_article(
            title="청년 주거 실태조사 분석 보고서",
            lead_text="청년 1인가구의 주거비와 정책 수요를 분석한 연구 결과다.",
            url="https://example.com/report",
        )
        research["youth_research_signal"] = True
        research["content_direction"] = web_updater.CONTENT_DIRECTION_INSIGHT
        central = make_article(
            title="고용노동부 청년고용 보도자료",
            lead_text="청년고용 지원 정책을 발표했다.",
            url="https://www.moel.go.kr/news/press/1",
            source_kind="official",
        )
        central["is_official_source"] = True
        central["source_channel"] = "press_release"
        local = make_article(
            title="서울시 청년정책 보도자료",
            lead_text="서울시가 청년정책 시행계획을 발표했다.",
            url="https://www.seoul.go.kr/news/press/1",
            source_kind="local",
            region="서울",
        )
        local["source_channel"] = "press_release"
        status = {"finished_at": self.reference_time}
        records = [general_news, opinion, research, central, local]

        news_html = web_updater.build_news_page(records, status)
        opinion_html = web_updater.build_opinion_page(records, status)
        reports_html = web_updater.build_reports_page(records, status)
        official_html = web_updater.build_official_page(records, status)
        local_html = web_updater.build_local_materials_page(records, status)

        self.assertIn(general_news["title"], news_html)
        self.assertNotIn(opinion["title"], news_html)
        self.assertNotIn(research["title"], news_html)
        self.assertIn(opinion["title"], opinion_html)
        self.assertNotIn(general_news["title"], opinion_html)
        self.assertNotIn('id="filters"', opinion_html)
        self.assertNotIn('filter-region-map-svg', opinion_html)
        self.assertNotIn('data-news-filter-root="opinion"', opinion_html)
        self.assertIn(research["title"], reports_html)
        self.assertNotIn(opinion["title"], reports_html)
        self.assertNotIn('id="filters"', reports_html)
        self.assertNotIn('filter-region-map-svg', reports_html)
        self.assertNotIn('data-news-filter-root="reports"', reports_html)
        self.assertIn(central["title"], official_html)
        self.assertNotIn(local["title"], official_html)
        self.assertIn(local["title"], local_html)
        self.assertNotIn(central["title"], local_html)

    def test_research_menu_does_not_capture_ordinary_insight_or_recruitment_news(self) -> None:
        analytical_news = make_article(
            title="청년 전월세 부담 커져…현장 목소리 들어보니",
            lead_text="통계와 조사 결과를 인용해 청년 주거 문제를 다룬 일반 기사다.",
            url="https://example.com/analytical-news",
        )
        analytical_news["youth_research_signal"] = True
        analytical_news["content_direction"] = web_updater.CONTENT_DIRECTION_INSIGHT
        recruitment_news = make_article(
            title="울산 동구, 제4기 청년정책협의체 위원 모집",
            lead_text="청년정책협의체 위원을 모집한다.",
            url="https://example.com/recruitment",
        )
        recruitment_news["content_direction"] = web_updater.CONTENT_DIRECTION_INSIGHT
        survey_plan_news = make_article(
            title="정부, 청년 주거 실태조사 실시",
            lead_text="정부가 향후 실태조사를 추진한다는 계획을 발표했다.",
            url="https://example.com/survey-plan",
        )
        survey_plan_news["youth_research_signal"] = True
        survey_plan_news["content_direction"] = web_updater.CONTENT_DIRECTION_INSIGHT

        self.assertFalse(web_updater.is_research_report_menu_article(analytical_news))
        self.assertFalse(web_updater.is_research_report_menu_article(recruitment_news))
        self.assertFalse(web_updater.is_research_report_menu_article(survey_plan_news))
        self.assertTrue(web_updater.is_general_news_menu_article(analytical_news))
        self.assertTrue(web_updater.is_general_news_menu_article(recruitment_news))
        self.assertTrue(web_updater.is_general_news_menu_article(survey_plan_news))

    def test_research_menu_keeps_long_lived_indexed_research_records(self) -> None:
        indexed_research = make_article(
            title="청년정책 참여 경험에 관한 연구",
            lead_text="한국정책연구 · journal article",
            url="https://doi.org/10.1234/youth-policy",
            published_date="2020-01-20T00:00:00+09:00",
        )
        indexed_research.update(source_kind="research", article_type="research")

        page_html = web_updater.build_reports_page(
            [indexed_research],
            {"finished_at": "2026-08-26T02:00:00+09:00"},
        )

        self.assertIn(indexed_research["title"], page_html)
        self.assertIn("최근 10년 자료까지", page_html)

    def test_statistics_menu_requires_a_direct_youth_statistic_from_its_authority(self) -> None:
        incidental_survey_mention = make_article(
            title="대한민국 2045 전략수립위원회 2차 회의",
            lead_text="일반국민·청년·전문가 설문조사 결과를 전략 논의에 반영한다.",
            url="https://www.opm.go.kr/press/strategy",
            source_kind="official",
        )
        incidental_survey_mention.update(
            is_official_source=True,
            source="국무조정실 보도자료",
            source_name="국무조정실 보도자료",
        )
        youth_supplementary_survey = make_article(
            title="2025년 5월 청년층 부가조사 결과",
            lead_text="청년층 고용률과 첫 일자리 소요기간을 발표했다.",
            url="https://kostat.go.kr/board.es?bid=210&list_no=437676",
            source_kind="official",
        )
        youth_supplementary_survey.update(
            is_official_source=True,
            source="통계청 보도자료",
            source_name="통계청 보도자료",
        )

        self.assertFalse(web_updater.is_government_statistics_menu_article(incidental_survey_mention))
        self.assertTrue(web_updater.is_government_statistics_menu_article(youth_supplementary_survey))

    def test_public_archive_window_is_one_year_and_notice_page_declares_that_scope(self) -> None:
        notices_html = web_updater.build_notices_page([], {"finished_at": self.reference_time})
        self.assertEqual(web_updater.PUBLIC_ARCHIVE_WINDOW_DAYS, 365)
        self.assertEqual(web_updater.NEWS_WINDOW_DAYS, 365)
        self.assertIn("최근 1년 공고·신청", notices_html)
        self.assertIn("공식 공고에 적힌 자격과 기간이 기준입니다.", notices_html)

    def test_naive_article_dates_are_treated_as_korea_time_for_archive_filtering(self) -> None:
        article = make_article(
            title="날짜 표준화 확인 기사",
            lead_text="청년 정책 관련 기사입니다.",
            url="https://example.com/naive-date",
            published_date="2026-04-22T09:00:00",
        )

        filtered = web_updater.filter_recent_articles([article], self.reference_time, 24)

        self.assertEqual(filtered, [article])

    def test_local_materials_keeps_official_records_with_missing_dates_separate(self) -> None:
        local_material = make_article(
            title="청년 면접정장 대여 지원",
            lead_text="지자체 청년포털의 공식 정책 안내입니다.",
            url="https://youth.incheon.go.kr/job/suit.jsp",
            source_kind="local",
            region="인천",
            published_date="",
        )
        local_material["source"] = "인천광역시 청년포털"
        local_material["source_name"] = "인천광역시 청년포털"
        local_material["source_channel"] = "press_release"

        page_html = web_updater.build_local_materials_page(
            [local_material], {"finished_at": self.reference_time}
        )

        self.assertIn("게시일 미확인 공식 자료", page_html)
        self.assertIn(local_material["title"], page_html)

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

    def test_news_page_renders_topic_tags_and_topic_filter(self) -> None:
        article = make_article(
            title="파주시, 청년월세 지원금 신청자 모집",
            lead_text="파주시가 청년 주거 안정을 위해 월세 지원금 신청자를 모집한다.",
            url="https://example.com/topic-news",
            region="경기",
        )
        article["topic_tags"] = ["주거", "모집"]
        article["categories"] = ["청년은 지금", "지역 이슈"]

        page_html = web_updater.build_news_page([article], {"finished_at": self.reference_time})

        self.assertIn('class="section-card filter-panel news-filter-panel news-filter-split"', page_html)
        self.assertIn('>날짜별 기사 기록</h3>', page_html)
        self.assertIn('data-news-range-calendar', page_html)
        self.assertIn('data-news-calendar-month="2026-04"', page_html)
        self.assertIn('data-news-filter-apply', page_html)
        self.assertIn('data-news-filter-reset', page_html)
        self.assertNotIn('class="filter-region-map-svg"', page_html)
        self.assertNotIn('data-filter-group="region"', page_html)
        self.assertNotIn('data-filter-group="direction"', page_html)
        self.assertIn('data-filter-group="topic" data-filter-value="주거"', page_html)
        self.assertIn('>키워드 검색</label>', page_html)
        self.assertIn('data-news-hour-start', page_html)
        self.assertIn('data-news-hour-end', page_html)
        self.assertNotIn('>기간 설정</span>', page_html)
        self.assertIn('data-article-topics="주거|모집"', page_html)
        self.assertIn(">#주거</button>", page_html)
        self.assertIn('<div class="badge-row"><span class="badge">', page_html)
        self.assertIn(">주거</span>", page_html)
        self.assertNotIn('<div class="article-meta-tags"><span class="meta-pill primary">주거</span>', page_html)
        self.assertNotIn(">오늘 이슈</span>", page_html)

    def test_news_page_uses_shared_archive_cards_and_original_source_links(self) -> None:
        article = make_article(
            title="청년 주거 지원 접수 일정 안내",
            lead_text="청년 주거 지원사업의 접수 일정과 대상 기준을 안내하는 보도입니다.",
            url="https://example.com/original-news-source",
            region="서울",
        )

        page_html = web_updater.build_news_page([article], {"finished_at": self.reference_time})

        self.assertIn('class="article-grid"', page_html)
        self.assertIn('class="article-card', page_html)
        self.assertIn('href="https://example.com/original-news-source" target="_blank"', page_html)
        self.assertNotIn('class="editorial-feed-item"', page_html)
        self.assertNotIn('href="briefing-', page_html)

    def test_non_home_intro_uses_shared_readability_tokens(self) -> None:
        css = web_updater.READABILITY_REFINEMENT_CSS

        self.assertIn('body:not([data-page="index.html"]) .page-intro-card', css)
        self.assertIn('background: #ffffff;', css)
        self.assertIn('border: 1px solid #dce4ed;', css)
        self.assertIn('background: #fff0e8;', css)
        self.assertIn('body:not([data-page="index.html"]) .page-intro-card + .section', css)


class ProductRebuildTests(unittest.TestCase):
    def test_product_home_prioritizes_first_actions_and_editorial_briefing(self) -> None:
        article = make_article(
            title="서울 청년 주거 지원 시행계획 발표",
            lead_text="서울시가 청년 주거 지원 시행계획을 발표했다.",
            url="https://example.com/seoul-housing",
            published_date="2026-08-08T09:00:00+09:00",
            region="서울",
            topic_tags=["주거"],
        )
        page_html = web_updater.build_product_home_page(
            [article],
            [article],
            {"state": "completed", "finished_at": "2026-08-08T09:00:00+09:00"},
            {"email": "hello@example.com"},
        )

        self.assertNotIn('class="civic-site-title"', page_html)
        self.assertNotIn('class="civic-eyebrow">정책 최신 헤드라인</p>', page_html)
        self.assertNotIn('오늘 먼저 볼 변화', page_html)
        self.assertNotIn('class="civic-story-kicker">', page_html)
        self.assertNotIn('주요 최신 뉴스', page_html)
        self.assertNotIn('월간 기록', page_html)
        self.assertNotIn("소식을<br>", page_html)
        self.assertNotIn('class="civic-home-hero"', page_html)
        self.assertNotIn("전체 아카이브", page_html)
        self.assertNotIn("날짜별 자료", page_html)
        self.assertNotIn('class="civic-task-strip"', page_html)
        self.assertIn('id="today-briefing"', page_html)
        self.assertIn('id="activity-calendar"', page_html)
        self.assertLess(page_html.index('<section class="civic-ai-brief-home"'), page_html.index('id="today-briefing"'))
        self.assertNotIn('id="article-discovery"', page_html)
        self.assertIn("청년정책 AI 브리핑 보러가기", page_html)
        self.assertNotIn("서울 청년 주거 지원 시행계획 발표", page_html)
        self.assertIn('href="trends.html#brief-', page_html)
        self.assertNotIn('id="editorial-standard"', page_html)
        self.assertNotIn("자료를 고르는 기준을 함께 공개합니다.", page_html)
        self.assertNotIn('id="interest-builder"', page_html)
        self.assertNotIn("맞춤 변화 미리보기", page_html)
        self.assertNotIn('id="weekly-briefing"', page_html)
        self.assertNotIn("기관 협업", page_html)

    def test_home_latest_article_links_open_the_original_source(self) -> None:
        lead = make_article(
            title="중요 정책 발표",
            lead_text="중요 정책 발표 내용입니다.",
            url="https://example.com/lead-source",
            importance_score=30,
        )
        supporting = make_article(
            title="최근 언론 기사",
            lead_text="최근 언론 기사 요약입니다.",
            url="https://example.com/supporting-source",
            importance_score=10,
        )

        page_html = web_updater.build_product_home_page(
            [lead, supporting],
            [lead, supporting],
            {"state": "completed", "finished_at": "2026-08-08T09:00:00+09:00"},
            {"email": "hello@example.com"},
        )

        self.assertIn(
            'href="https://example.com/supporting-source" target="_blank" rel="noreferrer" data-event="home_supporting_story_open"',
            page_html,
        )
        self.assertNotIn('href="briefing-', page_html)

    def test_article_share_uses_native_share_with_copy_fallback(self) -> None:
        script = web_updater.build_product_event_script()

        self.assertIn("navigator.share", script)
        self.assertIn("청년투게더에서 원문과 관련 자료를 확인해 보세요.", script)
        self.assertIn("카카오톡 대화창에 붙여넣으세요.", script)

    def test_product_detail_keeps_source_metadata_without_automatic_commentary(self) -> None:
        article = make_article(
            title="청년 주거 지원 시행계획 발표",
            lead_text="서울시가 청년 주거 지원 시행계획을 발표했다.",
            url="https://example.com/seoul-housing",
            published_date="2026-08-08T09:00:00+09:00",
            region="서울",
            topic_tags=["주거"],
        )

        page_html = web_updater.build_product_detail_page(
            article,
            [],
            {"finished_at": "2026-08-08T10:00:00+09:00"},
        )

        self.assertIn("자료 확인", page_html)
        self.assertIn("원문 열기", page_html)
        self.assertIn("이 사건의 자료 흐름", page_html)
        self.assertNotIn("왜 지금 확인해야 하나", page_html)
        self.assertNotIn("현장에서 무엇이 막히는가", page_html)
        self.assertNotIn("다음으로 확인할 것", page_html)
        self.assertNotIn("편집 기준과 한계", page_html)

    def test_policy_event_card_and_detail_use_typed_source_relations(self) -> None:
        article = make_article(
            title="청년 주거 지원 종합대책 발표",
            lead_text="국토교통부가 청년 주거 지원 종합대책을 발표했다.",
            url="https://example.com/official-release",
            published_date="2026-08-08T09:00:00+09:00",
            region="전국",
            topic_tags=["주거"],
        )
        article.update(
            source_kind="official",
            is_official_source=True,
            story_cluster_role="official_release",
            policy_event_items=[
                {
                    "title": "청년 주거 지원 종합대책, 월세 지원 확대",
                    "url": "https://example.com/news-coverage",
                    "source": "테스트뉴스",
                    "published_date": "2026-08-08T10:00:00+09:00",
                    "relation_type": "news_coverage",
                },
                {
                    "title": "청년 주거 지원 종합대책 시행계획 공고",
                    "url": "https://example.com/official-follow-up",
                    "source": "국토교통부",
                    "published_date": "2026-08-12T09:00:00+09:00",
                    "relation_type": "official_follow_up",
                },
            ],
        )

        card_html = web_updater.render_article_card(article)
        detail_html = web_updater.build_product_detail_page(article, article["policy_event_items"], {})

        self.assertIn("이 사건의 자료 흐름 · 언론 보도 1건 · 후속 공식자료 1건", card_html)
        self.assertIn("2026-08-08 10:00", card_html)
        self.assertIn("이 사건의 자료 흐름", detail_html)
        self.assertIn('href="https://example.com/news-coverage" target="_blank"', detail_html)
        self.assertNotIn('href="briefing-', detail_html)

    def test_policy_trends_are_separate_from_news_and_require_typed_relations(self) -> None:
        official = make_article(
            title="청년 주거 지원 종합대책 발표",
            lead_text="국토교통부가 청년 주거 지원 종합대책을 발표했다.",
            url="https://example.com/official-release",
            published_date="2026-08-08T09:00:00+09:00",
            region="전국",
            topic_tags=["주거"],
        )
        official.update(
            source_kind="official",
            is_official_source=True,
            story_cluster_role="official_release",
            policy_event_items=[{
                "title": "청년 주거 지원 종합대책, 월세 지원 확대",
                "url": "https://example.com/news-coverage",
                "source": "테스트뉴스",
                "published_date": "2026-08-08T10:00:00+09:00",
                "relation_type": "news_coverage",
            }],
        )

        trends_html = web_updater.build_policy_trends_page([official], {"finished_at": "2026-08-08T12:00:00+09:00"})
        news_html = web_updater.build_news_page([official], {"finished_at": "2026-08-08T12:00:00+09:00"})

        self.assertIn("청년정책 AI 브리핑", trends_html)
        self.assertIn(official["title"], trends_html)
        self.assertIn("08:00–10:00", trends_html)
        self.assertNotIn('id="official-story-bundles"', news_html)

    def test_operator_page_states_identity_standard_and_limits(self) -> None:
        page_html = web_updater.build_product_about_page({"email": "hello@example.com"})

        self.assertIn("박진감", page_html)
        self.assertIn("전직 정부 공무원(6급)", page_html)
        self.assertIn("정보를 더 쌓기보다 판단 순서를 만듭니다", page_html)
        self.assertIn("완전하거나 실시간이라고 말하지 않습니다", page_html)
        self.assertIn("mailto:hello@example.com", page_html)

    def test_generated_page_has_unique_description_and_skip_link(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            output = Path(tempdir) / "index.html"
            web_updater.write_page(
                output,
                "청년투게더",
                "index.html",
                "<h1>테스트</h1>",
                {},
                {},
            )
            page_html = output.read_text(encoding="utf-8")

        self.assertIn('<meta name="description" content="청년정책의 변화와 현장 소식을 판단과 제안에 쓸 수 있게 연결합니다.">', page_html)
        self.assertIn('<title>적재적소 브리프</title>', page_html)
        self.assertIn('class="skip-link"', page_html)
        self.assertIn('<main class="shell" id="main-content"', page_html)
        self.assertNotIn('visitor_id:', page_html)


if __name__ == "__main__":
    unittest.main()

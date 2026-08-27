from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "public-site" / "scripts" / "web_updater.py"
SCRIPT_DIR = str(SCRIPT_PATH.parent)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

spec = importlib.util.spec_from_file_location("test_web_updater_local_module", SCRIPT_PATH)
web_updater = importlib.util.module_from_spec(spec)
assert spec is not None and spec.loader is not None
spec.loader.exec_module(web_updater)


def make_article(
    *,
    title: str,
    lead_text: str,
    url: str,
    source_kind: str = "news",
    region: str = "",
    source_channel: str = "",
) -> dict:
    return {
        "url": url,
        "title": title,
        "lead_text": lead_text,
        "summary": lead_text,
        "source": "테스트 출처",
        "source_name": "테스트 출처",
        "published_date": "2026-05-01T09:00:00+09:00",
        "issue_tags": [],
        "location_tags": [],
        "display_badges": [],
        "is_official_source": source_kind in {"official", "local"},
        "is_noise": False,
        "article_type": "news",
        "source_kind": source_kind,
        "source_channel": source_channel,
        "topic_tags": [],
        "region": region,
        "governance_scope": None,
        "importance_score": 10,
        "clean_score": 4,
        "editorial_decision": "default",
        "editorial_is_highlighted": False,
    }


class LocalGovernmentTrendsPageTests(unittest.TestCase):
    def test_local_page_uses_new_three_part_model(self) -> None:
        local_news = make_article(
            title="서울시, 청년 월세 지원 확대 발표",
            lead_text="서울시가 청년 주거비 부담을 줄이기 위한 월세 지원 정책을 공개했다.",
            url="https://example.com/local-news",
            source_kind="news",
            region="서울",
        )
        local_press = make_article(
            title="청년 일자리 보도자료",
            lead_text="서울특별시 청년 일자리 지원사업 보도자료입니다.",
            url="https://www.seoul.go.kr/news/youth-job",
            source_kind="local",
            region="서울",
            source_channel="press_release",
        )
        local_press["region_name"] = "서울"
        plan_document = make_article(
            title="서울 청년정책 기본계획",
            lead_text="서울특별시 청년정책 기본계획 원문입니다.",
            url="https://www.seoul.go.kr/plan/youth",
            source_kind="local",
            region="서울",
            source_channel="policy_plan",
        )
        plan_document["region_name"] = "서울"
        plan_document["attachment_url"] = "https://www.seoul.go.kr/files/youth-plan.pdf"
        central_policy = make_article(
            title="고용노동부 청년 정책 발표",
            lead_text="중앙정부가 청년 고용 정책을 발표했다.",
            url="https://www.moel.go.kr/news/youth",
            source_kind="official",
        )
        election_story = make_article(
            title="시장 후보 청년 공약 발표",
            lead_text="시장 후보가 청년 공약을 밝혔다.",
            url="https://example.com/election",
            source_kind="news",
            region="서울",
        )

        page_html = web_updater.build_local_government_trends_page(
            [local_news, local_press, plan_document, central_policy, election_story],
            {"finished_at": "2026-05-01T10:00:00+09:00"},
        )
        main_section = page_html.split('id="main-list"', 1)[1].split('id="local-press-releases"', 1)[0]

        self.assertIn("지역의 변화와 현장 맥락을 읽는 곳", page_html)
        self.assertIn("공식 자료와 참여 기록은 분리해서 확인", page_html)
        self.assertIn("<h3>자료 필터</h3>", page_html)
        self.assertIn("filter-panel has-region-map", page_html)
        self.assertIn('class="filter-stack filter-stack-map"', page_html)
        self.assertIn('class="filter-control-column"', page_html)
        self.assertIn('class="filter-region-map-svg"', page_html)
        self.assertEqual(page_html.count('class="filter-region-map-region"'), len(web_updater.LOCAL_YOUTH_PLAN_REGIONS))
        self.assertEqual(page_html.count('class="filter-region-map-tooltip"'), len(web_updater.LOCAL_YOUTH_PLAN_REGIONS))
        self.assertLess(
            page_html.rfind('class="filter-region-map-region"'),
            page_html.rfind('class="filter-region-map-tooltip-layer"'),
        )
        self.assertIn('class="filter-region-map-hit-target"', page_html)
        self.assertIn('aria-label="서울특별시 1건 선택"', page_html)
        self.assertIn('data-region-map-count="true">1건</tspan>', page_html)
        self.assertNotIn("<title>서울특별시", page_html)
        for region in ["서울", "강원", "세종", "울산", "전북", "제주"]:
            self.assertIn(f'data-filter-group="scope" data-filter-value="{region}"', page_html)
        self.assertIn(local_news["title"], main_section)
        self.assertNotIn(local_press["title"], main_section)
        self.assertNotIn(central_policy["title"], page_html)
        self.assertNotIn(election_story["title"], page_html)
        self.assertNotIn(local_press["title"], page_html)
        self.assertIn('href="local.html"', page_html)
        self.assertIn('href="hub.html"', page_html)

    def test_local_plan_map_covers_17_regions_with_truthful_download_fallback(self) -> None:
        summaries = web_updater.build_local_plan_region_summaries([])

        self.assertEqual(len(summaries), 17)
        incheon = next(item for item in summaries if item["id"] == "incheon")
        jeju = next(item for item in summaries if item["id"] == "jeju")
        self.assertIn("bbsMsgFileDown.do", incheon["basic_plan"]["download_url"])
        self.assertIn("bbsMsgFileDown.do", incheon["implementation_plan"]["download_url"])
        self.assertEqual(
            jeju["implementation_plan"]["scope"],
            "17개 지자체 종합본",
        )

        page_html = web_updater.render_local_policy_plan_map([])
        self.assertEqual(page_html.count('class="local-map-marker"'), 17)
        self.assertIn("PDF", page_html)
        self.assertIn("종합 PDF", page_html)

    def test_local_materials_switches_releases_and_each_plan_type_with_region_controls(self) -> None:
        local_press = make_article(
            title="서울시 청년 주거 지원사업 보도자료",
            lead_text="서울특별시가 청년 주거 지원 정책을 공식 발표했다.",
            url="https://www.seoul.go.kr/news/youth-housing",
            source_kind="local",
            region="서울",
            source_channel="press_release",
        )
        basic_plan = make_article(
            title="서울 청년정책 기본계획(2026~2030)",
            lead_text="서울특별시 청년정책 기본계획 원문입니다.",
            url="https://www.seoul.go.kr/plan/youth-basic",
            source_kind="local",
            region="서울",
            source_channel="policy_plan",
        )
        implementation_plan = make_article(
            title="2026년 서울 청년정책 시행계획",
            lead_text="서울특별시 연도별 청년정책 시행계획 원문입니다.",
            url="https://www.seoul.go.kr/plan/youth-implementation",
            source_kind="local",
            region="서울",
            source_channel="policy_plan",
        )

        page_html = web_updater.build_local_materials_page(
            [local_press, basic_plan, implementation_plan],
            {"finished_at": "2026-05-01T10:00:00+09:00"},
        )

        self.assertIn('data-local-view-tab="releases"', page_html)
        self.assertIn('data-local-view-tab="basic"', page_html)
        self.assertIn('data-local-view-tab="implementation"', page_html)
        self.assertIn('data-local-view-panel="releases"', page_html)
        self.assertIn('data-local-view-panel="basic"', page_html)
        self.assertIn('data-local-view-panel="implementation"', page_html)
        self.assertIn('data-policy-filter-root="local-materials"', page_html)
        self.assertIn('class="filter-region-map-svg"', page_html)
        self.assertIn('data-policy-region="서울"', page_html)
        self.assertIn("청년정책 기본계획(5개년)", page_html)
        self.assertIn("청년정책 시행계획(1개년)", page_html)
        self.assertIn('id="local-basic-policy-map"', page_html)
        self.assertIn('id="local-implementation-policy-map"', page_html)

    def test_government_resources_start_with_cross_government_documents(self) -> None:
        resources = web_updater.build_government_policy_resource_articles()
        urls = {article["url"] for article in resources}

        self.assertIn("https://www.opm.go.kr/_res/opm/etc/opm_youth_plan2.pdf", urls)
        self.assertIn(
            "https://www.korea.kr/common/download.do?fileId=198444829&tblKey=GMN",
            urls,
        )
        self.assertGreaterEqual(len(resources), 23)


if __name__ == "__main__":
    unittest.main()

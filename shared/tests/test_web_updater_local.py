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

        self.assertIn("지자체 홈페이지 보도자료", page_html)
        self.assertIn("기본·시행계획 지도", page_html)
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
        self.assertIn(local_press["title"], page_html)
        self.assertIn("원문 확인됨", page_html)
        self.assertIn("https://www.seoul.go.kr/files/youth-plan.pdf", page_html)
        self.assertIn('class="local-map-svg"', page_html)
        self.assertEqual(page_html.count('class="local-map-region"'), len(web_updater.LOCAL_YOUTH_PLAN_REGIONS))
        self.assertIn('class="local-map-hit-target"', page_html)
        self.assertEqual(page_html.count('class="local-map-marker"'), len(web_updater.LOCAL_YOUTH_PLAN_REGIONS))
        self.assertIn('class="local-map-stage"', page_html)
        self.assertIn('style="left: 44.69%; top: 21.82%;"', page_html)
        self.assertNotIn('style="left: 47%; top: 18%;"', page_html)
        self.assertIn("수집 후보 1건", page_html)
        self.assertIn("기본계획", page_html)
        self.assertIn("시행계획", page_html)
        self.assertNotIn('class="local-plan-card"', page_html)
        self.assertNotIn("local-source-design", page_html)
        self.assertNotIn("자료 표기 기준", page_html)


if __name__ == "__main__":
    unittest.main()

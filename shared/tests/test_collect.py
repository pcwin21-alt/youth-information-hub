from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path


SHARED_SRC = Path(__file__).resolve().parents[1] / "src"
if str(SHARED_SRC) not in sys.path:
    sys.path.insert(0, str(SHARED_SRC))

from youth_info_platform.collect import (  # noqa: E402
    apply_source_filters,
    get_source_parser,
    parse_naver_news_search,
    parse_source_payload,
)


NAVER_HTML = """
<html>
  <body>
    <div class="sds-comps-vertical-layout sds-comps-full-layout card-1">
      <div data-sds-comp="Profile">
        <a href="https://www.ytn.co.kr/" data-heatmap-target=".prof" target="_blank">YTN</a>
        <span>2시간 전</span>
      </div>
      <div class="sds-comps-vertical-layout sds-comps-full-layout content-1">
        <a href="https://www.ytn.co.kr/_ln/0103_202604201200000001" data-heatmap-target=".tit" target="_blank">
          <span class="sds-comps-text sds-comps-text-type-headline1">청년 공간 확대 정책 발표</span>
        </a>
        <a href="https://www.ytn.co.kr/_ln/0103_202604201200000001" data-heatmap-target=".body" target="_blank">
          <span class="sds-comps-text">청년 일자리와 청년 주거를 함께 다루는 정책 기사 요약입니다.</span>
        </a>
      </div>
    </div>
    <div class="sds-comps-vertical-layout sds-comps-full-layout card-2">
      <div data-sds-comp="Profile">
        <a href="https://help.naver.com/" data-heatmap-target=".prof" target="_blank">네이버 도움말</a>
        <span>1시간 전</span>
      </div>
      <div class="sds-comps-vertical-layout sds-comps-full-layout content-2">
        <a href="https://help.naver.com/example" data-heatmap-target=".tit" target="_blank">
          <span class="sds-comps-text sds-comps-text-type-headline1">도움말 내부 링크</span>
        </a>
        <a href="https://help.naver.com/example" data-heatmap-target=".body" target="_blank">
          <span class="sds-comps-text">제외되어야 하는 내부 링크입니다.</span>
        </a>
      </div>
    </div>
  </body>
</html>
"""


class NaverParserTests(unittest.TestCase):
    def test_parse_naver_news_search_extracts_expected_fields(self) -> None:
        now = datetime(2026, 4, 20, 17, 0, tzinfo=timezone(timedelta(hours=9)))

        articles = parse_naver_news_search(
            NAVER_HTML,
            "https://search.naver.com/search.naver?where=news&query=%EC%B2%AD%EB%85%84",
            "네이버뉴스 YTN 전용(1주)",
            "news",
            now=now,
        )

        self.assertEqual(len(articles), 1)
        article = articles[0]
        self.assertEqual(article["title"], "청년 공간 확대 정책 발표")
        self.assertEqual(article["source"], "YTN")
        self.assertEqual(article["source_name"], "네이버뉴스 YTN 전용(1주)")
        self.assertEqual(article["source_kind"], "news")
        self.assertEqual(article["url"], "https://www.ytn.co.kr/_ln/0103_202604201200000001")
        self.assertEqual(article["source_url"], "https://www.ytn.co.kr/")
        self.assertIn("청년 일자리", article["lead_text"])
        self.assertIsNotNone(article["published_date"])
        self.assertTrue(article["published_date"].startswith("2026-04-20T15:00:00"))

    def test_parse_source_payload_uses_registry_for_naver(self) -> None:
        source = {
            "name": "네이버뉴스 청년정책(1주)",
            "kind": "news",
            "parser": "naver_news_search",
            "url": "https://search.naver.com/search.naver?where=news&query=%EC%B2%AD%EB%85%84",
        }

        articles = parse_source_payload(NAVER_HTML, source)

        self.assertEqual(len(articles), 1)
        self.assertIsNotNone(get_source_parser("naver_news_search"))
        self.assertIsNotNone(get_source_parser("rss"))


class SourceFilterTests(unittest.TestCase):
    def test_apply_source_filters_respects_domain_publisher_and_keyword_rules(self) -> None:
        items = [
            {
                "title": "청년 공간 확대 정책 발표",
                "lead_text": "청년 일자리 지원",
                "source": "YTN",
                "url": "https://www.ytn.co.kr/_ln/0103_202604201200000001",
            },
            {
                "title": "청년 공간 확대 정책 발표",
                "lead_text": "청년 일자리 지원",
                "source": "YTN 사이언스",
                "url": "https://science.ytn.co.kr/program/program_view.php?s_mcd=0082&s_hcd=&key=20260420",
            },
            {
                "title": "청년 공간 확대 정책 발표",
                "lead_text": "청년 일자리 지원",
                "source": "YTN",
                "url": "https://star.ytn.co.kr/_sn/0117_202604201728041466",
            },
            {
                "title": "청소년 정책 발표",
                "lead_text": "청소년 지원",
                "source": "YTN",
                "url": "https://www.ytn.co.kr/_ln/0103_202604201200000002",
            },
            {
                "title": "청년 공간 확대 정책 발표",
                "lead_text": "청년 일자리 지원",
                "source": "연합뉴스",
                "url": "https://www.yna.co.kr/view/AKR20260420000100017",
            },
        ]
        source = {
            "allowed_domain_suffixes": ["ytn.co.kr"],
            "blocked_domain_suffixes": ["star.ytn.co.kr"],
            "allowed_publishers": ["YTN"],
            "blocked_publishers": ["YTN 사이언스"],
            "include_keywords": ["청년"],
            "exclude_keywords": ["청소년"],
        }

        filtered = apply_source_filters(items, source)

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["source"], "YTN")
        self.assertIn("ytn.co.kr", filtered[0]["url"])


if __name__ == "__main__":
    unittest.main()

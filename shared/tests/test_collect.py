from __future__ import annotations

import sys
import subprocess
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch


SHARED_SRC = Path(__file__).resolve().parents[1] / "src"
if str(SHARED_SRC) not in sys.path:
    sys.path.insert(0, str(SHARED_SRC))

from youth_info_platform.collect import (  # noqa: E402
    apply_source_filters,
    fetch_url_via_curl,
    get_source_parser,
    parse_feed,
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

    def test_parse_feed_keeps_google_news_date_as_portal_date_only(self) -> None:
        feed = """
        <rss>
          <channel>
            <item>
              <title>Youth rent support starts</title>
              <link>https://news.google.com/rss/articles/example?oc=5</link>
              <source url="https://www.korea.kr">Korea Policy Briefing</source>
              <pubDate>Thu, 23 Apr 2026 02:45:17 GMT</pubDate>
              <description>Youth rent support starts - Korea Policy Briefing</description>
            </item>
          </channel>
        </rss>
        """

        articles = parse_feed(feed, "Google News youth policy", "news")

        self.assertEqual(len(articles), 1)
        article = articles[0]
        self.assertEqual(article["source"], "Korea Policy Briefing")
        self.assertEqual(article["source_url"], "https://www.korea.kr")
        self.assertIsNone(article["published_date"])
        self.assertEqual(article["portal_published_at"], "2026-04-23T02:45:17+00:00")

    def test_parse_feed_extracts_media_thumbnail(self) -> None:
        feed = """
        <rss xmlns:media="http://search.yahoo.com/mrss/">
          <channel>
            <item>
              <title>Youth center opens</title>
              <link>https://example.com/news/1</link>
              <source url="https://example.com">Example News</source>
              <pubDate>Thu, 23 Apr 2026 02:45:17 GMT</pubDate>
              <description>Youth center opens</description>
              <media:thumbnail url="/images/youth-center.jpg" />
            </item>
          </channel>
        </rss>
        """

        articles = parse_feed(feed, "Example feed", "news")

        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["image_url"], "https://example.com/images/youth-center.jpg")
        self.assertEqual(articles[0]["image_source"], "feed_media")
        self.assertEqual(articles[0]["image_alt"], "Youth center opens")

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


class FetchUrlTests(unittest.TestCase):
    @patch("youth_info_platform.collect.resolve_command", return_value="curl")
    @patch("youth_info_platform.collect.subprocess.run")
    def test_curl_fallback_fails_on_http_error_status(
        self,
        run_mock,
        _resolve_mock,
    ) -> None:
        run_mock.side_effect = subprocess.CalledProcessError(22, ["curl"])

        with self.assertRaises(subprocess.CalledProcessError):
            fetch_url_via_curl("https://example.com/forbidden")

        command = run_mock.call_args.args[0]
        self.assertIn("--fail", command)


if __name__ == "__main__":
    unittest.main()

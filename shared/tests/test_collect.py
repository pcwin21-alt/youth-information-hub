from __future__ import annotations

import sys
import subprocess
import json
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch


SHARED_SRC = Path(__file__).resolve().parents[1] / "src"
if str(SHARED_SRC) not in sys.path:
    sys.path.insert(0, str(SHARED_SRC))

from youth_info_platform.collect import (  # noqa: E402
    apply_source_filters,
    attach_source_metadata,
    fetch_url_via_curl,
    get_source_parser,
    parse_feed,
    parse_korea_press_release_list,
    parse_local_board_search,
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

    def test_apply_source_filters_requires_one_required_keyword_when_configured(self) -> None:
        items = [
            {
                "title": "성과급 갈등 장기화",
                "lead_text": "대기업 노사 협상이 이어졌다.",
                "source": "Example News",
                "url": "https://example.com/no-youth-signal",
            },
            {
                "title": "Z세대 취준생은 성과급 있는 회사를 선호",
                "lead_text": "청년 구직자의 보상 선호를 조사했다.",
                "source": "Example News",
                "url": "https://example.com/youth-signal",
            },
        ]
        source = {
            "include_keywords": ["성과급"],
            "required_keywords_any": ["청년", "청년층", "2030", "Z세대"],
        }

        filtered = apply_source_filters(items, source)

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["url"], "https://example.com/youth-signal")

    def test_attach_source_metadata_carries_selection_priority(self) -> None:
        items = [{"title": "청년 임금 기사", "url": "https://example.com/article"}]
        source = {
            "selection_priority": 24,
            "source_focus": "nyouth_desk",
        }

        enriched = attach_source_metadata(items, source)

        self.assertEqual(enriched[0]["selection_priority"], 24)
        self.assertEqual(enriched[0]["source_focus"], "nyouth_desk")
        self.assertNotIn("selection_priority", items[0])


class LocalBoardParserTests(unittest.TestCase):
    def test_parse_local_board_search_extracts_youth_press_release(self) -> None:
        html = """
        <table>
          <tr class="board-item">
            <td class="title"><a href="/news/view.do?id=10">청년 일자리 보도자료</a></td>
            <td class="date">2026.05.01</td>
            <td class="summary">서울특별시 청년 지원사업 발표</td>
          </tr>
          <tr class="board-item">
            <td class="title"><a href="/news/view.do?id=11">아동 행사 안내</a></td>
            <td class="date">2026.05.02</td>
          </tr>
        </table>
        """
        source = {
            "name": "서울특별시 보도자료 청년 검색",
            "kind": "local",
            "parser": "local_board_search",
            "url": "https://www.seoul.go.kr/search?keyword=%EC%B2%AD%EB%85%84",
            "region_id": "seoul",
            "region_name": "서울",
            "source_channel": "press_release",
            "item_selector": "tr.board-item",
            "title_selector": ".title a",
            "link_selector": ".title a",
            "date_selector": ".date",
            "summary_selector": ".summary",
            "search_terms": ["청년"],
        }

        articles = parse_local_board_search(html, source)

        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["title"], "청년 일자리 보도자료")
        self.assertEqual(articles[0]["url"], "https://www.seoul.go.kr/news/view.do?id=10")
        self.assertEqual(articles[0]["published_date"], "2026-05-01T00:00:00+09:00")
        self.assertEqual(articles[0]["source_channel"], "press_release")
        self.assertEqual(articles[0]["region_name"], "서울")

    def test_parse_local_board_search_keeps_direct_document_url(self) -> None:
        html = """
        <ul>
          <li class="board-item">
            <a class="subject" href="/plan/view.do?id=20">청년정책 기본계획</a>
            <a class="file" href="/files/youth-plan.pdf">원문 PDF</a>
            <span class="date">2026-04-30</span>
          </li>
        </ul>
        """
        source = {
            "name": "서울특별시 청년정책 기본·시행계획 검색",
            "kind": "local",
            "parser": "local_board_search",
            "url": "https://www.seoul.go.kr/search?keyword=plan",
            "region_id": "seoul",
            "region_name": "서울",
            "source_channel": "policy_plan",
            "item_selector": "li.board-item",
            "title_selector": ".subject",
            "link_selector": ".subject",
            "date_selector": ".date",
            "search_terms": ["청년정책 기본계획", "시행계획"],
        }

        articles = parse_local_board_search(html, source)

        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["attachment_url"], "https://www.seoul.go.kr/files/youth-plan.pdf")
        self.assertEqual(articles[0]["original_document_url"], "https://www.seoul.go.kr/files/youth-plan.pdf")
        self.assertIsNotNone(get_source_parser("local_board_search"))

    def test_parse_local_board_search_cleans_placeholder_title_and_rejects_external_link(self) -> None:
        html = """
        <ul>
          <li class="board-item"><a href="https://outside.example/youth">해당없음 . 외부 청년 정보</a></li>
          <li class="board-item"><a href="/policy/detail?id=1">해당없음 . 청년 면접정장 대여 지원</a></li>
        </ul>
        """
        source = {
            "name": "인천 청년정책 검색",
            "kind": "local",
            "url": "https://youth.incheon.go.kr/search?keyword=%EC%B2%AD%EB%85%84",
            "region_name": "인천",
            "search_terms": ["청년"],
            "allowed_domain_suffixes": ["incheon.go.kr"],
        }

        articles = parse_local_board_search(html, source)

        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["title"], "청년 면접정장 대여 지원")
        self.assertEqual(articles[0]["url"], "https://youth.incheon.go.kr/policy/detail?id=1")

    def test_parse_local_board_search_resolves_javascript_detail_link(self) -> None:
        html = """
        <ul><li class="board-item">
          <a href="javascript:fnTbbsView('461792');">청년 마음건강 지원 보도자료</a>
          <span>2026-07-20</span>
        </li></ul>
        """
        source = {
            "name": "서울특별시 보도자료 청년 검색",
            "kind": "local",
            "url": "https://www.seoul.go.kr/news/news_report.do?srchText=청년",
            "region_name": "서울",
            "source_channel": "press_release",
            "search_terms": ["청년"],
            "javascript_link_pattern": r"fnTbbsView\('(?P<id>\d+)'\)",
            "detail_url_template": "/news/news_report.do?nttNo={id}",
        }

        articles = parse_local_board_search(html, source)

        self.assertEqual(len(articles), 1)
        self.assertEqual(
            articles[0]["url"],
            "https://www.seoul.go.kr/news/news_report.do?nttNo=461792",
        )

    def test_explicit_link_selector_does_not_fall_back_to_navigation_link(self) -> None:
        html = """
        <table><tbody><tr>
          <td><a href="/home">청년포털</a></td>
          <td>일반 보도자료</td>
        </tr></tbody></table>
        """
        source = {
            "name": "광역지자체 보도자료",
            "kind": "local",
            "url": "https://example.go.kr/press",
            "item_selector": "table tbody tr",
            "title_selector": "a[href*='view.do']",
            "link_selector": "a[href*='view.do']",
            "search_terms": ["청년"],
        }

        self.assertEqual(parse_local_board_search(html, source), [])


class KoreaPressReleaseParserTests(unittest.TestCase):
    def test_parse_cross_ministry_youth_press_release_results(self) -> None:
        html = """
        <div class="list_type"><ul><li>
          <a href="/briefing/pressReleaseView.do?newsId=156700001">
            <span class="text">
              <strong>청년 주거지원 확대 방안 발표</strong>
              <span class="lead"><span class="highlight">청년</span> 월세 지원을 확대합니다.</span>
              <span class="source"><span>2026-07-31</span><span>국토교통부</span></span>
            </span>
          </a>
        </li></ul></div>
        """
        source = {
            "name": "정책브리핑 정부부처 청년 보도자료",
            "kind": "official",
            "parser": "korea_press_release_list",
            "url": "https://www.korea.kr/briefing/pressReleaseList.do?srchWord=청년",
        }

        articles = parse_korea_press_release_list(html, source)

        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["source"], "국토교통부")
        self.assertEqual(articles[0]["policy_authority"], "국토교통부")
        self.assertEqual(articles[0]["source_channel"], "press_release")
        self.assertEqual(articles[0]["published_date"], "2026-07-31T00:00:00+09:00")
        self.assertEqual(
            articles[0]["url"],
            "https://www.korea.kr/briefing/pressReleaseView.do?newsId=156700001",
        )
        self.assertIsNotNone(get_source_parser("korea_press_release_list"))


class SourceRegistryCoverageTests(unittest.TestCase):
    def test_all_17_metropolitan_governments_have_press_release_trackers(self) -> None:
        config_path = Path(__file__).resolve().parents[2] / "public-site" / "config" / "source_config.yaml"
        sources = json.loads(config_path.read_text(encoding="utf-8"))["sources"]
        region_ids = {
            source.get("region_id")
            for source in sources
            if source.get("enabled")
            and source.get("kind") == "local"
            and source.get("source_channel") == "press_release"
        }

        self.assertEqual(
            region_ids,
            {
                "seoul", "busan", "daegu", "incheon", "gwangju", "daejeon",
                "ulsan", "sejong", "gyeonggi", "gangwon", "chungbuk", "chungnam",
                "jeonbuk", "jeonnam", "gyeongbuk", "gyeongnam", "jeju",
            },
        )


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

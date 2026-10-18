from __future__ import annotations

import sys
import unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from youth_info_platform.article_metadata import normalize_article_record, preferred_article_url, parse_generic_article_page
from youth_info_platform.collect import parse_feed, detect_source_access_issue
from youth_info_platform.curation import deduplicate_and_filter
from youth_info_platform.public_archive import deduplicate_public_stories
from youth_info_platform.publisher_names import article_publisher_name, publisher_display_name
from youth_info_platform.pipeline_feedback import source_health_metrics


def record(url, source="조선일보", **extra):
    return dict(url=url, title="청년 월세 지원 기준 확대", source=source,
                published_date="2026-10-17T10:00:00+09:00", source_kind="news", **extra)


class CollectionQualityTests(unittest.TestCase):
    def test_http_200_error_page_is_not_a_healthy_empty_source(self):
        self.assertEqual(detect_source_access_issue("<html><title>서울특별시청 에러페이지</title><p>요청하신 페이지를 찾을 수 없습니다.</p></html>"), "fetch_error")

    def test_specific_mobile_domain_and_placeholder(self):
        self.assertEqual(publisher_display_name("https://m.biz.chosun.com/news/1"), "조선비즈")
        self.assertEqual(article_publisher_name(record("https://www.chosun.com/news/1", publisher_name="새 창 열림")), "조선일보")
        self.assertEqual(article_publisher_name(record("https://v.daum.net/v/1", source="Daum")), "")
        self.assertEqual(article_publisher_name(record("https://unknown.example/news/1", source="unknown.example")), "")

    def test_normalization_repairs_feed_title_and_publisher_without_network(self):
        item = normalize_article_record(dict(url="https://news.google.com/rss/articles/1", source="조선일보", title="청년 월세 지원 기준 확대 - 조선일보"))
        self.assertEqual(item["publisher_name"], "조선일보")
        self.assertEqual(item["title"], "청년 월세 지원 기준 확대")

    def test_original_link_wins_over_saved_portal_links(self):
        self.assertEqual(preferred_article_url(record("https://www.chosun.com/news/1", portal_urls=["https://v.daum.net/v/1"])), "https://www.chosun.com/news/1")

    def test_archive_and_current_wrappers_collapse_but_other_publishers_do_not(self):
        items = [record("https://news.google.com/rss/articles/1"), record("https://news.google.com/rss/articles/2"), record("https://hani.co.kr/news/3", source="한겨레")]
        self.assertEqual(len(deduplicate_public_stories(items)), 2)
        self.assertEqual(len(deduplicate_and_filter(items)), 2)

    def test_portal_copy_cannot_bridge_two_known_publishers(self):
        items = [record("https://chosun.com/news/1"), record("https://hani.co.kr/news/2", source="한겨레"), record("https://v.daum.net/v/3", source="Daum")]
        self.assertEqual(len(deduplicate_public_stories(items)), 3)
        self.assertEqual(len(deduplicate_and_filter([items[2], *items[:2]])), 2)

    def test_unknown_direct_publisher_is_not_treated_as_a_portal(self):
        items = [record("https://chosun.com/news/1"), record("https://unknown.example/news/2", source="unknown.example")]
        self.assertEqual(len(deduplicate_public_stories(items)), 2)

    def test_portal_copy_keeps_original_identity_without_inheriting_portal_canonical(self):
        original = record("https://chosun.com/news/1")
        portal = record("https://v.daum.net/v/2", source="Daum", canonical_url="https://v.daum.net/v/2")
        merged = deduplicate_public_stories([portal, original])
        self.assertEqual(len(merged), 1)
        self.assertEqual(preferred_article_url(merged[0]), original["url"])

    def test_same_url_richer_later_record_is_not_discarded(self):
        first = record("https://chosun.com/news/1")
        rich = {**first, "body_text": "청년 월세 지원 기준과 신청 방법을 설명합니다."}
        self.assertEqual(deduplicate_and_filter([first, rich])[0]["body_text"], rich["body_text"])

    def test_portal_publisher_url_field_does_not_outrank_an_original(self):
        portal = record("https://v.daum.net/v/1", source="Daum", publisher_url="https://v.daum.net/v/1")
        original = record("https://chosun.com/news/1")
        self.assertEqual(deduplicate_and_filter([portal, original])[0]["url"], original["url"])

    def test_collection_manifest_does_not_create_false_empty_official_alarm(self):
        metrics = source_health_metrics({"sources": [{"kind": "official", "status": "ok", "name": "공식 발표", "fetched_items": 10, "filtered_items": 2}]})
        self.assertEqual(metrics["official_total_items"], 10)
        self.assertEqual(metrics["zero_total_sources"], [])

    def test_soft_block_is_counted_as_a_source_failure(self):
        metrics = source_health_metrics({"sources": [{"name": "Naver", "status": "blocked", "kind": "news"}]})
        self.assertEqual(metrics["error_count"], 1)

    def test_portal_article_structured_publisher_beats_portal_site_name(self):
        page = '''<meta property="og:site_name" content="Daum"><script type="application/ld+json">{"@type":"NewsArticle","publisher":{"name":"조선일보"}}</script>'''
        self.assertEqual(parse_generic_article_page(page, "https://v.daum.net/v/1")["publisher_name"], "조선일보")

    def test_atom_published_date_is_collected(self):
        feed = '''<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>청년 정책</title><link href="https://example.com/1"/><published>2026-10-17T09:00:00+09:00</published></entry></feed>'''
        self.assertEqual(parse_feed(feed, "공식", "official")[0]["published_date"], "2026-10-17T09:00:00+09:00")

    def test_explicit_original_link_on_portal_is_preserved(self):
        page = '<link rel="canonical" href="https://v.daum.net/v/1"><a href="https://chosun.com/news/1?utm_source=daum">기사원문</a>'
        meta = parse_generic_article_page(page, "https://v.daum.net/v/1")
        self.assertTrue(meta["publisher_url"].startswith("https://chosun.com/news/1"))
        self.assertEqual(meta["portal_urls"], ["https://v.daum.net/v/1"])

    def test_selected_article_keeps_enrichment_when_canonical_identity_changes(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "public-site" / "scripts"))
        import run_curator
        first = record("https://news.google.com/rss/articles/1")
        enriched = {**first, "canonical_url": "https://chosun.com/news/1", "publisher_url": "https://chosun.com/news/1", "image_url": "https://chosun.com/photo.jpg"}
        with patch.object(run_curator, "enrich_articles_for_curation", return_value=[enriched]):
            result = run_curator.enrich_selected_articles_for_media([first], max_network_enrich=1)
        self.assertEqual(result[0]["publisher_url"], enriched["publisher_url"])


if __name__ == "__main__":
    unittest.main()


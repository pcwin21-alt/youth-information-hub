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

spec = importlib.util.spec_from_file_location("test_web_updater_dates_module", SCRIPT_PATH)
web_updater = importlib.util.module_from_spec(spec)
assert spec is not None and spec.loader is not None
spec.loader.exec_module(web_updater)


def make_portal_only_article() -> dict:
    return {
        "url": "https://news.google.com/rss/articles/example",
        "title": "Portal only youth policy",
        "lead_text": "Youth policy application opens this week.",
        "summary": "Youth policy application opens this week.",
        "source": "Google News",
        "source_name": "Google News youth policy",
        "source_kind": "news",
        "published_date": None,
        "portal_published_at": "2026-05-07T07:36:55+00:00",
        "issue_tags": [],
        "location_tags": [],
        "display_badges": [],
        "topic_tags": ["policy"],
        "is_official_source": False,
        "is_noise": False,
        "article_type": "news",
        "region": "",
        "importance_score": 10,
        "clean_score": 4,
        "editorial_decision": "default",
        "editorial_is_highlighted": False,
    }


def make_official_government_article() -> dict:
    return {
        "url": "https://example.gov/central-youth-policy",
        "title": "Central official youth policy",
        "lead_text": "Central government youth policy briefing.",
        "summary": "Central government youth policy briefing.",
        "source": "Policy Briefing",
        "source_name": "Policy Briefing",
        "source_kind": "official",
        "source_channel": "press_release",
        "published_date": "2026-05-07T09:00:00+09:00",
        "publisher_published_at": "2026-05-07T09:00:00+09:00",
        "issue_tags": ["jobs"],
        "location_tags": [],
        "display_badges": [],
        "topic_tags": ["policy"],
        "is_official_source": True,
        "is_noise": False,
        "article_type": "news",
        "region": "central",
        "importance_score": 10,
        "clean_score": 4,
        "editorial_decision": "default",
        "editorial_is_highlighted": False,
    }


def make_local_official_article() -> dict:
    return {
        **make_official_government_article(),
        "url": "https://example.local/local-youth-policy",
        "title": "Local city official youth policy",
        "source": "Local City",
        "source_name": "Local City",
        "source_kind": "local",
        "source_channel": "press_release",
        "is_official_source": True,
        "region": "Local",
    }


def make_central_government_related_news_article() -> dict:
    return {
        **make_portal_only_article(),
        "url": "https://example.com/central-government-news",
        "title": "\uc815\ubd80 youth employment support expands",
        "lead_text": "\uc911\uc559\uc815\ubd80 youth policy news coverage.",
        "summary": "\uc911\uc559\uc815\ubd80 youth policy news coverage.",
        "source": "Example News",
        "source_name": "Example News",
        "source_kind": "news",
        "published_date": "2026-05-07T10:00:00+09:00",
        "portal_published_at": None,
    }


def make_local_government_news_with_central_keyword() -> dict:
    return {
        **make_portal_only_article(),
        "url": "https://example.com/local-government-news",
        "title": "\uc11c\uc6b8\uc2dc youth policy wins central government review",
        "lead_text": "\uad6d\ubb34\uc870\uc815\uc2e4 review mentioned local youth policy.",
        "summary": "\uad6d\ubb34\uc870\uc815\uc2e4 review mentioned local youth policy.",
        "source": "Example Local News",
        "source_name": "Example Local News",
        "source_kind": "news",
        "published_date": "2026-05-07T11:00:00+09:00",
        "portal_published_at": None,
        "region": "\uc11c\uc6b8",
    }


def make_central_government_news_with_location_text() -> dict:
    return {
        **make_portal_only_article(),
        "url": "https://example.com/central-government-location-news",
        "title": "\uad6d\ubc29\ubd80, \uccad\ub144 \uc7a5\ubcd1 \uc9c0\uc6d0 \ub300\ucc45 \ubc1c\ud45c",
        "lead_text": "\uc11c\uc6b8 \uc6a9\uc0b0\uad6c\uc5d0\uc11c \uc911\uc559\ubd80\ucc98 \uccad\ub144\uc815\ucc45 \uc9c0\uc6d0 \ubc29\uc548\uc744 \uc124\uba85\ud588\ub2e4.",
        "summary": "\uc11c\uc6b8 \uc6a9\uc0b0\uad6c\uc5d0\uc11c \uc911\uc559\ubd80\ucc98 \uccad\ub144\uc815\ucc45 \uc9c0\uc6d0 \ubc29\uc548\uc744 \uc124\uba85\ud588\ub2e4.",
        "source": "Example Defense News",
        "source_name": "Example Defense News",
        "source_kind": "news",
        "published_date": "2026-05-07T12:00:00+09:00",
        "portal_published_at": None,
        "region": "\uc11c\uc6b8",
    }


class WebUpdaterDateFallbackTests(unittest.TestCase):
    def test_recent_filter_uses_portal_published_at_when_published_date_is_missing(self) -> None:
        article = make_portal_only_article()

        recent = web_updater.filter_recent_articles(
            [article],
            "2026-05-08T00:00:00+09:00",
            48,
        )

        self.assertEqual(recent, [article])
        self.assertEqual(web_updater.article_date_value(article), "2026-05-07")

    def test_news_page_renders_portal_only_articles_with_filter_date(self) -> None:
        article = make_portal_only_article()

        page_html = web_updater.build_news_page(
            [article],
            {"finished_at": "2026-05-08T00:00:00+09:00"},
        )

        self.assertIn('data-article-card="true"', page_html)
        self.assertIn('data-article-date="2026-05-07"', page_html)
        self.assertIn("Portal only youth policy", page_html)

    def test_sorting_uses_portal_date_fallback(self) -> None:
        portal_only = make_portal_only_article()
        older_published = {
            **make_portal_only_article(),
            "url": "https://example.com/older",
            "title": "Older publisher article",
            "published_date": "2026-05-06T23:00:00+09:00",
            "portal_published_at": None,
        }

        sorted_articles = web_updater.sort_articles_by_recency([older_published, portal_only])

        self.assertEqual(sorted_articles[0]["url"], portal_only["url"])

    def test_home_government_column_uses_government_trend_pool(self) -> None:
        official = make_official_government_article()
        local = make_local_official_article()

        page_html = web_updater.build_home_page(
            [official, local],
            [official, local],
            {"finished_at": "2026-05-08T00:00:00+09:00"},
            {},
        )

        self.assertIn("정부 동향", page_html)
        self.assertIn("Central official youth policy", page_html)
        self.assertNotIn("Local city official youth policy", page_html)

    def test_government_page_has_separate_related_news_section(self) -> None:
        official = make_official_government_article()
        related_news = make_central_government_related_news_article()

        page_html = web_updater.build_policies_page_compact(
            [official, related_news],
            {"finished_at": "2026-05-08T00:00:00+09:00"},
        )

        self.assertIn('id="government-menu"', page_html)
        self.assertIn('href="#main-list"', page_html)
        self.assertIn('href="#government-official-releases"', page_html)
        self.assertIn('href="#government-policy-resources"', page_html)
        self.assertIn('data-government-announcement-news-card="true"', page_html)
        self.assertIn('data-government-related-news-card="true"', page_html)
        self.assertIn('data-government-policy-resource-card="true"', page_html)
        self.assertIn("정부 발표 뉴스 모음", page_html)
        self.assertIn("정부 홈페이지 보도자료", page_html)
        self.assertIn("각 부처별 기본·시행계획 자료 모음", page_html)
        self.assertIn("central-government-news", page_html)

    def test_government_announcement_news_excludes_local_government_actor(self) -> None:
        local_news = make_local_government_news_with_central_keyword()
        local_news_with_abbreviated_region = {
            **make_portal_only_article(),
            "url": "https://example.com/local-government-jeju-news",
            "title": "\uc81c\uc8fc\ub3c4, 3\ub9cc \uc6d0 \uc8fc\ud0dd \uc785\uc8fc\uc790 \ubaa8\uc9d1",
            "lead_text": "\uad6d\ud1a0\uad50\ud1b5\ubd80 \uc720\uc0ac \uae09\uc5ec\uc640 \uc9c0\uc790\uccb4 \uc8fc\uac70 \uc9c0\uc6d0\uc744 \ud568\uaed8 \uc18c\uac1c\ud588\ub2e4.",
            "summary": "\uad6d\ud1a0\uad50\ud1b5\ubd80 \uc720\uc0ac \uae09\uc5ec\uc640 \uc9c0\uc790\uccb4 \uc8fc\uac70 \uc9c0\uc6d0\uc744 \ud568\uaed8 \uc18c\uac1c\ud588\ub2e4.",
            "source": "Example Jeju News",
            "source_name": "Example Jeju News",
            "source_kind": "news",
            "published_date": "2026-05-07T11:30:00+09:00",
            "portal_published_at": None,
            "region": "\uc81c\uc8fc",
        }

        page_html = web_updater.build_policies_page_compact(
            [local_news, local_news_with_abbreviated_region],
            {"finished_at": "2026-05-08T00:00:00+09:00"},
        )

        self.assertNotIn("local-government-news", page_html)
        self.assertNotIn("local-government-jeju-news", page_html)
        self.assertNotIn('data-government-announcement-news-card="true"', page_html)

    def test_government_announcement_news_keeps_central_article_with_location_text(self) -> None:
        central_news = make_central_government_news_with_location_text()

        page_html = web_updater.build_policies_page_compact(
            [central_news],
            {"finished_at": "2026-05-08T00:00:00+09:00"},
        )

        self.assertIn("central-government-location-news", page_html)
        self.assertIn('data-government-announcement-news-card="true"', page_html)


if __name__ == "__main__":
    unittest.main()

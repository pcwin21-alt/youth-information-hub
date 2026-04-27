from __future__ import annotations

import sys
import unittest
from pathlib import Path


SHARED_SRC = Path(__file__).resolve().parents[1] / "src"
if str(SHARED_SRC) not in sys.path:
    sys.path.insert(0, str(SHARED_SRC))

from youth_info_platform.date_audit import build_article_date_audit_report  # noqa: E402


class DateAuditTests(unittest.TestCase):
    def test_unresolved_google_news_with_published_date_is_error(self) -> None:
        report = build_article_date_audit_report(
            {
                "step5_summarized.json": [
                    {
                        "title": "Youth rent support starts",
                        "url": "https://news.google.com/rss/articles/example?oc=5",
                        "canonical_url": "https://news.google.com/rss/articles/example?oc=5",
                        "source": "Korea Policy Briefing",
                        "published_date": "2026-04-25T02:45:17+00:00",
                    }
                ]
            }
        )

        self.assertEqual(report["error_count"], 1)
        self.assertEqual(report["warning_count"], 0)
        self.assertEqual(report["issues"][0]["code"], "untrusted_google_news_published_date")

    def test_unresolved_google_news_without_published_date_is_warning_only(self) -> None:
        report = build_article_date_audit_report(
            {
                "article_funnel.json": [
                    {
                        "title": "Youth rent support starts",
                        "url": "https://news.google.com/rss/articles/example?oc=5",
                        "canonical_url": "https://news.google.com/rss/articles/example?oc=5",
                        "portal_published_at": "2026-04-25T02:45:17+00:00",
                    }
                ]
            }
        )

        self.assertEqual(report["error_count"], 0)
        self.assertEqual(report["warning_count"], 1)
        self.assertEqual(report["issues"][0]["code"], "unresolved_google_news_without_published_date")

    def test_resolved_publisher_url_is_not_reported(self) -> None:
        report = build_article_date_audit_report(
            {
                "step5_summarized.json": [
                    {
                        "title": "Youth rent support starts",
                        "url": "https://news.google.com/rss/articles/example?oc=5",
                        "publisher_url": "https://www.korea.kr/news/reporterView.do?newsId=148962283",
                        "canonical_url": "https://www.korea.kr/news/reporterView.do?newsId=148962283",
                        "published_date": "2026-04-13T00:00:00+09:00",
                    }
                ]
            }
        )

        self.assertEqual(report["error_count"], 0)
        self.assertEqual(report["warning_count"], 0)


if __name__ == "__main__":
    unittest.main()

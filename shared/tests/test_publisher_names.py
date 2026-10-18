from __future__ import annotations

import sys
import unittest
from pathlib import Path


SHARED_SRC = Path(__file__).resolve().parents[1] / "src"
if str(SHARED_SRC) not in sys.path:
    sys.path.insert(0, str(SHARED_SRC))

from youth_info_platform.publisher_names import article_publisher_name, publisher_display_name


class PublisherDisplayNameTests(unittest.TestCase):
    def test_newfilenews_uses_verified_masthead_for_domain_and_feed_url(self) -> None:
        for value in ("newfilenews.com", "https://www.newfilenews.com/", "https://m.newfilenews.com/news/articleView.html?idxno=1"):
            with self.subTest(value=value):
                self.assertEqual(publisher_display_name(value), "최신뉴스")

    def test_google_feed_source_domain_resolves_without_guessing_unknown_publishers(self) -> None:
        self.assertEqual(article_publisher_name({"url": "https://news.google.com/rss/articles/test", "source": "https://www.newfilenews.com/"}), "최신뉴스")
        self.assertEqual(publisher_display_name("unknown-paper.example"), "unknown-paper.example")
        self.assertNotEqual(publisher_display_name("newfilenews.com.attacker.example"), "최신뉴스")

    def test_kgnews_domain_uses_the_newspaper_masthead_name(self) -> None:
        self.assertEqual(publisher_display_name("kgnews.co.kr"), "경기신문")
        self.assertEqual(
            publisher_display_name("https://www.kgnews.co.kr/news/article.html?no=910503"),
            "경기신문",
        )


if __name__ == "__main__":
    unittest.main()

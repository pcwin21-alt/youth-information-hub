from __future__ import annotations

import sys
import unittest
from pathlib import Path


SHARED_SRC = Path(__file__).resolve().parents[1] / "src"
if str(SHARED_SRC) not in sys.path:
    sys.path.insert(0, str(SHARED_SRC))

from youth_info_platform.publisher_names import publisher_display_name


class PublisherDisplayNameTests(unittest.TestCase):
    def test_kgnews_domain_uses_the_newspaper_masthead_name(self) -> None:
        self.assertEqual(publisher_display_name("kgnews.co.kr"), "경기신문")
        self.assertEqual(
            publisher_display_name("https://www.kgnews.co.kr/news/article.html?no=910503"),
            "경기신문",
        )


if __name__ == "__main__":
    unittest.main()

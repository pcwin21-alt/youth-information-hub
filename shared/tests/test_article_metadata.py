from __future__ import annotations

import sys
import unittest
from pathlib import Path


SHARED_SRC = Path(__file__).resolve().parents[1] / "src"
if str(SHARED_SRC) not in sys.path:
    sys.path.insert(0, str(SHARED_SRC))

from youth_info_platform.article_metadata import (  # noqa: E402
    extract_meta_content,
    parse_generic_article_page,
    resolve_article_metadata,
)


ARTICLE_HTML = """
<html>
  <head>
    <meta property="og:title" content="경실련, '봄 후원회' 행사 성황리 개최···&quot;연대와 화합의 장 마련&quot;" />
    <meta name="twitter:title" content="경실련, '봄 후원회' 행사 성황리 개최···&quot;연대와 화합의 장 마련&quot;" />
    <meta name="description" content="행사 소식 요약입니다." />
    <link rel="canonical" href="https://www.ngonews.kr/news/articleView.html?idxno=228784" />
    <title>경실련, '봄 후원회' 행사 성황리 개최···&quot;연대와 화합의 장 마련&quot; - 한국NGO신문</title>
  </head>
  <body>
    <article itemprop="articleBody">
      <p>경제정의실천시민연합이 봄 후원회를 열었다.</p>
    </article>
  </body>
</html>
"""


class ArticleMetadataTests(unittest.TestCase):
    def test_extract_meta_content_preserves_apostrophes_inside_double_quoted_attributes(self) -> None:
        value = extract_meta_content(ARTICLE_HTML, "og:title", "property")

        self.assertEqual(value, '경실련, \'봄 후원회\' 행사 성황리 개최···"연대와 화합의 장 마련"')

    def test_parse_generic_article_page_uses_full_title_from_meta_tag(self) -> None:
        parsed = parse_generic_article_page(
            ARTICLE_HTML,
            "https://www.ngonews.kr/news/articleView.html?idxno=228784",
        )

        self.assertEqual(parsed["title"], '경실련, \'봄 후원회\' 행사 성황리 개최···"연대와 화합의 장 마련"')
        self.assertEqual(parsed["canonical_url"], "https://www.ngonews.kr/news/articleView.html?idxno=228784")

    def test_resolve_article_metadata_strips_trailing_publisher_name_from_title(self) -> None:
        article = {
            "url": "https://www.ngonews.kr/news/articleView.html?idxno=228784",
            "title": '경실련, \'봄 후원회\' 행사 성황리 개최···"연대와 화합의 장 마련"',
            "source": "한국NGO신문",
            "source_name": "네이버뉴스 청년정책(1주)",
            "published_date": "2026-04-22T01:50:03+09:00",
            "pipeline_flags": {},
        }
        updated = resolve_article_metadata(
            article,
            homepage_cache={},
            page_cache={
                article["url"]: {
                    "title": '경실련, \'봄 후원회\' 행사 성황리 개최···"연대와 화합의 장 마련" - 한국NGO신문',
                    "canonical_url": article["url"],
                    "publisher_url": article["url"],
                    "publisher_domain": "www.ngonews.kr",
                    "lead_text": "행사 소식 요약입니다.",
                }
            },
        )

        self.assertEqual(updated["title"], '경실련, \'봄 후원회\' 행사 성황리 개최···"연대와 화합의 장 마련"')


if __name__ == "__main__":
    unittest.main()

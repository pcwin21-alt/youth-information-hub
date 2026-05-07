from __future__ import annotations

import sys
import unittest
from pathlib import Path


SHARED_SRC = Path(__file__).resolve().parents[1] / "src"
if str(SHARED_SRC) not in sys.path:
    sys.path.insert(0, str(SHARED_SRC))

from youth_info_platform.article_metadata import (  # noqa: E402
    extract_meta_content,
    extract_youth_preview_text,
    is_http_error_page_title,
    parse_generic_article_page,
    resolve_article_metadata,
)


ARTICLE_HTML = """
<html>
  <head>
    <meta property="og:title" content="경실련, '봄 후원회' 행사 성황리 개최···&quot;연대와 화합의 장 마련&quot;" />
    <meta name="twitter:title" content="경실련, '봄 후원회' 행사 성황리 개최···&quot;연대와 화합의 장 마련&quot;" />
    <meta name="description" content="행사 소식 요약입니다." />
    <meta property="og:image" content="/news/photo/202604/sample.jpg" />
    <link rel="canonical" href="https://www.ngonews.kr/news/articleView.html?idxno=228784" />
    <link rel="icon" href="/favicon.ico" />
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
        self.assertEqual(parsed["image_url"], "https://www.ngonews.kr/news/photo/202604/sample.jpg")
        self.assertEqual(parsed["image_source"], "article_page")
        self.assertEqual(parsed["publisher_icon_url"], "https://www.ngonews.kr/favicon.ico")

    def test_parse_generic_article_page_prefers_full_heading_when_meta_title_is_short(self) -> None:
        parsed = parse_generic_article_page(
            """
            <html>
              <head>
                <meta property="og:title" content="순천시, 청년 자산 형성" />
              </head>
              <body>
                <h1>순천시, 청년 자산 형성 '희망디딤돌 통장' 본격 가동</h1>
                <article itemprop="articleBody">
                  <p>순천시가 청년 희망디딤돌 통장사업 신규 대상자를 모집한다.</p>
                </article>
              </body>
            </html>
            """,
            "https://example.com/news/1",
        )

        self.assertEqual(parsed["title"], "순천시, 청년 자산 형성 '희망디딤돌 통장' 본격 가동")

    def test_parse_generic_article_page_extracts_json_ld_published_time(self) -> None:
        parsed = parse_generic_article_page(
            """
            <html>
              <head>
                <meta property="og:title" content="Youth policy update" />
                <meta name="date" content="2026-04-24" />
                <script type="application/ld+json">
                {
                  "@context": "https://schema.org",
                  "@type": "NewsArticle",
                  "datePublished": "2026-04-24T11:08:44+09:00"
                }
                </script>
              </head>
              <body><p>청년 정책 기사 본문입니다.</p></body>
            </html>
            """,
            "https://example.com/news/1",
        )

        self.assertEqual(parsed["publisher_published_at"], "2026-04-24T11:08:44+09:00")

    def test_parse_generic_article_page_ignores_http_error_page_title(self) -> None:
        parsed = parse_generic_article_page(
            """
            <html>
              <head><title>403 Forbidden</title></head>
              <body><h1>403 Forbidden</h1></body>
            </html>
            """,
            "https://www.sedaily.com/article/20038288",
        )

        self.assertTrue(is_http_error_page_title("403 Forbidden"))
        self.assertIsNone(parsed["title"])

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

    def test_resolve_article_metadata_does_not_replace_title_with_http_error_page(self) -> None:
        article = {
            "url": "https://www.sedaily.com/article/20038288",
            "title": "영상 엄마, 좀만 더 같이 살면 안될까?",
            "source": "서울경제",
            "source_name": "네이버뉴스 청년 고용",
            "published_date": "2026-04-28T21:00:00+09:00",
            "pipeline_flags": {},
        }
        updated = resolve_article_metadata(
            article,
            homepage_cache={},
            page_cache={
                article["url"]: {
                    "title": "403 Forbidden",
                    "canonical_url": article["url"],
                    "publisher_url": article["url"],
                    "publisher_domain": "www.sedaily.com",
                }
            },
        )

        self.assertEqual(updated["title"], article["title"])

    def test_resolve_article_metadata_keeps_official_detail_url_when_canonical_is_board_root(self) -> None:
        article = {
            "url": "https://www.opm.go.kr/opm/news/press-release.do?mode=view&articleNo=162154&articleLimit=20",
            "title": "[보도자료] 지속가능발전 국가보고서 의견수렴 협의회 개최",
            "source": "국무조정실 보도자료",
            "source_name": "국무조정실 보도자료",
            "source_kind": "official",
            "published_date": "2026-05-07T00:00:00+09:00",
            "pipeline_flags": {},
        }

        updated = resolve_article_metadata(
            article,
            homepage_cache={},
            page_cache={
                article["url"]: {
                    "title": (
                        "국무조정실 국무총리비서실 | 알림·소식 | 보도·설명자료 | "
                        "보도자료 게시판읽기([보도자료] 지속가능발전 국가보고서 의견수렴 협의회 개최)"
                    ),
                    "canonical_url": "https://www.opm.go.kr:443/opm/news/press-release.do",
                    "publisher_url": "https://www.opm.go.kr:443/opm/news/press-release.do",
                    "publisher_domain": "www.opm.go.kr:443",
                }
            },
        )

        self.assertEqual(updated["canonical_url"], article["url"])
        self.assertEqual(updated["publisher_url"], article["url"])
        self.assertEqual(updated["title"], article["title"])

    def test_resolve_article_metadata_keeps_local_search_title_when_page_title_is_portal_brand(self) -> None:
        article = {
            "url": "https://youth.incheon.go.kr/financial/dreamfor.jsp",
            "title": "드림for청년통장 인천 청년 근로자의 밝은 내일을 응원합니다.",
            "lead_text": "신청기간 : 2026.5.4.(월) ~ 5.15.(금) 지원대상 : 인천거주 청년근로자",
            "source": "인천광역시 보도자료 청년 검색",
            "source_name": "인천광역시 보도자료 청년 검색",
            "source_kind": "local",
            "published_date": "2026-05-04T00:00:00+09:00",
            "pipeline_flags": {},
        }

        updated = resolve_article_metadata(
            article,
            homepage_cache={},
            page_cache={
                article["url"]: {
                    "title": "인천유스톡톡 인천청년포털",
                    "canonical_url": article["url"],
                    "publisher_url": article["url"],
                    "publisher_domain": "youth.incheon.go.kr",
                    "lead_text": "인천청년포털, 인천유스톡톡",
                }
            },
        )

        self.assertEqual(updated["title"], article["title"])
        self.assertEqual(updated["lead_text"], article["lead_text"])

    def test_resolve_article_metadata_promotes_publisher_published_time(self) -> None:
        article = {
            "url": "https://example.com/news/1",
            "title": "Youth policy update",
            "source": "Example News",
            "source_name": "Example News",
            "published_date": "2026-04-24T00:00:00+09:00",
            "pipeline_flags": {},
        }
        updated = resolve_article_metadata(
            article,
            homepage_cache={},
            page_cache={
                article["url"]: {
                    "title": "Youth policy update",
                    "canonical_url": article["url"],
                    "publisher_url": article["url"],
                    "publisher_domain": "example.com",
                    "publisher_published_at": "2026-04-24T11:08:44+09:00",
                    "image_url": "/images/youth.jpg",
                    "image_source": "article_page",
                    "publisher_icon_url": "/favicon.ico",
                }
            },
        )

        self.assertEqual(updated["publisher_published_at"], "2026-04-24T11:08:44+09:00")
        self.assertEqual(updated["published_date"], "2026-04-24T11:08:44+09:00")
        self.assertEqual(updated["image_url"], "https://example.com/images/youth.jpg")
        self.assertEqual(updated["publisher_icon_url"], "https://example.com/favicon.ico")

    def test_resolve_article_metadata_does_not_trust_unresolved_google_news_date(self) -> None:
        article = {
            "url": "https://news.google.com/rss/articles/example?oc=5",
            "title": "Youth rent support starts",
            "source": "Korea Policy Briefing",
            "source_name": "Google News youth policy",
            "published_date": "2026-04-25T02:45:17+00:00",
            "pipeline_flags": {},
        }

        updated = resolve_article_metadata(article, homepage_cache={}, page_cache={})

        self.assertIsNone(updated["published_date"])
        self.assertIsNone(updated["publisher_published_at"])
        self.assertEqual(updated["portal_published_at"], "2026-04-25T02:45:17+00:00")

    def test_extract_youth_preview_text_prefers_sentence_with_youth_keyword(self) -> None:
        article = {
            "lead_text": "첫 문장은 행사 전체 개요입니다.",
            "body_text": "첫 문장은 행사 전체 개요입니다. 청년 참여자에게 제공되는 지원 내용을 별도로 안내했습니다.",
        }

        excerpt = extract_youth_preview_text(article)

        self.assertIn("청년 참여자", excerpt)
        self.assertNotEqual(excerpt, article["lead_text"])


if __name__ == "__main__":
    unittest.main()

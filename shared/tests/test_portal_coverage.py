from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'public-site/scripts'))
from audit_portal_coverage import article_index, match_article, naver_reference, source_query


class PortalCoverageTests(unittest.TestCase):
    def test_config_covers_plain_joined_and_spaced_queries_on_both_providers(self):
        sources = json.loads((ROOT / 'public-site/config/source_config.yaml').read_text(encoding='utf-8'))['sources']
        expected = {'청년', '청년정책', '청년 정책'}
        for provider in ('naver', 'google'):
            matching = [source for source in sources if source.get('enabled') and
                        (source.get('parser') == 'naver_news_search' if provider == 'naver'
                         else 'news.google.com/rss/search' in source.get('url', ''))]
            self.assertTrue(expected.issubset({source_query(source) for source in matching}))
            if provider == 'google':
                self.assertTrue(all(source.get('limit', 0) >= 100 for source in matching if source_query(source) in expected))

    def test_title_match_requires_publisher_and_kst_day(self):
        original = {'title': '청년 주거 지원', 'source': '연합뉴스',
                    'url': 'https://www.yna.co.kr/1', 'published_date': '2026-10-17T23:30:00+00:00'}
        index = article_index([original])
        copy = {**original, 'url': 'https://news.google.com/rss/articles/1',
                'published_date': '2026-10-18T08:30:00+09:00'}
        self.assertEqual(match_article(copy, index), 'title_publisher_day')
        self.assertIsNone(match_article({**copy, 'source': '조선일보'}, index))
        self.assertIsNone(match_article({**copy, 'published_date': '2026-10-19T08:30:00+09:00'}, index))
        self.assertIsNone(match_article({**copy, 'published_date': None}, index))

    def test_independent_reference_extracts_continuation_and_clean_labels(self):
        markup = '''<div><div data-sds-comp="Profile">
        <a data-heatmap-target=".prof">새 창 열림</a>
        <a data-heatmap-target=".prof">연합뉴스<span>새 창 열림</span></a></div>
        <a data-heatmap-target=".tit" href="https://www.yna.co.kr/1">청년 주거<span>새 창 열림</span></a></div>'''
        items = naver_reference(json.dumps({'collection': [{'html': markup}]}))
        self.assertEqual(items, [{'title': '청년 주거', 'url': 'https://www.yna.co.kr/1', 'source': '연합뉴스'}])


if __name__ == '__main__':
    unittest.main()

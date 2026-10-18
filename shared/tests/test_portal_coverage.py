from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'public-site/scripts'))
from audit_portal_coverage import article_index, match_article, naver_reference


class PortalCoverageTests(unittest.TestCase):
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

import sys
import unittest
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "public-site/scripts"))
from trend_digest import build_digest, render_digest


class TrendDigestTests(unittest.TestCase):
    now = datetime.fromisoformat("2026-10-04T12:00:00+09:00")

    def article(self, **changes):
        return dict({"title": "광양 청년 근속장려금 지원 - 테스트신문", "source": "테스트신문", "url": "https://example.org/a", "published_date": "2026-10-03T10:00:00+09:00", "region": "광양"}, **changes)

    def digest(self, articles, updated="2026-10-04T10:00:00+09:00"):
        return build_digest(articles, updated, now=self.now)

    def test_filters_noise_future_old_missing_dates_and_unsafe_urls(self):
        invalid = [self.article(title="노인의 날 기념식", is_official_source=True, hub_topics=["청년"]), self.article(published_date="2026-10-05"), self.article(published_date="2026-09-01"), self.article(published_date=None), self.article(url="javascript:alert(1)"), self.article(is_noise=True), self.article(title="이미지 없음 청년 " + "정보" * 100)]
        self.assertEqual([], self.digest(invalid)["issues"])

    def test_same_title_dedup_preserves_separate_regions_and_sources(self):
        articles = [self.article(), self.article(), self.article(url="https://example.org/b", title="광양 청년 근속장려금 지원 - yna.co.kr"), self.article(url="https://example.org/c", region="전남")]
        issues = self.digest(articles)["issues"]
        self.assertEqual(2, len(issues))
        self.assertEqual(3, sum(len(issue["records"]) for issue in issues))
        self.assertEqual("광양 청년 근속장려금 지원", issues[0]["records"][0]["title"])

    def test_stage_requires_review_and_evidence(self):
        raw = self.article(policy_stage="시행 중", is_official_source=True)
        self.assertIn("시행 상태 미확인", render_digest(self.digest([raw])))
        reviewed = dict(raw, review_status="approved", stage_evidence_url="https://example.org/evidence")
        self.assertIn("시행 중", render_digest(self.digest([reviewed])))

    def test_stale_data_uses_current_clock_not_last_success(self):
        digest = self.digest([self.article(published_date="2026-09-01")], "2026-09-01")
        self.assertTrue(digest["stale"])
        self.assertEqual([], digest["issues"])
        self.assertIn("수집 상태 확인 필요", render_digest(digest))

    def test_escapes_titles_and_keeps_no_script_sources(self):
        rendered = render_digest(self.digest([self.article(title='청년 <script>alert(1)</script> 지원')]))
        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertIn("https://example.org/a", rendered)
        self.assertIn("data-trend-reset", rendered)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import sys
import unittest
from pathlib import Path


SHARED_SRC = Path(__file__).resolve().parents[1] / "src"
if str(SHARED_SRC) not in sys.path:
    sys.path.insert(0, str(SHARED_SRC))

from youth_info_platform.pipeline_feedback import build_feedback_report, should_fail  # noqa: E402


def healthy_metrics() -> dict:
    return {
        "generated_at": "2026-05-07T21:40:00+09:00",
        "artifact_counts": {
            "raw": 460,
            "filtered": 330,
            "classified": 330,
            "selected": 10,
            "summarized": 10,
        },
        "missing_artifacts": [],
        "status": {
            "state": "completed",
            "error": None,
            "finished_age_hours": 1,
            "current_step": None,
        },
        "date_audit": {"error_count": 0, "warning_count": 0},
        "source_health": {
            "generated_at": "2026-05-07T21:35:00+09:00",
            "source_count": 65,
            "error_count": 0,
            "error_sources": [],
            "official_filtered_items": 48,
            "official_total_items": 140,
            "news_filtered_items": 560,
            "local_filtered_items": 12,
            "local_regions_with_items": ["서울", "인천"],
            "zero_total_sources": [],
        },
        "source_health_age_hours": 1,
        "public_html": {
            "missing_files": [],
            "news_cards": 40,
            "home_government_trends": 9,
            "home_latest_news": 127,
            "brand_ok": True,
        },
    }


class PipelineFeedbackTests(unittest.TestCase):
    def test_healthy_metrics_pass(self) -> None:
        report = build_feedback_report(healthy_metrics())

        self.assertEqual(report["verdict"], "pass")
        self.assertFalse(should_fail(report, "critical"))

    def test_home_government_underflow_is_critical(self) -> None:
        metrics = healthy_metrics()
        metrics["public_html"]["home_government_trends"] = 2

        report = build_feedback_report(metrics)

        self.assertEqual(report["verdict"], "fail")
        self.assertTrue(should_fail(report, "critical"))
        self.assertIn("low_home_government_trends", {item["code"] for item in report["findings"]})

    def test_local_source_errors_warn_without_failing_default_gate(self) -> None:
        metrics = healthy_metrics()
        metrics["source_health"]["error_count"] = 1
        metrics["source_health"]["error_sources"] = [
            {"name": "경기도 보도자료 청년 검색", "kind": "local", "status": "error:RuntimeError"}
        ]

        report = build_feedback_report(metrics)

        self.assertEqual(report["verdict"], "warn")
        self.assertFalse(should_fail(report, "critical"))
        self.assertTrue(should_fail(report, "warning"))

    def test_date_errors_fail(self) -> None:
        metrics = healthy_metrics()
        metrics["date_audit"]["error_count"] = 1

        report = build_feedback_report(metrics)

        self.assertEqual(report["verdict"], "fail")
        self.assertIn("date_audit_errors", {item["code"] for item in report["findings"]})


if __name__ == "__main__":
    unittest.main()

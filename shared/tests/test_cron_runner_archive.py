from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "public-site" / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def load_cron_runner():
    module_path = SCRIPTS_ROOT / "cron_runner.py"
    spec = importlib.util.spec_from_file_location("cron_runner_for_test", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CronRunnerArchiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.pipeline_root = Path(self.temp_dir.name)
        self.runner = load_cron_runner()
        self.runner.RUNTIME_PIPELINE_ROOT = self.pipeline_root

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_status(self, *, run_id: str = "run/test", started_at: datetime | None = None) -> Path:
        now = datetime.now(timezone.utc).astimezone()
        status = {
            "run_id": run_id,
            "started_at": (started_at or now - timedelta(seconds=10)).isoformat(),
            "finished_at": now.isoformat(),
        }
        status_path = self.pipeline_root / "pipeline_status.json"
        status_path.write_text(json.dumps(status), encoding="utf-8")
        return status_path

    def test_archive_run_artifacts_copies_current_json_outputs(self) -> None:
        status_path = self.write_status()
        (self.pipeline_root / "step2_filtered.json").write_text("[]", encoding="utf-8")
        (self.pipeline_root / "step5_summarized.json").write_text("[]", encoding="utf-8")

        snapshot = self.runner.archive_run_artifacts(status_path)

        snapshot_dir = Path(snapshot["snapshot_dir"])
        self.assertEqual(snapshot["copied"], ["step2_filtered.json", "step5_summarized.json", "pipeline_status.json"])
        self.assertTrue((snapshot_dir / "step2_filtered.json").exists())
        self.assertTrue((snapshot_dir / "step5_summarized.json").exists())
        self.assertTrue((snapshot_dir / "pipeline_status.json").exists())
        self.assertIn("run_test", str(snapshot_dir))

    def test_archive_run_artifacts_skips_stale_intermediate_outputs(self) -> None:
        now = datetime.now(timezone.utc).astimezone()
        status_path = self.write_status(started_at=now)
        stale_path = self.pipeline_root / "step2_filtered.json"
        stale_path.write_text("[]", encoding="utf-8")
        stale_timestamp = (now - timedelta(minutes=5)).timestamp()
        os.utime(stale_path, (stale_timestamp, stale_timestamp))

        snapshot = self.runner.archive_run_artifacts(status_path)

        snapshot_dir = Path(snapshot["snapshot_dir"])
        self.assertIn("step2_filtered.json", snapshot["skipped_stale"])
        self.assertFalse((snapshot_dir / "step2_filtered.json").exists())
        self.assertTrue((snapshot_dir / "pipeline_status.json").exists())


if __name__ == "__main__":
    unittest.main()

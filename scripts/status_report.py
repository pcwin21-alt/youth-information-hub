from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from youth_info_platform.io_utils import read_json


def format_step(step: dict) -> str:
    details = step.get("details", {})
    extra = ""
    if "stdout" in details and details["stdout"]:
        extra = f' | {details["stdout"]}'
    if "stderr" in details and details["stderr"]:
        extra = f' | {details["stderr"]}'
    return f'- {step.get("name")}: {step.get("state")} @ {step.get("updated_at")}{extra}'


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(ROOT / "output" / "pipeline_status.json"))
    args = parser.parse_args()

    status = read_json(Path(args.input), default={})
    scheduler_installation = read_json(ROOT / "output" / "scheduler_installation.json", default={})
    scheduler_task_status = read_json(ROOT / "output" / "scheduler_task_status.json", default={})
    wake_configuration_status = read_json(ROOT / "output" / "wake_configuration_status.json", default={})
    if not status:
        print("pipeline_status=missing")
        return 1

    print(f'run_id={status.get("run_id")}')
    print(f'state={status.get("state")}')
    print(f'started_at={status.get("started_at")}')
    print(f'updated_at={status.get("updated_at")}')
    print(f'finished_at={status.get("finished_at")}')
    if status.get("date_basis"):
        print(f'date_basis={status["date_basis"].get("article_date_basis")}')
        print(f'freshness_target_hours={status["date_basis"].get("freshness_target_hours")}')
    if status.get("update_policy"):
        print(f'update_frequency={status["update_policy"].get("frequency")}')
        print(f'update_times={",".join(status["update_policy"].get("times", []))}')
    if status.get("error"):
        print(f'error={status["error"]}')
    if scheduler_installation:
        print(f'scheduler_task_name={scheduler_installation.get("full_name")}')
        print(f'scheduler_installed_at={scheduler_installation.get("installed_at")}')
        print(f'scheduler_wake_to_run={scheduler_installation.get("wake_to_run")}')
        schedule = scheduler_installation.get("schedule", {})
        if schedule:
            print(f'scheduler_times={",".join(schedule.get("times", []))}')
    if scheduler_task_status:
        print(f'scheduler_state={scheduler_task_status.get("state")}')
        print(f'scheduler_enabled={scheduler_task_status.get("enabled")}')
        print(f'scheduler_wake_to_run_current={scheduler_task_status.get("wake_to_run")}')
        print(f'scheduler_next_run_time={scheduler_task_status.get("next_run_time")}')
        print(f'scheduler_last_run_time={scheduler_task_status.get("last_run_time")}')
        print(f'scheduler_last_task_result={scheduler_task_status.get("last_task_result")}')
    if wake_configuration_status:
        print(f'wake_active_scheme_guid={wake_configuration_status.get("active_scheme_guid")}')
        print(f'wake_timers_ac={wake_configuration_status.get("wake_timers_ac")}')
        print(f'wake_timers_dc={wake_configuration_status.get("wake_timers_dc")}')
        print(f'wake_battery_mode={wake_configuration_status.get("battery_mode")}')
    print("steps:")
    for step in status.get("steps", []):
        print(format_step(step))
    print("artifacts:")
    for name, value in status.get("artifacts", {}).items():
        print(f"- {name}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

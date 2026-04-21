from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .io_utils import read_json, write_json


DATE_BASIS = {
    "timezone": "Asia/Seoul",
    "article_date_basis": "원문 published_date 우선, 값이 없으면 수집 완료 시각 기준",
    "freshness_target_hours": 24,
}

UPDATE_POLICY = {
    "timezone": "Asia/Seoul",
    "frequency": "daily_3x",
    "times": ["09:00", "15:00", "21:00"],
    "notes": "정기 배치 기준이며, 긴급 이슈는 수동 재실행으로 보완",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def initialize_status(status_path: Path) -> dict[str, Any]:
    status = {
        "run_id": str(uuid4()),
        "state": "running",
        "started_at": _now_iso(),
        "updated_at": _now_iso(),
        "finished_at": None,
        "current_step": None,
        "steps": [],
        "artifacts": {},
        "date_basis": DATE_BASIS,
        "update_policy": UPDATE_POLICY,
        "error": None,
    }
    write_json(status_path, status)
    return status


def load_status(status_path: Path) -> dict[str, Any]:
    return read_json(status_path, default={}) or {}


def update_step(
    status_path: Path,
    step_name: str,
    state: str,
    *,
    details: dict[str, Any] | None = None,
    artifacts: dict[str, str] | None = None,
) -> dict[str, Any]:
    status = load_status(status_path)
    if not status:
        status = initialize_status(status_path)

    steps = [step for step in status.get("steps", []) if step.get("name") != step_name]
    steps.append(
        {
            "name": step_name,
            "state": state,
            "updated_at": _now_iso(),
            "details": details or {},
        }
    )
    status["steps"] = steps
    status["current_step"] = step_name if state == "running" else status.get("current_step")
    status["updated_at"] = _now_iso()
    if artifacts:
        status.setdefault("artifacts", {}).update(artifacts)
    write_json(status_path, status)
    return status


def complete_run(status_path: Path, *, success: bool, error: str | None = None) -> dict[str, Any]:
    status = load_status(status_path)
    status["state"] = "completed" if success else "failed"
    status["finished_at"] = _now_iso()
    status["updated_at"] = _now_iso()
    status["current_step"] = None
    status["error"] = error
    write_json(status_path, status)
    return status

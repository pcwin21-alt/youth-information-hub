from __future__ import annotations

from datetime import datetime
from typing import Any

from .io_utils import read_json, runtime_pipeline_root, write_json


AUTO_UPDATE_SETTINGS_PATH = runtime_pipeline_root() / "auto_update_settings.json"
AUTO_UPDATE_STATUS_PATH = runtime_pipeline_root() / "auto_update_status.json"

DEFAULT_AUTO_UPDATE_SETTINGS = {
    "enabled": False,
    "interval_minutes": 10,
    "skip_outbound_notifications": True,
    "publish_on_article_change_only": True,
    "updated_at": "2026-04-21T00:00:00+09:00",
}


def current_timestamp() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off", ""}:
        return False
    return default


def normalize_auto_update_settings(
    data: dict[str, Any] | None,
    *,
    updated_at: str | None = None,
) -> dict[str, Any]:
    source = data or {}
    normalized = dict(DEFAULT_AUTO_UPDATE_SETTINGS)
    normalized["enabled"] = _coerce_bool(source.get("enabled"), DEFAULT_AUTO_UPDATE_SETTINGS["enabled"])
    normalized["skip_outbound_notifications"] = _coerce_bool(
        source.get("skip_outbound_notifications"),
        DEFAULT_AUTO_UPDATE_SETTINGS["skip_outbound_notifications"],
    )
    normalized["publish_on_article_change_only"] = _coerce_bool(
        source.get("publish_on_article_change_only"),
        DEFAULT_AUTO_UPDATE_SETTINGS["publish_on_article_change_only"],
    )
    try:
        normalized["interval_minutes"] = int(source.get("interval_minutes", normalized["interval_minutes"]))
    except (TypeError, ValueError):
        normalized["interval_minutes"] = DEFAULT_AUTO_UPDATE_SETTINGS["interval_minutes"]
    normalized["updated_at"] = (
        source.get("updated_at")
        or updated_at
        or DEFAULT_AUTO_UPDATE_SETTINGS["updated_at"]
        or current_timestamp()
    )
    return normalized


def validate_auto_update_settings(data: dict[str, Any] | None) -> dict[str, Any]:
    settings = normalize_auto_update_settings(data, updated_at=current_timestamp())
    interval_minutes = settings["interval_minutes"]
    if interval_minutes < 3 or interval_minutes > 60:
        raise ValueError("interval_minutes must be between 3 and 60")
    return settings


def load_auto_update_settings() -> dict[str, Any]:
    return normalize_auto_update_settings(read_json(AUTO_UPDATE_SETTINGS_PATH, default={}))


def save_auto_update_settings(data: dict[str, Any] | None) -> dict[str, Any]:
    settings = validate_auto_update_settings(data)
    write_json(AUTO_UPDATE_SETTINGS_PATH, settings)
    return settings


def load_auto_update_status() -> dict[str, Any]:
    return read_json(AUTO_UPDATE_STATUS_PATH, default={}) or {}


def save_auto_update_status(data: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(data or {})
    payload["updated_at"] = payload.get("updated_at") or current_timestamp()
    write_json(AUTO_UPDATE_STATUS_PATH, payload)
    return payload


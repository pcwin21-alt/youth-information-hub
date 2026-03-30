from __future__ import annotations

import base64
import hashlib
import hmac
import os
from datetime import datetime
from pathlib import Path

from youth_info_platform.io_utils import project_root, read_json, write_json


ROOT = project_root()
CONTACT_SETTINGS_PATH = ROOT / "content" / "contact_settings.json"
ADMIN_SETTINGS_PATH = ROOT / "config" / "contact_admin.local.json"

DEFAULT_CONTACT_SETTINGS = {
    "organization_name": "유쾌한 청년들(박진감)",
    "copyright_text": "© 2026",
    "version_text": "v0.3 preview",
    "email": "pcwin21@gmail.com",
    "extra_line_1": "궁금한 점이나 제안할 내용이 있다면 언제든 편하게 보내주세요.",
    "extra_line_2": "문의, 제보, 협업 제안은 연락 페이지에서 확인할 수 있습니다.",
    "updated_at": "2026-03-29T09:45:32+09:00",
}

REQUIRED_CONTACT_FIELDS = (
    "organization_name",
    "copyright_text",
    "version_text",
    "email",
    "extra_line_1",
)


def current_timestamp() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def normalize_contact_settings(data: dict | None, *, updated_at: str | None = None) -> dict[str, str]:
    normalized = dict(DEFAULT_CONTACT_SETTINGS)
    for key in DEFAULT_CONTACT_SETTINGS:
        value = (data or {}).get(key, normalized[key])
        if isinstance(value, str):
            normalized[key] = value.strip()
    normalized["updated_at"] = (data or {}).get("updated_at") or updated_at or normalized["updated_at"] or current_timestamp()
    return normalized


def validate_contact_settings(data: dict | None) -> dict[str, str]:
    settings = normalize_contact_settings(data, updated_at=current_timestamp())
    errors: list[str] = []

    for field_name in REQUIRED_CONTACT_FIELDS:
        if not settings[field_name]:
            errors.append(f"{field_name} is required")

    email = settings["email"]
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        errors.append("email must be a valid address")

    if len(settings["extra_line_1"]) > 180:
        errors.append("extra_line_1 must be 180 characters or fewer")
    if len(settings["extra_line_2"]) > 180:
        errors.append("extra_line_2 must be 180 characters or fewer")

    if errors:
        raise ValueError(", ".join(errors))

    return settings


def load_contact_settings() -> dict[str, str]:
    return normalize_contact_settings(read_json(CONTACT_SETTINGS_PATH, default={}))


def save_contact_settings(data: dict | None) -> dict[str, str]:
    settings = validate_contact_settings(data)
    write_json(CONTACT_SETTINGS_PATH, settings)
    return settings


def load_admin_settings() -> dict | None:
    return read_json(ADMIN_SETTINGS_PATH, default=None)


def hash_password(password: str, *, salt: bytes | None = None, iterations: int = 250_000) -> dict[str, str | int]:
    if not password:
        raise ValueError("password is required")

    salt_bytes = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, iterations)
    return {
        "algorithm": "pbkdf2_sha256",
        "iterations": iterations,
        "password_hash": base64.b64encode(digest).decode("ascii"),
        "password_salt": base64.b64encode(salt_bytes).decode("ascii"),
    }


def write_admin_settings(password: str, path: Path | None = None) -> Path:
    admin_path = path or ADMIN_SETTINGS_PATH
    payload = hash_password(password)
    write_json(admin_path, payload)
    return admin_path


def verify_password(password: str, settings: dict | None = None) -> bool:
    admin_settings = settings or load_admin_settings()
    if not admin_settings:
        return False

    try:
        salt = base64.b64decode(admin_settings["password_salt"])
        iterations = int(admin_settings.get("iterations", 250_000))
        expected = base64.b64decode(admin_settings["password_hash"])
    except (KeyError, ValueError, TypeError):
        return False

    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(candidate, expected)

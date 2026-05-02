from __future__ import annotations

from datetime import datetime

from youth_info_platform.io_utils import public_site_root, read_json, write_json


ROOT = public_site_root()
CONTACT_SETTINGS_PATH = ROOT / "content" / "contact_settings.json"

DEFAULT_CONTACT_SETTINGS = {
    "organization_name": "유스사이드(Youthside)",
    "copyright_text": "© 2026 유스사이드 · 박진감",
    "version_text": "v0.3",
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

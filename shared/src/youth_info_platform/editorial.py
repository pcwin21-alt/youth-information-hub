from __future__ import annotations

from pathlib import Path
from typing import Any

from .article_metadata import article_identity_key, normalize_article_record, normalize_tracking_url
from .io_utils import read_json, runtime_pipeline_root


DECISION_DEFAULT = "default"
DECISION_EXCLUDE = "exclude"
DECISION_FEATURE = "feature"
DECISION_CHOICES = {DECISION_DEFAULT, DECISION_EXCLUDE, DECISION_FEATURE}


def editorial_overrides_path() -> Path:
    return runtime_pipeline_root() / "editorial_overrides.json"


def normalize_editorial_decision(value: str | None) -> str:
    candidate = (value or "").strip().lower()
    if candidate in DECISION_CHOICES:
        return candidate
    return DECISION_DEFAULT


def normalize_feature_rank(value: Any) -> int | None:
    try:
        rank = int(value)
    except (TypeError, ValueError):
        return None
    if rank <= 0:
        return None
    return rank


def build_article_identifiers(article: dict[str, Any]) -> list[str]:
    normalized = normalize_article_record(article)
    candidates = [
        normalized.get("article_key"),
        normalized.get("normalized_url"),
        normalized.get("canonical_url"),
        normalized.get("publisher_url"),
        normalized.get("url"),
        normalized.get("feed_url"),
    ]

    identifiers: list[str] = []
    for candidate in candidates:
        normalized_value = normalize_tracking_url(candidate)
        if normalized_value and normalized_value not in identifiers:
            identifiers.append(normalized_value)

    identity = article_identity_key(normalized)
    if identity and identity not in identifiers:
        identifiers.append(identity)
    return identifiers


def load_editorial_overrides(path: Path | None = None) -> dict[str, dict[str, Any]]:
    payload = read_json(path or editorial_overrides_path(), default={})
    records = payload.get("articles", []) if isinstance(payload, dict) else []
    index: dict[str, dict[str, Any]] = {}

    for record in records:
        if not isinstance(record, dict):
            continue
        decision = normalize_editorial_decision(record.get("decision"))
        if decision == DECISION_DEFAULT:
            continue
        normalized_record = {
            **record,
            "decision": decision,
            "feature_rank": normalize_feature_rank(record.get("feature_rank")),
            "identifiers": list(dict.fromkeys(record.get("identifiers") or [])),
        }
        for identifier in normalized_record["identifiers"]:
            if identifier:
                index[identifier] = normalized_record
    return index


def apply_editorial_overrides(
    articles: list[dict[str, Any]],
    overrides: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    override_index = overrides if overrides is not None else load_editorial_overrides()
    updated_articles: list[dict[str, Any]] = []

    for article in articles:
        updated = dict(article)
        matched_record = None
        for identifier in build_article_identifiers(updated):
            matched_record = override_index.get(identifier)
            if matched_record is not None:
                break

        if matched_record is None:
            updated["editorial_decision"] = normalize_editorial_decision(updated.get("editorial_decision"))
            updated["editorial_feature_rank"] = normalize_feature_rank(updated.get("editorial_feature_rank"))
            updated["editorial_note"] = (updated.get("editorial_note") or "").strip()
            updated_articles.append(updated)
            continue

        updated["editorial_decision"] = matched_record["decision"]
        updated["editorial_feature_rank"] = matched_record.get("feature_rank")
        updated["editorial_note"] = (matched_record.get("note") or "").strip()
        updated["editorial_updated_at"] = matched_record.get("updated_at")
        updated["editorial_updated_by"] = matched_record.get("updated_by")
        updated_articles.append(updated)

    return updated_articles

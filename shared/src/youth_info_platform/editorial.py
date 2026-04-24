from __future__ import annotations

from pathlib import Path
from typing import Any

from .article_metadata import (
    article_identity_key,
    is_portal_url,
    normalize_article_record,
    normalize_tracking_url,
)
from .constants import CATEGORY_OPINION
from .io_utils import read_json, runtime_pipeline_root


DECISION_DEFAULT = "default"
DECISION_INCLUDE = "include"
DECISION_EXCLUDE = "exclude"
DECISION_CHOICES = {DECISION_DEFAULT, DECISION_INCLUDE, DECISION_EXCLUDE}
LEGACY_DECISION_FEATURE = "feature"
CLEAN_SCORE_THRESHOLD = 4


def editorial_overrides_path() -> Path:
    return runtime_pipeline_root() / "editorial_overrides.json"


def normalize_editorial_decision(value: str | None) -> str:
    candidate = (value or "").strip().lower()
    if candidate == LEGACY_DECISION_FEATURE:
        return DECISION_INCLUDE
    if candidate in DECISION_CHOICES:
        return candidate
    return DECISION_DEFAULT


def normalize_editorial_highlighted(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    candidate = str(value or "").strip().lower()
    return candidate in {"1", "true", "yes", "on", "highlight", "highlighted"}


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


def load_editorial_payload(path: Path | None = None) -> dict[str, Any]:
    payload = read_json(path or editorial_overrides_path(), default={})
    return payload if isinstance(payload, dict) else {}


def _normalize_override_record(record: dict[str, Any]) -> dict[str, Any]:
    decision = normalize_editorial_decision(record.get("decision"))
    is_highlighted = normalize_editorial_highlighted(record.get("is_highlighted"))
    if decision == DECISION_EXCLUDE:
        is_highlighted = False
    elif is_highlighted:
        decision = DECISION_INCLUDE
    return {
        **record,
        "decision": decision,
        "is_highlighted": is_highlighted,
        "identifiers": list(dict.fromkeys(record.get("identifiers") or [])),
    }


def load_editorial_overrides(path: Path | None = None) -> dict[str, dict[str, Any]]:
    payload = load_editorial_payload(path)
    records = payload.get("articles", [])
    index: dict[str, dict[str, Any]] = {}

    if not isinstance(records, list):
        return index

    for record in records:
        if not isinstance(record, dict):
            continue
        normalized_record = _normalize_override_record(record)
        if normalized_record["decision"] == DECISION_DEFAULT and not normalized_record["is_highlighted"]:
            continue
        for identifier in normalized_record["identifiers"]:
            if identifier:
                index[identifier] = normalized_record
    return index


def load_manual_editorial_articles(path: Path | None = None) -> list[dict[str, Any]]:
    payload = load_editorial_payload(path)
    records = payload.get("manual_articles", [])
    if not isinstance(records, list):
        return []
    return [dict(record) for record in records if isinstance(record, dict)]


def clean_signal(article: dict[str, Any]) -> tuple[int, list[str], bool]:
    normalized = normalize_article_record(article)
    score = 0
    labels: list[str] = []

    if normalized.get("is_official_source") or normalized.get("source_kind") in {"official", "local"}:
        score += 3
        labels.append("공식·공공")

    canonical_url = normalized.get("canonical_url")
    publisher_url = normalized.get("publisher_url")
    if publisher_url or (canonical_url and not is_portal_url(canonical_url)):
        score += 2
        labels.append("원문링크")

    if normalized.get("source") or normalized.get("source_name"):
        score += 1
    if normalized.get("publisher_published_at") or normalized.get("published_date") or normalized.get("portal_published_at"):
        score += 1
        labels.append("날짜확인")
    if normalized.get("lead_text") or normalized.get("body_text"):
        score += 1
        labels.append("본문확보")
    if normalized.get("issue_tags") or normalized.get("governance_scope") or normalized.get("region"):
        score += 1
        labels.append("맥락명확")

    is_portal_only = bool(
        normalized.get("portal_urls")
        and not normalized.get("publisher_url")
        and (not canonical_url or is_portal_url(canonical_url))
    )
    if is_portal_only:
        score -= 2

    categories = set(normalized.get("categories") or [])
    article_type = str(normalized.get("article_type") or "").strip().lower()
    is_noise = bool(normalized.get("is_noise"))
    is_opinion = article_type == "opinion" or CATEGORY_OPINION in categories

    if is_noise:
        score -= 4
    if is_opinion:
        score -= 3

    is_clean = score >= CLEAN_SCORE_THRESHOLD and not is_noise and not is_opinion
    return score, labels, is_clean


def apply_clean_signal(article: dict[str, Any]) -> dict[str, Any]:
    updated = dict(article)
    score, labels, is_clean = clean_signal(updated)
    updated["clean_score"] = score
    updated["clean_labels"] = labels
    updated["is_clean_article"] = is_clean
    return updated


def is_clean_article(article: dict[str, Any]) -> bool:
    if article.get("is_clean_article") is not None:
        return bool(article.get("is_clean_article"))
    _, _, is_clean = clean_signal(article)
    return is_clean


def merge_manual_articles(
    classified_articles: list[dict[str, Any]],
    manual_articles: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    appended_manual_articles = manual_articles if manual_articles is not None else load_manual_editorial_articles()
    if not appended_manual_articles:
        return [apply_clean_signal(article) for article in classified_articles]

    merged_by_key: dict[str, dict[str, Any]] = {}
    order: list[str] = []

    for article in classified_articles:
        normalized = apply_clean_signal(article)
        key = article_identity_key(normalized)
        merged_by_key[key] = normalized
        order.append(key)

    for article in appended_manual_articles:
        normalized_manual = apply_clean_signal(article)
        key = article_identity_key(normalized_manual)
        if not key:
            continue

        if key in merged_by_key:
            merged = dict(merged_by_key[key])
            for field_name in (
                "editorial_decision",
                "editorial_note",
                "editorial_updated_at",
                "editorial_updated_by",
                "editorial_is_highlighted",
                "clean_score",
                "clean_labels",
                "is_clean_article",
            ):
                if field_name in normalized_manual:
                    merged[field_name] = normalized_manual[field_name]
            merged_by_key[key] = merged
            continue

        merged_by_key[key] = normalized_manual
        order.append(key)

    return [merged_by_key[key] for key in order]


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
            updated["editorial_is_highlighted"] = normalize_editorial_highlighted(
                updated.get("editorial_is_highlighted")
            )
            updated["editorial_note"] = (updated.get("editorial_note") or "").strip()
        else:
            updated["editorial_decision"] = matched_record["decision"]
            updated["editorial_is_highlighted"] = matched_record.get("is_highlighted", False)
            updated["editorial_note"] = (matched_record.get("note") or "").strip()
            updated["editorial_updated_at"] = matched_record.get("updated_at")
            updated["editorial_updated_by"] = matched_record.get("updated_by")

        if updated["editorial_decision"] == DECISION_EXCLUDE:
            updated["editorial_is_highlighted"] = False
        elif updated["editorial_is_highlighted"]:
            updated["editorial_decision"] = DECISION_INCLUDE

        updated_articles.append(apply_clean_signal(updated))

    return updated_articles


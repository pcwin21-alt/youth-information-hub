from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime

from youth_info_platform.article_metadata import preferred_article_url
from youth_info_platform.io_utils import read_json, runtime_pipeline_root

from briefings.models import SyncedArticle


def runtime_article_key(article: dict) -> str:
    for field_name in ("normalized_url", "canonical_url", "publisher_url", "url"):
        value = (article.get(field_name) or "").strip()
        if value:
            return value
    title = (article.get("title") or "").strip() or "untitled"
    published = (article.get("published_date") or "").strip() or "undated"
    return f"title::{published}::{title}"


def runtime_article_defaults(article: dict) -> dict[str, object]:
    published_raw = article.get("published_date")
    published_date = parse_datetime(published_raw) if isinstance(published_raw, str) else None
    return {
        "title": (article.get("title") or "").strip(),
        "article_url": preferred_article_url(article).strip(),
        "source_name": (article.get("source") or article.get("source_name") or article.get("publisher_domain") or "").strip(),
        "source_url": (
            article.get("source_homepage_url")
            or article.get("source_url")
            or article.get("publisher_url")
            or article.get("canonical_url")
            or ""
        ),
        "source_kind": (article.get("source_kind") or "").strip(),
        "published_date": published_date,
        "region": (article.get("region") or "").strip(),
        "categories": list(article.get("categories") or []),
        "governance_scope": (article.get("governance_scope") or "").strip(),
        "hub_owner_label": (article.get("hub_owner_label") or "").strip(),
        "hub_topics": list(article.get("hub_topics") or []),
        "importance_score": article.get("importance_score"),
        "selection_bucket": (article.get("selection_bucket") or "").strip(),
        "is_noise": bool(article.get("is_noise")),
        "is_official_source": bool(article.get("is_official_source")),
        "lead_text": (article.get("lead_text") or "").strip(),
        "summary": (article.get("summary") or "").strip(),
        "raw_payload": article,
    }


class Command(BaseCommand):
    help = "Sync public runtime article candidates into the institution-site database."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--source",
            default=str(runtime_pipeline_root() / "step3_classified.json"),
            help="Path to the runtime classified articles JSON file.",
        )

    def handle(self, *args, **options) -> None:
        source_path = Path(options["source"])
        payload = read_json(source_path, default=None)
        if payload is None:
            raise CommandError(f"missing_runtime_source:{source_path}")
        if not isinstance(payload, list):
            raise CommandError("invalid_runtime_payload")

        created_count = 0
        updated_count = 0
        for article in payload:
            if not isinstance(article, dict):
                continue

            article_key = runtime_article_key(article)
            defaults = runtime_article_defaults(article)
            _, created = SyncedArticle.objects.update_or_create(article_key=article_key, defaults=defaults)
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(f"runtime_source={source_path}")
        self.stdout.write(f"runtime_articles={len(payload)}")
        self.stdout.write(f"created={created_count}")
        self.stdout.write(f"updated={updated_count}")
        self.stdout.write(f"runtime_pipeline_root={settings.INSTITUTION_RUNTIME_PIPELINE_ROOT}")

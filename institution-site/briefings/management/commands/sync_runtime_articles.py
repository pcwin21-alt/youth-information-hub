from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from youth_info_platform.io_utils import read_json, runtime_pipeline_root

from briefings.editorial import build_synced_article_defaults
from briefings.models import SyncedArticle


def runtime_article_key(article: dict) -> str:
    for field_name in ("normalized_url", "canonical_url", "publisher_url", "url"):
        value = (article.get(field_name) or "").strip()
        if value:
            return value
    title = (article.get("title") or "").strip() or "untitled"
    published = (article.get("published_date") or "").strip() or "undated"
    return f"title::{published}::{title}"


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
            defaults = build_synced_article_defaults(article, is_manual_entry=bool(article.get("is_manual_entry")))
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

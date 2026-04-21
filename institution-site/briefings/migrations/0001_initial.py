from __future__ import annotations

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ReportDraft",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200)),
                ("body", models.TextField(blank=True)),
                ("filters", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="report_drafts", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={"ordering": ["-updated_at"]},
        ),
        migrations.CreateModel(
            name="StaffProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(choices=[("platform_admin", "Platform admin"), ("staff", "Staff")], default="staff", max_length=32)),
                ("organization", models.CharField(blank=True, max_length=120)),
                ("home_region", models.CharField(blank=True, max_length=80)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="staff_profile", to=settings.AUTH_USER_MODEL),
                ),
            ],
        ),
        migrations.CreateModel(
            name="SyncedArticle",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("article_key", models.CharField(max_length=500, unique=True)),
                ("title", models.CharField(max_length=300)),
                ("source_name", models.CharField(blank=True, max_length=160)),
                ("source_url", models.URLField(blank=True, max_length=1000)),
                ("published_date", models.DateTimeField(blank=True, null=True)),
                ("region", models.CharField(blank=True, max_length=80)),
                ("categories", models.JSONField(blank=True, default=list)),
                ("governance_scope", models.CharField(blank=True, max_length=80)),
                ("hub_owner_label", models.CharField(blank=True, max_length=120)),
                ("hub_topics", models.JSONField(blank=True, default=list)),
                ("lead_text", models.TextField(blank=True)),
                ("summary", models.TextField(blank=True)),
                ("raw_payload", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["-published_date", "-updated_at"]},
        ),
        migrations.CreateModel(
            name="TrackedRegion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("region_name", models.CharField(max_length=80)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tracked_regions", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={"ordering": ["region_name"]},
        ),
        migrations.CreateModel(
            name="SavedArticle",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "article",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="saved_by", to="briefings.syncedarticle"),
                ),
                (
                    "user",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="saved_articles", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="ExportJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("export_format", models.CharField(choices=[("clipboard", "Clipboard"), ("hwpx", "HWPX"), ("hwp", "HWP")], default="clipboard", max_length=16)),
                ("state", models.CharField(choices=[("pending", "Pending"), ("completed", "Completed"), ("failed", "Failed")], default="pending", max_length=16)),
                ("file_path", models.CharField(blank=True, max_length=400)),
                ("error_message", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "report_draft",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="export_jobs", to="briefings.reportdraft"),
                ),
                (
                    "user",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="export_jobs", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="trackedregion",
            constraint=models.UniqueConstraint(fields=("user", "region_name"), name="unique_tracked_region_per_user"),
        ),
        migrations.AddConstraint(
            model_name="savedarticle",
            constraint=models.UniqueConstraint(fields=("user", "article"), name="unique_saved_article_per_user"),
        ),
    ]

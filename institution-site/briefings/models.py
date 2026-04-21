from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class StaffProfile(models.Model):
    ROLE_PLATFORM_ADMIN = "platform_admin"
    ROLE_STAFF = "staff"
    ROLE_CHOICES = [
        (ROLE_PLATFORM_ADMIN, "Platform admin"),
        (ROLE_STAFF, "Staff"),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="staff_profile")
    role = models.CharField(max_length=32, choices=ROLE_CHOICES, default=ROLE_STAFF)
    organization = models.CharField(max_length=120, blank=True)
    home_region = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.user.username} ({self.role})"


class AdminAuditLog(models.Model):
    SCOPE_EDITORIAL = "editorial"
    SCOPE_CONTACT = "contact"
    SCOPE_PUBLISH = "publish"
    SCOPE_ROLE = "role"
    SCOPE_CHOICES = [
        (SCOPE_EDITORIAL, "Editorial"),
        (SCOPE_CONTACT, "Contact"),
        (SCOPE_PUBLISH, "Publish"),
        (SCOPE_ROLE, "Role"),
    ]

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admin_audit_logs",
    )
    scope = models.CharField(max_length=32, choices=SCOPE_CHOICES)
    action = models.CharField(max_length=80)
    target_key = models.CharField(max_length=300, blank=True)
    summary = models.CharField(max_length=300)
    before_data = models.JSONField(default=dict, blank=True)
    after_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["scope", "created_at"], name="audit_scope_created_idx"),
            models.Index(fields=["created_at"], name="audit_created_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.scope}:{self.action} @ {self.created_at:%Y-%m-%d %H:%M}"


class PageViewEvent(models.Model):
    SCOPE_PUBLIC = "public"
    SCOPE_INSTITUTION = "institution"
    SCOPE_CHOICES = [
        (SCOPE_PUBLIC, "Public"),
        (SCOPE_INSTITUTION, "Institution"),
    ]

    site_scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default=SCOPE_PUBLIC)
    visitor_id = models.CharField(max_length=80)
    session_id = models.CharField(max_length=80, blank=True)
    page_path = models.CharField(max_length=300)
    page_url = models.URLField(max_length=1000, blank=True)
    page_title = models.CharField(max_length=200, blank=True)
    referrer_url = models.URLField(max_length=1000, blank=True)
    referrer_host = models.CharField(max_length=200, blank=True)
    source_origin = models.CharField(max_length=200, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["site_scope", "occurred_at"], name="pageview_scope_time_idx"),
            models.Index(fields=["visitor_id", "occurred_at"], name="pageview_visitor_time_idx"),
            models.Index(fields=["page_path", "occurred_at"], name="pageview_path_time_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.site_scope}:{self.page_path} @ {self.occurred_at:%Y-%m-%d %H:%M}"


class TrackedRegion(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tracked_regions")
    region_name = models.CharField(max_length=80)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "region_name"], name="unique_tracked_region_per_user"),
        ]
        ordering = ["region_name"]

    def __str__(self) -> str:
        return f"{self.user.username}: {self.region_name}"


class SyncedArticle(models.Model):
    DECISION_DEFAULT = "default"
    DECISION_EXCLUDE = "exclude"
    DECISION_FEATURE = "feature"
    EDITORIAL_DECISION_CHOICES = [
        (DECISION_DEFAULT, "기본"),
        (DECISION_FEATURE, "상단 노출"),
        (DECISION_EXCLUDE, "배제"),
    ]

    article_key = models.CharField(max_length=500, unique=True)
    title = models.CharField(max_length=300)
    article_url = models.URLField(max_length=1000, blank=True)
    source_name = models.CharField(max_length=160, blank=True)
    source_url = models.URLField(max_length=1000, blank=True)
    source_kind = models.CharField(max_length=40, blank=True)
    published_date = models.DateTimeField(null=True, blank=True)
    region = models.CharField(max_length=80, blank=True)
    categories = models.JSONField(default=list, blank=True)
    governance_scope = models.CharField(max_length=80, blank=True)
    hub_owner_label = models.CharField(max_length=120, blank=True)
    hub_topics = models.JSONField(default=list, blank=True)
    importance_score = models.IntegerField(null=True, blank=True)
    selection_bucket = models.CharField(max_length=40, blank=True)
    is_noise = models.BooleanField(default=False)
    is_official_source = models.BooleanField(default=False)
    editorial_decision = models.CharField(
        max_length=16,
        choices=EDITORIAL_DECISION_CHOICES,
        default=DECISION_DEFAULT,
    )
    editorial_feature_rank = models.PositiveSmallIntegerField(null=True, blank=True)
    editorial_note = models.TextField(blank=True)
    editorial_updated_at = models.DateTimeField(null=True, blank=True)
    editorial_updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="editorially_updated_articles",
    )
    lead_text = models.TextField(blank=True)
    summary = models.TextField(blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-published_date", "-updated_at"]

    def __str__(self) -> str:
        return self.title

    @property
    def is_editorially_featured(self) -> bool:
        return self.editorial_decision == self.DECISION_FEATURE

    @property
    def is_editorially_excluded(self) -> bool:
        return self.editorial_decision == self.DECISION_EXCLUDE


class SavedArticle(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_articles")
    article = models.ForeignKey(SyncedArticle, on_delete=models.CASCADE, related_name="saved_by")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "article"], name="unique_saved_article_per_user"),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user.username}: {self.article.title}"


class ReportDraft(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="report_drafts")
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    filters = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return self.title


class ExportJob(models.Model):
    FORMAT_CLIPBOARD = "clipboard"
    FORMAT_HWPX = "hwpx"
    FORMAT_HWP = "hwp"
    FORMAT_CHOICES = [
        (FORMAT_CLIPBOARD, "Clipboard"),
        (FORMAT_HWPX, "HWPX"),
        (FORMAT_HWP, "HWP"),
    ]

    STATE_PENDING = "pending"
    STATE_COMPLETED = "completed"
    STATE_FAILED = "failed"
    STATE_CHOICES = [
        (STATE_PENDING, "Pending"),
        (STATE_COMPLETED, "Completed"),
        (STATE_FAILED, "Failed"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="export_jobs")
    report_draft = models.ForeignKey(
        ReportDraft,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="export_jobs",
    )
    export_format = models.CharField(max_length=16, choices=FORMAT_CHOICES, default=FORMAT_CLIPBOARD)
    state = models.CharField(max_length=16, choices=STATE_CHOICES, default=STATE_PENDING)
    file_path = models.CharField(max_length=400, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user.username}: {self.export_format} ({self.state})"


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def ensure_staff_profile(sender, instance, created, **kwargs):  # noqa: ANN001,ARG001
    if created:
        StaffProfile.objects.create(user=instance)

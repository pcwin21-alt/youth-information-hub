from __future__ import annotations

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.admin.sites import NotRegistered

from .editorial import create_admin_audit_log
from .models import (
    AdminAuditLog,
    ExportJob,
    PageViewEvent,
    ReportDraft,
    SavedArticle,
    StaffProfile,
    SyncedArticle,
    TrackedRegion,
)


User = get_user_model()


try:
    admin.site.unregister(User)
except NotRegistered:
    pass


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = (
        "username",
        "email",
        "is_active",
        "is_staff",
        "is_superuser",
        "staff_role",
        "staff_organization",
        "staff_region",
        "last_login",
    )
    list_filter = (*DjangoUserAdmin.list_filter, "staff_profile__role")
    search_fields = ("username", "email", "first_name", "last_name", "staff_profile__organization")
    readonly_fields = (*DjangoUserAdmin.readonly_fields, "staff_role", "staff_organization", "staff_region")
    fieldsets = DjangoUserAdmin.fieldsets + (
        (
            "운영 정보",
            {
                "fields": (
                    "staff_role",
                    "staff_organization",
                    "staff_region",
                )
            },
        ),
    )

    @admin.display(description="역할")
    def staff_role(self, obj):  # noqa: ANN001
        profile = getattr(obj, "staff_profile", None)
        return profile.get_role_display() if profile else "-"

    @admin.display(description="조직")
    def staff_organization(self, obj):  # noqa: ANN001
        profile = getattr(obj, "staff_profile", None)
        return profile.organization if profile else ""

    @admin.display(description="지역")
    def staff_region(self, obj):  # noqa: ANN001
        profile = getattr(obj, "staff_profile", None)
        return profile.home_region if profile else ""


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "organization", "home_region", "updated_at")
    search_fields = ("user__username", "organization", "home_region")
    list_filter = ("role", "organization", "home_region")
    readonly_fields = ("created_at", "updated_at")

    def save_model(self, request, obj, form, change):  # noqa: ANN001
        before_state = {}
        if change:
            previous = StaffProfile.objects.get(pk=obj.pk)
            before_state = {
                "role": previous.role,
                "organization": previous.organization,
                "home_region": previous.home_region,
            }
        super().save_model(request, obj, form, change)
        after_state = {
            "role": obj.role,
            "organization": obj.organization,
            "home_region": obj.home_region,
        }
        if not change or before_state != after_state:
            summary = "운영자 권한 정보를 수정했습니다." if change else "운영자 권한 정보를 등록했습니다."
            create_admin_audit_log(
                request.user,
                AdminAuditLog.SCOPE_ROLE,
                "update_staff_profile",
                target_key=str(obj.user_id),
                summary=summary,
                before_data=before_state,
                after_data=after_state,
            )

    def log_addition(self, request, obj, message):  # noqa: ANN001
        return None

    def log_change(self, request, obj, message):  # noqa: ANN001
        return None

    def log_deletion(self, request, obj, object_repr):  # noqa: ANN001
        return None


@admin.register(TrackedRegion)
class TrackedRegionAdmin(admin.ModelAdmin):
    list_display = ("user", "region_name", "created_at")
    search_fields = ("user__username", "region_name")


@admin.register(SyncedArticle)
class SyncedArticleAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "editorial_decision",
        "editorial_feature_rank",
        "source_name",
        "region",
        "published_date",
        "updated_at",
    )
    search_fields = ("title", "region", "source_name", "hub_owner_label", "editorial_note")
    list_filter = ("editorial_decision", "region", "governance_scope", "is_official_source", "source_kind")
    readonly_fields = (
        "article_key",
        "title",
        "article_url",
        "source_name",
        "source_url",
        "source_kind",
        "published_date",
        "region",
        "categories",
        "governance_scope",
        "hub_owner_label",
        "hub_topics",
        "importance_score",
        "selection_bucket",
        "is_noise",
        "is_official_source",
        "lead_text",
        "summary",
        "raw_payload",
        "editorial_updated_at",
        "editorial_updated_by",
        "created_at",
        "updated_at",
    )
    fieldsets = (
        (
            "운영 결정",
            {
                "fields": (
                    "editorial_decision",
                    "editorial_feature_rank",
                    "editorial_note",
                    "editorial_updated_at",
                    "editorial_updated_by",
                )
            },
        ),
        (
            "기사 정보",
            {
                "fields": (
                    "title",
                    "article_key",
                    "article_url",
                    "source_name",
                    "source_url",
                    "source_kind",
                    "published_date",
                    "region",
                    "categories",
                    "governance_scope",
                    "hub_owner_label",
                    "hub_topics",
                    "importance_score",
                    "selection_bucket",
                    "is_noise",
                    "is_official_source",
                    "lead_text",
                    "summary",
                    "raw_payload",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )


@admin.register(AdminAuditLog)
class AdminAuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "scope", "action", "actor", "target_key", "summary")
    list_filter = ("scope", "action", "created_at")
    search_fields = ("summary", "target_key", "actor__username")
    readonly_fields = ("actor", "scope", "action", "target_key", "summary", "before_data", "after_data", "created_at")

    def has_add_permission(self, request):  # noqa: ANN001
        return False

    def has_view_permission(self, request, obj=None):  # noqa: ANN001
        return bool(request.user and request.user.is_active and request.user.is_staff)

    def has_change_permission(self, request, obj=None):  # noqa: ANN001
        return False

    def has_delete_permission(self, request, obj=None):  # noqa: ANN001
        return False


@admin.register(PageViewEvent)
class PageViewEventAdmin(admin.ModelAdmin):
    list_display = ("occurred_at", "site_scope", "page_path", "page_title", "visitor_id", "referrer_host")
    list_filter = ("site_scope", "occurred_at", "referrer_host")
    search_fields = ("page_path", "page_title", "visitor_id", "session_id", "referrer_host")
    readonly_fields = (
        "site_scope",
        "visitor_id",
        "session_id",
        "page_path",
        "page_url",
        "page_title",
        "referrer_url",
        "referrer_host",
        "source_origin",
        "user_agent",
        "occurred_at",
    )

    def has_add_permission(self, request):  # noqa: ANN001
        return False


@admin.register(SavedArticle)
class SavedArticleAdmin(admin.ModelAdmin):
    list_display = ("user", "article", "created_at")
    search_fields = ("user__username", "article__title")


@admin.register(ReportDraft)
class ReportDraftAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "updated_at")
    search_fields = ("title", "user__username")


@admin.register(ExportJob)
class ExportJobAdmin(admin.ModelAdmin):
    list_display = ("user", "export_format", "state", "created_at", "updated_at")
    search_fields = ("user__username", "file_path")
    list_filter = ("export_format", "state")

from __future__ import annotations
import os
import subprocess
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.management import call_command
from django.core.paginator import Paginator
from django.db.models import Case, IntegerField, Q, Value, When
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from youth_info_platform.auto_update_config import (
    AUTO_UPDATE_SETTINGS_PATH,
    load_auto_update_settings,
    load_auto_update_status,
    save_auto_update_settings,
)
from youth_info_platform.contact_config import CONTACT_SETTINGS_PATH, load_contact_settings, save_contact_settings
from youth_info_platform.editorial import editorial_overrides_path
from youth_info_platform.io_utils import read_json, runtime_pipeline_root, write_json

from .analytics import analytics_dashboard_context, record_page_view
from .editorial import (
    DECISION_DEFAULT,
    DECISION_EXCLUDE,
    DECISION_FEATURE,
    PipelineLockedError,
    create_admin_audit_log,
    export_editorial_overrides,
    load_pipeline_lock_snapshot,
    run_contact_settings_refresh,
    run_manual_news_refresh,
    run_public_editorial_refresh,
    user_can_manage_editorial,
)
from .models import AdminAuditLog, PageViewEvent, ReportDraft, SavedArticle, SyncedArticle


CONTACT_SETTING_FIELDS = (
    "organization_name",
    "copyright_text",
    "version_text",
    "email",
    "extra_line_1",
    "extra_line_2",
)
OPS_RADAR_PATH = runtime_pipeline_root() / "ops_radar.json"
AUTO_UPDATE_RUNNER_STALE_MINUTES = 5
AUTO_UPDATE_STATE_LABELS = {
    "starting": "시작 중",
    "checking": "기사 점검 중",
    "checked": "점검 완료",
    "idle_no_change": "변화 없음",
    "publishing": "공개 반영 중",
    "published": "반영 완료",
    "waiting_for_lock": "다른 파이프라인 대기 중",
    "disabled": "자동 반영 꺼짐",
    "stopped": "실행 중지",
    "error": "오류",
}


def _redirect_target(request: HttpRequest, fallback: str) -> str:
    return request.POST.get("next") or request.GET.get("next") or fallback


def _decision_label(decision: str) -> str:
    labels = {
        DECISION_DEFAULT: "기본",
        DECISION_FEATURE: "상단 노출",
        DECISION_EXCLUDE: "배제",
    }
    return labels.get(decision, decision)


def _command_brief(record: dict) -> str:
    output = (record.get("stdout") or record.get("stderr") or "").strip()
    if output:
        first_line = output.splitlines()[0][:180]
        return f"{record.get('command')}: {first_line}"
    return f"{record.get('command')}: completed"


def _editorial_response_forbidden() -> HttpResponseForbidden:
    return HttpResponseForbidden("관리 권한이 필요합니다.")


def _contact_form_payload(request: HttpRequest, current: dict[str, str] | None = None) -> dict[str, str]:
    source = current or {}
    return {
        field_name: (request.POST.get(field_name) or source.get(field_name, "")).strip()
        for field_name in CONTACT_SETTING_FIELDS
    }


def _auto_update_form_payload(request: HttpRequest, current: dict[str, object] | None = None) -> dict[str, object]:
    source = current or {}
    return {
        "enabled": bool(request.POST.get("auto_update_enabled")),
        "interval_minutes": request.POST.get("auto_update_interval_minutes") or source.get("interval_minutes", 10),
        "skip_outbound_notifications": True,
        "publish_on_article_change_only": True,
    }


def _auto_update_interval_minutes(settings: dict[str, object]) -> int:
    try:
        return max(3, min(60, int(settings.get("interval_minutes", 10))))
    except (TypeError, ValueError):
        return 10


def _auto_update_heartbeat_deadline(settings: dict[str, object]) -> timedelta:
    interval_minutes = _auto_update_interval_minutes(settings)
    return timedelta(minutes=max(AUTO_UPDATE_RUNNER_STALE_MINUTES, interval_minutes * 2 + 2))


def _process_exists(pid: int | None) -> bool | None:
    if not pid:
        return False

    try:
        if os.name == "nt":
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                check=False,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                return None
            output = (result.stdout or "").strip()
            if not output or "No tasks are running" in output:
                return False
            return f'"{pid}"' in output or f",{pid}," in output
        os.kill(pid, 0)
        return True
    except OSError:
        return False
    except Exception:
        return None


def _build_auto_update_runtime(
    settings: dict[str, object] | None = None,
    status: dict[str, object] | None = None,
) -> dict[str, object]:
    settings = settings or load_auto_update_settings()
    status = status or load_auto_update_status()

    is_enabled = bool(settings.get("enabled"))
    interval_minutes = _auto_update_interval_minutes(settings)
    heartbeat_deadline = _auto_update_heartbeat_deadline(settings)
    updated_at_raw = status.get("updated_at")
    updated_at = parse_datetime(updated_at_raw) if isinstance(updated_at_raw, str) else None
    now = timezone.now()
    heartbeat_recent = bool(updated_at and now - updated_at <= heartbeat_deadline)

    raw_state = str(status.get("state") or "").strip()
    runner_pid_raw = status.get("runner_pid")
    try:
        runner_pid = int(runner_pid_raw) if runner_pid_raw not in (None, "") else None
    except (TypeError, ValueError):
        runner_pid = None
    runner_alive = _process_exists(runner_pid)
    expected_running = is_enabled
    is_runner_missing = expected_running and (not heartbeat_recent or runner_alive is False)

    if not is_enabled:
        display_state = "자동 반영 꺼짐"
        summary = "자동 반영 설정이 꺼져 있습니다."
    elif is_runner_missing:
        display_state = "설정 ON / 러너 미실행"
        summary = (
            "이 기능은 이 노트북에서 자동 반영 러너가 실행 중일 때만 동작합니다. "
            "start_auto_update.ps1로 시작하고 stop_auto_update.ps1로 멈춥니다."
        )
    else:
        state_label = AUTO_UPDATE_STATE_LABELS.get(raw_state, raw_state or "실행 중")
        display_state = f"실행 중 · {state_label}" if raw_state else "실행 중"
        summary = "노트북이 켜져 있고 자동 반영 러너가 주기적으로 새 기사를 확인하고 있습니다."

    return {
        "display_state": display_state,
        "summary": summary,
        "raw_state": raw_state,
        "raw_state_label": AUTO_UPDATE_STATE_LABELS.get(raw_state, raw_state or "상태 없음"),
        "heartbeat_recent": heartbeat_recent,
        "heartbeat_deadline_minutes": int(heartbeat_deadline.total_seconds() // 60),
        "runner_pid": runner_pid,
        "runner_alive": runner_alive,
        "updated_at": updated_at_raw,
        "last_checked_at": status.get("last_checked_at"),
        "last_published_at": status.get("last_published_at"),
        "next_check_at": status.get("next_check_at"),
        "last_error": status.get("last_error") or "",
        "interval_minutes": interval_minutes,
        "enabled": is_enabled,
    }


def _auto_update_context_bundle(
    settings: dict[str, object] | None = None,
    status: dict[str, object] | None = None,
) -> dict[str, object]:
    resolved_settings = settings or load_auto_update_settings()
    resolved_status = status or load_auto_update_status()
    return {
        "auto_update_settings": resolved_settings,
        "auto_update_status": resolved_status,
        "auto_update_runtime": _build_auto_update_runtime(resolved_settings, resolved_status),
        "auto_update_start_command": r"public-site\scripts\start_auto_update.ps1",
        "auto_update_stop_command": r"public-site\scripts\stop_auto_update.ps1",
    }


def _load_ops_radar_payload(*, limit: int = 8) -> dict[str, object]:
    payload = read_json(OPS_RADAR_PATH, default={})
    if not isinstance(payload, dict):
        return {"generated_at": None, "summary": {}, "items": []}

    summary = payload.get("summary")
    items = payload.get("items")
    if not isinstance(summary, dict):
        summary = {}
    if not isinstance(items, list):
        items = []

    overlooked_items = [item for item in items if isinstance(item, dict) and item.get("ops_radar_overlooked")]
    return {
        "generated_at": payload.get("generated_at"),
        "summary": summary,
        "items": overlooked_items[:limit],
    }


def _audit_contact_save(
    request: HttpRequest,
    before_settings: dict[str, str],
    after_settings: dict[str, str],
    refresh_result: dict,
) -> None:
    create_admin_audit_log(
        request.user,
        AdminAuditLog.SCOPE_CONTACT,
        "update_contact_settings",
        target_key="contact_settings",
        summary="문의/연락처 설정을 저장했습니다.",
        before_data=before_settings,
        after_data={
            "contact_settings": after_settings,
            "refresh_result": refresh_result,
            "settings_path": str(CONTACT_SETTINGS_PATH),
        },
    )


def _update_article_editorial(article: SyncedArticle, request: HttpRequest) -> str:
    decision = (request.POST.get("editorial_decision") or DECISION_DEFAULT).strip().lower()
    if decision not in {DECISION_DEFAULT, DECISION_EXCLUDE, DECISION_FEATURE}:
        decision = DECISION_DEFAULT

    rank_value = request.POST.get("editorial_feature_rank")
    try:
        feature_rank = int(rank_value) if rank_value else None
    except (TypeError, ValueError):
        feature_rank = None
    if feature_rank is not None and feature_rank <= 0:
        feature_rank = None

    if decision != DECISION_FEATURE:
        feature_rank = None

    note = (request.POST.get("editorial_note") or "").strip()
    before_state = {
        "decision": article.editorial_decision,
        "feature_rank": article.editorial_feature_rank,
        "note": article.editorial_note,
    }
    article.editorial_decision = decision
    article.editorial_feature_rank = feature_rank
    article.editorial_note = note
    article.editorial_updated_at = timezone.now()
    article.editorial_updated_by = request.user
    article.save(
        update_fields=[
            "editorial_decision",
            "editorial_feature_rank",
            "editorial_note",
            "editorial_updated_at",
            "editorial_updated_by",
            "updated_at",
        ]
    )
    override_path = export_editorial_overrides()
    create_admin_audit_log(
        request.user,
        AdminAuditLog.SCOPE_EDITORIAL,
        "update_article_editorial",
        target_key=article.article_key,
        summary=f"기사 운영 결정을 {_decision_label(decision)}로 저장했습니다.",
        before_data=before_state,
        after_data={
            "decision": decision,
            "feature_rank": feature_rank,
            "note": note,
            "override_path": override_path,
        },
    )
    return _decision_label(decision)


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    can_manage_editorial = user_can_manage_editorial(request.user)
    tracked_regions = list(
        request.user.tracked_regions.order_by("region_name").values_list("region_name", flat=True)
    )
    articles = SyncedArticle.objects.order_by("-published_date", "-updated_at")
    if tracked_regions:
        articles = articles.filter(region__in=tracked_regions)

    auto_update_context = _auto_update_context_bundle()
    context = {
        "tracked_regions": tracked_regions,
        "recent_articles": articles[:20],
        "saved_count": SavedArticle.objects.filter(user=request.user).count(),
        "draft_count": ReportDraft.objects.filter(user=request.user).count(),
        "synced_count": SyncedArticle.objects.count(),
        "featured_count": SyncedArticle.objects.filter(editorial_decision=DECISION_FEATURE).count(),
        "excluded_count": SyncedArticle.objects.filter(editorial_decision=DECISION_EXCLUDE).count(),
        "recent_audit_logs": AdminAuditLog.objects.select_related("actor")[:6],
        "public_visitor_count_7d": PageViewEvent.objects.filter(site_scope=PageViewEvent.SCOPE_PUBLIC)
        .values("visitor_id")
        .distinct()
        .count(),
        "can_manage_editorial": can_manage_editorial,
        "ops_radar": _load_ops_radar_payload() if can_manage_editorial else {"generated_at": None, "summary": {}, "items": []},
    }
    context.update(auto_update_context)
    return render(request, "briefings/dashboard.html", context)


@login_required
def editorial_dashboard(request: HttpRequest) -> HttpResponse:
    if not user_can_manage_editorial(request.user):
        return _editorial_response_forbidden()

    redirect_to = reverse("editorial_dashboard")

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        redirect_to = _redirect_target(request, redirect_to)

        if action == "sync_runtime":
            call_command("sync_runtime_articles")
            override_path = export_editorial_overrides()
            create_admin_audit_log(
                request.user,
                AdminAuditLog.SCOPE_EDITORIAL,
                "sync_runtime_articles",
                target_key="runtime_articles",
                summary="운영 후보 기사를 동기화했습니다.",
                after_data={"override_path": override_path},
            )
            messages.success(request, "운영 후보 기사를 최신 상태로 동기화했습니다.")
            return redirect(redirect_to)

        if action == "update_article":
            article = get_object_or_404(SyncedArticle, pk=request.POST.get("article_id"))
            label = _update_article_editorial(article, request)
            messages.success(request, f"운영 결정을 저장했습니다. {label}")
            return redirect(redirect_to)

        if action == "collect_and_refresh_public":
            override_path = export_editorial_overrides()
            try:
                outputs = run_manual_news_refresh()
            except PipelineLockedError as exc:
                snapshot = exc.lock_details or load_pipeline_lock_snapshot()
                create_admin_audit_log(
                    request.user,
                    AdminAuditLog.SCOPE_PUBLISH,
                    "collect_and_refresh_public",
                    target_key="public_site",
                    summary="새 기사 수집과 공개 반영을 시작하지 못했습니다.",
                    after_data={
                        "status": "blocked",
                        "override_path": override_path,
                        "lock_snapshot": snapshot,
                    },
                )
                messages.warning(request, "이미 파이프라인 실행 중입니다. 현재 작업이 끝난 뒤 다시 시도해 주세요.")
                return redirect(redirect_to)
            except subprocess.CalledProcessError as exc:
                create_admin_audit_log(
                    request.user,
                    AdminAuditLog.SCOPE_PUBLISH,
                    "collect_and_refresh_public",
                    target_key="public_site",
                    summary="새 기사 수집과 공개 반영 중 오류가 발생했습니다.",
                    after_data={
                        "status": "failed",
                        "override_path": override_path,
                        "command": exc.cmd,
                        "returncode": exc.returncode,
                        "stdout": (exc.output or "").strip(),
                        "stderr": (exc.stderr or "").strip(),
                    },
                )
                messages.error(request, "새 기사 수집과 공개 반영 중 오류가 발생했습니다.")
                if exc.stderr:
                    messages.error(request, exc.stderr.strip().splitlines()[0][:180])
                return redirect(redirect_to)

            sync_failed = None
            try:
                call_command("sync_runtime_articles")
            except Exception as exc:  # noqa: BLE001
                sync_failed = str(exc)
                create_admin_audit_log(
                    request.user,
                    AdminAuditLog.SCOPE_PUBLISH,
                    "sync_runtime_articles_after_manual_refresh",
                    target_key="runtime_articles",
                    summary="수동 전체 반영 후 기사 동기화에 실패했습니다.",
                    after_data={"error": sync_failed},
                )
                messages.warning(request, "공개 반영은 완료됐지만 관리자 기사 목록 동기화에는 실패했습니다.")

            create_admin_audit_log(
                request.user,
                AdminAuditLog.SCOPE_PUBLISH,
                "collect_and_refresh_public",
                target_key="public_site",
                summary="새 기사 수집과 공개 반영을 실행했습니다.",
                after_data={
                    "status": "completed",
                    "override_path": override_path,
                    "outputs": outputs,
                    "sync_runtime_articles": "failed" if sync_failed else "completed",
                    "sync_error": sync_failed or "",
                },
            )
            messages.success(request, "새 기사 수집과 공개 반영을 실행했습니다.")
            for output in outputs:
                messages.info(request, _command_brief(output))
            return redirect(redirect_to)

        if action == "refresh_public":
            export_editorial_overrides()
            try:
                outputs = run_public_editorial_refresh()
            except subprocess.CalledProcessError as exc:
                create_admin_audit_log(
                    request.user,
                    AdminAuditLog.SCOPE_PUBLISH,
                    "refresh_public",
                    target_key="public_site",
                    summary="공개 반영 실행에 실패했습니다.",
                    after_data={
                        "command": exc.cmd,
                        "returncode": exc.returncode,
                        "stdout": (exc.output or "").strip(),
                        "stderr": (exc.stderr or "").strip(),
                    },
                )
                messages.error(request, "공개 반영 실행 중 오류가 발생했습니다.")
                if exc.stderr:
                    messages.error(request, exc.stderr.strip().splitlines()[0][:180])
                return redirect(redirect_to)

            create_admin_audit_log(
                request.user,
                AdminAuditLog.SCOPE_PUBLISH,
                "refresh_public",
                target_key="public_site",
                summary="공개 반영을 실행했습니다.",
                after_data={"outputs": outputs},
            )

            try:
                call_command("sync_runtime_articles")
            except Exception as exc:  # noqa: BLE001
                create_admin_audit_log(
                    request.user,
                    AdminAuditLog.SCOPE_PUBLISH,
                    "sync_runtime_articles_after_publish",
                    target_key="runtime_articles",
                    summary="공개 반영 후 운영 후보 동기화에 실패했습니다.",
                    after_data={"error": str(exc)},
                )
                messages.warning(request, "공개 반영은 완료됐지만 운영 후보 재동기화에는 실패했습니다.")
            else:
                messages.success(request, "공개 사이트 반영을 다시 실행했습니다.")

            for output in outputs:
                messages.info(request, _command_brief(output))
            return redirect(redirect_to)

        messages.error(request, "지원하지 않는 요청입니다.")
        return redirect(redirect_to)

    query = (request.GET.get("query") or "").strip()
    decision = (request.GET.get("decision") or "all").strip().lower()
    region = (request.GET.get("region") or "all").strip()

    articles = SyncedArticle.objects.all()
    if query:
        articles = articles.filter(
            Q(title__icontains=query)
            | Q(source_name__icontains=query)
            | Q(region__icontains=query)
            | Q(hub_owner_label__icontains=query)
            | Q(editorial_note__icontains=query)
        )
    if decision in {DECISION_DEFAULT, DECISION_FEATURE, DECISION_EXCLUDE}:
        articles = articles.filter(editorial_decision=decision)
    if region and region != "all":
        articles = articles.filter(region=region)

    articles = articles.annotate(
        editorial_priority=Case(
            When(editorial_decision=DECISION_FEATURE, then=Value(0)),
            When(editorial_decision=DECISION_EXCLUDE, then=Value(2)),
            default=Value(1),
            output_field=IntegerField(),
        )
    ).order_by("editorial_priority", "editorial_feature_rank", "-published_date", "-updated_at")

    paginator = Paginator(articles, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    auto_update_context = _auto_update_context_bundle()
    context = {
        "decision_choices": [
            (DECISION_DEFAULT, "기본"),
            (DECISION_FEATURE, "상단 노출"),
            (DECISION_EXCLUDE, "배제"),
        ],
        "page_obj": page_obj,
        "query": query,
        "decision": decision,
        "region": region,
        "region_options": list(
            SyncedArticle.objects.exclude(region="").order_by("region").values_list("region", flat=True).distinct()
        ),
        "featured_count": SyncedArticle.objects.filter(editorial_decision=DECISION_FEATURE).count(),
        "excluded_count": SyncedArticle.objects.filter(editorial_decision=DECISION_EXCLUDE).count(),
        "default_count": SyncedArticle.objects.filter(editorial_decision=DECISION_DEFAULT).count(),
        "synced_count": SyncedArticle.objects.count(),
        "override_path": str(editorial_overrides_path()),
        "ops_radar": _load_ops_radar_payload(),
    }
    context.update(auto_update_context)
    return render(request, "briefings/editorial_dashboard.html", context)


@login_required
def editorial_settings(request: HttpRequest) -> HttpResponse:
    if not user_can_manage_editorial(request.user):
        return _editorial_response_forbidden()

    current_settings = load_contact_settings()
    form_values = current_settings
    current_auto_update_settings = load_auto_update_settings()
    auto_update_form_values = current_auto_update_settings

    if request.method == "POST":
        action = (request.POST.get("action") or "save_contact_settings").strip()
        if action == "save_auto_update_settings":
            previous_auto_update_settings = load_auto_update_settings()
            auto_update_form_values = _auto_update_form_payload(request, previous_auto_update_settings)
            try:
                saved_auto_update_settings = save_auto_update_settings(auto_update_form_values)
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                create_admin_audit_log(
                    request.user,
                    AdminAuditLog.SCOPE_PUBLISH,
                    "update_auto_update_settings",
                    target_key="auto_update_settings",
                    summary="자동 반영 설정을 저장했습니다.",
                    before_data=previous_auto_update_settings,
                    after_data=saved_auto_update_settings,
                )
                messages.success(request, "자동 반영 설정을 저장했습니다. 실행 중인 자동 러너가 다음 주기부터 반영합니다.")
                return redirect(reverse("editorial_settings"))
        else:
            previous_settings = load_contact_settings()
            form_values = _contact_form_payload(request, previous_settings)
            try:
                saved_settings = save_contact_settings(form_values)
                refresh_result = run_contact_settings_refresh()
            except ValueError as exc:
                messages.error(request, str(exc))
            except subprocess.CalledProcessError as exc:
                write_json(CONTACT_SETTINGS_PATH, previous_settings)
                messages.error(request, "문의/연락처 설정은 저장하지 않았습니다. 공개 페이지 재생성에 실패했습니다.")
                if exc.stderr:
                    messages.error(request, exc.stderr.strip().splitlines()[0][:180])
                form_values = previous_settings
            else:
                _audit_contact_save(request, previous_settings, saved_settings, refresh_result)
                messages.success(request, "문의/연락처 설정을 저장하고 공개 페이지를 다시 생성했습니다.")
                messages.info(request, _command_brief(refresh_result))
                return redirect(reverse("editorial_settings"))

    auto_update_context = _auto_update_context_bundle(current_auto_update_settings)
    auto_update_context["auto_update_settings"] = auto_update_form_values
    context = {
        "contact_settings": form_values,
        "contact_settings_path": str(CONTACT_SETTINGS_PATH),
        "auto_update_settings_path": str(AUTO_UPDATE_SETTINGS_PATH),
    }
    context.update(auto_update_context)
    return render(request, "briefings/editorial_settings.html", context)


@login_required
def editorial_history(request: HttpRequest) -> HttpResponse:
    if not user_can_manage_editorial(request.user):
        return _editorial_response_forbidden()

    scope = (request.GET.get("scope") or "all").strip().lower()
    query = (request.GET.get("query") or "").strip()

    logs = AdminAuditLog.objects.select_related("actor")
    if scope in {choice[0] for choice in AdminAuditLog.SCOPE_CHOICES}:
        logs = logs.filter(scope=scope)
    if query:
        logs = logs.filter(
            Q(summary__icontains=query)
            | Q(action__icontains=query)
            | Q(target_key__icontains=query)
            | Q(actor__username__icontains=query)
        )

    paginator = Paginator(logs, 30)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "page_obj": page_obj,
        "scope": scope,
        "query": query,
        "scope_choices": [("all", "전체"), *AdminAuditLog.SCOPE_CHOICES],
    }
    return render(request, "briefings/editorial_history.html", context)


@login_required
def editorial_analytics(request: HttpRequest) -> HttpResponse:
    if not user_can_manage_editorial(request.user):
        return _editorial_response_forbidden()

    scope = (request.GET.get("scope") or "public").strip().lower()
    context = analytics_dashboard_context(scope)
    return render(request, "briefings/editorial_analytics.html", context)


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def analytics_collect(request: HttpRequest) -> HttpResponse:
    response_headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
        "Cache-Control": "no-store",
    }
    if request.method == "OPTIONS":
        response = HttpResponse(status=204)
        for key, value in response_headers.items():
            response[key] = value
        return response

    try:
        record_page_view(request)
    except ValueError as exc:
        response = JsonResponse({"ok": False, "error": str(exc)}, status=400)
    else:
        response = HttpResponse(status=204)

    for key, value in response_headers.items():
        response[key] = value
    return response

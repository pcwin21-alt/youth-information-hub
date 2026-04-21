from __future__ import annotations

import json
from datetime import datetime, time, timedelta
from urllib.parse import urlparse

from django.db.models import Count
from django.db.models.functions import TruncDate
from django.http import HttpRequest
from django.utils import timezone

from .models import PageViewEvent


VALID_SCOPES = {PageViewEvent.SCOPE_PUBLIC, PageViewEvent.SCOPE_INSTITUTION}


def _clean_string(value: object, *, max_length: int) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:max_length]


def _host_from_url(url: str) -> str:
    if not url:
        return ""
    try:
        return (urlparse(url).hostname or "")[:200]
    except ValueError:
        return ""


def parse_analytics_payload(request: HttpRequest) -> dict[str, str]:
    if len(request.body or b"") > 8_192:
        raise ValueError("payload_too_large")

    try:
        raw_payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid_json") from exc

    site_scope = _clean_string(raw_payload.get("site_scope"), max_length=20).lower()
    if site_scope not in VALID_SCOPES:
        site_scope = PageViewEvent.SCOPE_PUBLIC

    visitor_id = _clean_string(raw_payload.get("visitor_id"), max_length=80)
    if not visitor_id:
        raise ValueError("missing_visitor_id")

    page_path = _clean_string(raw_payload.get("page_path"), max_length=300)
    page_url = _clean_string(raw_payload.get("page_url"), max_length=1000)
    if not page_path and page_url:
        page_path = urlparse(page_url).path[:300]
    if not page_path:
        raise ValueError("missing_page_path")

    referrer_url = _clean_string(raw_payload.get("referrer"), max_length=1000)
    source_origin = _clean_string(raw_payload.get("source_origin"), max_length=200)

    return {
        "site_scope": site_scope,
        "visitor_id": visitor_id,
        "session_id": _clean_string(raw_payload.get("session_id"), max_length=80),
        "page_path": page_path,
        "page_url": page_url,
        "page_title": _clean_string(raw_payload.get("page_title"), max_length=200),
        "referrer_url": referrer_url,
        "referrer_host": _host_from_url(referrer_url),
        "source_origin": source_origin,
        "user_agent": _clean_string(request.headers.get("User-Agent", ""), max_length=300),
    }


def record_page_view(request: HttpRequest) -> PageViewEvent:
    payload = parse_analytics_payload(request)
    return PageViewEvent.objects.create(**payload)


def analytics_dashboard_context(scope: str = "public") -> dict:
    allowed_scopes = {"all", *VALID_SCOPES}
    selected_scope = scope if scope in allowed_scopes else "public"
    queryset = PageViewEvent.objects.all()
    if selected_scope in VALID_SCOPES:
        queryset = queryset.filter(site_scope=selected_scope)

    now = timezone.now()
    today = timezone.localdate()
    today_start = timezone.make_aware(datetime.combine(today, time.min))
    seven_days_ago = now - timedelta(days=7)

    today_events = queryset.filter(occurred_at__gte=today_start)
    recent_events = queryset.filter(occurred_at__gte=seven_days_ago)

    top_pages = list(
        recent_events.values("page_path", "page_title")
        .annotate(pageviews=Count("id"), visitors=Count("visitor_id", distinct=True))
        .order_by("-pageviews", "page_path")[:10]
    )
    top_referrers = list(
        recent_events.exclude(referrer_host="")
        .values("referrer_host")
        .annotate(pageviews=Count("id"), visitors=Count("visitor_id", distinct=True))
        .order_by("-pageviews", "referrer_host")[:10]
    )
    daily_breakdown = list(
        recent_events.annotate(day=TruncDate("occurred_at"))
        .values("day")
        .annotate(pageviews=Count("id"), visitors=Count("visitor_id", distinct=True))
        .order_by("day")
    )

    return {
        "scope": selected_scope,
        "scope_choices": [
            ("public", "공개 사이트"),
            ("institution", "기관용 포털"),
            ("all", "전체"),
        ],
        "today_pageviews": today_events.count(),
        "today_visitors": today_events.values("visitor_id").distinct().count(),
        "seven_day_pageviews": recent_events.count(),
        "seven_day_visitors": recent_events.values("visitor_id").distinct().count(),
        "direct_visits": recent_events.filter(referrer_host="").count(),
        "top_pages": top_pages,
        "top_referrers": top_referrers,
        "daily_breakdown": daily_breakdown,
        "recent_events": queryset.select_related()[:20],
    }

from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .curation import is_public_interest_article
from .io_utils import read_json


SEVERITY_ORDER = {"info": 0, "warning": 1, "critical": 2}
DEFAULT_THRESHOLDS: dict[str, int] = {
    "min_raw_articles": 50,
    "min_filtered_articles": 20,
    "min_classified_articles": 20,
    "min_summarized_articles": 1,
    "min_news_cards": 1,
    "min_government_related_news_cards": 1,
    "min_government_policy_resource_cards": 10,
    "min_news_card_candidate_ratio_pct": 50,
    "min_home_government_trends": 3,
    "max_status_age_hours": 36,
    "max_source_health_age_hours": 168,
    "min_local_regions_with_items": 2,
}
PIPELINE_FILES = {
    "raw": "step1_raw_articles.json",
    "filtered": "step2_filtered.json",
    "classified": "step3_classified.json",
    "selected": "step4_selected.json",
    "summarized": "step5_summarized.json",
}
CONTROL_FILES = ("pipeline_status.json", "article_date_audit.json", "ops_radar.json")
PUBLIC_HTML_FILES = ("index.html", "news.html", "policies.html", "hub.html", "tools.html", "contact.html")


def now_aware() -> datetime:
    return datetime.now(timezone.utc).astimezone()


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc).astimezone()
    return parsed.astimezone()


def age_hours(value: str | None, reference: datetime | None = None) -> float | None:
    parsed = parse_datetime(value)
    if parsed is None:
        return None
    ref = reference or now_aware()
    return max((ref - parsed).total_seconds() / 3600, 0.0)


def load_json_list(path: Path) -> list[dict[str, Any]]:
    payload = read_json(path, default=[])
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("items"), list):
        return [item for item in payload["items"] if isinstance(item, dict)]
    return []


ARTICLE_EXPOSURE_DATE_FIELDS = (
    "publisher_published_at",
    "published_date",
    "portal_published_at",
)


def has_article_exposure_date(article: dict[str, Any]) -> bool:
    return any(
        parse_datetime(str(article.get(field)))
        for field in ARTICLE_EXPOSURE_DATE_FIELDS
        if article.get(field)
    )


def is_public_candidate(article: dict[str, Any]) -> bool:
    editorial_decision = str(article.get("editorial_decision") or "").strip().lower()
    if editorial_decision == "exclude":
        return False
    if article.get("editorial_is_highlighted") or editorial_decision == "include":
        return True
    return is_public_interest_article(article)


NEWS_PAGE_ELECTION_KEYWORDS = (
    "\uc120\uac70",
    "\ud6c4\ubcf4",
    "\uc608\ube44\ud6c4\ubcf4",
    "\uc720\uc138",
    "\uacf5\ucc9c",
    "\uc9c0\uc9c0\uc790",
    "\ub2e8\uc77c\ud654",
    "\ucd9c\ub9c8",
    "\uacbd\uc120",
    "\uc815\ub2f9",
    "\uad6d\ubbfc\uc758\ud798",
    "\ub354\ubd88\uc5b4\ubbfc\uc8fc\ub2f9",
    "\ubbfc\uc8fc\ub2f9",
    "\uac1c\ud601\uc2e0\ub2f9",
    "\uc870\uad6d\ud601\uc2e0\ub2f9",
    "\uc9c4\ubcf4\ub2f9",
    "\uacf5\uc57d",
)


def news_page_candidate_text(article: dict[str, Any]) -> str:
    return " ".join(
        str(article.get(field) or "")
        for field in ("title", "summary", "lead_text", "section")
    )


def is_news_page_candidate(article: dict[str, Any]) -> bool:
    if article.get("is_official_source"):
        return False
    text = news_page_candidate_text(article)
    return not any(keyword in text for keyword in NEWS_PAGE_ELECTION_KEYWORDS)


def public_news_candidate_metrics(articles: list[dict[str, Any]]) -> dict[str, int]:
    public_news = [
        article
        for article in articles
        if is_public_candidate(article) and is_news_page_candidate(article)
    ]
    with_exposure_date = [article for article in public_news if has_article_exposure_date(article)]
    fallback_only = [
        article
        for article in with_exposure_date
        if not article.get("published_date")
        and (article.get("publisher_published_at") or article.get("portal_published_at"))
    ]
    return {
        "public_news_candidates": len(public_news),
        "public_news_display_date_candidates": len(with_exposure_date),
        "public_news_fallback_date_candidates": len(fallback_only),
    }


def count_news_cards(web_root: Path) -> int:
    news_path = web_root / "news.html"
    if not news_path.exists():
        return 0
    return news_path.read_text(encoding="utf-8-sig").count('data-article-card="true"')


def count_government_related_news_cards(web_root: Path) -> int:
    policies_path = web_root / "policies.html"
    if not policies_path.exists():
        return 0
    return policies_path.read_text(encoding="utf-8-sig").count('data-government-related-news-card="true"')


def count_government_policy_resource_cards(web_root: Path) -> int:
    policies_path = web_root / "policies.html"
    if not policies_path.exists():
        return 0
    return policies_path.read_text(encoding="utf-8-sig").count('data-government-policy-resource-card="true"')


def read_text_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8-sig")


def extract_home_glance_count(index_html: str, label: str) -> int | None:
    pattern = re.compile(
        rf'<span class="home-glance-label">{re.escape(label)}</span>\s*'
        r'<strong class="home-glance-value">(?P<count>[\d,]+)건</strong>'
    )
    match = pattern.search(index_html)
    if not match:
        return None
    return int(match.group("count").replace(",", ""))


def extract_home_government_trends_count(index_html: str) -> int | None:
    for label in ("정부 동향", "정부·지자체 동향"):
        count = extract_home_glance_count(index_html, label)
        if count is not None:
            return count
    return None


def normalize_source_kind(entry: dict[str, Any]) -> str:
    kind = str(entry.get("kind") or entry.get("source_kind") or "").strip()
    if kind:
        return kind
    name = str(entry.get("name") or "")
    if any(token in name for token in ("광역시", "특별시", "특별자치", "경기도", "충청", "전라", "경상", "제주")):
        return "local"
    if any(token in name for token in ("정책브리핑", "국무조정실", "금융위원회", "고용노동부", "교육부", "국토교통부", "보건복지부")):
        return "official"
    return "news"


def source_health_metrics(source_health: dict[str, Any]) -> dict[str, Any]:
    sources = [entry for entry in source_health.get("sources", []) if isinstance(entry, dict)]
    errors = [entry for entry in sources if str(entry.get("status") or "").startswith("error")]
    official_sources = [entry for entry in sources if normalize_source_kind(entry) == "official"]
    local_sources = [entry for entry in sources if normalize_source_kind(entry) == "local"]
    news_sources = [entry for entry in sources if normalize_source_kind(entry) == "news"]
    local_regions = {
        str(entry.get("region_name") or entry.get("region_id") or entry.get("name") or "").strip()
        for entry in local_sources
        if int(entry.get("filtered_items") or 0) > 0
    }
    return {
        "generated_at": source_health.get("generated_at"),
        "source_count": len(sources),
        "error_count": len(errors),
        "error_sources": [
            {
                "name": entry.get("name"),
                "kind": normalize_source_kind(entry),
                "status": entry.get("status"),
            }
            for entry in errors
        ],
        "official_filtered_items": sum(int(entry.get("filtered_items") or 0) for entry in official_sources),
        "official_total_items": sum(int(entry.get("total_items") or 0) for entry in official_sources),
        "news_filtered_items": sum(int(entry.get("filtered_items") or 0) for entry in news_sources),
        "local_filtered_items": sum(int(entry.get("filtered_items") or 0) for entry in local_sources),
        "local_regions_with_items": sorted(region for region in local_regions if region),
        "zero_total_sources": [
            {
                "name": entry.get("name"),
                "kind": normalize_source_kind(entry),
                "status": entry.get("status"),
            }
            for entry in sources
            if str(entry.get("status") or "") == "ok" and int(entry.get("total_items") or 0) == 0
        ],
    }


def build_metrics(
    *,
    pipeline_root: Path,
    web_root: Path,
    reference: datetime | None = None,
) -> dict[str, Any]:
    reference = reference or now_aware()
    artifact_counts: dict[str, int] = {}
    classified_articles: list[dict[str, Any]] = []
    missing_artifacts: list[str] = []
    for label, file_name in PIPELINE_FILES.items():
        path = pipeline_root / file_name
        if not path.exists():
            missing_artifacts.append(file_name)
            artifact_counts[label] = 0
        else:
            items = load_json_list(path)
            artifact_counts[label] = len(items)
            if label == "classified":
                classified_articles = items
    missing_control_files = [file_name for file_name in CONTROL_FILES if not (pipeline_root / file_name).exists()]

    status = read_json(pipeline_root / "pipeline_status.json", default={}) or {}
    date_audit = read_json(pipeline_root / "article_date_audit.json", default={}) or {}
    source_health = read_json(pipeline_root / "source_healthcheck.json", default={}) or {}
    index_html = read_text_if_exists(web_root / "index.html")
    missing_html = [file_name for file_name in PUBLIC_HTML_FILES if not (web_root / file_name).exists()]

    return {
        "generated_at": reference.isoformat(),
        "artifact_counts": artifact_counts,
        "missing_artifacts": missing_artifacts,
        "missing_control_files": missing_control_files,
        "status": {
            "state": status.get("state"),
            "error": status.get("error"),
            "finished_at": status.get("finished_at"),
            "finished_age_hours": age_hours(status.get("finished_at"), reference),
            "current_step": status.get("current_step"),
        },
        "date_audit": {
            "error_count": int(date_audit.get("error_count") or 0),
            "warning_count": int(date_audit.get("warning_count") or 0),
        },
        "source_health": source_health_metrics(source_health) if source_health else None,
        "source_health_age_hours": age_hours(source_health.get("generated_at"), reference) if source_health else None,
        "public_html": {
            "missing_files": missing_html,
            "news_cards": count_news_cards(web_root),
            "government_related_news_cards": count_government_related_news_cards(web_root),
            "government_policy_resource_cards": count_government_policy_resource_cards(web_root),
            **public_news_candidate_metrics(classified_articles),
            "home_government_trends": extract_home_government_trends_count(index_html),
            "home_latest_news": extract_home_glance_count(index_html, "가장 최근 뉴스"),
            "brand_ok": "청년정책 모아봄" in index_html,
        },
    }


def finding(
    severity: str,
    component: str,
    code: str,
    message: str,
    action: str,
) -> dict[str, str]:
    return {
        "severity": severity,
        "component": component,
        "code": code,
        "message": message,
        "action": action,
    }


def is_pipeline_feedback_step_in_progress(status: dict[str, Any]) -> bool:
    return (
        status.get("state") == "running"
        and status.get("current_step") == "pipeline_feedback"
        and not status.get("error")
    )


def build_findings(metrics: dict[str, Any], thresholds: dict[str, int] | None = None) -> list[dict[str, str]]:
    thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    findings: list[dict[str, str]] = []
    counts = metrics.get("artifact_counts", {})

    for file_name in metrics.get("missing_artifacts", []):
        findings.append(
            finding(
                "critical",
                "artifacts",
                "missing_artifact",
                f"필수 파이프라인 산출물이 없습니다: {file_name}",
                "전체 배치 `python public-site/scripts/cron_runner.py --skip-outbound-notifications`를 재실행합니다.",
            )
        )
    for file_name in metrics.get("missing_control_files", []):
        findings.append(
            finding(
                "critical",
                "artifacts",
                "missing_control_file",
                f"필수 운영 제어 파일이 없습니다: {file_name}",
                "전체 배치를 재실행하고 해당 step이 status/artifact를 기록하는지 확인합니다.",
            )
        )

    if counts.get("raw", 0) < thresholds["min_raw_articles"]:
        findings.append(
            finding(
                "critical",
                "collect-news",
                "low_raw_article_count",
                f"수집 원본이 {counts.get('raw', 0)}건으로 기준 {thresholds['min_raw_articles']}건보다 적습니다.",
                "`source_healthcheck.py`를 실행하고 실패/0건 소스를 `source_config.yaml`과 parser 기준으로 점검합니다.",
            )
        )
    if counts.get("filtered", 0) < thresholds["min_filtered_articles"]:
        findings.append(
            finding(
                "critical",
                "dedup-filter",
                "low_filtered_article_count",
                f"중복 제거 후 생존 기사가 {counts.get('filtered', 0)}건입니다.",
                "`dedup_filter.py` 결과와 `drop_reason`, include/exclude keyword를 확인합니다.",
            )
        )
    if counts.get("classified", 0) < thresholds["min_classified_articles"]:
        findings.append(
            finding(
                "critical",
                "content-curator",
                "low_classified_article_count",
                f"분류 기사 수가 {counts.get('classified', 0)}건입니다.",
                "`run_curator.py` 로그와 `article_funnel.json`을 확인합니다.",
            )
        )
    if counts.get("summarized", 0) < thresholds["min_summarized_articles"]:
        findings.append(
            finding(
                "critical",
                "publish",
                "low_summarized_article_count",
                f"최종 송출 기사 수가 {counts.get('summarized', 0)}건입니다.",
                "큐레이션 bucket 기준과 `step4_selected.json`/`step5_summarized.json`을 비교합니다.",
            )
        )

    status = metrics.get("status", {})
    if status.get("state") not in {None, "completed"} and not is_pipeline_feedback_step_in_progress(status):
        findings.append(
            finding(
                "critical",
                "scheduler",
                "pipeline_not_completed",
                f"최근 배치 상태가 completed가 아닙니다: {status.get('state')}",
                "`pipeline_status.json`의 실패 step을 보고 해당 스크립트를 단독 재실행합니다.",
            )
        )
    if status.get("error"):
        findings.append(
            finding(
                "critical",
                "scheduler",
                "pipeline_status_error",
                f"최근 배치 오류가 남아 있습니다: {status.get('error')}",
                "오류 메시지를 기준으로 실패 step을 재실행하고 원인 파일을 수정합니다.",
            )
        )
    if status.get("finished_age_hours") is not None and status["finished_age_hours"] > thresholds["max_status_age_hours"]:
        findings.append(
            finding(
                "critical",
                "scheduler",
                "stale_pipeline_status",
                f"최근 배치 완료 시각이 {status['finished_age_hours']:.1f}시간 전입니다.",
                "Windows Scheduler/systemd timer 상태를 확인하고 전체 배치를 수동 실행합니다.",
            )
        )

    date_audit = metrics.get("date_audit", {})
    if date_audit.get("error_count", 0) > 0:
        findings.append(
            finding(
                "critical",
                "date-audit",
                "date_audit_errors",
                f"날짜 감사 오류가 {date_audit.get('error_count')}건 있습니다.",
                "`article_date_audit.json`에서 error 항목의 URL/date source를 고칩니다.",
            )
        )
    elif date_audit.get("warning_count", 0) > 0:
        findings.append(
            finding(
                "info",
                "date-audit",
                "date_audit_warnings",
                f"날짜 감사 경고가 {date_audit.get('warning_count')}건 있습니다.",
                "경고는 송출 차단 조건은 아니지만 반복되는 source를 다음 parser 개선 후보로 올립니다.",
            )
        )

    source_health = metrics.get("source_health")
    if not source_health:
        findings.append(
            finding(
                "warning",
                "collect-news",
                "missing_source_healthcheck",
                "`source_healthcheck.json`이 없습니다.",
                "`python public-site/scripts/source_healthcheck.py`를 정기 점검 루틴에서 실행합니다.",
            )
        )
    else:
        if (
            metrics.get("source_health_age_hours") is not None
            and metrics["source_health_age_hours"] > thresholds["max_source_health_age_hours"]
        ):
            findings.append(
                finding(
                    "warning",
                    "collect-news",
                    "stale_source_healthcheck",
                    f"소스 헬스체크가 {metrics['source_health_age_hours']:.1f}시간 전 결과입니다.",
                    "`source_healthcheck.py`를 다시 실행해 현재 소스 상태를 갱신합니다.",
                )
            )
        if source_health.get("official_filtered_items", 0) <= 0:
            findings.append(
                finding(
                    "critical",
                    "collect-news",
                    "official_sources_empty",
                    "공식 소스에서 필터 통과한 항목이 없습니다.",
                    "중앙부처 parser와 공식 RSS/보도자료 URL을 우선 복구합니다.",
                )
            )
        error_sources = source_health.get("error_sources", [])
        high_risk_errors = [
            entry for entry in error_sources if entry.get("kind") in {"official", "news"}
        ]
        local_errors = [entry for entry in error_sources if entry.get("kind") == "local"]
        if high_risk_errors:
            findings.append(
                finding(
                    "critical",
                    "collect-news",
                    "primary_source_errors",
                    f"공식/뉴스 핵심 소스 오류가 {len(high_risk_errors)}건 있습니다.",
                    "오류 source의 parser, URL, 차단 여부를 먼저 확인합니다.",
                )
            )
        if local_errors:
            findings.append(
                finding(
                    "warning",
                    "collect-news",
                    "local_source_errors",
                    f"지자체 소스 오류가 {len(local_errors)}건 있습니다.",
                    "범용 검색 URL 의존을 줄이고 지자체별 보도자료/공고 board parser로 교체합니다.",
                )
            )
        local_regions = source_health.get("local_regions_with_items", [])
        if len(local_regions) < thresholds["min_local_regions_with_items"]:
            findings.append(
                finding(
                    "warning",
                    "collect-news",
                    "low_local_region_coverage",
                    f"지자체 공식 수집이 {len(local_regions)}개 지역에서만 잡혔습니다.",
                    "17개 광역 지자체 공식 보도자료/공고 엔드포인트를 지역별로 보강합니다.",
                )
            )
        official_zero_total_sources = [
            entry for entry in source_health.get("zero_total_sources", []) if entry.get("kind") == "official"
        ]
        if official_zero_total_sources:
            findings.append(
                finding(
                    "warning",
                    "collect-news",
                    "official_source_zero_total",
                    f"공식 소스 중 total_items=0인 항목이 {len(official_zero_total_sources)}건 있습니다.",
                    "해당 공식 source URL과 parser가 실제 목록 HTML/RSS를 아직 읽는지 확인합니다.",
                )
            )

    public_html = metrics.get("public_html", {})
    for file_name in public_html.get("missing_files", []):
        findings.append(
            finding(
                "critical",
                "publish",
                "missing_public_html",
                f"공개 HTML 파일이 없습니다: {file_name}",
                "`web_updater.py`를 재실행하고 Pages artifact 준비 전 파일 존재를 확인합니다.",
            )
        )
    if public_html.get("news_cards", 0) < thresholds["min_news_cards"]:
        findings.append(
            finding(
                "critical",
                "publish",
                "low_news_cards",
                f"뉴스 카드가 {public_html.get('news_cards', 0)}개입니다.",
                "`news.html` 생성 기준과 `step3_classified.json` 공개 후보를 비교합니다.",
            )
        )
    display_date_candidates = int(public_html.get("public_news_display_date_candidates") or 0)
    news_cards = int(public_html.get("news_cards") or 0)
    min_ratio_pct = thresholds["min_news_card_candidate_ratio_pct"]
    if (
        display_date_candidates >= thresholds["min_news_cards"]
        and news_cards * 100 < display_date_candidates * min_ratio_pct
    ):
        findings.append(
            finding(
                "warning",
                "publish",
                "news_cards_below_candidate_pool",
                (
                    f"News cards are {news_cards}, below {min_ratio_pct}% of public news "
                    f"candidates with display dates ({display_date_candidates})."
                ),
                (
                    "`web_updater.py` date fallback and news/election/policy exposure split "
                    "should be checked against `step3_classified.json`."
                ),
            )
        )
    if public_html.get("government_related_news_cards", 0) < thresholds["min_government_related_news_cards"]:
        findings.append(
            finding(
                "warning",
                "publish",
                "low_government_related_news_cards",
                f"정부 동향의 중앙정부 관련 뉴스 카드가 {public_html.get('government_related_news_cards', 0)}건입니다.",
                "정부 동향 페이지의 관련 뉴스 분리 조건과 중앙정부 키워드 후보를 `step3_classified.json` 기준으로 점검합니다.",
            )
        )
    if public_html.get("government_policy_resource_cards", 0) < thresholds["min_government_policy_resource_cards"]:
        findings.append(
            finding(
                "warning",
                "publish",
                "low_government_policy_resource_cards",
                f"정부 동향의 주요 정책 자료 카드가 {public_html.get('government_policy_resource_cards', 0)}건입니다.",
                "정부 동향 페이지의 주요 정책·시행계획 자료 구역과 중앙부처 watchlist 렌더링을 확인합니다.",
            )
        )
    home_government_trends = public_html.get("home_government_trends")
    if home_government_trends is None:
        findings.append(
            finding(
                "critical",
                "publish",
                "missing_home_government_metric",
                "홈 정부 동향 카운트를 찾지 못했습니다.",
                "`web_updater.py` 홈 섹션 마크업 또는 `home-glance` 렌더링을 확인합니다.",
            )
        )
    elif home_government_trends < thresholds["min_home_government_trends"]:
        findings.append(
            finding(
                "critical",
                "publish",
                "low_home_government_trends",
                f"홈 정부 동향 후보가 {home_government_trends}건입니다.",
                "정부 동향 페이지 후보, 공식 URL identity, 홈 노출 조건을 함께 점검합니다.",
            )
        )
    if not public_html.get("brand_ok"):
        findings.append(
            finding(
                "critical",
                "publish",
                "brand_missing",
                "홈 HTML에서 `청년정책 모아봄` 브랜드 문구를 찾지 못했습니다.",
                "브랜드/타이틀 렌더링 변경 후 `web_updater.py`를 재실행합니다.",
            )
        )

    if not findings:
        findings.append(
            finding(
                "info",
                "feedback",
                "no_findings",
                "현재 기준에서 차단할 문제를 찾지 못했습니다.",
                "정기 루틴을 유지하고 source health 추이를 봅니다.",
            )
        )
    return findings


def report_verdict(findings: list[dict[str, str]]) -> str:
    max_severity = max((SEVERITY_ORDER.get(item["severity"], 0) for item in findings), default=0)
    if max_severity >= SEVERITY_ORDER["critical"]:
        return "fail"
    if max_severity >= SEVERITY_ORDER["warning"]:
        return "warn"
    return "pass"


def build_feedback_report(
    metrics: dict[str, Any],
    thresholds: dict[str, int] | None = None,
) -> dict[str, Any]:
    findings = build_findings(metrics, thresholds)
    return {
        "generated_at": metrics.get("generated_at") or now_aware().isoformat(),
        "verdict": report_verdict(findings),
        "thresholds": {**DEFAULT_THRESHOLDS, **(thresholds or {})},
        "metrics": metrics,
        "findings": findings,
        "next_actions": list(dict.fromkeys(item["action"] for item in findings if item["severity"] != "info")),
    }


def should_fail(report: dict[str, Any], fail_on: str) -> bool:
    if fail_on == "never":
        return False
    minimum = SEVERITY_ORDER.get(fail_on, SEVERITY_ORDER["critical"])
    return any(SEVERITY_ORDER.get(item.get("severity", "info"), 0) >= minimum for item in report.get("findings", []))


def render_markdown_report(report: dict[str, Any]) -> str:
    metrics = report.get("metrics", {})
    counts = metrics.get("artifact_counts", {})
    public_html = metrics.get("public_html", {})
    source_health = metrics.get("source_health") or {}
    findings = report.get("findings", [])

    lines = [
        "# Pipeline Feedback Report",
        "",
        f"- generated_at: `{report.get('generated_at')}`",
        f"- verdict: `{report.get('verdict')}`",
        "",
        "## Key Metrics",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| raw articles | {counts.get('raw', 0)} |",
        f"| filtered articles | {counts.get('filtered', 0)} |",
        f"| classified articles | {counts.get('classified', 0)} |",
        f"| selected articles | {counts.get('selected', 0)} |",
        f"| summarized articles | {counts.get('summarized', 0)} |",
        f"| news cards | {public_html.get('news_cards', 0)} |",
        f"| government related news cards | {public_html.get('government_related_news_cards', 0)} |",
        f"| government policy resource cards | {public_html.get('government_policy_resource_cards', 0)} |",
        f"| public news candidates | {public_html.get('public_news_candidates', 0)} |",
        (
            "| public news candidates with display date | "
            f"{public_html.get('public_news_display_date_candidates', 0)} |"
        ),
        f"| public news fallback-date candidates | {public_html.get('public_news_fallback_date_candidates', 0)} |",
        f"| home government trends | {public_html.get('home_government_trends')} |",
        f"| source errors | {source_health.get('error_count', 'n/a')} |",
        f"| official filtered source items | {source_health.get('official_filtered_items', 'n/a')} |",
        f"| local filtered source items | {source_health.get('local_filtered_items', 'n/a')} |",
        "",
        "## Findings",
        "",
    ]
    for item in findings:
        lines.extend(
            [
                f"### {item['severity'].upper()} / {item['component']} / {item['code']}",
                "",
                item["message"],
                "",
                f"Action: {item['action']}",
                "",
            ]
        )
    if report.get("next_actions"):
        lines.extend(["## Next Actions", ""])
        for action in report["next_actions"]:
            lines.append(f"- {action}")
        lines.append("")
    lines.extend(
        [
            "## Operating Rule",
            "",
            "이 리포트는 배치가 끝난 뒤 `collect-news -> dedup-filter -> curator -> publish` 흐름을 빠르게 되짚는 자동 피드백 기록이다.",
            "critical은 송출 신뢰를 해치는 문제이므로 배치를 실패 처리할 수 있고, warning은 다음 소스/파서 정비 backlog로 올린다.",
            "",
        ]
    )
    return "\n".join(lines)


def html_escape_summary(report: dict[str, Any]) -> str:
    findings = report.get("findings", [])
    summary = ", ".join(f"{item['severity']}:{item['code']}" for item in findings[:5])
    return html.escape(summary or "no findings")

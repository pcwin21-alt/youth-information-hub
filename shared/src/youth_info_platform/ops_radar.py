from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .article_metadata import article_identity_key, normalize_article_record, preferred_article_url
from .curation import freshness_bonus, selection_published_at
from .editorial import DECISION_EXCLUDE, normalize_editorial_decision


@dataclass(frozen=True)
class RadarLaneSpec:
    slug: str
    label: str
    description: str
    keyword_groups: tuple[tuple[str, ...], ...]
    blocked_keywords: tuple[str, ...] = ()
    weight: int = 4


OPS_RADAR_LANES: tuple[RadarLaneSpec, ...] = (
    RadarLaneSpec(
        slug="youth_center_ops",
        label="청년센터 운영",
        description="청년센터, 허브, 공간 운영 변화나 센터장 이슈를 우선 포착합니다.",
        keyword_groups=(
            (
                "청년센터",
                "청년허브",
                "청년공간",
                "청년지원센터",
                "청년일자리센터",
                "청년창업센터",
                "청년재단",
            ),
            (
                "운영",
                "센터장",
                "개소",
                "개관",
                "재개관",
                "휴관",
                "폐관",
                "이전",
                "확장",
                "위탁",
                "수탁",
                "예산",
                "프로그램",
                "입주",
                "모집",
                "설명회",
            ),
        ),
        weight=6,
    ),
    RadarLaneSpec(
        slug="institution_program",
        label="기관·사업 공고",
        description="실무자가 챙겨야 할 모집, 접수, 선정, 프로그램 공고형 기사를 찾습니다.",
        keyword_groups=(
            ("청년", "청년정책", "청년센터", "청년단체", "청년공간"),
            (
                "모집",
                "신청",
                "접수",
                "공고",
                "선정",
                "참여자",
                "참가자",
                "지원사업",
                "사업설명회",
                "설명회",
                "프로그램",
                "교육",
                "멘토링",
                "컨설팅",
                "오픈",
                "개소",
                "개관",
                "확대",
            ),
        ),
        blocked_keywords=("대학일자리플러스센터", "자기소개서", "채용 박람회", "취업박람회"),
        weight=5,
    ),
    RadarLaneSpec(
        slug="governance_personnel",
        label="거버넌스·인사",
        description="위원회, 정책네트워크, 참여기구, 임명·위촉 기사 등을 묶습니다.",
        keyword_groups=(
            (
                "청년정책네트워크",
                "청년정책조정위원회",
                "청년위원회",
                "청년위원",
                "청년협의체",
                "청년참여",
                "청년정책",
                "청년단체",
                "청년센터",
                "청년보좌역",
            ),
            (
                "회의",
                "간담회",
                "토론회",
                "포럼",
                "공청회",
                "위원회",
                "발족",
                "출범",
                "위촉",
                "임명",
                "자문",
                "정책제안",
                "정책협의",
                "네트워크",
            ),
        ),
        weight=5,
    ),
    RadarLaneSpec(
        slug="political_commitment",
        label="정치·공약",
        description="청년 공약, 후보, 비례대표, 선거 의제를 별도 레이더로 남깁니다.",
        keyword_groups=(
            ("청년", "청년정책", "청년센터", "청년단체"),
            (
                "공약",
                "후보",
                "예비후보",
                "비례대표",
                "선거",
                "지방선거",
                "총선",
                "대선",
                "공천",
                "출마",
                "정당",
            ),
        ),
        weight=5,
    ),
    RadarLaneSpec(
        slug="risk_alert",
        label="리스크·논란",
        description="갈등, 감사, 갑질, 예산 삭감, 폐지 같은 운영 리스크를 우선 경보합니다.",
        keyword_groups=(
            ("청년", "청년센터", "청년정책", "청년단체", "청년공간"),
            (
                "갑질",
                "논란",
                "감사",
                "수사",
                "고발",
                "징계",
                "민원",
                "반발",
                "갈등",
                "폐지",
                "폐쇄",
                "중단",
                "예산 삭감",
                "예산삭감",
                "부실",
                "특혜",
                "파행",
            ),
        ),
        weight=7,
    ),
)


def annotate_ops_radar(
    articles: list[dict[str, Any]],
    *,
    generated_at: str | None = None,
    max_items: int = 120,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    timestamp = generated_at or datetime.now(timezone.utc).astimezone().isoformat()
    annotated_articles: list[dict[str, Any]] = []
    radar_items: list[dict[str, Any]] = []
    lane_counts: Counter[str] = Counter()

    for raw_article in articles:
        article = normalize_article_record(raw_article)
        lane_matches = _match_lanes(article)
        overlooked = _is_overlooked(article)
        score = _radar_score(article, lane_matches, overlooked=overlooked)
        labels = [match["label"] for match in lane_matches]
        priority = _priority_label(score)

        article["ops_radar_score"] = score
        article["ops_radar_priority"] = priority
        article["ops_radar_overlooked"] = overlooked
        article["ops_radar_lanes"] = [match["lane"] for match in lane_matches]
        article["ops_radar_labels"] = labels
        article["ops_radar_matches"] = lane_matches
        article["ops_radar_note"] = _build_note(lane_matches)
        annotated_articles.append(article)

        if not lane_matches:
            continue

        for match in lane_matches:
            lane_counts[match["lane"]] += 1

        radar_items.append(
            {
                "article_key": article_identity_key(article),
                "title": article.get("title"),
                "preferred_url": preferred_article_url(article),
                "source": article.get("source"),
                "source_name": article.get("source_name"),
                "source_kind": article.get("source_kind"),
                "publisher_domain": article.get("publisher_domain"),
                "published_at": selection_published_at(article),
                "region": article.get("region"),
                "selection_bucket": article.get("selection_bucket"),
                "drop_reason": article.get("drop_reason"),
                "importance_score": article.get("importance_score"),
                "ops_radar_score": score,
                "ops_radar_priority": priority,
                "ops_radar_overlooked": overlooked,
                "ops_radar_labels": labels,
                "ops_radar_lanes": [match["lane"] for match in lane_matches],
                "ops_radar_matches": lane_matches,
                "ops_radar_note": article["ops_radar_note"],
            }
        )

    radar_items.sort(key=_radar_sort_key, reverse=True)
    trimmed_items = radar_items[:max_items]

    payload = {
        "generated_at": timestamp,
        "summary": {
            "total_matched": len(radar_items),
            "visible_items": len(trimmed_items),
            "overlooked_count": len([item for item in radar_items if item.get("ops_radar_overlooked")]),
            "selected_count": len([item for item in radar_items if not item.get("ops_radar_overlooked")]),
            "lane_counts": [
                {
                    "lane": spec.slug,
                    "label": spec.label,
                    "count": lane_counts.get(spec.slug, 0),
                }
                for spec in OPS_RADAR_LANES
                if lane_counts.get(spec.slug, 0)
            ],
            "top_overlooked_count": len(
                [item for item in trimmed_items if item.get("ops_radar_overlooked")][:8]
            ),
        },
        "items": trimmed_items,
    }
    return annotated_articles, payload


def _match_lanes(article: dict[str, Any]) -> list[dict[str, Any]]:
    if article.get("is_noise"):
        return []
    if normalize_editorial_decision(article.get("editorial_decision")) == DECISION_EXCLUDE:
        return []

    text = _article_text(article)
    if not text:
        return []

    matches: list[dict[str, Any]] = []
    for spec in OPS_RADAR_LANES:
        if spec.blocked_keywords and any(keyword in text for keyword in spec.blocked_keywords):
            continue

        matched_keywords: list[str] = []
        for group in spec.keyword_groups:
            group_hits = [keyword for keyword in group if keyword in text]
            if not group_hits:
                matched_keywords = []
                break
            matched_keywords.append(group_hits[0])

        if not matched_keywords:
            continue

        matches.append(
            {
                "lane": spec.slug,
                "label": spec.label,
                "description": spec.description,
                "matched_keywords": matched_keywords,
                "score": spec.weight + min(len(set(matched_keywords)), 2),
            }
        )

    return matches


def _article_text(article: dict[str, Any]) -> str:
    return " ".join(
        str(part).strip()
        for part in [
            article.get("title") or "",
            article.get("lead_text") or "",
            article.get("section") or "",
            article.get("source") or "",
            article.get("hub_owner_label") or "",
        ]
        if part
    )


def _is_overlooked(article: dict[str, Any]) -> bool:
    pipeline_flags = article.get("pipeline_flags", {}) or {}
    if pipeline_flags.get("selected"):
        return False
    return normalize_editorial_decision(article.get("editorial_decision")) != DECISION_EXCLUDE


def _radar_score(
    article: dict[str, Any],
    lane_matches: list[dict[str, Any]],
    *,
    overlooked: bool,
) -> int:
    if not lane_matches:
        return 0

    score = sum(int(match.get("score") or 0) for match in lane_matches)
    score += max(freshness_bonus(selection_published_at(article)), 0)

    if overlooked:
        score += 4
    if str(article.get("drop_reason") or "").startswith("selection_cutoff"):
        score += 3
    if article.get("source_kind") in {"official", "local"}:
        score += 2
    if article.get("governance_scope"):
        score += 2
    if article.get("issue_tags"):
        score += min(len(article.get("issue_tags") or []) * 2, 4)
    if article.get("region") not in {None, "", "전국"}:
        score += 1
    return score


def _priority_label(score: int) -> str:
    if score >= 18:
        return "critical"
    if score >= 13:
        return "high"
    if score >= 8:
        return "medium"
    return "low"


def _build_note(lane_matches: list[dict[str, Any]]) -> str:
    if not lane_matches:
        return ""
    parts = []
    for match in lane_matches:
        keywords = ", ".join(match.get("matched_keywords") or [])
        parts.append(f"{match['label']} ({keywords})")
    return " / ".join(parts[:3])


def _radar_sort_key(item: dict[str, Any]) -> tuple[Any, ...]:
    published_at = item.get("published_at")
    try:
        published_ts = datetime.fromisoformat(str(published_at).replace("Z", "+00:00")).timestamp()
    except ValueError:
        published_ts = 0.0

    return (
        bool(item.get("ops_radar_overlooked")),
        item.get("ops_radar_score", 0),
        published_ts,
        item.get("importance_score", 0) or 0,
    )


__all__ = ["OPS_RADAR_LANES", "annotate_ops_radar"]

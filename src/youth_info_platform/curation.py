from __future__ import annotations

import difflib
import re
from datetime import datetime
from urllib.parse import parse_qsl, urlsplit, urlunsplit

from .constants import (
    CATEGORIES,
    CENTRAL_GOVERNMENT_CONTEXT_KEYWORDS,
    CATEGORY_NOW,
    CATEGORY_OPINION,
    CATEGORY_POLICY,
    CATEGORY_REGION,
    GOVERNANCE_ACTIVITY_KEYWORDS,
    GOVERNMENT_GOVERNANCE_KEYWORDS,
    HUB_ROUTING_KEYWORDS,
    LOCAL_GOVERNMENT_CONTEXT_KEYWORDS,
    NOISE_KEYWORDS,
    NOW_KEYWORDS,
    OFFICIAL_KEYWORDS,
    OPINION_KEYWORDS,
    REGIONS,
    REGIONAL_GOVERNANCE_KEYWORDS,
    YOUTH_RELATED_KEYWORDS,
)


def normalize_url(url: str) -> str:
    parts = urlsplit(url)
    query = [(key, value) for key, value in parse_qsl(parts.query) if not key.lower().startswith("utm_")]
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc.lower(),
            parts.path.rstrip("/"),
            "&".join(f"{key}={value}" for key, value in query),
            "",
        )
    )


def deduplicate_and_filter(articles: list[dict]) -> list[dict]:
    deduped: list[dict] = []
    seen_urls: set[str] = set()
    groups: list[list[dict]] = []
    for article in articles:
        normalized = normalize_url(article["url"])
        if normalized in seen_urls:
            continue
        seen_urls.add(normalized)

        article = dict(article)
        article["normalized_url"] = normalized
        if not _is_candidate(article):
            continue

        placed = False
        for group in groups:
            if _is_similar(group[0]["title"], article["title"]):
                group.append(article)
                placed = True
                break
        if not placed:
            groups.append([article])

    for index, group in enumerate(groups, start=1):
        representative = choose_representative(group)
        representative["related_article_count"] = len(group)
        representative["related_sources"] = [article["source"] for article in group]
        for article in group:
            article["dedup_group_id"] = f"group-{index}"
            article["candidate_role"] = "representative" if article["url"] == representative["url"] else "related"
        deduped.append(representative)
    return deduped


def choose_representative(group: list[dict]) -> dict:
    def sort_key(article: dict) -> tuple[int, int, str]:
        if article.get("source_kind") == "official":
            return (0, 0, article["title"])
        if article.get("source") in {"연합뉴스", "YTN"}:
            return (1, 0, article["title"])
        if article.get("source_kind") == "local":
            return (2, 0, article["title"])
        return (3, 0, article["title"])

    return dict(sorted(group, key=sort_key)[0])


def classify_articles(articles: list[dict]) -> list[dict]:
    classified: list[dict] = []
    for article in articles:
        text = f'{article.get("title", "")} {article.get("lead_text", "")}'
        categories: list[str] = []
        hub_topics = extract_hub_topics(text)
        governance_scope = extract_governance_scope(article, text)
        governance_activity_types = extract_governance_activity_types(text)
        has_policy_signal = article.get("source_kind") == "official" or any(
            keyword in text for keyword in OFFICIAL_KEYWORDS
        )
        is_official = article.get("source_kind") == "official"

        if has_policy_signal:
            categories.append(CATEGORY_POLICY)
        if any(keyword in text for keyword in NOW_KEYWORDS):
            categories.append(CATEGORY_NOW)
        if any(keyword in text for keyword in OPINION_KEYWORDS):
            categories.append(CATEGORY_OPINION)

        region = extract_region(text)
        if region != "전국":
            categories.append(CATEGORY_REGION)
        if not categories:
            categories.append(CATEGORY_NOW)

        categories = [category for category in CATEGORIES if category in categories]
        is_noise = False if is_official else detect_noise(text)

        classified.append(
            {
                **article,
                "categories": categories,
                "region": region,
                "is_noise": is_noise,
                "is_official_source": is_official,
                "is_hub_candidate": bool(hub_topics),
                "hub_topics": hub_topics,
                "governance_scope": governance_scope,
                "governance_activity_types": governance_activity_types,
                "is_government_governance": governance_scope == "정부",
                "is_regional_governance": governance_scope == "지역",
                "classification_reason": build_classification_reason(
                    categories,
                    region,
                    is_official,
                    is_noise,
                    hub_topics,
                    governance_scope,
                    governance_activity_types,
                ),
            }
        )
    return classified


def select_articles(articles: list[dict], limit: int = 10) -> list[dict]:
    scored = []
    for article in articles:
        if article.get("is_noise"):
            continue
        score = score_article(article)
        scored.append(
            {
                **article,
                "importance_score": score,
                "selection_reason": build_selection_reason(article, score),
                "is_representative": True,
                "related_article_count": article.get("related_article_count", 1),
            }
        )
    scored.sort(key=lambda item: (item["importance_score"], _published_timestamp(item.get("published_date"))), reverse=True)
    return scored[:limit]


def summarize_articles(articles: list[dict]) -> list[dict]:
    summarized = []
    for article in articles:
        summary = build_summary(article)
        badges = []
        if article.get("is_official_source"):
            badges.append("정부 원문 우선")
        if article.get("governance_scope") == "정부":
            badges.append("정부 거버넌스")
        if article.get("governance_scope") == "지역":
            badges.append("지역 거버넌스")
        if article.get("related_article_count", 1) > 1:
            badges.append(f'유사 보도 {article["related_article_count"]}건 통합')
        if CATEGORY_NOW in article.get("categories", []):
            badges.append("청년 현실·통계")
        if article.get("is_hub_candidate"):
            badges.append("활동가 허브")
        summarized.append({**article, "summary": summary, "display_badges": badges[:2]})
    return summarized


def extract_region(text: str) -> str:
    for region in REGIONS:
        if region in text:
            return region
    return "전국"


def detect_noise(text: str) -> bool:
    if any(keyword in text for keyword in NOISE_KEYWORDS):
        return True
    return not any(keyword in text for keyword in YOUTH_RELATED_KEYWORDS)


def extract_hub_topics(text: str) -> list[str]:
    return [keyword for keyword in HUB_ROUTING_KEYWORDS if keyword in text]


def extract_governance_activity_types(text: str) -> list[str]:
    activity_types: list[str] = []
    for label, keywords in GOVERNANCE_ACTIVITY_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            activity_types.append(label)
    return activity_types


def extract_government_governance_topics(text: str) -> list[str]:
    return [keyword for keyword in GOVERNMENT_GOVERNANCE_KEYWORDS if keyword in text]


def extract_regional_governance_topics(text: str) -> list[str]:
    return [keyword for keyword in REGIONAL_GOVERNANCE_KEYWORDS if keyword in text]


def has_central_government_context(article: dict, text: str) -> bool:
    source_text = f'{article.get("source", "")} {text}'
    return any(keyword in source_text for keyword in CENTRAL_GOVERNMENT_CONTEXT_KEYWORDS)


def has_local_government_context(article: dict, text: str) -> bool:
    source_text = f'{article.get("source", "")} {text}'
    if any(keyword in source_text for keyword in LOCAL_GOVERNMENT_CONTEXT_KEYWORDS):
        return True
    if article.get("source_kind") == "local":
        return True
    return extract_region(text) != "전국"


def extract_governance_scope(article: dict, text: str) -> str | None:
    activity_types = extract_governance_activity_types(text)
    if not activity_types:
        return None

    if not any(keyword in text for keyword in YOUTH_RELATED_KEYWORDS):
        return None

    if has_central_government_context(article, text) and (
        extract_government_governance_topics(text) or article.get("source_kind") == "official"
    ):
        return "정부"

    if extract_regional_governance_topics(text) and has_local_government_context(article, text):
        return "지역"

    return None


def build_summary(article: dict) -> str:
    lead = " ".join((article.get("lead_text") or "").split())
    first_line = f'[{article["categories"][0]}] {article["title"]}'
    second_line = lead[:120] if lead else "청년 관련 핵심 내용을 본문에서 확인할 수 있습니다."
    third_line = f'지역 {article["region"]} / 출처 {article["source"]}'
    return "\n".join([first_line, second_line, third_line])


def build_classification_reason(
    categories: list[str],
    region: str,
    is_official: bool,
    is_noise: bool,
    hub_topics: list[str] | None = None,
    governance_scope: str | None = None,
    governance_activity_types: list[str] | None = None,
) -> str:
    if is_noise:
        return "청년 관련성이 낮거나 노이즈 키워드가 감지되었습니다."

    chunks = [", ".join(categories)]
    if is_official:
        chunks.append("공식 발표")
    if hub_topics:
        chunks.append(f'허브={", ".join(hub_topics)}')
    if governance_scope:
        chunks.append(f"거버넌스={governance_scope}")
    if governance_activity_types:
        chunks.append(f'활동={", ".join(governance_activity_types)}')
    chunks.append(f"지역={region}")
    return " / ".join(chunks)


def build_selection_reason(article: dict, score: int) -> str:
    if article.get("is_official_source"):
        return f"공식 정책 발표로 우선 노출 (score={score})"
    if article.get("source_kind") == "news":
        return f"최신 청년 뉴스로 우선 노출 (score={score})"
    if CATEGORY_NOW in article.get("categories", []):
        return f"청년 현실·통계 설명력이 높음 (score={score})"
    if CATEGORY_REGION in article.get("categories", []):
        return f"지역 청년 이슈로서 고유성이 있음 (score={score})"
    return f"청년 관련성과 시의성을 고려한 선별 (score={score})"


def score_article(article: dict) -> int:
    score = 0
    categories = set(article.get("categories", []))

    if CATEGORY_NOW in categories:
        score += 5
    if CATEGORY_POLICY in categories:
        score += 4
    if CATEGORY_REGION in categories:
        score += 3
    if CATEGORY_OPINION in categories:
        score += 1
    if article.get("is_official_source"):
        score += 2
    if article.get("source_kind") == "news":
        score += 2
    if article.get("region") != "전국":
        score += 1

    score += freshness_bonus(article.get("published_date"))
    return score


def freshness_bonus(value: str | None) -> int:
    if not value:
        return 0

    try:
        published = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return 0

    delta = datetime.now(published.tzinfo) - published
    if delta.total_seconds() < 0:
        return 0
    if delta.days < 1:
        return 6
    if delta.days < 3:
        return 4
    if delta.days < 7:
        return 2
    if delta.days < 30:
        return 1
    if delta.days >= 180:
        return -6
    if delta.days >= 90:
        return -4
    if delta.days >= 30:
        return -3
    return 0


def _published_timestamp(value: str | None) -> float:
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _is_candidate(article: dict) -> bool:
    text = f'{article.get("title", "")} {article.get("lead_text", "")}'
    if article.get("source_kind") == "official":
        return True
    return any(keyword in text for keyword in YOUTH_RELATED_KEYWORDS)


def _is_similar(left: str, right: str) -> bool:
    normalized_left = re.sub(r"\s+", " ", left).strip().lower()
    normalized_right = re.sub(r"\s+", " ", right).strip().lower()
    return difflib.SequenceMatcher(a=normalized_left, b=normalized_right).ratio() >= 0.82

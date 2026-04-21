from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from .article_metadata import (
    article_identity_key,
    detect_article_type,
    extract_issue_tags,
    extract_location_tags,
    infer_region,
    is_google_news_url,
    normalize_article_title,
    normalize_article_record,
    normalize_tracking_url,
    title_similarity,
)
from .constants import (
    CATEGORIES,
    CENTRAL_GOVERNMENT_CONTEXT_KEYWORDS,
    CENTRAL_GOVERNMENT_OWNER_PATTERNS,
    CATEGORY_NOW,
    CATEGORY_OPINION,
    CATEGORY_POLICY,
    CATEGORY_REGION,
    GOVERNANCE_ACTIVITY_KEYWORDS,
    GOVERNMENT_GOVERNANCE_KEYWORDS,
    HUB_EXCLUDE_KEYWORDS,
    HUB_ROUTING_KEYWORDS,
    LOCAL_GOVERNMENT_CONTEXT_KEYWORDS,
    NOISE_KEYWORDS,
    NOW_KEYWORDS,
    OFFICIAL_KEYWORDS,
    OPINION_KEYWORDS,
    PUBLIC_GOVERNANCE_KEYWORDS,
    PUBLIC_INSTITUTION_CONTEXT_KEYWORDS,
    REGIONS,
    REGIONAL_GOVERNANCE_KEYWORDS,
    YOUTH_RELATED_KEYWORDS,
)
from .editorial import (
    DECISION_EXCLUDE,
    DECISION_FEATURE,
    normalize_editorial_decision,
    normalize_feature_rank,
)


NATIONWIDE_REGION = "전국"
ISSUE_TAG_SCORES: dict[str, int] = {
    "청년센터 운영": 3,
    "노동권": 3,
    "고립·은둔": 2,
    "주거": 2,
    "부채": 2,
    "고용": 2,
}
SELECTION_BUCKET_SPECS: list[tuple[str, int]] = [
    ("official_policy", 3),
    ("youth_issue", 3),
    ("opinion", 1),
    ("regional_issue", 2),
    ("governance", 1),
]
BUCKET_LABELS = {
    "official_policy": "공식·정책",
    "youth_issue": "청년 현안",
    "opinion": "의견·칼럼",
    "regional_issue": "지역 이슈",
    "governance": "거버넌스",
}


def normalize_url(url: str) -> str:
    return normalize_tracking_url(url)


def deduplicate_and_filter(articles: list[dict]) -> list[dict]:
    groups: list[list[dict[str, Any]]] = []
    seen_keys: set[str] = set()

    for raw_article in articles:
        article = normalize_article_record(raw_article)
        article["normalized_url"] = normalize_url(article.get("url", ""))
        if not _is_candidate(article):
            continue

        identity = article_identity_key(article)
        if identity in seen_keys:
            continue
        seen_keys.add(identity)

        for group in groups:
            if any(_is_same_story(existing, article) for existing in group):
                group.append(article)
                break
        else:
            groups.append([article])

    deduped: list[dict[str, Any]] = []
    for index, group in enumerate(groups, start=1):
        representative = choose_representative(group)
        representative["dedup_group_id"] = f"group-{index}"
        representative["related_article_count"] = len(group)
        representative["related_sources"] = list(
            dict.fromkeys(article.get("source", "") for article in group if article.get("source"))
        )
        representative["discovered_from"] = list(
            dict.fromkeys(
                origin
                for article in group
                for origin in (article.get("discovered_from") or [])
                if origin
            )
        )
        representative["portal_urls"] = list(
            dict.fromkeys(url for article in group for url in (article.get("portal_urls") or []) if url)
        )
        representative["pipeline_flags"] = {
            **representative.get("pipeline_flags", {}),
            "collected": True,
            "deduped": True,
            "classified": False,
            "selected": False,
            "published": False,
        }
        representative["candidate_role"] = "representative"
        deduped.append(representative)

    return deduped


def choose_representative(group: list[dict]) -> dict:
    return dict(sorted(group, key=_representative_sort_key)[0])


def editorial_feature_rank(article: dict[str, Any]) -> int | None:
    return normalize_feature_rank(article.get("editorial_feature_rank"))


def is_editorially_excluded(article: dict[str, Any]) -> bool:
    return normalize_editorial_decision(article.get("editorial_decision")) == DECISION_EXCLUDE


def is_editorially_featured(article: dict[str, Any]) -> bool:
    return normalize_editorial_decision(article.get("editorial_decision")) == DECISION_FEATURE


def classify_articles(articles: list[dict]) -> list[dict]:
    classified: list[dict[str, Any]] = []
    for raw_article in articles:
        article = normalize_article_record(raw_article)
        text = _article_text(article)
        issue_tags = list(dict.fromkeys((article.get("issue_tags") or []) + extract_issue_tags(text)))
        location_tags = list(dict.fromkeys((article.get("location_tags") or []) + extract_location_tags(text)))
        region = article.get("region") or infer_region(text, location_tags)
        if not region:
            region = NATIONWIDE_REGION

        article_type = article.get("article_type") or detect_article_type(
            article.get("title", ""),
            article.get("section", "") or "",
            article.get("body_text", "") or "",
        )
        governance_activity_types = extract_governance_activity_types(text)
        governance_scope = extract_governance_scope(article, text, governance_activity_types)
        hub_topics = extract_hub_topics(text, governance_scope)
        hub_owner_label = extract_hub_owner_label(article, text, governance_scope, region)
        hub_cluster_key = build_hub_cluster_key(
            article,
            governance_scope=governance_scope,
            hub_owner_label=hub_owner_label,
            region=region,
            hub_topics=hub_topics,
            governance_activity_types=governance_activity_types,
        )
        is_official = article.get("source_kind") == "official" or article_type == "official"
        has_policy_signal = is_official or any(keyword in text for keyword in OFFICIAL_KEYWORDS)

        categories: list[str] = []
        if has_policy_signal:
            categories.append(CATEGORY_POLICY)
        if issue_tags or any(keyword in text for keyword in NOW_KEYWORDS):
            categories.append(CATEGORY_NOW)
        if article_type == "opinion" or any(keyword in text for keyword in OPINION_KEYWORDS):
            categories.append(CATEGORY_OPINION)
        if region != NATIONWIDE_REGION:
            categories.append(CATEGORY_REGION)
        if not categories:
            categories.append(CATEGORY_NOW)

        ordered_categories = [category for category in CATEGORIES if category in categories]
        is_noise = False if is_official else detect_noise(text)
        pipeline_flags = {
            **article.get("pipeline_flags", {}),
            "collected": True,
            "deduped": True,
            "classified": True,
            "selected": False,
            "published": False,
        }

        classified.append(
            {
                **article,
                "categories": ordered_categories,
                "region": region,
                "issue_tags": issue_tags,
                "location_tags": location_tags,
                "article_type": article_type,
                "is_noise": is_noise,
                "is_official_source": is_official,
                "is_hub_candidate": bool(governance_scope and hub_topics),
                "hub_topics": hub_topics,
                "governance_scope": governance_scope,
                "governance_activity_types": governance_activity_types,
                "hub_owner_label": hub_owner_label,
                "hub_cluster_key": hub_cluster_key,
                "is_government_governance": governance_scope == "정부",
                "is_regional_governance": governance_scope == "지자체",
                "is_public_governance": governance_scope == "공공기관",
                "classification_reason": build_classification_reason(
                    ordered_categories,
                    region,
                    is_official,
                    is_noise,
                    issue_tags=issue_tags,
                    hub_topics=hub_topics,
                    governance_scope=governance_scope,
                    governance_activity_types=governance_activity_types,
                    article_type=article_type,
                ),
                "editorial_decision": normalize_editorial_decision(article.get("editorial_decision")),
                "editorial_feature_rank": editorial_feature_rank(article),
                "editorial_note": (article.get("editorial_note") or "").strip(),
                "editorial_updated_at": article.get("editorial_updated_at"),
                "editorial_updated_by": article.get("editorial_updated_by"),
                "pipeline_flags": pipeline_flags,
                "drop_reason": None,
            }
        )
    return classified


def select_articles(articles: list[dict], limit: int = 10) -> tuple[list[dict], list[dict]]:
    prepared: list[dict[str, Any]] = []
    eligible: list[dict[str, Any]] = []

    for raw_article in articles:
        article = normalize_article_record(raw_article)
        article["categories"] = list(article.get("categories") or [])
        article["issue_tags"] = list(article.get("issue_tags") or [])
        article["location_tags"] = list(article.get("location_tags") or [])
        article["editorial_decision"] = normalize_editorial_decision(article.get("editorial_decision"))
        article["editorial_feature_rank"] = editorial_feature_rank(article)
        article["editorial_note"] = (article.get("editorial_note") or "").strip()
        article["pipeline_flags"] = {
            **article.get("pipeline_flags", {}),
            "collected": True,
            "deduped": True,
            "classified": True,
            "selected": False,
            "published": False,
        }
        article["importance_score"] = score_article(article)
        article["selection_bucket"] = determine_selection_bucket(article)
        article["selection_reason"] = build_selection_reason(article, article["importance_score"])
        article["is_representative"] = True
        article["related_article_count"] = article.get("related_article_count", 1)
        if article.get("is_noise"):
            article["drop_reason"] = "noise_filtered"
        elif is_editorially_excluded(article):
            article["drop_reason"] = "editorial_excluded"
        else:
            article["drop_reason"] = None
        prepared.append(article)
        if not article.get("is_noise") and not is_editorially_excluded(article):
            eligible.append(article)

    ranked = sorted(
        eligible,
        key=lambda article: (
            article.get("importance_score", 0),
            _published_timestamp(selection_published_at(article)),
            article.get("related_article_count", 1),
        ),
        reverse=True,
    )

    selected_keys: set[str] = set()
    selected: list[dict[str, Any]] = []

    def take_candidates(candidates: list[dict[str, Any]], count: int) -> None:
        taken = 0
        for article in candidates:
            if taken >= count:
                break
            key = article_identity_key(article)
            if key in selected_keys:
                continue
            selected.append(article)
            selected_keys.add(key)
            taken += 1

    featured_candidates = sorted(
        [article for article in ranked if is_editorially_featured(article)],
        key=lambda article: (
            editorial_feature_rank(article) or 9999,
            -article.get("importance_score", 0),
            -_published_timestamp(selection_published_at(article)),
        ),
    )
    take_candidates(featured_candidates, limit)

    for bucket, minimum in SELECTION_BUCKET_SPECS:
        bucket_candidates = [
            article
            for article in ranked
            if article.get("selection_bucket") == bucket and not is_editorially_featured(article)
        ]
        take_candidates(bucket_candidates, minimum)

    if len(selected) < limit:
        remaining = [
            article
            for article in ranked
            if article_identity_key(article) not in selected_keys and not is_editorially_featured(article)
        ]
        take_candidates(remaining, limit - len(selected))

    if len(selected) > limit:
        selected = sort_selected_articles(selected)[:limit]
        selected_keys = {article_identity_key(article) for article in selected}

    for article in prepared:
        key = article_identity_key(article)
        if key in selected_keys:
            article["pipeline_flags"]["selected"] = True
            article["drop_reason"] = None
            if is_editorially_featured(article):
                rank = editorial_feature_rank(article) or 9999
                article["selection_reason"] = f"editorial_featured:rank={rank}"
        elif not article.get("drop_reason"):
            bucket = BUCKET_LABELS.get(article.get("selection_bucket", ""), article.get("selection_bucket", "기타"))
            article["drop_reason"] = f"selection_cutoff:{bucket}:score={article.get('importance_score', 0)}"

    selected_articles = sort_selected_articles(
        [article for article in prepared if article_identity_key(article) in selected_keys]
    )
    return selected_articles, prepared


def summarize_articles(articles: list[dict]) -> list[dict]:
    summarized: list[dict[str, Any]] = []
    for raw_article in articles:
        article = normalize_article_record(raw_article)
        article["editorial_decision"] = normalize_editorial_decision(article.get("editorial_decision"))
        article["editorial_feature_rank"] = editorial_feature_rank(article)
        badges: list[str] = []
        if is_editorially_featured(article):
            badges.append("상단 노출")
        if article.get("is_official_source"):
            badges.append("공식 발표")
        elif article.get("article_type") == "opinion":
            badges.append("의견·칼럼")

        if article.get("issue_tags"):
            badges.append(article["issue_tags"][0])

        if article.get("governance_scope") == "정부":
            badges.append("정부 거버넌스")
        elif article.get("governance_scope") == "지자체":
            badges.append("지역 거버넌스")
        elif article.get("governance_scope") == "공공기관":
            badges.append("공공기관 참여")

        if article.get("related_article_count", 1) > 1:
            badges.append(f'유사 보도 {article["related_article_count"]}건')

        article["pipeline_flags"] = {
            **article.get("pipeline_flags", {}),
            "collected": True,
            "deduped": True,
            "classified": True,
            "selected": True,
            "published": True,
        }
        article["summary"] = build_summary(article)
        article["display_badges"] = badges[:2]
        summarized.append(article)
    return summarized


def extract_region(text: str) -> str:
    for region in REGIONS:
        if region in text:
            return region
    return NATIONWIDE_REGION


def detect_noise(text: str) -> bool:
    if any(keyword in text for keyword in NOISE_KEYWORDS):
        return True
    return not any(keyword in text for keyword in YOUTH_RELATED_KEYWORDS)


def extract_hub_topics(text: str, governance_scope: str | None = None) -> list[str]:
    if governance_scope == "정부":
        keywords = GOVERNMENT_GOVERNANCE_KEYWORDS
    elif governance_scope == "지자체":
        keywords = REGIONAL_GOVERNANCE_KEYWORDS
    elif governance_scope == "공공기관":
        keywords = PUBLIC_GOVERNANCE_KEYWORDS
    else:
        keywords = HUB_ROUTING_KEYWORDS
    return [keyword for keyword in keywords if keyword in text]


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


def extract_public_governance_topics(text: str) -> list[str]:
    return [keyword for keyword in PUBLIC_GOVERNANCE_KEYWORDS if keyword in text]


def has_central_government_context(article: dict, text: str) -> bool:
    source_text = _hub_context_text(article, text)
    return any(keyword in source_text for keyword in CENTRAL_GOVERNMENT_CONTEXT_KEYWORDS)


def has_local_government_context(article: dict, text: str) -> bool:
    source_text = _hub_context_text(article, text)
    if any(keyword in source_text for keyword in LOCAL_GOVERNMENT_CONTEXT_KEYWORDS):
        return True
    if article.get("source_kind") == "local":
        return True
    if _extract_local_owner_label(source_text):
        return True
    return extract_region(text) != NATIONWIDE_REGION


def has_public_institution_context(article: dict, text: str) -> bool:
    source_text = _hub_context_text(article, text)
    if any(keyword in source_text for keyword in HUB_EXCLUDE_KEYWORDS):
        return False
    return bool(_extract_public_institution_owner_label(source_text)) or any(
        keyword in source_text for keyword in PUBLIC_INSTITUTION_CONTEXT_KEYWORDS
    )


def is_excluded_hub_record(article: dict, text: str, activity_types: list[str] | None = None) -> bool:
    source_text = _hub_context_text(article, text)
    if any(keyword in source_text for keyword in HUB_EXCLUDE_KEYWORDS):
        return True

    if "청년위원회" in text and not any(
        keyword in source_text
        for keyword in CENTRAL_GOVERNMENT_CONTEXT_KEYWORDS
        + LOCAL_GOVERNMENT_CONTEXT_KEYWORDS
        + PUBLIC_INSTITUTION_CONTEXT_KEYWORDS
    ):
        return True

    normalized_activity_types = activity_types or []
    if "협약" in normalized_activity_types and article.get("source_kind") == "news":
        if not (
            has_central_government_context(article, text)
            or has_local_government_context(article, text)
            or has_public_institution_context(article, text)
        ):
            return True

    return False


def extract_governance_scope(
    article: dict,
    text: str,
    activity_types: list[str] | None = None,
) -> str | None:
    activity_types = activity_types or extract_governance_activity_types(text)
    if not activity_types:
        return None

    if not any(keyword in text for keyword in YOUTH_RELATED_KEYWORDS):
        return None

    if is_excluded_hub_record(article, text, activity_types):
        return None

    if has_central_government_context(article, text) and extract_government_governance_topics(text):
        return "정부"

    if extract_regional_governance_topics(text) and has_local_government_context(article, text):
        return "지자체"

    if extract_public_governance_topics(text) and has_public_institution_context(article, text):
        return "공공기관"

    return None


def extract_hub_owner_label(article: dict, text: str, governance_scope: str | None, region: str) -> str | None:
    if not governance_scope:
        return None

    source_text = _hub_context_text(article, text)
    if governance_scope == "정부":
        for label, keywords in CENTRAL_GOVERNMENT_OWNER_PATTERNS:
            if any(keyword in source_text for keyword in keywords):
                return label
        source = str(article.get("source") or article.get("source_name") or "").replace("보도자료", "").strip()
        return source or "중앙정부"

    if governance_scope == "지자체":
        owner = _extract_local_owner_label(source_text)
        if owner:
            return owner
        if region and region != NATIONWIDE_REGION:
            return region
        return None

    if governance_scope == "공공기관":
        owner = _extract_public_institution_owner_label(source_text)
        if owner:
            return owner
        source = str(article.get("source") or article.get("source_name") or "").strip()
        return source or None

    return None


def build_hub_cluster_key(
    article: dict,
    *,
    governance_scope: str | None,
    hub_owner_label: str | None,
    region: str,
    hub_topics: list[str],
    governance_activity_types: list[str],
) -> str | None:
    if not governance_scope or not hub_topics:
        return None

    owner = hub_owner_label or (region if region != NATIONWIDE_REGION else "") or str(article.get("source") or "")
    primary_topic = hub_topics[0]
    primary_activity = governance_activity_types[0] if governance_activity_types else ""
    published_key = (selection_published_at(article) or "")[:10]
    return "|".join(
        part
        for part in [governance_scope, owner.strip(), region or "", primary_topic, primary_activity, published_key]
        if part
    )


def build_summary(article: dict) -> str:
    lead = " ".join((article.get("lead_text") or "").split())
    primary_category = (article.get("categories") or [CATEGORY_NOW])[0]
    first_line = f"[{primary_category}] {article.get('title', '제목 없음')}"
    second_line = lead[:120] if lead else "본문 보강이 필요한 기사입니다."
    third_line = f'지역 {article.get("region", NATIONWIDE_REGION)} / 출처 {article.get("source", "미상")}'
    return "\n".join([first_line, second_line, third_line])


def build_classification_reason(
    categories: list[str],
    region: str,
    is_official: bool,
    is_noise: bool,
    *,
    issue_tags: list[str] | None = None,
    hub_topics: list[str] | None = None,
    governance_scope: str | None = None,
    governance_activity_types: list[str] | None = None,
    article_type: str | None = None,
) -> str:
    if is_noise:
        return "청년 관련성이 약하거나 노이즈로 판정했습니다."

    chunks = [", ".join(categories)]
    if is_official:
        chunks.append("공식 발표")
    if article_type:
        chunks.append(f"유형={article_type}")
    if issue_tags:
        chunks.append(f"이슈={', '.join(issue_tags[:3])}")
    if hub_topics:
        chunks.append(f"허브={', '.join(hub_topics[:3])}")
    if governance_scope:
        chunks.append(f"거버넌스={governance_scope}")
    if governance_activity_types:
        chunks.append(f"활동={', '.join(governance_activity_types[:3])}")
    chunks.append(f"지역={region}")
    return " / ".join(chunks)


def build_selection_reason(article: dict, score: int) -> str:
    bucket = BUCKET_LABELS.get(determine_selection_bucket(article), "기타")
    issue_tags = article.get("issue_tags") or []
    issue_text = f" / 이슈={', '.join(issue_tags[:2])}" if issue_tags else ""
    return f"{bucket} 버킷 우선순위 반영{issue_text} (score={score})"


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
        score += 2
    if article.get("is_official_source"):
        score += 2
    if article.get("governance_scope"):
        score += 2
    if article.get("source_kind") == "news":
        score += 2
    if article.get("region") not in {None, "", NATIONWIDE_REGION}:
        score += 1
    if article.get("article_type") == "opinion":
        score += 1
    if article.get("body_text"):
        score += 1

    for tag in article.get("issue_tags") or []:
        score += ISSUE_TAG_SCORES.get(tag, 1)

    score += freshness_bonus(selection_published_at(article))
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


def selection_published_at(article: dict) -> str | None:
    return (
        article.get("publisher_published_at")
        or article.get("published_date")
        or article.get("portal_published_at")
        or None
    )


def sort_selected_articles(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        articles,
        key=lambda article: (
            0 if is_editorially_featured(article) else 1,
            editorial_feature_rank(article) or 9999,
            -article.get("importance_score", 0),
            -_published_timestamp(selection_published_at(article)),
            -(article.get("related_article_count", 1)),
        ),
    )


def determine_selection_bucket(article: dict) -> str:
    if article.get("is_official_source"):
        return "official_policy"
    if article.get("governance_scope") or article.get("is_hub_candidate"):
        return "governance"
    if article.get("article_type") == "opinion" or CATEGORY_OPINION in set(article.get("categories", [])):
        return "opinion"
    if article.get("region") not in {None, "", NATIONWIDE_REGION} and CATEGORY_REGION in set(article.get("categories", [])):
        return "regional_issue"
    return "youth_issue"


def _published_timestamp(value: str | None) -> float:
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _is_candidate(article: dict) -> bool:
    if article.get("source_kind") == "official":
        return True
    text = _article_text(article)
    if article.get("issue_tags"):
        return True
    return any(keyword in text for keyword in YOUTH_RELATED_KEYWORDS)


def _is_similar(left: str, right: str) -> bool:
    return title_similarity(left, right) >= 0.82


def _is_same_story(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if article_identity_key(left) == article_identity_key(right):
        return True

    left_domain = left.get("publisher_domain") or left.get("source")
    right_domain = right.get("publisher_domain") or right.get("source")
    if left_domain and right_domain and str(left_domain).lower() != str(right_domain).lower():
        return False

    if title_similarity(left.get("title"), right.get("title")) < 0.92:
        return False

    left_ts = _published_timestamp(selection_published_at(left))
    right_ts = _published_timestamp(selection_published_at(right))
    if left_ts and right_ts and abs(left_ts - right_ts) > 60 * 60 * 48:
        return False
    return True


def _article_text(article: dict[str, Any]) -> str:
    authors = " ".join(article.get("authors") or [])
    return " ".join(
        part
        for part in [
            article.get("title", "") or "",
            article.get("lead_text", "") or "",
            article.get("section", "") or "",
            article.get("body_text", "") or "",
            authors,
            article.get("source", "") or "",
            article.get("source_name", "") or "",
        ]
        if part
    )


def _hub_context_text(article: dict[str, Any], text: str) -> str:
    return " ".join(
        part
        for part in [
            str(article.get("source") or ""),
            str(article.get("source_name") or ""),
            str(article.get("section") or ""),
            text,
        ]
        if part
    )


def _extract_local_owner_label(text: str) -> str | None:
    match = re.search(
        r"(?:^|[\s'\"“”‘’(\[])"
        r"([가-힣]{1,12}(?:특별시|광역시|특별자치시|특별자치도|자치시|자치도|도|시|군|구))"
        r"(?:[\s,.'\"“”‘’)\]]|$)",
        text,
    )
    if match:
        candidate = match.group(1)
        if candidate not in {"주도"}:
            return candidate

    for pattern in [
        r"([가-힣]{1,12}(?:시|군|구))장",
        r"([가-힣]{1,12}도)지사",
    ]:
        extra_match = re.search(pattern, text)
        if not extra_match:
            continue
        candidate = extra_match.group(1)
        if candidate not in {"주도"}:
            return candidate
    return None


def _extract_public_institution_owner_label(text: str) -> str | None:
    matches = re.findall(
        r"([가-힣A-Za-z0-9· ]{2,40}?(?:공단|공사|진흥원|재단|청년센터|센터|청년허브|허브|청년일자리스테이션|일자리스테이션))",
        text,
    )
    for candidate in matches:
        cleaned = normalize_article_title(candidate)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,·")
        if not cleaned:
            continue
        if any(keyword in cleaned for keyword in HUB_EXCLUDE_KEYWORDS):
            continue
        return cleaned
    return None


def _representative_sort_key(article: dict[str, Any]) -> tuple[Any, ...]:
    source_kind = article.get("source_kind") or ""
    source_rank = {"official": 0, "local": 1, "news": 2}.get(source_kind, 3)
    has_publisher_url = 0 if article.get("publisher_url") else 1
    google_wrapper_penalty = 1 if is_google_news_url(article.get("url")) else 0
    enriched_penalty = 0 if article.get("body_text") else 1
    official_rank = 0 if article.get("source_kind") == "official" else 1
    timestamp = -_published_timestamp(selection_published_at(article))
    issue_score = -(len(article.get("issue_tags") or []))
    return (
        official_rank,
        has_publisher_url,
        google_wrapper_penalty,
        enriched_penalty,
        source_rank,
        issue_score,
        timestamp,
        article.get("title", ""),
    )

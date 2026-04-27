from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from .article_metadata import (
    article_identity_key,
    detect_article_type,
    extract_issue_tags,
    extract_location_tags,
    extract_youth_preview_text,
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
    POLITICAL_CAMPAIGN_KEYWORDS,
    POLITICAL_HUB_EXCLUDE_KEYWORDS,
    PUBLIC_GOVERNANCE_KEYWORDS,
    PUBLIC_INSTITUTION_CONTEXT_KEYWORDS,
    REGIONS,
    REGIONAL_GOVERNANCE_KEYWORDS,
    SUBSTANTIVE_PROMISE_KEYWORDS,
    YOUTH_ISSUE_CONTEXT_KEYWORDS,
    YOUTH_ISSUE_KEYWORDS,
    YOUTH_INSTITUTION_CONTEXT_KEYWORDS,
    YOUTH_RELATED_KEYWORDS,
    YOUTH_STRONG_CONTEXT_KEYWORDS,
    YOUTH_KEYWORDS,
    YOUTH_POLICY_CONTEXT_KEYWORDS,
)
from .editorial import (
    DECISION_EXCLUDE,
    DECISION_INCLUDE,
    apply_clean_signal,
    is_clean_article,
    normalize_editorial_decision,
    normalize_editorial_highlighted,
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
TOPIC_TAG_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("취업", ("취업", "채용", "일자리", "고용", "구직", "구직단념", "직무", "GSAT", "인턴")),
    ("주거", ("주거", "주택", "월세", "전세", "임대", "기숙사", "보증금", "청년월세", "청년전세")),
    ("노동", ("노동", "노동권", "근로", "임금", "직장", "계약", "부당해고", "괴롭힘", "노조")),
    ("금융", ("금융", "대출", "부채", "자산형성", "적금", "도약계좌", "학자금", "상환", "신용회복")),
    ("청년센터", ("청년센터", "청년공간", "청년허브", "청년일자리센터", "청년지원센터", "청년재단")),
    ("모집", ("모집", "신청", "접수", "선발", "공고", "참여자", "지원자", "대상자", "모집공고")),
    ("복지", ("복지", "돌봄", "자립", "상담", "마음건강", "고립", "은둔", "생활비", "지원금")),
    ("창업", ("창업", "예비창업", "초기창업", "스타트업", "벤처", "창업기업", "청년농업인")),
    ("지역정착", ("지역정착", "지역 정착", "관계인구", "생활인구", "인구소멸", "지역소멸", "소멸위기", "빈집", "지역활력", "지역재생", "청년마을", "꿈터")),
)
NON_POLITICAL_HUB_EXCLUDE_KEYWORDS = tuple(
    keyword for keyword in HUB_EXCLUDE_KEYWORDS if keyword not in POLITICAL_HUB_EXCLUDE_KEYWORDS
)
YOUTH_POLICY_OR_OPERATIONAL_CONTEXT_KEYWORDS = tuple(
    dict.fromkeys(
        YOUTH_POLICY_CONTEXT_KEYWORDS
        + YOUTH_INSTITUTION_CONTEXT_KEYWORDS
        + CENTRAL_GOVERNMENT_CONTEXT_KEYWORDS
        + LOCAL_GOVERNMENT_CONTEXT_KEYWORDS
        + PUBLIC_INSTITUTION_CONTEXT_KEYWORDS
    )
)
PUBLIC_HELPFUL_DIRECT_KEYWORDS = tuple(
    dict.fromkeys(
        YOUTH_ISSUE_KEYWORDS
        + [
            "학자금",
            "취업 후 상환",
            "청년정책",
            "청년복지",
            "청년고용",
            "청년일자리",
            "청년월세",
            "청년전세",
            "청년주택",
            "청년대출",
            "청년부채",
            "청년금융",
            "청년자산형성",
            "고립·은둔 청년",
            "쉬었음 청년",
            "구직단념 청년",
        ]
    )
)
PUBLIC_HELPFUL_CONTEXT_KEYWORDS = tuple(
    dict.fromkeys(
        YOUTH_ISSUE_CONTEXT_KEYWORDS
        + YOUTH_POLICY_CONTEXT_KEYWORDS
        + YOUTH_INSTITUTION_CONTEXT_KEYWORDS
        + [
            "지원",
            "신청",
            "접수",
            "상담",
            "자립",
            "돌봄",
            "안내",
        ]
    )
)
PUBLIC_OPERATOR_ENTITY_KEYWORDS = (
    "청년센터",
    "청년공간",
    "청년허브",
    "청년일자리스테이션",
    "청년일자리센터",
    "청년창업센터",
    "청년미래센터",
)
PUBLIC_OPERATOR_ACTION_KEYWORDS = (
    "운영",
    "위탁",
    "개소",
    "신설",
    "설치",
    "폐지",
    "재개관",
    "시행",
    "계획",
    "지원사업",
    "모집",
    "공고",
)
LOW_VALUE_BUSINESS_KEYWORDS = (
    "순이익",
    "영업이익",
    "매출",
    "실적",
    "배당",
    "자사주",
    "주가",
    "시가총액",
    "소각",
    "증권",
)
LOW_VALUE_POLITICAL_ANALYSIS_KEYWORDS = (
    "여론조사",
    "지지율",
    "표심",
    "민심",
    "보수 성향",
    "진보 성향",
    "정치 성향",
)
POLITICAL_ATTACK_KEYWORDS = (
    "사퇴",
    "사퇴 촉구",
    "갑질",
    "의혹",
    "논란",
    "비판",
    "고발",
    "공세",
    "검증 요구",
)


def _contains_any(text: str, keywords: list[str] | tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def classify_topic_tags(text: str, *, limit: int = 2) -> list[str]:
    scored_tags: list[tuple[int, int, str]] = []
    for priority, (label, keywords) in enumerate(TOPIC_TAG_RULES):
        score = sum(1 for keyword in keywords if keyword in text)
        if score:
            scored_tags.append((-score, priority, label))
    return [label for _, _, label in sorted(scored_tags)[:limit]]


def has_youth_keyword_signal(text: str) -> bool:
    return _contains_any(text, YOUTH_KEYWORDS)


def has_strong_youth_context(text: str) -> bool:
    return _contains_any(text, YOUTH_STRONG_CONTEXT_KEYWORDS)


def has_policy_or_operational_youth_context(text: str) -> bool:
    return _contains_any(text, YOUTH_POLICY_OR_OPERATIONAL_CONTEXT_KEYWORDS)


def has_campaign_political_signal(text: str) -> bool:
    return _contains_any(text, POLITICAL_CAMPAIGN_KEYWORDS)


def has_substantive_promise_signal(text: str) -> bool:
    return has_campaign_political_signal(text) and _contains_any(text, SUBSTANTIVE_PROMISE_KEYWORDS)


def has_political_attack_signal(text: str) -> bool:
    return has_campaign_political_signal(text) and _contains_any(text, POLITICAL_ATTACK_KEYWORDS)


def has_meaningful_youth_context(article: dict[str, Any], text: str) -> bool:
    if article.get("source_kind") == "official":
        return True
    if article.get("issue_tags"):
        return True
    if _contains_any(text, YOUTH_RELATED_KEYWORDS) and not has_youth_keyword_signal(text):
        return True
    if not has_youth_keyword_signal(text):
        return _contains_any(text, YOUTH_RELATED_KEYWORDS)
    return has_strong_youth_context(text) or has_policy_or_operational_youth_context(text)


def is_weak_youth_signal(article: dict[str, Any], text: str) -> bool:
    if article.get("source_kind") == "official":
        return False
    if not has_youth_keyword_signal(text):
        return False
    return not has_meaningful_youth_context(article, text)


def _article_prominent_text(article: dict[str, Any]) -> str:
    return " ".join(
        part
        for part in [
            article.get("title", "") or "",
            article.get("summary", "") or "",
            article.get("lead_text", "") or "",
            article.get("section", "") or "",
        ]
        if part
    )


def _article_title_text(article: dict[str, Any]) -> str:
    return " ".join(
        part
        for part in [
            article.get("title", "") or "",
            article.get("section", "") or "",
        ]
        if part
    )


def has_direct_helpful_youth_signal(article: dict[str, Any], text: str, prominent_text: str | None = None) -> bool:
    prominent = prominent_text or _article_prominent_text(article)
    if _contains_any(prominent, PUBLIC_HELPFUL_DIRECT_KEYWORDS):
        return True
    return has_youth_keyword_signal(prominent) and has_strong_youth_context(prominent)


def has_operator_relevant_signal(article: dict[str, Any], text: str, prominent_text: str | None = None) -> bool:
    prominent = prominent_text or _article_prominent_text(article)
    if article.get("is_official_source") or article.get("governance_scope"):
        return True
    if _contains_any(prominent, PUBLIC_OPERATOR_ENTITY_KEYWORDS):
        return True
    if _contains_any(prominent, PUBLIC_OPERATOR_ACTION_KEYWORDS) and (
        has_direct_helpful_youth_signal(article, text, prominent)
        or _contains_any(prominent, PUBLIC_OPERATOR_ENTITY_KEYWORDS)
    ) and (
        has_central_government_context(article, text)
        or has_local_government_context(article, text)
        or has_public_institution_context(article, text)
    ):
        return True
    return has_public_institution_context(article, text) and _contains_any(prominent, PUBLIC_HELPFUL_CONTEXT_KEYWORDS)


def is_generic_business_result_article(article: dict[str, Any], text: str, prominent_text: str | None = None) -> bool:
    title_text = _article_title_text(article)
    if not _contains_any(title_text, LOW_VALUE_BUSINESS_KEYWORDS):
        return False
    if has_direct_helpful_youth_signal(article, text, title_text):
        return False
    return not has_operator_relevant_signal(article, text, title_text)


def is_political_analysis_article(article: dict[str, Any], text: str, prominent_text: str | None = None) -> bool:
    title_text = _article_title_text(article)
    if not _contains_any(title_text, LOW_VALUE_POLITICAL_ANALYSIS_KEYWORDS):
        return False
    if has_direct_helpful_youth_signal(article, text, title_text):
        return False
    return not has_operator_relevant_signal(article, text, title_text)


def score_public_relevance(article: dict[str, Any], text: str, prominent_text: str | None = None) -> int:
    prominent = prominent_text or _article_prominent_text(article)
    score = 0

    if has_direct_helpful_youth_signal(article, text, prominent):
        score += 4
    if has_operator_relevant_signal(article, text, prominent):
        score += 4
    if _contains_any(prominent, PUBLIC_HELPFUL_CONTEXT_KEYWORDS) and has_meaningful_youth_context(article, text):
        score += 2
    if article.get("issue_tags"):
        score += min(len(article.get("issue_tags") or []), 2)
    if article.get("governance_scope"):
        score += 2
    if article.get("is_official_source"):
        score += 2
    if is_clean_article(article):
        score += 1
    if article.get("substantive_promise"):
        score += 1

    if article.get("weak_youth_signal"):
        score -= 6
    if article.get("campaign_political") and not article.get("substantive_promise"):
        score -= 6
    if article.get("campaign_attack") or has_political_attack_signal(text):
        score -= 8
    if is_generic_business_result_article(article, text, prominent):
        score -= 10
    if is_political_analysis_article(article, text, prominent):
        score -= 8

    return score


def is_public_interest_article(article: dict[str, Any], text: str | None = None) -> bool:
    article_text = text or _article_text(article)
    prominent = _article_prominent_text(article)
    if article.get("is_noise") or article.get("article_type") == "opinion":
        return False
    if article.get("missing_youth_content_signal"):
        return False
    if article.get("campaign_attack") or has_political_attack_signal(article_text):
        return False
    if article.get("weak_youth_signal"):
        return False
    if article.get("campaign_political") and not article.get("substantive_promise"):
        return False
    if is_generic_business_result_article(article, article_text, prominent):
        return False
    if is_political_analysis_article(article, article_text, prominent):
        return False
    if article.get("is_official_source") or article.get("governance_scope"):
        return True

    has_help_signal = has_direct_helpful_youth_signal(article, article_text, prominent)
    has_operator_signal = has_operator_relevant_signal(article, article_text, prominent)
    if not has_help_signal and not has_operator_signal:
        return False

    score = int(article.get("public_relevance_score") or score_public_relevance(article, article_text, prominent))
    return score >= 4


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


def is_editorially_excluded(article: dict[str, Any]) -> bool:
    return normalize_editorial_decision(article.get("editorial_decision")) == DECISION_EXCLUDE


def is_editorially_included(article: dict[str, Any]) -> bool:
    return normalize_editorial_decision(article.get("editorial_decision")) == DECISION_INCLUDE


def is_editorially_highlighted(article: dict[str, Any]) -> bool:
    return normalize_editorial_highlighted(article.get("editorial_is_highlighted"))


def classify_articles(articles: list[dict]) -> list[dict]:
    classified: list[dict[str, Any]] = []
    for raw_article in articles:
        article = normalize_article_record(raw_article)
        text = _article_text(article)
        content_text = _article_content_text(article)
        issue_tags = list(dict.fromkeys((article.get("issue_tags") or []) + extract_issue_tags(content_text)))
        location_tags = list(dict.fromkeys((article.get("location_tags") or []) + extract_location_tags(content_text)))
        region = article.get("region") or infer_region(content_text, location_tags)
        if not region:
            region = NATIONWIDE_REGION

        article_type = article.get("article_type") or detect_article_type(
            article.get("title", ""),
            article.get("section", "") or "",
            article.get("body_text", "") or "",
        )
        campaign_political = has_campaign_political_signal(text)
        substantive_promise = has_substantive_promise_signal(text)
        campaign_attack = has_political_attack_signal(text)
        is_official = article.get("source_kind") == "official" or article_type == "official"
        has_youth_content_signal = _contains_any(content_text, YOUTH_RELATED_KEYWORDS)
        missing_youth_content_signal = not is_official and not has_youth_content_signal
        topic_tags = list(dict.fromkeys((article.get("topic_tags") or []) + classify_topic_tags(content_text)))
        weak_youth_signal = False if missing_youth_content_signal else is_weak_youth_signal(article, content_text)
        has_policy_operational_context = has_policy_or_operational_youth_context(content_text)
        governance_activity_types = extract_governance_activity_types(content_text)
        governance_scope = extract_governance_scope(article, content_text, governance_activity_types)
        hub_topics = extract_hub_topics(content_text, governance_scope)
        hub_owner_label = extract_hub_owner_label(article, content_text, governance_scope, region)
        hub_cluster_key = build_hub_cluster_key(
            article,
            governance_scope=governance_scope,
            hub_owner_label=hub_owner_label,
            region=region,
            hub_topics=hub_topics,
            governance_activity_types=governance_activity_types,
        )
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
        is_noise = False if is_official else detect_noise(content_text) or weak_youth_signal or missing_youth_content_signal
        pipeline_flags = {
            **article.get("pipeline_flags", {}),
            "collected": True,
            "deduped": True,
            "classified": True,
            "selected": False,
            "published": False,
        }

        classified_article = apply_clean_signal(
            {
                **article,
                "categories": ordered_categories,
                "region": region,
                "issue_tags": issue_tags,
                "topic_tags": topic_tags[:2],
                "location_tags": location_tags,
                "article_type": article_type,
                "is_noise": is_noise,
                "has_youth_content_signal": has_youth_content_signal,
                "missing_youth_content_signal": missing_youth_content_signal,
                "weak_youth_signal": weak_youth_signal,
                "campaign_political": campaign_political,
                "substantive_promise": substantive_promise,
                "campaign_attack": campaign_attack,
                "has_policy_operational_context": has_policy_operational_context,
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
                    weak_youth_signal=weak_youth_signal,
                    campaign_political=campaign_political,
                    substantive_promise=substantive_promise,
                    campaign_attack=campaign_attack,
                ),
                "editorial_decision": normalize_editorial_decision(article.get("editorial_decision")),
                "editorial_is_highlighted": normalize_editorial_highlighted(article.get("editorial_is_highlighted")),
                "editorial_note": (article.get("editorial_note") or "").strip(),
                "editorial_updated_at": article.get("editorial_updated_at"),
                "editorial_updated_by": article.get("editorial_updated_by"),
                "pipeline_flags": pipeline_flags,
                "drop_reason": None,
            }
        )
        public_relevance_score = score_public_relevance(classified_article, text)
        classified_article["has_direct_helpful_youth_signal"] = has_direct_helpful_youth_signal(
            classified_article,
            text,
        )
        classified_article["has_operator_relevant_signal"] = has_operator_relevant_signal(
            classified_article,
            text,
        )
        classified_article["public_relevance_score"] = public_relevance_score
        classified_article["is_public_interest_article"] = is_public_interest_article(classified_article, text)
        classified.append(classified_article)
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
        article["editorial_is_highlighted"] = normalize_editorial_highlighted(article.get("editorial_is_highlighted"))
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
        is_manual_priority = is_editorially_highlighted(article) or is_editorially_included(article)
        if article.get("is_noise") and not is_manual_priority:
            article["drop_reason"] = "noise_filtered"
        elif not article.get("is_public_interest_article") and not is_manual_priority:
            article["drop_reason"] = "public_relevance_filtered"
        elif is_editorially_excluded(article):
            article["drop_reason"] = "editorial_excluded"
        else:
            article["drop_reason"] = None
        prepared.append(article)
        if (
            not is_editorially_excluded(article)
            and (not article.get("is_noise") or is_manual_priority)
            and (article.get("is_public_interest_article") or is_manual_priority)
        ):
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

    highlighted_candidates = [article for article in ranked if is_editorially_highlighted(article)]
    take_candidates(highlighted_candidates, len(highlighted_candidates))

    included_candidates = [
        article
        for article in ranked
        if is_editorially_included(article) and not is_editorially_highlighted(article)
    ]
    take_candidates(included_candidates, len(included_candidates))

    for bucket, minimum in SELECTION_BUCKET_SPECS:
        bucket_candidates = [
            article
            for article in ranked
            if (
                article.get("selection_bucket") == bucket
                and not is_editorially_highlighted(article)
                and not is_editorially_included(article)
            )
        ]
        take_candidates(bucket_candidates, minimum)

    if len(selected) < limit:
        remaining = [
            article
            for article in ranked
            if article_identity_key(article) not in selected_keys
            and not is_editorially_highlighted(article)
            and not is_editorially_included(article)
        ]
        take_candidates(remaining, limit - len(selected))

    protected_keys = {
        article_identity_key(article)
        for article in selected
        if is_editorially_highlighted(article) or is_editorially_included(article)
    }
    if len(selected) > limit and protected_keys:
        ordered_selected = sort_selected_articles(selected)
        protected_articles = [article for article in ordered_selected if article_identity_key(article) in protected_keys]
        auto_articles = [article for article in ordered_selected if article_identity_key(article) not in protected_keys]
        selected = protected_articles + auto_articles[: max(limit - len(protected_articles), 0)]
        selected_keys = {article_identity_key(article) for article in selected}
    elif len(selected) > limit:
        selected = sort_selected_articles(selected)[:limit]
        selected_keys = {article_identity_key(article) for article in selected}

    for article in prepared:
        key = article_identity_key(article)
        if key in selected_keys:
            article["pipeline_flags"]["selected"] = True
            article["drop_reason"] = None
            if is_editorially_highlighted(article):
                article["selection_reason"] = "editorial_highlighted"
            elif is_editorially_included(article):
                article["selection_reason"] = "editorial_included"
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
        article["editorial_is_highlighted"] = normalize_editorial_highlighted(article.get("editorial_is_highlighted"))
        badges: list[str] = []
        if is_editorially_highlighted(article):
            badges.append("하이라이트")
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
    if _contains_any(text, HUB_ROUTING_KEYWORDS):
        return False
    if has_youth_keyword_signal(text):
        return not (has_strong_youth_context(text) or has_policy_or_operational_youth_context(text))
    return not _contains_any(text, YOUTH_RELATED_KEYWORDS)


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
    if any(keyword in source_text for keyword in NON_POLITICAL_HUB_EXCLUDE_KEYWORDS):
        return False
    return bool(_extract_public_institution_owner_label(source_text)) or any(
        keyword in source_text for keyword in PUBLIC_INSTITUTION_CONTEXT_KEYWORDS
    )


def is_excluded_hub_record(article: dict, text: str, activity_types: list[str] | None = None) -> bool:
    source_text = _hub_context_text(article, text)
    if any(keyword in source_text for keyword in NON_POLITICAL_HUB_EXCLUDE_KEYWORDS):
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
    preview = article.get("youth_excerpt") or extract_youth_preview_text(article, limit=160)
    primary_category = (article.get("categories") or [CATEGORY_NOW])[0]
    topic_text = ", ".join(article.get("topic_tags") or [])
    headline_prefix = f"{primary_category} · {topic_text}" if topic_text else primary_category
    first_line = f"[{headline_prefix}] {article.get('title', '제목 없음')}"
    second_line = (preview or lead)[:120] if (preview or lead) else "본문 보강이 필요한 기사입니다."
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
    weak_youth_signal: bool = False,
    campaign_political: bool = False,
    substantive_promise: bool = False,
    campaign_attack: bool = False,
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
    if weak_youth_signal:
        chunks.append("청년맥락 약함")
    if campaign_political:
        chunks.append("선거성")
    if substantive_promise:
        chunks.append("실질공약")
    if campaign_attack:
        chunks.append("공방형")
    chunks.append(f"지역={region}")
    return " / ".join(chunks)


def build_selection_reason(article: dict, score: int) -> str:
    bucket = BUCKET_LABELS.get(determine_selection_bucket(article), "기타")
    issue_tags = article.get("issue_tags") or []
    issue_text = f" / 이슈={', '.join(issue_tags[:2])}" if issue_tags else ""
    public_score = int(article.get("public_relevance_score") or 0)
    public_text = " / 공개적합" if article.get("is_public_interest_article") else " / 공개보류"
    return f"{bucket} 버킷 우선순위 반영{issue_text}{public_text} (score={score}, public={public_score})"


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

    if is_clean_article(article):
        score += 2
    if int(article.get("clean_score") or 0) >= 6:
        score += 1
    score += int(article.get("public_relevance_score") or 0)
    if article.get("campaign_political"):
        score -= 3
    if article.get("substantive_promise"):
        score += 2
    if article.get("weak_youth_signal"):
        score -= 5
    if not article.get("is_public_interest_article"):
        score -= 12

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
            0 if is_editorially_highlighted(article) else 1,
            0 if is_editorially_included(article) else 1,
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
    text = _article_content_text(article)
    if article.get("issue_tags"):
        return True
    if has_meaningful_youth_context(article, text):
        return True
    return has_youth_keyword_signal(text) and has_policy_or_operational_youth_context(text)


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


def _article_content_text(article: dict[str, Any]) -> str:
    authors = " ".join(article.get("authors") or [])
    return " ".join(
        part
        for part in [
            _strip_source_markers(article.get("title", "") or "", article),
            _strip_source_markers(article.get("summary", "") or "", article),
            _strip_source_markers(article.get("lead_text", "") or "", article),
            _strip_source_markers(article.get("section", "") or "", article),
            _strip_source_markers(article.get("body_text", "") or "", article),
            authors,
        ]
        if part
    )


def _strip_source_markers(value: str, article: dict[str, Any]) -> str:
    text = normalize_article_title(value)
    if not text:
        return ""
    source_values = [
        normalize_article_title(candidate)
        for candidate in (
            article.get("source"),
            article.get("source_name"),
            article.get("publisher_domain"),
        )
        if normalize_article_title(candidate)
    ]
    for source in sorted(set(source_values), key=len, reverse=True):
        escaped = re.escape(source)
        text = re.sub(rf"^\s*[\[【〈(<［]\s*{escaped}\s*[\]】〉)>］]\s*", "", text)
        text = re.sub(rf"\s*[-|·]\s*{escaped}\s*$", "", text)
    return normalize_article_title(text)


def _article_text(article: dict[str, Any]) -> str:
    return " ".join(
        part
        for part in [
            _article_content_text(article),
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

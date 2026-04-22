from __future__ import annotations

import difflib
import html
import re
from datetime import datetime
from typing import Any
from urllib.parse import parse_qsl, urljoin, urlparse, urlunparse

from .collect import fetch_url, strip_html
from .constants import OPINION_KEYWORDS, REGIONS


GOOGLE_NEWS_HOSTS = {"news.google.com"}
PORTAL_HOSTS = {
    "v.daum.net",
    "news.v.daum.net",
    "n.news.naver.com",
    "news.naver.com",
}
SEOUL_DISTRICTS = [
    "강남",
    "강동",
    "강북",
    "강서",
    "관악",
    "광진",
    "구로",
    "금천",
    "노원",
    "도봉",
    "동대문",
    "동작",
    "마포",
    "서대문",
    "서초",
    "성동",
    "성북",
    "송파",
    "양천",
    "영등포",
    "용산",
    "은평",
    "종로",
    "중구",
    "중랑",
]
ISSUE_TAG_KEYWORDS: dict[str, list[str]] = {
    "청년센터 운영": ["청년센터", "청년일자리센터", "청년공간", "청년허브"],
    "노동권": ["노동권", "근로계약", "고용승계", "직장내 괴롭힘", "부당해고", "노동조합"],
    "고립·은둔": ["고립", "은둔", "은둔형", "사회적 고립"],
    "주거": ["주거", "월세", "전세", "주택", "생활비"],
    "부채": ["부채", "대출", "금융", "신용회복"],
    "고용": ["고용", "취업", "일자리", "구직단념", "쉬었음", "청년고용조사"],
}
BODY_CONTAINER_PATTERNS = [
    r'<article[^>]*itemprop=["\']articleBody["\'][^>]*>(?P<body>.*?)</article>',
    r'<div[^>]+id=["\']article-view-content-div["\'][^>]*>(?P<body>.*?)</div>',
    r'<div[^>]+class=["\'][^"\']*article[^"\']*body[^"\']*["\'][^>]*>(?P<body>.*?)</div>',
    r'<div[^>]+class=["\'][^"\']*article[^"\']*view[^"\']*body[^"\']*["\'][^>]*>(?P<body>.*?)</div>',
]
NATIONWIDE_REGION = "전국"
LOCATION_STOPWORDS = {"다시", "예시", "실시", "지시", "변경시", "누구"}


def normalize_tracking_url(url: str | None) -> str:
    if not url:
        return ""
    parts = urlparse(url.strip())
    query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        lowered = key.lower()
        if lowered.startswith("utm_"):
            continue
        if lowered in {"from", "botref", "botevent", "ref", "rss", "spm"}:
            continue
        query.append((key, value))
    normalized_path = parts.path.rstrip("/") or "/"
    return urlunparse(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            normalized_path,
            "",
            "&".join(f"{key}={value}" for key, value in query),
            "",
        )
    )


def is_google_news_url(url: str | None) -> bool:
    if not url:
        return False
    return urlparse(url).netloc.lower() in GOOGLE_NEWS_HOSTS


def is_portal_url(url: str | None) -> bool:
    if not url:
        return False
    return urlparse(url).netloc.lower() in PORTAL_HOSTS


def extract_domain(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.strip()
    if "://" not in candidate and "/" not in candidate:
        return candidate.lower()
    parsed = urlparse(candidate)
    return parsed.netloc.lower() or None


def infer_source_homepage_url(record: dict[str, Any]) -> str | None:
    for candidate in (record.get("source_url"), record.get("source_homepage_url"), record.get("source")):
        if not candidate or not isinstance(candidate, str):
            continue
        value = candidate.strip()
        if not value:
            continue
        if value.startswith(("http://", "https://")):
            return value
        if " " in value or "/" in value:
            continue
        if "." not in value:
            continue
        return f"https://{value}"
    return None


def normalize_article_title(value: str | None) -> str:
    if not value:
        return ""
    normalized = strip_html(value)
    normalized = html.unescape(normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def strip_title_suffixes(value: str | None, suffixes: list[str] | tuple[str, ...]) -> str:
    normalized = normalize_article_title(value)
    if not normalized:
        return ""
    for raw_suffix in suffixes:
        suffix = normalize_article_title(raw_suffix)
        if not suffix:
            continue
        markers = (
            f" - {suffix}",
            f" | {suffix}",
            f" : {suffix}",
            f" / {suffix}",
            f" :: {suffix}",
        )
        updated = True
        while updated:
            updated = False
            for marker in markers:
                if normalized.endswith(marker):
                    normalized = normalized[: -len(marker)].strip()
                    updated = True
    return normalized


def clean_metadata_title(value: str | None, article: dict[str, Any]) -> str:
    normalized = normalize_article_title(value)
    if not normalized:
        return ""
    cleaned = strip_title_suffixes(
        normalized,
        (
            article.get("source") or "",
            article.get("source_name") or "",
        ),
    )
    return cleaned or normalized


def title_similarity(left: str | None, right: str | None) -> float:
    return difflib.SequenceMatcher(
        a=normalize_article_title(left).lower(),
        b=normalize_article_title(right).lower(),
    ).ratio()


def normalize_article_record(article: dict[str, Any]) -> dict[str, Any]:
    record = dict(article)
    url = record.get("url", "")
    source_url = infer_source_homepage_url(record)
    source_domain = extract_domain(source_url) or extract_domain(record.get("source"))
    feed_url = record.get("feed_url") or url
    discovered_from = list(
        dict.fromkeys(record.get("discovered_from") or [record.get("source_name") or record.get("source")])
    )
    portal_urls = list(dict.fromkeys(record.get("portal_urls") or ([] if not is_portal_url(url) else [url])))
    publisher_url = record.get("publisher_url")
    canonical_url = record.get("canonical_url")
    if not canonical_url:
        if publisher_url:
            canonical_url = normalize_tracking_url(publisher_url)
        else:
            canonical_url = normalize_tracking_url(url)

    record.update(
        {
            "feed_url": feed_url,
            "canonical_url": canonical_url,
            "publisher_url": publisher_url,
            "portal_urls": portal_urls,
            "publisher_domain": record.get("publisher_domain") or source_domain,
            "publisher_published_at": record.get("publisher_published_at") or record.get("published_date"),
            "portal_published_at": record.get("portal_published_at"),
            "section": record.get("section"),
            "article_type": record.get("article_type"),
            "authors": list(dict.fromkeys(record.get("authors") or [])),
            "discovered_from": discovered_from,
            "resolved_at": record.get("resolved_at"),
            "body_text": record.get("body_text"),
            "issue_tags": list(dict.fromkeys(record.get("issue_tags") or [])),
            "location_tags": list(dict.fromkeys(record.get("location_tags") or [])),
            "source_homepage_url": source_url,
            "pipeline_flags": {
                "collected": True,
                "deduped": bool(record.get("pipeline_flags", {}).get("deduped")),
                "classified": bool(record.get("pipeline_flags", {}).get("classified")),
                "selected": bool(record.get("pipeline_flags", {}).get("selected")),
                "published": bool(record.get("pipeline_flags", {}).get("published")),
                "resolved_url": bool(record.get("pipeline_flags", {}).get("resolved_url")),
                "body_enriched": bool(record.get("pipeline_flags", {}).get("body_enriched")),
            },
            "drop_reason": record.get("drop_reason"),
        }
    )
    return record


def article_identity_key(article: dict[str, Any]) -> str:
    for candidate in (
        article.get("canonical_url"),
        article.get("publisher_url"),
        article.get("url"),
        article.get("feed_url"),
    ):
        normalized = normalize_tracking_url(candidate)
        if normalized:
            return normalized
    title = normalize_article_title(article.get("title"))
    source = (article.get("source") or article.get("publisher_domain") or "").strip().lower()
    published = (article.get("publisher_published_at") or article.get("published_date") or "")[:10]
    return f"title:{title}|source:{source}|date:{published}"


def preferred_article_url(article: dict[str, Any]) -> str:
    if article.get("publisher_url"):
        return article["publisher_url"]
    portal_urls = article.get("portal_urls") or []
    if portal_urls:
        return portal_urls[0]
    if article.get("canonical_url"):
        return article["canonical_url"]
    return article.get("url") or ""


def extract_meta_content(html_text: str, key: str, attr_name: str = "name") -> str | None:
    attr_name = attr_name.lower()
    key = key.lower()
    attr_pattern = re.compile(
        r'([^\s=/>]+)\s*=\s*(?:(["\'])(.*?)\2|([^\s>]+))',
        re.IGNORECASE | re.DOTALL,
    )
    for match in re.finditer(r"<meta\b[^>]*>", html_text, re.IGNORECASE | re.DOTALL):
        attrs: dict[str, str] = {}
        for attr_match in attr_pattern.finditer(match.group(0)):
            value = attr_match.group(3) if attr_match.group(3) is not None else (attr_match.group(4) or "")
            attrs[attr_match.group(1).lower()] = html.unescape(value).strip()
        if attrs.get(attr_name, "").lower() == key and attrs.get("content"):
            return attrs["content"]
    return None


def extract_canonical_link(html_text: str) -> str | None:
    match = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\'](.*?)["\']', html_text, re.IGNORECASE)
    if not match:
        return None
    return html.unescape(match.group(1)).strip()


def extract_links_with_titles(html_text: str, base_url: str) -> list[tuple[str, str]]:
    pattern = re.compile(r'<a[^>]+href=["\'](?P<href>[^"\']+)["\'][^>]*>(?P<title>.*?)</a>', re.IGNORECASE | re.DOTALL)
    links: list[tuple[str, str]] = []
    for match in pattern.finditer(html_text):
        title = normalize_article_title(match.group("title"))
        href = html.unescape(match.group("href")).strip()
        if not title or not href or href.startswith("javascript:") or href.startswith("#"):
            continue
        links.append((urljoin(base_url, href), title))
    return links


def discover_publisher_url_via_homepage(
    article: dict[str, Any],
    homepage_cache: dict[str, list[tuple[str, str]]],
) -> str | None:
    homepage_url = article.get("source_homepage_url")
    title = normalize_article_title(article.get("title"))
    if not homepage_url or not title:
        return None

    if homepage_url not in homepage_cache:
        try:
            homepage_html = fetch_url(homepage_url, timeout=20)
            homepage_cache[homepage_url] = extract_links_with_titles(homepage_html, homepage_url)
        except Exception:
            homepage_cache[homepage_url] = []

    best_url = None
    best_score = 0.0
    for href, candidate_title in homepage_cache[homepage_url]:
        normalized_candidate = normalize_article_title(candidate_title)
        score = title_similarity(title, normalized_candidate)
        if title and normalized_candidate and (title in normalized_candidate or normalized_candidate in title):
            score = max(score, 0.97)
        if score > best_score:
            best_score = score
            best_url = href

    if best_score >= 0.92:
        return best_url
    return None


def extract_body_text(html_text: str) -> str:
    for pattern in BODY_CONTAINER_PATTERNS:
        match = re.search(pattern, html_text, re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        body = strip_html(match.group("body"))
        body = re.sub(r"\s+", " ", body).strip()
        if len(body) >= 80:
            return body[:4000]

    paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", html_text, re.IGNORECASE | re.DOTALL)
    paragraph_text = [re.sub(r"\s+", " ", strip_html(paragraph)).strip() for paragraph in paragraphs]
    paragraph_text = [text for text in paragraph_text if len(text) >= 20]
    return " ".join(paragraph_text)[:4000]


def detect_article_type(title: str, section: str, body_text: str) -> str | None:
    haystack = " ".join(part for part in [title, section, body_text] if part)
    if any(keyword in haystack for keyword in OPINION_KEYWORDS):
        return "opinion"
    if any(keyword in haystack for keyword in ["오피니언", "칼럼", "사설", "기고", "연재"]):
        return "opinion"
    if any(keyword in haystack for keyword in ["보도자료", "정책브리핑"]):
        return "official"
    return None


def extract_location_tags(text: str) -> list[str]:
    tags: list[str] = []
    for region in REGIONS:
        if region and region in text:
            tags.append(region)
    for district in SEOUL_DISTRICTS:
        if district and district in text:
            tags.append(district)
    for match in re.finditer(r"(?:^|[\s'\"(])([가-힣]{1,12}(?:시|군|구))(?:[\s,.'\")]|$)", text):
        candidate = match.group(1)
        if candidate in LOCATION_STOPWORDS:
            continue
        if len(candidate) > 5 and not candidate.endswith(("군", "구")):
            continue
        tags.append(candidate)
    return list(dict.fromkeys(tags))


def infer_region(text: str, location_tags: list[str]) -> str:
    for region in REGIONS:
        if region and region in text:
            return region
    for tag in location_tags:
        if tag in SEOUL_DISTRICTS:
            return "서울"
    return NATIONWIDE_REGION


def extract_issue_tags(text: str) -> list[str]:
    tags: list[str] = []
    for label, keywords in ISSUE_TAG_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            tags.append(label)
    return tags


def parse_generic_article_page(html_text: str, source_url: str) -> dict[str, Any]:
    canonical = extract_canonical_link(html_text) or extract_meta_content(html_text, "og:url", "property")
    title = extract_meta_content(html_text, "og:title", "property") or extract_meta_content(html_text, "title")
    if not title:
        title_match = re.search(r"<title>(.*?)</title>", html_text, re.IGNORECASE | re.DOTALL)
        if title_match:
            title = normalize_article_title(title_match.group(1))

    description = (
        extract_meta_content(html_text, "og:description", "property")
        or extract_meta_content(html_text, "description")
        or ""
    )
    raw_section_parts = [
        extract_meta_content(html_text, "Classification"),
        extract_meta_content(html_text, "article:section1", "property"),
        extract_meta_content(html_text, "article:section2", "property"),
    ]
    section_parts: list[str] = []
    for part in raw_section_parts:
        if not part:
            continue
        cleaned = part.strip()
        if any(cleaned == existing or cleaned in existing or existing in cleaned for existing in section_parts):
            continue
        section_parts.append(cleaned)
    section = " > ".join(section_parts)
    published_at = (
        extract_meta_content(html_text, "article:published_time", "property")
        or extract_meta_content(html_text, "og:article:published_time", "property")
        or extract_meta_content(html_text, "datePublished", "itemprop")
        or ""
    )
    body_text = extract_body_text(html_text)
    author_values = [
        extract_meta_content(html_text, "author"),
        extract_meta_content(html_text, "og:article:author", "property"),
    ]
    authors = [value for value in author_values if value]
    source_host = urlparse(source_url).netloc.lower()
    portal_urls = [source_url] if is_portal_url(source_url) else []
    publisher_url = None
    canonical_url = normalize_tracking_url(canonical or source_url)
    if canonical:
        if is_portal_url(canonical):
            portal_urls.append(canonical)
        else:
            publisher_url = canonical
    if not publisher_url and not is_portal_url(source_url) and source_host not in GOOGLE_NEWS_HOSTS:
        publisher_url = source_url

    merged_text = " ".join(part for part in [title or "", description, section, body_text] if part)
    location_tags = extract_location_tags(merged_text)
    return {
        "title": title or None,
        "canonical_url": canonical_url,
        "publisher_url": publisher_url,
        "portal_urls": list(dict.fromkeys(portal_urls)),
        "publisher_domain": extract_domain(publisher_url or canonical or source_url),
        "publisher_published_at": published_at or None,
        "portal_published_at": published_at if is_portal_url(source_url) else None,
        "section": section or None,
        "article_type": detect_article_type(title or "", section, body_text),
        "authors": list(dict.fromkeys(authors)),
        "lead_text": description or None,
        "body_text": body_text or None,
        "issue_tags": extract_issue_tags(merged_text),
        "location_tags": location_tags,
        "region": infer_region(merged_text, location_tags),
    }


def resolve_article_metadata(
    article: dict[str, Any],
    *,
    homepage_cache: dict[str, list[tuple[str, str]]],
    page_cache: dict[str, dict[str, Any] | None],
    allow_playwright_fallback: bool = False,
) -> dict[str, Any]:
    del allow_playwright_fallback
    updated = normalize_article_record(article)
    current_url = updated.get("url") or ""
    target_url = None

    if is_google_news_url(current_url):
        publisher_url = discover_publisher_url_via_homepage(updated, homepage_cache)
        if publisher_url:
            updated["publisher_url"] = publisher_url
            updated["canonical_url"] = normalize_tracking_url(publisher_url)
            updated["publisher_domain"] = extract_domain(publisher_url)
            updated["pipeline_flags"]["resolved_url"] = True
            target_url = publisher_url
        else:
            updated["canonical_url"] = normalize_tracking_url(current_url)
    else:
        target_url = current_url
        updated["pipeline_flags"]["resolved_url"] = True
        if is_portal_url(current_url):
            updated["portal_urls"] = list(dict.fromkeys((updated.get("portal_urls") or []) + [current_url]))
        else:
            updated["publisher_url"] = updated.get("publisher_url") or current_url
            updated["publisher_domain"] = updated.get("publisher_domain") or extract_domain(current_url)
            updated["canonical_url"] = normalize_tracking_url(updated.get("publisher_url") or current_url)

    if target_url:
        if target_url not in page_cache:
            try:
                page_html = fetch_url(target_url, timeout=20)
                page_cache[target_url] = parse_generic_article_page(page_html, target_url)
            except Exception:
                page_cache[target_url] = None
        metadata = page_cache[target_url]
        if metadata:
            for key in [
                "title",
                "canonical_url",
                "publisher_url",
                "publisher_domain",
                "publisher_published_at",
                "portal_published_at",
                "section",
                "article_type",
                "body_text",
                "region",
            ]:
                if metadata.get(key):
                    if key == "title":
                        updated[key] = clean_metadata_title(metadata[key], updated)
                    else:
                        updated[key] = metadata[key]
            if metadata.get("lead_text"):
                updated["lead_text"] = metadata["lead_text"]
            updated["authors"] = list(dict.fromkeys((updated.get("authors") or []) + (metadata.get("authors") or [])))
            updated["portal_urls"] = list(
                dict.fromkeys((updated.get("portal_urls") or []) + (metadata.get("portal_urls") or []))
            )
            updated["issue_tags"] = list(
                dict.fromkeys((updated.get("issue_tags") or []) + (metadata.get("issue_tags") or []))
            )
            updated["location_tags"] = list(
                dict.fromkeys((updated.get("location_tags") or []) + (metadata.get("location_tags") or []))
            )
            updated["pipeline_flags"]["body_enriched"] = bool(updated.get("body_text"))

    text_for_classification = " ".join(
        part
        for part in [
            updated.get("title") or "",
            updated.get("lead_text") or "",
            updated.get("section") or "",
            updated.get("body_text") or "",
        ]
        if part
    )
    if not updated.get("issue_tags"):
        updated["issue_tags"] = extract_issue_tags(text_for_classification)
    if not updated.get("location_tags"):
        updated["location_tags"] = extract_location_tags(text_for_classification)
    if updated.get("region") in {None, "", NATIONWIDE_REGION}:
        updated["region"] = infer_region(text_for_classification, updated.get("location_tags") or [])
    updated["resolved_at"] = datetime.now().astimezone().isoformat()
    return updated


def enrich_articles_for_curation(
    articles: list[dict[str, Any]],
    *,
    max_network_enrich: int = 240,
) -> list[dict[str, Any]]:
    homepage_cache: dict[str, list[tuple[str, str]]] = {}
    page_cache: dict[str, dict[str, Any] | None] = {}
    enriched: list[dict[str, Any]] = []

    sorted_indexes = sorted(
        range(len(articles)),
        key=lambda index: articles[index].get("publisher_published_at")
        or articles[index].get("published_date")
        or "",
        reverse=True,
    )
    network_indexes = set(sorted_indexes[:max_network_enrich])

    for index, article in enumerate(articles):
        normalized = normalize_article_record(article)
        if index in network_indexes:
            normalized = resolve_article_metadata(
                normalized,
                homepage_cache=homepage_cache,
                page_cache=page_cache,
            )
        enriched.append(normalized)
    return enriched

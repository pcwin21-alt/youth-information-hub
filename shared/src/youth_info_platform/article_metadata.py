from __future__ import annotations

import difflib
import html
import json
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import parse_qsl, urljoin, urlparse, urlunparse

from .collect import fetch_url, strip_html
from .constants import OPINION_KEYWORDS, REGIONS, YOUTH_KEYWORDS


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
HTML_ATTR_PATTERN = re.compile(
    r'([^\s=/>]+)\s*=\s*(?:(["\'])(.*?)\2|([^\s>]+))',
    re.IGNORECASE | re.DOTALL,
)
PUBLISHED_META_FIELDS = (
    ("article:published_time", "property"),
    ("og:article:published_time", "property"),
    ("article:published", "property"),
    ("datePublished", "itemprop"),
    ("datePublished", "name"),
    ("pubdate", "name"),
    ("publishdate", "name"),
    ("publish_date", "name"),
    ("parsely-pub-date", "name"),
    ("sailthru.date", "name"),
    ("dc.date.issued", "name"),
    ("dcterms.created", "name"),
    ("originalpublicationdate", "name"),
    ("date", "name"),
)
YOUTH_EXCERPT_KEYWORDS = tuple(dict.fromkeys(["청년", *YOUTH_KEYWORDS]))
EXCERPT_BOUNDARY_CHARS = ".!?。！？"
NATIONWIDE_REGION = "전국"
LOCATION_STOPWORDS = {"다시", "예시", "실시", "지시", "변경시", "누구"}
HTTP_ERROR_PAGE_TITLES = {
    "401 unauthorized",
    "403 forbidden",
    "404 not found",
    "429 too many requests",
    "500 internal server error",
    "502 bad gateway",
    "503 service unavailable",
    "504 gateway timeout",
    "access denied",
    "forbidden",
}
MEDIA_URL_BLOCKLIST_TOKENS = (
    "spacer",
    "blank",
    "pixel",
    "tracking",
    "analytics",
)


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


def normalize_media_url(value: Any, base_url: str | None = None) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict):
        for key in ("url", "contentUrl", "thumbnailUrl", "@id"):
            if normalized := normalize_media_url(value.get(key), base_url):
                return normalized
        return None
    if isinstance(value, list):
        for item in value:
            if normalized := normalize_media_url(item, base_url):
                return normalized
        return None

    raw = html.unescape(str(value)).strip().strip("'\"")
    if not raw or raw.lower().startswith(("data:", "javascript:", "mailto:")):
        return None
    resolved = urljoin(base_url or "", raw)
    parsed = urlparse(resolved)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return None
    lowered = resolved.lower()
    if any(token in lowered for token in MEDIA_URL_BLOCKLIST_TOKENS):
        return None
    return resolved


def extract_json_ld_image_url(html_text: str, base_url: str) -> str | None:
    pattern = re.compile(
        r'<script[^>]+type=["\'][^"\']*ld\+json[^"\']*["\'][^>]*>(?P<payload>.*?)</script>',
        re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(html_text):
        payload = html.unescape(match.group("payload")).strip()
        payload = re.sub(r"^\s*<!--|-->\s*$", "", payload).strip()
        if not payload:
            continue
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            continue
        for node in _iter_json_ld_nodes(parsed):
            for key in ("image", "thumbnailUrl", "primaryImageOfPage"):
                if key in node:
                    if normalized := normalize_media_url(node.get(key), base_url):
                        return normalized
    return None


def extract_article_image_url(html_text: str, base_url: str) -> str | None:
    candidates = [
        extract_meta_content(html_text, "og:image", "property"),
        extract_meta_content(html_text, "og:image:secure_url", "property"),
        extract_meta_content(html_text, "og:image:url", "property"),
        extract_meta_content(html_text, "twitter:image", "name"),
        extract_meta_content(html_text, "twitter:image:src", "name"),
        extract_meta_content(html_text, "image", "itemprop"),
        extract_json_ld_image_url(html_text, base_url),
    ]
    for candidate in candidates:
        if normalized := normalize_media_url(candidate, base_url):
            return normalized
    return None


def extract_publisher_icon_url(html_text: str, base_url: str) -> str | None:
    icon_candidates: list[tuple[int, str]] = []
    for match in re.finditer(r"<link\b[^>]*>", html_text, re.IGNORECASE | re.DOTALL):
        attrs = parse_html_attributes(match.group(0))
        rel_values = {part.strip().lower() for part in (attrs.get("rel") or "").split()}
        href = attrs.get("href")
        if not href:
            continue
        priority = None
        if "apple-touch-icon" in rel_values:
            priority = 0
        elif "icon" in rel_values or "shortcut" in rel_values and "icon" in rel_values:
            priority = 1
        if priority is None:
            continue
        if normalized := normalize_media_url(href, base_url):
            icon_candidates.append((priority, normalized))

    if icon_candidates:
        return sorted(icon_candidates, key=lambda item: item[0])[0][1]

    parsed = urlparse(base_url)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}/favicon.ico"
    return None


def is_http_error_page_title(value: str | None) -> bool:
    normalized = normalize_article_title(value).casefold()
    if not normalized:
        return False
    normalized = re.sub(r"\s+", " ", normalized)
    if normalized in HTTP_ERROR_PAGE_TITLES:
        return True
    return bool(
        re.fullmatch(
            r"(?:error\s*)?(?:401|403|404|429|500|502|503|504)"
            r"(?:\s*[-:]\s*|\s+)"
            r"(?:unauthorized|forbidden|not found|too many requests|internal server error|bad gateway|service unavailable|gateway timeout)",
            normalized,
        )
    )


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


def simplify_title_for_comparison(value: str | None) -> str:
    normalized = normalize_article_title(value).lower()
    return re.sub(r"[^0-9a-z가-힣]+", "", normalized)


def should_prefer_richer_heading_title(base_title: str | None, heading_title: str | None) -> bool:
    base = normalize_article_title(base_title)
    heading = normalize_article_title(heading_title)
    if not heading:
        return False
    if not base:
        return True
    if len(heading) <= len(base):
        return False
    simplified_base = simplify_title_for_comparison(base)
    simplified_heading = simplify_title_for_comparison(heading)
    return bool(simplified_base and simplified_base in simplified_heading)


def extract_heading_titles(html_text: str) -> list[str]:
    titles: list[str] = []
    for match in re.finditer(r"<h1\b[^>]*>(?P<title>.*?)</h1>", html_text, re.IGNORECASE | re.DOTALL):
        title = normalize_article_title(match.group("title"))
        if title:
            titles.append(title)
    return list(dict.fromkeys(titles))


def choose_article_page_title(base_title: str | None, heading_titles: list[str]) -> str:
    title = normalize_article_title(base_title)
    richer_headings = [
        heading
        for heading in heading_titles
        if should_prefer_richer_heading_title(title, heading)
    ]
    if richer_headings:
        return max(richer_headings, key=len)
    if title:
        return title
    return max(heading_titles, key=len) if heading_titles else ""


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
    has_resolved_publisher_url = bool(publisher_url and not is_google_news_url(publisher_url))
    has_resolved_canonical_url = bool(canonical_url and not is_google_news_url(canonical_url))
    is_unresolved_google_news = is_google_news_url(url) and not (
        has_resolved_publisher_url or has_resolved_canonical_url
    )
    published_date = record.get("published_date")
    publisher_published_at = record.get("publisher_published_at") or published_date
    portal_published_at = record.get("portal_published_at")
    if is_unresolved_google_news:
        portal_published_at = portal_published_at or publisher_published_at or published_date
        published_date = None
        publisher_published_at = None

    record.update(
        {
            "feed_url": feed_url,
            "canonical_url": canonical_url,
            "publisher_url": publisher_url,
            "portal_urls": portal_urls,
            "publisher_domain": record.get("publisher_domain") or source_domain,
            "published_date": published_date,
            "publisher_published_at": publisher_published_at,
            "portal_published_at": portal_published_at,
            "section": record.get("section"),
            "article_type": record.get("article_type"),
            "authors": list(dict.fromkeys(record.get("authors") or [])),
            "discovered_from": discovered_from,
            "resolved_at": record.get("resolved_at"),
            "body_text": record.get("body_text"),
            "youth_excerpt": record.get("youth_excerpt") or extract_youth_preview_text(record),
            "image_url": normalize_media_url(record.get("image_url"), canonical_url or url),
            "image_source": record.get("image_source"),
            "image_alt": normalize_article_title(record.get("image_alt") or record.get("title")),
            "publisher_icon_url": normalize_media_url(record.get("publisher_icon_url"), source_url or canonical_url or url),
            "publisher_icon_source": record.get("publisher_icon_source"),
            "issue_tags": list(dict.fromkeys(record.get("issue_tags") or [])),
            "topic_tags": list(dict.fromkeys(record.get("topic_tags") or [])),
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


def parse_html_attributes(tag_text: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for attr_match in HTML_ATTR_PATTERN.finditer(tag_text):
        value = attr_match.group(3) if attr_match.group(3) is not None else (attr_match.group(4) or "")
        attrs[attr_match.group(1).lower()] = html.unescape(value).strip()
    return attrs


def extract_meta_content(html_text: str, key: str, attr_name: str = "name") -> str | None:
    attr_name = attr_name.lower()
    key = key.lower()
    for match in re.finditer(r"<meta\b[^>]*>", html_text, re.IGNORECASE | re.DOTALL):
        attrs = parse_html_attributes(match.group(0))
        if attrs.get(attr_name, "").lower() == key and attrs.get("content"):
            return attrs["content"]
    return None


def extract_canonical_link(html_text: str) -> str | None:
    match = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\'](.*?)["\']', html_text, re.IGNORECASE)
    if not match:
        return None
    return html.unescape(match.group(1)).strip()


def _kst_datetime(
    year: str,
    month: str,
    day: str,
    hour: str | None = None,
    minute: str | None = None,
    second: str | None = None,
) -> str:
    parsed = datetime(
        int(year),
        int(month),
        int(day),
        int(hour or 0),
        int(minute or 0),
        int(second or 0),
        tzinfo=timezone(timedelta(hours=9)),
    )
    return parsed.isoformat()


def normalize_published_datetime(value: Any) -> str | None:
    if value is None:
        return None
    normalized = strip_html(str(value))
    normalized = html.unescape(normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip(" \t\r\n[]()")
    if not normalized:
        return None

    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone(timedelta(hours=9)))
        return parsed.isoformat()
    except ValueError:
        pass

    try:
        return parsedate_to_datetime(normalized).isoformat()
    except (TypeError, ValueError, IndexError):
        pass

    korean_match = re.search(
        r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일(?:\s*(\d{1,2})[:시]\s*(\d{1,2})?(?:[:분]\s*(\d{1,2}))?)?",
        normalized,
    )
    if korean_match:
        return _kst_datetime(*korean_match.groups())

    numeric_match = re.search(
        r"(\d{4})[./-](\d{1,2})[./-](\d{1,2})(?:[T\s.]+(\d{1,2}):(\d{2})(?::(\d{2}))?)?",
        normalized,
    )
    if numeric_match:
        return _kst_datetime(*numeric_match.groups())

    return None


def _iter_json_ld_nodes(value: Any) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    if isinstance(value, dict):
        nodes.append(value)
        for nested in value.values():
            nodes.extend(_iter_json_ld_nodes(nested))
    elif isinstance(value, list):
        for item in value:
            nodes.extend(_iter_json_ld_nodes(item))
    return nodes


def _first_normalized_published_value(value: Any) -> str | None:
    if isinstance(value, list):
        for item in value:
            if normalized := _first_normalized_published_value(item):
                return normalized
        return None
    return normalize_published_datetime(value)


def extract_json_ld_published_at(html_text: str) -> str | None:
    pattern = re.compile(
        r'<script[^>]+type=["\'][^"\']*ld\+json[^"\']*["\'][^>]*>(?P<payload>.*?)</script>',
        re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(html_text):
        payload = html.unescape(match.group("payload")).strip()
        payload = re.sub(r"^\s*<!--|-->\s*$", "", payload).strip()
        if not payload:
            continue
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            continue
        for node in _iter_json_ld_nodes(parsed):
            for key in ("datePublished", "dateCreated", "uploadDate"):
                if key in node:
                    if normalized := _first_normalized_published_value(node.get(key)):
                        return normalized
    return None


def extract_time_tag_published_at(html_text: str) -> str | None:
    for match in re.finditer(r"<(?:time|span|div)\b[^>]*>", html_text, re.IGNORECASE | re.DOTALL):
        attrs = parse_html_attributes(match.group(0))
        marker_values = {
            (attrs.get("itemprop") or "").lower(),
            (attrs.get("property") or "").lower(),
            (attrs.get("name") or "").lower(),
        }
        is_time_tag = match.group(0).lower().startswith("<time")
        is_published_marker = bool(marker_values.intersection({"datepublished", "article:published_time"}))
        if not is_time_tag and not is_published_marker:
            continue
        for attr_name in ("datetime", "content", "data-date", "data-published", "title"):
            if normalized := normalize_published_datetime(attrs.get(attr_name)):
                return normalized
    return None


def extract_published_datetime(html_text: str) -> str | None:
    candidates: list[str] = []
    for key, attr_name in PUBLISHED_META_FIELDS:
        if normalized := normalize_published_datetime(extract_meta_content(html_text, key, attr_name)):
            candidates.append(normalized)
    for extractor in (extract_json_ld_published_at, extract_time_tag_published_at):
        if normalized := extractor(html_text):
            candidates.append(normalized)
    for candidate in candidates:
        if has_specific_time(candidate):
            return candidate
    return candidates[0] if candidates else None


def has_specific_time(value: str | None) -> bool:
    if not value:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return any((parsed.hour, parsed.minute, parsed.second, parsed.microsecond))


def should_use_publisher_published_at(current_value: str | None, publisher_value: str | None) -> bool:
    if not publisher_value:
        return False
    if not current_value:
        return True
    if has_specific_time(publisher_value):
        return True
    return not has_specific_time(current_value)


def normalize_excerpt_text(value: Any) -> str:
    if value is None:
        return ""
    text = strip_html(str(value))
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def keyword_excerpt(text: Any, *, keywords: tuple[str, ...] = YOUTH_EXCERPT_KEYWORDS, limit: int = 220) -> str:
    normalized = normalize_excerpt_text(text)
    if not normalized:
        return ""

    lowered = normalized.lower()
    matches = [
        (index, keyword)
        for keyword in keywords
        if keyword and (index := lowered.find(keyword.lower())) >= 0
    ]
    if not matches:
        return ""

    keyword_index, keyword = min(matches, key=lambda item: item[0])
    start = 0
    for position in range(keyword_index - 1, -1, -1):
        if normalized[position] in EXCERPT_BOUNDARY_CHARS:
            start = position + 1
            break

    if keyword_index - start > limit // 2:
        start = max(0, keyword_index - limit // 3)
        while start > 0 and start < keyword_index and not normalized[start - 1].isspace():
            start += 1

    end = len(normalized)
    keyword_end = keyword_index + len(keyword)
    for position in range(keyword_end, len(normalized)):
        if normalized[position] in EXCERPT_BOUNDARY_CHARS:
            end = position + 1
            break

    if end - start < min(80, limit) and end < len(normalized):
        end = min(len(normalized), start + limit)
    if end - start > limit:
        if keyword_index - start > limit // 3:
            start = max(0, keyword_index - limit // 3)
            while start > 0 and start < keyword_index and not normalized[start - 1].isspace():
                start += 1
        end = min(len(normalized), start + limit)

    excerpt = normalized[start:end].strip()
    if not excerpt:
        return ""
    if start > 0:
        excerpt = "..." + excerpt.lstrip(" .,:;")
    if end < len(normalized):
        excerpt = excerpt.rstrip(" .,:;") + "..."
    return excerpt


def extract_youth_preview_text(article: dict[str, Any], *, limit: int = 220) -> str:
    for field in ("lead_text", "body_text", "summary"):
        if excerpt := keyword_excerpt(article.get(field), limit=limit):
            return excerpt
    return ""


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
    title = choose_article_page_title(title, extract_heading_titles(html_text))
    if is_http_error_page_title(title):
        title = None

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
    published_at = extract_published_datetime(html_text)
    image_url = extract_article_image_url(html_text, source_url)
    publisher_icon_url = extract_publisher_icon_url(html_text, source_url)
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
    youth_excerpt = extract_youth_preview_text({"lead_text": description, "body_text": body_text})
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
        "youth_excerpt": youth_excerpt or None,
        "image_url": image_url,
        "image_source": "article_page" if image_url else None,
        "image_alt": title or None,
        "publisher_icon_url": publisher_icon_url,
        "publisher_icon_source": "page_icon" if publisher_icon_url else None,
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
                "youth_excerpt",
                "image_url",
                "image_source",
                "image_alt",
                "publisher_icon_url",
                "publisher_icon_source",
                "region",
            ]:
                if metadata.get(key):
                    if key == "title":
                        cleaned_title = clean_metadata_title(metadata[key], updated)
                        if not is_http_error_page_title(cleaned_title):
                            updated[key] = cleaned_title
                    elif key in {"image_url", "publisher_icon_url"}:
                        if normalized_media_url := normalize_media_url(metadata[key], target_url):
                            updated[key] = normalized_media_url
                    else:
                        updated[key] = metadata[key]
            publisher_published_at = metadata.get("publisher_published_at")
            if should_use_publisher_published_at(updated.get("published_date"), publisher_published_at):
                updated["published_date"] = publisher_published_at
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
    if excerpt := extract_youth_preview_text(updated):
        updated["youth_excerpt"] = excerpt
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

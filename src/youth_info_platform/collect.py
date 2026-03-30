from __future__ import annotations

import base64
import html
import json
import re
import shutil
import subprocess
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urljoin

from .constants import YOUTH_RELATED_KEYWORDS
from .sample_data import SAMPLE_ARTICLES, SAMPLE_VIDEOS


def resolve_command(*candidates: str) -> str:
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise FileNotFoundError(f"command_not_found:{','.join(candidates)}")


def load_source_config(config_path: str) -> list[dict[str, Any]]:
    with open(config_path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload.get("sources", [])


def decode_response_bytes(payload: bytes, header_charset: str | None = None) -> str:
    candidates: list[str] = []

    def add_candidate(value: str | None) -> None:
        if not value:
            return
        normalized = value.strip().strip('"').strip("'")
        if normalized and normalized not in candidates:
            candidates.append(normalized)

    add_candidate(header_charset)
    head = payload[:4096].decode("ascii", errors="ignore")
    meta_match = re.search(r"charset\s*=\s*([A-Za-z0-9_\-]+)", head, re.IGNORECASE)
    if meta_match:
        add_candidate(meta_match.group(1))
    for fallback in ("utf-8", "cp949", "euc-kr"):
        add_candidate(fallback)

    for encoding in candidates:
        try:
            return payload.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return payload.decode("utf-8", errors="ignore")


def fetch_url(url: str, timeout: int = 10) -> str:
    errors: list[Exception] = []
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read()
            charset = response.headers.get_content_charset()
            return decode_response_bytes(payload, charset)
    except Exception as error:
        errors.append(error)

    for fallback in (fetch_url_via_curl, fetch_url_via_powershell):
        try:
            return fallback(url, timeout=timeout)
        except Exception as error:
            errors.append(error)

    raise RuntimeError(f"failed_to_fetch_url:{url}") from errors[-1]


def fetch_url_via_curl(url: str, timeout: int = 10) -> str:
    curl_command = resolve_command("curl", "curl.exe")
    result = subprocess.run(
        [
            curl_command,
            "-L",
            "--max-time",
            str(timeout),
            "-A",
            "Mozilla/5.0",
            url,
        ],
        check=True,
        capture_output=True,
    )
    return decode_response_bytes(result.stdout)


def fetch_url_via_powershell(url: str, timeout: int = 10) -> str:
    powershell_command = resolve_command("pwsh", "powershell", "powershell.exe")
    escaped_url = url.replace("'", "''")
    command = (
        "$ProgressPreference='SilentlyContinue';"
        "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8;"
        "$response = Invoke-WebRequest -UseBasicParsing "
        f"'{escaped_url}' -TimeoutSec {timeout};"
        "$stream = New-Object System.IO.MemoryStream;"
        "$response.RawContentStream.CopyTo($stream);"
        "$result = @{"
        "  contentType = $response.Headers['Content-Type'];"
        "  payload = [Convert]::ToBase64String($stream.ToArray())"
        "};"
        "$result | ConvertTo-Json -Compress"
    )
    result = subprocess.run(
        [powershell_command, "-NoProfile", "-Command", command],
        check=True,
        capture_output=True,
    )
    response_payload = json.loads(result.stdout.decode("utf-8", errors="ignore"))
    raw = base64.b64decode(response_payload["payload"])
    content_type = response_payload.get("contentType") or ""
    charset_match = re.search(r"charset=([A-Za-z0-9_\-]+)", content_type, re.IGNORECASE)
    charset = charset_match.group(1) if charset_match else None
    return decode_response_bytes(raw, charset)


def strip_html(value: str) -> str:
    plain = re.sub(r"<[^>]+>", " ", value or "")
    plain = html.unescape(plain)
    plain = re.sub(r"\s+", " ", plain).strip()
    return plain


def _parse_published(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).isoformat()
    except (TypeError, ValueError, IndexError):
        return value


def parse_feed(feed_text: str, source_name: str, source_kind: str) -> list[dict[str, Any]]:
    root = ET.fromstring(feed_text)
    articles: list[dict[str, Any]] = []
    items = root.findall(".//item")
    if not items:
        items = root.findall(".//{http://www.w3.org/2005/Atom}entry")
    for item in items:
        title = _find_text(item, ["title", "{http://www.w3.org/2005/Atom}title"])
        url = _find_text(item, ["link", "{http://www.w3.org/2005/Atom}link"])
        if not url:
            link_node = item.find("{http://www.w3.org/2005/Atom}link")
            if link_node is not None:
                url = link_node.attrib.get("href")
        publisher = strip_html(
            _find_text(item, ["source", "{http://www.w3.org/2005/Atom}source"]) or ""
        )
        description = _find_text(
            item,
            [
                "description",
                "summary",
                "{http://www.w3.org/2005/Atom}summary",
                "{http://purl.org/rss/1.0/modules/content/}encoded",
            ],
        )
        published = _find_text(
            item,
            ["pubDate", "published", "updated", "{http://www.w3.org/2005/Atom}updated"],
        )
        if not title or not url:
            continue
        cleaned_title = strip_html(title)
        if publisher and cleaned_title.endswith(f" - {publisher}"):
            cleaned_title = cleaned_title[: -(len(publisher) + 3)].strip()
        for suffix in ["> 뉴스", "| 뉴스", "- 뉴스"]:
            if cleaned_title.endswith(suffix):
                cleaned_title = cleaned_title[: -len(suffix)].strip()
        articles.append(
            {
                "title": cleaned_title,
                "url": url.strip(),
                "source": publisher or source_name,
                "source_name": source_name,
                "source_kind": source_kind,
                "published_date": _parse_published(published),
                "lead_text": strip_html(description)[:200],
            }
        )
    return articles


def parse_opm_press_release(page_text: str, base_url: str, source_name: str, source_kind: str) -> list[dict[str, Any]]:
    row_pattern = re.compile(
        r'<tr class="">.*?<a href="(?P<href>\?mode=view&amp;articleNo=\d+[^"]*)" class="c-board-title">\s*(?P<title>.*?)\s*</a>.*?<td>(?P<department>.*?)</td>\s*<td>\s*(?P<date>\d{4}\.\d{2}\.\d{2})',
        re.DOTALL,
    )
    articles: list[dict[str, Any]] = []
    for match in row_pattern.finditer(page_text):
        title = strip_html(match.group("title"))
        href = html.unescape(match.group("href"))
        department = strip_html(match.group("department"))
        published = match.group("date").replace(".", "-")
        articles.append(
            {
                "title": title,
                "url": urljoin(base_url, href),
                "source": source_name,
                "source_kind": source_kind,
                "published_date": f"{published}T00:00:00+09:00",
                "lead_text": department,
            }
        )
    return articles


def parse_korea_withyou_policy_news(
    page_text: str,
    base_url: str,
    source_name: str,
    source_kind: str,
) -> list[dict[str, Any]]:
    pattern = re.compile(
        r'<a href="(?P<href>https?://[^"]*policyNewsView\.do\?newsId=\d+[^"]*)" class="item"[^>]*>.*?<div>\s*<em>(?P<label>.*?)</em>\s*<strong>(?P<title>.*?)</strong>',
        re.DOTALL,
    )
    articles: list[dict[str, Any]] = []
    for match in pattern.finditer(page_text):
        label = strip_html(match.group("label"))
        title = strip_html(match.group("title"))
        url = html.unescape(match.group("href")).replace("#policyNews", "")
        if not title or not url:
            continue
        articles.append(
            {
                "title": title,
                "url": urljoin(base_url, url),
                "source": source_name,
                "source_kind": source_kind,
                "published_date": None,
                "lead_text": label,
            }
        )
    return articles


def parse_opm_detail(detail_text: str) -> str:
    match = re.search(
        r'<div class="board-view-txt board-common-txt">.*?<div class="fr-view">(.*?)</div>\s*</div>',
        detail_text,
        re.DOTALL,
    )
    if not match:
        return ""
    body = strip_html(match.group(1))
    body = re.sub(r"\s+", " ", body).strip()
    return body[:1200]


def parse_korea_policy_detail(detail_text: str) -> dict[str, str | None]:
    description = (
        extract_meta_content(detail_text, "og:description", attr_name="property")
        or extract_meta_content(detail_text, "description", attr_name="name")
        or ""
    )
    if description:
        description = description.split(" - 정책브리핑", 1)[0].strip()
    date_match = re.search(r'"datePublished"\s*:\s*"([^"]+)"', detail_text)
    published_date = date_match.group(1) if date_match else None
    return {
        "lead_text": strip_html(description)[:1200] if description else None,
        "published_date": published_date,
    }


def extract_meta_content(detail_text: str, key: str, attr_name: str = "name") -> str | None:
    pattern = re.compile(
        rf'<meta[^>]+{attr_name}=["\']{re.escape(key)}["\'][^>]+content=["\'](.*?)["\']',
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(detail_text)
    if not match:
        return None
    return html.unescape(match.group(1)).strip()


def enrich_articles_with_detail(articles: list[dict[str, Any]], source: dict[str, Any]) -> list[dict[str, Any]]:
    if not source.get("detail_enrichment"):
        return articles

    detail_parser = source.get("detail_parser") or source.get("parser")
    enriched: list[dict[str, Any]] = []
    for article in articles:
        updated = dict(article)
        try:
            detail_text = fetch_url(article["url"])
            if detail_parser == "opm_press_release":
                detail_body = parse_opm_detail(detail_text)
                if detail_body:
                    updated["lead_text"] = detail_body
            elif detail_parser == "korea_policy_news":
                detail_data = parse_korea_policy_detail(detail_text)
                if detail_data.get("lead_text"):
                    updated["lead_text"] = detail_data["lead_text"]
                if detail_data.get("published_date"):
                    updated["published_date"] = detail_data["published_date"]
        except Exception:
            pass
        enriched.append(updated)
    return enriched


def _find_text(node: ET.Element, tags: list[str]) -> str | None:
    for tag in tags:
        child = node.find(tag)
        if child is not None and child.text:
            return child.text
    return None


def collect_articles(
    sources: list[dict[str, Any]],
    use_sample_data: bool = False,
    fallback_to_sample: bool = False,
) -> list[dict[str, Any]]:
    if use_sample_data:
        return list(SAMPLE_ARTICLES)

    articles: list[dict[str, Any]] = []
    for source in sources:
        if not source.get("enabled", False):
            continue
        try:
            payload = fetch_url(source["url"])
            parser = source.get("parser", "rss")
            if parser == "rss":
                items = parse_feed(payload, source["name"], source.get("kind", "news"))
            elif parser == "opm_press_release":
                items = parse_opm_press_release(
                    payload,
                    source["url"],
                    source["name"],
                    source.get("kind", "news"),
                )
            elif parser == "korea_withyou_policy_news":
                items = parse_korea_withyou_policy_news(
                    payload,
                    source["url"],
                    source["name"],
                    source.get("kind", "news"),
                )
            else:
                items = []
            items = enrich_articles_with_detail(items, source)
            items = apply_source_filters(items, source)
            articles.extend(items[: int(source.get("limit", len(items)))])
        except Exception:
            continue

    if articles:
        return articles
    if fallback_to_sample:
        return list(SAMPLE_ARTICLES)
    return []


def collect_videos(use_sample_data: bool = False) -> list[dict[str, Any]]:
    return list(SAMPLE_VIDEOS)


def resolve_include_keywords(source: dict[str, Any]) -> list[str]:
    include_keywords = list(source.get("include_keywords") or [])
    if source.get("include_youth_related"):
        include_keywords.extend(YOUTH_RELATED_KEYWORDS)
    return list(dict.fromkeys(include_keywords))


def apply_source_filters(items: list[dict[str, Any]], source: dict[str, Any]) -> list[dict[str, Any]]:
    include_keywords = resolve_include_keywords(source)
    exclude_keywords = source.get("exclude_keywords") or []
    if not include_keywords and not exclude_keywords:
        return items

    filtered: list[dict[str, Any]] = []
    for item in items:
        text = f'{item.get("title", "")} {item.get("lead_text", "")}'
        if include_keywords and not any(keyword in text for keyword in include_keywords):
            continue
        if exclude_keywords and any(keyword in text for keyword in exclude_keywords):
            continue
        filtered.append(item)
    return filtered

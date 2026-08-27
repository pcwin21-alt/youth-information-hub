from __future__ import annotations

import base64
import html
import json
import os
import re
import shutil
import subprocess
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup, Tag

from .constants import YOUTH_RELATED_KEYWORDS
from .sample_data import SAMPLE_ARTICLES, SAMPLE_VIDEOS


NAVER_INTERNAL_HOSTS = {
    "",
    "search.naver.com",
    "kin.naver.com",
    "help.naver.com",
    "mkt.naver.com",
    "blog.naver.com",
    "cafe.naver.com",
    "post.naver.com",
    "news.naver.com",
    "n.news.naver.com",
}
GOOGLE_NEWS_HOSTS = {"news.google.com"}
NAVER_IGNORED_TEXTS = {
    "",
    "언론사 선정",
    "Keep에 저장",
    "Keep에 바로가기",
}
ParserFn = Callable[[str, dict[str, Any]], list[dict[str, Any]]]
SOURCE_METADATA_FIELDS = (
    "selection_priority",
    "source_focus",
    "source_origin",
    "publisher_icon_url",
)


def is_google_news_feed_url(url: str | None) -> bool:
    if not url:
        return False
    return urlparse(url).netloc.lower() in GOOGLE_NEWS_HOSTS


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


class SourceAccessError(RuntimeError):
    """A source returned an access wall rather than collection data."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def detect_source_access_issue(payload: str) -> str | None:
    """Classify known soft blocks; this deliberately does not attempt a bypass."""

    normalized = re.sub(r"\s+", " ", payload).lower()
    if any(
        marker in normalized
        for marker in (
            "captcha",
            "recaptcha",
            "access denied",
            "unusual traffic",
            "automated queries",
            "비정상적인 접근",
            "자동화된 요청",
            "접근이 차단",
        )
    ):
        return "blocked"
    if any(
        marker in normalized
        for marker in (
            "로그인이 필요",
            "로그인 후 이용",
            "sign in to continue",
            "login required",
            "authentication required",
        )
    ):
        return "auth_required"
    return None


def require_usable_source_payload(payload: str) -> None:
    if issue := detect_source_access_issue(payload):
        raise SourceAccessError(issue)


def classify_collection_error(error: Exception) -> str:
    if isinstance(error, SourceAccessError):
        return error.code
    if isinstance(error, ValueError) and str(error).startswith("unsupported_parser:"):
        return "unsupported_parser"
    if isinstance(error, (ET.ParseError, json.JSONDecodeError)):
        return "parser_error"
    return "fetch_error"


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
            "--fail",
            "--show-error",
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


def _normalize_feed_media_url(value: str | None, base_url: str | None = None) -> str | None:
    if not value:
        return None
    raw = html.unescape(value).strip().strip("'\"")
    if not raw or raw.lower().startswith(("data:", "javascript:", "mailto:")):
        return None
    resolved = urljoin(base_url or "", raw)
    parsed = urlparse(resolved)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return None
    lowered = resolved.lower()
    if any(token in lowered for token in ("spacer", "blank", "pixel", "tracking", "analytics")):
        return None
    return resolved


def _local_xml_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _extract_feed_image_url(item: ET.Element, article_url: str) -> str | None:
    for node in item.iter():
        local_name = _local_xml_name(node.tag)
        if local_name in {"content", "thumbnail"}:
            medium = (node.attrib.get("medium") or "").lower()
            content_type = (node.attrib.get("type") or "").lower()
            if local_name == "content" and medium and medium != "image" and not content_type.startswith("image/"):
                continue
            if normalized := _normalize_feed_media_url(node.attrib.get("url"), article_url):
                return normalized
        if local_name == "enclosure":
            content_type = (node.attrib.get("type") or "").lower()
            if content_type and not content_type.startswith("image/"):
                continue
            if normalized := _normalize_feed_media_url(node.attrib.get("url"), article_url):
                return normalized

    for node in item.iter():
        if _local_xml_name(node.tag) != "image":
            continue
        if normalized := _normalize_feed_media_url((node.text or "").strip(), article_url):
            return normalized
        image_url = _find_text(node, ["url"])
        if normalized := _normalize_feed_media_url(image_url, article_url):
            return normalized
    return None


def _parse_published(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", normalized):
        return f"{normalized}T00:00:00+09:00"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", normalized):
        return f'{normalized.replace(" ", "T")}+09:00'
    try:
        return parsedate_to_datetime(normalized).isoformat()
    except (TypeError, ValueError, IndexError):
        pass
    try:
        return datetime.fromisoformat(normalized.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return normalized


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
        source_node = item.find("source")
        if source_node is None:
            source_node = item.find("{http://www.w3.org/2005/Atom}source")
        publisher = strip_html(
            _find_text(item, ["source", "{http://www.w3.org/2005/Atom}source"]) or ""
        )
        publisher_homepage_url = None
        if source_node is not None:
            publisher_homepage_url = source_node.attrib.get("url")
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
            [
                "pubDate",
                "published",
                "updated",
                "{http://www.w3.org/2005/Atom}updated",
                "{http://purl.org/dc/elements/1.1/}date",
            ],
        )
        if not title or not url:
            continue
        cleaned_title = strip_html(title)
        if publisher and cleaned_title.endswith(f" - {publisher}"):
            cleaned_title = cleaned_title[: -(len(publisher) + 3)].strip()
        for suffix in ["> 뉴스", "| 뉴스", "- 뉴스"]:
            if cleaned_title.endswith(suffix):
                cleaned_title = cleaned_title[: -len(suffix)].strip()
        article_url = url.strip()
        parsed_published = _parse_published(published)
        is_google_news_item = is_google_news_feed_url(article_url)
        image_url = _extract_feed_image_url(item, article_url)
        article = {
            "title": cleaned_title,
            "url": article_url,
            "source": publisher or source_name,
            "source_name": source_name,
            "source_kind": source_kind,
            "source_url": publisher_homepage_url,
            "published_date": None if is_google_news_item else parsed_published,
            "lead_text": strip_html(description)[:200],
        }
        if image_url:
            article["image_url"] = image_url
            article["image_source"] = "feed_media"
            article["image_alt"] = cleaned_title
        if is_google_news_item:
            article["portal_published_at"] = parsed_published
        articles.append(article)
    return articles


def parse_fsc_press_release(page_text: str, base_url: str, source_name: str, source_kind: str) -> list[dict[str, Any]]:
    item_pattern = re.compile(
        r'<li>\s*<div class="inner">.*?<div class="subject">\s*<a href="(?P<href>/no010101/\d+[^"]*)" title="(?P<title>[^"]+)"[^>]*>.*?</a>\s*</div>.*?<div class="info">\s*<span>담당부서\s*:\s*(?P<department>.*?)</span>.*?</div>.*?<div class="day">(?P<date>\d{4}-\d{2}-\d{2})</div>',
        re.DOTALL,
    )
    articles: list[dict[str, Any]] = []
    for match in item_pattern.finditer(page_text):
        articles.append(
            {
                "title": strip_html(match.group("title")),
                "url": urljoin(base_url, html.unescape(match.group("href"))),
                "source": source_name,
                "source_name": source_name,
                "source_kind": source_kind,
                "source_url": base_url,
                "published_date": f'{match.group("date")}T00:00:00+09:00',
                "lead_text": strip_html(match.group("department")),
            }
        )
    return articles


def parse_mohw_press_release(page_text: str, base_url: str, source_name: str, source_kind: str) -> list[dict[str, Any]]:
    row_pattern = re.compile(
        r'<tr>\s*<td class="m_hidden" data-label="번호">.*?</td>\s*<td class="txt_left" data-label="제목">\s*<a href="(?P<href>/board\.es\?mid=a10503000000&amp;bid=0027&amp;act=view&amp;list_no=\d+[^"]*)" class="txt_title">\s*(?P<title>.*?)</a></td>\s*<td data-label="담당부서">(?P<department>.*?)</td>\s*<td data-label="등록일">(?P<date>\d{4}-\d{2}-\d{2})</td>',
        re.DOTALL,
    )
    articles: list[dict[str, Any]] = []
    for match in row_pattern.finditer(page_text):
        title = re.sub(r"^새글\s*", "", strip_html(match.group("title"))).strip()
        articles.append(
            {
                "title": title,
                "url": urljoin(base_url, html.unescape(match.group("href"))),
                "source": source_name,
                "source_name": source_name,
                "source_kind": source_kind,
                "source_url": base_url,
                "published_date": f'{match.group("date")}T00:00:00+09:00',
                "lead_text": strip_html(match.group("department")),
            }
        )
    return articles


def parse_moe_press_release(page_text: str, base_url: str, source_name: str, source_kind: str) -> list[dict[str, Any]]:
    parsed_url = urlparse(base_url)
    menu_id = parse_qs(parsed_url.query).get("m", ["020402"])[0]
    row_pattern = re.compile(
        r"<tr>\s*<td class=\"no\">.*?</td>\s*<td class=\"title left\">\s*<a href=\"#\" onclick=\"javascript:goView\('(?P<board>\d+)', '(?P<seq>\d+)', '(?P<lev>\d+)', (?P<section>[^,]+), '(?P<status>[A-Z])', '(?P<page>\d+)', '(?P<writer>[A-Z])', '(?P<dept>[^']*)'\);\" title=\"(?P<title>[^\"]+)\">.*?</a>\s*</td>\s*<td>(?P<department>.*?)</td>\s*<td>(?P<date>\d{4}-\d{2}-\d{2})</td>",
        re.DOTALL,
    )
    articles: list[dict[str, Any]] = []
    for match in row_pattern.finditer(page_text):
        detail_url = (
            "/boardCnts/viewRenew.do"
            f'?boardID={match.group("board")}'
            f'&boardSeq={match.group("seq")}'
            f'&lev={match.group("lev")}'
            f'&searchType=null&statusYN={match.group("status")}'
            f'&page={match.group("page")}'
            f"&s=moe&m={menu_id}&opType=N"
        )
        articles.append(
            {
                "title": strip_html(match.group("title")),
                "url": urljoin(base_url, detail_url),
                "source": source_name,
                "source_name": source_name,
                "source_kind": source_kind,
                "source_url": base_url,
                "published_date": f'{match.group("date")}T00:00:00+09:00',
                "lead_text": strip_html(match.group("department")),
            }
        )
    return articles


def parse_molit_board_list(page_text: str, base_url: str, source_name: str, source_kind: str) -> list[dict[str, Any]]:
    row_pattern = re.compile(
        r'<tr>\s*<td class="bd_num">.*?</td>\s*<td class="bd_title">\s*<a href="(?P<href>[^"]*dtl\.jsp[^"]*)" class="[^"]*">\s*(?P<title>.*?)\s*(?:<i>.*?</i>)?\s*</a>\s*</td>\s*<td class="bd_(?:field|category)">(?P<meta>.*?)</td>\s*<td class="bd_date">(?P<date>\d{4}-\d{2}-\d{2})</td>',
        re.DOTALL,
    )
    articles: list[dict[str, Any]] = []
    for match in row_pattern.finditer(page_text):
        title = re.sub(r"^새글\s*", "", strip_html(match.group("title"))).strip()
        articles.append(
            {
                "title": title,
                "url": urljoin(base_url, html.unescape(match.group("href"))),
                "source": source_name,
                "source_name": source_name,
                "source_kind": source_kind,
                "source_url": base_url,
                "published_date": f'{match.group("date")}T00:00:00+09:00',
                "lead_text": strip_html(match.group("meta")),
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
                "source_name": source_name,
                "source_kind": source_kind,
                "source_url": base_url,
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
                "source_name": source_name,
                "source_kind": source_kind,
                "source_url": base_url,
                "published_date": None,
                "lead_text": label,
            }
        )
    return articles


def parse_naver_news_search(
    page_text: str,
    base_url: str,
    source_name: str,
    source_kind: str,
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    soup = BeautifulSoup(page_text, "html.parser")
    reference_time = now or datetime.now().astimezone()
    articles: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for span in soup.find_all("span", class_=lambda value: _class_contains(value, "sds-comps-text-type-headline1")):
        title_anchor = span.find_parent("a", href=True)
        if title_anchor is None:
            continue
        url = html.unescape(title_anchor["href"]).strip()
        if not _is_allowed_external_article_link(url):
            continue
        if url in seen_urls:
            continue

        title = strip_html(span.get_text(" ", strip=True))
        if not title:
            continue

        content_root = title_anchor.parent if isinstance(title_anchor.parent, Tag) else None
        summary_anchor = None
        if content_root is not None:
            summary_anchor = content_root.find("a", attrs={"data-heatmap-target": ".body"}, href=True)
        lead_text = ""
        if summary_anchor is not None:
            lead_text = strip_html(summary_anchor.get_text(" ", strip=True))

        profile_block = _find_naver_profile_block(title_anchor)
        source = source_name
        source_url = None
        published_date = None
        if profile_block is not None:
            source = _extract_naver_publisher(profile_block) or source_name
            source_url = _extract_naver_profile_link(profile_block)
            profile_text = profile_block.get_text(" | ", strip=True)
            published_date = _extract_naver_published_date(profile_text, reference_time)

        articles.append(
            {
                "title": title,
                "url": url,
                "source": source,
                "source_name": source_name,
                "source_kind": source_kind,
                "source_url": source_url or base_url,
                "published_date": published_date,
                "lead_text": lead_text[:400],
            }
        )
        seen_urls.add(url)

    return articles


def parse_openalex_works(payload: str, source: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize OpenAlex work records into the shared article schema.

    OpenAlex is used only as a public scholarly metadata index. The record
    links to the DOI or landing page; it does not copy a paper's abstract or
    full text into the public-site pipeline.
    """

    try:
        document = json.loads(payload)
    except json.JSONDecodeError as error:
        raise ValueError("invalid_openalex_payload") from error

    works = document.get("results") if isinstance(document, dict) else None
    if not isinstance(works, list):
        return []

    allowed_languages = {
        str(value).strip().lower()
        for value in source.get("allowed_languages", [])
        if str(value).strip()
    }
    articles: list[dict[str, Any]] = []
    for work in works:
        if not isinstance(work, dict):
            continue
        language = str(work.get("language") or "").strip().lower()
        if allowed_languages and language and language not in allowed_languages:
            continue
        title = strip_html(str(work.get("display_name") or "")).strip()
        if not title:
            continue
        primary_location = work.get("primary_location") or {}
        if not isinstance(primary_location, dict):
            primary_location = {}
        best_oa_location = work.get("best_oa_location") or {}
        if not isinstance(best_oa_location, dict):
            best_oa_location = {}
        primary_source = primary_location.get("source") or {}
        if not isinstance(primary_source, dict):
            primary_source = {}
        url = (
            str(work.get("doi") or "").strip()
            or str(best_oa_location.get("landing_page_url") or "").strip()
            or str(primary_location.get("landing_page_url") or "").strip()
        )
        if not url:
            continue
        authors = [
            str((authorship.get("author") or {}).get("display_name") or "").strip()
            for authorship in work.get("authorships") or []
            if isinstance(authorship, dict)
        ]
        venue = str(primary_source.get("display_name") or "").strip()
        publication_date = str(work.get("publication_date") or "").strip() or None
        meta = " · ".join(
            part
            for part in [venue, str(work.get("type") or "").replace("_", " ")]
            if part
        )
        articles.append(
            {
                "url": url,
                "title": title,
                "source": venue or source["name"],
                "source_name": source["name"],
                "source_kind": source.get("kind", "research"),
                "source_url": "https://openalex.org/",
                "published_date": publication_date,
                "lead_text": meta[:240],
                "article_type": "research",
                "authors": [author for author in authors if author][:8],
                "openalex_id": work.get("id"),
                "open_access": bool((work.get("open_access") or {}).get("is_oa")),
            }
        )
    return articles


LOCAL_BOARD_ATTACHMENT_PATTERN = re.compile(
    r"\.(?:pdf|hwp|hwpx|doc|docx|xls|xlsx|zip)(?:$|[?#])|file(?:down|download)|atchFileId|attach",
    re.IGNORECASE,
)
LOCAL_BOARD_DATE_PATTERN = re.compile(r"(20\d{2})[.\-/년]\s*(\d{1,2})[.\-/월]\s*(\d{1,2})")


def _selector_values(source: dict[str, Any], key: str) -> list[str]:
    value = source.get(key)
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value if str(item).strip()]


def _first_selected_text(root: Tag, selectors: list[str]) -> str:
    for selector in selectors:
        node = root.select_one(selector)
        if node is not None:
            text = strip_html(node.get_text(" ", strip=True))
            if text:
                return text
    return ""


def _first_selected_anchor(root: Tag, selectors: list[str]) -> Tag | None:
    for selector in selectors:
        node = root.select_one(selector)
        if isinstance(node, Tag):
            if node.name == "a" and node.get("href"):
                return node
            anchor = node.find("a", href=True)
            if isinstance(anchor, Tag):
                return anchor
    if selectors:
        return None
    anchor = root.find("a", href=True)
    return anchor if isinstance(anchor, Tag) else None


def _extract_local_board_date(value: str) -> str | None:
    match = LOCAL_BOARD_DATE_PATTERN.search(value or "")
    if not match:
        return None
    year, month, day = match.groups()
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}T00:00:00+09:00"


def _clean_local_board_title(value: str) -> str:
    title = re.sub(r"^\s*해당\s*없음\s*[.·:：-]*\s*", "", value or "").strip()
    return re.sub(r"\s+", " ", title)


def _matches_allowed_local_domain(url: str, source: dict[str, Any]) -> bool:
    allowed_suffixes = [str(value).lower().strip() for value in (source.get("allowed_domain_suffixes") or []) if value]
    if not allowed_suffixes:
        return True
    hostname = (urlparse(url).hostname or "").lower()
    return any(hostname == suffix or hostname.endswith(f".{suffix}") for suffix in allowed_suffixes)


def _extract_attachment_url(root: Tag, base_url: str) -> str | None:
    for anchor in root.find_all("a", href=True):
        href = html.unescape(str(anchor.get("href") or "")).strip()
        label = strip_html(anchor.get_text(" ", strip=True))
        if LOCAL_BOARD_ATTACHMENT_PATTERN.search(href) or LOCAL_BOARD_ATTACHMENT_PATTERN.search(label):
            return urljoin(base_url, href)
    return None


def _fallback_local_board_roots(soup: BeautifulSoup) -> list[Tag]:
    roots: list[Tag] = []
    seen: set[int] = set()
    for anchor in soup.find_all("a", href=True):
        title = strip_html(anchor.get_text(" ", strip=True))
        if not title:
            continue
        parent = anchor.find_parent(["tr", "li", "article"])
        if parent is None:
            parent = anchor.find_parent(["div", "section"]) or anchor
        if not isinstance(parent, Tag):
            continue
        key = id(parent)
        if key in seen:
            continue
        seen.add(key)
        roots.append(parent)
    return roots


def parse_local_board_search(page_text: str, source: dict[str, Any]) -> list[dict[str, Any]]:
    base_url = str(source.get("url") or "")
    source_name = str(source.get("name") or "")
    source_kind = str(source.get("kind") or "local")
    source_channel = str(source.get("source_channel") or "")
    search_terms = [str(value).strip() for value in (source.get("search_terms") or []) if str(value).strip()]
    if not search_terms:
        search_terms = resolve_include_keywords(source) or ["청년"]

    soup = BeautifulSoup(page_text, "html.parser")
    item_selectors = _selector_values(source, "item_selector")
    title_selectors = _selector_values(source, "title_selector") or ["a"]
    link_selectors = _selector_values(source, "link_selector") or title_selectors
    date_selectors = _selector_values(source, "date_selector")
    summary_selectors = _selector_values(source, "summary_selector")

    roots: list[Tag] = []
    for selector in item_selectors:
        roots.extend(node for node in soup.select(selector) if isinstance(node, Tag))
    if not roots:
        roots = _fallback_local_board_roots(soup)

    articles: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for root in roots:
        anchor = _first_selected_anchor(root, link_selectors)
        if anchor is None:
            continue
        href = html.unescape(str(anchor.get("href") or "")).strip()
        if href.lower().startswith("javascript:"):
            link_pattern = str(source.get("javascript_link_pattern") or "")
            detail_template = str(source.get("detail_url_template") or "")
            match = re.search(link_pattern, href) if link_pattern and detail_template else None
            if match:
                href = detail_template.format(*match.groups(), **match.groupdict())
        if not href or href.lower().startswith(("javascript:", "mailto:", "#")):
            continue
        title = _clean_local_board_title(
            _first_selected_text(root, title_selectors) or strip_html(anchor.get_text(" ", strip=True))
        )
        title = re.sub(r"^\s*(?:새글|new|첨부파일)\s*", "", title, flags=re.IGNORECASE).strip()
        if not title or title in {"청년포털", "홈", "메인", "더보기"}:
            continue

        item_text = strip_html(root.get_text(" ", strip=True))
        summary = _first_selected_text(root, summary_selectors) or item_text
        matched_terms = [term for term in search_terms if term in f"{title} {summary}"]
        if search_terms and not matched_terms:
            continue

        article_url = urljoin(base_url, href)
        if not _matches_allowed_local_domain(article_url, source):
            continue
        if article_url in seen_urls:
            continue
        seen_urls.add(article_url)

        article: dict[str, Any] = {
            "title": title,
            "url": article_url,
            "source": source_name,
            "source_name": source_name,
            "source_kind": source_kind,
            "source_url": base_url,
            "published_date": _extract_local_board_date(
                _first_selected_text(root, date_selectors) if date_selectors else item_text
            ),
            "lead_text": summary[:400],
            "region": source.get("region_name") or "",
            "region_id": source.get("region_id"),
            "region_name": source.get("region_name"),
            "source_channel": source_channel,
            "search_terms": matched_terms,
        }
        if source_kind == "official":
            article["is_official_source"] = True
            article["policy_authority"] = str(source.get("policy_authority") or source_name)
            article["publisher_url"] = article_url
        attachment_url = _extract_attachment_url(root, base_url)
        if attachment_url:
            article["attachment_url"] = attachment_url
            article["original_document_url"] = attachment_url
        articles.append(article)

    return articles


def parse_korea_press_release_list(page_text: str, source: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse the Policy Briefing press-release search result.

    Policy Briefing is the stable cross-ministry index. Individual ministry
    boards remain useful fallbacks, but this collector prevents coverage gaps
    when a ministry changes its own board markup.
    """
    base_url = str(source.get("url") or "https://www.korea.kr/briefing/pressReleaseList.do")
    source_name = str(source.get("name") or "정책브리핑 정부부처 보도자료")
    source_kind = str(source.get("kind") or "official")
    soup = BeautifulSoup(page_text, "html.parser")
    articles: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for anchor in soup.select('a[href*="/briefing/pressReleaseView.do"]'):
        href = html.unescape(str(anchor.get("href") or "")).strip()
        title_node = anchor.select_one(".text > strong, strong")
        title = strip_html(title_node.get_text(" ", strip=True) if title_node else "")
        if not href or not title:
            continue
        article_url = urljoin(base_url, href)
        if article_url in seen_urls:
            continue
        seen_urls.add(article_url)

        lead_node = anchor.select_one(".text > .lead, .lead")
        source_nodes = anchor.select(".text > .source > span, .source > span")
        published_date = _extract_local_board_date(
            source_nodes[0].get_text(" ", strip=True) if source_nodes else anchor.get_text(" ", strip=True)
        )
        authority = (
            strip_html(source_nodes[-1].get_text(" ", strip=True))
            if len(source_nodes) >= 2
            else source_name
        )
        lead_text = strip_html(lead_node.get_text(" ", strip=True)) if lead_node else ""
        articles.append(
            {
                "title": title,
                "url": article_url,
                "source": authority,
                "source_name": source_name,
                "source_kind": source_kind,
                "source_url": base_url,
                "published_date": published_date,
                "lead_text": lead_text[:1200],
                "policy_authority": authority,
                "source_channel": "press_release",
                "is_official_source": True,
                "region": "전국",
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
    detail_limit = int(source.get("detail_limit", len(articles)))
    enriched: list[dict[str, Any]] = []
    for index, article in enumerate(articles):
        updated = dict(article)
        if index < detail_limit:
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


def _class_contains(value: Any, target: str) -> bool:
    if not value:
        return False
    if isinstance(value, str):
        tokens = value.split()
    else:
        tokens = list(value)
    return target in tokens


def _is_allowed_external_article_link(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = parsed.netloc.lower()
    if host in NAVER_INTERNAL_HOSTS:
        return False
    return True


def _find_naver_profile_block(title_anchor: Tag) -> Tag | None:
    current: Tag | None = title_anchor
    for _ in range(8):
        if current is None:
            break
        current = current.parent if isinstance(current.parent, Tag) else None
        if current is None:
            break
        profile_block = current.find("div", attrs={"data-sds-comp": "Profile"})
        if profile_block is not None:
            return profile_block
    return None


def _extract_naver_profile_link(profile_block: Tag) -> str | None:
    profile_anchor = profile_block.find("a", attrs={"data-heatmap-target": ".prof"}, href=True)
    if profile_anchor is None:
        return None
    href = html.unescape(profile_anchor["href"]).strip()
    return href or None


def _extract_naver_publisher(profile_block: Tag) -> str | None:
    profile_anchor = profile_block.find("a", attrs={"data-heatmap-target": ".prof"}, href=True)
    if profile_anchor is not None:
        publisher = strip_html(profile_anchor.get_text(" ", strip=True))
        if publisher:
            return publisher

    for token in (strip_html(text) for text in profile_block.stripped_strings):
        if token in NAVER_IGNORED_TEXTS:
            continue
        if _looks_like_published_token(token):
            continue
        return token
    return None


def _looks_like_published_token(value: str) -> bool:
    return any(
        re.search(pattern, value)
        for pattern in (
            r"\d+\s*분 전",
            r"\d+\s*시간 전",
            r"\d+\s*일 전",
            r"\d{4}[.-]\d{2}[.-]\d{2}",
        )
    )


def _extract_naver_published_date(profile_text: str, reference_time: datetime) -> str | None:
    absolute_dot_match = re.search(r"(\d{4})\.(\d{2})\.(\d{2})\.?", profile_text)
    if absolute_dot_match:
        year, month, day = absolute_dot_match.groups()
        return f"{year}-{month}-{day}T00:00:00+09:00"

    absolute_dash_match = re.search(r"(\d{4})-(\d{2})-(\d{2})", profile_text)
    if absolute_dash_match:
        year, month, day = absolute_dash_match.groups()
        return f"{year}-{month}-{day}T00:00:00+09:00"

    relative_match = re.search(r"(\d+)\s*(분|시간|일)\s*전", profile_text)
    if not relative_match:
        return None

    amount = int(relative_match.group(1))
    unit = relative_match.group(2)
    if unit == "분":
        published_at = reference_time - timedelta(minutes=amount)
    elif unit == "시간":
        published_at = reference_time - timedelta(hours=amount)
    else:
        published_at = reference_time - timedelta(days=amount)
    return published_at.isoformat()


def _parse_rss_payload(payload: str, source: dict[str, Any]) -> list[dict[str, Any]]:
    return parse_feed(payload, source["name"], source.get("kind", "news"))


def _parse_fsc_payload(payload: str, source: dict[str, Any]) -> list[dict[str, Any]]:
    return parse_fsc_press_release(payload, source["url"], source["name"], source.get("kind", "news"))


def _parse_mohw_payload(payload: str, source: dict[str, Any]) -> list[dict[str, Any]]:
    return parse_mohw_press_release(payload, source["url"], source["name"], source.get("kind", "news"))


def _parse_moe_payload(payload: str, source: dict[str, Any]) -> list[dict[str, Any]]:
    return parse_moe_press_release(payload, source["url"], source["name"], source.get("kind", "news"))


def _parse_molit_payload(payload: str, source: dict[str, Any]) -> list[dict[str, Any]]:
    return parse_molit_board_list(payload, source["url"], source["name"], source.get("kind", "news"))


def _parse_opm_payload(payload: str, source: dict[str, Any]) -> list[dict[str, Any]]:
    return parse_opm_press_release(payload, source["url"], source["name"], source.get("kind", "news"))


def _parse_korea_withyou_payload(payload: str, source: dict[str, Any]) -> list[dict[str, Any]]:
    return parse_korea_withyou_policy_news(payload, source["url"], source["name"], source.get("kind", "news"))


def _parse_naver_payload(payload: str, source: dict[str, Any]) -> list[dict[str, Any]]:
    return parse_naver_news_search(payload, source["url"], source["name"], source.get("kind", "news"))


def _parse_openalex_payload(payload: str, source: dict[str, Any]) -> list[dict[str, Any]]:
    return parse_openalex_works(payload, source)


def _parse_local_board_payload(payload: str, source: dict[str, Any]) -> list[dict[str, Any]]:
    return parse_local_board_search(payload, source)


def _parse_korea_press_release_payload(payload: str, source: dict[str, Any]) -> list[dict[str, Any]]:
    return parse_korea_press_release_list(payload, source)


PARSER_REGISTRY: dict[str, ParserFn] = {
    "rss": _parse_rss_payload,
    "fsc_press_release": _parse_fsc_payload,
    "mohw_press_release": _parse_mohw_payload,
    "moe_press_release": _parse_moe_payload,
    "molit_board_list": _parse_molit_payload,
    "opm_press_release": _parse_opm_payload,
    "korea_withyou_policy_news": _parse_korea_withyou_payload,
    "naver_news_search": _parse_naver_payload,
    "openalex_works": _parse_openalex_payload,
    "local_board_search": _parse_local_board_payload,
    "korea_press_release_list": _parse_korea_press_release_payload,
}


def get_source_parser(parser_name: str) -> ParserFn | None:
    return PARSER_REGISTRY.get(parser_name)


def parse_source_payload(payload: str, source: dict[str, Any]) -> list[dict[str, Any]]:
    parser_name = str(source.get("parser") or "rss")
    parser = get_source_parser(parser_name)
    if parser is None:
        raise ValueError(f"unsupported_parser:{parser_name}")
    return parser(payload, source)


def build_paginated_source_url(base_url: str, *, start: int) -> str:
    parsed = urlparse(base_url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    query["start"] = [str(start)]
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))


def fetch_source_items(source: dict[str, Any]) -> list[dict[str, Any]]:
    parser_name = str(source.get("parser") or "rss")
    if parser_name == "naver_news_search":
        return fetch_naver_news_items(source)

    payload = fetch_url(source["url"])
    require_usable_source_payload(payload)
    items = parse_source_payload(payload, source)
    return enrich_articles_with_detail(items, source)


def fetch_naver_news_items(source: dict[str, Any]) -> list[dict[str, Any]]:
    limit = int(source.get("limit", 10))
    collected: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for start in range(1, limit + 1, 10):
        page_url = build_paginated_source_url(source["url"], start=start)
        payload = fetch_url(page_url)
        require_usable_source_payload(payload)
        page_source = {**source, "url": page_url}
        page_items = parse_source_payload(payload, page_source)
        if not page_items:
            break

        for item in page_items:
            url = item.get("url") or ""
            if not url or url in seen_urls:
                continue
            collected.append(item)
            seen_urls.add(url)
            if len(collected) >= limit:
                return collected

        if len(page_items) < 10:
            break

    return collected


def attach_source_metadata(items: list[dict[str, Any]], source: dict[str, Any]) -> list[dict[str, Any]]:
    metadata = {field: source[field] for field in SOURCE_METADATA_FIELDS if field in source}
    if not metadata:
        return items
    return [{**item, **metadata} for item in items]


def collect_articles_with_manifest(
    sources: list[dict[str, Any]],
    use_sample_data: bool = False,
    fallback_to_sample: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if use_sample_data:
        articles = list(SAMPLE_ARTICLES)
        return articles, {
            "generated_at": datetime.now().astimezone().isoformat(),
            "state": "sample",
            "source_count": 0,
            "successful_sources": 0,
            "failed_sources": 0,
            "sources": [],
        }

    articles: list[dict[str, Any]] = []
    source_manifest: list[dict[str, Any]] = []
    for source in sources:
        if not source.get("enabled", False):
            source_manifest.append(
                {
                    "name": source.get("name", "unnamed_source"),
                    "kind": source.get("kind"),
                    "parser": source.get("parser"),
                    "source_url": source.get("url"),
                    "status": "disabled",
                    "fetched_items": 0,
                    "filtered_items": 0,
                    "collected_items": 0,
                }
            )
            continue
        try:
            items = fetch_source_items(source)
            items = attach_source_metadata(items, source)
            filtered_items = apply_source_filters(items, source)
            selected_items = filtered_items[: int(source.get("limit", len(filtered_items)))]
            articles.extend(selected_items)
            source_manifest.append(
                {
                    "name": source.get("name", "unnamed_source"),
                    "kind": source.get("kind"),
                    "parser": source.get("parser"),
                    "source_url": source.get("url"),
                    "status": "ok" if selected_items else "empty_result",
                    "fetched_items": len(items),
                    "filtered_items": len(filtered_items),
                    "collected_items": len(selected_items),
                }
            )
        except Exception as error:
            source_manifest.append(
                {
                    "name": source.get("name", "unnamed_source"),
                    "kind": source.get("kind"),
                    "parser": source.get("parser"),
                    "source_url": source.get("url"),
                    "status": classify_collection_error(error),
                    "fetched_items": 0,
                    "filtered_items": 0,
                    "collected_items": 0,
                    "error_type": error.__class__.__name__,
                }
            )
            continue

    manifest = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "state": "completed" if articles else "empty",
        "source_count": sum(1 for source in sources if source.get("enabled", False)),
        "successful_sources": sum(
            1 for entry in source_manifest if entry["status"] in {"ok", "empty_result"}
        ),
        "failed_sources": sum(
            1
            for entry in source_manifest
            if entry["status"] not in {"ok", "empty_result", "disabled"}
        ),
        "sources": source_manifest,
    }
    if articles:
        return articles, manifest
    if fallback_to_sample:
        return list(SAMPLE_ARTICLES), {**manifest, "state": "fallback_sample"}
    return [], manifest


def collect_articles(
    sources: list[dict[str, Any]],
    use_sample_data: bool = False,
    fallback_to_sample: bool = False,
) -> list[dict[str, Any]]:
    articles, _manifest = collect_articles_with_manifest(
        sources,
        use_sample_data=use_sample_data,
        fallback_to_sample=fallback_to_sample,
    )
    return articles


def load_youtube_source_config(config_path: str | None = None) -> dict[str, Any]:
    default = {
        "keywords": [],
        "channels": [],
        "max_results_per_keyword": 8,
        "lookback_days": 14,
        "region_code": "KR",
        "language": "ko",
    }
    if not config_path:
        return default
    try:
        with open(config_path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return default
    if not isinstance(payload, dict):
        return default
    return {**default, **payload}


def _youtube_api_json(url: str) -> dict[str, Any]:
    payload = json.loads(fetch_url(url, timeout=15))
    if not isinstance(payload, dict):
        raise RuntimeError("youtube_api_response_is_not_object")
    return payload


def _youtube_video_from_api(item: dict[str, Any], keyword: str) -> dict[str, Any] | None:
    identifier = item.get("id") or {}
    snippet = item.get("snippet") or {}
    if not isinstance(identifier, dict) or not isinstance(snippet, dict):
        return None
    video_id = str(identifier.get("videoId") or "").strip()
    title = strip_html(str(snippet.get("title") or ""))
    if not video_id or not title:
        return None
    thumbnails = snippet.get("thumbnails") or {}
    image = thumbnails.get("medium") or thumbnails.get("default") or {}
    return {
        "title": title,
        "video_id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "channel": strip_html(str(snippet.get("channelTitle") or "")),
        "channel_id": str(snippet.get("channelId") or "").strip(),
        "published_date": _parse_published(str(snippet.get("publishedAt") or "")),
        "description": strip_html(str(snippet.get("description") or "")),
        "thumbnail_url": str(image.get("url") or "").strip() if isinstance(image, dict) else "",
        "collection_mode": "youtube_api_search",
        "matched_keywords": [keyword],
    }


def _youtube_videos_from_channel_feed(channel: dict[str, Any]) -> list[dict[str, Any]]:
    channel_id = str(channel.get("channel_id") or "").strip()
    if not channel_id:
        return []
    root = ET.fromstring(fetch_url(f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}", timeout=15))
    atom = "{http://www.w3.org/2005/Atom}"
    yt = "{http://www.youtube.com/xml/schemas/2015}"
    media = "{http://search.yahoo.com/mrss/}"
    result: list[dict[str, Any]] = []
    for entry in root.findall(f"{atom}entry"):
        video_id = (entry.findtext(f"{yt}videoId") or "").strip()
        title = strip_html(entry.findtext(f"{atom}title") or "")
        if not video_id or not title:
            continue
        author = entry.find(f"{atom}author")
        channel_name = (author.findtext(f"{atom}name") if author is not None else "") or channel.get("label") or ""
        group = entry.find(f"{media}group")
        description = group.findtext(f"{media}description") if group is not None else ""
        thumbnail = group.find(f"{media}thumbnail") if group is not None else None
        result.append(
            {
                "title": title,
                "video_id": video_id,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "channel": strip_html(str(channel_name)),
                "channel_id": channel_id,
                "published_date": _parse_published(entry.findtext(f"{atom}published") or ""),
                "description": strip_html(description or ""),
                "thumbnail_url": (thumbnail.attrib.get("url") if thumbnail is not None else "") or "",
                "collection_mode": "channel_rss",
                "matched_keywords": [str(tag) for tag in (channel.get("topic_tags") or []) if str(tag).strip()],
            }
        )
    return result


def collect_videos_with_status(
    *,
    use_sample_data: bool = False,
    config_path: str | None = None,
    api_key: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if use_sample_data:
        sample_videos = [{**video, "collection_mode": "sample", "matched_keywords": ["샘플"]} for video in SAMPLE_VIDEOS]
        return sample_videos, {
            "state": "sample",
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "search_video_count": 0,
            "rss_video_count": len(sample_videos),
            "message": "샘플 영상으로 화면을 확인하고 있습니다.",
        }

    config = load_youtube_source_config(config_path)
    key = (api_key or os.getenv("YOUTUBE_API_KEY") or "").strip()
    videos: list[dict[str, Any]] = []
    search_video_count = 0
    rss_video_count = 0
    errors: list[str] = []

    if key:
        max_results = max(1, min(int(config.get("max_results_per_keyword") or 8), 25))
        lookback_days = max(1, min(int(config.get("lookback_days") or 14), 90))
        published_after = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        for keyword in [str(value).strip() for value in (config.get("keywords") or []) if str(value).strip()]:
            params = urlencode(
                {
                    "part": "snippet",
                    "type": "video",
                    "order": "date",
                    "maxResults": max_results,
                    "q": keyword,
                    "relevanceLanguage": str(config.get("language") or "ko"),
                    "regionCode": str(config.get("region_code") or "KR"),
                    "publishedAfter": published_after,
                    "key": key,
                }
            )
            try:
                payload = _youtube_api_json(f"https://www.googleapis.com/youtube/v3/search?{params}")
                for item in payload.get("items", []):
                    if isinstance(item, dict) and (video := _youtube_video_from_api(item, keyword)):
                        videos.append(video)
                        search_video_count += 1
            except Exception:
                errors.append("YouTube API 검색")

    for channel in config.get("channels") or []:
        if not isinstance(channel, dict):
            continue
        try:
            channel_videos = _youtube_videos_from_channel_feed(channel)
            videos.extend(channel_videos)
            rss_video_count += len(channel_videos)
        except Exception:
            errors.append("채널 RSS")

    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for video in videos:
        key_id = str(video.get("video_id") or video.get("url") or "")
        if not key_id or key_id in seen:
            continue
        seen.add(key_id)
        deduped.append(video)

    if deduped:
        state = "connected"
        message = "유튜브에서 가져온 영상입니다. 영상마다 수집 방식을 표시합니다."
    elif not key and not any(isinstance(channel, dict) and channel.get("channel_id") for channel in config.get("channels") or []):
        state = "not_connected"
        message = "YouTube API 키 또는 채널 RSS 목록을 연결하면 영상이 표시됩니다."
    elif errors:
        state = "partial_failure"
        message = "일부 유튜브 수집을 완료하지 못했습니다. 다음 수집에서 다시 확인합니다."
    else:
        state = "no_results"
        message = "현재 설정한 검색어와 채널에서 표시할 영상이 없습니다."
    return deduped, {
        "state": state,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "search_video_count": search_video_count,
        "rss_video_count": rss_video_count,
        "message": message,
    }


def collect_videos(use_sample_data: bool = False) -> list[dict[str, Any]]:
    videos, _status = collect_videos_with_status(use_sample_data=use_sample_data)
    return videos


def resolve_include_keywords(source: dict[str, Any]) -> list[str]:
    include_keywords = list(source.get("include_keywords") or [])
    if source.get("include_youth_related"):
        include_keywords.extend(YOUTH_RELATED_KEYWORDS)
    return list(dict.fromkeys(include_keywords))


def extract_item_domain(item: dict[str, Any]) -> str:
    candidate = (item.get("url") or "").strip()
    if not candidate:
        return ""
    return urlparse(candidate).netloc.lower()


def matches_domain_suffix(domain: str, suffix: str) -> bool:
    normalized_domain = domain.lower().lstrip(".")
    normalized_suffix = suffix.lower().lstrip(".")
    return normalized_domain == normalized_suffix or normalized_domain.endswith(f".{normalized_suffix}")


def normalize_publisher_name(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip()).casefold()


def apply_source_filters(items: list[dict[str, Any]], source: dict[str, Any]) -> list[dict[str, Any]]:
    include_keywords = resolve_include_keywords(source)
    required_keywords_any = list(source.get("required_keywords_any") or [])
    exclude_keywords = list(source.get("exclude_keywords") or [])
    allowed_domain_suffixes = [suffix.lower() for suffix in (source.get("allowed_domain_suffixes") or [])]
    blocked_domain_suffixes = [suffix.lower() for suffix in (source.get("blocked_domain_suffixes") or [])]
    allowed_publishers = {normalize_publisher_name(name) for name in (source.get("allowed_publishers") or [])}
    blocked_publishers = {normalize_publisher_name(name) for name in (source.get("blocked_publishers") or [])}

    filtered: list[dict[str, Any]] = []
    for item in items:
        domain = extract_item_domain(item)
        publisher = normalize_publisher_name(item.get("source") or item.get("source_name"))

        if allowed_domain_suffixes and not any(matches_domain_suffix(domain, suffix) for suffix in allowed_domain_suffixes):
            continue
        if blocked_domain_suffixes and any(matches_domain_suffix(domain, suffix) for suffix in blocked_domain_suffixes):
            continue
        if allowed_publishers and publisher not in allowed_publishers:
            continue
        if blocked_publishers and publisher in blocked_publishers:
            continue

        text = " ".join(str(item.get(field) or "") for field in ("title", "lead_text", "source"))
        if required_keywords_any and not any(keyword in text for keyword in required_keywords_any):
            continue
        if include_keywords and not any(keyword in text for keyword in include_keywords):
            continue
        if exclude_keywords and any(keyword in text for keyword in exclude_keywords):
            continue
        filtered.append(item)
    return filtered

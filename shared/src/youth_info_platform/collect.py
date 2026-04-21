from __future__ import annotations

import base64
import html
import json
import re
import shutil
import subprocess
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
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
NAVER_IGNORED_TEXTS = {
    "",
    "언론사 선정",
    "Keep에 저장",
    "Keep에 바로가기",
}
ParserFn = Callable[[str, dict[str, Any]], list[dict[str, Any]]]


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
        source_node = item.find("source") or item.find("{http://www.w3.org/2005/Atom}source")
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
        articles.append(
            {
                "title": cleaned_title,
                "url": url.strip(),
                "source": publisher or source_name,
                "source_name": source_name,
                "source_kind": source_kind,
                "source_url": publisher_homepage_url,
                "published_date": _parse_published(published),
                "lead_text": strip_html(description)[:200],
            }
        )
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


PARSER_REGISTRY: dict[str, ParserFn] = {
    "rss": _parse_rss_payload,
    "fsc_press_release": _parse_fsc_payload,
    "mohw_press_release": _parse_mohw_payload,
    "moe_press_release": _parse_moe_payload,
    "molit_board_list": _parse_molit_payload,
    "opm_press_release": _parse_opm_payload,
    "korea_withyou_policy_news": _parse_korea_withyou_payload,
    "naver_news_search": _parse_naver_payload,
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
    items = parse_source_payload(payload, source)
    return enrich_articles_with_detail(items, source)


def fetch_naver_news_items(source: dict[str, Any]) -> list[dict[str, Any]]:
    limit = int(source.get("limit", 10))
    collected: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for start in range(1, limit + 1, 10):
        page_url = build_paginated_source_url(source["url"], start=start)
        payload = fetch_url(page_url)
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
            items = fetch_source_items(source)
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
        if include_keywords and not any(keyword in text for keyword in include_keywords):
            continue
        if exclude_keywords and any(keyword in text for keyword in exclude_keywords):
            continue
        filtered.append(item)
    return filtered

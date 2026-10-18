"""Snapshot public portal results and compare them without changing production data.

Naver is sampled in recency order; Google RSS is a bounded relevance sample,
not a claim about all portal results. Access walls remain unmeasurable.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import re
import subprocess
import types
from urllib.parse import urlencode, parse_qs, urlparse

from _bootstrap import PUBLIC_CONTENT_ROOT
from bs4 import BeautifulSoup
from youth_info_platform.collect import (
    detect_source_access_issue, fetch_url, parse_feed,
    parse_naver_news_search, apply_source_filters, load_source_config,
    naver_continuation_url,
)
from youth_info_platform.article_metadata import normalize_tracking_url, normalize_article_title
from youth_info_platform.publisher_names import article_publisher_name
from youth_info_platform.curation import deduplicate_and_filter, classify_articles

SEOUL = timezone(timedelta(hours=9))


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def load_articles(path):
    value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    return value.get("articles", []) if isinstance(value, dict) else value


def clean_text(node):
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True).replace("새 창 열림", "")).strip()


def naver_reference(payload):
    """Independent observed DOM contract, including current accessible labels."""
    if payload.lstrip().startswith("{"):
        data = json.loads(payload)
        payload = "\n".join(part.get("html", "") for part in data.get("collection", []))
    soup = BeautifulSoup(payload, "html.parser")
    found = []
    seen = set()
    for anchor in soup.select('a[data-heatmap-target=".tit"][href]'):
        url = anchor["href"]
        if url in seen or not url.startswith(("http://", "https://")):
            continue
        seen.add(url)
        parent = anchor
        profile = None
        for _ in range(8):
            parent = parent.parent
            if parent is None:
                break
            profile = parent.select_one('[data-sds-comp="Profile"]')
            if profile is not None:
                break
        publisher = ""
        if profile:
            names = [clean_text(a) for a in profile.select('a[data-heatmap-target=".prof"]')]
            publisher = next((name for name in names if name), "")
        found.append({"title": clean_text(anchor), "url": url, "source": publisher})
    return found


def article_urls(item):
    values = [item.get(key) for key in ("url", "canonical_url", "publisher_url", "feed_url")]
    values.extend(item.get("portal_urls") or [])
    return {normalize_tracking_url(url) for url in values if isinstance(url, str) and url}


def article_index(pool):
    urls, titles = set(), set()
    for item in pool:
        urls.update(article_urls(item))
        title = normalize_article_title(item.get("title") or "")
        publisher = article_publisher_name(item)
        day = article_day(item)
        if title and publisher and day:
            titles.add((title, publisher, day))
    return urls, titles


def match_article(item, index):
    urls, titles = index
    if article_urls(item) & urls:
        return "url"
    key = (normalize_article_title(item.get("title") or ""), article_publisher_name(item), article_day(item))
    if all(key) and key in titles:
        return "title_publisher_day"
    return None


def article_day(item):
    value = next((item.get(key) for key in ("publisher_published_at", "published_date", "portal_published_at") if item.get(key)), None)
    try:
        date = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if date.tzinfo is None:
            date = date.replace(tzinfo=SEOUL)
        return date.astimezone(SEOUL).date().isoformat()
    except (ValueError, TypeError):
        return None


def source_query(source):
    query = parse_qs(urlparse(source.get("url", "")).query)
    value = (query.get("query") or query.get("q") or [""])[0]
    return re.sub(r"\s+when:\S+", "", value).strip()


def analyse(snapshot_dir, archive, raw=None, sources=None):
    pages = json.loads((snapshot_dir / "snapshots.json").read_text(encoding="utf-8"))
    archive_payload = json.loads(Path(archive).read_text(encoding="utf-8-sig"))
    archive_items = archive_payload.get("articles", []) if isinstance(archive_payload, dict) else archive_payload
    archive_generated_at = archive_payload.get("generated_at") if isinstance(archive_payload, dict) else None
    raw_items = load_articles(raw) if raw else []
    archive_index = article_index(archive_items)
    raw_index = article_index(raw_items)
    results = []
    candidates = []
    configured_replay = []
    for page in pages:
        result = {**page}
        if not page.get("path"):
            results.append(result)
            continue
        payload = (snapshot_dir / page["path"]).read_text(encoding="utf-8")
        issue = detect_source_access_issue(payload)
        if page["portal"] == "naver":
            reference = naver_reference(payload)
            parsed = parse_naver_news_search(payload, page["url"], "포털 대조 네이버", "news", now=datetime.fromisoformat(page["observed_at"]))
        elif page["portal"] == "google":
            reference = parsed = parse_feed(payload, "포털 대조 구글", "news")
        else:
            # A blocked Daum page is retained, never replaced by another portal.
            reference = parsed = []
        result.update({"access_issue": issue, "reference_count": len(reference),
                       "parser_count": len(parsed), "collector_accepted_count": 0 if issue else len(parsed)})
        entries = []
        for item in reference:
            archive_match = match_article(item, archive_index)
            raw_match = match_article(item, raw_index) if raw else None
            entries.append({**item, "archive_match": archive_match, "raw_match": raw_match})
        result["entries"] = entries
        result["archive_matches"] = sum(bool(entry["archive_match"]) for entry in entries)
        result["bad_publisher_labels"] = sum(item.get("source") in {"새 창 열림", ""} for item in parsed)
        results.append(result)
        if not issue:
            candidates.extend(parsed)
        # Reproduce the configured route's keyword and total-limit behavior,
        # separate from archive overlap and from all other collection routes.
        page["parsed"] = parsed if not issue else []
    for source in sources or []:
        portal = "naver" if source.get("parser") == "naver_news_search" else "google" if "news.google.com/" in source.get("url", "") else None
        if not source.get("enabled") or not portal:
            continue
        replay_items = []
        for page in pages:
            if page["portal"] == portal and page["query"] == source_query(source):
                replay_items.extend(page.get("parsed", []))
        configured_replay.extend(apply_source_filters(replay_items, source)[:source.get("limit", len(replay_items))])
    route_urls = {item["url"] for item in configured_replay}
    for page in results:
        for entry in page.get("entries", []):
            entry["configured_route_match"] = entry["url"] in route_urls
        page["configured_route_matches"] = sum(entry["configured_route_match"] for entry in page.get("entries", []))
    unique = {}
    for article in candidates:
        unique.setdefault(article["url"], article)
    replay_unique = {article["url"]: article for article in configured_replay}
    filtered = deduplicate_and_filter(list(replay_unique.values()))
    classified = classify_articles(filtered)
    public_items = [item for item in classified if item.get("is_public_interest_article")]
    public_index = article_index(public_items)
    classified_index = article_index(classified)
    for page in results:
        for entry in page.get("entries", []):
            entry["classification_match"] = match_article(entry, classified_index)
            entry["public_candidate_match"] = match_article(entry, public_index)
            date = entry.get("published_date") or entry.get("portal_published_at")
            entry["after_archive_snapshot"] = (
                datetime.fromisoformat(date) > datetime.fromisoformat(archive_generated_at)
                if date and archive_generated_at else None
            )
    report = {"checked_at": datetime.now(SEOUL).isoformat(), "archive": str(archive),
              "archive_articles": len(archive_items), "archive_generated_at": archive_generated_at,
              "archive_match_method": "URL or exact normalized title + established publisher + KST day; overlap lower bound, not total recall; archive snapshot predates search",
              "raw": str(raw) if raw else None,
              "sampling": "Naver recency initial page and observed XLoad continuation up to 3 pages; Google RSS relevance first 100; 7-day search window; Daum access status only if blocked",
              "queries": ["청년", "청년정책", "청년 정책"], "pages": results,
              "accepted_unique_candidates": len(unique), "classified_candidates": len(classified),
              "dedup_filtered_candidates": len(filtered),
              "configured_replay_unique": len(route_urls),
              "public_candidates": sum(bool(item.get("is_public_interest_article")) for item in classified),
              "not_public_reasons": dict(Counter(item.get("drop_reason") or item.get("public_relevance_reason") or "not_public" for item in classified if not item.get("is_public_interest_article")))}
    return report, list(replay_unique.values()), classified


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--archive", default=str(PUBLIC_CONTENT_ROOT / "public_article_archive.json"))
    parser.add_argument("--raw")
    parser.add_argument("--reuse-snapshots", action="store_true")
    parser.add_argument("--report-name", default="coverage_report.json")
    parser.add_argument("--baseline-revision", help="Replay historical collector code/config against identical snapshots")
    args = parser.parse_args()
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    if args.baseline_revision:
        source_text = subprocess.run(["git", "show", args.baseline_revision + ":shared/src/youth_info_platform/collect.py"], capture_output=True, text=True, encoding="utf-8", check=True).stdout
        module = types.ModuleType("youth_info_platform._baseline_collect")
        module.__package__ = "youth_info_platform"
        exec(compile(source_text, "baseline_collect.py", "exec"), module.__dict__)
        for name in ("detect_source_access_issue", "parse_naver_news_search", "parse_feed", "apply_source_filters"):
            globals()[name] = getattr(module, name)
        curation_text = subprocess.run(["git", "show", args.baseline_revision + ":shared/src/youth_info_platform/curation.py"], capture_output=True, text=True, encoding="utf-8", check=True).stdout
        curation = types.ModuleType("youth_info_platform._baseline_curation")
        curation.__package__ = "youth_info_platform"
        exec(compile(curation_text, "baseline_curation.py", "exec"), curation.__dict__)
        for name in ("deduplicate_and_filter", "classify_articles"):
            globals()[name] = getattr(curation, name)
        sources = json.loads(subprocess.run(["git", "show", args.baseline_revision + ":public-site/config/source_config.yaml"], capture_output=True, text=True, encoding="utf-8", check=True).stdout)["sources"]
    else:
        sources = load_source_config(str(Path(__file__).resolve().parents[1] / "config/source_config.yaml"))
    if not args.reuse_snapshots:
        pages = []
        for query in ("청년", "청년정책", "청년 정책"):
            targets = []
            for start in (1,):
                targets.append(("naver", "https://search.naver.com/search.naver?" + urlencode({"where": "news", "query": query, "sort": 1, "nso": "so:dd,p:1w,a:all", "start": start})))
            targets.append(("google", "https://news.google.com/rss/search?" + urlencode({"q": query + " when:7d", "hl": "ko", "gl": "KR", "ceid": "KR:ko"})))
            targets.append(("daum", "https://search.daum.net/search?" + urlencode({"w": "news", "q": query, "sort": "recency", "period": "w"})))
            for portal, url in targets:
                entry = {"portal": portal, "query": query, "url": url, "observed_at": datetime.now(SEOUL).isoformat()}
                try:
                    payload = fetch_url(url)
                    name = hashlib.sha256(url.encode()).hexdigest()[:16] + (".xml" if portal == "google" else ".html")
                    (output / name).write_text(payload, encoding="utf-8")
                    entry.update({"path": name, "sha256": hashlib.sha256(payload.encode()).hexdigest()})
                except Exception as error:
                    entry["fetch_error"] = type(error).__name__
                pages.append(entry)
                print(json.dumps({**entry, "path": entry.get("path")}, ensure_ascii=True), flush=True)
                if portal == "naver" and entry.get("path"):
                    next_url = naver_continuation_url(payload, url)
                    visited = {url}
                    for _ in range(2):
                        if not next_url or next_url in visited:
                            break
                        visited.add(next_url)
                        extra = {"portal": portal, "query": query, "url": next_url,
                                 "observed_at": datetime.now(SEOUL).isoformat(), "pagination": "observed_xload"}
                        try:
                            payload = fetch_url(next_url)
                            name = hashlib.sha256(next_url.encode()).hexdigest()[:16] + ".json"
                            (output / name).write_text(payload, encoding="utf-8")
                            extra.update({"path": name, "sha256": hashlib.sha256(payload.encode()).hexdigest()})
                            next_url = naver_continuation_url(payload, url)
                        except Exception as error:
                            extra["fetch_error"] = type(error).__name__
                            next_url = None
                        pages.append(extra)
        dump(output / "snapshots.json", pages)
    report, candidates, classified = analyse(output, args.archive, args.raw, sources)
    report["collector_revision"] = args.baseline_revision or "working_tree"
    prefix = Path(args.report_name).stem
    report["raw_replay_path"] = prefix + "_candidates.json"
    report["classified_replay_path"] = prefix + "_classified.json"
    dump(output / args.report_name, report)
    dump(output / report["raw_replay_path"], candidates)
    dump(output / report["classified_replay_path"], classified)
    print(json.dumps({"report": str(output / args.report_name),
                      "accepted_unique_candidates": report["accepted_unique_candidates"],
                      "public_candidates": report["public_candidates"],
                      "pages": [{k: page.get(k) for k in ("portal", "query", "fetch_error", "access_issue", "reference_count", "parser_count", "collector_accepted_count", "archive_matches", "bad_publisher_labels")} for page in report["pages"]]}, ensure_ascii=True))


if __name__ == "__main__":
    main()

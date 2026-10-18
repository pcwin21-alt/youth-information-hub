"""Read-only input audit; write reproducible before/after evidence separately."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import subprocess
import urllib.request

from _bootstrap import PUBLIC_CONTENT_ROOT, RUNTIME_PIPELINE_ROOT
from bs4 import BeautifulSoup
from youth_info_platform.public_archive import deduplicate_public_stories, public_publisher_key
from youth_info_platform.publisher_names import article_publisher_name, clean_publisher_title


def metrics(items):
    titles = Counter((clean_publisher_title(x.get("title"), x), str(x.get("published_date") or x.get("portal_published_at") or "")[:10], public_publisher_key(x)) for x in items)
    return {
        "articles": len(items),
        "missing_publisher_name_field": sum(not x.get("publisher_name") for x in items),
        "unresolved_publisher": sum(not article_publisher_name(x) for x in items),
        "missing_original_url_field": sum(not x.get("publisher_url") for x in items),
        "publisher_title_suffixes": sum(str(x.get("title") or "") != clean_publisher_title(x.get("title"), x) for x in items),
        "duplicate_title_publisher_day_excess": sum(n-1 for n in titles.values() if n > 1),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--remote", action="store_true")
    parser.add_argument("--input", default=str(PUBLIC_CONTENT_ROOT / "public_article_archive.json"))
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--render-preview", action="store_true")
    args = parser.parse_args()
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    if args.remote:
        result = subprocess.run(["gh", "api", "repos/pcwin21-alt/youth-information-hub/contents/public-site/content/public_article_archive.json", "-H", "Accept: application/vnd.github.raw+json"], capture_output=True, text=True, encoding="utf-8", check=True, timeout=120)
        payload = json.loads(result.stdout)
    else:
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    items = payload.get("articles", []) if isinstance(payload, dict) else payload
    cleaned = deduplicate_public_stories(items)
    report = {"checked_at": datetime.now().astimezone().isoformat(), "source": "github_default_branch" if args.remote else args.input, "before": metrics(items), "after": metrics(cleaned)}
    if args.remote:
        page = urllib.request.urlopen("https://pcwin21-alt.github.io/youth-information-hub/news.html", timeout=30).read()
        soup = BeautifulSoup(page, "html.parser")
        headlines = [node.get_text(" ", strip=True) for node in soup.select("h3 .article-title-link")]
        report["live_html"] = {"bytes": len(page), "headline_count": len(headlines), "repeated_headline_excess": sum(n-1 for n in Counter(headlines).values() if n>1), "examples": [title for title,n in Counter(headlines).items() if n>1][:8]}
    manifest_path = RUNTIME_PIPELINE_ROOT / "source_collection_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        report["local_collection_snapshot"] = {key: manifest.get(key) for key in ["generated_at", "source_count", "successful_sources", "failed_sources"]}
    for filename, value in [("input_archive.json", payload), ("cleaned_archive.json", {"articles": cleaned}), ("quality_report.json", report)]:
        (output / filename).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.render_preview:
        import sys
        import web_updater
        # Render the inspected archive in isolation; do not mix in stale local
        # runtime records or mutate the production archive/database.
        web_updater.load_public_archive_articles = lambda: cleaned
        original_read = web_updater.read_json
        web_updater.read_json = lambda path, default=None: cleaned if Path(path).name == "step3_classified.json" else original_read(path, default=default)
        web_updater.cache_home_thumbnail_assets = lambda *a, **kw: {}
        status = json.loads(urllib.request.urlopen("https://pcwin21-alt.github.io/youth-information-hub/site-data/pipeline_status.json", timeout=30).read())
        (output / "deployed_pipeline_status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
        sys.argv = ["web_updater.py", "--input", str(output / "cleaned_archive.json"), "--status-input", str(output / "deployed_pipeline_status.json"), "--output", str(output / "preview" / "index.html")]
        # main expects a list, while the audit snapshot keeps an archive object.
        original_read_for_preview = web_updater.read_json
        web_updater.read_json = lambda path, default=None: cleaned if Path(path).resolve() == (output / "cleaned_archive.json").resolve() else original_read_for_preview(path, default=default)
        web_updater.main()
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()


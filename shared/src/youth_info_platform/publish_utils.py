from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .article_metadata import article_identity_key, normalize_article_record, preferred_article_url


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _join_values(values: Any) -> str:
    if values is None:
        return ""
    if isinstance(values, list):
        return ", ".join(str(value).strip() for value in values if str(value).strip())
    return str(values).strip()


def _archive_categories(article: dict[str, Any]) -> str:
    for field in ("topic_tags", "categories", "issue_tags"):
        values = _join_values(article.get(field))
        if values:
            return values
    return ""


def _archive_article_key(article: dict[str, Any]) -> str:
    return article_identity_key(article)


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS articles (
                url TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                source TEXT NOT NULL,
                published_date TEXT,
                region TEXT,
                categories TEXT,
                summary TEXT,
                importance_score INTEGER,
                is_official_source INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS article_archive (
                article_key TEXT PRIMARY KEY,
                url TEXT,
                title TEXT NOT NULL,
                source TEXT NOT NULL,
                published_date TEXT,
                region TEXT,
                categories TEXT,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                seen_count INTEGER NOT NULL DEFAULT 1,
                last_run_id TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_article_archive_url
            ON article_archive(url)
            """
        )
        connection.commit()


def upsert_articles(db_path: Path, articles: list[dict]) -> int:
    init_db(db_path)
    with closing(sqlite3.connect(db_path)) as connection:
        connection.executemany(
            """
            INSERT INTO articles (
                url, title, source, published_date, region, categories, summary, importance_score, is_official_source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                title=excluded.title,
                source=excluded.source,
                published_date=excluded.published_date,
                region=excluded.region,
                categories=excluded.categories,
                summary=excluded.summary,
                importance_score=excluded.importance_score,
                is_official_source=excluded.is_official_source
            """,
            [
                (
                    article["url"],
                    article["title"],
                    article["source"],
                    article.get("published_date"),
                    article.get("region"),
                    ", ".join(article.get("categories", [])),
                    article.get("summary"),
                    article.get("importance_score"),
                    1 if article.get("is_official_source") else 0,
                )
                for article in articles
            ],
        )
        connection.commit()
    return len(articles)


def upsert_article_archive(
    db_path: Path,
    articles: list[dict[str, Any]],
    *,
    run_id: str | None = None,
    seen_at: str | None = None,
) -> dict[str, int]:
    init_db(db_path)
    seen_at = seen_at or _now_iso()

    deduped: dict[str, dict[str, Any]] = {}
    for article in articles:
        normalized_article = normalize_article_record(article)
        article_key = _archive_article_key(normalized_article)
        if not article_key:
            continue
        deduped[article_key] = normalized_article

    if not deduped:
        with closing(sqlite3.connect(db_path)) as connection:
            total = connection.execute("SELECT COUNT(*) FROM article_archive").fetchone()[0]
        return {"inserted": 0, "updated": 0, "processed": 0, "total": total}

    article_keys = list(deduped)
    placeholders = ", ".join("?" for _ in article_keys)

    with closing(sqlite3.connect(db_path)) as connection:
        existing_keys = {
            row[0]
            for row in connection.execute(
                f"SELECT article_key FROM article_archive WHERE article_key IN ({placeholders})",
                article_keys,
            )
        }
        rows = [
            (
                article_key,
                preferred_article_url(article),
                article.get("title") or "(제목 없음)",
                article.get("source") or article.get("source_name") or "",
                article.get("published_date") or article.get("publisher_published_at"),
                article.get("region"),
                _archive_categories(article),
                seen_at,
                seen_at,
                1,
                run_id,
            )
            for article_key, article in deduped.items()
        ]
        connection.executemany(
            """
            INSERT INTO article_archive (
                article_key, url, title, source, published_date, region, categories,
                first_seen_at, last_seen_at, seen_count, last_run_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(article_key) DO UPDATE SET
                url=CASE WHEN excluded.url IS NOT NULL AND excluded.url != '' THEN excluded.url ELSE article_archive.url END,
                title=excluded.title,
                source=excluded.source,
                published_date=excluded.published_date,
                region=excluded.region,
                categories=excluded.categories,
                last_seen_at=excluded.last_seen_at,
                seen_count=article_archive.seen_count + 1,
                last_run_id=excluded.last_run_id
            """,
            rows,
        )
        total = connection.execute("SELECT COUNT(*) FROM article_archive").fetchone()[0]
        connection.commit()

    inserted = sum(1 for key in article_keys if key not in existing_keys)
    updated = sum(1 for key in article_keys if key in existing_keys)
    return {"inserted": inserted, "updated": updated, "processed": len(article_keys), "total": total}

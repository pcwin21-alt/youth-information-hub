from __future__ import annotations

import sqlite3
from pathlib import Path


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
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
        connection.commit()


def upsert_articles(db_path: Path, articles: list[dict]) -> int:
    init_db(db_path)
    with sqlite3.connect(db_path) as connection:
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


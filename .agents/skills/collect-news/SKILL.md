---
name: collect-news
description: Use when auditing, changing, or explaining news/source collection for the youth information platform, including RSS, Naver News search, official releases, source_config.yaml, rss_fetcher.py, and step1_raw_articles.json.
---

# collect-news

뉴스 RSS, 네이버 뉴스 검색, 공식 발표 소스를 수집한다.

## Standard Entry Points

- 설정: `public-site/config/source_config.yaml`
- 실행: `python public-site/scripts/rss_fetcher.py`
- 산출물: `runtime/pipeline/step1_raw_articles.json`
- 파서: `shared/src/youth_info_platform/collect.py`

## When Changing Sources

1. `source_config.yaml`에서 `kind`, `parser`, `url`, `include_keywords`, `limit`, `detail_enrichment`을 먼저 확인한다.
2. 새 parser가 필요하면 `collect.py`의 parser registry와 실제 fetch/parse 함수를 함께 확인한다.
3. 수집 기준을 설명하거나 바꾸는 작업이면 `references/source-criteria.md`를 읽고 현행 기준과 개선 후보를 구분한다.

## Reference

- 수집 판단 기준: `references/source-criteria.md`

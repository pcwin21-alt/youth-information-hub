# collect-news

뉴스 RSS, 네이버 뉴스 검색, 공식 발표 소스를 수집한다.

현재 표준 진입점:

- 설정: `public-site/config/source_config.yaml`
- 실행: `python public-site/scripts/rss_fetcher.py`
- 산출물: `runtime/pipeline/step1_raw_articles.json`

새 소스를 추가할 때는 `shared/src/youth_info_platform/collect.py`의 parser registry와 `public-site/config/source_config.yaml`을 함께 확인한다.

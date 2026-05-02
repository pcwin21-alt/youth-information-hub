# dedup-filter

기사 중복 제거와 기본 필터링을 수행한다.

현재 표준 진입점:

- 실행: `python public-site/scripts/dedup_filter.py`
- 입력: `runtime/pipeline/step1_raw_articles.json`
- 산출물: `runtime/pipeline/step2_filtered.json`

중복 키와 필터 규칙은 `shared/src/youth_info_platform/curation.py`와 `shared/src/youth_info_platform/article_metadata.py`를 기준으로 확인한다.

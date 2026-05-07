---
name: dedup-filter
description: Use when auditing, changing, or explaining article survival, deduplication, curation scoring, public relevance, noise filtering, election filtering, bucket selection, curation.py, article_metadata.py, and step2_filtered/step3/step4/step5 article flow.
---

# dedup-filter

기사 중복 제거, 공개 적합성, 큐레이션 선별 기준을 확인한다.

## Standard Entry Points

- 중복 제거 실행: `python public-site/scripts/dedup_filter.py`
- 큐레이션 실행: `python public-site/scripts/run_curator.py`
- 입력: `runtime/pipeline/step1_raw_articles.json`
- 주요 산출물: `runtime/pipeline/step2_filtered.json`, `step3_classified.json`, `step4_selected.json`, `step5_summarized.json`
- 기준 코드: `shared/src/youth_info_platform/curation.py`, `shared/src/youth_info_platform/article_metadata.py`

## When Changing Criteria

1. 먼저 `references/article-survival-criteria.md`에서 현행 기준을 확인한다.
2. `public_relevance_score`, `importance_score`, `drop_reason`, `selection_bucket` 변경은 공개 노출량과 메뉴 구성을 함께 바꾸므로 테스트 데이터를 확인한다.
3. 개선안은 실제 동작처럼 적지 말고 `개선 후보`로 분리한다.

## Reference

- 기사 생존/선별 판단 기준: `references/article-survival-criteria.md`

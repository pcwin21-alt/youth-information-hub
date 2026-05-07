---
name: publish
description: Use when publishing or explaining public-site output, DB writes, GitHub Pages artifacts, web_updater.py, menu-specific article exposure criteria, home/news/election/policies/hub/tools page rules, and prebuilt deployment.
---

# publish

최종 데이터세트를 DB와 공개 정적 사이트에 발행한다.

## Standard Entry Points

- DB 갱신: `python public-site/scripts/db_writer.py`
- 공개 HTML 생성: `python public-site/scripts/web_updater.py`
- Pages 패키징: `python public-site/scripts/prepare_pages_site.py --site-dir public-site/dist`

## Main Outputs

- DB: `runtime/db/articles.db`
- 공개 HTML 원본: `public-site/web/*.html`
- Pages artifact: `public-site/dist/`

## When Changing Public Exposure

1. 작은 UI/문구 수정과 전체 큐레이션 재실행을 구분한다.
2. 메뉴별 기사 노출 기준을 바꾸는 작업이면 `references/menu-exposure-criteria.md`를 먼저 읽는다.
3. `[deploy-prebuilt]` 배포는 로컬에서 생성된 `public-site/web`/runtime artifacts를 기준으로 올린다는 점을 확인한다.

## Reference

- 메뉴별 노출 판단 기준: `references/menu-exposure-criteria.md`

# publish

최종 데이터세트를 DB와 공개 정적 사이트에 발행한다.

현재 표준 진입점:

- DB 갱신: `python public-site/scripts/db_writer.py`
- 공개 HTML 생성: `python public-site/scripts/web_updater.py`
- Pages 패키징: `python public-site/scripts/prepare_pages_site.py --site-dir public-site/dist`

주요 산출물:

- DB: `runtime/db/articles.db`
- 공개 HTML 원본: `public-site/web/*.html`
- Pages artifact: `public-site/dist/`

작은 UI/문구 수정과 전체 큐레이션 재실행을 구분한다.

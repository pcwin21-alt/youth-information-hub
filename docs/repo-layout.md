# Repo Layout

이 저장소는 공개 정적 사이트, 기관용 Django 운영 콘솔, 공용 파이프라인 패키지를 한 저장소에서 함께 관리한다.

## Top-Level Structure

- `shared/`: 공용 Python 패키지. 수집, 메타데이터 보강, 큐레이션, 편집 오버라이드, 발행 유틸, 런타임 경로 helper를 둔다.
- `public-site/`: 공개 정적 사이트와 파이프라인 실행 스크립트, GitHub Pages/Lightsail 배포 템플릿을 둔다.
- `institution-site/`: 기관 운영자용 Django 앱. 기사 편집, 수동 기사, 문의 설정, 감사 로그, 런타임 동기화를 담당한다.
- `runtime/`: 실행 산출물 저장소. 파이프라인 JSON, SQLite DB, 로그를 둔다.
- `docs/`: 운영 문서와 배포 문서.

## Functional Map

| 기능 | 현재 진입점 | 주요 산출물 |
| --- | --- | --- |
| 기사 수집 | `public-site/scripts/rss_fetcher.py` | `runtime/pipeline/step1_raw_articles.json` |
| 유튜브 수집 | `public-site/scripts/youtube_fetcher.py` | `runtime/pipeline/step1_raw_youtube.json` |
| 중복 제거/기본 필터 | `public-site/scripts/dedup_filter.py` | `runtime/pipeline/step2_filtered.json` |
| 분류/선정/요약 | `public-site/scripts/run_curator.py` | `step3_classified.json`, `step4_selected.json`, `step5_summarized.json` |
| 발행 DB 갱신 | `public-site/scripts/db_writer.py` | `runtime/db/articles.db` |
| 공개 HTML 생성 | `public-site/scripts/web_updater.py` | `public-site/web/*.html` |
| Pages 패키징 | `public-site/scripts/prepare_pages_site.py` | `public-site/dist/` |
| 전체 실행 | `public-site/scripts/cron_runner.py` | `pipeline_status.json`, archive snapshot |
| 운영 콘솔 | `institution-site/manage.py runserver` | Django DB, `editorial_overrides.json` export |
| 배포 템플릿 | `public-site/deploy/` | systemd/nginx/Lightsail 설정 |

## Runtime Structure

```text
runtime/
  pipeline/   step1~step5, article_funnel, ops_radar, pipeline_status, 운영 설정 JSON
  db/         공유 SQLite DB
  logs/       scheduler, preview server, tunnel 로그
```

## Ownership Rules

- `shared/` 변경은 공개 사이트와 기관 사이트 모두에 영향을 줄 수 있다.
- `public-site/scripts/*`는 CI와 운영 명령의 공개 인터페이스이므로 1차 정비에서는 물리 경로를 유지한다.
- `public-site/web/`는 생성된 공개 사이트 원본이고, `public-site/dist/`는 Pages 업로드용 패키지다. 둘을 혼동하지 않는다.
- `runtime/pipeline/*.json`과 `public-site/web/*.html`은 일부 추적 중인 생성 산출물이다. 코드 정비와 데이터 갱신은 가능한 한 커밋을 분리한다.
- 구버전 루트 경로(`scripts/`, `src/`, `web/`, `output/`, `deploy/`)는 현재 표준이 아니다. 새 설명은 각각 `public-site/scripts/`, `shared/src/`, `public-site/web/`, `runtime/pipeline/`, `public-site/deploy/`를 기준으로 쓴다.

## Cleanup Notes

- 별도 Basic Auth 문의 관리자 서버는 Django `/editorial/settings/`로 대체된 레거시다.
- `.agents/skills/`가 현재 에이전트용 안내 위치다. 구버전 Claude skill tree의 중복 스크립트/스킬은 유지하지 않는다.
- `.claude/agents/content-curator/AGENT.md`는 설명성 파일이라 삭제 전 사용자 리뷰가 필요하다.

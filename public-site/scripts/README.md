# Public Site Scripts

`public-site/scripts/`는 공개 사이트 파이프라인의 운영 진입점이다. CI, GitHub Pages workflow, 로컬 자동 반영 스크립트가 이 경로를 직접 호출하므로 1차 정비에서는 파일 위치를 유지한다.

## Pipeline Order

| 단계 | 스크립트 | 입력 | 출력 |
| --- | --- | --- | --- |
| 기사 수집 | `rss_fetcher.py` | `public-site/config/source_config.yaml` | `runtime/pipeline/step1_raw_articles.json` |
| 유튜브 수집 | `youtube_fetcher.py` | 샘플/기본 데이터 | `runtime/pipeline/step1_raw_youtube.json` |
| 중복 제거 | `dedup_filter.py` | `step1_raw_articles.json` | `step2_filtered.json` |
| 큐레이션 | `run_curator.py` | `step2_filtered.json` | `step3_classified.json`, `step4_selected.json`, `step5_summarized.json` |
| 날짜 감사 | `audit_article_dates.py` | classified/selected/summarized/funnel | `article_date_audit.json` |
| DB 발행 | `db_writer.py` | `step5_summarized.json`, `step2_filtered.json` | `runtime/db/articles.db` |
| 공개 HTML | `web_updater.py` | `step5_summarized.json`, settings | `public-site/web/*.html` |
| 전체 실행 | `cron_runner.py` | 위 단계 전체 | 상태 JSON, archive snapshot |

## Operations

- 상태 리포트: `status_report.py`
- 소스 헬스체크: `source_healthcheck.py`
- 공개 artifact 검증: `verify_site_artifacts.py`
- Pages 패키징: `prepare_pages_site.py`
- 로컬 자동 반영: `start_auto_update.ps1`, `stop_auto_update.ps1`, `auto_update_runner.py`
- 프리뷰/터널: `start_preview_servers.ps1`, `stop_preview_servers.ps1`, `start_public_tunnel.ps1`, `stop_public_tunnel.ps1`

## Deprecated

- 별도 Basic Auth 문의 관리자 서버는 사용하지 않는다. 문의/연락처 설정은 Django 운영 콘솔 `/editorial/settings/`에서 관리한다.
- 구버전 루트 `scripts/` 경로는 현재 표준이 아니다.

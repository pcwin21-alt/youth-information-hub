# scheduler

전체 파이프라인을 순차 실행한다.

현재 표준 진입점:

- 전체 실행: `python public-site/scripts/cron_runner.py`
- 샘플 실행: `python public-site/scripts/cron_runner.py --use-sample-data`
- 상태 확인: `python public-site/scripts/status_report.py`

주요 산출물:

- 상태: `runtime/pipeline/pipeline_status.json`
- 아카이브: `runtime/pipeline/archive/`
- 중복 실행 방지: `runtime/pipeline/pipeline.lock`

GitHub Pages는 `.github/workflows/deploy-pages.yml`이 실행하고, VM 운영은 `public-site/deploy/systemd/`와 `public-site/deploy/linux/`를 기준으로 한다.

# GitHub Pages Deployment Guide

공개 사이트는 GitHub Actions가 파이프라인을 실행한 뒤 `public-site/dist/`를 Pages artifact로 업로드해 배포한다.

## Workflow

- Workflow: `.github/workflows/deploy-pages.yml`
- 실행 조건:
  - `shared/**`, `public-site/**`, workflow 파일 변경 push
  - `workflow_dispatch`
  - 정기 schedule
- 기본 모드: `python public-site/scripts/cron_runner.py --curator-max-network-enrich 20` 실행 후 새 artifact 배포
- 예외 모드: workflow dispatch의 `use_prebuilt_site=true` 또는 커밋 메시지 `[deploy-prebuilt]`일 때 체크인된 `public-site/web/`, `runtime/pipeline/` 산출물을 기준으로 배포

## Local Commands

```powershell
python -m pip install -e .\shared -e .\public-site
python public-site\scripts\cron_runner.py --use-sample-data
python public-site\scripts\verify_site_artifacts.py --min-articles 1 --min-news-cards 0
python public-site\scripts\prepare_pages_site.py --site-dir public-site\dist
```

## Artifact Contract

- 공개 HTML 원본: `public-site/web/*.html`
- Pages artifact: `public-site/dist/`
- Pages data copy: `public-site/dist/site-data/*.json`
- 파이프라인 상태/중간 산출물: `runtime/pipeline/*.json`
- 공유 SQLite: `runtime/db/articles.db`

## Operational Notes

- GitHub Pages는 `public-site/web/`를 직접 배포하지 않는다. 반드시 `prepare_pages_site.py`가 `public-site/dist/`를 만든다.
- scheduled run은 UTC 기준이며 GitHub Actions 큐 상황에 따라 지연될 수 있다.
- `public-site/dist/`는 `.gitignore` 대상이다. 배포 artifact로만 사용한다.
- `public-site/web/*.html`, `runtime/pipeline/*.json`은 일부 추적 중이므로 데이터 갱신과 코드 정비 커밋을 섞지 않는 편이 안전하다.
- workflow가 실패하면 기존 Pages 배포는 유지된다.

## Custom Domain

저장소 변수 `PAGES_CNAME`을 설정하면 `prepare_pages_site.py`가 artifact에 `CNAME` 파일을 포함한다.

- 경로: `Settings -> Secrets and variables -> Actions -> Variables`
- 변수명: `PAGES_CNAME`
- 예시: `youth.example.com`

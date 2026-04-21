# Public Site

`public-site`는 공개용 정적 사이트 빌드와 배포 스크립트를 담당한다.

## Quick Start

```powershell
python -m pip install -e ..\\shared -e .
python scripts\\cron_runner.py --use-sample-data
python scripts\\verify_site_artifacts.py --min-articles 1 --min-news-cards 0
```

## Key Paths

- 정적 산출물: `public-site/web/`
- Pages 아티팩트: `public-site/dist/`
- 공용 런타임: `../runtime/pipeline/`, `../runtime/db/`, `../runtime/logs/`

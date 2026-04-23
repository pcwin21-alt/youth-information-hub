# Public Site

`public-site` contains the static public site, news collection scripts, and
GitHub Pages deployment pipeline.

## Quick Start

```powershell
python -m pip install -e ..\shared -e .
python scripts\cron_runner.py --use-sample-data
python scripts\verify_site_artifacts.py --min-articles 1 --min-news-cards 0
```

## Deployment Notes

- The live GitHub Pages site is refreshed by the `Build And Deploy Pages`
  workflow.
- Scheduled runs are configured in UTC and can be delayed by GitHub Actions.
  Treat the displayed update times as target windows, not exact clock times.
- The local auto-update runner updates local runtime/site artifacts only. A live
  GitHub Pages refresh still needs a GitHub Actions deployment.

## Key Paths

- Static source: `public-site/web/`
- Pages artifact: `public-site/dist/`
- Shared runtime data: `../runtime/pipeline/`, `../runtime/db/`, `../runtime/logs/`

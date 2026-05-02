# Repo Cleanup Audit - 2026-04-29

## Decisions

- Cleanup depth: audit plus low-risk cleanup.
- Legacy policy: delete only after references are checked.
- Layout target: keep `shared/`, `public-site/`, `institution-site/`, `runtime/`, `docs/` and improve internal maps.
- Generated artifacts: keep current tracking policy and separate artifact churn from code/docs changes.

## Findings

- The active pipeline now runs through `public-site/scripts/*` and `shared/src/youth_info_platform/*`.
- The old root paths `scripts/`, `src/youth_info_platform/`, `web/`, `output/`, `deploy/`, `config/`, and `content/` are deleted or superseded by domain folders.
- Current runtime outputs live under `runtime/pipeline/` and `runtime/db/`.
- Current public static source lives under `public-site/web/`; Pages artifact lives under `public-site/dist/`.
- `.agents/skills/` is the current skill instruction location.
- `.claude/skills/` duplicated old skill docs and scripts; the old scripts were already removed.

## Deleted As Legacy

- Root legacy paths already marked deleted:
  - `scripts/`
  - `src/youth_info_platform/`
  - `web/`
  - `output/`
  - root `deploy/`
  - root `config/`, `content/`
- Basic Auth contact admin path:
  - `public-site/scripts/contact_admin_server.py`
  - `public-site/scripts/set_contact_admin_password.py`
  - `public-site/config/contact_admin.local.json.example`
- `.claude/skills/*/SKILL.md` duplicates, because `.agents/skills/` is now the maintained location.

## Left For Review

- `.claude/agents/content-curator/AGENT.md`
  - Reason: this is a descriptive agent instruction, not a duplicated script.
  - Action: keep until the owner confirms whether it should move into `.agents/` or be deleted.

## Verification Commands

```powershell
rg -n -e "python scripts/" -e "bash deploy/" -e "chmod \+x deploy/" -e "cp deploy/" -e "cat /opt/youth-together/output/" -e "/opt/youth-together/deploy/" -e "\.claude/skills" README.md harness.md docs .agents .github public-site shared institution-site
python -m unittest discover shared/tests
python public-site/scripts/cron_runner.py --use-sample-data
python public-site/scripts/verify_site_artifacts.py --min-articles 1 --min-news-cards 0
python institution-site/manage.py test
python public-site/scripts/article_debug.py --url "https://www.sedaily.com/article/20038288" --limit 3
```

## Verification Results

- Stale execution path search: clean outside this audit note.
- Basic Auth admin helper reference search: clean outside this audit note.
- `python -m unittest discover shared/tests`: 57 tests passed.
- `python public-site/scripts/cron_runner.py --use-sample-data`: completed with 6 selected/summarized articles and 3 ops radar items.
- `python public-site/scripts/verify_site_artifacts.py --min-articles 1 --min-news-cards 0`: passed with pipeline state `completed`.
- `python institution-site/manage.py test`: Django system check passed; 0 tests discovered.
- `python public-site/scripts/article_debug.py --url "https://www.sedaily.com/article/20038288" --limit 3`: returned `not_collected` with `failed_to_fetch_url`, so the 4xx page title was not merged into article metadata.

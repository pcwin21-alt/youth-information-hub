# Collection engine quality audit — 2026-10-18

## Contract and routing

Request: inspect accumulated collection and live homepage/news output, repair duplicate articles, publisher labels and original links, and update the engine. Audience: site owner and visitors. Acceptance: reproduce live failures, repair source-to-render paths, preserve independent reporting, run regression tests, generate an isolated preview, and verify deployment separately.

Always: shared AGENTS, Brain and Skill Router. Active: collect-news, dedup-filter, publish and Eval Global Gate. Reference: shared inventory (33 nodes), existing parser/curation/menu criteria, runtime and GitHub deployment evidence. Excluded: writing styles, content planning and unrelated UI redesign. Inventory drift: skill source/menu criteria date from May and differ from current 85-source / 365-day archive implementation; current code and live artifacts are authority.

## Evidence

- Inspected GitHub default-branch archive: 3,799 articles. Live news HTML: 13,087,038 bytes, 3,053 headlines, 339 repeated-headline excess occurrences. Repeated headlines alone are not proof of duplicate articles across different publishers/dates.
- Baseline archive: 3,745 publisher_name fields absent, 270 records without usable publisher evidence, 221 source/domain title tails, and 106 excess records with the same cleaned title, publisher and raw publication day.
- Cleanup of that fixed snapshot: 3,577 articles (222 copies consolidated); publisher_name absent/unresolved 238; title tails 0; three repeated-title/publisher/raw-day cases retain differing original-versus-portal publication metadata. Those date conflicts are not guessed away.
- Only existing domain mappings, source labels, article-scoped structured publisher metadata and explicit original-article links are used. An unresolved Daum record is not assigned a guessed newspaper.
- Last inspected live execution: https://github.com/pcwin21-alt/youth-information-hub/actions/runs/39081356573 completed at 2026-10-18 09:16 KST; collection 428, 47 successful sources, 38 failures; date audit 0 errors and 323 warnings. Quality feedback failed despite successful deployment.
- Local runtime stopped on October 11 after the local scheduler was disabled; it was not treated as today's production data.

## Repairs

1. Normalize publisher names from observed domain/feed/page metadata; support subdomains with longest established domain match, and remove verified title source tails.
2. Read Article/NewsArticle publisher from JSON-LD and explicit 기사원문 links on portal pages. Prefer an observed direct original URL over a stored portal URL.
3. Keep richer copies of identical URL records. Do not let a Google wrapper override known publisher boundaries, or let a portal copy bridge two distinct publishers. Exclude the representative itself from related_articles.
4. Re-deduplicate after metadata enrichment and during archive/current-list merging. Correct canonical-key changes that previously discarded selected-article enrichment.
5. Compare archive publication days in KST. Preserve original identity fields and publisher date provenance when consolidating a portal copy.
6. Collect Atom published timestamps and prioritize portal-dated fresh articles for metadata enrichment.
7. Record per-source elapsed_seconds; read fetched_items as the collection manifest's total count instead of incorrectly reporting official sources empty. Production feedback now recognizes blocked/fetch_error/auth_required outcomes and uses the current collection manifest.
8. Add audit_collection_quality.py for reproducible snapshot audits and isolated rendering; attach current source manifest, feedback report and quality report to GitHub verification artifacts.

## Validation and boundaries

- Local full suite: 191 tests after the final source-failure regression. Deployment checkout has a different baseline test set; its count is recorded in the final handoff.
- Isolated preview: runtime/quality-audit/2026-10-18/verified/preview/index.html and news.html, generated from the inspected remote archive and deployed status without production data mutations. The preview generated 3,555 detail pages.
- Machine evidence: runtime/quality-audit/2026-10-18/final/quality_report.json; raw and cleaned snapshots retained in the same audit tree.
- Source blocking/access failures remain an operational issue. This change does not claim all 85 sources are healthy or that absent publisher names/original URLs have been recovered without evidence.
- Existing unrelated uncommitted UI, institution and deployment changes in the primary checkout were preserved. Deployment changes were isolated on the remote main baseline.
- External deployment: pending verification at report creation; final response records actual outcome.


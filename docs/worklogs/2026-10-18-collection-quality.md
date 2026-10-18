# Collection engine quality audit — 2026-10-18

## Contract and routing

Request: inspect accumulated collection and live homepage/news output, repair duplicate articles, publisher labels and original links, and update the engine. Audience: site owner and visitors. Acceptance: reproduce live failures, repair source-to-render paths, preserve independent reporting, run regression tests, generate an isolated preview, and verify deployment separately.

Always: shared AGENTS, Brain and Skill Router. Active: collect-news, dedup-filter, publish and Eval Global Gate. Reference: shared inventory (33 nodes), existing parser/curation/menu criteria, runtime and GitHub deployment evidence. Excluded: writing styles, content planning and unrelated UI redesign. Inventory drift: skill source/menu criteria date from May and differ from current 85-source / 365-day archive implementation; current code and live artifacts are authority.

## Evidence

- Inspected GitHub default-branch archive: 3,799 articles. Live news HTML: 13,087,038 bytes, 3,053 headlines, 339 repeated-headline excess occurrences. Repeated headlines alone are not proof of duplicate articles across different publishers/dates.
- Final baseline audit: 3,745 publisher_name fields absent, 416 records without an established human publisher label, 221 source/domain title tails, and 71 excess records with the same cleaned title, publisher identity and raw publication day. Unknown direct-publisher domains remain independent identities.
- Cleanup of that fixed snapshot: 3,615 articles (184 copies consolidated); publisher_name absent/unresolved 379; title tails 0; three repeated-title/publisher/raw-day cases retain differing original-versus-portal publication metadata. Those date conflicts are not guessed away.
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

- Final deployment checkout suite: 191 tests passed; primary checkout: 196 tests passed. Bytecode and diff checks passed.
- Isolated previews: runtime/quality-audit/2026-10-18/deployment-preview/preview/index.html and news.html use the final conservative publisher-identity rules; the earlier verified/preview contains an intermediate version. All previews use the inspected remote archive and deployed status, without production data mutations.
- Machine evidence: runtime/quality-audit/2026-10-18/final/quality_report.json; raw and cleaned snapshots retained in the same audit tree.
- Source blocking/access failures remain an operational issue. This change does not claim all 85 sources are healthy or that absent publisher names/original URLs have been recovered without evidence.
- Existing unrelated uncommitted UI, institution and deployment changes in the primary checkout were preserved. Deployment changes were isolated on the remote main baseline.
- External deployment: https://github.com/pcwin21-alt/youth-information-hub/actions/runs/39094500689 succeeded (commit 9a932ab). Public index/news returned HTTP 200 after deployment; news HTML changed from 13,087,038 to 12,224,920 bytes, headlines 3,053 to 2,880, portal title tails 0. The observed youth housing-loan duplicate now appears once. Repeated headlines across different publishers/dates are intentionally not all removed.
- This is an archive-only regeneration, not a fresh successful collection. The separately started full collection was cancelled as redundant after archive regeneration. Regular GitHub schedules remain enabled. The render-only verification artifact still includes the older checked-in pipeline_status; it is not used as today's collection proof. The last fresh collection evidence is the separate October 18 09:16 run cited above.
- Machine deployment evidence: runtime/quality-audit/2026-10-18/deployed_verification.json; source snapshot SHA256 e7c7a037d679445e40ac269a7506d15dbad4266b1f96a0b0af4847928cc7a964.
- The recovery renderer originally bypassed archive cleanup. Its input loader now applies the same rules, with a regression that exercises the actual archive-only entry point.
- Health checks now recognize the observed current brand (적재적소 브리프) and do not require the retired home-glance widget in the redesigned home. Genuine source errors remain findings.

## Live source failures checked

- Policy briefing RSS returned HTTP 404. The publisher explicitly discontinued all RSS on July 1: https://www.korea.kr/etc/noticeView.do?newsId=132038885 . That one source is now disabled with the notice and reason retained. Existing direct official HTML sources remain enabled (85 configured, 84 enabled).
- Naver search returned HTTP 403. No access-bypass or invented credentials were added.
- Seoul redirected to common/errorAccess.html and Daegu to code404.jsp with HTTP 200. The collector now recognizes the observed short error-page bodies as fetch_error rather than successful empty results. These routes still require replacement with verified board endpoints; they are not reported as repaired sources.


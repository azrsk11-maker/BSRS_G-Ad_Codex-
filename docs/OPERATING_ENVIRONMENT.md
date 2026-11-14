# Execution environment and integrations

Verified 7 November 2026. This document records capabilities, not credentials or permission grants. A different Codex account must recheck its actual tool catalog and authenticated account before acting.

| Surface | Current evidence | Dependency / boundary |
|---|---|---|
| GitHub | Public owner-designated repository; owner Chrome session can upload/configure; connected API identity can read/open issues but lacks push/admin on this repo | Use feature PRs. Do not copy browser tokens, grant credentials or weaken review. Resolve independent execution/review identity in issue6 |
| Chrome | Connected extension successfully read Ads, GTM, GA4 and owner GitHub; ordinary file chooser uploads work | One browser writer. Keep signed-in profiles distinct. After ambiguous writes read back; do not retry submissions blindly |
| WordPress | Public site responds; authenticated admin navigation reaches login | User sign-in is needed to refresh installed-source and release access. Existing deployment was reviewed plugin ZIP replacement plus source/asset readback |
| Hostinger | Owner-managed site, CDN headers observed; existing control-panel tab is at authentication | Current selected site, staging, plan/runtime, backups and recovery unverified; no SSH/FTP/git deployment credentials available |
| Google Ads | Read-only snapshots in audit/LIVE_READBACK_2026-11-07.json, audit/ADS_MEASUREMENT_READBACK_2026-11-07.json and audit/CAMPAIGN_CONTROLS_READBACK_2026-11-07.json; 20-campaign baseline, accepted tag IDs/goals, four V2 shared controls/CPC limits, account automation and Brand policy observed | Zero enabled campaigns; Brand policy Approved is not launch authorization. Language and remaining inherited/manager controls need verification. Accepted action shows legacy lplife source; qualified action has no import connection. Conversion-customer ownership, runtime binding and provider compatibility remain open |
| GA4 and GTM | Dedicated identifiers verified in the same readback; GTM live version empty, collection inactive | Do not infer full runtime installation, consent acceptance or conversion delivery from account identity |
| Apps Script / private Sheets / email | Historical signed WordPress → receiver → private Sheet → authenticated email flow; deployed receiver Version2 uses wire1 and26columns | Preserve owner-only bindings/outbox. Editor HEAD is not deployed source. No live Sheet ID, webhook signature, receiver secret or lead data is included here |
| Calendar/staff | Previous Nov4 attendance confirmation exists; completion/invite unverified | Do not schedule past dates or infer capacity from login. Confirm readiness and attendance before any new meeting |

## Relevant tools and skills

- GitHub connector: prefer supported read/issue/PR operations when permissions suffice; inspect returned permissions before mutation. Browser owner session is the current upload/settings fallback. Public issue creation does not imply permission to label, push or administer.
- Computer Use skill and `cua_repl`: use documented browser APIs only; no alternate token extraction or browser-driver bypass. Follow the installed skill's current version and confirmation rules in the executing environment.
- Google Drive/Sheets/Gmail/Calendar connectors: discover the relevant tools and verify the Real Estate account first. A connected Business Setup account does not authorize touching those records or provide Real Estate access. No connector-access expansion was performed in this phase.
- jCodeMunch: repository ID `azrsk11-maker/BSRS_G-Ad_Codex-` indexed locally (54code/configfiles,510symbols at initial snapshot). Use `menu` and explicit `get_file_outline`/`get_symbol_source` for focused exploration; refresh only changed files. JSON/YAML import extraction is incomplete. Local index availability does not prove availability in another chat.
- CLI: Git and Node are available; Python PATH resolved to a Windows Store alias, so tests used an existing trusted Python3.12.14 interpreter. No runtime was installed or security policy bypassed. CI independently executed PHP8.5.4 and17isolated native checks; current production PHP version still needs Hostinger/WP verification.
- Web research: use current primary Google/platform sources. Source access/facts are recorded in audit/research-evidence.md; do not invent current platform limits or regard source citations as business inventory/advertising-rights evidence.

No automatic deployment bridge, production Google credentials, CRM synchronization, call/WhatsApp verification provider, viewing booking provider or live property feed was established. Future capabilities require actual supported providers, business evidence, scoped approval and acceptance tests.

Verified identifiers are retained in `config/tracking/verified-destinations.unpublished.json` as dated observations only. The register is not imported into the runtime contract, has no approved mapping, and authorizes no publication or test conversion. An action ID differs from its Google Ads tag conversion ID; do not substitute one for the other or reuse the accepted-enquiry label for the offline qualified action.

## Efficient continuation

1. Read PROGRESS and approved decision issues; inspect the current PR/head/check status.
2. Check the actual target account and source hashes relevant to the task. Preserve source-pack originals.
3. Use one agent for dependent work; up to three independent parallel workstreams plus one coordinator were useful here. Respect the host's actual limit.
4. Run the smallest meaningful changed-behavior check. The full offline foundation runner is mandatory for a release-foundation PR; production gates remain separate.
5. Save compact evidence and measured time/counts; keep logs/private data outside the public repository. A cached audit microbenchmark is not total token or productivity savings.

Browser upload readback: two post-commit waits (URL and heading) timed out during this continuation, while the next independent accessibility snapshot confirmed each commit succeeded. No commit was retried. Root cause of the wait behavior is unverified; do not infer submission failure from it. Use a separate fresh state readback after GitHub's processing page, then verify the remote commit/bytes before any retry. Do not repeat the failing wait loop or expand authentication to work around it.

## Reviewed Python runtime - 12 November 2026

CI's unpinned Python3.14 exposed runtime-sensitive default AST review hashes and a pathlib mock keyword mismatch. The reviewed local interpreter is Python3.12.14; CI now selects Python3.12 with official setup-python commit `e797f83bcb11b83ae66e0230d6156d7c80228e7c` and fail-closed validation against the unchanged original review before expensive checks. The resolved patch is printed and must pass current-source CI; do not assume every3.12patch is already accepted. Python3.13+ remains unsupported by this reviewed binding rather than silently skipped or repinned. Local preflight and four focused mock checks pass; complete candidate CI is pending. [Exact failure evidence, checks and limits](audit/CI_PYTHON_RUNTIME_COMPATIBILITY_2026-11-12.json). This environment control grants no production or Ads authority.

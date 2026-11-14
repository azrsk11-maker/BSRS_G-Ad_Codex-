# Phase 0 website and tracking audit — 7 November 2026

The existing site is WordPress with Houzez and Elementor evidence. The six existing enquiry routes are healthy in the bounded HTTP checks, and publicly served BSRE assets identify version 0.2.12. This is an audit and an offline development package; it does not publish pages, change tracking, activate Ads or complete live acceptance.

## 11 November Dubai-day read-only refresh

[Fresh sanitized public inventory](public-audit-2026-11-11.json), observed10November20:18:02UTC, used ten allowlisted GETs in4.118seconds: nine routes all HTTP200, including the known same-origin sitemap redirect. The seven HTML summaries match9November exactly. The hub and five funnels retain noindex and referenced BSRE asset0.2.12. Initial HTML exposes no Google measurement IDs; this does not prove tags absent or establish runtime consent, payload privacy, installed source identity or delivery acceptance. No JavaScript was executed or form/consent endpoint posted to by this HTTP audit.

The [connected Chrome readback](../../docs/audit/ACCESS_READBACK_2026-11-11.json) reaches the WordPress login form. No authenticated admin tab was found among enabled connected surfaces; unconnected profiles were not assessed. No credentials were entered or configuration read/changed. Historical readiness switches and private integrations remain unrefreshed; [issue6](https://github.com/azrsk11-maker/BSRS_G-Ad_Codex-/issues/6) continues to cover that access dependency. No tracking, website, permission, financial or Ads change occurred.

## Evidence and freshness

| Evidence | Observation | Limit |
|---|---|---|
| [Public inventory](public-audit-2026-11-07.json), 05:23:51 UTC | Homepage and six enquiry routes return 200 without authentication, query parameters or JavaScript. Nine GETs took 4.664 seconds. | Initial HTML/headers only; no consent execution, payload capture, form submission or delivery test. |
| [Sitemap follow-up](sitemap-followup-2026-11-07.json), 05:24:46 UTC | `/sitemap_index.xml` redirects 302 to same-origin `/sitemap.xml`; index has 19 child sitemaps. | Child maps were not fetched; absence of enquiry URLs from the index is not exclusion from child maps. |
| Existing `docs/CONSENT_RELEASE.md`, 2 November | Privileged readback: primary 0.2.12 and companion 0.1.0 active; eight readiness checks configured; all three measurement switches OFF. | Historical administrative state; current public asset version corroborates the primary version only. |
| Repository `docs/audit/LIVE_READBACK_2026-11-07.json`, 7 November approximately 05:25 UTC | Dedicated GA4 and GTM identifiers and settings below reverified. WordPress admin redirected to login. | Authenticated account UI readback by root; no authenticated WordPress refresh in this subtask. |

Total public-site requests in this subtask: **12 GETs**: initial nine, one bounded redirect diagnosis, and two-request sitemap follow-up. No page JavaScript was executed, no form/context/consent endpoint was posted to, and no Google measurement request or test conversion was generated. Output retains no HTML bodies, cookies, tokens, form values or raw CSP. The follow-up is documented rather than silently replacing the original refused-redirect observation.

## Current public website

| Route | HTTP | Forms | Canonical | Robots |
|---|---:|---:|---|---|
| `/` | 200 | 4 total, zero BSRE forms | Main origin `/` | No noindex observed in captured meta/header |
| `/enquire/` | 200 | 0 | Exact route | noindex, nofollow |
| `/enquire/off-plan/` | 200 | 1 BSRE form | Exact route | noindex, nofollow |
| `/enquire/resale/` | 200 | 1 BSRE form | Exact route | noindex, nofollow |
| `/enquire/rent/` | 200 | 1 BSRE form | Exact route | noindex, nofollow |
| `/enquire/sell/` | 200 | 1 BSRE form | Exact route | noindex, nofollow |
| `/enquire/let/` | 200 | 1 BSRE form | Exact route | noindex, nofollow |

- Main-page public asset paths identify `houzez`, `elementor`, `houzez-studio`, `houzez-theme-functionality`, `all-in-one-seo-pack`, `mailchimp` and `revslider`. These are evidence of referenced assets, not an authenticated installed/active plugin inventory. HTML generators report WordPress 7.1.4 and Elementor 4.3.3; privileged versions remain to be confirmed.
- Main-page initial HTML includes an external Elfsight script origin. The six enquiry responses reference only BSRE plugin assets in the captured HTML and have no external script origin in that initial document. This does not rule out runtime injection or additional browser requests.
- No `GTM-*`, `G-*` or `AW-*` identifier was found in the initial HTML of these seven pages. This does not prove zero tracking: conditional loaders, runtime frames, cached pages and consent choices were not executed.
- Hostinger is owner-stated and supported by current `server: hcdn` plus `x-hcdn-*` headers, as well as the historical Hostinger backup receipt. The selected Hostinger site/account, permissions, plan/page capacity, deployment controls and current backup inventory still need authenticated verification.
- Homepage CSP is only `upgrade-insecure-requests`; do not describe it as a restrictive script policy. Enquiry pages have a more restrictive multi-directive CSP. Nonce values were deliberately discarded. SDK compatibility and complete browser traffic remain untested in this phase.
- `robots.txt` has a WordPress-admin disallow and declares a sitemap. It has no observed blanket disallow or `/enquire/` disallow. This is not a successful AdsBot fetch or Google destination approval test.
- Service HTML exposes `data-campaign` and `data-cta-location`; it does not establish the complete v3 stable campaign/page/CTA/form contract. The hub lacks the matching context attributes in this narrow extractor. Native source and runtime mapping work is required.
- No planned `/lp/bsre-c####/` routes were created or probed. The 360 registry entries remain planned slots, not verified live pages or inventory.

## Native ownership, deployment and recovery

Selective review of the captured installed source (`work/installed-source-2026-11-02/bsre-enquiries/includes/drafts.php`) shows native WordPress `page` records created by `wp_insert_post` for the hub and five child service pages. `includes/parent-isolation.php` reserves their response with the packaged template after the native query, preserving isolation from inherited theme/tag machinery. Existing service records were historically 26751–26755 and hub 26750; those CMS IDs are not freshly verified by public HTTP.

The existing creation and template functions use a fixed six-route map. They must not be reused unmodified to generate 360 routes, and `/lp/` pages do not automatically inherit the existing intake/consent integration. A separate reviewed native adapter is required; an offline preview is not a WordPress draft or published page.

The verified historical deployment procedure was a reviewed plugin ZIP installed through WordPress's replacement flow, followed by installed-source and directly served asset readback. This is not evidence of a GitHub-to-Hostinger deployment pipeline. Root's current WordPress admin readback reaches login; credentials must remain in WordPress. No FTP, SSH, database, Hostinger project or GitHub deployment credentials were read here.

The 2 November release checkpoint records scoped plugin-only rollback packages and warns against restoring settings, accepted leads, private configuration or outbox state for a UI fault. The historical 22 October Hostinger file/database backup completion does not establish a current backup or successful recovery rehearsal. The approved new-recovery policy is encrypted owner-only copies expiring after 30 days, with deletion manifests reapplied before reopening restored systems; implementation/provider inventory remains separate acceptance.

The active receiver was audited on 2 November as immutable Apps Script deployment Version 2, using **wire envelope version 1** and the original **26-column intake**. Version 2 is a deployment label, not a new wire protocol. The two deployed files differed from the 19-file editor HEAD. Accepted-source v2, current withdrawal/closure authority and canonical outcome writing were absent. Do not deploy all draft HEAD helpers or enable incompatible callers to close this gap. Preserve the existing durable receipt, same-ID retry/conflict handling, private Sheet, email outbox and no-CRM architecture.

## Tracking identifiers and native configuration

Root's read-only Chrome observations on 7 November supersede the older 23 October freshness for these values:

| Item | Verified identifier / observation | Readiness interpretation |
|---|---|---|
| Dedicated Real Estate GA4 | Property `559502861`, web stream `16159906474`, measurement `G-W01P9W3NWE`, correct domain | Configuration identity only; no real accepted-event delivery established |
| GA4 collection controls | Enhanced measurement OFF; user-provided-data collection OFF; Google signals OFF; granular location/device OFF; zero connected site tags | Preserve until approved mapping and payload acceptance |
| GA4 collection diagnostics | Data collection not active; no data in previous 48 hours | Not proof of all-time zero events |
| GA4 redaction | Email redaction active; URL query-parameter redaction inactive | Do not rely on product redaction for privacy. Produce query-free allowlisted payloads; do not change this live setting without approval |
| Dedicated GTM | `GTM-NW8WXKRF`, container `267608465` | Published Version 1 is **Empty Container**, zero tags/triggers/variables, latest publication 19 October |
| Ads customer | `573-038-4686`, from explicit project scope and historical account evidence | Customer ID is not a conversion ID or action label |
| Ads conversion tag ID/labels | Not freshly verified in this subtask | Leave production destination configuration unset until native action readback |
| Private Google Sheet / receiver bindings | Intentionally omitted from this public-facing package | Owner-only verification; no workbook sharing expansion |

Historical receipts for the dedicated identifiers: old source `docs/BLACK_SWAN_STATE.md:101–102`; `work/v2-implementation/execution-2026-10-23/continuation-1142-root/TURN-RESULT.md`; `continuation-1204-root/TURN-RESULT.md`. The installed source's `includes/measurement-runtime.php` corroborates those configured IDs but is not account ownership proof.

## Requirements that need explicit reconciliation

1. The new addendum defaults to a shared company GTM/GA4 stream across main-site and campaign pages. Prior decisions created dedicated Real Estate funnel tracking and preserved the legacy shared/lplife configuration. Audit legacy ownership and propose a migration/isolation decision; do not silently replace existing tags or create another property.
2. V3 names the operational receipt `form_accepted`; existing code uses versioned `bsre_lead_accepted` internally, canonical `form_submit`, and one `generate_lead` adapter. Choose an explicit compatibility adapter, not multiple producers. Existing accepted-enquiry Ads action stays Secondary under the prior decision unless a new goal approval changes it; the v3 candidate-primary wording is not approval.
3. Existing four-campaign/six-ad-group routing uses multiple service destinations in buyer/owner campaigns. V3's 360 planning pairs and one dedicated page per deployed campaign require a reviewed mapping/migration decision, not immediate replacement or scaling.
4. The new v3 configuration deliberately leaves Ads account/budgets/IDs unverified/null and says no production writes; historical AED2,000 aggregate average/day approval does not authorize this new package's deployment. Latest instruction explicitly requires separate approval for production pages, live tracking and Ads changes.

## Executable artifacts and checks

- `public_audit.mjs`: dependency-free allowlisted HTTPS GET inventory; no browser runtime or submission. Fixed site/path scope, redirect/body/time limits, redacted output. Output is create-only and refuses an existing file before requesting the site. Five focused safety tests cover scope, redaction, redirects and secret-header exclusion.
- `validate_tracking_evidence.mjs`: validates privacy/dedup/event invariants and all 32 source test IDs; keeps source design unexecuted. Rejects PASS without evidence/reviewer/date/method, isolated HTTP/unit evidence labeled as complete live acceptance, and synthetic production conversions. Eight focused tests, including output/input collision through canonical paths and hardlinks; OS policy prevented the symlink creation subcase. The guard resolves symlinks but that subcase is not claimed tested here.
- `tracking-evidence-2026-11-07.json`: nine partial static observations; zero complete live gates passed. `tracking-validation-2026-11-07.json` validates the evidence structure but explicitly reports `acceptance_complete: false` and `release_authorized: false`.
- `tracking-system/`: offline context/payload/consent/adapter/idempotency prototype with 16 focused tests. See [its implementation limits](tracking-system/README.md).
- `commercial-system/`: offline verified-export report calculator with 16 focused synthetic tests. No actual accounting treatment is invented: missing approved finance rules or source completeness produce BLOCKED/null metrics. It separates contractual closing, collection, first-ever person qualification and opportunities; conserves transaction allocations and prevents duplicate daily spend. Known other-source, genuine unknown and unmapped Ads are distinct buckets. See [its finance dependencies](commercial-system/README.md).

Last combined test run: **45/45 passed**, Node runner **237.4159 ms**. These are local behavior checks, not site release acceptance. No full website build was available or run. Test fixture destination IDs and financial figures are fictional and are never sent anywhere. Adversarial review tightened missing outcome-evidence handling, added an absolute HTTP deadline, protected report inputs, rejected invalid calendar dates and prevented phone-shaped IDs from entering the Ads transaction field. Independent commercial review reproduced two defects before integration; regression tests now reject a later claimed first qualification contradicted by earlier verified history and unsafe final contribution arithmetic.

Run locally from this directory:

```powershell
node --test public_audit.test.mjs validate_tracking_evidence.test.mjs tracking-system/contract.test.mjs commercial-system/report.test.mjs
node validate_tracking_evidence.mjs <contract.json> <acceptance-tests.json> tracking-evidence-2026-11-07.json
# Optional fresh public inventory; performs bounded real GETs, never tag execution:
node public_audit.mjs <new-output.json>
```

## Next dependencies and acceptance

1. Restore authenticated WordPress/Hostinger read-only access; inspect selected native site, versions, plugin/theme tag installers, native IDs, current backups and deployment ownership. Do not re-ask for an already granted permission; a login session can still have expired.
2. Reconcile the tracking and campaign/page decisions in GitHub owner-decision issues. Inventory the legacy main-site property/container without altering it. Read actual Ads conversion IDs/labels and goal associations.
3. Prepare one native WordPress pilot in a feature branch/staging context. Preserve all main-site forms/navigation. Bind its reviewed registry/CTA metadata and existing signed durable intake. Resolve wire compatibility and current permission/retention authority first.
4. Complete actual consent and QA-after-logout behavior, full outgoing-payload inspection, idempotency and destination mapping under isolated diagnostics. No synthetic production conversion and no real ad clicks for testing.
5. Verify same-ID receiver/Sheet/email acceptance and recovery, restricted staff workflow/rehearsal/capacity, and genuine eligible GCLID import setup. Phone/WhatsApp clicks remain diagnostic; bookings/conversations/transactions/commission require real authorized producers and evidence.
6. Complete all relevant WT-001–WT-032 gates and owner-reviewed release artifacts. A successful local test or PR merge does not authorize production publication, live tracking changes or Ads expenditure.

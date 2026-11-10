# Offline commercial report prototype

`report.mjs` implements a small, dependency-free calculation over a **verified, sanitized export supplied by the owner**, without reading any real business record or making network calls. No finance policy is assumed to have been approved. It returns `BLOCKED` and `metrics: null` if a policy decision or required source completeness is missing. A successful calculation remains an offline result requiring finance reconciliation.

The module checks explicit input assertions; it does not authenticate their author, prove ledger completeness or inspect the GitHub decision register. A production caller must establish those facts and resolve the policy approval reference before supplying `verified`/`approved` flags. Test fixtures are not approvals or verified business records.

The supported policy is deliberately explicit: gross collected commission including VAT; refund figures excluding refunded VAT; VAT and pass-through deducted once; agent/referral/direct costs supplied separately and not already netted; actual Ads media cost excluding VAT; separate non-media acquisition cost; and transaction allocations in millionths summing to exactly one. These are **synthetic fixture settings**, not approved BlackSwan accounting treatment. Finance must confirm a compatible policy or request a separately tested alternative. Do not substitute blanks with zero or run real figures through the fixture policy.

Implemented controls:

- Canonical transaction identity across buyer/seller acquisition, exact duplicate suppression and changed-record conflict detection. Allocation weights are combined once and preserve monetary minor units with deterministic rounding.
- Actual collection is distinct from contractual closing and pipeline value. Installments do not create multiple transactions within a reporting window. Property sale price is an unsupported field and cannot become brokerage revenue.
- Net brokerage revenue = collected commission minus supplied VAT, refunds and true pass-through; contribution further subtracts separate payouts/direct costs. Post-acquisition contribution also subtracts separate non-media costs and unique campaign/day media spend. No VAT rate or commission rate is invented.
- First-ever confirmed qualification counts each canonical person once across roles; a person with any unresolved history row is held from the total, an earlier verified qualification contradicts a later claimed first-ever qualification, and opportunity counts remain separate.
- Qualification/opportunity/allocation rows support `source_class: ads | other | unknown`. Known other-source outcomes remain `OTHER_SOURCE`; genuine unknowns remain `UNKNOWN_SOURCE`; verified Ads source without a campaign mapping remains `ADS_UNMAPPED`. An omitted class defaults only to Ads when a campaign is present and unknown when null. Never use null to hide known organic/other-source evidence. Media spend is always Ads scope and uses `ADS_UNMAPPED` if its campaign is missing.
- Timestamp-aware, inclusive-start/exclusive-end reporting; windows must use Dubai-day boundaries because the spend grain is daily. All money inputs are nonnegative integer minor units, while refund-driven negative net contribution is allowed. Final and intermediate money arithmetic reject unsafe integers. Zero denominators return null.
- Period spend per period first qualification is descriptive. Both campaign and account ratios are withheld while any supplied qualification history is unresolved. Verified counts and spend remain available. The campaign ratio requires a mapped Ads campaign. Unmapped Ads counts and spend still contribute to the account-level period ratio when eligible. No cohort CPQL, new-collected-customer CAC, mature funnel rate, pipeline ROAS, payback or collection-lag conclusion is inferred.

Remaining requirements: finance owner and approved actual treatment; verified ledgers/export permissions and full-history canonical person audit; stable receipt/cost transaction IDs; dedup against prior exports and provider reversals; actual source freshness and cohort linkage; different segments' economics; consent-eligible conversion import rules. The prototype neither edits financial records nor transmits financial or contact data to Google.

## Executed whole-history audit

`commercialReportFromHistory(financeInput, policy, historyOptions)` now integrates the existing [qualification audit](../../qualification-history/README.md#commercial-report-integration) with these calculations. `financeInput` has the existing verified finance/export/window/completeness fields, without `qualifications` or `qualification_audit`. Base finance-policy, verified-export and source-completeness blockers return before any private history file or interpreter is accessed.

`historyOptions` has exactly `python`, `ledger_path`, `source_review_path` (a private absolute path or explicit null), `business_review_path` and `now_utc`. The evaluation clock is explicit UTC (`Z` or `+00:00`) with at most six fractional digits, matching Python's microsecond precision; sub-millisecond changes invalidate receipt reuse. Select an existing reviewed **trusted Python executable**. The two required history files and optional source review must be regular files outside the source checkout. The business-review contract binds exact source bytes, complete-history review, an authoritative retention-history marker and an actual evidence freshness window. The audit and core/schema/classifier hashes are pinned in `history-bridge.mjs`; changed producer bytes require review and a deliberate pin update.

The bridge executes the actual bounded Python audit, checks input hashes before/after execution and against its provenance, limits combined stdout/stderr to 2 MiB and execution to 30 seconds, suppresses child stderr and produces an immutable in-memory receipt. Handwritten JSON, a deep clone or independently supplied first-ever booleans cannot enter this executed-audit branch. WeakSet branding and byte hashes are call/provenance controls, not authentication of an arbitrary chosen executable or proof that source assertions are true. The caller must protect its runtime, code and input custody and supply an accurate evaluation clock.

The same canonical person is counted once across all roles over the entire supplied history before filtering inclusive Dubai dates. An earliest tie or other unresolved historical business hold anywhere blocks the audited report. Truncated/replaced files fail exact-byte binding; stale/future review, incomplete/unreviewed history and unknown/incomplete retention markers hold it. The 10,000-row bound cannot represent larger genuine history by taking a recent slice; that requires a separately reviewed ingestion design.

Audited counts preserve Ads, other and unknown sources independently of optional advertising permission or export readiness. Native-campaign counts derive only from the existing validated source-review rows. They appear under `qualification_evidence.native_campaign_counts`; they are not mapped to invented `BSRE-Cxxxx` identities. Audited Ads totals enter `ADS_UNMAPPED`, so mapped campaign qualification ratios stay null while eligible account-level descriptive spend ratios can be calculated. Missing source evidence remains unknown and cannot become Ads demand.

The old row API remains available for existing explicitly verified callers and synthetic tests; its output says `CALLER_ASSERTED_ROWS_NOT_AUTHENTICATED`. The integrated branch says `EXECUTED_PINNED_LOCAL_HISTORY_AUDIT`, carries fixture classification and still states `source_truth_independently_verified:false` and `google_upload_supported:false`. All results remain offline and unreconciled with the provider. No Google-ready source, genuine import, release approval, production access or approved finance treatment is inferred. The advertising queue is not an input to this business report.

```javascript
import {commercialReportFromHistory} from './report.mjs';
const report = await commercialReportFromHistory(reviewedFinanceInput, reviewedFinancePolicy, {
  python: trustedPythonExecutable,
  ledger_path: privateFullHistoryPath,
  source_review_path: privateSourceReviewPathOrNull,
  business_review_path: privateBusinessReviewPath,
  now_utc: actualEvaluationTime,
});
```

The helper returns aggregate report data without raw person, lead, outcome, contact or click records. Its `qualification_evidence` retains the aggregate schema, evaluation/review times and byte/component provenance alongside the native-campaign counts. Finance aggregates, source dates/counts and evidence hashes can still be private business information; do not publish them or transmit them to Google. It does not write report files, send messages, schedule work or change either ledger. A local receipt must be freshly generated for its exact evaluation clock and report window; it is not a reusable source certificate.

Run `node --test commercial-system/report.test.mjs` from the parent directory. All records, dates, amounts and approvals in tests are explicitly synthetic; no actual performance is represented. Source requirements are Master Plan v3 sections 15–16 and 19. The source pack's illustrative arithmetic is not used as the company's policy or forecast.

Run `python -B -m unittest discover -s tools/qualification-history -p 'test_commercial_integration.py' -v` from the repository root for the actual Python → Node → pinned Python path. Tests use temporary labelled synthetic files and a trusted local interpreter. They cover count/source/campaign reconciliation, original-first window ordering, permission independence, history/tie/retention/freshness holds, exact-byte truncation rejection, receipt replay/window rejection, private path boundaries and unchanged finance prerequisites.

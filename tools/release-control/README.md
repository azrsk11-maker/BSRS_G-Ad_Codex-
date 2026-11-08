# Release packet review

This read-only tool checks the internal consistency of a proposed production release. It **always returns `execution_allowed:false` and `release_authorized:false`**, including for a completely consistent packet. JSON assertions cannot authenticate the owner, a reviewer, business evidence, provider state or deployment permissions. There is no network client, deployment job, credentials store or production writer.

This implements part of Master sections 18/21/24 and [the repository governance contract](../../docs/GOVERNANCE.md). It does not close the open [owner decisions](../../docs/decisions/OWNER_DECISIONS.md) or the live acceptance gates. The seven additional named gates summarize source truth, keyword scope, durable routing/retry, retention/recovery, staffing, qualification history and scoped rollback. They supplement the supplied WT tests; the supplied specification files are unchanged.

## Checks

- Separate `WEBSITE_PUBLICATION`, `TRACKING_PUBLICATION`, `ADS_CONFIGURATION` and `ADS_ACTIVATION` actions. Website/tracking records cannot carry media authority; an Ads configuration request cannot silently enable campaigns.
- Exact reviewed Git commit, clean checkout, bounded artifact hashes and membership in that commit. Ignored files cannot masquerade as reviewed source. Evidence is separate from source artifacts to avoid a commit/hash cycle.
- Stable `BSRE-C0001`–`BSRE-C0360` / `BSRE-LP0001`–`BSRE-LP0360` pairs; unique native page IDs, campaign IDs and same-origin canonical URLs. These are validation rules, not fabricated live mappings.
- Exact known GA4/GTM destinations, version transition, normalized configuration diff and launch privacy/bidding constraints. Unknown change operations are held; the diff cannot contradict safe-mode summaries. Actual conversion-action semantics/labels and raw tag payloads still require authenticated evidence and review.
- Current four new campaign IDs only, all four for activation, exact account/budget pools and before/after state. At least the 16 frozen legacy campaigns remain paused/removed and unchanged. Broader cohorts or a replacement baseline require a reviewed policy revision after owner decisions; do not silently expand this allowlist.
- Evidence bound to proposal digest, commit, full page scope, reviewer, method, observation time and expiry. Missing, partial, expired or unit-test-only results cannot close runtime gates. The approval window cannot outlive the evidence.
- Independent approval of the exact PR head and both required check names. Owner decisions and the separate release statement bind the exact proposal/packet. Local identity strings remain unauthenticated.
- Rollback versions and page scope, preservation of accepted records/outbox, no old-campaign reactivation, retention reapplication and the adopted 30-day recovery window.

Website/tracking preflight requires WT-001 through WT-030 and the seven additional gates. WT-031/032 require actual publication/readback evidence and remain **post-publication obligations**, not manufactured preflight passes. Ads actions require that publication evidence already exists. Production readback must still follow every authorized operation. A consistent packet is not evidence that a deployment happened.

The current policy retains the Master's full 14,000/14,000 reviewed-count gate. Owner issue #1 must resolve the pilot-versus-full-library question before any relaxation is designed and reviewed. Historical draft candidates do not satisfy it. All seven currently open owner decisions are held by this initial packet policy; future applicability changes require review.

## Ads activation evidence

Collect fresh evidence in account 573-038-4686. Bind each result to the proposal and reviewed commit, and capture the source and observation time before reducing it to the packet fields.

The campaign language field is held pending [owner decision #11](https://github.com/azrsk11-maker/BSRS_G-Ad_Codex-/issues/11). Google documents automatic language matching for Search and says legacy language criteria do not govern serving. A dash in the UI or a legacy API criterion cannot certify English-only targeting. A bounded scan of the dated launch inventory found no non-Latin letters in 114 ad copy components and 82 keyword rows, and identified six distinct native destinations. This is a script check for review. It does not establish English language quality, the language of the current landing pages, or audience eligibility. [Google Ads language criteria](https://developers.google.com/google-ads/api/docs/targeting/criteria?hl=en#language_targeting_criteria)

| Check | What the operator verifies | Packet result |
|---|---|---|
| Campaign inventory | Match all four launch IDs and the [frozen legacy inventory](../../docs/audit/CAMPAIGN_STATUS_BASELINE_2026-11-07.json). Read the existing Search settings, CPC caps and AED 1,200 / 400 / 300 / 100 average daily split. | Campaign before/after records differ only by the four status changes. Legacy campaign rows retain their recorded Paused or Removed status. |
| Brand | Read the exact Brand ad and its landing URL from the Ads table. Use the policy approval status. Ad strength is a separate field. | `BRAND_POLICY` binds account, campaign, ad group, ad, URL and Approved status. |
| Ad groups, ads and keywords | Export the reviewed children by campaign. Compare the exact IDs and parent assignments to the [ad](../../docs/audit/ACCOUNT_AD_URL_READBACK_2026-11-07.json) and [keyword](../../docs/audit/KEYWORD_URL_READBACK_2026-11-07.json) inventories. Use entity status. A paused parent can prevent serving even when a child is enabled. | `SERVING_CHILDREN` records exact enabled IDs and the per-campaign split for six groups, six ads and 82 keywords. |
| Account and effective assets | Compare the [17 account holds](../../docs/audit/asset-audit-2026-11-07/README.md) by Item ID. Inspect inherited associations that can apply to the four campaigns. | `ASSET_HOLDS` records paused statuses and the count of unreviewed effective assets. |
| Automation | Inspect rules, scripts, solutions and auto-apply. Identify relevant manager-level automation and external writers with the account owner. | `AUTOMATION` covers all those surfaces. A missing readback leaves the gate open. |

The dated campaign and keyword readbacks showed paused children. If a fresh readback confirms that state, prepare a separate configuration proposal while the parent campaigns are paused. Keep the preflight evidence open until the relevant operation has explicit authorization and a verified readback.

## Use

```text
python -B -m unittest discover -s tools/release-control -p "test_*.py"
python -B tools/release-control/release_packet.py <private-packet.json> --root <clean-checkout>
```

The CLI prints a compact JSON result to stdout. Exit 0 means only `packet_consistent:true`; it never means "deploy". A release mechanism must independently verify the exact owner comment, author and current permissions, PR/check states, revocations, evidence and protected environment approval immediately before the exact separately authorized action. **No such release mechanism is provided here.**

The envelope has `schema_version`, `proposal`, `evidence`, `review`, `decisions` and `approval`. First hash the proposal with `digest()`. Evidence and decisions reference that digest. Then hash the envelope excluding `approval`; the owner's exact action statement names that packet digest. Code artifacts belong to the reviewed commit. Post-commit evidence can be kept in an ignored/private location within the evidence checkout; hashes are pinned in the packet. Publish only a sanitized review record to GitHub; never upload private source evidence or client data.

Tests build clearly synthetic fixtures in temporary directories and exercise the complete shape. These are test inputs, **not approved releases or usable production records**. No synthetic fixture is submitted to Google. Metadata JSON is limited to 2 MB; artifact hashing streams files up to 64 MB so full provenance-bearing keyword files can be reviewed without loading them into context. Unsafe paths, symlinks, duplicate JSON keys, nonfinite numbers and unsupported file types are rejected. Artifact/evidence provenance is structural only; source truth remains an independent acceptance obligation.

Production approval, actual WordPress builds, provider/runtime acceptance, Ads configuration semantics, staff capacity and the complete keyword masters remain blocked. A local consistency check and a green CI run must never be represented as production readiness.

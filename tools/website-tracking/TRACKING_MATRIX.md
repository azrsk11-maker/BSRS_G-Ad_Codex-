# Page tracking evidence review

This read-only validator implements the page-level matrix in Master/Addendum 24.7 and the per-page independent evidence requirement in 24.8.9. It closes a consistency gap: a global WT PASS receipt naming every page cannot substitute for recorded outcomes for each page. It performs no network requests, submissions, deployment or provider verification. Every result retains `evidence_authenticated:false`, `execution_allowed:false` and `release_authorized:false`.

## Release packet binding

The existing `WT-002` receipt must reference both `page_tracking_inventory` and `page_tracking_matrix` using the existing `{path, sha256}` file-reference shape. The inventory must also be a proposal artifact whose exact hash belongs to the reviewed commit. The evidence matrix is separate post-commit evidence, avoiding a commit/hash cycle. Existing exact-head CI, human PR review, owner decisions, source-truth, rollback and separate release approval checks still apply.

The inventory has exactly `schema_version:1`, `target_origin` and `pages`. Each inventory page contains the proposal's exact `page_id`, `campaign_key`, `campaign_id`, `wordpress_page_id` and `url`, plus:

- `gtm_container_id`, positive integer `gtm_version`, `ga4_web_stream_id`, `ga4_measurement_id`;
- `conversion_action_mapping` with `operational_event:form_accepted`, `ga4_event:generate_lead`, the explicitly reviewed `ads_action_id`, and `ads_route:NATIVE_ADS_SECONDARY`;
- the complete `cta_inventory`, each entry containing `cta_id`, `placement` and `destination`.

Do not create this inventory from assumed live IDs, invented CTAs or unreviewed page content. Existing accepted-action selection and source binding remain owner/reviewer obligations; this module supplies no action-selection default. Known GTM/GA4 identifiers come from the repository's existing verified identifier observations, and a tracking publication must match its proposed `version_after`. The module does not establish fresh ownership or installed runtime configuration.

The evidence matrix has exactly `schema_version:1`, `proposal_sha256`, `commit`, `target_origin`, `production_synthetic_conversions:0` and `pages`. Each page repeats the exact inventory fields and adds:

- `results`: individual `{test_id,status,evidence_ref}` outcomes for WT-002, WT-005–008, WT-010–026 and WT-028–030, exactly once each;
- `reviewer`, `method`, `observed_at_utc`, `valid_until_utc`, and a page-specific opaque `evidence_ref`;
- `journey_correlation`, with `acceptance`, `email` and `sheet`, each containing `lead_sha256` and `source_sha256`;
- a `status` and `evidence_ref` on every CTA inventory entry.

All three journey records must hash the same immutable Lead ID and permitted source context, including an explicit unknown source where appropriate. Each page needs its own accepted test journey and evidence section reference. Hashes and references are consistency links, not authenticated receipts. Keep real journey evidence private; do not commit lead rows, click IDs, personal contact details or raw payloads. CLI reports omit those inputs.

Every required page/CTA result must be PASS before `acceptance_complete` can become true. Unknown configuration may be null, and unexecuted outcomes retain `NOT_EXECUTED` with null references and review metadata; these remain pending. PASS requires authenticated-staging or native-browser-network methodology, named independent evidence, observation after proposal creation and before the enclosing WT-002 review, and validity covering the enclosing receipt. A reviewer matching the known last pusher is rejected case-insensitively. A staff reviewer need not have a GitHub account. Claimed identity, independence and test execution remain unauthenticated.

WT-001/003/004/009/027 remain separate existing global gates. WT-031/032 remain existing post-publication gates. Reviewers must inspect the underlying evidence for every required journey variant, actual CTA completeness, correct configuration/action selection, noindex/crawlability, direct/missing-source operation, consent choices, invalid submissions, duplicate/retry cases, outage recovery, mobile behavior and existing main-site regression. Matrix consistency alone proves none of these ran.

## Execution and limits

Normal integration is `python -B tools/release-control/release_packet.py <private-packet.json> --root <reviewed-checkout>`. One bounded Node invocation validates the complete matrix per packet. Missing Node, timeout, invalid output, changed hashes, missing pages/outcomes or incomplete evidence hold the packet.

For isolated tooling, export `validateTrackingMatrix(matrix, context)` or use `node tools/website-tracking/validate_tracking_matrix.mjs --stdin` with exactly `{matrix,context}` on stdin. Context supplies the exact proposal hashes/resources, reviewed `inventory`, `expected_tracking_ids`, nullable `expected_gtm_version`, `operator`, `pusher`, and the proposal/enclosing receipt timestamps. This interface reads no files and writes only a sanitized JSON summary to stdout. It never accepts a previously computed PASS summary as evidence.

Release metadata files are capped at 2 MB each; stdin is capped at 4 MB, with up to 360 pages, 128 CTAs per page and a 15-second subprocess deadline. Maximum-size field combinations may exceed the byte caps and must be reduced to opaque references. The synthetic 360-page boundary test exercises every per-page field and all required outcomes without creating any real acceptance record.

Focused checks: `node --test tools/website-tracking/validate_tracking_matrix.test.mjs` and `python -B -m unittest discover -s tools/release-control -p test_release_packet.py`.

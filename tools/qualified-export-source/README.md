# Private qualified-outcome source preparation

This functioning local candidate stages a minimal, durable owner-review queue in SQLite. It reuses the unchanged Outcome40 schema and existing qualification validator. It has no network client, Google credentials, scopes, uploader, spreadsheet writer or production adapter. All outputs remain `UPLOAD_PROHIBITED`.

The queue reserves candidates passing local checks against supplied evidence. It does not authenticate a genuine business outcome, a staff reviewer, source completeness, original consent, installed producer integrity or a Google account. Review flags and exact-byte hashes are attestations, not independently verified facts. No actual private source has been accepted by these synthetic tests.

## Admissible future source and current hold

The [pinned tracking review](../../docs/audit/TRACKING_CONFIGURATION_READBACK_2026-11-08.md#restricted-scheduling-compatibility-review--9-november) identifies Google's [Sheets source guide](https://support.google.com/google-ads-data-manager/answer/15146000?hl=en-AU), [field/time requirements](https://support.google.com/google-ads-data-manager/answer/14184381?hl=en) and [connection credentials/schedules](https://support.google.com/google-ads-data-manager/answer/13944739). Those repo findings support a dedicated workbook's first tab with reviewed column mapping of an unchanged GCLID and the actual qualification time with timezone. They do not pin an accepted native header list, actual restricted credential grant, configured schedule, click/action-window eligibility or successful import for account 573-038-4686. [Pinned research](../../docs/audit/research-evidence.md) also records Google's duplicate identity as GCLID, conversion name and conversion time, and the current API-migration caveat.

Consequently this module emits **no Google-ready source file**. It preserves the existing `GCLID_INTERNAL_REVIEW_PREVIEW_NOT_UPLOAD_FORMAT` prohibition and creates a separately labelled `PRIVATE_QUALIFIED_OWNER_REVIEW_QUEUE_NOT_GOOGLE_SOURCE` artifact. Its internal JSON keys are not proposed Google headers. It invents no provider IDs, values, timestamps or lead outcomes, and does not turn the existing prohibited preview into upload rows. The existing Outcome40 order ID is only a private identity cross-check here; support for mapping it to a future connector remains unverified.

Future acceptance still requires the actual original permission/capture producer, authoritative full-history and retention-journal readbacks, a verified provider mapping and conversion window, account/action ownership, an isolated dedicated-export grant, diagnostics/reconciliation and separate production authorization. A broad Drive/Sheets grant reaching the intake workbook fails the restricted-route gate. Keep scheduling and immediate imports held; no manual/API fallback is supplied.

## Evidence contract

All five inputs are regular contact-free JSON files, read with the existing bounded/no-follow reader (10 MiB each; at most 10,000 records per list). Unknown fields, duplicate JSON keys and nonfinite numbers are rejected. No raw contact-bearing workbook is accepted.

1. `ledger`: the exact [qualification-history envelope](../qualification-history/README.md#input-contract), containing the entire available history and unchanged Outcome40 records. Actual `fixture_only`/`history_complete` booleans and a real complete-history evidence reference are required. No date-window slice is accepted.
2. `purpose`: a list with exactly the existing `qualification_core.PURPOSE_FIELDS`, joined to original intake lead IDs. Include genuine historical permission/capture evidence and current observations, withdrawals and expiry. A matching same-evidence/GCLID snapshot must establish permission no later than its capture time, which must precede the actual qualification. A late readback alone leaves `ORIGINAL_PERMISSION_AT_CAPTURE_NOT_ESTABLISHED`; it is not proof that consent was newly granted. Supply trusted original coverage evidence for legitimate historical readbacks; never invent/backdate observations to satisfy this check. Both permission-mapping and producer trust remain external acceptance gates.
3. `binding`: exactly `customer_id`, `conversion_owner_customer_id`, `conversion_action_id`, `conversion_name`, `mapping_verified`, `stage_key`, `identifier_route`. The existing core requires account 573-038-4686, action 7878013428, exact `qualified_lead` name/stage and `GCLID_ONLY`. Accepted-enquiry actions, contact matching and audience routes are rejected.
4. `retention`: exactly `schema` (`bsre-qualified-retention-review-v1`), `fixture_only`, `ledger_sha256`, `history_incomplete`, `history_marker_verified`, `history_marker_evidence_reference`, `history_marker_read_at_utc`, `records`. The marker must be a reviewed readback of the authoritative [retention journal's `historyIncomplete()`](../closed-enquiry-retention/Workflow.php) rather than inferred from the remaining workbook rows. Unknown/unverified markers hold the queue. A true marker permanently latches the local completeness gap. Each `records` row has exactly `outcome_id`, `closed_at_utc` (UTC Z or null), `retention_due_at_utc` (UTC Z or null for an open case), `review_verified` and an opaque `evidence_reference`. Closed cases require a deadline no later than twelve calendar months after actual closure. Effective local expiry is the earliest supplied permission expiry or retention deadline. Missing per-outcome retention evidence holds the candidate.
5. `review`: exactly `schema` (`bsre-qualified-preparation-review-v1`), `fixture_only`, `ledger_sha256`, `purpose_sha256`, `binding_sha256`, `retention_sha256`, `whole_history_reviewed`, `permission_mapping_reviewed`, `reviewer_reference`, `evidence_reference`, `reviewed_at_utc`. Hashes are SHA-256 of the four original file byte streams, including formatting; they are not reserialized-object hashes. The two review flags must reflect actual review and be true. The review must follow the supplied history/permission/retention observations. References must be opaque letters/digits/colon/underscore/hyphen, beginning with a letter; never use names, contact details or private paths.

Fixtures must stay explicitly labelled and use a separate database. A database cannot switch between fixture and business classification. The fixtures in the tests use false `is_test` solely to exercise local eligibility inside an outer `fixture_only:true` envelope. They must never be imported into any production system.

## Durable behavior

The complete-history business audit runs before candidate selection can be accepted. An unresolved historical business hold vetoes every candidate, including an otherwise eligible different person. The existing core selects the earliest qualification across all supplied roles before applying separate permission gates; later enquiries cannot replace an earlier ineligible first qualification. Tied earliest outcomes hold review.

SQLite transactions and unique original person/outcome reservations suppress unchanged retries across process restarts and concurrent connections. Payload identity includes the exact original GCLID, original Outcome40 occurrence string (fractional seconds preserved), reviewed action/name and existing order ID. Changing a reserved event, timestamp, GCLID or person binding permanently holds that reservation; there is no automatic replacement, timestamp adjustment or re-key operation.

Local owner review binds to the exact five-input snapshot. Any changed source bytes invalidate it. `project` re-runs the complete-history, permission, withdrawal and expiry checks immediately before reading the same reviewed snapshot transactionally. Approval of this private queue never claims that Google imported or accepted anything. No external-import success operation exists.

Withdrawals are checked across all supplied leads joined to each person, including when that person's current qualification is business-ineligible. They permanently latch while the bounded reservation exists and erase its stored GCLID/payload. Removing withdrawal evidence, replacing an evidence ID or regranting permission cannot revive that reservation.

`purge` and every fresh staging run remove expired private reservations. A purge, missing formerly reserved person or authoritative incomplete-history marker sets a durable **aggregate** gap. No hashed-person tombstone is kept. The gap cannot be reset through this API, prevents all new private reservations and prevents projection/review. Even a later true history flag or extended permission/retention deadline cannot recreate deleted private mappings. Do not create a fresh database to evade a known history gap; the authoritative retention marker must carry that condition into any replacement deployment.

## Private custody and operation

Database and projection paths must be outside the source checkout; an existing unrelated SQLite database, nonregular target or symlink file is rejected. New files use mode `0600` where supported. **That is not verification of Windows owner-only ACLs, encryption, parent-directory access or backup custody.** All artifacts explicitly report private-storage access as unverified. Private/production deployment remains held until a separately reviewed directory/file ACL, encryption and cleanup procedure is accepted. Do not supply real source data to an unverified storage location.

SQLite uses transactions, `secure_delete` and deleted rollback journals rather than a retained WAL. These settings do not prove forensic erasure, SSD erasure or deletion from snapshots/backups. Queue purge removes rows from this database only. Dated JSON projections, evidence extracts, journals/backups outside the live database and any copied files require their own bounded custodial deletion/recovery procedure. A projection carries a review expiry and `requires_fresh_reconciliation`; it must never become an ingestion source or be reused after withdrawal/expiry.

Use an already approved private directory. The following variables refer to actual reviewed files and immutable IDs; no directory, evidence or approval is manufactured by these commands. Substitute the available Python 3 executable.

```powershell
$evidence = @('--ledger', $ledgerPath, '--purpose', $purposePath,
  '--binding', $bindingPath, '--retention', $retentionPath, '--review', $reviewPath)
python -B tools/qualified-export-source/source_queue.py stage --db $privateDb --now $now @evidence
python -B tools/qualified-export-source/source_queue.py review --db $privateDb --now $now `
  --outcome-id $actualOutcomeId --snapshot-sha256 $stagedSnapshotHash --reviewer-reference $actualReviewerReference
python -B tools/qualified-export-source/source_queue.py project --db $privateDb --now $now @evidence --output $newPrivateReviewPath
python -B tools/qualified-export-source/source_queue.py purge --db $privateDb --now $now
```

`stage`, `review` and `purge` print aggregate status only. `project` prints only aggregates and writes an explicitly requested new private JSON review file with identifiers; it never overwrites an existing output. Do not log that file. Rejection exits 2 with a bounded code that contains no supplied values or paths. Exit 0 can still include holds and never denotes provider readiness. The CLI does not schedule itself; fresh eligibility, regular cleanup and retained evidence remain operational acceptance work.

## Focused verification

```powershell
python -B -m unittest discover -s tools/qualified-export-source -p 'test_*.py' -v
```

Tests create temporary labelled synthetic evidence/SQLite only. They cover restart and concurrent idempotency, exact GCLID/microsecond preservation, action binding, complete-history holds, owner-review invalidation, changed identity, historical-permission coverage, withdrawals through ineligibility/regrant, expiry, purge gaps, authoritative retention markers, no resurrection, transaction rollback, custody boundaries and leak-free rejection. No real source, Google call, import acceptance, Windows ACL acceptance or deployed producer acceptance is claimed.

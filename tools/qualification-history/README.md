# Qualification history audit

Read-only local entry point for the historical standalone intake and Outcome40 model. It audits an explicitly supplied, contact-free JSON extract and prints an aggregate JSON report. It performs no network calls, uploads, ledger writes or file exports.

From the repository root, run with the available Python 3 interpreter.

```powershell
$auditPython = Join-Path $env:USERPROFILE '.codex/tools/jcodemunch/venv/Scripts/python.exe'
& $auditPython -B tools/qualification-history/audit_history.py --ledger C:/private/ledger.json --now 2026-11-08T12:00:00Z
```

Optional `--from-day` and `--to-day` accept inclusive Dubai dates in `YYYY-MM-DD` form. Supply the entire available history even when selecting a reporting window. The validator chooses each person's earliest qualification before filtering dates.

Optional `--source-review C:/private/source-review.json` accepts the existing `bsre-qualified-source-review-v1` contract in `qualification_sources.py`. Its SHA-256 binding must match the exact ledger file bytes. Without reviewed source evidence, source counts remain `UNKNOWN_SOURCE`. Click IDs alone never establish Ads attribution.

The output also includes selected-window Dubai-day/source aggregates and, where the existing native source classifier accepts the evidence, day/native-campaign counts. Native campaign IDs are aggregate evidence only; no `BSRE-Cxxxx` mapping is inferred. Every earliest qualification is selected over full supplied history before the reporting window. Earliest ties outside the selected window also withhold whole-history completeness.

## Input contract

The ledger object allows only these keys.

- `fixture_only` and `history_complete` must be actual JSON booleans. The caller must distinguish synthetic fixtures from business records.
- `history_evidence_reference` is a private evidence reference or null. It is omitted from the report. Missing/empty evidence prevents a complete-history claim. Whitespace-only evidence is rejected.
- `intake` is a list of minimal original intake projections, containing exactly `lead_id`, `role`, `accepted_at_utc` and `is_test`. Contact fields and other extra intake keys are rejected.
- `records` is a list of objects conforming to the preserved 40-property [outcome schema](schema/outcome-register-schema.json). Required and optional properties are defined in that schema. Do not pass the raw workbook or map displayed cell positions without first verifying its headers.

Each input must be a regular file, with symbolic links and special files rejected before opening. Where supported, the reader also opens with nonblocking and no-follow flags, validates the opened descriptor and verifies file identity. Each input file is limited to 10 MiB. Intake, outcome and source-review lists each allow at most 10,000 supplied rows. Duplicate JSON keys, nonfinite numbers, malformed JSON, unsupported fields and conflicting joins receive rejection or documented holds. A file changed while being read is rejected.

The command emits no identifiers, person keys, click identifiers, staff notes, evidence values or private paths. Success exit code `0` means the audit completed. The report may still contain holds. Rejection exits with `2` and a bounded error code. No output-file option is provided.

## Interpretation and preserved behavior

The original business validator supplies schema checks, role-specific staff-confirmation requirements, original/canonical intake joins, test exclusions, one-person/one-canonical validation, whole-history first-qualification ordering and source grouping. Cross-role repeat enquiries may share a canonical person, while each outcome must match its own intake role. Unchanged retries are deduplicated. Conflicting outcome IDs and canonical mappings hold the affected person.

The report separates unambiguous qualifications found in the supplied history from a staff-attested complete-history total. `truth_independently_verified` is always false. A complete-history total is available only for non-fixture input with complete-history evidence and no unresolved business holds. This tool cannot establish the truth or completeness of the source evidence.

The following deliberate restrictions apply around the historical validator.

- Distinct outcomes tied at the earliest qualification time are excluded from the unambiguous aggregate and hold the staff-attested total. Historical reporting selected one deterministically while holding its export.
- Any unresolved business hold withholds the overall staff-attested total, including when the held record falls outside the selected date window. Test, duplicate and non-qualification exclusions remain separately counted.
- The reporting wrapper supplies no permission/export binding and discards the historical preview and identifier-bearing lists. It does not certify conversion readiness or create import records.
- Strict envelope types, file/row limits, generic failure handling and whitespace-evidence rejection are enforced before returning aggregates.

Source-review holds affect source attribution. They do not change the separate business-qualification count or grant measurement permission.

## Commercial report integration

The existing [commercial report](../website-tracking/commercial-system/README.md#executed-whole-history-audit) now has an executable local integration rather than requiring hand-transcribed first-ever flags. It runs this exact audit through a reviewed, trusted Python interpreter and consumes a frozen aggregate receipt. It never consumes the advertising-eligible queue, permission preview or a Google source file. Advertising permission, withdrawal and export readiness do not define the business count.

For that path, add `--business-review C:/private/business-review.json` and explicit inclusive `--from-day`/`--to-day`. The bounded private review object has exactly these fields:

- `schema`: `bsre-business-history-review-v1`; `fixture_only`: the same actual boolean as the ledger.
- `ledger_sha256` and `source_review_sha256`: SHA-256 of the original file bytes; the latter is null when no source review is supplied.
- `all_available_history_reviewed`: an actual boolean attesting that the entire available history was reviewed. The maximum 10,000-row input bound does not authorize selecting the latest 10,000 rows. If genuine full history exceeds this bound, production reporting remains held until a separately reviewed bounded ingestion design is available.
- `retention_history_incomplete`: the authoritative retention journal's actual boolean marker, or null if unknown; `retention_marker_verified`: actual boolean for its reviewed readback. Unknown/unverified or incomplete history holds the commercial path. Remaining workbook rows alone cannot establish this marker.
- `observed_at_utc` and `valid_until_utc`: actual timezone-aware review times. The owner determines the evidence window; the module invents no source-freshness policy. Review must cover the supplied recorded history and be current at the explicitly supplied evaluation clock. Processing an old snapshot now does not refresh its review.
- `reviewer_reference` and `evidence_reference`: opaque references beginning with a letter and using letters/digits/colon/underscore/hyphen, maximum 150 characters. Never use names, contact details or paths.

The resulting `commercial_qualification_aggregate` is `PRIVATE_BUSINESS_AGGREGATE_REVIEW_ONLY` and always `UPLOAD_PROHIBITED`. It contains day/source/native-campaign counts, current holds, selected-window metadata, exact source/review byte hashes and hashes of the executed validator, unchanged core, classifier and Outcome40 schema. It contains no person, lead, outcome, contact, staff-note, evidence-reference or click records. Aggregate business counts and provenance can still be private business information; do not publish or send them to Google.

Hashes bind bytes and the executed-code receipt binds this local call. Neither authenticates the interpreter, reviewer, completeness assertion, retention journal, native attribution or underlying business truth. Those production acceptance gates remain open. The caller must select a reviewed trusted Python executable and protect the source/input directory from concurrent untrusted modification. The Node bridge checks input bytes before/after the audit, checks pinned producer bytes and rejects handwritten/cloned JSON receipts. This does not turn an arbitrary caller-selected executable into a trusted runtime.

Fixture aggregates remain labelled `fixture_only:true`; their raw staff-attested genuine total remains null. Synthetic offline arithmetic through this branch is illustrative and never a production result. Existing finance-policy approval and sanitized-export requirements still apply independently.

## Provenance and verification

[source-provenance.json](source-provenance.json) records SHA-256 hashes of the owner-supplied historical validator, source classifier and schema, plus the derived files. `qualification_sources.py` and the schema are byte-for-byte copies. `qualification_core.py` retains the original business core, removes its write/export CLI and adds a reporting wrapper. The private native Apps Script producer and its identifiers are excluded.

Run the focused synthetic tests from the repository root.

```powershell
& $auditPython -B -m unittest discover -s tools/qualification-history -p "test_*.py" -v
```

Tests cover cross-role deduplication, date-window ordering, schema/boolean failures, history uncertainty, conflicts, ties, test exclusions, source evidence binding, private-field rejection, leak-free reports/errors and bounded CLI input. Real workbook acceptance, source-evidence review, import validation and production release remain separate gates.

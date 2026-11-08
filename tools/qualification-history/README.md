# Qualification history audit

Read-only local entry point for the historical standalone intake and Outcome40 model. It audits an explicitly supplied, contact-free JSON extract and prints an aggregate JSON report. It performs no network calls, uploads, ledger writes or file exports.

From the repository root, run with the available Python 3 interpreter.

```powershell
$auditPython = Join-Path $env:USERPROFILE '.codex/tools/jcodemunch/venv/Scripts/python.exe'
& $auditPython -B tools/qualification-history/audit_history.py --ledger C:/private/ledger.json --now 2026-11-08T12:00:00Z
```

Optional `--from-day` and `--to-day` accept inclusive Dubai dates in `YYYY-MM-DD` form. Supply the entire available history even when selecting a reporting window. The validator chooses each person's earliest qualification before filtering dates.

Optional `--source-review C:/private/source-review.json` accepts the existing `bsre-qualified-source-review-v1` contract in `qualification_sources.py`. Its SHA-256 binding must match the exact ledger file bytes. Without reviewed source evidence, source counts remain `UNKNOWN_SOURCE`. Click IDs alone never establish Ads attribution.

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

## Provenance and verification

[source-provenance.json](source-provenance.json) records SHA-256 hashes of the owner-supplied historical validator, source classifier and schema, plus the derived files. `qualification_sources.py` and the schema are byte-for-byte copies. `qualification_core.py` retains the original business core, removes its write/export CLI and adds a reporting wrapper. The private native Apps Script producer and its identifiers are excluded.

Run the focused synthetic tests from the repository root.

```powershell
& $auditPython -B -m unittest discover -s tools/qualification-history -p "test_*.py" -v
```

Tests cover cross-role deduplication, date-window ordering, schema/boolean failures, history uncertainty, conflicts, ties, test exclusions, source evidence binding, private-field rejection, leak-free reports/errors and bounded CLI input. Real workbook acceptance, source-evidence review, import validation and production release remain separate gates.

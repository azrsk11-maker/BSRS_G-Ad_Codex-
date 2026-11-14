# Per-choice retention planning candidate

This is a pure, versioned, disabled-by-default **synthetic review planner**, separate from the unchanged [RetentionInventory](../RetentionInventory.php) and its existing database controller. It has no apply method, WordPress hook, database/provider client, scheduler, file-data reader, deletion or reopening path. Existing runtime behavior and provenance pins are unchanged. No genuine source, business approval or production eligibility is established.

```php
PerChoicePlanner::plan($snapshot, $coverage, $now, $enabled = false);
```

The disabled result inspects no source rows. Explicit enablement still produces only `SYNTHETIC_REVIEW_ONLY`, with `execution: NONE`, `apply_supported: false`, `source_authenticated: false` and `production_authorized: false`.

## Inputs and evidence boundary

`snapshot` uses the original helper's exact `SYNTHETIC_INCOMPLETE` shape and consent-store columns: `kind`, `state`, `history`, `captures`, bounded to 1,000 total rows. The original helper performs schema, scalar and calendar validation; its conservative classifications are not reused as the new per-choice policy. Valid database unsigned-number strings are normalized internally. A bounded scalar-only copy prevents the original normalizer from mutating caller-owned PHP references.

`coverage` has exactly:

| Field | Value |
|---|---|
| `kind` | `SYNTHETIC_PER_CHOICE_COVERAGE_V1` |
| `snapshot_sha256` | `PerChoicePlanner::digest($snapshot)` |
| `status` | `COMPLETE_SYNTHETIC` or `UNKNOWN` |
| `observed_at` | Whole Unix seconds when the supplied fixture was observed |
| `valid_until` | Explicit supplied fixture-evidence expiry, exclusive |
| `history_pruned` | Boolean; true holds all choice candidates |

The evaluation clock is explicit positive Unix seconds through 2100-01-01 UTC. Observation must not be future or predate any supplied row; expiry must follow observation and remain current. The planner does not choose a real source-freshness interval. A snapshot mismatch, unknown/expired coverage or prior pruning holds all choice candidates. Extra fields such as `verified_live: true` are rejected.

`COMPLETE_SYNTHETIC`, the marker, timestamps and digest are caller-supplied fixture assertions, **not authenticated completeness or a source certificate**. A production caller cannot use them to waive actual provenance, custody, lineage or permission acceptance. The digest sorts map keys, preserves list order and original scalar types, and is an object hash rather than a raw-file hash. Hashing is bounded by depth, node count and size; objects, cyclic/deep structures and nonfinite values fail with a constant error code.

## Review behavior

- Each choice uses its own original `changed_at` plus twelve Dubai calendar months. Leap-day anniversaries clamp to 28 February. Reaching the exact boundary can classify an otherwise unreferenced row `DUE_UNREFERENCED_SYNTHETIC_REVIEW`. Rechecking or retrying does not restart the original deadline.
- A newer active choice does not by itself hold unrelated older history. The current state and its matching current history remain held while the 180-day preference is active. Unknown preference windows, gaps, time regressions, uncertain choices or inconsistent current/history state hold the subject.
- A consistently linked accepted or staged capture protects current permission authority and **every history revision from the earliest referenced capture onward**. This retains the original decision plus later withdrawal/regrant history; it does not merely retain the first and latest rows. History strictly before that necessary interval may still be due for review. Submitted evidence stays outside this never-submitted-choice route and needs the separate closure-based retention workflow.
- A claimed original capture must precede the next choice revision as well as its preference expiry. At the next choice's exact second, ordering is ambiguous and the whole subject remains held. Processing/retries must preserve the original capture timestamp; a later processing clock neither invalidates a valid earlier capture nor resets its evidence interval.
- Unresolved capture lineage holds the subject. An unlinked capture, cross-subject receipt conflict, reused history receipt or duplicate/conflicting capture request holds all subject-exclusion conclusions. An unchanged retry of the same input is deterministic; duplicate exported rows are not silently counted as new evidence or deduplicated into an authoritative source.
- Capture rows always remain `PROTECTED_CAPTURE_OUTSIDE_SCOPE`; no capture is a choice-retirement candidate. Delivery state never becomes proof that a capture can be deleted.

## Results and limitations

The result contains exact private row references, classifications, individual Dubai deadlines, constant reason codes, counts and input/plan digests. Keep it private for any non-test data; do not post its rows, identities or source hashes to GitHub, Google or project memory. The tests use fabricated identifiers and print only a synthetic scope, aggregate check count and false authority flags.

`DUE_UNREFERENCED_SYNTHETIC_REVIEW` is **not a deletion manifest or approval**. No existing controller consumes this result. Applying selective history removal would require a separately reviewed writer, preservation of current authority and submitted evidence, authenticated complete lineage/linkage and a method for reconciling resulting history gaps. The planner intentionally holds already missing/pruned history rather than assuming absent rows were safely retired. A local counter cannot prove that a subject never submitted an enquiry.

Actual closed-enquiry/email retention, current withdrawal authority, provider recovery, external history custody and separately scoped production authorization remain unresolved outside this candidate. No production retention compliance or reopening readiness is claimed.

Run focused synthetic checks only:

```sh
php -l tools/consent-retention/per-choice/PerChoicePlanner.php
php tools/consent-retention/per-choice/test_per_choice.php
```

The 55 checks cover independent deadlines, active current choices, leap boundaries, accepted/in-flight and withdrawal history, next-choice capture boundaries, missing/cross-subject evidence, retries, coverage binding/freshness, pruned history, bounded malformed input, scalar normalization, caller immutability and absence of execution authority. They do not perform native/provider acceptance or validate real records.

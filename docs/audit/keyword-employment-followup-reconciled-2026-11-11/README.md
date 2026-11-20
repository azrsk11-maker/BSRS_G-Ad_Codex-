# Employment follow-up: canonical source reconciliation and preliminary review

The two source captures each contain the **same 444 normalized phrases**. They preserve **888 actual source occurrences**, not 888 distinct research keywords. This review retains both source hashes and resolves every canonical identity through the source-bound reconciler; the original captures, projections and preliminary previews remain unchanged.

## Current evidence and assessment

A complete `current_negative_library.reconstruct()` verified **10,014 eligible negative research records and 15,309 protected queries** on 11 November 2026. Each source batch has 24 exact current-negative overlaps, 45 exact protected-query overlaps, and **375 novel, unprotected phrases**. This is a dated observed membership snapshot. A later admission must reconstruct the current register again; this file is not an acceptance cache.

Every one of the 375 novel complete literals was read individually. The [preliminary review](review.json) covers all 444 canonical identities:

| Preliminary outcome | Canonical phrases |
|---|---:|
| Full-literal EXACT negative-review proposals | 191 |
| HOLD | 235 |
| Existing-negative occurrence only; no new row | 18 |
| Unassessed | 0 |

All **79 disagreements** between the two earlier previews remain HOLD. They comprise 65 first-negative/second-hold and 14 first-hold/second-negative assessments. Six of the 24 existing-negative overlaps participate in those disagreements: this new preliminary review holds them without editing, deleting, reapproving or admitting their existing library records. The remaining 18 contribute source occurrences only.

The 191 proposals use explicit job, career, occupational-entry or named-role-vacancy wording. They propose only the complete observed literal as EXACT for later scope review. They assert no current employer identity, vacancy, affiliation, jurisdiction, service coverage or real-estate inventory fact. No generic housing, job, caretaker, officer, salary or role token is proposed as a broad or phrase exclusion.

Holds preserve existing protections; role descriptions and client-service/hiring ambiguity; live-in accommodation or residential-vacancy ambiguity; unclear entities/acronyms; incomplete or unusual wording; and observed token-order variants. No corrected spelling, generated permutation or newest-preview-wins rule is used. Shared token groups are source observations, not Google concept or matching certification.

## Provenance and reproducibility

`source_refs` pins both capture manifests, public projections, raw-export hashes and original preview files. Each review record's `canonical_id` is `KW-` plus the SHA-256 of its exact normalized phrase. The source reconciler retains both physical source-line bindings, exact original texts and original preview assessment objects.

From the repository root, `tools/keyword-system/followup_reconciliation.py` supplies `load_sources()` and `reconcile_sources(inputs)`. Resolve this review's identities against that output before relying on its counts or source links. This review intentionally references the reconciler instead of copying all source/provenance arrays again.

Run its focused source/authority/conflict checks with:

```powershell
python -B -m unittest discover -s tools/keyword-system -p test_followup_reconciliation.py
python -B tools/keyword-system/followup_reconciliation.py --review docs/audit/keyword-employment-followup-reconciled-2026-11-11/review.json --output test-output/followup-review-new.json
```

The CLI output must be a new file in an existing directory; an existing destination is refused. It validates the dated ID-to-membership snapshot and both pinned sources, leaves current-library membership unverified, and prints only aggregate counts. The 16 focused cases include source/identity/count tampering, conflict and protection bypasses, authority changes and source/output alias guards. Local results: 15 passed and one Windows symlink capability skip in 0.245s; the hardlink case executed. Existing keyword test discovery runs these cases automatically.

A source-binding check compared all 444 review IDs, normalized/original texts, preview states, both source descriptors, count totals and false authority flags with the freshly reconciled source objects. It confirmed all 79 conflicts held, all 375 novel records assessed and zero master contribution. The current-library report hash also matched. This verifies artifact binding and controls; semantic judgment remains preliminary AI work.

The baseline verification used for this snapshot took **23.772161 seconds**. That is a single observed execution duration, not a controlled performance comparison, token saving or whole-project speedup. One earlier oversized diagnostic output was discarded after truncation and replaced by compact source/membership output; no review evidence was built from truncated data.

## Required next step

The proposals remain preliminary AI work. Scope, protected-intent checks, distinctness/variant review, business evidence where required, independent human review and the existing admission pipeline must pass before any library addition. Both 14,000 targets and the four-campaign release holds remain in force.

**Master contribution: zero positive rows, zero negative rows, zero approved exclusions and zero deployments.** This work changed only these new review artifacts. Production, Google Ads, tracking, access, the original lead workbook and financial records were not changed.


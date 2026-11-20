# Authentic Keyword Planner discovery - 8 November 2026

Four authenticated discovery batches in Real Estate account573-038-4686 returned8,778records containing7,705distinct normalized phrases. All remain unreviewed ideas. They contribute **zero** reviewed, approved or deployed positives or negatives. The14,000/14,000delivery targets remain unmet; these counts are not a partial claim of master acceptance.

| Batch | Input seeds | Export rows | Per-batch distinct |
|---|---:|---:|---:|
| Buyers |10|3,326|3,326|
| Residential rentals |10|4,415|4,415|
| Sellers/landlords/brokers |10|345|345|
| Commercial purchase/leasing |10|692|692|
| Combined observations |40|8,778|7,705 across batches|

There are1,073repeated occurrences in1,038cross-batch overlap groups. Original rows remain in their source batches; no preferred metrics or master records were silently selected. Normalization uses the existing keyword-system NFKC/casefold/whitespace and matching-wrapper rule. This is lexical identity, not Google's close-variant grouping or independent search demand. Do not sum volumes across rows or infer leads, qualifications, revenue or actual CPC.

## Verified research context

- Location:United Arab Emirates; language:English; network display:Google.
- Last12months preset; all four export date headers are **1October2025-30September2026**. Do not replace this with an inferred October2026window.
- Exclude adult ideas remained the default active filter. No website filter supplied.
- Exact ten seeds for each batch are preserved in that batch's JSON. Seeds are research hypotheses, not approved keywords or inventory statements.
- The account banner showed no ads running. Research did not create/modify/enable a serving campaign, change campaign settings/budgets or commit spending. No keyword was added to a serving campaign. Discovery may keep non-serving draft metadata; no numeric plan ID is asserted.
- Issue1 is still open with no new owner cohort approval recorded. Its independent research path remains authorized. No cohort, page mapping, publication or launch decision is inferred.

The final commercial capture uses the verified ten commercial seeds and692rows. An intermediate mixed owner/commercial771-result view was corrected and was not exported or counted.

## Privacy and exactness

Each batch contains a projection from its immutable private UTF-16BOM/tab-separated download. `capture.json` records original basenames, byte counts, rawSHA256, public-fileSHA256 and aggregate reconciliation. Original downloads and native UI evidence remain private outside the source checkout; no raw export, account performance, contact, prospect or financial record is committed.

All values of five account-specific columns are excluded: **Ad impression share**, **Organic impression share**, **Organic average position**, **In account?**, **In plan?**. Their column names remain in schema/provenance metadata, but their cells never enter record values. The other21column labels and nonempty strings are preserved exactly; blank cells become null. Top-of-page bid estimates retain those labels and are never relabeled actual CPC.

The tenant seed `dubai apartment rental` has no separate exact export row. Grouping remains null; no other row's estimate is assigned to it. Missing exact rows do not establish zero demand. The other39seed inputs have exact corresponding rows in their own exports.

These ideas may include competitor/portal brands, irrelevant intent, unavailable property/entity references or excluded Business Setup topics. No automatic positive/negative admission, semantic review, inventory verification or exclusion scope is assigned. Existing reviewed `tools/keyword-system/data/` masters and historical staging remain unchanged. Both reviewed masters still contain zero rows.

## Verification

The offline importer rejects malformed/bounded input, unknown/duplicate headers, unsupported dates/encoding, bad widths and blank/control keywords. Fourteen synthetic parser tests cover privacy and exact preservation. `verify_capture.py` pins every public JSON, checks schema/privacy, counts, seed reconciliation, zero-authority controls and the distinct union. Required CI verifies public consistency only; raw source equality needs the private downloads.

```sh
python -B docs/audit/keyword-discovery-2026-11-08/verify_capture.py
python -B docs/audit/keyword-discovery-2026-11-08/verify_capture.py --source 'buyers=<private-export>' --source 'tenants=<private-export>' --source 'owners=<private-export>' --source 'commercial=<private-export>'
```

Parent execution verified all four private originals against their public projections. Renaming a private archive copy does not change its byte/checksum evidence. No private path is required in this repository. This verifies exported data preservation, not the truth of a provider estimate, semantic business suitability, source freshness admission, current campaign/page ownership, protected-intent approval or deployment permission. Current-head CI and PR8reports govern later executions.

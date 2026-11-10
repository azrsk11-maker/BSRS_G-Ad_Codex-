# Focused seller/landlord discovery - 8 November 2026

## 11 November executable transcription

The existing [intent review](INTENT_REVIEW.md) already covers all 31 phrases. Its new pinned [workbench](workbench.json) and [proposals](proposals.json) preserve twelve conditional Dubai positive candidates and nineteen holds, with zero negatives or unassessed phrases. The two commercial-owner phrases remain held as explicitly required in that narrative; fourteen possible owner roles do not mean fourteen admitted positive records. All service/admission gates remain unverified. No source phrase, raw capture, existing placement or master entry changed. Run `python -B docs/audit/keyword-discovery-supply-2026-11-08/verify_triage.py`. [Cross-source reconciliation](../keyword-review-coverage-2026-11-11/README.md) retains the overlapping phrase independently.

Two separate research submissions in verified Real Estate account **573-038-4686** returned **31 provider rows / 31 distinct phrases**. Twenty rows are the supplied seed hypotheses returned exactly; eleven are additional provider ideas. This is not a claim of 31 newly discovered owner-intent queries, actual search terms or approved keywords.

| Batch | Supplied seeds returned exactly | Additional ideas | Export rows |
|---|---:|---:|---:|
| Seller-focused | 10 | 8 | 18 |
| Landlord-focused | 10 | 3 | 13 |
| Total | 20 | 11 | 31 |

All records remain unreviewed for business admission. Zero reviewed/approved/deployed/master records were added. No live campaign, budget, keyword, tracking, website, sharing or financial-record change was made.

## Observed context and source fidelity

Both submissions used UAE location, English, Google network, Last 12 months, the existing adult-ideas exclusion and no website filter. Both original UTF-16 CSV headers specify **1 October 2025 - 30 September 2026**; that actual header wins over an inferred later twelve-month window. Each batch JSON preserves the exact confirmed seed-chip order, the ten supplied seeds, UI count and every original public string/null and physical source line.

The five account-specific cell columns are discarded entirely from record values. Twenty-one public column labels/values remain. Raw downloads, exact private copies, native account evidence and screenshots stay outside this public repository. Source basenames, byte counts and SHA256s bind the original files without publishing machine paths or raw account cells. Both private files were checked cell-for-cell against these projections; CI can prove public consistency only.

`capture.json` uses distinct counters for all repeated occurrences, all duplicate-phrase groups and true cross-batch overlap. A peer review caught an ambiguous earlier count label before publication; the helper and nine focused tests now distinguish an isolated within-batch duplicate from cross-batch overlap. The original four-batch capture has no internal duplicates and remains unchanged.

## Source yield and limits

The seller batch's eight additional ideas concern Sharjah property-sale listings; they do not establish owner acquisition intent. The landlord batch adds `dubai estate agent`, `rental agents dubai` and `dubai letting agents`; their owner-versus-tenant role is unresolved. First-person and landlord-agent seed wording can be an owner-service hypothesis, but it is not evidence that a real owner searched it, that Black Swan supports the service/location, or that the phrase passed factual admission.

This narrow source experiment has limited marginal owner-vocabulary yield. Sparse results do not prove low demand. Do not repeat near-identical seed variants or manufacture phrases to satisfy a quota. Additional owner/customer language must come from authorized, appropriately redacted business sources; supported service/geography, inventory/mandates, language, destination and claim reviews remain necessary. Owner issues #1 and #2 remain relevant. No private enquiry text or contact details should be posted in public issues.

## Overlap without inherited classifications

| Source measure | Count |
|---|---:|
| Original distinct phrases | 7,705 |
| Supplemental distinct phrases | 31 |
| Shared with original | 1 |
| Supplemental-only distinct phrases | 30 |
| Combined distinct phrases | 7,735 |
| Combined source occurrences | 8,809 |
| Total repeated occurrences | 1,074 |

The one shared phrase is `dubai letting agents`. The 30 supplemental-only records comprise twenty returned seed hypotheses and ten additional provider ideas. These are source identities, not independent demand, reviewed-master contributions or additional placements. Do not sum provider volumes/CPC estimates across rows or infer performance.

`overlap.json` includes only the 31 supplemental phrase forms and all relevant original/supplemental source references, plus counts and the original manifest hash. Original-only occurrences are reconstructed from their existing capture rather than duplicated here. No estimates, service decisions or authority are inherited. The original 7,705 classifications and source pins remain byte-identical; this supplement does not silently extend or rewrite the completed original-corpus workbench.

## Exact exported phrase inventory

The entries below describe source provenance only. They carry no business admission or owning campaign/page mapping.

| Batch | Physical source line | Phrase | Source role |
|---|---:|---|---|
| sellers | 4 | sharjah villa for sale | Additional provider idea |
| sellers | 5 | sharjah property for sale | Additional provider idea |
| sellers | 6 | apartments for sale in sharjah | Additional provider idea |
| sellers | 7 | flats for sale in sharjah | Additional provider idea |
| sellers | 8 | freehold villa for sale in sharjah | Additional provider idea |
| sellers | 9 | sharjah house for sale | Additional provider idea |
| sellers | 10 | sharjah freehold property for sale | Additional provider idea |
| sellers | 11 | flat for sale in sharjah al nahda | Additional provider idea |
| sellers | 12 | sell my property dubai | Supplied hypothesis returned exactly |
| sellers | 13 | sell property sharjah | Supplied hypothesis returned exactly |
| sellers | 14 | sell my apartment dubai | Supplied hypothesis returned exactly |
| sellers | 15 | sell my villa dubai | Supplied hypothesis returned exactly |
| sellers | 16 | list my property for sale dubai | Supplied hypothesis returned exactly |
| sellers | 17 | property selling agent dubai | Supplied hypothesis returned exactly |
| sellers | 18 | sell my house in dubai | Supplied hypothesis returned exactly |
| sellers | 19 | sell my commercial property dubai | Supplied hypothesis returned exactly |
| sellers | 20 | sell my property abu dhabi | Supplied hypothesis returned exactly |
| sellers | 21 | list property for sale abu dhabi | Supplied hypothesis returned exactly |
| landlords | 4 | dubai estate agent | Additional provider idea |
| landlords | 5 | rental agents dubai | Additional provider idea |
| landlords | 6 | dubai letting agents | Additional provider idea |
| landlords | 7 | rent out my property dubai | Supplied hypothesis returned exactly |
| landlords | 8 | rent out my apartment dubai | Supplied hypothesis returned exactly |
| landlords | 9 | rent out my villa dubai | Supplied hypothesis returned exactly |
| landlords | 10 | find tenants for my property dubai | Supplied hypothesis returned exactly |
| landlords | 11 | landlord letting agent dubai | Supplied hypothesis returned exactly |
| landlords | 12 | property letting services dubai | Supplied hypothesis returned exactly |
| landlords | 13 | lease my commercial property dubai | Supplied hypothesis returned exactly |
| landlords | 14 | rent out property abu dhabi | Supplied hypothesis returned exactly |
| landlords | 15 | landlord agent abu dhabi | Supplied hypothesis returned exactly |
| landlords | 16 | property letting agent sharjah | Supplied hypothesis returned exactly |

## Verification and boundaries

`verify_capture.py` pins the new batches and manifest, independently verifies the original capture, checks the unchanged original classification hashes, and reproduces the compact overlap report. The shared helper validates exact schemas, context, privacy, line/duplicate/seed identities, totals and zero authority. Optional private originals distinguish public consistency, partial private equality and complete private equality; verifying one file cannot authenticate both.

```sh
python -B docs/audit/keyword-discovery-supply-2026-11-08/verify_capture.py
python -B -m unittest discover -s tools/keyword-system -p test_supplemental_discovery.py
```

`--source sellers=PRIVATE_PATH --source landlords=PRIVATE_PATH` supplies the two original files for full private equality. Do not commit those paths or files. Required foundation runs the public verifier and helper tests. Tests establish capture/overlap correctness, not commercial eligibility, platform matching or live conversion acceptance.

The [fresh status/budget readback](../ADS_PAUSED_READBACK_2026-11-08.json) observed all twenty campaigns: 17 paused, three removed, zero enabled. The four V2 average budgets remain AED1,200/400/300/100, totaling AED2,000 average/day. That readback verifies only status and displayed budgets, not CPC limits, goals, policy, automation, staff capacity or release readiness. No advertising was enabled.

Both 14,000 reviewed-master targets remain at zero. The full native-page, measurement, private-routing, lifecycle, commercial, review and deployment requirements remain open; source research does not authorize production publication or Ads spending.

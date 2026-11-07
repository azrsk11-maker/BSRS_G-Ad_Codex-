# Historical keyword seed intake

Prepared 7 November 2026. The original owner's ZIP contains **82 draft placements representing 41 distinct normalized positive phrases**, not 82 unique research phrases. Those records are now available for GitHub review in [the staged intake](../../tools/keyword-system/staging/historical-intake.json).

All records remain unapproved historical candidates. **Reviewed positives: 0/14,000; approved: 0; deployed by this intake: 0.** No new 360-slot campaign/ad-group/page assignment, demand metric, review date, freshness deadline or live-state assertion was inferred. The reviewed master under `data/positive.json` remains unchanged and empty.

## Preserved evidence

The intake preserves every original keyword CSV field and its exact metadata join, including historical campaign/ad-group names, match type, paused source statuses, role, proposed destination, readiness text, reason and original `NOT VERIFIED` live-account evidence. Each record links to its archive member, record ordinal and physical CSV line span. Candidates retain original text variants and every placement reference. Normalization only groups the 41 Exact/Phrase pairs; it does not overwrite original text.

| Original draft dimension | Placements |
|---|---:|
| Brand | 8 |
| Buyers | 34 |
| Tenants | 16 |
| Owners | 24 |
| **Total** | **82: 41 Exact + 41 Phrase** |

These are source labels, not verified current account assignments. The original names differ from the later V2 campaign names. Existing imports must not be recreated or replayed from this file. Proposed source URLs remain historical proposals even where a current route separately exists.

Provenance is checksum-pinned:

- Original ZIP SHA256: `08a689590b812cd7eac46baf8a5e1fe23f2ced94168d8982012498e003c84794`.
- `campaigns/keywords.csv`: 7,863 bytes; SHA256 `87eefba1d96fbdde0b7a83dee5d0bb36c4c3ad8516f5ca5ac37c7166a0e5646f`.
- `campaigns/keyword-metadata.csv`: 24,507 bytes; SHA256 `80da168affeedbec3a81b6c035df605025b48b13f2ecb089f83e203727f1918e`.
- The `full-scope/campaigns/keywords.csv` duplicate is byte-identical and was not counted twice.

The importer reads only those three known CSV members, with size/hash checks, and extracts no archive files. No archive, private lead data, personal machine paths or secrets are copied into this repository.

## Contract and validation

[historical_intake.py](../../tools/keyword-system/historical_intake.py) and [its staging schema](../../tools/keyword-system/historical-intake.schema.json) deliberately use a separate intake contract. The reviewed keyword contract requires current evidence, review and campaign/page ownership; weakening it to accept these unverified records would overstate progress. A negative-control test proves these candidates still contribute zero reviewed rows to the existing validator.

The importer fails on changed source hashes, duplicate/missing metadata joins, lost/reused placements, altered draft status, introduced mappings/metrics/reviewer values and false completion/approval claims. [Intake result](../../tools/keyword-system/staging/intake-validation.json) reports only staging integrity, not keyword quality or release acceptance.

The final combined targeted run passed 48 tests (15 new intake tests and 33 existing keyword tests) in 0.046 seconds. This measured test duration excludes tool startup. Artifact readback verifies the recorded SHA256. A Windows newline mismatch found during verification was repaired by explicit LF output and a scoped Git attributes rule, with a regression assertion on the saved artifact hash. No external calls, Google conversions or production changes occurred. The existing jCodeMunch index was consulted; known-file checks were then used for the narrow contract boundary.

Independent review found and prompted repairs to two structural checks: the validator now rejects source-envelope/hash/freshness relabeling, and it rederives candidate identity order from original placements to prevent reordered records being silently renumbered. Regression cases cover both. Pinned archive reading was already enforced by the importer; these repairs strengthen verification of the saved staging artifact.

## Next independent review work

### Negative candidate recovery — 7 November 2026

The separate [negative staging](../../tools/keyword-system/staging/historical-negative-intake.json) preserves 27 original placements as **nine distinct, unapproved phrases**. Both original members are byte-identical: `campaigns/negative-keywords-candidates.csv` and `full-scope/campaigns/negative-keywords.csv` under `black-swan-implementation/`. Each is 5,532 bytes, SHA256 `3a388e1b46a5e083d07b9f97624618bd889ea2f71753deb21d3866f7f64e3257`.

Original campaign/ad-group, match type, scope, risk, reason and `CANDIDATE ONLY` fields are historical claims, not current approved exclusions. Current mappings and review facts remain null. Reviewed, approved and deployed negatives remain zero; the researched-negative deficit remains 14,000. No prior negative wording is automatically safe to deploy.

The importer pins the original ZIP, both members and canonical original records; it reads/hashes/parses one bounded archive snapshot. Fifteen focused tests and independent review verified counts, mutation rejection, exact staging reproduction and source-preserving output guards. Extra independent hardlink tests passed; Windows denied symlink creation, so that extra path case is not claimed locally. [Validation receipt](../../tools/keyword-system/staging/negative-intake-validation.json). Output SHA256: `740b9e74e0a02ef263807f62a457b1ee7f5fef2caf984f75fca9c031898d8fd4`.

### Current-evidence review

1. Review each original phrase for current Real Estate service/entity relevance, language, grammar and overlap. Source provenance does not establish current demand or inventory.
2. Collect permitted source evidence with real review dates and expiry rules. Leave unmeasured volume/CPC null; unknown metrics alone are not a reason to invent estimates.
3. Resolve the new campaign/ad-group/page ownership through the approved crosswalk and existing [owner decision #1](https://github.com/azrsk11-maker/BSRS_G-Ad_Codex-/issues/1). Do not parse old campaign names into new IDs.
4. Build protected intent cases for the valid buyer, tenant, seller and landlord queries before proposing exclusions. Keep pending candidates separate from reviewed and approved counts.
5. Promote only individually reviewed records through a later deliberate transformation; this staging importer offers no promotion or Ads export operation.

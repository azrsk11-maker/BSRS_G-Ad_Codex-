# Ofqual occupational-title research admission

The complete negative research library is **11,170 / 14,000; deficit 2,830**. This append-only cohort adds **207 AI-reviewed complete qualification titles / 214 exact source occurrences**. Positive admission, exclusion approval and deployment remain **zero**. Independent human approval and actual live applicability remain unverified. [Complete result](library-report.json), [cohort result](cohort-report.json), [source-bound admission review](review.json), [measured evidence and limits](review-metadata.json).

## Source and independent reading

The unchanged [source extraction](../keyword-ofqual-occupational-2026-11-12/README.md) preserves 524 actual occurrences / 517 normalized full titles from the already captured, hash-verified official Ofqual CSV. Selection has an explicit occupational-topic and published-status boundary, with all earlier 338 property-projection ordinals excluded. No research quota, shortened text, generated wording, provider-prefix removal or new download determined the selection.

The separate [independent AI review](../keyword-ofqual-occupational-2026-11-12/semantic-review.md) reads every complete literal in the 296 length/word-precheck groups. It proposes 207 groups / 214 occurrences and holds 89: 88 for documented symbols and one for occupational-service ambiguity. The original 221 full-title length/word holds remain unchanged. All **310 held groups / 310 occurrences** receive source-labelled protection; these are unresolved research controls, not observed queries or verified service eligibility.

Fresh reconciliation compared all 517 source groups with **every complete current negative, archived negative and protected-query body**, using normalized exact identity, ordered tokens, equal token bags and closed alphanumeric strings. No additional conflict, alias hold or existing protection overlap was found. The 207 selections reproduce the peer reading without forcing that preliminary count. The prior eight-index diagnostic remains separately labelled as a snapshot and was not reused as admission acceptance.

The corrected implementation executes **2,068 external key joins and 2,068 within-source key joins across all 517 groups**, including the 310 already held groups. Existing-negative peers under any of the four methods hold the whole new admission rather than removing old records. Independent code review identified an earlier scope gap: only the 207 proposals received all external joins despite the broader claim. The linked metadata records the superseded hashes. This correction received a new complete baseline, regenerated source-bound review/output pins and new focused tests; the earlier result was not reused to accept the repair.

All seven same-title duplicate groups retain their actual, distinct qualification numbers, original CSV record ordinals and physical line ranges. Each admitted record preserves every selected source occurrence and its original full title/status, source and raw-CSV hashes, and admission/independent-review references. Source qualification status establishes neither actual course delivery nor UAE recognition, local availability, demand, provider affiliation or a brokerage service. Metrics and observed queries remain unknown. Token diagnostics are not Google matching certification.

## Preservation and scope

The caller reconstructed and verified the complete **10,963-record apprenticeship baseline** freshly in the generating process. Its full-input SHA256 `4db6a3a93ac0b7f4015cb2e329898b5446aa947586e2880b98b02537941373ac` remained unchanged. Every prior record body, ordering, provenance, historical marker, all 18 archives, 24 sources and the complete 16,383-protection prefix remain preserved. The result has **16,693 protections, 25 sources and 11,383 retained exact source occurrences**. No serialized baseline, acceptance cache or historical source rewrite was used.

New records remain **EXACT / HIGH / PENDING**, only for the existing unbound residential-rental planning purpose **BSRE-C0301 / BSRE-LP0301**, RNT slot 1. Actual URL, Google campaign ID, exclusion approval and release authority remain unset. Other 359 planning slots and the four live campaigns are not newly bound. The unchanged public rental intake purpose supplies no inventory, service coverage, staff, delivery or conversion acceptance.

The unchanged category targets allocate these 207 records to ACADEMIC, now **1,883 / 2,000; 117 remaining**. There is no target transfer, media-budget change, new owner approval or exclusion export. Both full 14,000-keyword libraries and all business, service, consent, history, provider, staffing, independent-human and separate production release gates remain required. Production, permissions, private workbook, finance and Ads are unchanged; advertising stays paused.

## Verification and entrypoints

The adapter reuses the existing append-only stage and complete generic auditor unchanged. It rereads pinned source, extractor, independent review, service context, scope registry and matching/compatibility code. It recomputes the derived cohort and new protection tail before checking saved output hashes. Changed or resealed source facts, authority, scope, chronology, whole-base markers, derived records and malformed protections fail closed.

`current_negative_library.reconstruct()` and `verify()` now freshly verify the complete history and this stage. The new `reconstruct_apprenticeship_snapshot()` and `verify_apprenticeship_snapshot()` preserve the frozen 10,963-row API. All earlier snapshot APIs and `_fresh_apprenticeship_state` remain unchanged. Fourteen public entrypoints retain fresh-history guards.

Measured in one ephemeral Python 3.12.14 process:

| Check | Result | Seconds |
| --- | --- | ---: |
| Fresh complete prior baseline | PASS; all original inputs checked | 63.935617 |
| Source-bound review and all 517 full-body variant checks | PASS; no additional holds | 0.966875 |
| Complete generic-audited output generation | PASS | 5.172985 |
| Twelve focused tests over that same fresh base | PASS; zero failures/errors | 32.629857 |
| Separate fourteen-entrypoint freshness guard | PASS; one test | 0.273 |

The focused tests include actual historical prefix/body preservation, complete provider provenance, every source hold, conservative conflict handling, source/peer tampering, resealed authority/scope/date/tail changes, real generic-auditor rejection of malformed protection, unchanged category targets and fresh public dispatch. The additional regression introduces external protected/archive/current aliases for a pre-held title and verifies all executed comparison counters. Same-process baseline reuse is limited to that live generating/test process. There is no persisted acceptance state. The unchanged aggregate keyword deadline is 300 seconds, with at most two workers; these individual timings do not predict combined CI performance or claim a speedup.

Current-source combined Foundation, native CI, independent human and live acceptance remain **pending**. The root integration owns those acceptance runs; no earlier green check is reused to accept this new revision.

Reproduce from the repository root using the verified Python runtime:

```powershell
python -B -m unittest discover -s tools/keyword-system -p test_ofqual_occupational_admission.py
python -B tools/keyword-system/current_negative_library.py
```

The first command independently reconstructs its complete baseline when no fresh same-process generator supplies one. `build_outputs(base, root, when)` accepts only the exact caller-fresh full baseline, generates in memory and performs the real complete audit; it has no filesystem, network, Google or production writer.

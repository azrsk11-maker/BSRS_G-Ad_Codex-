# Ofqual occupational-title source extraction - 12 November 2026

**296 distinct normalized full titles / 303 original source occurrences pass the local length and word-count precheck. They are unreviewed source candidates, not newly admitted research.** An additional **221 complete titles / 221 occurrences remain held** because of length or word count. Current-library novelty and admissible counts are unknown. Admission, approved exclusions and deployment remain zero.

The source is the already captured official [Ofqual Qualifications CSV](https://downloads.find-a-qualification.services.ofqual.gov.uk/extracts/Qualifications.csv), linked by the [official download index](https://www.gov.uk/find-a-regulated-qualification). The exact private source bytes were freshly checked before extraction: **23,984,795 bytes**, SHA256 `ec3d5f789e14dd07fcc8a46b61e46a5d4f103ac84b6a6fd3330fcc94211409d5`. This extraction makes no new network request. The original 11 November capture, published source HTTP dates and licence provenance remain bound in [capture.json](capture.json); the raw CSV and local machine path remain private.

## Meaning and coverage boundary

The selection reads all **53,175 actual CSV records**, with the 36 exact headers, duplicate qualification-number checks and the original complete-source status totals. It selects complete official qualification titles with an explicit hair, beauty, barber, nail, makeup, culinary, catering or food-safety expression and the exact source-published status **Available to learners**. The eight original regular expressions are explicit in [extract.py](extract.py) and [qualifications.json](qualifications.json). This topic/status boundary was chosen before the definitive candidate count and does not truncate to an admission quota or research-pool balance.

All **1,744** topic-matching occurrences are accounted for: **524 Available to learners, 72 No longer available to new learners, 1,146 No longer awarded and 2 Not yet available to learners**. The 1,220 occurrences outside the selected published status are counted but not projected as this cohort. All 338 source ordinals from the preceding property-title projection are explicitly excluded; their overlap with this selected cohort is zero. No earlier source, review, hold, protection, master or register is modified.

The selected **524 occurrences / 517 normalized titles** are all retained, including every complete locally overlong title. The existing `keyword_audit.normalize` helper is imported unchanged. Seven duplicate normalized-title groups account for seven repeated source occurrences; all original provider qualification numbers, title spellings, CSV record ordinals and physical source-line ranges remain present. No representative is discarded, variant generated, spelling corrected, provider prefix removed or title shortened. Grouping is not route, alias, concept or Google matching clearance.

The conservative local precheck uses each original full title, **at most 80 characters and 10 whitespace-delimited words**. It passes 303 occurrences / 296 normalized titles and holds 221 occurrences / 221 titles. There are 98 occurrences over 80 characters and 220 over 10 words, with overlap. These counts replace the exploratory PowerShell estimate; the authoritative result uses Python CSV parsing, the actual project normalizer and Python `str.split()`. No Google acceptance or complete platform-compatibility claim is made.

## Evidence and limits

Each retained record preserves the same ten exact public metadata fields used by the preceding Ofqual projection: complete qualification title and number, awarding organisation, level, type, subject area, published status and three original operational/certification dates. Source metadata establishes neither actual course delivery nor UAE recognition, current local availability, legal eligibility, provider affiliation or a brokerage service. Published qualification titles are official references, not observed queries or search demand. Volume, CPC and competition remain unknown.

Only the complete original literal can be considered for later EXACT research review. Semantic intent, actual current-master/archive membership, protected-query and campaign/page scope, provider-prefixed forms, route aliases, token peers, symbols and compatibility all remain pending. Legitimate property demand, business premises, service-provider due diligence, licensing/recognition guidance and other unresolved intent remain protected. No campaign, page, Google ID or exclusion scope is selected here.

The subsequent **committed-index snapshot diagnostic is not admission acceptance**: eight existing index-file hashes were checked, and their union/removals reconcile **10,963 eligible identities / 18 archived identities**. None of the 296 candidate normalized-title identities exactly matches either set. No nonidentical ordered-token, equal-token-bag or closed-alphanumeric peer group occurs within the new 296-title cohort. These checks do not cover the complete current external literal bodies, 16,383 protected queries, external aliases or campaign scope; a fresh complete baseline remains required for admission.

The existing `keyword_text_compatibility.profile_text` helper separately flags **88 of the 296 titles for documented invalid symbols**, leaving **208 with no known local incompatibility detected** before semantics and all other checks. Those 88 require HOLD; punctuation must not be removed to manufacture eligible wording. The frozen source-only projection remains unchanged, so its narrower length/word precheck still reports 296. This diagnostic adds zero research rows and establishes no platform acceptance.

Current committed research allocation is **ACADEMIC 1,676 / 2,000; 324 slots remaining**, while the total negative-research deficit is 3,037. These are context, not admission authority or a selection quota. No target transfer, media-budget change, current-library reconstruction, source registration or master addition was performed. Full independent semantic review and a fresh complete admission baseline are required before claiming an increment. Production and Ads remain unchanged, with advertising paused.

## Reproduction

From the repository root, use the verified Python runtime:

```powershell
python -B docs/audit/keyword-ofqual-occupational-2026-11-12/extract.py
python -B docs/audit/keyword-ofqual-occupational-2026-11-12/extract.py --source PRIVATE_PATH
```

The first command verifies public structure, complete-literal metadata, counters, exclusions, original source/projection pins, extractor bytes and both dependency hashes. It does not authenticate omitted private raw bytes. The second freshly hashes and parses the complete pinned private CSV and requires byte-for-byte deterministic equality with the saved projection. The optional `--write-new --source PRIVATE_PATH` mode exclusively creates the two JSON files and refuses existing outputs; it never overwrites an earlier artifact. No current-library code path, network client or production writer is present.

Fresh complete private raw hash/reprojection verification passed in **7.508235 seconds**. Separate public-only verification passed in **0.054632 seconds**. Five in-memory public-integrity checks rejected an altered title, an ordinal from the old 338-row projection, an altered published status, a dropped source record and a production-authority flip. All four new source-extraction files are verified UTF-8 with LF newlines. These are individual measured host executions and bounded checks, not speedup, token-cost, full Foundation, human-review, native or live acceptance claims. The three hashed files below, alongside this README, are the complete source-extraction write scope; the separately assigned independent semantic review has its own files.

| File | Bytes | SHA256 |
| --- | ---: | --- |
| extract.py | 16,708 | `c37a98859e1865d543e82c43886608b63f265b0ac3d44725fd52bdc30ab199ed` |
| qualifications.json | 646,710 | `8cdd1a1e0475857b1fc7473734756da9bb20b2229890c61d639ee41ed6dac91c` |
| capture.json | 5,257 | `85c9a3ed815c72a8bfc3966fdaa016aec64063e43c4dd352e59e5504fa61530e` |

Contains public sector information licensed under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/), except where otherwise stated. The original [Ofqual register licence notice](https://find-a-qualification.services.ofqual.gov.uk/find-regulated-qualifications) and third-party exceptions remain applicable. No affiliation, endorsement or unrestricted third-party rights are inferred.

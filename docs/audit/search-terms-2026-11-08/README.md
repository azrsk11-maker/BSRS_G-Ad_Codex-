# Historical Search terms availability - 8 November 2026

A read-only, authenticated Real Estate account **573-038-4686** audit reached the actual **1-31 October 2026** Search terms report. Campaign and ad-group statuses were both All, including removed resources; the report table had no additional filters. The UI showed **5,005 report rows**, matching the downloaded private source after removing five aggregate footers.

Only count-level findings and code are public. **No actual query strings, campaign/ad-group labels, financial/performance values or private raw files are committed.** The existing main site, campaign settings/budgets/statuses, tracking and financial records were not modified. No keyword, negative, conversion or qualification was applied.

## Measured source structure

| Measure | Count |
|---|---:|
| CSV data records including totals | 5,010 |
| Retained query placements | 5,005 |
| Aggregate footer rows | 5 |
| Distinct raw terms | 3,691 |
| Distinct normalized lexical identities | 3,691 |
| Repeat occurrences beyond distinct terms | 1,314 |
| Repeated query/campaign-label/ad-group-label contexts | 20 |
| Exact duplicates across all retained placement fields | 0 |
| Distinct campaign labels | 8 |
| Nonblank ad-group labels | 13 |
| Campaign/ad-group label pairs including blank | 16 |
| Nonblank campaign/ad-group label pairs | 15 |
| Rows with missing/double-dash ad-group labels | 131 |
| Records with a potential privacy indicator | 1 |
| Records requiring manual disclosure review | 5,005 |

Labels are not resource IDs. The report lacks campaign/ad-group/keyword ID columns; labels can be shared or renamed. These counts cannot bind exclusions to actual or new campaign resources. The 131 missing ad-group rows are retained, not silently dropped. Twenty repeated query/context combinations differ in other retained fields, so they are not twenty duplicated full records, people or conversions.

The raw source is a 675,640-byte UTF-8 CSV with the exact title, dated header and fifteen column labels. The private intake retains exact query/placement text, original physical start lines and duplicates, but discards **all performance, financial and conversion cell values** from its derived projection. Raw bytes stay unchanged in the private source. Five known totals are not queries, including the Other search terms aggregate; unknown/malformed aggregate-like structures fail closed. Exact footer-label collisions with genuine populated placement context survive as queries.

Google's disclosed report is not proof of every search or all account history. The Other search terms total row is present, but undisclosed term count remains UNKNOWN; its metric cells are not used. The report is historical availability evidence, not keyword quality, campaign performance, actual qualified outcomes or acquisition economics.

## Privacy and authority

Heuristics flag obvious email/phone/URL/token/control/formula candidates across retained text. A flag is not proof of personal data or ineligible intent. No flag is not proof of safety: every record still requires manual disclosure review. Formula-looking text is data and is never executed. Source errors disclose only fixed codes, not cells or paths.

`parse_search_terms(path)` in `tools/keyword-system/search_terms_intake.py` returns a **PRIVATE** in-memory projection plus count-only summary; it writes nothing and has no network, Ads exporter or production mutator. Do not print, commit or share its `records` collection. Only approved, separately reviewed non-sensitive disclosure sets could be considered later; this audit grants none. Names, geography, nationality, budget or a privacy heuristic are not negative-keyword or qualification decisions.

Public disclosure, negative application, qualification and deployment authority remain false. Both reviewed 14,000-keyword masters remain zero. Private source access must not expand original-workbook access or involve the excluded Business Setup account.

## Count-only lexical overlap

The separately pinned public Planner captures contain 7,735 idea identities. Private comparison found 74 shared normalized identities and 3,617 disclosed-report-only identities, giving an **11,352 lexical union**. This is not an accepted library or independent demand. Provider ideas, supplied hypotheses and actual disclosed report terms have different source semantics and date windows; no classification, scope, volume, spend or qualification is inherited. Original captures and the 7,705-classification workbench are unchanged.

## Verification

`audit.json` is a pinned, count-only receipt tied to the private source/native-evidence hashes and public idea-manifest pins. Required CI verifies its integrity, allowed fields and arithmetic only. It cannot independently reproduce the private source or authenticate Google origin. The source origin/scope was observed in the authenticated UI; raw-source identity and counts were checked locally and independently reviewed.

```sh
python -B docs/audit/search-terms-2026-11-08/verify_audit.py
python -B -m unittest discover -s tools/keyword-system -p test_search_terms_intake.py
```

`verify_audit.py --source PRIVATE_SOURCE` reproduces the pinned source hash/size, count summary and lexical overlap locally without outputting rows or paths. Without that input its scope is `PUBLIC_COUNT_INTEGRITY_ONLY`; with the exact original it is `PRIVATE_SOURCE_COUNT_REPRODUCTION`. Neither mode authorizes disclosure or Ads changes.

Seven synthetic tests cover date/schema/encoding/byte/row boundaries, physical multiline starts, duplicates, genuine footer-text collisions, malformed totals, discarded metric cells and privacy/authority controls. No actual query or financial fixture is in the repository.

Next: resource-ID enrichment or separately verified scope binding, private manual privacy and full-phrase intent review, factual service/destination/protected-intent evidence and approved research admission. Never treat 5,005 placements or 3,691 terms as new eligible negatives. Owner decisions, independent human PR review and separate production release authorization remain open. The full 360-page/14,000-positive/14,000-negative/lifecycle goal remains active and incomplete.

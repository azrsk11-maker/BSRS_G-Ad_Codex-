# Employment follow-up provider audit — 11 November 2026

This is a bounded, read-only Keyword Planner audit for the next employment research inputs. It is not a keyword admission, exclusion approval, campaign mapping, or deployment export.

## Verified UI capture

- Account: Google Ads `573-038-4686`, Black Swan Real Estate, marketing account.
- Provider: Google Keyword Planner, **Discover new keywords**.
- Location: United Arab Emirates.
- Language: English.
- Network: Google.
- Date range: Last 12 months.
- Adult-idea filter: enabled.
- Site filter: blank.
- Authored seed inputs: the eight values listed in `capture.json`.
- Provider result: **444 keyword ideas available**; the first visible provided rows included the first four seeds.
- Ads state readback: Google displayed that no ads were running and campaigns/ad groups were paused or removed.

## Export and reconciliation

The first CSV action was blocked by the connected browser (`ERR_BLOCKED_BY_CLIENT`). A keyboard-triggered retry then saved the provider export privately and it was reconciled with the independently observed UI context: **444 rows, 444 distinct normalized phrases**, and all eight authored seeds returned as separate rows. The private TSV is not committed; only the sanitized 21-column projection and its pinned source hash are stored in `employment-followup.json` and `capture.json`.

The projection remains `AUTHENTIC_PLANNER_DISCOVERY_UNREVIEWED`. It is not a keyword admission, exclusion approval, campaign mapping, or deployment export. No row has been promoted to either library.

`REVIEW_PREVIEW.md` records a bounded lexical routing screen only. `semantic-review-preview.json` preserves all 444 source lines with a reproducible preliminary route: 109 explicit employment/facilities/caretaker literals are candidates for exact-negative review and 335 remain held. It deliberately does not classify ambiguous caretaker, housing, estate, employer or entity phrases and confers no approval.

`protected-overlap-report.json` records a fresh current-corpus check: 20 exact overlaps with the current negative research and 39 exact overlaps with the protected-query corpus (43 conservative token-subset diagnostics). These are conflict signals, not automatic exclusions; all affected rows remain unapproved.

The artifact contract is checked by `tools/keyword-system/employment_followup_validator.py`; its focused tests reject missing, duplicated or unbound review rows and non-zero authority flags.

## Inputs

See `capture.json` for the exact seed list and bounded status. The prior 212 query inputs and all existing source captures remain unchanged.

## Safety boundary

No campaign, budget, keyword, account, tracking, website, workbook, permission, or production setting was changed. Advertising remains paused.

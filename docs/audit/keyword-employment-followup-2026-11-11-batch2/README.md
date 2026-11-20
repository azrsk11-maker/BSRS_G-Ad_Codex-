# Employment follow-up provider audit — batch 2 — 11 November 2026

This is a second bounded, read-only Google Keyword Planner capture for the approved employment research inputs. It is not keyword admission, exclusion approval, campaign mapping, or deployment.

## Verified UI context

- Account: Google Ads `573-038-4686`, Black Swan Real Estate, `marketing@blackswanrealestate.ae`.
- Provider: Keyword Planner, Discover new keywords.
- Location: United Arab Emirates; language: English; network: Google; date range: Last 12 months; adult ideas excluded; no site filter.
- Eight authored seeds were entered exactly as recorded in the preflight receipt.
- Provider UI showed **444 keyword ideas available** and the account banner said no ads were running because campaigns/ad groups were paused or removed.

## Export and controls

The private CSV is retained only in local Downloads and is not committed. `employment-followup-batch2.json` is the sanitized 21-column projection generated through the existing `project_discovery` and `assemble_capture` pipeline. It contains 444 rows and 444 distinct normalized phrases, with the source SHA pinned in both the batch and capture manifest.

The batch scope is `AUTHENTIC_PLANNER_DISCOVERY_UNREVIEWED`. Review, scope approval, campaign mapping, production authorization and deployment remain false. No row was added to either 14,000-keyword library.

`semantic-review-preview.json` adds a reproducible lexical pre-screen only: **58** rows are candidates for exact-negative human review and **386** remain held. Every row remains human-review-required; no positive, approved, or deployed row exists.

Use `tools/keyword-system/supplemental_batch_validator.py` for the fail-closed provenance and authority check.

## Safety boundary

No campaign, budget, keyword setting, website, tracking, workbook, permission, financial record or production setting changed. Advertising remains paused.

# Read-only content evidence and suppression

This implements bounded offline consistency checks for Master Plan sections 9 and 17. It does not create factual content, invent stock or rights, authenticate a reviewer, fetch a source, publish a page or change a website/Ads account. No real business ledger is supplied. The test module contains explicitly synthetic examples only.

`evaluate_content_evidence(ledger, *, expected_pages, now_utc)` checks an exact selected page set. The caller must derive `expected_pages` independently from reviewed content artifact bytes: each row has exactly `page_id`, `campaign_key` and `content_sha256`. A digest copied from the same unverified ledger does not independently establish the actual content. Root release controls additionally bind artifacts, inventory, ledger and acceptance to the actual proposal/commit/evaluation context.

## Ledger contract

The top-level keys are exactly `schema: bsre-content-evidence-v1`, `pages` and `records`. Up to 360 pages and 20,000 evidence records are accepted. Empty page sets, duplicate identities, unreferenced records, scope outside the selected pages and extra fields fail closed. The CLI reads at most 8 MiB per regular, non-symlink JSON input; duplicate keys and nonfinite JSON constants are rejected. API inputs must already be parsed trusted JSON structures, not arbitrary Python objects.

Each page has exactly:

- `page_id`, `campaign_key`, `content_sha256`, `content_author`, `update_owner`;
- `offer_kind`, `inventory_presentation`;
- `evidence_ids`, `evidence_sha256_by_id`, `offer_inventory_ids`, `alternative_evidence_ids`;
- `disclosure_claim_id`, `alternative_claim_id`, `review`.

Each record has exactly `evidence_id`, `kind`, `page_ids`, `source_class`, `source_ref`, `source_sha256`, `source_as_of_utc`, `valid_until_utc`, `details`, `review`. IDs/references are bounded opaque ASCII identifiers, not private file paths, contact details or claims of verified ownership. `page_ids` must equal the pages actually binding that record. Shared evidence can therefore invalidate every affected page without holding unrelated pages.

`details` has exactly these fields for its kind:

| Kind | Details |
|---|---|
| `CLAIM` | `text`, `category`, `related_evidence_ids` |
| `ASSET_RIGHTS` | `asset_sha256`, `rights_basis` (`OWNED`/`LICENSED`), `licence_ref`, `permitted_use: PAID_LANDING_PAGE` |
| `INVENTORY` | `property_id`, `availability_state`, `asking_price_minor`, `currency: AED` |
| `BROKERAGE_SERVICE` | `service_key`, `description` |

`asking_price_minor` is a bounded nonnegative integer or explicit null; missing price is never replaced with zero or an invented estimate. Availability is exactly `available`, `limited-confirmed`, `waitlist`, `sold/rented`, `unavailable` or `unknown`.

Claim categories are `PRICE`, `YIELD`, `PAYMENT_PLAN`, `HANDOVER`, `OWNERSHIP`, `FINANCE`, `RESIDENCY`, `GUARANTEE`, `REVIEW`, `AFFILIATION`, `LEGAL_REGULATORY`, `AVAILABILITY_DISCLOSURE`, `ALTERNATIVE_OFFER`, `OTHER`. The exact wording is retained privately and hashed without trimming, normalization or translation. Related evidence must exist on the same page.

Source classes are `BUSINESS_EVIDENCE`, `OFFICIAL_AUTHORITY`, `PUBLIC_RESEARCH`. Only supplied business-evidence attestations support services, inventory and rights. Official-authority attestations can support legal/regulatory claims; public research alone cannot make an offer publishable. These labels remain supplied assertions, not network-verified facts.

## Review and freshness

Every review contains exactly `reviewer`, `reviewed_at_utc`, `evidence_ref`, `subject_sha256`, `approved` (a boolean). Page reviews additionally contain boolean `claims_complete` and `assets_complete`. They must explicitly attest completeness and use a reviewer different from the page's content author. Semantic completeness, an actual qualified reviewer and business approval still need independent authentication.

`subject_sha256` is `canonical_sha256(subject_without_review)`: sorted JSON keys, compact separators, UTF-8, non-ASCII preserved, nonfinite numbers rejected. This is a canonical object hash, distinct from a raw input-file hash. A page's `evidence_sha256_by_id` has exactly its evidence IDs and canonical hashes of the **complete evidence records including their reviews**. Its own review consequently binds exact record text, source hashes, scope, dates, rights and reviewer attestations. Replacing a source, changing a date or re-attesting a record at the same timestamp cannot reuse the old page review.

Evaluation requires an explicit valid whole-second UTC timestamp (`Z` or `+00:00`, years 1970–2100). Root acceptance must bind that clock to actual observation/freshness evidence; an arbitrary old clock is not current acceptance. A source cannot be from the future, its expiry must follow its as-of time, and expiry holds at the exact boundary. Record review cannot predate its source or exceed evaluation time; page review cannot predate any evidence review. Renewing evidence means new review and page bindings, not changing a timestamp automatically.

## Supported offer presentations

- `BROKERAGE_SERVICE` uses `NOT_APPLICABLE`, empty inventory/alternative lists and null disclosure/alternative claim IDs. It requires current supplied service evidence, without requiring buyer-side stock. This covers advisory and owner-acquisition offers when the actual business review supports them.
- `PROPERTY_OFFER` / `CURRENT_OFFER` requires at least one subject inventory ID and current available/limited-confirmed evidence for every subject. Disclosure/alternative fields stay empty/null.
- `PROPERTY_OFFER` / `DISCLOSED_UNAVAILABLE_WITH_ALTERNATIVES` requires nonavailable subject inventory, an `AVAILABILITY_DISCLOSURE` claim linked to exactly those subject IDs, and an `ALTERNATIVE_OFFER` claim linked to exactly the alternative IDs. Each alternative must be currently available inventory or a genuine reviewed brokerage advisory/service record. The unavailable subject cannot be its own alternative. Unknown, waitlist, sold/rented and unavailable records never become current stock.

Exact wording, related IDs and page content hashes bind the supplied disclosure and alternatives; the checker cannot automatically determine whether prose is truthful, prominent or suitable. Those are independent editorial/licensed-team acceptance obligations.

## Results and boundaries

The result provides `all_pages_eligible`, per-page `eligible`/reason codes, `suppressed_evidence_ids`, and `suppressed_current_offer_ids`. Invalid evidence is suppressed in this **read-only manifest**. A current, accurately disclosed unavailable subject can appear in the disclosure while still being suppressed as a current offer. Structural errors raise only stable `ContentEvidenceError` codes; reports/exceptions never include exact claim text, source references, private paths, prices, reviewer identities or update-owner identities.

`authenticated_business_approval` and `publication_authorized` always remain false; network calls/production writes remain zero. An eligible result means local consistency of supplied attestations. It does not verify a source document's authenticity, actual property/asset bytes, mandates, permits, regulatory suitability, evidence inventory completeness, reviewer identity or the truth of wording. No regulator/permit approval or real availability is inferred from hashes. Existing independent legal/business/source-truth acceptance and separate production permission remain required. Runtime suppression still needs a separately approved website implementation; this module performs none.

Run focused checks:

```powershell
python -B -m unittest discover -s tools/content-evidence -p 'test_*.py' -q
python -B tools/content-evidence/content_evidence.py --ledger '<private-ledger.json>' --expected-pages '<independent-page-inventory.json>' --now-utc '2026-11-10T12:00:00Z'
```

CLI output is a sanitized report on stdout: exit 0 means locally consistent, 1 means held evidence, 2 means invalid/unreadable input. It writes no file. Twenty-three focused synthetic tests cover service-only offers, exact content/page bindings, shared expiry, review/source chronology, source replacement, asset rights, missing evidence, independent/completeness attestations, public versus official/business sources, available stock, truthful unavailable-plus-alternative/advisory flows, safe reports and strict CLI parsing.

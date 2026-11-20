# Codex task — BlackSwan Real Estate acquisition implementation

Read `BlackSwan_Real_Estate_Algorithmic_Master_Plan_v3.md` in full. It is the authority for this task after the owner's latest explicit instructions.

## Non-negotiable scope

Prepare exactly 14,000 distinct positive keyword phrases and 14,000 distinct negative-keyword research phrases across the entire system, not per campaign. Each needs provenance, a valid commercial classification and a justified mapping/scope. Do not count placeholders, duplicates, match-type copies or rejected terms toward the totals. No fabricated volume, CPC, inventory, rights or performance.

Retain the 360 planned campaign/page slots. Each live campaign owns a separate unlisted, noindex route under `blackswanrealestate.ae`; no shared designated entry page between campaigns. The 10,800 page-intent cells are research labels, not live campaign objects. Preserve useful existing website assets.

Cover all seven UAE emirates, residential and commercial off-plan and ready/secondary property, buying/investing, rental/leasing, sellers and landlords. Do not import Business Setup account IDs, budgets, geo exclusions or consultant rosters.

No CRM/Zoho synchronization, writes or workflows. Persist each accepted lead durably, then email `marketing@blackswanrealestate.ae` using `G-Ad | [Campaign] | [Lead Name] | [Lead ID]`, plus the same Lead ID in the verified company-controlled Google Sheet. Use retries and visible exceptions; never count both outputs as separate leads.

## Sequence

1. Audit actual repository, account, pages, tracking, sources and access; document blockers without inventing answers.
2. Freeze schemas, immutable IDs, company config, source/claim registers and approval boundaries.
3. Build and validate keyword masters, protected queries, negative applicability and exact count audits.
4. Build dedicated, useful campaign pages with current verified inventory/service facts and tested noindex controls.
5. Implement consent-aware capture, canonical events, attribution, durable storage, email/Sheet outbox and error recovery.
6. Independently test source truth, keywords, protected intent, forms, contact routing, noindex, crawl access, duplicates, privacy, stale inventory and rollback.
7. Produce paused/held platform exports and a minimal-diff release manifest. No live spend, publication, audience upload or production write without explicit authority.
8. After authorized execution only, read back platform objects and test the actual complete journey. Report generated, validated, approved, deployed and blocked counts separately.

## Important technical safeguards

- Unlisted/noindex is not private: ad clicks and shared links must open the same truthful page.
- Exclude campaign routes from menus, sitemaps and site search, but do not block the crawl needed for noindex and ad review.
- Do not require GCLID/referrer/login to load production ad pages. Do not hide claims from reviewers.
- Disable and read back final URL expansion; audit inherited sitelinks and destination overrides.
- Do not retag internal links with new UTMs or claim paid traffic creates organic ranking benefits.
- Negatives are scoped exclusions, not a blanket 14,000-term account block. Protect legitimate rental, affordability, financial readiness, owner, occupier and research intent.
- Distinguish clicks from messages/calls, accepted leads from qualifications, booked from attended viewings, contractual close from collected commission.
- Keep PII out of analytics and URLs; sanitize email headers and spreadsheet cells.
- Evaluate collected brokerage contribution, not property value. Prevent double credit when acquiring both seller and buyer for one deal.
- Use actual available concurrency with exclusive worktree ownership and independent QA; after two identical failures investigate the root cause.

## Finish with evidence

Provide exact artifact paths, source references, deterministic count results, mapping and negative-conflict tests, delivery/attribution results, approval status, live read-back where authorized, rollback and named blockers. A 14,000-row file that is padded or unsafe is not accepted.


## Version 3 — owner-mandated native website and tracking requirement

Read section 24 of the master, `Website_Tracking_Addendum_v3.md`, `website_tracking_contract.json` and `website_tracking_acceptance_tests.json`. All campaign pages are native content/routes of the existing Hostinger-managed main website and existing admin/application workflow—not standalone landing websites. Audit the actual CMS and capabilities; do not create another site, hosting project, CMS install or iframe workaround. Reuse verified shared company tracking, and implement distinct page/form/CTA IDs, supported events, consent, deduplication and source continuity into public-site enquiries. Actual account IDs remain unknown until verified; no fabricated placeholders may ship. Validate a complete native pilot before scaling. Every release needs page-level tracking evidence. Hostinger access alone is not access to Google analytics/ad accounts and is not advertising spend approval.

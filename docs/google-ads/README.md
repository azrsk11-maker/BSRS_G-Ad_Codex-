# BlackSwan Real Estate implementation specification — v3

Start with `BlackSwan_Real_Estate_Algorithmic_Master_Plan_v3.md`. Give Codex that file plus `Codex_Execution_Brief.md` and the relevant JSON registers.

## Exact content status

This is a **design and execution specification**, not a Google Ads upload package.

- 360 planned campaign/page records are materialized.
- 70 positive-intent taxonomy records are materialized; their seed examples are not an approved keyword library.
- 14,000 positive and 14,000 negative phrases are implementation targets.
- **The actual 28,000 researched keyword records are not in this package.**
- No live pages, Ads objects, audiences, budgets, CRM writes or production routing were changed.

All actual URLs, platform IDs and approvals remain unknown/false where not verified. Proposed `/lp/` paths are route specifications only.

Run `python validate_planning_package.py` from this directory to check the planning arithmetic and structural invariants. Passing that validator does not satisfy live campaign release gates.

## Version-3 additions

The owner requires native pages inside the existing Hostinger-managed main website, not separate landing sites. The amendment, JSON tracking/event contract and 32-test website/measurement acceptance register are included. Actual IDs, native page identities and all live tracking tests remain unknown or NOT_EXECUTED. Planning validation is not runtime QA.

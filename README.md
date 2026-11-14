# Black Swan Real Estate Google Ads

Phase 0 audit and tested offline foundation for the existing native WordPress website. **No production publication, tracking change, Ads change or spending is authorized by this repository or a successful merge.**

- [Current progress and blockers](docs/PROGRESS.md)
- [Complete authoritative Master Plan](docs/google-ads/BlackSwan_Real_Estate_Algorithmic_Master_Plan_v3.md) and [specification pack](docs/google-ads/README.md)
- [Detailed execution plan](docs/EXECUTION_PLAN.md), [source traceability](docs/audit/REQUIREMENTS_TRACEABILITY.md), [inconsistencies](docs/audit/INCONSISTENCIES.md)
- [Owner decisions](docs/decisions/OWNER_DECISIONS.md) and [open GitHub decision issues](https://github.com/azrsk11-maker/BSRS_G-Ad_Codex-/issues?q=is%3Aopen+label%3Aowner-decision-required)
- [Governance and release separation](docs/GOVERNANCE.md)

Run `python -B tools/check_repository.py` with Python3.12 and Node20+; PHP8.2+ is required for the separate native-adapter CI gate. Existing reviewed AST hashes use the Python3.12 representation. CI selects that minor version and checks the unchanged review binding before expensive tests; other Python minors are not accepted for the complete Foundation. See [runtime evidence](docs/audit/CI_PYTHON_RUNTIME_COMPATIBILITY_2026-11-12.json). No production credentials are installed. Tests use isolated/synthetic records and make no Google conversion requests.

360 entries are planning slots, not built or published pages. The supplied pack contains zero researched positive/negative masters; both14,000targets remain open. Verified identifiers and dated live readbacks are separate from unchanged draft specifications. Private lead/financial data and secrets must remain outside this public repository.

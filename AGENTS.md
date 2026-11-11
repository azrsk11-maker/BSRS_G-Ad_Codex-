# Black Swan Real Estate execution rules

Read `docs/PROGRESS.md`, then only the task-relevant evidence. The complete requirements are in `docs/google-ads/`; preserve the supplied files verbatim. Reconcile conflicts in `docs/decisions/OWNER_DECISIONS.md` and linked owner-decision issues; never silently choose between them.

- Real Estate only. Exclude Business Setup and Zoho/CRM synchronization. Keep the original lead workbook private.
- Work on `codex/*` branches and submit PRs. No direct main writes, force pushes, self-approval or bypass of protection. Bootstrap commit contains only the initial README.
- Read approved issue decisions before affected work. A proposal, issue comment by a non-owner, merge, green test or old authorization does not authorize a separate production action.
- No publication, live tags, Google Ads changes or expenditure without specific separate owner authorization. No production credentials in CI; no deployment workflow in this phase.
- Preserve the existing WordPress site, stable receipts, signed wire v1, intake/outbox and private Sheet/email architecture. Native page drafts only after separate approved staging access; never manufacture inventory or publish 360 placeholder pages.
- Research counts, approved counts and deployed counts are distinct. Never manufacture keyword evidence, metrics, IDs or approvals to meet a count.
- One browser writer. Parallelize independent work with separate ownership. After two identical logical-phase failures investigate; verify ambiguous writes before retrying.
- Use small targeted checks, bounded output and existing results. Do not load archives or print private records. Record material changes, measurements and uncertainty in the progress report.
- Windows Git can convert LF source bytes, including during `git archive`. Disable `core.autocrlf` for source-only checkout/archive commands and verify pinned fixture hashes before acceptance. Preserve original bytes; never change provenance pins to accommodate a converted checkout.
- On Windows, Python's default text encoding can be a legacy code page. Pass `encoding='utf-8'` explicitly for project text reads/writes, or use verified bytes. Review small diffs for Unicode corruption; do not rewrite unchanged text through the default encoding.
- PowerShell does not expand wildcard paths for `rg`: pass a real directory with `-g '*.php'` (or the relevant pattern), rather than a path such as `tools/example/*.php`.
- Public repository: exclude secrets, prospect/transaction records, live private workbook IDs, raw logs and personal machine paths. Synthetic fixtures must be clearly marked and must never be sent to Google.

Run `python tools/check_repository.py` for the offline release-foundation checks. This validates development artifacts, not production readiness. See `docs/EXECUTION_PLAN.md` for gates and `docs/GOVERNANCE.md` for approval boundaries.

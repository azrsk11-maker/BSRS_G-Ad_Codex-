# Offline 100-goal coordinator

This small Python standard-library tool tracks the existing goal numbers in
`docs/EXECUTION_BACKLOG_100.md`. It performs no network calls or production actions.
The supplied `goals.json` is a planning snapshot, not an authorization or release
receipt. Goal definitions and full acceptance gates stay in the canonical document.

Use the project's verified Python 3 interpreter. From this directory:

```text
python -B -m unittest -v test_ledger
python -B ledger.py validate goals.json
python -B ledger.py summary goals.json
```

From the repository root the focused check is:

```text
python -B -m unittest discover -s tools/goal-ledger -p test_ledger.py
python -B tools/goal-ledger/ledger.py validate tools/goal-ledger/goals.json
```

`validate` and `summary` never write the input. Output is deterministic compact JSON;
invalid input returns a nonzero status. `seed CANONICAL_JSON NEW_LEDGER_JSON` imports
only goal IDs, dependency IDs and launch classifications from the reviewed grouped
canonical JSON. It refuses an existing output file and imports no private prose,
identities or machine paths. Seeding does not import approval or completion statuses.

The plan checksum pins the imported graph and launch classifications. Ordinary
status/evidence edits preserve it. A deliberate canonical goal change needs a new
reviewed seed and reconciliation of existing evidence; do not recalculate a checksum
merely to bypass a validation error.

All 100 IDs must occur once in order. Dependencies must exist, be unique and form a
DAG. Status is `pending`, `running`, `verified` or `blocked`. Ready tasks are pending
with all dependencies verified; the output keeps `prelaunch`, `conditional` and
`later` queues separate. Only canonical prelaunch rows enter the launch count.
Conditional and post-release work remains visible without being promoted into
first-launch prerequisites. Conditional dependencies in the canonical graph still
apply to their dependent goal; an unselected scope needs an explicit honest
disposition in the canonical owner process, never fabricated implementation.

Update a status only after assessing its complete canonical gate. Add an evidence
entry with a public repository-relative `docs/` or `tools/` reference, its exact goal
bindings and appropriate kind; attach its key to the goal's `evidence_refs`.
`blocked` requires a bound `blocker`; `running` requires a progress/evidence
reference. By default, `running` and `verified` require verified dependencies.
For independent offline preparation, a running row may explicitly set the boolean
`"preparation_only": true`; it still needs bound nonblocker progress evidence, while
unfinished completion dependencies remain visible in `waiting_on`. The flag must
be an actual boolean and true is valid only for `running`. Missing/false keeps the
normal dependency checks. `verified` rejects preparation mode and always requires
all dependencies verified. Set the flag false or remove it before seeking final
acceptance; this neither grants approval nor changes the canonical goal graph.
The summary separates `running_preparation` and `running_execution`. Legacy
`running` remains their aggregate; `ready` remains pending dependency-ready work.
`ready_to_finish` includes pending/running execution rows whose dependencies are
verified, excluding preparation rows even after their dependencies complete. It
indicates dependency readiness only; complete acceptance evidence is still required.
Verified status requires goal acceptance evidence. Native CI, independent
human review, full-library approval, scoped authorization, publication readback,
activation and genuine-event goals require their distinct evidence kinds. Local
tests do not satisfy them. Authorization alone does not prove deployment. An old
baseline bound to no current goal cannot silently verify a new one.

Evidence references and kinds are declarations for the coordinator. This tool does
not examine receipt contents or independently authenticate reviewers/authority.
The responsible reviewer must assess those facts. A successful validation or a
complete launch count grants no execution permission. Unknown/missing evidence
remains pending or blocked. Keep private IDs, records and personal paths outside
this public artifact.

The snapshot retains bounded C6 acceptance and records G001 in progress: G39's
combined 52 local tests pass, while native integration acceptance remains pending.
Zero independent PR reviews, unverified Marketing identity, both full libraries
unapproved, unchanged production and paused Ads remain explicit. The four
blockers are G003/G005/G025/G029. Update statuses only when fresh evidence
establishes completion of each whole goal.

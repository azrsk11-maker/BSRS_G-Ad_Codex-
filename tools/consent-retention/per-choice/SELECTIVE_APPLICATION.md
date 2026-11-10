# First selective per-choice SQL application candidate

This separately enabled disposable-lab controller applies exact due rows from the unchanged [PerChoicePlanner](README.md). It closes the missing first SQL-application path without converting that review planner or its caller-provided coverage into production authority. Existing planner/helper/store fixtures, schemas, source pins, signed wire, intake/outbox and private routing remain unchanged. No hook, route, scheduler, provider or production integration is installed.

## Explicit scope and API

The class is `BSRE\RetentionReview\PerChoice\ApplicationV1\SelectiveChoiceRetirement`. Every public storage operation rechecks local WordPress environment, `http://bsre.invalid`, exact `per_choice_synthetic_` prefix, existing retention-lab guard, new `BSRE_PER_CHOICE_LAB_ENABLED === true`, administrator capability and a positive current actor. Application and schema initialization additionally require `BSRE_PER_CHOICE_APPLY_ENABLED === true`; both flags default to absent/disabled.

```text
installLabTables()
reviewSource()                        private actual synthetic snapshot and current anchor
anchor()
preview(coverage, currentAnchor)
labAcknowledgement(plan)              exact lab digest acknowledgement, not owner approval
apply(plan, labAcknowledgement, currentAnchor)
reconcileLast(plan, currentAnchor)     read-only exact last-operation readback
```

Plans and source snapshots contain private row references; never print, publish or export genuine inputs. The acknowledgement is only a lab operation guard. It cannot authenticate collector completeness, grant deletion rights or substitute for an owner-reviewed production manifest.

Initialization checks session transaction state and repeatable-read isolation before any DDL. It initializes only a genuinely new empty namespace: if either control/audit exists alone, or both are absent while any consent table exists, it holds. Native fixture setup therefore initializes control/audit before installing the separate pinned consent schema. Existing valid tables are validated read-only without CREATE, INSERT or reset; a history gap cannot be cleared by reinstalling. Failed/partial DDL requires separate reconciliation.

## Exact application and preserved evidence

The controller owns a transaction and refuses an existing caller transaction without starting, committing or rolling it back. It requires the existing repeatable-read session rather than changing isolation. Control/audit and all three source tables must be InnoDB. Locked reads are bounded to at most1,000 total consent rows and a bounded audit chain.

The preview binds the complete current control anchor, original coverage object, complete source digest, unchanged planner result, exact selected references, expected retained-state digest and per-table counts. Expiry is no later than15minutes or the coverage expiry, whichever is earlier. Unknown/inconsistent source coverage or any unexplained history/capture lineage gap holds the entire mutation batch, even if an unrelated subject would be individually age-eligible.

Apply rereads the current control, complete source and audit chain under real locks. Changed source, authority, plan, selected rows or coverage cannot be admitted by recomputing the lab acknowledgement. Only exact selected state/history primary keys can be deleted. Captures, current retained permission authority, submitted original decisions and later withdrawal/regrant history are preserved according to the unchanged planner. The complete retained snapshot must equal the planned digest after deletion; exact row counts must also match.

Minimal operational audit records contain plan/source/retained/anchor digests, counts, generation, actor and application time. They retain no retired subject IDs, receipts, permission choices, notice payloads or full source rows. A genesis-to-current hash chain binds each complete operational record and validates the current generation, last-plan hash, retained-state hash and irreversible history-gap latch. Hashes prove consistency in this controlled lab, not independent authentication or external custody.

Deletion, audit and control update commit together. Precommit failures roll back all three; false or thrown rollback responses hold the instance for fresh readback. A failed COMMIT response is ambiguous: the controller does not claim rollback or retry. The affected instance refuses another application. Inspect a fresh connection, current audit/anchor and retained source before any recovery decision. A lost acknowledgement can be reconciled read-only without repeating deletion.

## Deliberate first-application boundary

Any successful history pruning permanently latches `history_incomplete` in this version. Further preview/application holds; caller booleans and reinstall cannot clear it. `reconcileLast` proves only that the exact last operation's stored audit/anchor and current retained snapshot agree. It returns `future_application_authorized:false`, `production_acceptance:false` and `reopen_authorized:false`; it never recreates deleted permission payloads, assumes a missing revision was safely deleted or resumes recurring retirement.

Recurring post-pruning retirement still requires separately designed and authenticated complete-lineage/boundary admission. Production collector coverage, necessary-history review, protected custody, recovery/restore replay and explicit deletion approval remain open. This bounded candidate is actual first selective SQL application, not completion of retention policy or a deployable release.

## Verification

`selective-choice.test.php` exercises23pure guard cases with no native SQL. PHP lint is required separately. `selective-native.php` requires the already approved isolated WordPress/MariaDB lab and its unchanged candidate store; it must not run on a live website.

The native harness tests exact old-choice deletion while retaining active and submitted/withdrawal evidence, exact calendar boundaries, gap/audit/control tampering, partial initialization, caller-transaction preservation, isolation/engine refusal, stale/altered plans, delete-count conflicts, delete/audit/checkpoint rollback and both uncommitted and committed-but-unacknowledged COMMIT failures with fresh-connection readback. Two bounded separate-process orderings require actual InnoDB waiter/blocker evidence: a competing capture invalidates the waiting plan, and a real derived-store producer waits while the writer owns its snapshot then cannot stage a retired choice. Metadata observation uses the verified200ms cadence needed for MariaDB's shared cache; elapsed sleep alone cannot pass either gate.

Only constant check names, counts and false admission flags are emitted. Every row, clock and lead/event identity is synthetic; no enquiry is routed and no Google, Sheet, mailbox, financial record or production data is changed. Native acceptance remains unproven until the exact-source Linux job actually passes.

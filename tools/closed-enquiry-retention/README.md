# Closed-enquiry retention candidate

This is an isolated workflow candidate for the adopted monthly review and deletion of closed or unsuccessful enquiries twelve Dubai calendar months after actual closure. It preserves Intake26 and Outcome40. It introduces no live collector, Gmail permission, production deletion route, scheduler or production provider adapter.

## Data and authority

The separate version1 closure record contains an immutable closure ID, revision, explicit OPEN/CLOSED/UNSUCCESSFUL status, original request/lead/event IDs, actual acceptance/closure/recording times, reviewer and evidence reference/hash, associated outcome IDs, exact marketing mailbox message IDs and observed outbox status. `DISQUALIFIED` alone cannot establish closure. A changed revision, reopened enquiry, missing evidence, unresolved outbox or incomplete resource inventory holds the plan.

Each resource binding uses a stable key, exact request/lead/event identities, a single owning request, content fingerprint and evidence reference/hash. Email also requires the exact mailbox, message ID and RFC822 Message-ID. Multiple associated outcomes are supported. A resource shared with another enquiry is held. The workflow never deletes a Gmail thread, searches by subject during apply or relies on a shifting Sheet row number. Shared consent state/history and cross-enquiry canonical data are outside these resource adapters.

`preview()` returns only aggregate status, confirmed-absence count and hold codes. `prepare()` is owner-review gated and returns a private exact plan with a digest and fifteen-minute initial approval window. That plan contains restricted identities and must not be published. `execute()` requires a separately authorized exact-plan action through the Authority adapter.

Issue10 Option A is approved. The owner handles exact copies in the marketing mailbox. The workflow commits an intent and returns `AWAITING_OWNER_MAIL_ACTION`. `ownerMailAction()` returns the private exact-copy manifest only while the reviewed binding remains current. A later `execute()` advances only after an authenticated receipt binds that owner, plan digest, mailbox, message ID, binding hash and time to a positively confirmed absence. Mail readback must cover the complete authorized surface, including Trash. A missing search result or provider error cannot supply absence evidence. The workflow never invokes mail deletion. No OAuth scope is added.

All operations require `BSRE_CLOSED_RETENTION_LAB=true`, WordPress local environment and synthetic `http://bsre.invalid` home. The supplied provider implementations use synthetic arrays only. Authority and runtime-readback classes named `Lab*` are test fixtures, with no live trust claim.

## Admission and cross-store execution

Admission defaults to unverified. Both actual WordPress and receiver gates must use the reviewed `bsre-retention-admission-v1` descriptor, enforced mode, installed WP routes and store, the same audience/generation/activation epoch and900-second server proof lifetime. A trusted readback adapter must provide exact source and supported-restore policy hashes and a fresh bounded observation. The plan pins the stable configuration; refreshed evidence can extend observation freshness without changing that configuration. A caller's true/complete flag cannot create live enforcement evidence. The synthetic journal pins a nonidentifying admission floor before any owner action. It survives private-job cleanup, and a missing or different floor holds resume. Real floor custody outside restorable data and admission-compatible rollback enforcement remain required. No authenticated production adapter exists here.

The journal serializes closure editing with execution. The MariaDB adapter uses a connection-owned closure lease, compare-and-swap journal revisions and individually committed write-ahead intents. It does not claim one transaction across email, Sheets and WordPress. Every provider must compare the exact binding and support bounded authoritative readback. The workflow checks the remaining inventory before every step and before reporting completion. Unexpected new or recreated resources hold the job.

The durable global history-incomplete marker is set and verified before the first irreversible action. It survives partial failures and completed-job cleanup. The workflow never changes it back to complete. Associated outcome deletion therefore cannot silently preserve a first-ever qualification claim. This follows the historical outcomes README policy, including its prohibition on an indefinite hashed-person register.

Lost acknowledgments retain an intent. A later readback may establish absence and allow continuation without a repeated delete. An absent resource before any intent is stale evidence. A changed resource, generation, closure or incomplete readback holds the job. Reopening during a partial purge does not trigger automatic restoration or further deletion.

Completed private jobs and closure identifiers can be removed after the thirty-day recovery window, provided a fresh gate readback and final absence inventory still agree. Only the nonidentifying history-gap flag persists. Unresolved jobs cannot auto-resume after thirty days. Separately authorized cleanup scrubs their cached plan/journal identities and increments a nonidentifying unresolved counter. Their authoritative closure evidence remains available for fresh manual reconciliation of unfinished provider work. No provider completion is inferred. The real reconciliation workflow and its source-retention handling remain deployment gates.

## Remaining deployment gates

- Genuine protected closure ledger and complete per-enquiry collectors, including exact mail-copy evidence.
- Implement the approved manual exact-copy manifest, receipt collection and independent marketing-mailbox readback in the protected owner workflow. MailApp supplies neither inbox access nor message IDs. No automation scope is authorized.
- Real producers honoring the same purge fence and closure lease. Current adapters cannot prove that an external manual edit, new mail copy or unrelated producer is quiesced.
- Authenticated admission-enforcement readback and integration with the production receiver, retries and restore path.
- Actual provider deletion/readback and interruption acceptance. Current provider resources are mocked even when the journal uses real MariaDB.
- Current retirement-ledger custody, backup expiry and restore fencing, with bounded identifiers and no permanent person registry.

The current candidate requires SENT plus exact message bindings. Confirmed-never-sent handling remains held until a reviewed no-copy evidence contract and outbox fence exist. No missing copy is invented to unblock a purge.

## Verification

Run `php -n tools/closed-enquiry-retention/test_workflow.php` with the verified PHP8.2 binary. Forty-five focused checks cover calendar limits, default holds, exact approval, malformed/stale/shared bindings, outbox ambiguity, owner action/receipt/independent absence, interrupted deletes, fresh same-configuration readback, nonidentifying policy floor, direct mailbox binding conflicts, last-step reopening, history flags, corrupt journals and thirty-day cleanup.

The native harness is `native-test.php`, copied with this directory to `/opt/lab/closed-enquiry-retention/` and run after the existing WordPress bootstrap. At3181639 it passed12checks using realMariaDB for durableintent, freshconnectionresume, closurelease, CASconflict andcleanup, alongside45purecontractchecks. Resource deletion stays in synthetic memory adapters. Evidence is `../../docs/audit/CLOSED_RETENTION_LAB_2026-11-08.json`; liveprovider andproduction acceptance remain open.

## Policy provenance

The historical `work/v2-implementation/outcomes/README.md` has SHA256 `c9e3f13b4dda87a8d86edc23e9e0533d694ff2ab8135eb3e0f7e24eee2c3a261`. It states that associated outcomes follow the twelve-month closure policy and missing/deleted history must not be attested complete. The shared approval is also in `docs/decisions/OWNER_DECISIONS.md`, OD-007.

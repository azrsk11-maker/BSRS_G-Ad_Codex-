# Default-disabled retirement-journal compaction — 10 November 2026

## Accepted baseline and independent gap

The preceding content/creative batch is published at `4a493be2870d80a6089666d5a8cbdae6eb2739db`, exactly matching all 348 reviewed files. Both Foundation jobs and the isolated WordPress job passed. [Verified progress receipt](https://github.com/azrsk11-maker/BSRS_G-Ad_Codex-/pull/8#issuecomment-6765854989), [source-delivery/access clarification](https://github.com/azrsk11-maker/BSRS_G-Ad_Codex-/issues/12#issuecomment-6765860381).

The lab retirement journal retains private replay identities after their existing thirty-day window and previously capped absolute lifetime sequence at 1,000. Removing rows alone would break chain verification and lose the ability to identify resurrected records. The adopted thirty-day recovery policy supports preparing a guarded lab candidate; it does not authorize a production purge or establish recovery provenance.

## Implemented boundaries

- Compaction is independently disabled by default. Both the wrapper and direct helper enforce the opt-in, local/synthetic origin, exact allowed prefix, current administrator and apply guards. The additional literal compaction prefix is allowed only with the opt-in; it cannot target real WordPress tables.
- A fifteen-minute exact plan binds the complete current anchor and contiguous expired prefix. The mutation helper owns its transaction, locks and rereads the real journal, validates approval/current authority, deletes exact due rows, updates the floor and writes the audit atomically. It refuses an existing caller transaction without committing or rolling it back. Failed precommit writes roll back together; ambiguous commit responses require protected audit/current-anchor inspection before retry.
- Existing legacy anchors remain unchanged before actual pruning. Afterward a versioned full anchor binds the retained boundary, generation and history gap. The floor excludes raw retired subject/receipt identities; the protected audit retains time/actor/count/integrity metadata. Hashes are consistency evidence, not proof of anonymity, current external authority or custody.
- Capacity now counts retained rows, allowing sequence 1,001 after a valid thousand-row compaction. Overflow, altered/missing floor, stale approvals, stripped anchors, duplicate/lost-ack retries and rows resurrected below the floor hold.
- **Nonempty recovery after any pruning remains held.** Fresh dates, watermarks or a caller Boolean cannot replace complete authenticated recovery provenance. Empty structural recovery never authorizes reopening. Actual useful recovery, expiry scheduling and protected source/audit custody remain deployment gates.

No original consent-table schema, signed wire format, receipt, intake/outbox or immutable fixture was changed. The purpose-retention adapter was deliberately repinned to the reviewed new candidate bytes; its immutable store/restore fixtures remain pinned. Both its normal and compaction namespaces are mapped away from the base synthetic tables, with tampered-source rejection retained.

## Review and verification

Independent review found and corrected the direct-helper default-off and autocommit bypasses. The final helper owns approval/readback/audit/rollback rather than relying on a wrapper convention. Pure guard/planning checks passed nineteen cases. The native harness uses a fresh connection and separate synthetic prefix; it covers actual SQL rollback, floor integrity, stale/replay and recovery holds, retained capacity and observed competing-process lock waits. Native execution is a separate required CI result, not implied by source review.

The initial combined run passed 56 of 57 checks in 116.014024 seconds and intentionally stopped derived retention construction at the old source pin. The failed receipt is preserved under ignored `test-output/retirement-compaction-20261110-source-pin-hold.json`. After reviewing the changed producer, the adapter pins and isolated-prefix checks were updated deliberately. Its focused derivation/tamper test passed in 9.5488 milliseconds. All 57 final required local checks then passed in 114.097815 seconds with PHP required. The final receipt is `test-output/retirement-compaction-20261110.json`; current-head native results are recorded in the GitHub receipt. These different test sets/timings are not a controlled performance comparison.

For the next complete-source upload, intermediate source commits use GitHub's documented skip instruction, followed by an ordinary final commit and all mandatory checks. Required checks remain pending on intermediate heads; no protection or workflow is disabled. Actual workflow counts, if available, are reported separately from estimates.

Measured scheduling baseline, collected in one complete GitHub run-list call: the preceding eight upload commits generated sixteen workflow runs (ten succeeded, six cancelled, none failed). Seven intermediate commits generated fourteen of those runs; the final head generated the two successful workflows containing its three required jobs. This is observed run-count evidence, not a runtime, billing or token-savings estimate.

## Fresh access findings and full-goal holds

A new WordPress tab successfully reached the real login page, resolving navigation independently of the stale target, but the admin session has expired. No credentials were entered or security settings changed. [Issue 6 records the authentication dependency](https://github.com/azrsk11-maker/BSRS_G-Ad_Codex-/issues/6#issuecomment-6766144453). The fresh Real Estate Ads UI readback is blocked by its ad-blocker dialog; protections were left unchanged and no new live status/configuration acceptance is claimed.

A bounded inspection classified an unrelated open desktop tracker as outside this project, and stopped without further inspection, edits or copying records. It supplies no Real Estate rehearsal evidence; these limited searches do not prove that the reported evidence does not exist.

Production, financial records, live tracking and Ads settings remain unchanged; no advertisement was activated or expenditure authorized. Both reviewed keyword masters, evidence-backed native content and historical mappings, staff/capacity evidence, actual consent/retention/recovery/history/import/conversion acceptance, finance authority, independent human PR review and separate production approvals remain open. This lab candidate does not complete the full goal.

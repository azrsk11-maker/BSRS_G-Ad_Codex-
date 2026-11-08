# Independent-purpose attribution candidate

This opt-in development path preserves the original plugin and receiver fixtures. It does not install itself, enable production measurement or authorize release.

## Transport and binding

`build-purpose-attribution-candidate.mjs` composes the existing actual client and derives WordPress intake/store functions from pinned source. The additional same-origin `/bsre/v1/purpose-lead` endpoint accepts a bounded envelope containing the exact legacy wire body and separate analytics/advertising first/latest histories. The receiver still receives the unchanged signed wire-v1 body and keeps all26 intake columns. Extended metadata, permission references and correlation identifiers remain outside that wire projection and every public measurement bus.

Each purpose touch carries its original server decision reference. The server resolves that reference within the signed-cookie subject's history, checks the actual decision interval, notice, purpose, expiry and subsequent withdrawal, and intersects it with the original submission decision. Missing historical evidence remains unavailable. Browser timestamps and URL parameters are observed hints. They do not prove a genuine Google click or a verified campaign resource.

The existing capture transaction stores four additive fields, `purpose_version`, `purpose_hash`, `purpose_record_hash` and `purpose_json`. The input-sidecar hash detects changed retries. The separate record hash binds retained, permission-filtered data to the wire fingerprint. Receipt linking preserves these fields. A retry cannot replace their original data. A legacy request cannot backfill or downgrade an existing purpose-enabled record. Missing legacy fields represent unknown history.

Unsupported fields and oversized data reject. Permission-unverifiable but structurally supported histories are discarded while intake remains available. Capture storage failures retain the existing fail-closed measurement behavior. The endpoint and legacy guard require explicit `BSRE_PURPOSE_ATTRIBUTION_ENABLED=true`; the client additionally requires the exact `purposeAttributionEndpoint` setting. Defaults retain the legacy path.

## Retention and recovery

The new private fields are in the existing capture row. Source-derived retention candidates validate and preserve them while applying the existing bounded retention policy. Old backup schemas remain legacy/unknown. Restore rejects a purpose touch referring to retired decision evidence, including when that reference differs from the submission's decision. Submitted-record closure and corresponding email deletion remain the wider project's separate unfinished acceptance gate.

The native harness runs after prior baseline tests. It exercises the actual composed client, actual WordPress handlers and database, and the pinned receiver through a local pipe. Twenty role/permission combinations, immutable retries, changed-sidecar/body conflicts, legacy downgrade, withdrawal/regrant and a lost-upstream-acknowledgment case are defined. The derived restore fixture includes a purpose-enabled accepted capture through encryption, restoration and deletion replay.

## Verification state

Seven focused Node tests and30pure PHP assertions pass locally. Generated PHP and client syntax checks pass. The first native run reached the final outbox check after all twenty scenarios, then failed because the harness called the receiver's five-message outbox batch once while expecting twenty messages. The corrected harness uses four bounded batches and a no-duplicate recheck. A focused test verifies that preserved receiver behavior.

The second native run passed the purpose client pipeline with552 assertions, including13 concurrency checks and an observed1205 timeout with rollback. It then stopped at the derived retirement-ledger isolation guard because that class still required the original test-table prefix. The builder now applies the same new prefix to both retirement classes and their fixture, while retaining the local-environment and synthetic-origin guards. Focused source regressions and eight local constructor-guard checks passed. Full current-head retention/restore execution remains required. Browser DOM/storage and Google destinations remain doubles. No production conversion is emitted.

Further release acceptance includes genuine browser cookie/bridge behavior, full outgoing payload inspection, actual account/resource mappings, submission-closure retention, and current-head combined regression checks. New stage/read paths can encounter the existing mixed lock ordering with legacy exports; a database deadlock must roll back without changing immutable evidence, and dedicated concurrent acceptance remains required. No claim of completed full-purpose production integration is made.

The next native fixture exercises a deterministic capture-lock timeout using the actual owner reader and intake route. It verifies observed MariaDB1205, rollback, released state locks, immutable data, a same-ID retry and unchanged receiver rows/mail. Its read-only receiver snapshot has a focused regression proving that it does not dispatch the outbox. Native execution is pending; coverage of every deadlock schedule is not claimed.

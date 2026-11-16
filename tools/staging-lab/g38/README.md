# G38: bounded G2/preference retirement concurrency

This fixed, CLI-only synthetic fixture adds four real two-process schedules after every existing isolated lab mode: consent choice and capture staging, each against actual preference retirement commit and precommit rollback. All original runtime sources, manifests, default-OFF switches and prior lab invocations are retained.

Acceptance requires actual `INNODB_LOCK_WAITS` requester/blocker transactions and the consent-state PRIMARY index, exact SQL, distinct live processes/connections, canonical custody and named-lock ownership. Thirty raw wait fields are emitted before final assertions. A delay alone cannot pass. Capture comparisons include the original parent-owned input, personalization and immutable retry decisions.

Run `node --test tools/staging-lab/g38/construction.test.mjs` and `node tools/staging-lab/g38/preflight.mjs` for portable construction/actual-source checks. Run `node tools/staging-lab/g38/check-receipt.mjs PROFILE_LOG` against each complete plain profile log after isolated native execution. The independent CI audit additionally binds both profiles, every predecessor assertion and the exact published tree.

At preparation, the ten Node tests and grammar/preflight checks passed; actual PHP/SQL execution is pending exact-head CI on both retained MariaDB profiles. Constructed log tests are not native evidence. Opposite winner orders, full fault/migration/scale coverage and genuine provider/operational acceptance remain separate gates. No production deployment, tracking change, conversion upload or advertising activation is authorized.

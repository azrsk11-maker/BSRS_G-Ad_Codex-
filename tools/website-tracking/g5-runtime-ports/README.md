# G5 durable runtime-port candidate

**Partial, held, inert.** No production deployment, provider acceptance, scheduler, REST registration, mailbox operation or permission change is supplied here. The original guarded retention workflows remain unchanged.

`buildG5RuntimeCandidate()` in `build-candidate.mjs` is a pure byte builder: it reads and pins eight original domain modules and five new candidate modules, independently validates the original capture source and four pure-rule extraction spans, and returns `{outputs, manifest}`. `outputs` maps exactly thirteen plugin-relative paths to Buffers. There are no writes or network calls. Changed or missing preimages fail closed. The manifest always remains held; its source/output SHA256 maps are portable public paths.

The new modules implement an encrypted WPDB journal/current-anchor seam, a full-binding capture SQL seam and explicit owner/domain/capability/custody contracts. Current-anchor read/CAS receipts require an existing independently operated service, nonce-bound Ed25519 authentication and existing private key custody. No production signing or encryption key is supplied. SQL/custody uncertainty and restored snapshots hold; exact whole-row approval binding is required before capture deletion. Closure collection and sender-retirement commit additionally require independent source/receiver proof, so owner approval alone cannot supply that authority.

Run the focused byte tests with `node --test tools/website-tracking/g5-runtime-ports/candidate.test.mjs`. They cover exact thirteen-output composition, original/candidate byte equality, source/module pin rejection, complete capture-rule derivation, native fixture separation and deterministic held manifests. These are build/source checks, not PHP/provider acceptance.

The fixed lab wrapper `tools/staging-lab/build-g5-runtime-lab.mjs` resolves the same repository-relative layout. In the reviewed image it creates only `/opt/lab/g5/ready/plugin/...`, `/opt/lab/g5/tests/native.php` and a held manifest. Existing domain copies at `/opt/lab/closed-enquiry-retention` and `/opt/lab/consent-retention` supply originals. The unchanged isolated entrypoint must start its disposable database before running `php -d sendmail_path=/bin/false /opt/lab/g5/tests/native.php`. That fixture uses real WordPress/WPDB/MariaDB with clearly synthetic witness, keys, producer and evidence; none of those fixture services is runtime authority.

Required boundaries remain:

- Accepted G2/G3 uses ordinary canonical `$wpdb`; these ports require its reviewed reconnect-denying lease integration. No global connection swap or permissive second handle is included.
- The separate [canonical lease slice](../canonical-lease/README.md) implements the G2/G3 `CaptureProducer`; [held V3 coupling](../coupled-package-v3/README.md) binds it to the final contact-specific members. Independent durable anchor/key custody, receiver/HMAC/intake/outbox identity joins, exact Marketing-mailbox/Trash/source/history evidence and their operational acceptance remain absent. The original partial G5 builder is unchanged.
- `ActualPreferenceRetention.php`, `ActualRetirementPort.php`, real thirty-day encrypted recovery snapshot/key-expiry/preservation across restores and complete native/concurrency/failure/provider acceptance remain unimplemented or unaccepted. Existing twelve-calendar-month and no-resurrection rules are preserved in the original domain algorithms; including those originals does not make their lab-only orchestration deployable.

The builder must never be used as a complete-profile certificate. Production and advertising remain unchanged.

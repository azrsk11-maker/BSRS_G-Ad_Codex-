# Bounded retention admission candidate

This opt-in candidate prevents an old request from being recreated after its intake row and bounded recovery records are deleted. It introduces no indefinite request/person register. Production installation, configuration, purge and mailbox permissions remain separately gated.

## Contract

The existing guarded receipt-recovery proof endpoint generates the UUID. Its empty request body cannot select a previous UUID. The candidate adds a 900-second admission proof with exact fields `version`, `request_id`, `issued_at`, `expires_at`, `session_hash`, `generation`, `audience` and `signature`. The signing domain is `bsre-retention-admission-v1`. Audience is the SHA256 of the configured receiver URL. Generation and activation time require explicit configuration, with no production defaults.

The client carries the proof in `X-BSRE-Admission`. WordPress forwards it in the outer signed receiver envelope. The original wire-v1 body, its signature and the 26-column intake stay unchanged. The proof is absent from public measurement events and contact bodies. The client cannot fall back to a self-chosen UUID when admission is required and preparation fails.

Both legacy and purpose WordPress callbacks must use the source-derived admission store. Within its existing transaction, it locks the request row before deciding whether this is a known identical request or a new insertion. Unknown requests require a fresh, session-bound proof. A known matching row retains its retry path after expiry or generation rotation; a changed fingerprint conflicts. Admission failure prevents forwarding when capture staging did not succeed.

The receiver makes the same known-versus-unknown decision under its existing script lock. Known identical requests retain the existing receipt. Any unknown request requires the fresh proof with the current audience and generation before append. After a purge, an expired proof cannot recreate the row. A newly prepared proof selects a different server UUID and cannot authorize an old body.

The sender and receiver mode defaults are disabled. Purge must remain held while either old unknown-request path can accept without this contract.

## Enforcement readback

The descriptor contains `contract`, `mode`, `generation`, `activated_at`, `max_age_seconds` and `audience`. The WordPress readback also checks `routes_installed` and `store_installed`. Every applicable POST callback must be the candidate callback; an additional legacy POST handler invalidates the route check. Descriptor equality alone cannot establish source integrity or authenticated live deployment. The deletion workflow must bind trusted current readback evidence, source/configuration hashes and the same generation/audience, then revalidate before every purge/resume.

Before any real purge, authenticated evidence must establish a nonidentifying enforcement floor held outside restorable intake data. Every supported rollback and restore must preserve unknown-request rejection. This candidate supplies no verified provider custody or rollback-floor capability. Keep real purge held when either is unverified.

## Isolated validation

Seven Node cases exercise the actual composed client and source-derived pinned receiver, including expiry, simulated row purge, fresh outer-envelope timestamps, proof substitutions, legacy mode and required-proof fallback refusal. Twenty-five pure PHP assertions cover cryptographic/session binding, generation rotation, row-lock ordering and ambiguous route registration. PHP and JS syntax checks pass locally.

`retention-admission-native.php` passed32checks at921fbe1 in the network-isolated WordPress lab. It uses the actual guarded proof endpoint, both actual intake callbacks, real capture storage and a pipe-connected pinned receiver. It verified caller-selected UUID refusal, known expired retry, synthetic purge, expired old-body refusal and purpose-history preservation. A local IPC scenario executed the actual composed client through WordPress to the pinned receiver, with browser services doubled. The25purePHP checks also passed. Evidence is `../../../docs/audit/RETENTION_ADMISSION_LAB_2026-11-08.json`.

For lab integration, copy the builder, bridge and client driver to `/opt/lab/tracking-system/`, the runtime/tests/native PHP to `/opt/lab/retention-admission/`, derive `store.php` and `intake.php` there, then run the pure and native PHP in separate processes after existing baseline phases. The bridge uses only local synthetic capabilities. Original fixtures and production configuration are preserved.

Residual gates include authenticated all-path deployment evidence, cross-store retirement ordering and restore policy, real mailbox bindings/permissions, full browser acceptance and separate production authorization. A simulated purge is evidence about replay prevention, not authority to delete business records.

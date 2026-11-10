# Purpose-enabled selective retirement integration

This version connects the existing durable purpose-enabled intake to the selective lab writer. It does not install a production route, introduce another browser producer, change wire-v1/26-column routing, or turn browser attribution hints into verified acquisitions. Production and recurring post-pruning retirement remain held.

## Actual compatibility gap

The original capture schema has no `purpose_version`, `purpose_hash`, `purpose_record_hash` or `purpose_json`. The purpose-enabled store already persists these four fields transactionally. Its nested first/latest touches can reference a consent decision older than the enquiry's `original_revision`. Stripping those fields before retirement without inspecting them could delete necessary acquisition-permission evidence.

`PurposeChoicePlanner` therefore validates the complete extended snapshot and each stored record before deriving a separate baseline-schema projection. Original `PerChoicePlanner`, `RetentionInventory`, source-derived purpose store, fixtures and provenance pins remain unchanged. Both snapshot and coverage are bounded scalar copies that detach PHP references; projection cannot remove fields from caller-owned records. All source/coverage/plan digests remain bound to the full extended input, including exact stored JSON and identifiers.

## Protected history and uncertainty

- Require all four fields, version1, canonical stored JSON, the capture-fingerprint/input-hash/record-hash relationship and complete known lineage. Version0, unknown captures, malformed or partial records hold the entire mutation batch; they are never assumed to contain no earlier references.
- Resolve every first/latest decision against the same subject and exact original revision/receipt/notice. Validate purpose permission, expiry, touch time and every intervening choice through the original capture. Later withdrawal/regrant and current authority remain retained; current refusal or expiry must not erase legitimate historical evidence.
- Extend protection from the earliest referenced nested decision through all later history. This supplements the original enquiry decision and capture protections. Capture rows, four added fields and retained state remain byte-identical after application.
- Match the actual persisted input bounds, including256UTF16 text units, exact click/Google-ID strings, canonical lowercase UUIDs and permitted fields. Extra contact fields and query/fragment-bearing stored URLs reject. The fixed reviewed source origin is `https://blackswanrealestate.ae`; this is the existing site simulated by the isolated intake, not a new URL or publication. Other origins/ports and unsupported values hold rather than being rewritten.
- Hashes and `COMPLETE_SYNTHETIC` are consistency inputs, not authenticated collector completeness, deletion approval or external custody.

## Fixed controller mode

`SelectiveChoiceRetirement::purposeLab($db, $clock)` selects only `per_choice_purpose_synthetic_` and `SYNTHETIC_PURPOSE_PER_CHOICE_APPLICATION_V1`. It additionally requires `BSRE_PER_CHOICE_PURPOSE_LAB_ENABLED` and `BSRE_PER_CHOICE_PURPOSE_APPLY_ENABLED`, on top of the existing local-environment, synthetic home, owner, component and apply guards. Flags default off. No arbitrary table, planner callback or scope can be injected. The ordinary constructor remains plain-mode compatible.

Exact locked source/anchor rereads, full retained-state hashes, audit chaining, caller-transaction refusal, InnoDB/repeatable-read requirements, rollback and ambiguous-COMMIT readback are shared with the accepted controller. Any successful history pruning still irreversibly holds further application. Read-only reconciliation never clears that hold, reconstructs expired consent or authorizes reopening.

## Verification and remaining acceptance

The focused PHP8.2 suite passes41cases, including older nested decisions, subsequent withdrawals, malformed/cross-subject/unknown records, exact extended hashes, source origin/text boundaries, caller-reference preservation and fixed-mode guards. An initial regression failure exposed shared fixture references; the fixture was isolated, and malformed-touch cases now keep paired IDs consistent so a duplicate-conflict guard cannot mask a missing validator.

All68required local Foundation checks pass in57.295005seconds with PHP required; the ignored receipt is `test-output/purpose-retention-integration-20261110.json`. This includes existing plain-mode guard and source-provenance checks. It does not execute native MariaDB locally.

The first published attempt `b84feb0c` matched all378source files and passed both Foundation jobs. Its isolated job passed the existing38plain selective checks, then stopped before the new purpose workflow at `SELECTIVE_ISOLATED_LAB_ONLY`: the HTTPS request fixture made WordPress infer an HTTPS lab home. The harness now explicitly returns `http://bsre.invalid` for controller operations and the existing HTTPS source origin only during intake simulation, with a native assertion for that separation. The controller guard is unchanged. Lint and fresh revised-head native acceptance are required; this failure is retained rather than counted as purpose acceptance.

`purpose-selective-native.php` uses the actual purpose REST callback and source-derived store, links its receipt through the pinned pipe receiver, then retires against the same synthetic database. It requires actual SQL preservation, faults/readback and competing choose/stage lock orderings. Google/Sheets/mail remain service doubles; the original signed body and26-column schema must stay unchanged. Native acceptance requires the final exact-source isolated Ubuntu job; PHP lint and pure tests cannot establish it.

Main-window source review and focused verification continued; independent human review remains mandatory. Fresh installed-source verification, authenticated complete collectors, recovery custody, actual provider/staff/business evidence and separately scoped production authorization remain open.

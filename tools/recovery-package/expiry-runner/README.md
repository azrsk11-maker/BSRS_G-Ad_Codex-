# Disabled synthetic recovery-copy expiry runner

This small orchestration candidate wraps the existing authenticated per-file recovery-package expiry function. It has no scheduler, network/provider client, mail sender, keys, production records, ACL implementation or restore operation. Every job and adapter uses SYNTHETIC_BSRE_LAB plus the separate SYNTHETIC_RECOVERY_COPY_EXPIRY_V1 purpose. Only SYNTHETIC_*.bsre basenames are admitted. Escape paths, ordinary backup names, changed manifests and other purposes hold.

The default runExpiry mode is PLAN_ONLY and performs no journal, provider or key-resolver operation. An explicit run requires enabled:true and authorization:RUN_SYNTHETIC_EXPIRY_ONLY. This is a lab operation acknowledgement, not an owner permission or production approval. All reports keep productionAcceptance, expirySchedulingAccepted and providerCustodyAccepted false.

## Small API

    expiryJob({filename, packageSha256, expiresAtMs})
    initialState()
    runExpiry({jobs, journal, provider, nowMs, enabled:false, authorization:null, maxJobs:8})
    acknowledgeAlert(journal, receiptId, {nowMs})
    ownerFileProvider(directory, async jobId => ephemeralKeyBuffer)

Job identity binds the exact encrypted-file SHA256, synthetic basename, purpose, source and due time. Supply expiry from the existing package writer's receipt. The existing authenticated cleanup still refuses early deletion, wrong keys, other package sources, tampering and unsafe paths. No source label, hash or deadline authenticates a provider or proves a real deletion policy is deployed.

The bounded journal contains at most 32 jobs, processes at most eight per invocation, retries at most three times with a 60-second minimum backoff and admits at most 128 KiB of serialized state. Reusing a filename with a new encrypted identity is held. Caller times must advance monotonically. Job manifests, intent and completion are checked on every load. Reports contain only constant codes and aggregate counts; keys, file names, hashes and private provider errors are omitted.

The caller must supply a separately accepted synthetic journal adapter with source/purpose and exclusive(async transaction => ...). The transaction supplies asynchronous load() and save(state). Save must durably commit before resolving; exclusive must serialize all writers across processes. The separate [explicit POSIX local journal](LOCAL_JOURNAL.md) implements local storage and exclusion for synthetic fixtures; it does not establish production/provider custody or stale-lock recovery. Flags and this interface cannot establish those properties. The original focused fixture adapter still simulates saved state, failures and exclusivity; the separate local-journal suite must exercise actual Linux persistence and competing processes. Hardware power-loss and genuine custody acceptance remain required.

Before deletion, the runner inspects the exact encrypted identity and durably saves INTENT. An authenticated cleanup receipt yields AUTHENTICATED_EXPIRY_DELETED. If deletion succeeded but its acknowledgement or completion save was lost, restart can reconcile the still-absent pathname only after that saved intent. Its receipt is ABSENCE_RECONCILED_AFTER_INTENT: it does not claim who deleted the file or that the former package can still be authenticated. Absence without intent and replacement bytes hold. A failed intent save prevents deletion; a failed completion save leaves the earlier intent available. Terminal jobs do not repeat deletion.

Completion must fall between its saved intent and the journal's last observed clock; a future fabricated completion holds before provider effects. Completion clears the current error while preserving any historical pending alert, which still needs explicit acknowledgement. A historical alert cannot originate after completion.

Each provider failure creates one bounded pending alert receipt in the same journal when that journal remains writable. An unavailable journal cannot guarantee persistence of its own failure alert; the caller receives a constant HOLD code and still needs out-of-band monitoring. The receipt has no mail address, recipient, content delivery or external send. acknowledgeAlert is a separate explicit outbox acknowledgement and returns deliveryVerified:false. Repeated acknowledgement is idempotent. A later failure after acknowledgement gets a new attempt-bound receipt, preventing an old acknowledgement from clearing the newer alert. Operators still need genuine alert delivery, monitoring and recovery procedures.

The optional local ownerFileProvider delegates deletion to deleteExpiredOwnerOnlyPackage from ../package.mjs. Inspection requires a current-user-owned POSIX 0700 directory, regular single-link 0600 file, bounded reads, stable identity and no symlink components. Windows fails closed until a reviewed ACL adapter exists. It uses the same trusted-owner/OS assumption as the existing helper: the inspect-to-delete interval is not an atomic hostile-owner inode/hash-conditional unlink guarantee. Callers must preserve immutable names and exclude concurrent owner file replacement. No such production custody or writer-lease guarantee is claimed.

## Focused verification and remaining gates

    node --test tools/recovery-package/expiry-runner/runner.test.mjs

Tests use only synthetic identities, fabricated journal/provider adapters, ephemeral random keys and disposable temporary packages. They cover default-off, scope/path refusal, exact deadline, durable intent ordering, lost acknowledgements, storage-write failure/restart, changed/absent identities, backoff/attempt/batch bounds, idempotent alert receipts, serialized invocation and owner-file guards. Linux must execute the actual POSIX file deletion/symlink branch; Windows exercises explicit unsupported refusal.

This is preparation for an expiry orchestrator, not acceptance of a scheduled provider purge. Real durable custody, failure-alert delivery, key rotation/destruction, filesystem/provider race handling, independent absence evidence, external deletion-ledger authority and a genuine nonempty restore rehearsal remain held. Nothing here authorizes reopening a service or deleting mailbox data.

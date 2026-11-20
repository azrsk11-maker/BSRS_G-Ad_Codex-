# Explicit synthetic local expiry journal

This POSIX adapter supplies actual local storage for the existing [expiry runner](README.md) contract. It is disabled by default, accepts only the synthetic source/purpose, and performs no production admission, scheduling, provider request, mail operation, key storage, selective consent deletion or restore. Windows refuses before filesystem access; a separate reviewed ACL implementation is still needed there. Existing runner and package behavior is unchanged.

## Initialization and use

Create an empty, current-user-owned `0700` directory with a basename matching `bsre-synthetic-expiry-journal-` followed by six to eighty letters, digits, underscores or hyphens. The caller creates this dedicated directory; the adapter never repairs permissions or adopts an existing directory containing other files. A symlink or symlink-containing resolved path is refused.

```js
const receipt = await initializeLocalJournal(directory, {
  enabled: true,
  authorization: 'INITIALIZE_SYNTHETIC_LOCAL_JOURNAL'
});
const journal = createLocalJournal(directory, {
  journalId: receipt.journalId,
  enabled: true,
  authorization: 'USE_SYNTHETIC_LOCAL_JOURNAL'
});
// Supply journal to runExpiry; its independent default-off/run acknowledgement still applies.
```

The acknowledgements are literal lab opt-ins, not owner approval or authentication. Initialization returns `productionAcceptance:false` and `providerCustodyAccepted:false`. The journal also keeps production acceptance false. Protect and retain the expected journal ID separately; it is an identity binding, not a secret or external freshness certificate. Creation options are copied so later caller mutation cannot silently enable or retarget an instance.

Initialization writes only the fixed synthetic identity and state filenames in a new empty directory. It never overwrites or reinitializes an existing journal. Missing state, partial initialization, unknown files, abandoned temporary files, corrupt framing, a wrong expected identity and unsafe permissions hold. State and owner records are regular single-link `0600` files; reads are bounded and verify open-file and pathname identity. Parent-directory identity is rechecked at mutation boundaries.

## Persistence and exclusion protocol

`exclusive(async tx => ...)` creates a fixed lock directory atomically. A fresh random owner token and exact lock inode bind the lease. The owner record, lock directory and parent directory are synced before the lease can run user operations. Competing processes receive a held-lock error; they do not wait indefinitely or remove it.

The transaction offers `load()` and `save(state)`. Load must precede save. Save captures a bounded JSON copy at invocation, so subsequent caller mutation cannot alter queued bytes. Operations are serialized and any already-queued save drains before the lease is released, even if the caller omitted its await. Escaped transaction methods reject after the callback ends.

Each save checks the current identity and exact previously read state inode, bytes and generation. It creates an exclusive new `0600` temporary file, writes and syncs it, rechecks the current target, atomically renames it over the known state file, syncs the containing directory and rereads the committed bytes/inode. Only then does the save promise resolve. A successful callback return also waits for lease cleanup. Serialization constructs a bounded fresh data-only copy; accessors, custom serializers, symbols, non-enumerable fields, custom prototypes, sparse/oversized arrays and excessive strings/depth/bytes are refused before whole-state serialization. The envelope's generation and SHA256 detect inconsistent bytes and stale observations within that instance; they do not authenticate custody or detect a restored old valid envelope in a fresh process.

[Linux fsync documentation](https://man7.org/linux/man-pages/man2/fsync.2.html) explains why syncing the file alone is insufficient for its containing directory entry. [Linux rename documentation](https://man7.org/linux/man-pages/man2/rename.2.html) describes atomic replacement, and [Node FileHandle.sync](https://nodejs.org/api/fs.html#filehandlesync) exposes the file sync operation used here. These calls and readbacks do not certify a filesystem, disk controller, provider, hardware power-loss behavior or backup policy.

Each save is durable independently; the callback is an exclusive lease, not a rollback transaction. A callback failure after an acknowledged save preserves that save and returns a constant error. A failed or ambiguous storage operation poisons the lease and retains its lock for reconciliation; no provider effect should follow a rejected intent save. The runner still validates the complete business-state schema before acting. The journal validates only bounded data-only JSON, root scope and storage consistency; it cannot establish source completeness or legitimate business outcomes.

## Crash and recovery boundary

Cleanup reads the exact created lock-directory and owner-record inodes plus owner token before removing anything. Changed owner records or directories hold and remain untouched, including a replacement owner file that copies the old token. A killed process leaves its lock held. There is **no** automatic PID-liveness test, timeout lease stealing, TTL deletion or stale-lock recovery function. Unknown temporary files or an interrupted initialization likewise require explicit review. Recovery needs an independently reviewed procedure with current state, custody and absence evidence; this adapter cannot authorize that review itself.

The path and inode protocol assumes a trusted same-user process and OS, matching the existing package helper. Node pathname operations do not provide a hostile-owner, inode-conditional replacement/unlink boundary. Cooperating writers must use the journal lease; root or another process with the same ownership can defeat those assumptions. Production provider custody, external current anchors, real alert delivery, scheduled operations and useful nonempty recovery remain unverified.

## Focused acceptance

```text
node --test tools/recovery-package/expiry-runner/local-journal.test.mjs
```

Five data/default/scope/Windows checks pass locally on Windows; seventeen POSIX cases are explicitly skipped there. Linux must execute the POSIX cases: real modes and generation saves, fresh-process reads, actual competing-process exclusion, acknowledged-save crash with a retained lock, lost-ack reconciliation, queued-save draining, corrupt/missing/oversized state, unsafe paths/links, external state changes, owner-token and identical-token inode replacement, and real synthetic encrypted-package expiry with persisted state. Two separately labeled fault tests simulate a file-sync error before rename and a directory-sync error after rename; they check rejected acknowledgement, zero subsequent effect and retained locks against actual old/new file bytes. They simulate syscall rejection, not a disk or power failure. Child readiness and termination have bounded timers, and test children suppress raw output. The kill test demonstrates process-crash handling, not hardware power-loss durability. All packages, clocks and outcomes are fabricated; no production conversion, record or mailbox operation occurs.

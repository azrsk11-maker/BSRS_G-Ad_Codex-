# Local recovery journal and negative-review chronology

## Verified starting point

Published `b48aa6592a577616687538066ffdc6bf00365a78` exactly matches all358reviewed files and passed all three required CI jobs. [Accepted source, results and remaining gates](https://github.com/azrsk11-maker/BSRS_G-Ad_Codex-/pull/8#issuecomment-6768821977). A fresh readback found the PR open/unmerged, main unchanged, no human reviews and no new owner instructions. This continuation makes no production, live-tracking, Ads, permission or financial-record changes.

## Actual local storage candidate

The previous expiry runner depended on an injected journal contract. The [explicit local journal](../../tools/recovery-package/expiry-runner/LOCAL_JOURNAL.md) now supplies real POSIX storage for synthetic use: empty dedicated owner-private initialization, fixed identity, bounded0600state, atomic replacement, file/directory sync and readback, cross-process exclusion and exact lock-directory/owner-file/token checks. Escaped or poisoned transaction methods hold; acknowledged saves survive normal reopening. Crashes, ambiguous saves and abandoned temporary files retain a hold rather than stealing a lease or reinitializing missing state.

Review corrected custom-serialization/sparse-array bounds and exact owner-file identity. The code remains default-disabled and validates only storage consistency, not complete business schema or source authenticity. A hash/generation cannot establish external freshness in a restored fresh process. Real provider custody, hardware power-loss behavior, stale-lock recovery, scheduling, alert delivery and useful nonempty recovery remain separate acceptance gates. Existing package encryption, expiry, runner flags and consent helpers are unchanged.

## Negative evidence chronology

Three synthetic counterexamples previously passed research/approval despite supporting evidence or research occurring later. The validator now requires source/query/used-metric observations at or before research and research plus applicable scope/context/protected reviews at or before exclusion approval. Approval-only holds preserve valid research and the coverage classifier's established hold prefix. Same-day equality reflects the existing date granularity; no stronger timing or authenticated approval is inferred.

Protected dependency dates are precomputed once per campaign, retaining invalid-date holds. An operation-count regression prevents reintroducing a corpus-date scan for each negative. Matching, protected-intent conflict logic, scope bindings, target counts and actual source/library artifacts remain unchanged. The actual reviewed masters remain0/14,000each.

## Acceptance and limitations

The keyword-only suite passed177cases in12.829seconds, including17new regressions. The journal's Windows-focused run passed5cases and explicitly skipped17POSIXcases; all17must execute successfully in Linux CI. Those include actual file modes, fresh-process reads, competing processes, killed-writer holds, persisted intent, real synthetic encrypted expiry and exact owner-file replacement refusal. Two injected sync failures use actual old/new file bytes while remaining simulations, not proof of hardware power-loss safety.

Both independent source reviews cleared the final revisions. All60required local Foundation checks pass in127.933307seconds with PHP required; the receipt is saved under ignored `test-output/local-journal-negative-chronology-20261110.json`. The journal suite is mandatory in the repository checker. Existing Windows capability limits and the17explicit POSIX skips require real Linux execution; local guard results are not that acceptance. Exact source publication and all three current-head jobs remain mandatory. Broader regression checks were required because keyword validation is shared by research, triage, protected simulation and complete-library coverage. Differing suite timings are not a controlled performance comparison.

The full project remains incomplete: both reviewed keyword masters, verified native content/business evidence, actual staff workload/rehearsal results, authenticated installed-source and integration checks, genuine imports/conversions/finance, independent human review and separately scoped production authorizations remain required. No safe synthetic result replaces these gates.

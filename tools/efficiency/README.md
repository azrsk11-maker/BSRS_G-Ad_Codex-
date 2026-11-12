# Efficiency audit — 7 November 2026

## Current ARM result and follow-up — 13 November 2026

Actual ARM execution completed all559keyword cases/44modules in169.343477s,zero skips,complete ordered coverage and no timeout under the original300s bound. Full acceptance was false because a filesystem-order-dependent tamper test targeted the preview. The follow-up selects the manifest-pinned source and requires an exact byte-hash rejection under both discovery orders; validator/data and case counts stay unchanged. The focused real reporting worker passes allthree cases. [Actual runtime, limits, root cause and current-CI requirement](../../docs/audit/ARM_RUNTIME_TRIAL_2026-11-13.json). Cloud hosts/images differ; no causal speedup percentage or passing combined CI is inferred from the first failed ARM run.


## Current runtime trial — 13 November 2026

Foundation's existing300s keyword bound stopped the559-case/44-module source at535finished cases. The copier experiment was withdrawn after its benefit gate failed. A reversible trial now requests the standard public-repository Ubuntu24.04 ARM runner, retaining Python3.12, all cases, source/history checks, process/resource controls and both WordPress jobs. The startup observer validates actual Linux/aarch64/public-repository metadata and emits a bounded whitelist; it grants no acceptance. Complete local efficiency tests:115cases,112passed/threeexisting platform skips. [Baseline, pricing evidence, trial gates and rollback](../../docs/audit/ARM_RUNTIME_TRIAL_2026-11-13.json). Actual ARM completion and performance remain unproven until current-head CI finishes. Earlier measurements below keep their original scopes.


## Retain failures and partial progress on timeout — 11 November 2026

An actual required Foundation attempt exceeded the existing300-second keyword-suite bound. The old top-level handler discarded the successful earlier checks and all partial output. `execute_check` now records an explicit failed timed-out check, bounded decoded partial output in the ignored local report, and elapsed time, allowing the remaining checks to run while overall acceptance stays false. Incomplete TAP evidence cannot become a successful numeric summary. Normal commands, serial order and the300/120-second budgets stay unchanged. Fifteen focused timeout/summary regressions pass; no full current-source PASS is claimed. [Attempt and bounded diagnostics](../../docs/audit/OFQUAL_CONCURRENCY_CHECKS_2026-11-11.json).

## Opt-in two-check concurrency experiment — 11 November 2026

`benchmark_check_groups.py --run` compares the existing historical vendor-coverage verifier and release-control test suite serially, then with two workers. It preserves their commands, 120-second timeouts, ordered results and complete output comparisons. Only the unittest elapsed-time field is normalized; source bytes, observer code and Python identity are pinned. It neither changes Foundation defaults nor caches acceptance results. [Measured receipt](check-group-concurrency-2026-11-11.json).

One actual pair took **81.060296 seconds serial and 52.338413 seconds concurrent**, a 28.721883-second observed reduction (1.548773 ratio). Complete outcomes matched on the same 682-file source snapshot. The first check validates a historical 8,035-record snapshot, not the current 10,610-record library. Seven focused regressions cover output drift, failures, timeouts, source drift and two-worker ordering. This is one serial-first comparison with uncontrolled warming and contention; it establishes no whole-Foundation, token, API or billing gain. Individual-check timings were not retained. Forced timeout terminates the direct Python process; nested Node cleanup and temporary-fixture removal are not guaranteed. The helper remains opt-in pending further adoption review.

## Bounded evidence inspection — 11 November 2026

`inspect_json.py` prevents an observed inspection error: omitting top-level `records` did not prevent PowerShell from serializing `source_projection.records`. It is read-only, shows root structure by default, and emits explicitly selected dotted fields only within a complete UTF-8 output limit (default 4,000 bytes, maximum 16,000). Input is bounded to 4 MiB by default, with a 32 MiB maximum. Duplicate keys, malformed/nonfinite JSON, missing selectors and oversized output fail with sanitized error codes; there is no partial-content success, network request or file writer. Keys containing dots are not addressable by its deliberately small selector syntax.

Example from repository root:

```powershell
python -B tools/efficiency/inspect_json.py docs/audit/keyword-valuation-employment-2026-11-11/membership-snapshot.json --select counts --select equal_token_baseline_peers
```

The [measured comparison](json-inspection-2026-11-11.json) used one unchanged, already-parsed public follow-up export. Selecting the same three requested metadata fields produced identical values in **525 bytes versus 399,992 bytes** for the full formatted document (99.87% less output). Seven alternating serialization pairs measured medians of 0.0082594 seconds full and 0.0000597 seconds selected. This excludes parsing, disk reads, tool/network latency and model reasoning. Exact token, provider-call, billing and whole-project savings are unavailable; no broader speedup is claimed. Twelve focused regressions cover the bounds, strict parsing, selectors and absence of unsolicited nested values. This inspection utility is not a provenance, admission or production-acceptance validator.

The [earlier Foundation receipt](../../docs/audit/VALUATION_INSPECTION_CHECKS_2026-11-11.json) took542.506050s, versus the earlier uncontrolled474.687330s run. Its largest subprocess was the keyword suite at275.250875s; the five largest checks account for most elapsed time. The runner is serial, but repeated historical validation protects freshness and independent entrypoints; no redundant check was justified for removal. Reuse completed implementation receipts for documentation-only changes. The later opt-in experiment above preserves every selected check/timeout/ordered result; Foundation concurrency has not been adopted.

## Safe Foundation evidence summaries — 10 November 2026

The existing Foundation checker now requests Node's [TAP reporter](https://nodejs.org/api/test.html#test-reporters) explicitly for the synthetic local-journal suite. It extracts the complete bounded numeric trailer from that already-executed command's stdout and prints one `TEST_SUMMARY` JSON line. No second test execution, raw test text, private path, stderr or arbitrary receipt field is exported. The fixed check name selects this evidence requirement internally; missing/malformed counters, nonzero exits, failures/cancellations or an entirely skipped suite cannot pass that check. Other command checks retain their existing exit semantics.

Counters are observed test evidence, not source authentication or production acceptance. `runner_platform` is the Python runner's platform, not an independently queried Node-child identity. Pass, skipped and todo remain separate; `release_authorized` is always false. The full test output still remains only in the ignored local report tail. Nine focused regressions cover valid Windows/Linux counter examples, malformed/truncated/oversized trailers, status preservation and payload filtering. The mandatory efficiency test discovery includes them automatically.

Run `python -B -m unittest discover -s tools/efficiency -p test_foundation_summary.py` for the focused reporter checks. A full Foundation run is still required for combined acceptance; current-head CI establishes actual Linux results. This removes the prior need to infer case totals from a suite exit while leaving test selection and production gates unchanged.

This is a local, read-only audit utility. It does not execute recorded commands, contact APIs, change application settings or touch production. Only aggregate reports are retained. No raw logs, credentials or prospect data belong in this directory.

## Verified baseline

[baseline-audit.json](baseline-audit.json) covers the available tail of the exact BSRS_G-Adwords thread, using the fixed UTC interval 3 November 00:00 through 7 November 05:21:26.520. The source was 38,750,178 bytes; the scan consumed 8,388,609 logical bytes and omitted a prefix. This is a bounded sample, not a complete historical audit. The 153 MB compressed archive was not opened.

| Observation | Measured result | Interpretation |
|---|---:|---|
| Outer tool calls / paired outputs | 59 / 59 | Tool events, not underlying HTTP API calls |
| Browser calls | 33; median 0.912 s; maximum 28.210 s | Largest observed latency group; total latency can overlap |
| Literal shell invocations | 12 | Nine read and three search category occurrences; categories can overlap |
| Exact repeated shell / tool payload groups | 0 / 0 | No evidence here of repeated identical commands; semantic duplication is not established |
| Outputs exceeding 6,000 characters | 17 | Review candidates; required documentation is not automatically waste |
| Paired output volume | 353,076 UTF-8 bytes | Largest output 58,919 bytes |
| Reported response usage | 11,619,619 input; 11,244,800 cached input; 18,087 output | 68 unique response records; not billing or this agent's total usage |

Three timeout and two stale/unattached lexical markers occurred. These are not confirmed failures or proof of repeated authentication. No unnecessary full test suite is established by this sample. Command CPU time, persistent process utilization, actual HTTP API counts, hidden provider calls and overall token savings are unavailable.

Prior `work/consent-focus-live-2026-11-02/TURN-METRICS.md` already records six isolated focus cases and 16 retention checks instead of repeated full suites. The prior optimization reports from 22–24 October already introduced bounded readers and the sanitizer reused here. No historical improvement is claimed as newly achieved.

## Safe optimization implemented

`tools/audit_runner.py` adds a bounded, metadata-keyed cache around the existing sanitized `codex_metrics.py`. It invalidates on source identity/size/timestamps, analyzer or wrapper source changes, and audit options. It rejects corrupted or altered cache payloads and does not cache a source that changes while being read. Cache hits avoid rereading source logs and produce the same aggregate report. A cache digest detects corruption; it is not an adversarial integrity or authentication mechanism.

The reused analyzer is copied unchanged from the earlier project tools. SHA-256: `0a3994e56ab0baa4f4e35073b511841f1d8989f09a288fe9ee48c4ccbf45872c`.

[repeat-audit-benchmark.json](repeat-audit-benchmark.json) records one cold/warm pair on the actual log:

| Run | In-process elapsed | Logical source bytes read | Report |
|---|---:|---:|---|
| Cold bounded scan | 0.333560 s | 8,388,609 | 3,749 compact bytes |
| Unchanged cache reuse | 0.004558 s | 0 | Identical |

This demonstrates reuse for one repeated audit. It excludes process/tool startup, is not a statistically repeated benchmark, and does not establish overall project speed or token savings. Source metadata changes intentionally invalidate the whole cached summary. Use `--refresh` after an external rewrite that preserves file metadata; the source log itself is not content-hashed.

Ten focused tests passed in 0.063 s: cold/warm parity, source/window invalidation, forced refresh, malformed/tampered cache recovery, redaction, changing-source refusal, invalid input bounds and refusal to overwrite a source log with a report. No unrelated production tests were rerun.

A later check, recorded in [active-log-recheck.json](active-log-recheck.json), encountered an actively changing source twice and correctly refused both cache writes. No third retry was made. The successful benchmark above is the original observed pair, preserved from its aggregate cache and tool result; it is not a claim that active logs can be reused unchanged. The later CLI overwrite guard does not change the cache execution path.

## Reuse

The installed jCodeMunch virtual environment provides verified Python 3.12.14. Windows `python`/`python3` resolve to a nonfunctional Store alias; do not retry them or install another runtime for this task.

```powershell
$auditPython = Join-Path $env:USERPROFILE '.codex/tools/jcodemunch/venv/Scripts/python.exe'
& $auditPython -B tools/test_audit_runner.py
& $auditPython -B tools/audit_runner.py --since 2026-11-03T00:00:00Z --until 2026-11-07T05:21:26.520Z --tail-mib 8 --cache-dir .cache --report audit.json '<explicit-session-jsonl-path>'
```

Run from this directory and supply an existing explicit JSONL file; never expand every session or decompress archives by default. Rerun the identical command to reuse an unchanged result. The CLI prints only a compact status. Read the JSON report only when its metrics are relevant. `.cache` and bytecode are excluded from version control.

Continue using one browser writer, bounded discovery, independent agents with separate ownership, and the existing two-failure investigation rule. Verify authentication/account identity once per affected surface and stop repeated login attempts when the observed problem is access configuration. These are operating controls, not newly measured gains.

## Pinned working tree verification

`verify_worktree.py` compares current file bytes with one pinned Git commit using a single `cat-file --batch` process. It preserves the prior comparison report fields, includes untracked nonignored files and reports missing, unexpected and changed paths. It validates NUL-delimited names and binary framing, bounds input sizes, checks for local changes while reading, and rejects symlinks, junctions and submodules that require separate verification. It performs no fetch or write.

From the repository root, fetch the authorized branch when a refresh is needed, then run the comparison.

```powershell
$auditPython = Join-Path $env:USERPROFILE '.codex/tools/jcodemunch/venv/Scripts/python.exe'
git fetch -q origin codex/phase0-audit-foundation
& $auditPython -B tools/efficiency/verify_worktree.py
```

Exit0 means exact equality. Exit1 means reported differences. Exit2 means verification could not complete. The old helper returned zero even for differences, so callers adopting the CLI must handle this intentional exit-status improvement. JSON comparison fields remain equivalent.

The [controlled comparison](../../docs/audit/worktree-verifier-benchmark-2026-11-08.json) used identical local bytes and the same reference. Both implementations reported the same four unpublished files and two modified files among245local/241remote paths. The existing per-file implementation took32.4701715seconds and the final batch implementation2.1997987seconds. This single ordered pair measured a14.76xratio and30.27seconds less elapsed time. The legacy run came first and may have warmed the filesystem cache. It establishes this task's measured result only; total token, provider API and whole-project gains are unmeasured.

The nonempty batch comparison uses five Git processes independent of shared-file count. The original algorithm launches one `git show` per shared file plus three discovery/ref calls. These process counts follow the executed algorithms; they are not provider API counts.

The focused suite has16cases. Fourteen passed and two Windows capability cases were skipped. Junction detection and resolved-path escape checks ran through mocks because the attempted real junction fixture was blocked by tool policy. Linux CI must exercise newline filenames and supported symlink creation. Independent review verified the final containment fix.

## Controlled remeasurement of existing Git batching

[`benchmark_worktree.py`](benchmark_worktree.py) measures the existing verifier against an explicitly constructed baseline using the same discovery and raw-byte guards with one `git cat-file blob` process per shared path. It is not a recovered historical implementation or a newly implemented optimization. It changes no verifier, acceptance rule, Git ref or production setting, and has no network/API path.

The [10 November result](benchmark-worktree-2026-11-10.json) pins `bc8c72b282454ebeff44f39b993ea7928b20523a`. One batch warmup and three alternating measured pairs each compared all337files and24,063,805raw bytes. Complete comparison reports and per-path local/Git byte digests matched across all seven runs, with337byte-equal files and no missing, unexpected or changed paths.

| Reader | Median elapsed | Actual Git processes per comparison |
|---|---:|---:|
| Constructed per-file baseline | 21.255469s | 341 |
| Existing batched verifier | 1.004085s | 5 |

The measured median ratio is21.17x, with20.251384seconds less elapsed time for this task. The benchmark completed in67.272553seconds. These are local Git process counts, not provider API requests. Timings include Git subprocess startup, raw-byte guards and digest observation within one Python process; outer tool/Python startup is excluded. This is one Windows checkout with three pairs. Desktop/browser activity was not isolated, and six small synthetic fixture tests briefly overlapped the first baseline run; every trial is retained. No token, billing or whole-project improvement is established.

The runner requires an explicit full commit and a complete byte-equal tree, checks all reports/digests across runs and stops on changes or its time budget. Reports cannot overwrite an existing file; inside the checked tree they must use an ignored `test-output` or `.cache` location. Six focused synthetic tests cover binary/duplicate-blob parity, exact process counts, line-ending changes, changed inputs between runs, elapsed-budget enforcement, output guards and bounds. Independent source review found a budget edge, which was fixed before measurement.

To repeat, point the tool at a separate clean checkout of the pinned source with raw Git bytes preserved (`core.autocrlf=false`). Keep the runner and its output outside that checkout so adding them does not alter the337-file input. The tool does not create or mutate a checkout.

```powershell
& $auditPython -B tools/efficiency/benchmark_worktree.py --root '<clean-pinned-checkout>' --ref bc8c72b282454ebeff44f39b993ea7928b20523a --pairs 3 --max-seconds 180 --report '<outside-checkout>/paired-report.json'
& $auditPython -B -m unittest discover -s tools/efficiency -p test_benchmark_worktree.py
```

## Inline tree publication

For an explicitly reviewed batch of UTF-8 regular files, pass each file as a GitHub tree entry with `path`, `mode`, `type: blob` and `content`. Read the raw bytes and decode UTF-8 without newline conversion. Preserve each file's mode and pin the base tree to the expected feature-branch head. For binary files, use the existing blob path. [GitHub tree API](https://docs.github.com/en/rest/git/trees#create-a-tree)

A three-file no-change probe on ff546e6 included the project rules, this README and the retention-admission receipt. The connector returned the exact original tree hash in one request (0.916 seconds). The previous method would require three blob requests and one tree request for the same inputs. The request-count comparison follows the two procedures. No comparable elapsed-time or token saving was measured.

Create the candidate commit, fetch its exact SHA and run `verify_worktree.py --ref <candidate-sha>` before moving the branch when the checkout represents that candidate. Require byte equality, confirm only the reviewed paths and modes changed, then use the expected-head guard and a non-force update. Read back the branch and current-head checks.

When using the command tool, a response with a session ID is an active process. Poll that same session until it returns a terminal result. An absent exit code does not authorize publication. Require `result.exit_code === 0`, parse the completed JSON receipt, and require `commit === candidateSha` and `byte_equal === local_files && byte_equal === remote_files`. A missing, malformed or contradictory receipt holds the ref update.

## Avoid duplicate Discovery verification in Foundation

The standalone Discovery CLI remains available, including its optional private-source checks. Foundation now relies on the original public-capture verification already required by the supply and triage checks. The two retained checks each rejected an altered Buyers batch in a disposable copy.

Three alternating local trials per variant measured the affected group at a median of 1.7668 seconds with three commands and 1.5314 seconds with two, a reduction of 0.2354 seconds (13.3%) on this Windows checkout. This is a measurement of that group only. The isolated WordPress job on the preceding revision spent 35 seconds building dependencies and 9 seconds running the isolated lab. Those stages are unchanged. Token use was unavailable.

## Dependency-build baseline, 10 November

The [accepted dd52 lab job](https://github.com/azrsk11-maker/BSRS_G-Ad_Codex-/actions/runs/42845032296/job/129930114847) has these observed consecutive-log boundaries. They include small dispatch overheads; they are not API-reported step durations or a hardware benchmark.

| Interval | Seconds |
|---|---:|
| Checkout | 1.460 |
| Source verification | 1.505 |
| Image build | 33.744 |
| Native execution | 11.696 |
| Cleanup | 0.152 |
| Total measured span | 48.557 |

Build is69.5% of that span. BuildKit directly reports16.3s for apt/PHP extensions,2.1s for the pinned WordPress archive,6.5s base pull and6.1s image export. The18.4s reusable dependency work is an upper-bound opportunity, not demonstrated cache savings: builder setup, cache transfers, source derivation and export still cost time.

No cache or builder change is adopted. A later bounded trial could cache only a public dependency stage, force source derivation fresh and compare actual whole-job warm time including setup/post-cache, while rerunning every acceptance check. A cache hit alone is insufficient. Keep existing allowance/settings, source pins, `--pull`, kernel `--network none`, read-only runtime and absence of production credentials.

Cached `RUN apt-get` layers do not refresh merely with age; a trial needs an explicit refresh epoch. GitHub's inactivity-based eviction is not dependency freshness. PR merge-ref caches are scoped and cannot be consumed by main or another PR. These constraints follow [Docker invalidation](https://docs.docker.com/build/cache/invalidation/#run-instructions), [Docker GHA cache behavior](https://docs.docker.com/build/cache/backends/gha/) and [GitHub access restrictions](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching#restrictions-for-accessing-a-cache). No extra run, paid setting, permission expansion or cache write was made for this measurement.

## Observed Planner access and inspection, 11 November

[The paired observation](planner-navigation-2026-11-11.json) records two routes to the same verified Real Estate account and ready Keyword Planner home, in the existing authenticated Chrome session. The baseline uses the official Ads entry, existing sign-in link and visible Tools→Planning→Keyword Planner controls. The smaller route opens the **actual URL previously observed in that same browser**, then verifies the account, Planner readiness and absence of a visible blocker again.

| Bounded navigation sample | Explicit browser API calls | Summed awaited-call time |
| --- | ---: | ---: |
| Official entry and menu path | 15 | 12.146 seconds |
| Reused observed Planner route | 6 | 1.202 seconds |

Nine fewer explicit browser method calls reached the same checked postcondition. This is **one sequential existing-session pair**, with different cache warmness. Times exclude model/reasoning gaps and unobserved network work; method counts are not HTTP request counts. No repeatable whole-task speedup, token saving, billing saving or campaign/conversion improvement is inferred.

Retain only the observed URL in private session state. Do not publish its account/query values, reconstruct opaque parameters, reuse it across unverified accounts, store credentials or bypass verification. Before any research action require account573-038-4686, the intended marketing account, ready Planner and no actual access blocker. If that route or private context is unavailable, return to the official visible navigation. No browser/account setting or permission was changed.

The same evidence file records a reversible **inspection-display** reduction over all2,262new source phrases. Exact recurring strings `abu dhabi`, `sharjah`, `for rent` and `for sale` were shown as collision-checked AD/SH/FR/FS aliases while reading the corpus. Every displayed string round-trips to its original. Keyword-text payload is76,269UTF8bytes before and58,296after, excluding row labels and the legend. Original capture strings, provenance, proposals, public data and counts remain unencoded and unchanged. This measures display bytes, **not tokens**; provider token use and billing are unavailable. No approval, business fact, geographic assignment or research phrase is created by display encoding.

## Bounded lexical preprocessing, 11 November

The existing required-check receipts identified `keyword-abu-sharjah-triage` and `keyword-observed-review-reconciliation` as the two slowest commands. Their repeated conservative matching normalized/tokenized the same short literals many times. `negative_matches` now reuses only immutable token tuples and frozensets in a process-local LRU, capped at 4,096 entries and 512 input characters per entry. Larger or nonstandard inputs retain the uncached path and its existing validation. Public `tokens()` still returns a fresh mutable list. Nothing is written to disk; no research verdict, source verification, approval, report or test result is cached.

[The measured receipt](lexical-matching-2026-11-11.json) binds the before/after matcher hashes and the exact unchanged input/verifier/report bytes. Both complete required Foundation executions already supplied these subprocess timings; no extra baseline or probe execution was added.

| Same-input command | Before | After | Observed reduction |
| --- | ---: | ---: | ---: |
| Abu Dhabi/Sharjah triage reproduction | 33.382833 s | 4.871281 s | 85.408% |
| Complete source/review reconciliation | 38.562353 s | 6.921639 s | 82.051% |

Every frozen workbench/protection screen and the combined reconciliation still reproduces exactly. Six focused regressions cover Unicode/wrappers/punctuation, close variants, repeated words, mutation isolation, nonstring/unhashable inputs, oversized strings, eviction and invalid/empty match cases. These are automatically included in the existing keyword suite; they do not replace any acceptance checks.

The full local checklist remains 84 named checks, all passing with PHP required: 146.091538 seconds before and 81.457086 after. Its after run also contains six additional tests, so total timing is descriptive. The two same-input command timings are one sequential local pair, not a median; CPU scheduling and filesystem warmth are uncontrolled. No whole-task, token, API, billing, campaign-performance or production-readiness saving is inferred. Retain this reversible source change because it reduces observed repeated computation while preserving the exact evidence outputs. CI still reruns all required checks at the final uploaded revision.

## Bounded keyword-module execution

Foundation executes every discovered keyword test module in a separate Python process, using an observed resource budget of at most four concurrent workers. Module isolation preserves process-local mocks and class fixtures; an audit found all filesystem writes use unique temporary directories. In-process module threads are unsafe. Discovery is dynamic; no test-module allowlist or acceptance cache is used.

The12November runtime repair replaces the fixedtwo-worker scheduling limit with `--workers auto`: the minimum of effective CPUs (including affinity/cgroup quota), four and availableRAM/2GiB, with conservative one-worker fallback. Explicit `--workers 1` or `2` preserve previous bounded behavior; requested3/4workers require observed headroom. `worker_resources` is revalidated in the Foundation receipt. The already-executed check also emits one validated `KEYWORD_SUMMARY` in the job log with completed case/module counts, elapsed time and actual worker/CPU/RAM observation. It revalidates completion/resources and withholds arbitrary fields; no extra run or raw output is used. Known costly suites start earlier, while dynamic discovery and per-module/class/test ordering remain complete. No fixture/source/verdict cache is added. The local Windows audit has about1GiB available and selectsone; fresh CI must supply actual resource selection and full acceptance. [Timing, tests and limits](../../docs/audit/KEYWORD_RUNTIME_DIAGNOSTICS_2026-11-12.json).

`keyword_progress.py` appends bounded metadata at module boundaries and five-second intervals to a unique ignored1MiB JSONL file. A killed final append preserves the last complete line. The timeout reader exposes only checked module/count/time fields and an explicit diagnostic-only/acceptancefalse marker. Write failures disable the optional observer once; they cannot change test selection or verdicts. Raw logs and private data are excluded. A completed progress row never replaces the complete identity/receipt checks.

The same aggregate300-second deadline begins before supervisor loading/job setup and covers discovery, all workers and evidence completion. Each discovered test must have exactly one ordered start/finish outcome. Missing/duplicate/unknown IDs, crashes, fixture/import errors, inconsistent counts and late completion fail. Existing capability skips remain visible. Every run writes a unique ignored `test-output/keyword-modules-*.json` receipt; it is never read to reuse acceptance.

Foundation uses the opt-in `owned_process.run_owned` supervisor only for this check. Windows assigns the gated runner to a noninheritable KillOnJobClose job before test imports or descendant creation; assignment errors fail closed. POSIX uses a dedicated process group killed on timeout/final cleanup. Only the Windows job guarantees descendant termination after abrupt supervisor death. Linux-native cleanup requires Linux execution; a Windows skip is not Linux evidence. No host process settings, dependencies, network access or production state are changed.

The CLI entry point owns the supervised invocation:

```text
python -B tools/efficiency/keyword_modules.py
```

Historical two-worker acceptance: Nineteen focused runner/containment guards pass in7.314seconds with one Linux-native skip. Native Windows timeout-grandchild and abrupt-supervisor-death cleanup passed using retained process handles. Twenty Foundation orchestration guards pass in0.134seconds. Independent source review found no blocker. Parent combined Foundation at1ac1758 subsequently passes109checks in653.412605seconds. All437cases/34modules complete in218.221639seconds under the unchanged300-second aggregate bound, with exact independently reconciled identities and two capability skips. The prior serial attempt timed out after429case markers. Full Foundation time increased versus that incomplete run; no whole-workflow or causal billing/token/API gain is claimed. [Complete measurement and limits](../../docs/audit/PARALLEL_KEYWORD_FOUNDATION_CHECKS_2026-11-12.json). No timeout is increased or test omitted; native/live gates remain separate.

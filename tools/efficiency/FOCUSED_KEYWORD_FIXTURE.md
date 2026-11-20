# Opt-in focused keyword fixture

`focused_keyword_fixture.py` runs exactly the reviewed pest/commercial19 and pool/sprinkler20 test cases. It freshly reconstructs the common history once, checks both original base digests, and gives each worker only a detached `FRESH_BASE`. The original `FRESH_INPUTS` remains unset: current-stage review/extension logic and every original negative test still run. Every case receives a detached copy of its base, inputs and material together.

Use the configured Python3.12 interpreter:

```text
python3 -B tools/efficiency/focused_keyword_fixture.py --inspect
python3 -B tools/efficiency/focused_keyword_fixture.py
python3 -B tools/efficiency/focused_keyword_fixture.py --root /path/to/reviewed/source --output-base /path/to/private/test-output
```

The default Source root is the repository containing the tool. Only profile `pest-pool-v1` is supported; unsupported profiles or changed pins hold before expensive work. The reviewed test date is13November2026, matching those unchanged test classes. This tool supplies no current business approval, deployment authority or live-source verification.

The checked-in profile pins the complete479-file public code/input closure exercised by both modules. Reads of unbound existing inputs and writes outside a unique run directory are denied. Loaded modules must come from the selected Source root. Per-run binding rechecks Source/input bytes, the tool/codec/support code, runtime dependency bytes, fixed date and producer function semantics. Fixtures never cross run IDs or substitute for test results. Missing or altered data fails closed; there is no verdict cache or automatic fallback to an unreviewed profile.

The codec, bound keyword modules and explicit support modules compile their pinned `.py` source directly. Existing bytecode caches are neither read, allowed nor deleted; `-B` alone would only prevent writes. A preloaded bound module with an unverified loader holds.

`fresh_history_codec.py` is a closed, bounded JSON graph codec. It preserves integer versus numeric-string keys, tuples and shared container aliases; each case still receives detached data. It rejects arbitrary Python types, cycles, bad references, unreachable nodes, duplicate keys and byte/node/depth overflows. It never evaluates data or uses pickle.

Each phase has a240-second bound and uses the existing owned-process supervisor/startup gate. Fresh fixture creation, decode, deepcopies, tests and guards are included in child phase costs. Failed/timeout partial output and diagnostics are persisted before a hold. The original Foundation selection, four-worker scheduler,300-second keyword deadline, test discovery and acceptance rules are unchanged. This separate CLI is intentionally sequential; it is not imported by the default pipeline.

The completed prototype comparison is in `focused-keyword-measurement-2026-11-16.json`: both arms passed all39 cases with zero skips. Baseline complete-child time was457.568885s; optimized time including fresh typed fixture creation was309.975662s, an observed147.593223s/32.255957% reduction. This was one ordered local Windows/Python3.12 pair with uncontrolled warmth/load/resources. It does not establish a four-worker ARM CI, token, billing, whole-task or production saving. The first162.041904-second plain-JSON preparation failed an integrity check and is retained separately as diagnostic work.

The corrected portable entry passed all39 original cases with six genuine poisoned bytecode caches present:322.516159s outer time, including fresh fixture creation and all guards. All479 input pins and cache bytes remained unchanged. Source-only loaders compile the bound source directly; they never allow, read or delete cached bytecode. The actual repository inspection and complete151-test efficiency group passed locally (three platform capability skips), including unchanged PHP-isolation and timeout fixtures. This corrected CLI run is a verification result, not a new paired performance comparison. Full Foundation and mandatory CI remain required; do not skip them because this focused subset passes.

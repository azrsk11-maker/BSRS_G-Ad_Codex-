# Efficiency audit — 7 November 2026

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

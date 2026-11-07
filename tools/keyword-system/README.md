# Offline keyword research controls

This is implemented development, not a completed14,000/14,000library or an Ads uploader. It uses Python's standard library and never makes a network request. Reviewed `data/` remains empty. The separate [historical intake](staging/historical-intake.json) preserves 82 original draft placements as 41 unapproved phrase candidates, with exact source provenance and no inferred metrics or new campaign mapping. See [the intake report](../../docs/audit/KEYWORD_SEED_INTAKE.md). Synthetic fixtures exist only in test modules.

## Run

Use a verified Python3 runtime. Verify the interpreter before running; use Python3.10+ available in your environment. In this directory:

```powershell
python -B -m unittest -v test_keyword_audit.py
python -B keyword_audit.py --kind positive --input data/positive.json --sources data/sources.json --campaigns '../../docs/google-ads/planned_campaign_page_registry.json' --campaign-context data/campaign_context.json --protected data/protected_queries.json --as-of 2026-11-07 --output results/positive.json
```

Repeat the second command with `--kind negative`, `data/negative.json`, and `results/negative.json`. Update `--as-of` for a fresh audit; do not reuse old freshness results for a new release. A structural success with zero input rows correctly reports14,000missing phrases. Completion is `exact_target_pass`, not the process exit code.

## Interchange and review model

`research.schema.json` defines a combined interchange envelope. CLI inputs are separate arrays: records (`.json` or `.csv`), sources, campaign context and protected queries. JSON and CSV duplicate keys/headers fail. Nested CSV scope/list fields contain JSON; empty measured-volume/CPC cells are null. Input is preserved; output contains validation diagnostics, not a rewritten master or platform-upload file. CLI refuses to overwrite any input. Keep approved evidence/private customer information out of public repository records; reference appropriately controlled evidence without copying its contents.

Every phrase retains original text and a computed NFKC/casefold/collapsed-whitespace key. A matching bracket/quote wrapper is excluded from uniqueness; language labels, match types and repeated placements do not create new phrases. Duplicate groups all fail pending reconciliation, so a preferred row is never selected silently. Placeholder, invisible/control-character and malformed-wrapper texts hold. Semantic/grammar/entity review remains human/evidence-dependent; the program does not invent a claim that lexical validation proves relevance.

Reviewed research rows require dated unexpired source evidence and review references. Observed versus hypothesis evidence remains distinct. Hypotheses carry explicit warnings; they are not measured demand. Missing volume/CPC stays null. Numeric metrics require their own provider/reference/date window; those references still need independent factual verification. Draft/rejected/held rows remain visible but do not count as reviewed. The research and approval stages are separate: a reviewed negative may count toward the research master while still **unapproved and undeployable**.

Positive ownership resolves a known campaign to its exact designated landing-page identity and requires an ad-group design key. Real platform IDs are never generated. Additional placements belong in a separate future placement register; repeating them in the master creates a duplicate failure. Broad research is allowed but explicitly held from deployment pending an approved experiment.

Negatives retain the Master§6metadata, narrow explicitscope, eligible/ineligiblecampaigns, reason, services, risk, approval and deployment state. Shared-list and account scopes cannot hide unknown/excluded campaigns. Every eligible campaign needs dated service evidence and protected-query coverage; missing coverage fails closed. Protected terms requireHIGHreview. Actual exclusion approval has a separate reference/date and an approver distinct from the research reviewer. This is provenance checking, not cryptographic validation that a named person really approved a change.

Approval readiness also requires `--scope-bindings` with dated evidence for the Real Estate customer573-038-4686, each real campaign mapping, actual ad-group ownership where used, and the complete shared-list associations. An unknown/wrong account, invented group key or unverified list cannot be reported as an approved applicable exclusion. The research row can still count if independently researched and valid; approval/readiness counts remain separate. No live scope-binding file is supplied or fabricated. The schema defines its structure; the isolated tests use clearly marked synthetic platform IDs only in memory.

Protected-query matching uses token postings to avoid a blind all-pairs scan. Exact matches compare token sequences; phrase matches require contiguous ordered tokens; broad checks token inclusion. Scope filters are applied before conflicts. The simulator is deliberately conservative and does **not** reproduce Google's platform/close-variant behavior or prove the supplied corpus is exhaustive. Punctuation/compound differences can produce safe overholds. Conflicts hold regardless of declared approval; a declared empty conflict list cannot conceal a computed collision. AD_GROUPtests currently use whole-campaign protection, which can conservatively hold a narrower proposal until an explicitly reviewed ad-group corpus exists.

Per-campaign service coverage is precomputed once, and reports count actual lexical comparisons. `positive_library_coverage_verified:false` remains explicit: this prototype has not reconciled every reviewed positive phrase and its legitimate long-tail queries against the protected corpus. That missing completeness certificate blocks release; a passing selected corpus is not a claim of no lost demand.

Official Google guidance was rechecked on7November2026; see [research evidence](../../docs/audit/research-evidence.md). Google documents automatic negative-keyword casing/misspelling handling but separate synonym/plural considerations. This simulator does not emulate misspellings or special symbol/operator behavior. Proposed-cap diagnostics flag account-list1,000, per-shared-list5,000,20shared-lists and direct-campaign proposals already exceeding the10,000campaign limit. They are lower-bound checks; actual existing/inherited counts and platform combination accounting remain unverified. No exclusive ad-group negative limit is invented from the broader targeting-item allowance.

## Reproduce the historical staging intake

From this directory, provide the original owner's ZIP explicitly:

```powershell
python -B historical_intake.py --archive '<path-to-original-zip>' --intake-date 2026-11-07 --output staging/historical-intake.json --report staging/intake-validation.json
python -B -m unittest -q test_historical_intake.py test_keyword_audit.py
```

The archive and selected members must match the reviewed checksums. Changed sources require a separate review; do not bypass the pins to make a replacement import succeed. The intake date records when provenance was captured and is not a source-freshness or review date. This command never edits the reviewed master.

## Deployment boundary

All reports and release diagnostics have `deployment_export_allowed:false`. There is no Ads API, write, push or upload-format exporter. The release diagnostic separately checks both exact14,000targets, reviewed structure, negative exclusion approvals and separate settings/budget/publication/tracking owner references; it still directs execution to a separately reviewed release manifest. Passing research checks or inserting an approval-shapedJSONrecord never grants production authority. Deployment availability is a future explicitly authorized integration, not a hidden switch.

## Acceptance and remaining dependencies

Focused adversarial tests cover duplicate/wrapper/Unicode counts, stale/future evidence, metric fabrication, page ownership, candidate/rejected exclusions, narrow/account scopes, missing service/protected coverage, hidden conflicts, exact/phrase/broad behavior, self-approval, false deployment claims, CSV/JSON parsing and release locks. These tests do not verify actual keywords or real sources. The genuine masters, real inventory/entities, approved source evidence, campaign-service crosswalk, protected-query corpus, external semantic review and current platform limits remain to be supplied/researched. The supplied planning registry is usable for immutable design IDs but itsnullbusiness fields cannot satisfy those evidence gates.

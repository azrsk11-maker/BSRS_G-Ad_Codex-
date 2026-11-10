# Git-client access diagnostic

## Source delivery when the Git client is Read-only

A denied Git transport does not justify repeated sign-in flows, speculative permission changes or another repository. Use a separately verified, already-authorized owner browser session if ordinary feature-branch upload is available. Preserve protected main, the existing PR and the local commit history. A browser upload does not repair or establish the Git client's role.

Prepare an immutable public-source snapshot from a full reviewed commit, with exact destination paths and raw Git blob/SHA256 checks. Exclude private evidence, credentials, surrounding workspace, `.git` and uncommitted files. Choose regular files within their intended directory. Bind each upload to its explicit snapshot path; do not redefine an old REPL wrapper that may retain a stale helper or hardcoded snapshot. Verify staged names/counts, submit once, then reconcile the resulting commit before another write. On an ambiguous result, inspect before retrying. After two similar failures investigate the actual cause rather than starting another authentication flow.

Read-only Git fetch can verify the entire resulting tree against the reviewed local tree even when web commits have different history. Verify ancestry and unchanged main, then inspect required CI at that exact final head. A file count or an uploader success message alone cannot detect stale content. Record tested head/tree and remaining role/review/release gates in the PR. No force update, self-approval, main merge or production authorization is implied.

For a pretested multi-directory source batch, intermediate commits may use `[skip ci]`; the final complete-source commit must omit it and run every required check. GitHub leaves skipped required checks pending, so intermediate heads must never be treated as accepted or mergeable. This avoids testing incomplete upload states without changing workflows, protection or final acceptance. Verify final whole-tree parity and all three current-head jobs, and measure intermediate/final run counts where available. See [GitHub's documented skip behavior](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/skip-workflow-runs).

## Read-only role diagnostic

Run from this repository:

```sh
python -B tools/github-governance/read_access.py --account BlackSwanBss3701
```

This checks the expected Git-client identity and this exact repository using the already authenticated Git Credential Manager account. It performs two HTTPS GET requests. `--invitations` adds one GET and reports only matching counts; a full first page does not establish an exhaustive absence result. It never accepts invitations, pushes, changes configuration, starts interactive sign-in, grants access, reads browser profiles or changes repository protection. Exit0 means Write was observed, exit1 means authenticated Read-only access, and exit2 means verification could not complete. Write access is not production authorization.

Credentials stay in the helper's subprocess/API memory path and are never printed, written to project files or included in errors. Git Credential Manager retains its own existing secure-storage/refresh policy. Interactive Git/GCM, tracing and askpass fallbacks are disabled. API authentication is restricted to `api.github.com`, redirects are refused, and the HTTPS Git origin must match `azrsk11-maker/BSRS_G-Ad_Codex-`. Profiles are reduced to the expected username; mail addresses, unrelated invitations and API bodies are omitted. The Codex connector can use a different GitHub identity, so its permissions do not establish Git-client access.

Focused verification: `python -B -m unittest discover -s tools/github-governance -p 'test_*.py'`. Tests mock credentials and network and never change live permissions. The diagnostic reports elapsed wall time and its own HTTP request count; these are not token-usage or whole-project efficiency measurements.

# Git-client access diagnostic

Run from this repository:

```sh
python -B tools/github-governance/read_access.py --account BlackSwanBss3701
```

This checks the expected Git-client identity and this exact repository using the already authenticated Git Credential Manager account. It performs two HTTPS GET requests. `--invitations` adds one GET and reports only matching counts; a full first page does not establish an exhaustive absence result. It never accepts invitations, pushes, changes configuration, starts interactive sign-in, grants access, reads browser profiles or changes repository protection. Exit0 means Write was observed, exit1 means authenticated Read-only access, and exit2 means verification could not complete. Write access is not production authorization.

Credentials stay in the helper's subprocess/API memory path and are never printed, written to project files or included in errors. Git Credential Manager retains its own existing secure-storage/refresh policy. Interactive Git/GCM, tracing and askpass fallbacks are disabled. API authentication is restricted to `api.github.com`, redirects are refused, and the HTTPS Git origin must match `azrsk11-maker/BSRS_G-Ad_Codex-`. Profiles are reduced to the expected username; mail addresses, unrelated invitations and API bodies are omitted. The Codex connector can use a different GitHub identity, so its permissions do not establish Git-client access.

Focused verification: `python -B -m unittest discover -s tools/github-governance -p 'test_*.py'`. Tests mock credentials and network and never change live permissions. The diagnostic reports elapsed wall time and its own HTTP request count; these are not token-usage or whole-project efficiency measurements.

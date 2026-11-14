# GitHub write-access remediation

Current authoritative readback for `azrsk11-maker/BSRS_G-Ad_Codex-` is:

```text
pull=true, push=false, maintain=false, admin=false
```

This is the cause of the 403 for `BlackSwanBss3701`.

## Owner-side fix

1. Sign in to GitHub as repository owner `azrsk11-maker`.
2. Open the repository’s **Settings → Collaborators** page.
3. Locate the exact collaborator `BlackSwanBss3701`.
4. Change its repository role to **Write** (do not change branch protection or grant Admin/Maintain).
5. Complete GitHub’s identity confirmation if requested.
6. Verify the collaborator entry shows Write access.

## Verification condition

After the change, the connected repository metadata must read `push=true` for the intended Git identity. Only then should the owner-authorized local commit range be uploaded to `codex/phase0-audit-foundation` and reconciled against PR #8. A successful role change does not authorize merging, production publication, live tracking changes, Ads activation or expenditure.

No credentials, codes, private workbook IDs or prospect data belong in this file.

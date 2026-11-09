# GitHub governance and separate production authorization

The owner-designated repository is the shared record for committed work, requirements, test evidence, progress and scoped decisions. Private conversation history is not required to supervise this project. Public GitHub must not contain prospect data, secrets or private financial records.

## Repository controls

7 November 2026: the repository was empty and public. A README-only bootstrap commit `f239701e47873f6dea7e6336d59cbe0dd6c15053` established main so feature PRs can exist. All substantive work belongs to `codex/phase0-audit-foundation` and subsequent feature PRs.

Main protection was created through the authenticated owner session: require a PR, one approval, code-owner review, dismiss stale approvals, require approval of the most recent push by another person, resolve conversations, apply protections to administrators, disallow force pushes/deletion, require up-to-date checks. After the first successful workflow run, both named checks were saved as mandatory: `offline-validation` and `native-wordpress-check`. Initial CODEOWNERS content is on the feature branch; its owner mapping becomes a base-branch rule after review and merge. The first PR still requires an independent approving reviewer and latest-push approval.

The connected GitHub API identity is a different account and is read-only on this repository. Browser owner access was verified. Work uploaded through the owner's session is authored by that account; the owner cannot approve their own PR. Nominate a separate authorized human reviewer or connect an independently authorized execution identity before merging. Never remove review controls to bypass this separation.

## Owner decisions

Every unresolved owner judgment is a GitHub issue labeled `owner-decision-required`, containing background, options, commercial/technical consequences, recommendation and exact requested approval. Keep a status/link in `decisions/OWNER_DECISIONS.md`. An owner response is recorded with account, date, issue/comment URL, exact authorized scope and exclusions. Do not treat a suggested option as approved. Continue unrelated tasks while decisions wait.

## Deployment separation

No production publisher, Ads mutator, deployment credentials or live tracking uploader is included in this foundation. CI tests local/synthetic artifacts only. A merge cannot deploy anything.

Validation runs on PR updates targeting main; open a draft PR when beginning a branch. It does not also run identical jobs on each push event. Both required check names and administrator-enforced review remain unchanged.

Three separate environments were created and verified on 7 November: `production-website`, `production-tracking`, and `production-google-ads`. Each requires the repository owner as reviewer, prevents self-review, disables administrator bypass and allows protected branches only. No deployment secrets or jobs were added. These controls apply to future workflows that explicitly reference the appropriate environment; they do not control manual changes in provider UIs.

Future deployment jobs additionally require separately authorized scoped secrets and a release manifest pinned to a reviewed commit. Keep website publication, tracking publication and Ads activation separate approval records. Creating an environment does not itself authorize a deployment.

A valid release record identifies the approved action, target website/account, exact commit and artifact hashes, affected page/campaign IDs, budget/serving window where applicable, acceptance evidence, expiry/window, responsible operator and recovery trigger. Financial approval must separately state monthly/cash-risk authority; a daily average is not a hard daily ceiling.

No user credentials should be entered in issues. Sign-in happens in the real service UI. Provider access, GitHub collaborators, OAuth scopes, workbook sharing and any expanded security-sensitive access need their own specific authorization.

The [local release-packet checker](../tools/release-control/README.md) checks exact source/evidence hashes, scope, review/decision references, expiry, budget totals and rollback bindings. It always denies execution and cannot authenticate approvals. WT-031/032 publication/readback evidence is a post-publication obligation for website/tracking changes and must already exist before Ads activation. Passing this checker never substitutes for authenticated owner authorization or protected environment review.

## Recovery

Keep scoped before/after manifests. Do not restore a whole database over new accepted leads. Revert code/tag versions only; preserve accepted receipts, original decisions and outbox reconciliation. Roll page changes back using recorded IDs/revisions and campaign-specific metadata. Do not delete existing pages or reactivate old campaigns. Reapply retention deletions before reopening a restored system. New recovery copies use the approved 30-day encrypted owner-only window.

GitHub reference: [protected deployment environments](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments). Actual configured controls must be verified in GitHub; documentation is not enforcement evidence.

## 9 November branch-rule readback

GitHub's public branch response marked `main` protected and listed two required checks: `offline-validation` and `native-wordpress-check`. The `isolated-native-wordpress` check passed on PR #8 and is required by the local release packet. It is absent from the live branch's required-check list. Check it explicitly before merging this PR. To enforce all three at merge time, add `isolated-native-wordpress` in the authenticated protection settings and verify the readback while retaining the two existing checks and independent approval rules. [Reviewer and access issue #6](https://github.com/azrsk11-maker/BSRS_G-Ad_Codex-/issues/6)

The public branch response could not verify the detailed review or administrator settings. The full protection endpoint required authentication. This audit changed no settings.

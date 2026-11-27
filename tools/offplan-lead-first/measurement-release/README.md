# Review-only measurement patch builder

This portable offline tool derives a two-member patch and exact rollback files. It does not install, upload, create a plugin ZIP, enable measurement or contact a provider. Every report retains `ready_to_install:false` and `deployment_prohibited:true`.

The proposal reuses the existing exact-hash frame queue builder, and changes only the primary plugin header and `PLUGIN_VERSION` from `0.2.12` to `0.2.13`. The version change updates the existing renderer's asset query version. All other bytes, including the original mixed line endings, contact paths, consent, routing, wire protocol and intake, are preserved.

The complete raw input tree must contain exactly thirty regular plugin members. The output contains seven files: two forward replacements, two original rollback members, a complete before/after inventory manifest, operations metadata and a review notice. This directory is not a complete plugin and must not replace one.

## Required inputs

- A Source checkout with the existing pinned frame builder and coupled-package read/validation helpers.
- The complete retained raw snapshot and its separately reviewed member-hash receipt.
- The nine-member editor audit and the distinct three-member extra editor audit. Exact cohort paths, uniqueness and a twelve-member union are required.
- A private bindings JSON, independently reviewed alongside the input evidence. Supplying matching hashes does not create acceptance or release authority.
- An explicit private output root, disjoint from Source and the raw snapshot.

The bindings file has exactly these fields. Replace placeholders with independently reviewed digests; do not commit actual private inputs, bindings or outputs.

```json
{
  "schema": "bsre-private-measurement-input-bindings-v1",
  "classification": "ACTUAL_PRIVATE_READBACK",
  "fresh_editor_audit_sha256": "<64 lowercase hex characters>",
  "extra_editor_audit_sha256": "<64 lowercase hex characters>",
  "historical_raw_receipt_sha256": "<64 lowercase hex characters>"
}
```

The fresh entrypoint editor representation is classified separately from exact raw bytes. Its known CRLF-to-LF diagnostic equivalence is never used to normalize patch inputs or relax raw preimage checks. Current raw identity, served cache/opcache, GTM publication, native browser/privacy, genuine delivery/provider deduplication and human/release gates remain external.

## Commands

Set the path variables to the intended local inputs. The builder requires every path explicitly; it has no private workspace defaults.

```powershell
node $builder build `
  --source-root $source `
  --raw-snapshot $rawSnapshot `
  --historical-receipt $historicalReceipt `
  --editor-audit $editorAudit `
  --extra-editor-audit $extraEditorAudit `
  --bindings $privateBindings `
  --output-root $privateOutputRoot `
  --output $newBundleDirectory
```

Existing output directories are rejected. Building again from unchanged inputs yields byte-identical bundle files; use a new output directory only for an intentional comparison.

The verifier reconstructs the expected bundle and checks all thirty local installed preimages. It performs no writes to the supplied mirror and does not establish that it is a current server snapshot.

```powershell
node $builder verify `
  --source-root $source `
  --raw-snapshot $rawSnapshot `
  --historical-receipt $historicalReceipt `
  --editor-audit $editorAudit `
  --extra-editor-audit $extraEditorAudit `
  --bindings $privateBindings `
  --bundle $bundleDirectory `
  --installed-root $exactLocalInstalledMirror `
  --direction forward
```

Use `--direction rollback` to require the exact proposed postimages before reviewing restoration of both originals. The tool exposes no filesystem apply/install operation; the complete forward/rollback transformation is verified in memory by the tests. A partially applied pair fails both directions.

## Focused checks

The test file reads the existing immutable Source fixture in place and creates only small synthetic metadata and a seven-file temporary patch bundle. It does not copy the full plugin fixture or need private readbacks.

```powershell
$env:BSRE_SOURCE_ROOT = $source
$env:BSRE_MEASUREMENT_TEST_OUTPUT = $privateTestOutputRoot
node --test $testFile
```

Tests cover deterministic construction, the exact two-byte version delta, mixed-newline preservation, full preimage and inverse checks, partial-pair refusal, evidence drift and duplicate-cohort rejection, bundle/rollback/manifest tampering, explicit output boundaries, unchanged input fixtures and bounded CLI failure. Existing five frame and four composed behavior results are reused separately; this test file does not rerun them.

## Chrome frame transport

The optional local check runs the exact composed parent asset in a new headless Chrome profile on loopback HTTPS. It uses a disposable certificate pinned only in that invocation, a local header observer, and a synthetic runtime frame. The fixture uses no production credentials, form submissions, click identifiers or vendor SDKs. It verifies origin-only referrer and same-origin iframe headers, refusal, route isolation, the India marker, and the missing-referrer negative control. [Chrome Headless documentation](https://developer.chrome.com/docs/automation-and-testing/headless).

```powershell
python -B check_chrome_transport.py --chrome $chromePath --candidate $privateComposedReview --out $newPrivateReceipt
```

Use the local Python environment with `cryptography` and an existing Windows Chrome executable. Choose a new private receipt path. The test fixture verifies the asset hash in the review manifest. Actual Hostinger headers, the deployed runtime and Google processing need live evidence.

## Private archive and rollback review

`pack_plugin_review.py` pairs the full 49-file `0.2.15` candidate with the 30-file retained `0.2.12` rollback. It verifies the SHA-256 of every member against the review and retained file receipt. Both archives use the existing `bsre-enquiries/` root. Reconciliation reads every archived member after packaging. `--check` compares the existing output against the current reviewed inputs without writing it.

```powershell
python -B pack_plugin_review.py --review $privateComposedReview --preimage-receipt $retainedFileReceipt --out $privateArchiveDirectory
python -B pack_plugin_review.py --review $privateComposedReview --preimage-receipt $retainedFileReceipt --out $privateArchiveDirectory --check
```

The retained receipt supplies archive provenance. A fresh deployed file comparison and the native release gates still govern any use of the review pair.

All snapshots, real audits, private bindings and paths, generated bundles, receipts and independent review artifacts remain private. Required Source checks, native acceptance, human review and concrete publication authorization are not supplied by these tools.

## Reproduce the country transport review archive

`COUNTRY_TRANSPORT_REVIEW.json` contains the checked byte edits and expected 51-member inventory. It omits the retained base package. From Source, run the composer on the exact previously reviewed private 0.2.15 forward ZIP and use a new output path outside Source.

```text
python -B tools/offplan-lead-first/measurement-release/compose_country_review.py /private/base.zip /private/country-transport-PRIVATE-REVIEW.zip
```

The composer checks the base archive and changed preimage hashes, then matches every output member to the native test receipt. The reproduced ZIP matched a separately assembled private archive. The transport flag defaults off. Preserve both rollback packages and obtain a distinct release version, current Hostinger file identity, independent review and deployment approval before use.

## German advertising consent prototype

`GERMAN_ADVERTISING_REVIEW.json` applies a second exact review to the 51-member transport archive. The result has 53 members, with 12 changed or added files. It retains default-off route flags and has no installed page binding or credential material. Use the explicit profile and a private output path.

```text
python -B tools/offplan-lead-first/measurement-release/compose_country_review.py /private/country-transport-PRIVATE-REVIEW.zip /private/german-advertising-PRIVATE-REVIEW.zip --profile german-advertising
```

The exact prototype was checked with two tabs using the same synthetic WordPress session. With the baseline, the second tab's frame stayed active through the first tab's withdrawal acknowledgement. With the new consent asset, the frame was gone at the 610 ms observation while the first-party POST still waited. The message only invalidates the sibling context and carries no choice or identifier. The sibling must reload the page or confirm its own choice before enabling measurement again. In the fixture, neither build attempted a lead POST or delivered a vendor request.

Further review must resolve overlapping grant and withdrawal writes and delayed pending-state reads. The stored 180-day expiry is tied to a two-hour browser session and the prototype cannot restore the choice after session expiry. A browser without the peer signal falls back to the pending cookie and server lease checks. The test covers Chrome with the signal available. German notice approval, deployed cache and Hostinger checks, provider acceptance and other locales are separate release gates.

## Ordered German consent and session renewal

The `german-ordered-consent` profile is a four-file delta against the preceding 53-member private prototype. The route compares a signed, scoped expected revision under the existing InnoDB row lock before granting measurement. Withdrawals may proceed with a stale revision. Pending reads suspend measurement without writing preference state. Each tab clears only its own pending marker after acknowledgement. An acknowledged choice sets an opaque, signed, HttpOnly preference cookie that restores the choice when the temporary transport session renews. Both features use the existing schema and remain off by default.

```text
python -B tools/offplan-lead-first/measurement-release/compose_country_review.py /private/german-advertising-PRIVATE-REVIEW.zip /private/german-ordered-PRIVATE-REVIEW.zip --profile german-ordered-consent
```

Real local Chrome and WordPress confirmed the stale grant's HTTP 409, overlapping marker acknowledgements, and renewed session restoration of a grant and a refusal. A separate two-connection MariaDB fixture observed the exact waiting lock pair and verified preserved withdrawal history after a fresh grant. Focused browser-script checks cover the storage-event fallback and restored-page denial. The fixtures used synthetic records and did not submit an enquiry or transmit to Google. The inherited live and independent review gates still apply to this candidate.

## Original consent receipt on a German capture

The `german-capture-lineage` profile preserves the original consent receipt on a new German capture. The store checks the current grant and original history under lock before recording optional evidence. The route still uses the immutable request ID and exact body hash for retry reconciliation. Its notice and route identify eligible German captures. Older staged retries can recover the accepted receipt through that alias. A previously stored opaque retry marker cannot grant measurement or attest original consent history.

```text
python -B tools/offplan-lead-first/measurement-release/compose_country_review.py /private/german-ordered-PRIVATE-REVIEW.zip /private/german-lineage-PRIVATE-REVIEW.zip --profile german-capture-lineage
```

The isolated InnoDB check passed actual staging, receipt linkage, old-choice and missing-history denial, same-body replay and cross-route rejection. The existing retention planner protected the submitted capture and its withdrawal history while identifying two overdue rows for a separate unsubmitted choice. The fixture used synthetic rows and a preview only. It supplies current storage compatibility for the candidate, with production retention and provider acceptance still subject to their release gates.

## Isolated German measurement frame

The `german-isolated-frame` profile uses an opaque-origin frame on the German page. The parent grants a dedicated message port only to the expected frame. The frame uses the port to request its lease from the fixed first-party status endpoint. The parent keeps the rotating lease token and aborts outstanding renewals on withdrawal. The child policy denies first-party connections and removes the bootstrap configuration before loading measurement scripts. The frame keeps the existing purpose and receipt validation. [HTML sandbox semantics](https://html.spec.whatwg.org/multipage/iframe-embed-object.html) · [Content Security Policy](https://www.w3.org/TR/CSP3/).

```text
python -B tools/offplan-lead-first/measurement-release/compose_country_review.py /private/german-lineage-PRIVATE-REVIEW.zip /private/german-isolated-PRIVATE-REVIEW.zip --profile german-isolated-frame
```

The review profile affects German advertising only. The live Google script behavior and conversion acceptance inside an opaque frame need separate evidence. Current Hostinger file identity, disclosure, independent review and deployment approval remain release gates.

## Owned off-plan frames and cache version rehearsal

The `owned-opaque-frame` profile applies a separate four-member change to the German isolated-frame base. The canonical off-plan page uses an opaque frame and a dedicated message port for each allowed purpose. The parent validates the measurement fields before dispatch. A verified click identifier enters only the Ads frame URL under advertising consent. The Analytics frame URL, page location, and outgoing command payloads exclude it. The bound India path retains the existing canonical reporting identity. Unbound and unrelated paths hold measurement.

The `isolated-cache-version` profile changes the two version digits on the German isolated-frame base. The native WordPress rehearsal changed all six rendered asset keys from `0.2.15` to `0.2.16` and restored them on downgrade. The 52 other members and held application state matched exactly. The cache version and broader frame profiles are separately tested artifacts.

```text
python -B tools/offplan-lead-first/measurement-release/compose_country_review.py /private/german-isolated-PRIVATE-REVIEW.zip /private/owned-frames-PRIVATE-REVIEW.zip --profile owned-opaque-frame
python -B tools/offplan-lead-first/measurement-release/compose_country_review.py /private/german-isolated-PRIVATE-REVIEW.zip /private/cache-version-PRIVATE-REVIEW.zip --profile isolated-cache-version
```

Chrome and local WordPress tested the exact owned-frame candidate. Both purposes obtained first-party leases through the parent, and both inert scripts were blocked from the parent form and browser cookies. Chrome recorded one Analytics page view, one Analytics lead event and one Ads conversion command for a single fresh signed synthetic receipt. A repeated submit produced no new lead or measurement command. Withdrawal removed both frames. Live Google behavior, Hostinger cache and installed-file evidence, and approval remain release gates.

## Combined off-plan review and rollback

The `owned-combined-0216` profile applies the two previously rehearsed version bytes to the exact 53-member owned-frame archive. The other 52 members retain their verified hashes. The resulting SHA-256 is `8d248292812b04bc5faf69cbd0f0a2db69e02e1cf71bab5e98e279031894b466`.

```text
python -B tools/offplan-lead-first/measurement-release/compose_country_review.py /private/owned-frames-PRIVATE-REVIEW.zip /private/combined-0216-PRIVATE-REVIEW.zip --profile owned-combined-0216
```

Local WordPress verified all installed members across the upgrade from the retained `0.2.12` archive and the exact rollback. Six canonical asset keys rotated and reverted, and scoped synthetic intake data and page settings retained their digests. Wrong-package and installed-byte drift controls stopped before installation. Actual Hostinger file identity, published consent, provider behavior, and independent review remain release gates.

Two initial exact-package Chrome runs requested all seven expected `0.2.16` asset keys. At least one local lease response crossed the five-second browser deadline in each run. The affected frame retired and the runs stopped before submitting a synthetic enquiry. A single warm worker returned both leases in 2.007 and 4.203 seconds. Its four-second headroom check held that browser run.

Using separate purpose-specific native fixture workers resolved the local contention. The exact combined archive passed all 11 checks and four browser observations in the cleanup-verified run. Actual browser leases took 2.402 and 2.423 seconds under the unchanged five-second timeout. Chrome verified one signed synthetic receipt, no duplicate, an inert measurement command for each eligible purpose, and retirement of both frames on withdrawal. No request reached a vendor.

## GTM bootstrap CSP nonce review

The authenticated owned-funnel container still publishes an empty version. Its sole pending Custom HTML tag checks for the guarded local activation method and invokes it from an inline script. The `0.2.16` frame policy allows the external container but prevents its inline bootstrap from running. The existing external-stub fixture invokes the method directly and therefore covers a different activation path.

The `gtm-nonce-0217` profile generates a fresh cryptographic nonce per authorized runtime response and carries it into the first-party script element and its dynamic GTM loader. The parent page policy and response scope are unchanged. The opaque frame retains its existing restrictions, inline attributes stay denied, and the policy does not introduce `unsafe-inline` or `unsafe-eval`. [Google CSP integration guidance](https://developers.google.com/tag-platform/security/guides/csp).

```text
python -B tools/offplan-lead-first/measurement-release/compose_country_review.py /private/combined-0216-PRIVATE-REVIEW.zip /private/gtm-nonce-0217-PRIVATE-REVIEW.zip --profile gtm-nonce-0217
```

The review reproduces 53 members at SHA-256 `4e62a282828eef4748394b33f211277a59e901135c7c4800e42f7ec02a7edfd3`, with changes to the runtime PHP and JavaScript plus the cache version. In the focused Chrome fixture, the exact `0.2.16` render blocked three inline calls. The exact `0.2.17` render accepted all four calls with a matching nonce and blocked calls with wrong or absent nonces. Six authorized responses had unique nonces and no frame could access the parent DOM or cookies. The 25 baseline and 46 successor checks used synthetic authorization and inert GTM and gtag resources. Live GTM publication and execution, actual Ads acceptance, and Hostinger release checks remain open.

The separate native WordPress and Chrome trial exercised both canonical purposes with a local provider stub that injected the browser-visible guarded inline bootstrap. All 11 inherited fixture checks, four browser observations and three native CSP checks passed. The runtime, loader and inline element matched each response nonce. Both purpose leases completed inside the unchanged browser deadline. One signed receipt emitted one inert command per allowed purpose, the duplicate emitted none, and withdrawal removed both frames. The fixture used synthetic records and blocked external traffic.

## Captured GTM draft and recovery version

On 27 November the full container exports confirmed version 1 contains zero tags and triggers, and the selected Default Workspace contains one reviewed bootstrap tag and its single Page View trigger. Each export retained the same five default built-in variables. Workspace exports use container version ID `0`, so the acquisition record preserves the actual workspace identity from the export selector. Keep the provider exports and acquisition record private. [Google GTM export procedure](https://support.google.com/tagmanager/answer/6106997?hl=en).

```text
python -B tools/offplan-lead-first/measurement-release/check_gtm_exports.py /private/live-version-1.json /private/default-workspace.json --candidate-zip /private/gtm-nonce-0217.zip --checkpoint /private/export-acquisition.json --checkpoint-sha256 TRUSTED_CAPTURE_SHA256
```

The offline verifier checks the three input hashes, one owned container, both inventories and the exact guarded bootstrap bytes. It rejects a drifted draft or rollback artifact. The test suite constructs synthetic exports. Publication decisions require current authenticated provider readback and separate approval. GTM version 1 is retained as the starting recovery reference for this container. Google GTM version history provides the provider-side restoration path. [Google GTM version and publication guidance](https://support.google.com/tagmanager/answer/6107163?hl=en-gb).

The local browser rehearsal also executed the exact exported inline body against the reviewed plugin archives. `0.2.16` blocked all three attempts. `0.2.17` passed all four valid-nonce cases and blocked the missing and wrong nonce. The baseline ran 25 checks in 2.046 seconds and the successor ran 46 in 2.663 seconds. The browser used inert Google scripts and sent nothing to a vendor.

## Installed Hostinger plugin comparison

An authenticated capture is limited to the `bsre-enquiries` plugin directory on the Real Estate site. Use the folder's **Download as ZIP** function where available. Record the selected site, exact folder, capture time, size and SHA-256 before comparison. Keep the download and provenance private. [Hostinger File Manager guidance](https://www.hostinger.com/support/4548688-basic-actions-in-the-file-manager-in-hostinger/).

```text
python -B tools/offplan-lead-first/measurement-release/check_hostinger_preimage.py /private/hostinger-bsre-enquiries.zip /private/bsre-enquiries-0.2.12-rollback.zip --export-sha256 CAPTURE_SHA256
```

The comparison accepts the exact 30-member roster in a ZIP containing the plugin folder or its direct contents. The retained rollback remains pinned. Container metadata such as ZIP compression and directory entries may differ. Each matching file must retain its original bytes. The verifier rejects unrelated, missing, altered, encrypted, oversized, duplicate or symbolic-link entries. It checks the complete roster before reading member data and never extracts files. Its result covers the two local inputs. Hostinger capture provenance, live provider state and change approval remain separate.

Ten synthetic tests and a separate repack of the exact retained rollback passed. The repack exercised all 30 members and took 0.041 seconds. Authenticated Hostinger bytes remain pending.

## Combined 0.2.17 evidence check

The `OFFPLAN_0217_PRIVATE_EVIDENCE` capture lists the relative path and SHA-256 of each private input. `check_offplan_release_evidence.py` recomposes the exact release archive and reconciles the rollback, native WordPress and Chrome, exported GTM bootstrap, direct REST and loopback HTTPS retries, Chrome retries across both replacements, saved TEST, and five-market hold receipts. The path checks confine private inputs to the named workspace. The optional `host_export` entry also runs the complete installed-plugin comparison against the pinned rollback.

The loopback run verified 17 TLS 1.3 requests and 25 checks across exact `0.2.12 → 0.2.17 → 0.2.12` native replacements. The local receiver recorded six synthetic receipts from eleven signed attempts. The exact retries preserved IDs, both changed bodies were rejected before relay, and measurement remained denied. All fixture processes exited and external transmissions were zero. Chrome execution across a hosting deployment and live receiver acceptance remain outside that run.

The separate loopback Chrome run kept the same native enquiry document open during each replacement. Seven assertions passed in six browser phases. Exactly four lead POSTs exercised both acknowledgement faults and retries. Both retries preserved the body, request ID and receipt. The verifier hashes all twelve served form assets against their two archived versions. Reloading or reopening a pending form and actual production deployment remain additional observations.

```text
python -B tools/offplan-lead-first/measurement-release/check_offplan_release_evidence.py --workspace PRIVATE_WORKSPACE --capture PRIVATE_CAPTURE.json --capture-sha256 TRUSTED_CAPTURE_SHA256
```

The receipt records existing offline verification and a separate launch `HOLD`. `--require-launch-ready` exits 3 on this offline-only scope. The tool cannot establish present provider state, authenticate the source of a Hostinger file, or imply live approval. The private capture and underlying exports stay on the authorized workspace.

## Attribution continuity and CTA diagnostics

```text
python -B tools/offplan-lead-first/measurement-release/compose_country_review.py /private/gtm-nonce-0217-PRIVATE-REVIEW.zip /private/attribution-0218-PRIVATE-REVIEW.zip --profile attribution-continuity-0218
```

The 53-member `0.2.18` review reproduces SHA-256 `be8a76ba2a9cb3dfbfcad37767a5d72c06c9ea632597a6a83c9ef9b00f849be3`. The five enquiry clients retain the latest permitted analytics touch across clean internal navigation and accept explicit inbound replacements. Existing advertising click continuity and purpose-specific browser storage remain in place. Seven scenarios ran against each actual client in a simulated page. Independently scoped Chrome checks verified the exact LF-preserving runtime member. The terminal Analytics adapter sends `phone_click` and `whatsapp_click` diagnostics with the existing consent and payload restrictions. The 14 check groups sent zero vendor requests and zero lead or Ads conversion submissions. This archive remains for review. Independent-purpose attribution through the full signed intake, actual provider acceptance, and the Hostinger release gates remain open.

## Combined 0.2.18 evidence check

The release checker accepts a complete successor group in the pinned 0.2.17 manifest format. Add `successor_archive`, `successor_browser`, `successor_attribution` and `successor_retry` together. It recomposes the exact 53-member archive, compares the actual served assets, and checks 11 native measurement gates, 14 native navigation gates and seven cross-version retry gates. Only the exact successor evidence changes the reported candidate identity. Earlier exported GTM bootstrap and direct REST and TLS observations retain their 0.2.17 identity.

The latest native Chrome rehearsal kept the form open through exact `0.2.12 → 0.2.18 → 0.2.12` replacements. Four lead requests produced two durable synthetic receipts and preserved the original IDs. Both request pairs started with a lost acknowledgement and completed with an unchanged retry. Twelve archived form assets matched. Optional measurement stayed denied and no vendor requests were sent. The verified local inputs still return `HOLD` for live release.

## English country Ads measurement review

```text
python -B tools/offplan-lead-first/measurement-release/compose_country_review.py /private/attribution-0218-PRIVATE-REVIEW.zip /private/country-ads-0219-PRIVATE-REVIEW.zip --profile english-country-ads-0219
```

The 53-member `0.2.19` r2 review reproduces SHA-256 `3abc01b3e92b09c81ae6dd3111c12b3421a536cb868935c857b8117d3522d13a`. The English Germany, France and Taiwan routes can request advertising measurement only with an exact path-to-published-page-ID binding, the route transport and master Ads switch, plus a current route-specific grant. The German route retains its existing consent namespace. India retains its separate native binding. The scoped Ads frame receives the fixed clean route and an opaque accepted receipt. The route flow leaves Analytics off and excludes click IDs and raw referrers. The tested client aliases leave canonical click history untouched. The r2 child checks the exact route's cookie prefix, matching the server and parent cleanup logic.

This review still requires the applicable consent disclosure and hosted acceptance, purpose-bound choice CSRF review, independently verified provider behavior, and a recovery test for a newly staged positive choice. A downgrade to `0.2.18` lacks the new English capture notices. The existing full-replacement proof applies to the `0.2.18` inputs. It cannot certify rollback after `0.2.19` English capture activation. The country Ads receipt remains distinct from verified paid-click attribution.

## Country consent-choice token review

```text
python -B tools/offplan-lead-first/measurement-release/compose_country_review.py /private/country-ads-0219-r2-PRIVATE-REVIEW.zip /private/country-choice-0220-PRIVATE-REVIEW.zip --profile country-choice-csrf-0220
```

The 53-member `0.2.20` review reproduces SHA-256 `b7d9dedcdd7bf8c5f716824d0629bb7dc8ff6b70326c19006b5b65459100a2c0`. The existing country context supplies `ad_choice_csrf_token` only when advertising configuration and the exact route binding are eligible. The separate choice token is bound to the session, purpose, native route, page and notice. Its minimum age is two seconds and its lifetime is two hours. The form keeps its existing intake token, UUID and body. A missing or malformed choice token keeps optional measurement off. Five changed members passed syntax checks, and 11 focused PHP checks covered scope and expiry. The exact browser scripts consumed the new field in a simulated context-to-choice flow. An independent native fixture passed 31 checks, including both wrong-purpose denials and preserved signed TEST intake with measurement excluded. Provider transmissions were zero.

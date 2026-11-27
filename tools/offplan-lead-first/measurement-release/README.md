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

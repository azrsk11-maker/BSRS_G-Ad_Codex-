# Installed-preimage locale candidate

`derive_localization.py` is executable offline tooling, not a WordPress plugin or deployment package. It reuses the existing 85-string catalog and pure form-text compiler against three exact preimages. It rejects the old contact-mismatched lead fixture and preserves the approved 8663 matcher. Every lead/consent string edit has a recorded inverse that reconstructs the complete original bytes.

The script also implements a pure locale selector for the existing `/enquire/off-plan/` request target. It accepts exactly `de-DE`, `fr-FR` or `zh-Hant-TW` through a single canonical `bsre_locale` query parameter. Invalid, duplicate, array, encoded-key, malformed, off-route and oversized inputs select existing English. The selector returns a fixed locale string; it persists nothing and does not construct URLs, endpoint configurations or remote assets. India continues to use English.

## Inputs and output

All paths are explicit CLI arguments. The source compiler/catalog and each supplied raw member must match pinned hashes. The primary editor-audit JSON must bind the contact-correct lead member, version0.2.12, all-off measurement and no editor save. The optional supplemental editor audit can bind the consent bridge and off-plan HTML; mismatches are rejected rather than normalized. Without that audit, their current-editor bindings remain false. Editor evidence never becomes raw-server, opcache, served-asset or native-execution proof.

Expected raw members:

| Member | Bytes | SHA-256 |
| --- | ---: | --- |
| `assets/lead.js` | 26591 | `c42a6a68cdab20a700f9fe06a306a32903080fa1ac58b87fc8e8f26ce3f25f16` |
| `assets/consent-bridge.js` | 18242 | `490b50be1fa1113f8a152bd0fcb8899efc9d7a1f9e5a149798a851e342f1f993` |
| `templates/source/off-plan.html` | 11168 | `78e2349a7e1b1e2acee94e65d592d72a9d1902d6881040ec89bf7c38c5d8e05f` |

For each locale, output includes an **inert disabled** form fragment, localized lead and consent clients, and template strings. `JS_TEXT_INVERSES.json`, `LOCALE_SELECTION.json`, `DEPLOYMENT_REJECTIONS.json` and a deterministic manifest complete the 16-file bundle. The output scope must be explicitly authorized, the output directory must be its descendant and outside Source, and populated output cannot be overwritten. `--check` reconciles the exact inventory/bytes and rejects symlink members.

```text
python -B derive_localization.py --source-root SOURCE --installed-root RAW_MEMBERS --editor-audit EDITOR_AUDIT.json --extra-editor-audit RELEASE_AUDIT.json --output-scope AUTHORIZED_PRIVATE_DIRECTORY --out AUTHORIZED_PRIVATE_DIRECTORY/generated
python -B derive_localization.py --source-root SOURCE --installed-root RAW_MEMBERS --editor-audit EDITOR_AUDIT.json --extra-editor-audit RELEASE_AUDIT.json --output-scope AUTHORIZED_PRIVATE_DIRECTORY --out AUTHORIZED_PRIVATE_DIRECTORY/generated --check
python -B derive_localization.py --resolve-target "/enquire/off-plan/?bsre_locale=de-DE"
```

Use the verified Python interpreter specified by the applicable workspace instructions. These commands do not authenticate to WordPress, change code, submit forms or enable measurement.

## Focused tests

Run `python -B -m unittest test_derivation -v` beside the script, with `BSRE_FORM_SOURCE_ROOT` set to Source or the working directory set appropriately. `BSRE_LOCALIZATION_TEST_SCOPE` can confine temporary test files to an explicitly authorized directory. Tests construct clearly labelled synthetic preimages from immutable fixtures using the approved contact substitutions, verify their exact pinned hashes, and never treat them as an installed readback. They need no private raw downloads, accounts, network or credentials.

The new tests cover installed-versus-old-contact bytes, source/catalog drift, audit conflicts/duplicates, inverses and tampering, form control invariants, query ambiguity/bounds, output ownership and exact-output reconciliation. Existing 21 form-compiler tests retain their original proof scope and are not rerun by this tooling.

## Deployment remains rejected

`offplan-locale.php` provides a review-only PHP selector for the existing registered off-plan page. It requires the protected renderer's validated page binding before it reads the exact request target. Its output is a fixed locale, with English as the default. The isolated PHP cases check this boundary with no WordPress bootstrap or network access. Run them with `php offplan-locale.test.php` from this directory.

Native renderer wiring, asset allowlist changes, page creation and privacy translations remain open. The form's disabled preview fieldset remains intact. The signed wire, stored option values, canonical intake path, recipient/transport, receipt/dedup ownership, eligibility/QA and consent logic stay outside the text edits. The separate consent panel still needs an explicit language binding, and current URL validators require actual fixed query-free privacy destinations.

Actual native page/locale/asset/privacy/document-language integration, served-byte and cache verification, competent copy/staff-language and human review, current native/genuine intake/consent/delivery/dedup acceptance and Taiwan applicability remain gates. The bounded candidate is not legal approval, inventory evidence, launch permission or provider acceptance. Root owns Source integration and any later live action.

## Protected country-page previews

`offplan-country-pages.php` is a review component for the six planned English and local-language paths in Germany, France and Taiwan. The private integration harness wired it into the exact 0.2.15 renderer and tested it on WordPress 7.1.5. It requires a native page ID, exact slug, default page template and per-post editor permission. The six scoped paths return a held response for public requests even if a page is published or its binding is missing. Other routes keep their existing handlers.

The preliminary render exposed two release defects. The existing lead clients send the browser path instead of the canonical intake path. Removing a measurement loader leaves the global REST eligibility and client attribution paths active. The hardened component therefore emits only editor previews with disabled forms. An alias-aware intake adapter and an explicit server measurement boundary must pass separate end-to-end tests before public serving. The component has no configured production IDs or deployment procedure.

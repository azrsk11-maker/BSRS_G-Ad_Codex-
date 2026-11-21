# Off-plan form text candidate

Private offline preparation for German, French and Taiwan Traditional Chinese. The compiler produces **85 translated strings per locale** in a form-only fragment, text-only variants of the existing lead/measurement-preference clients, and inert strings for the owned PHP template. It cannot install, publish, submit a lead, change consent, emit a measurement event or contact a service. No runtime hook is added to Source.

`BASE_MANIFEST.json` binds seven exact fixture files at Source head `854fa07032709856c33a418f81ac8f385a863c59`, tree `738f32887c610260b614b95b3f0470ac35683a90`. These are immutable staging fixtures, not a readback of installed WordPress. Source fixtures/runtime remain unchanged. The compiler refuses output inside Source, populated output directories, base drift, missing/extra translation keys/locales and unmapped source text. Output checks compare the complete file inventory and bytes.

```text
python3 -B -m unittest discover -s tools/offplan-lead-first/form-localization -p test_form_localization.py -v
python3 -B tools/offplan-lead-first/form-localization/compile_form.py --source-root . --out ../form-localization-preview
python3 -B tools/offplan-lead-first/form-localization/compile_form.py --source-root . --out ../form-localization-preview --check
```

On Windows use the verified interpreter from the applicable workspace instructions. From another tooling location, set `BSRE_FORM_SOURCE_ROOT` to the Source checkout for tests and pass `--source-root` for compilation. The existing landing-package CI test pattern does not discover these tests; add the explicit focused command when integrating this tooling. This candidate does not require a native/runtime suite because it changes no fixture/runtime bytes. Generated client variants would require new native acceptance before installation.

| Surface | Produced artifact | Remaining binding |
| --- | --- | --- |
| Form labels, placeholders, options, mandatory contact, optional marketing, submit/no-script text | `LOCALE/form.html`, with a local `lang` attribute and enclosing disabled preview fieldset/legend | Existing owned renderer must deliberately select/insert this fragment. No whole page or contact link is copied. |
| Client validation, secure-send/retry/conflict/uncertain statuses, durable receipt and success copy | `LOCALE/lead.js` | No asset selection/install. Exact inverses restore all nontranslated bytes, including existing transport, receipt, deduplication and event logic. |
| Optional measurement labels, aria label, retention explanation, save/pending/error copy | `LOCALE/consent-bridge.js` | No asset selection/install. Consent state, unknown/denied behavior, eligibility and personalization-off remain unchanged. |
| WordPress privacy insertion, preview/live banner and legend, unavailable text | `LOCALE/template-strings.json` | Metadata only. `templates/page.php` still inserts English; `includes/presentation.php` still emits canonical asset names. |
| Browser-native required/pattern/email validation pop-ups | No runtime replacement | Browser-controlled language; verify in the actual intended browser. Explicit client/server validation statuses are translated. |
| Translated privacy policy document, global page content/contact links and live page language | No artifact | Authenticated readback, real approved privacy/contact/CMS route and renderer/runtime resolution are still required. |

The preserved `data-landing-path` is the existing `/enquire/off-plan/` protocol value; it is not a new localized URL or an observed live route. New country landing slugs are not accepted by the native fixed six-path resolver. DOM form language `zh-Hant-TW`, trusted measurement language `zh-TW`, and Ads language `zh_TW`/1018 belong to different contracts; no automatic conversion or context binding is added. Consent UI language cannot be promised solely from the scoped form language.

The preview fixture contains historical contact information. The fragment omits its numbered fallback and all contact links. Derived clients deliberately preserve the original contact-matching logic byte-for-byte; they must not be installed against the owner's current contact setup until the real contact path is read back and separately bound. Endpoints and asset URLs are never invented. `action="#"` and the original disabled submit are preserved. An added enclosing disabled fieldset prevents existing `lead.init` from enabling interactive preview submission when it enables the button; the localized legend makes that preview state visible. Original control attributes, constraints and wire values are unchanged. The preview fieldset must remain disabled during review; runtime integration is a separate change requiring its own acceptance.

Translations are drafts. Existing private DE/FR UI-label drafts informed the wording; additional option/status strings were authored for this exact fixture. Competent language review remains pending, including Traditional Chinese. Owner-confirmed Mandarin handling does not approve this copy or establish Taiwan legal applicability. Mandatory enquiry contact remains distinct from optional marketing and optional measurement; no legal acceptance, fluent DE/FR staffing promise, inventory, property availability or qualification claim is added.

Integration remains **HELD**: no Source/runtime/CMS/Ads write, live intake test, delivery receipt, privacy-document translation, country/platform clearance or activation follows from these offline tests. Review the fragment and client variants privately, then design the owned renderer/asset selection against authenticated installed-byte readback while preserving the existing endpoint, signed wire-v1 and accepted-event ownership. Do not paste this fragment into an ordinary WordPress content block and claim integration; the owned page renderer controls output.

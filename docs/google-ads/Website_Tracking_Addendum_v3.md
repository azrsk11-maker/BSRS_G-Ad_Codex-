# BlackSwan Real Estate — Native Website and Tracking Amendment

## 24. Owner amendment — native Hostinger website pages and complete conversion instrumentation

**Added in version 3.0, 6 November 2026.** The owner will open Hostinger and the existing website admin panel for the implementation workflow. This is a specification amendment, not evidence that those panels were accessed or that the live website has been changed.

**Binding interpretation:** every campaign still has a dedicated destination, but that destination must be a native page or route of the existing BlackSwan Real Estate main website. “Separate landing page” means a campaign-specific page within that website, not an independent website, microsite, hosting project, secondary CMS or third-party landing-page deployment. Retain 14,000 total positive phrases, 14,000 total negative phrases and the 360 planned campaign/page slots.

### 24.1 Main-site ownership and implementation boundary

Use the existing main site's verified canonical domain, website application, CMS/content model, admin panel, design system and deployment pipeline. The expected domain remains `blackswanrealestate.ae` from the prior plan; confirm the actual canonical hostname, redirects and selected Hostinger website before changing anything. Never create a second brand/domain based on a speech-to-text spelling variation.

Each page must have an editable CMS content record or native application route managed through the main site's existing deployment process. Reuse shared typography, branding, approved legal information, property data and consent controls. Campaign-specific layouts may simplify navigation without becoming a separately hosted site. Do not embed an external landing page in an iframe and call it a native page.

Proposed routes remain `/lp/bsre-c0001/`, `/lp/bsre-c0002/`, etc. They are URL examples, not existing published pages. If the CMS cannot support this exact hierarchy, propose a supported same-site path and update the registry before implementation; do not silently move the campaign to another host, domain or application.

Keep pages out of the public menu, site search, page directories and sitemaps, but accessible through ads and shared/direct links. Preserve page-level `noindex` with crawler access. Do not accidentally apply `noindex` to the whole main website. Unlisted does not mean private. Source: G1, rechecked for this amendment on 6 November 2026.

### 24.2 Hostinger and admin-panel discovery sequence

1. Confirm the selected company, site/domain and access permissions. Hostinger access alone does not establish access to Google Tag Manager, GA4 or Google Ads.
2. Identify whether the existing website uses WordPress, a Hostinger builder, or another framework/application. Do not assume WordPress because the site is hosted by Hostinger, or assume the website builder because Hostinger provides one.
3. Inspect the actual main-site page editor, theme/templates, form handling, plugins/integrations, code deployment, cache/CDN and current analytics installation. Record ownership and a baseline before changing anything.
4. Verify page-count limits, supported URL paths, page-level indexing controls, metadata, custom events, form-success callbacks, secure backend processing and the planned 360-page scale. Unsupported capabilities are blockers to report, not permission to create independent landing sites or silently migrate the main website.
5. Export or back up supported content/configuration and verify a practical rollback route. Work in a protected staging/draft workflow appropriate to the actual CMS; staging must not send real leads or production bidding conversions.
6. Build one native campaign-page template and validate it end to end before generating the remaining pages. Preserve existing working pages and production forms.
7. Use authorized access only; never store admin passwords, session cookies, Google credentials or private client data in the repository. Opening a panel is not approval to change unrelated DNS, billing, hosting subscriptions, access permissions or active advertising spend.

Hostinger documents a GTM container-ID integration for its builder/manual-mode interface. That is an available product capability, not confirmation of BlackSwan's current CMS. If that is the detected stack, use its supported integration; otherwise use the actual website's supported global installation mechanism. Source: H1.

### 24.3 One shared measurement configuration; distinct page and CTA identities

Proposed default: use the verified BlackSwan Real Estate GTM web container and GA4 web stream across the main website and all campaign pages. Audit existing installations first. Do not create a separate GA4 property, GTM container or conversion label for every landing page merely to distinguish performance. Record any justified existing multi-container/cross-account setup rather than deleting it blindly.

Use one deployment path for each tag. Check the CMS, theme, plugins, Hostinger integrations and GTM for duplicate installations before adding code. Preserve existing approved measurement until a tested migration/replacement is authorized.

Maintain a restricted-access tracking register:

| Item | Required record |
|---|---|
| Website | Verified canonical domain, Hostinger site identity, CMS/application identity and deployment owner |
| GTM | Actual container ID, workspace/environment, published version, ownership and verification evidence |
| GA4 | Actual property ID, web-stream identity and `G-...` measurement ID |
| Google Ads | Actual Real Estate customer ID, relevant conversion account, `AW-...` tag/conversion ID and conversion-action labels |
| Conversion actions | Business meaning, trigger, primary/secondary treatment, selected import route, counting/deduplication rule and approval |
| Campaign page | Immutable campaign key, actual Ads campaign ID when known, landing-page ID, CMS/native route identity, content version and actual URL |
| CTA/form | Stable CTA ID, action type, placement, destination, form ID, expected event and test result |
| Operational delivery | Approved backend destination, email route, Sheet ID, failure owner and delivery evidence |

The ID formats above are descriptions, not account values. Leave actual IDs null or `SOURCE_REQUIRED` until read from authorized accounts. A Google Ads customer ID is not the same field as an Ads conversion ID. For manual Google Ads conversion tags in GTM, use the real Conversion ID and Conversion Label. Source: G12.

### 24.4 What must be measured

Preserve the existing canonical operational events. The following is the page-instrumentation contract, not a claim that all integrations already exist:

| Interaction or outcome | Event / record | Meaning and control |
|---|---|---|
| Page visit | `page_view` with landing-page context | One normal view per actual navigation; do not duplicate automatic and manual page views |
| Ordinary CTA click | `cta_click` | CTA, placement and destination are known; not automatically a lead |
| Call-button click | `phone_click` | Dial intent only; not proof of a connected call |
| WhatsApp button | `whatsapp_click` | Outbound action only; not proof a message was sent |
| Email button | `email_click` | Mail-client launch intent only; not proof of a delivered email |
| Form interaction | `form_start` | A visitor began the enquiry flow |
| Form failure | `form_error` | Sanitized error category only; no entered field contents |
| Accepted enquiry | Operational `form_accepted`; GA4 mapping `generate_lead` | Emit after durable server acceptance, not on submit click or thank-you reload |
| Brochure/floor-plan | `brochure_download`, `floorplan_view` | Record a click/open/confirmed response accurately; do not claim the document was read |
| Calculator/comparison | `calculator_complete`, `comparison_complete` | Valid result produced; not automatically qualified demand |
| Property details | `property_view` | Property ID and context where available |
| Viewing request | `viewing_request` | Request captured; not the same as a confirmed booking |
| Confirmed viewing | `viewing_booked`, later `viewing_attended` | Require booking-system or authorized outcome evidence |
| Main-site continuation | `lp_to_main_site` | Internal navigation; no new source, artificial visitor or fake homepage view |
| Connected conversation | `conversation_verified` | Supported call/message integration or documented operational evidence |
| Commercial stages | Existing `qualified_lead`, `mandate_signed`, `offer_submitted`, `transaction_closed`, `commission_collected` | Evidence-backed operational outcomes; separately authorized offline feedback only |

A specialized CTA event such as `phone_click` is the canonical click record for that interaction. Do not also count a generic `cta_click` as another CTA action in totals. When duplicate diagnostic representations are necessary, explicitly reconcile them rather than summing them.

Use native GA4 recommended-event mappings where appropriate, including `generate_lead` for the accepted-enquiry representation, without creating two bidding conversions for one enquiry. Source: G17. Select the primary bidding outcome by the approved campaign objective. Raw phone/WhatsApp clicks, document interactions and page views remain diagnostic by default.

Real call reporting depends on country/account and provider eligibility. Verify the applicable integration before claiming answered-call or duration tracking. Where it is unavailable, retain honest click measurement and an approved operational evidence route. Source: G16. Likewise, a WhatsApp conversation needs supported messaging evidence; a website click cannot establish it.

### 24.5 Page, CTA and attribution fields

Populate page metadata from the native page registry, not from arbitrary visitor-supplied query parameters:

```text
company = BlackSwan Real Estate
campaign_key; landing_page_id; page_version; page_family
property_destination; property_segment; transaction_intent; language
property_id/project_id when applicable
cta_id; cta_type; cta_position; form_id when applicable
```

Example internal identifiers:

```text
campaign_key: BSRE-C0001
landing_page_id: BSRE-LP0001
cta_id: BSRE-LP0001-HERO-WHATSAPP
form_id: BSRE-LP0001-ENQUIRY
```

Use stable data attributes or native component properties, rather than matching mutable button text. Push structured events into the shared data layer using the supported implementation and GTM's native tag templates. A data layer does not persist automatically across ordinary page loads: rehydrate approved context on each relevant page. Source: G15.

Preserve permitted GCLID, GBRAID, WBRAID and standardized UTMs when available, alongside actual campaign/ad-group/creative IDs when provided. Verify auto-tagging and that redirects retain the relevant parameters. Source: G13. Do not infer a per-person search query or invent missing identifiers. Values provided by browser URLs are attribution hints, not trusted authorization or inventory data.

Store the first and most recent permitted acquisition touch separately from the current page. Moving from a campaign page to the homepage, another listing or a public contact form must not overwrite the original acquisition source. Do not put new UTMs on internal links. Ensure public-site enquiry components inherit permitted attribution as well as campaign-page forms.

At enquiry acceptance, join the contact record, immutable operational Lead ID, page/CTA IDs, permitted source context and event ID in the secure backend. Copy the relevant attribution to the approved email/Sheet outputs. Never make acceptance dependent on analytics consent or on a click ID being present. A missing source remains unknown rather than fabricated.

### 24.6 Privacy, consent and duplicate prevention

Consent controls must reflect the approved markets and actual implementation. Configure the required storage/data-use signals, including `analytics_storage`, `ad_storage`, `ad_user_data` and `ad_personalization`, and test initial, granted, denied and withdrawn states. Basic versus advanced consent mode is a reviewed choice, not an automatic preference. Consent Mode communicates choices; it does not itself obtain them. Source: G14.

Keep names, personal email addresses, personal phone numbers, free-text messages and other personal details out of GA4 event parameters, page URLs, titles and UTMs. Only allowlisted, non-sensitive metadata may go to general analytics. Enhanced-conversion user data, if separately approved and eligible, needs its own supported consent-aware path; hashing does not make it suitable for ordinary GA4 parameters. Source: G18.

Retain the existing durable backend, idempotency and outbox controls. Use a stable opaque conversion identifier in a supported deduplication field where applicable. Do not assume that a custom `event_id` universally deduplicates GA4, native Ads and imported events. Choose one Google Ads measurement route for each business action and test duplicates explicitly. Source: G12 and the baseline master.

No blanket promise of 100% visitor identification or attribution is permitted. Browser restrictions, consent choices, unavailable integrations and offline activity create gaps. Report observed, modeled and unknown outcomes separately. Do not require analytics consent in order to make an enquiry.

### 24.7 Mandatory implementation and release tests

Before a page is accepted, demonstrate native-page ownership, the actual editable content/route record, correct main domain, page-only noindex, useful content, functioning mobile layout and correct destinations.

Then test the journey:

```text
Ad/test acquisition context
  -> native campaign page
  -> meaningful CTA
  -> public main-site page
  -> valid enquiry
  -> durable record and single canonical conversion
  -> email + Sheet delivery with the same Lead ID/source
  -> supported qualification/outcome evidence
```

Repeat for direct traffic without click identifiers; consent granted/denied/withdrawn; invalid form fields; double-click; reload; network retry; email/Sheet outage; slow mobile; external booking return where used; unchanged main-site public forms; and staging/test traffic exclusion. Validate Google tag firing with Tag Assistant/GTM Preview, GA4 DebugView, Ads diagnostics and backend/delivery logs. Do not test by repeatedly clicking live advertisements or training production bidding with synthetic leads.

Deliver a page-level tracking matrix: URL, CMS/native page ID, campaign/page IDs, GTM version, GA4 stream, conversion-action mapping, CTA inventory, source persistence result, form acceptance result, email/Sheet receipt, consent result, duplicate result, mobile result, reviewer and evidence reference. A page is not complete merely because it looks correct or contains a tracking script.

### 24.8 Codex instructions added to the main mandate

```text
1. Inspect the existing Hostinger website and admin panel through authorized access.
2. Confirm the real stack and website identity; do not assume a CMS or invent IDs.
3. Build campaign destinations as native pages/routes inside this same website.
4. Use the existing CMS/app and deployment pipeline; no independent landing sites,
   second hosting projects, separate CMS installs, external-page iframes or silent migration.
5. Keep each campaign's own designated route while preserving normal main-site branding,
   shared components, public navigation onward and public-page functionality.
6. Discover/reuse verified company tracking accounts; audit duplicates before installing.
7. Apply shared tags plus page/form/CTA identities, supported event triggers, consent,
   attribution persistence, durable acceptance and single-action conversion counting.
8. Verify page limits, page-level noindex, server/form capabilities and supported callbacks.
   If blocked, keep the affected pages on hold and report the exact incompatibility.
9. Prove an end-to-end pilot before scaling; attach independent test evidence per page.
10. Retain no-CRM scope, email/Sheet routing, all keyword counts and budget/release gates.
    Panel access alone does not authorize advertising spend or unrelated account changes.
```

**Current amendment status:** requirements and planning registers updated only. The live Hostinger site, CMS, GTM, GA4, Ads conversion IDs, phone/messaging integrations and production events have not been inspected or configured in this drafting task.

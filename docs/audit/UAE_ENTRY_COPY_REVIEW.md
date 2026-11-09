# UAE Search entry copy for owner review

The owner approved preparation of Option A on 9 November 2026. These offline copy drafts preserve one native entry page per campaign and the existing enquiry routes. The exact WordPress routes and planning slot bindings await authenticated checks and review. See the [decision register](../decisions/OWNER_DECISIONS.md).

| Campaign | Existing Ads ID | Average AED/day | Existing enquiry routes to preserve |
| --- | --- | ---: | --- |
| Buyers | 24372566774 | 1,200 | Off-plan and resale |
| Owners | 24367388382 | 400 | Sell and let |
| Tenants | 24378494092 | 300 | Rent |
| Brand | 24378494098 | 100 | Enquiry hub |

The first release must wait for both 14,000-keyword reviewed libraries and the remaining acceptance gates.

### Proposed page bindings for WordPress review

- **Buyers and Owners:** prepare a distinct native entry for each campaign. The 7 November ad inventory shows two different service destinations in each campaign. Preserve both destinations as explicit choices from the new entry. Keep the entry path, WordPress page ID and planning-slot ID unassigned until native route and registry checks pass.
- **Tenants and Brand:** assess reuse of the current rental page and enquiry hub, respectively. Each is already the sole final URL for its campaign in the dated ad inventory. Public HTTPS responses on 9 November returned the exact canonical URLs and page-level noindex metadata, without exposing a WordPress page ID in the body class. Verify CMS ownership, navigation and crawler eligibility before accepting either as the dedicated entry.
- **All four:** review the exact proposed entry-to-service paths against the [dated ad inventory](ACCOUNT_AD_URL_READBACK_2026-11-07.json). Reuse requires the same consent and receipt behavior as a new entry. Leave Ads destinations and the site untouched during this review.

### Public WordPress identity readback — 9 November 2026

A read-only request to the public WordPress pages API returned six published records with exact canonical links. The enquiry hub is page **26750**, with no parent. It is the recorded parent of off-plan **26751**, resale **26752**, rent **26753**, sell **26754**, and let **26755**. This establishes the public CMS identities of the Brand and Tenants reuse candidates and the existing service pages. Verify internal ownership, Ads crawler eligibility and end-to-end CTA behavior before accepting a binding. Buyers and Owners still need their own entry-page assignments.

### Public CTA readback — 9 November 2026

The Brand hub HTML contains links to all five exact same-origin enquiry routes and has no HTML form. The Tenants page has one form marked `data-bsre-form`, `data-role="tenant"` and `data-landing-path="/enquire/rent/"`. This supports the proposed hub-to-service and direct-rental journeys. The request was read-only. No enquiry, permission choice or conversion was submitted. Verify rendered navigation, permission behavior and receipt binding in the isolated end-to-end test before release.

### Candidate planning slots for the reuse review

| Campaign | Proposed planning pair | Family | Existing WordPress candidate |
| --- | --- | --- | --- |
| Tenants | BSRE-C0301 / BSRE-LP0301 | RNT | `/enquire/rent/`, page 26753 |
| Brand | BSRE-C0281 / BSRE-LP0281 | CMP, brand-demand subset | `/enquire/`, page 26750 |

These are the first unbound placeholders in their respective families, chosen as a deterministic proposal. Each slot currently has a proposed `/lp/` path and no deployed identity. Reusing an existing enquiry page would bind its canonical route after review. It would not create or redirect an `/lp/` path. Before changing the registry, reconcile the existing native page against any reserved slot or historical brief, confirm the exact binding, and preserve the approved family totals. Buyers and Owners are pending their primary family choices.

### Historical brief crosswalk check

The private 300-brief worksheet has no reviewed assignment to either proposed landing-page ID. BSRE-LP0301 is outside the historical candidate pools, consistent with RNT being an expansion family. BSRE-LP0281 appears in the shared CMP candidate pool for 20 historical briefs. Treat that overlap as a planning dependency. A Brand assignment would consume one CMP slot and requires item-level review of any competing paid adaptation. Preserve the original public brief IDs and routes. No private worksheet rows were published.

The next read-only review joined all 20 CMP candidate briefs to the hash-verified historical register. They have 20 distinct proposed routes and no exact overlap with the enquiry hub or rental page. One brief mentions Black Swan in its title or primary query. It is a webinar-planning brief with a separate event route, so keep it in the public-content register and preserve its identity. This clears the observed route overlap for the reuse proposal. It leaves the CMP slot allocation and independent content review open.

### Public crawler preflight

On 9 November, the public robots file contained one wildcard group and disallowed only `/wp-admin/`, with an exception for its AJAX endpoint. Neither reuse candidate was excluded. Four direct GET requests using the desktop and mobile AdsBot user-agent strings returned HTTP 200 without redirect for both `/enquire/` and `/enquire/rent/`. These requests were local simulations. Actual Google Ads crawler access, policy status and post-migration destination behavior require native readback before launch.

### Native page sitemap check

On 9 November the sitemap index listed 19 child sitemaps. The page sitemap returned HTTP 200 with 51 page locations. It omitted the Brand enquiry hub and all `/lp/` paths, but included all five existing service routes: off-plan, resale, rent, sell and let. Consequently the proposed Tenants reuse fails the sitemap-exclusion requirement in the current public snapshot despite its page-level noindex metadata. Prepare a scoped sitemap exclusion for designated paid pages and verify the cached sitemap after separately authorized deployment. Preserve the public guide sitemap entries and direct Ads crawler access. Other sitemap types and menus/search/feed exclusions were outside this check.

### Scoped sitemap correction for review

The public XML identifies All in One SEO 5.0.2.1 as the generator. Its [XML sitemap documentation](https://aioseo.com/docs/how-to-exclude-content-from-your-xml-sitemap/) supports individual page exclusions. If the Tenants reuse binding is approved, prepare a General Sitemap exclusion for WordPress page **26753** only. Confirm the page ID and existing exclusion list in the authenticated UI, preserve every existing entry, and save only after separate authorization. The Brand hub already meets this XML exclusion check, so the proposed change does not add it.

Before any approved save, capture the page-sitemap URL set and exclusion list. After the save and any narrowly scoped cache refresh, confirm only the rental URL was removed from that baseline, the rental page still serves its canonical URL with noindex, and existing service and public-guide links continue to work. If the result differs, restore the prior exclusion list and recheck. RSS sitemap, search and navigation acceptance remain separate.

### Native site-search check

On 9 November, public WordPress search for each exact page title returned the corresponding page ID once: Brand 26750 and Tenants 26753. The public search HTML also contained links to the requested route, although the link markup alone did not establish which template component emitted them. Both reuse candidates fail the public WordPress search exclusion check. A sitemap-only exclusion will not address this separate surface. Any correction needs a narrowly scoped search filter and positive controls for ordinary pages. Direct campaign destinations, enquiry navigation, and the private admin search must remain functional. No search settings were changed.

### Navigation sample and search correction status

The public homepage HTML had two navigation elements and contained no links to either proposed reuse page. The hub still linked to the rental form outside any navigation element, as required for its enquiry journey. This sample does not cover every theme template, mobile or JavaScript-generated navigation.

The opt-in search correction passed the [isolated WordPress lab](https://github.com/azrsk11-maker/BSRS_G-Ad_Codex-/actions/runs/42562068443/job/128980460332). The synthetic database showed that both paid pages were hidden from public core and REST search after activation of the candidate. An ordinary page stayed searchable, editor REST search still returned all three, and the rental page was directly accessible. The lab restored its pre-test fixture count before later phases. Live theme acceptance and the sitemap correction remain separate.

## Buyers

### Find a Dubai property to buy

Start with the type of purchase you have in mind. Tell us your preferred locations, budget and timing. If you are considering both options, choose the one you want to discuss first.

- **Discuss an off-plan purchase** → [/enquire/off-plan/](https://blackswanrealestate.ae/enquire/off-plan/)
- **Discuss a resale purchase** → [/enquire/resale/](https://blackswanrealestate.ae/enquire/resale/)

Keep both choices visible together. Review whether the two existing ad groups can use intent-specific CTA prominence without changing the campaign’s dedicated entry or creating an extra indexable route.

## Owners

### Plan the sale or letting of your Dubai property

Choose whether you want to sell or let. Tell us where the property is, what type it is and when you want to move forward. If you are deciding between selling and letting, mention that in your enquiry.

- **Discuss selling my property** → [/enquire/sell/](https://blackswanrealestate.ae/enquire/sell/)
- **Discuss letting my property** → [/enquire/let/](https://blackswanrealestate.ae/enquire/let/)

Review the wording against the confirmed seller and landlord service remit. Verify commercial coverage separately before adding a claim about commercial sales or leasing.

## Tenants

### Find a Dubai rental that fits your move

Share your move-in date, preferred areas and rental budget so the team can understand what you are looking for.

- **Start a rental enquiry** → [/enquire/rent/](https://blackswanrealestate.ae/enquire/rent/)

Review whether the existing rental page can serve as this campaign’s dedicated entry. If it does, place the CTA at the enquiry form on that page and avoid a circular link.

## Brand

### Contact Black Swan Real Estate about Dubai property

Choose the kind of help you need. The enquiry hub can direct you to the form for buying, selling, letting or renting.

- **Choose an enquiry type** → [/enquire/](https://blackswanrealestate.ae/enquire/)

Review whether the existing hub can serve as this campaign’s dedicated entry. If it does, place the CTA at the existing service choices and avoid a circular link.

## Acceptance before use

- Compare the four campaign identities and the six existing routes with the [dated ad inventory](ACCOUNT_AD_URL_READBACK_2026-11-07.json). Verify native ownership and resolve the dedicated page mapping with the owner.
- Have the nominated factual reviewer approve each service description and destination. The draft includes no prices, listings, guarantees or availability claims.
- Test each entry and follow-on CTA on desktop, mobile and keyboard. Verify attribution through the CTA, preserve the current intake and consent flow, and check that a page or CTA interaction does not count as an accepted enquiry.
- Preserve noindex and ad crawler access. Require separate publication and Ads approvals before any live change.

## Entry-to-enquiry attribution review

Record the dedicated entry as the acquisition page and the chosen enquiry route as the submission page. The same-origin CTA must use a clean URL. Preserve permitted acquisition context through the existing purpose-specific state and bind it to the durable receipt on the server. An internal navigation must neither start a new acquisition nor forward a click ID in the URL.

The offline [event contract](../../tools/website-tracking/tracking-system/contract.mjs) validates a supplied event URL against its registered campaign entry URL. A reviewed form CTA can declare a separate submission path. The prototype checks the server-confirmed receipt against that path and keeps the submission URL out of GA4 and Ads payloads. The production caller must establish the receipt and route from authoritative server context before using this binding.

### Source of the receipt binding

The [pinned intake handler](../../tools/staging-lab/fixtures/bsre-enquiries/bsre-enquiries.php) retains the validated wire body in request memory through upstream acceptance and passes it to `consent_link_accepted`. That is where a server integration can derive the route from the original body after checking the accepted capture fingerprint and IDs. The consent table stores the fingerprint, not the body. Avoid persisting a second copy of the contact-bearing body for measurement.

The [proof-only recovery handler](../../tools/website-tracking/tracking-system/receipt-recovery-wordpress.php) reads capture identifiers and status without the original body. A recovery using that path can return the existing lead reference but cannot establish a new submission-route binding. Preserve its no-measurement behavior. An exact-body retry must verify the same fingerprint and receipt and preserve the existing conversion deduplication rules.

| Review journey | Evidence needed |
|---|---|
| Buyers or Owners chooses either service | The registered entry CTA resolves to the exact service route. The enquiry retains the original campaign attribution, with the service route recorded separately. |
| Brand opens the hub then a service | The hub and subsequent internal CTA preserve the original Brand acquisition. Neither interaction produces an enquiry conversion. |
| Tenants uses the rental form directly | An in-page CTA keeps the same navigation context. Only the accepted receipt can produce the enquiry conversion. |
| Consent is refused or withdrawn before submission | The enquiry can still be delivered. Browser measurement stops and denied advertising identifiers are omitted from subsequent export. |
| Acknowledgment is lost and the visitor retries | The same durable lead and event IDs reconcile to one intake result. CTA clicks and a replayed receipt do not produce an extra conversion. |

The offline attribution and event tests cover separate portions of this flow. Final acceptance needs an isolated end-to-end test with the approved native entries, their real CTA bindings and the actual service routes.

## Tenants copy review

A public read-only request to the rental entry returned HTTP 200 on 9 November. The page requests preferred Dubai areas, an annual AED budget, property type and move-in timing. It says that submission creates no reservation and that availability and viewings require separate confirmation. Keep those boundaries.

| Review point | Proposed public copy or action |
| --- | --- |
| The current timing paragraph refers to “this campaign.” | “Choose when you need to move so we can review your rental requirements against your timeline.” |
| Some readers may treat a viewing enquiry as a confirmed booking. | “Tell us your preferred areas and annual budget. A viewing is confirmed separately after we check availability.” Keep the same confirmation boundary in the receipt. |
| The fallback text calls the form a preview. | Inspect its visibility with JavaScript available and blocked in staging. If it is the no-JavaScript fallback for a released form, use “This form requires JavaScript. If you cannot submit it, use the contact options on this page.” Verify the live phone and WhatsApp destinations before release. |
| Official tenancy services have a different purpose from an immediate rental enquiry. | Keep registration and renewal guidance in separate editorial content. Point users to the official DLD service when relevant. Keep the Rental Index separate from live listings and any price or eligibility claim. [DLD tenancy contract service](https://dubailand.gov.ae/en/eservices/register-renew-ejari-contract/), [DLD Rental Index](https://dubailand.gov.ae/en/eservices/rental-index/?lang=en) |

The proposed wording preserves the tenant role, existing form fields, consent choices and receipt contract. A factual reviewer must verify service scope and actual contact ownership. This review used the returned HTML and did not exercise rendered visibility, submit a form or change WordPress.

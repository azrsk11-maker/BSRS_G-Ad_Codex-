# Native WordPress planning adapter

Implemented locally from the supplied version-3 register and Master Plan sections 8 and 24. This is a planning compiler and disabled preview adapter, not a deployed plugin or finished landing-page system. No WordPress request or write was made.

## Artifacts and verified scope

- `compile_native_manifest.py` validates the 360 source pairs, family allocations, unique immutable identities, proposed routes and unpublished state. It emits a native WordPress draft plan without property copy, inventory, verified URLs, campaign IDs, CMS IDs or publication authority.
- `native-page-manifest.json` was compiled from the supplied register: **360 pairs across 15 families**. Every slot remains `BLOCKED_SOURCE_REQUIRED`; every route is explicitly proposed. The compiler records a canonical input digest for reproducibility.
- `native-draft-preview.php` is inert unless included inside WordPress and explicitly enabled with `BSRE_NATIVE_PLANNER_PREVIEW_ENABLED=true`. Its only function requires `manage_options`, a valid `bsre_native_page_preview` nonce and `dry-run` mode. It validates all mappings, previews exactly one selected slot, checks both campaign and page metadata, preserves an existing matching record and rejects duplicate ownership or occupied paths. It never creates the `/lp` parent.
- Every proposed CMS request is a native `page`, `draft`, empty content, stable metadata, and an internal planning title. These are review data only. There is no public endpoint, hook, rendering replacement, network request, WordPress write API, theme change, global setting change or apply handler. All write modes fail closed.

Eight Python tests passed in 0.040898 s, covering identity preservation, missing/duplicate slots, unsafe or changed paths, family mismatches, existing/approved-state rejection, deterministic output, source immutability and CLI input-overwrite refusal. Compilation against the actual supplied package succeeded. Independent review found and fixed a CLI output-path overwrite risk before handoff; the post-fix result is recorded in `verification.json`. The separate ten efficiency-cache tests are recorded one directory above.

The PHP acceptance harness is supplied under `tests/` with isolated WordPress read doubles. It covers disabled state, authorization/nonce/mode/origin checks, missing parent, draft content, duplicate identities, unsafe path, publication rejection, path collision, existing-page preservation and conflicting ownership. **CI subsequently passed both PHP lint checks and all 17 isolated behavior checks on PHP8.5.4.** See [the pinned CI receipt](../../docs/audit/CI_VERIFICATION.json); later PR heads must pass again. PHP is not available through the verified local PATH; the historically security-blocked PHP executable was not reused or bypassed. The harness must never load a real `wp-load.php`.

## Relevant existing-source finding

`paid-entry-search.php` is a staging candidate for Option A. It registers hooks only when `BSRE_PAID_ENTRY_SEARCH_EXCLUSION_ENABLED` is explicitly true. On the verified Real Estate origin, it checks the exact WordPress type, ID and path of the proposed Brand and Tenants entries, then excludes them from main public search and REST post search. Existing exclusion lists, direct page requests and admin search are preserved. The isolated PHP harness tests the hook behavior. Real theme and REST integration acceptance is still required before deployment. [WordPress query hook](https://developer.wordpress.org/reference/hooks/pre_get_posts/) and [REST search hook](https://developer.wordpress.org/reference/hooks/rest_post_search_query/).

The saved 0.2.12 candidate associated with the current consent checkpoint uses a **fixed six-path map** and `owned_parent_scope()` with held/preview/live rendering. Its existing `ensure_drafts()` creates only the fixed `SERVICES` under `/enquire` and validates its owned-page registry. Its draft preview disables form submission and measurement. Neither mechanism establishes support for 360 `/lp` routes.

The two current local files were read, without modification: `includes/drafts.php` SHA-256 `d4021ae8572da12111d74e0a9b54daba38a1beb34badb8b07930a8c73a784632`; `templates/page.php` SHA-256 `9e29a3a16179223eec4b8c241eb6bae2bc2ed19d036c46ae33c5b3e1a22eb3ce`. Live deployment status comes from the existing checkpoint and is not refreshed by this code review.

## Reproduce and CI acceptance

```powershell
$nativePython = Join-Path $env:USERPROFILE '.codex/tools/jcodemunch/venv/Scripts/python.exe'
& $nativePython -B test_native_manifest.py
& $nativePython -B compile_native_manifest.py --registry '<spec-dir>/planned_campaign_page_registry.json' --allocation '<spec-dir>/page_family_allocation.json' --output native-page-manifest.json
```

On a reviewed CI runner with PHP 8.2 or newer:

```sh
php -l native-draft-preview.php
php -l tests/native-draft-preview-test.php
php tests/native-draft-preview-test.php
```

The preview adapter is not a plugin installation package. Do not install it to obtain a green check. Review and execute the isolated harness first; then a separate approved staging integration may call the function. Production publication, Ads configuration and live tracking require their own authorization even after merge or passing tests.

## Next acceptance and scoped recovery

Before a writer or renderer is implemented, resolve source/old-plan inconsistencies, verify the selected Hostinger site/CMS and canonical origin, map relevant existing pages, confirm the `/lp` parent/path and scaling limits, and approve one native template. Verify shared consent/routing, page-only noindex, crawler access, site-search/menu/sitemap/feed exclusions, attribution and real content evidence before accepting any page. Unlisted pages remain public after a separately approved publication; the current drafts/manifest do not satisfy that gate.

The preview's CMS queries are not a complete route audit: active filters can hide records, and page-path lookups do not establish that custom post types, redirects, rewrite rules, CDN or plugins leave a proposed route free. Independent review identified these as native-integration acceptance requirements; they do not authorize a writer or make a blocked plan deployable.

On 9 November, public HTTPS GETs without redirect following returned 404 for `/lp/` and for the first proposed manifest path in each of the 15 families. The sampled campaign suffixes were 0001, 0031, 0071, 0121, 0151, 0171, 0191, 0211, 0231, 0261, 0281, 0301, 0321, 0336 and 0351. No response provided a redirect target. This records public routing for 16 requests only. An authenticated check of private CMS records, redirects and rewrite rules is still required before assigning any route.

This version performs zero writes, so recovery is removal of these local candidate files or disabling the preview constant; there are no created CMS IDs to roll back. Do not change existing intake settings, private data, theme or sitewide indexing.

A future separately approved production writer must journal the exact campaign/page IDs, CMS ID, prior revision ID, before/after hashes, changed metadata and approval reference. Recovery must address only those allowlisted IDs, verify ownership and that the current version still matches the recorded after-version, preserve intervening staff edits, and restore only the recorded revision/metadata after review. Newly created records stay held as drafts for reconciliation. Never delete posts, reactivate old campaigns, replace the database or alter unrelated records as rollback. The separate [disposable lab writer](WRITER.md) implements native draft operations for synthetic acceptance only; it cannot run on the production site or turn this preview into a deployment handler.

The [ten property decision tools](../property-decision-tools/README.md) are a separate disabled integration candidate for Master Plan section 9. They calculate user-entered scenarios without invented rates, inventory or external transmission. Native page/template bindings, factual review and publication remain separate gates.

## Buyers and Owners block drafts

The [Buyers block body](entry-drafts/buyers.html) and [Owners block body](entry-drafts/owners.html) use WordPress core paragraph and buttons blocks. Use the page title separately in the editor: “Find a Dubai property to buy” and “Plan the sale or letting of your Dubai property.” The fragment contains two clean relative links to the existing service forms. It has no form, script, assets or publication settings.

Treat these as reviewable post-content fragments. The11November direct owner reply selected BuyersOFP and OwnersSEL, with resale/letting preserved as secondary context; [the classification record](entry-drafts/primary-family-decisions.json) retains the exact decision scope and historical campaign references. The existing fragments already place those enquiry links first and remain unchanged. Before import, confirm the individual planning slot and exact page/route binding, review CTA prominence, verify content/service evidence, and validate the blocks in the current WordPress editor and theme. No slot, CMS ID, actual entry URL or Tenants/Brand reclassification is inferred. These files carry no deployment authority.

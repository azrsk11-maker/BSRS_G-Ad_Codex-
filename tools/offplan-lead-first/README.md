# Off-plan lead-first country package

Owner scope: [issue 14](https://github.com/azrsk11-maker/BSRS_G-Ad_Codex-/issues/14), 21 November 2026. Target 345 new enquiries/day; **AED2,500 aggregate average/day before VAT** across UAE, Germany, France and Taiwan. No lead-volume or cost forecast is invented. Russia geography is excluded under current Google restrictions.

The operator's initial test allocation is UAE1,500 / Germany350 / France300 / Taiwan350. This split is a proposal within the authorized total, not observed market economics. Retain Maximize Clicks/CPC cap20, Search-only and presence targeting. Existing10:00–19:00 Dubai contact hours are retained pending live readback. No budget may be multiplied by country or increased to meet the target without further authorization.

## Implemented locally

- `copy.json`: customer-facing German, French and Taiwan Traditional Chinese pages and RSAs. No inventory, pricing, returns or licensing approval is fabricated.
- `keywords.json`:46 authored localized phrases /92 exact-or-phrase placements. They are neither observed search queries nor admissions to the full14,000-term master. Three narrow Taiwan negative proposals remain unapplied.
- `launch.json`: off-plan-only campaign review contract. Reuse the dated UAE campaign24372566774, only off-plan group204397706154/ad828621612892. Keep resale group204397706314, Owners/Tenants/Brand and all legacy campaigns paused. New campaign, geography and CMS IDs remain unbound.
- `compile.py`: deterministic, network-free compiler. It produces three native WordPress Custom HTML blocks, native page field proposals, review CSVs and an inert activation review. It cannot create a page, enable an ad, import conversions or write a Sheet/mailbox.
- `generated/MANIFEST.json`: input and output byte hashes; it excludes its own hash to avoid a cycle.

```text
python -B -m unittest discover -s tools/offplan-lead-first -p test_compile.py -v
python -B tools/offplan-lead-first/compile.py --write
python -B tools/offplan-lead-first/compile.py --verify
```

On Windows use the interpreter specified by the workspace AGENTS.md. Checks cover budget/identity/scope, Unicode double-width RSA limits, escaping, draft/readiness distinctions, duplicate/admission/metric rejection and deterministic output. They do not establish live WordPress or Google acceptance.

## Native WordPress handover

Create native **draft pages in the existing site**, using the proposed title/slug and each `.html` file as a Custom HTML block. No separate site, theme replacement, synthetic writer or new importer plugin is required by these artifacts. Proposed paths are not observed live URLs; inspect occupied paths before creation and retain the actual CMS IDs. The original360-slot register is unchanged; no false canonical ownership is assigned.

**The landing copy is localized; the enquiry form is not yet localized.** Each page explicitly says the next step opens the existing English off-plan form. Mandarin handling was owner-confirmed. German/French staff-language coverage was not independently established; no fluent-staff promise is made. The generated blocks add no form, script, tag or measurement storage. Separate UI-label drafts have not been installed.

Before publication/serving, verify native document language, hreflang/canonical/noindex settings, the actual enquiry journey and consent/privacy, factual claims, country applicability and platform approval. EEA measurement must respect applicable consent; enhanced matching, personalization and qualified imports remain outside this launch. Taiwan overseas-property requirements and applicability need qualified review; translation is not legal clearance. References are in `policy_sources.json`.

## Live action remains separate

The owner authorized off-plan launch within the new scope. This package is not an execution result: browser access was unavailable when prepared, no current live readback exists, and **zero campaigns/pages have been created or enabled by this compiler**. After access is restored, identify account573-038-4686, inspect the dated UAE IDs, keep resale/other campaigns paused, bind the new pages/campaigns and read back the aggregate serving budget before enabling anything. Do not replay old leads, upload synthetic conversions, share the original workbook or introduce CRM synchronization.

The earlier six-verified/94-incomplete roadmap is preserved. The full libraries, qualification intelligence and broader content architecture move behind this focused lead-first work; they are not marked complete or deleted. GitHub review/protection and separate production-change controls remain effective.

## Offline form-localization tooling and verified market references

[The form text compiler](form-localization/README.md) adds85 German/French/Traditional-Chinese strings per locale, guarded form-only previews, string-only client variants and inert PHP-template metadata. Its21 focused tests and34 independent offline probes passed. [Review evidence and scope](form-localization/REVIEW.json) retain the exact reviewed hashes and three resolved findings. It changes no pinned fixture, installed runtime, producer, destination or consent state. Outputs are generated outside the checkout and remain uninstalled; labels are not a fully localized production journey. Source route/asset resolution, privacy documents, approved contact binding, language review and live acceptance remain required. The scoped CI explicitly checks this tooling and its fixture inputs; no native runtime suite is claimed as rerun.

[The targeting reference](country-target-reference.json) records the four exact top-level entries in [Google's official geo-target catalog](https://developers.google.com/google-ads/api/data/geotargets), dated6October2026 and checked21November2026: UAE2784, Germany2276, France2250, Taiwan2158. Taiwan is catalog type Region with no parent; the child Province9075967 is not the requested whole-market target. These global reference IDs do not establish account targeting, country/legal eligibility or campaign binding; `launch.json` live binding remains unverified.

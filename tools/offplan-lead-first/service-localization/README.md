# Regional property enquiry drafts

Preview off-plan, resale, rentals, seller, landlord and the brand enquiry hub across the approved 35 markets and 69 country-language combinations. English is the default for every market and service. Each approved regional language is included in both page and keyword review. The site drafts use the same responsive enquiry shell, contact actions and consent layout, with service-specific copy and form controls.

```sh
python -B tools/offplan-lead-first/service-localization/compile_review.py --out /path/outside/repository/property-review
python -B tools/offplan-lead-first/service-localization/compile_review.py --out /path/outside/repository/property-review --verify
python -B tools/offplan-lead-first/service-localization/check_review.py /path/outside/repository/property-review
```

Open `index.html` in the generated folder, choose a market and language, then choose a service. The 345 form previews preserve the existing field IDs, form names, initial choices, validation constraints and option values from the five registered service fixtures. The 69 hub pages link to these forms. The package's `field-mapping.json` records the original roles and fields for native integration. All preview form controls are disabled.

The keyword file contains 7,800 exact and phrase placements, including 3,266 off-plan placements and 4,534 other placements. Every source intent remains mapped even when two translated phrases coincide. The non-off-plan keywords are based on the observed paused service ad groups. They await competent language and Ads review. The 336 placements across Swahili, Nepali and Sinhala carry platform holds based on Google's published ad language list.

Only off-plan is in launch scope, subject to the existing landing-page, consent, delivery, conversion and eligibility checks. Resale, rentals, seller, landlord and brand are draft-only. `campaign-language-review.json` records the mandatory English content and optional regional coverage for each planning slot. The separate budget record continues to show the five previously verified paused pools totaling AED2,500 average per day. Bangladesh and Pakistan are geographic exclusions.

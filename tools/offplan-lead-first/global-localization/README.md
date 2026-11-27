# Off-plan localization for 35 markets

The 25 November 2026 owner decision sets English as the primary content in every market, with the approved local-language variants alongside it. The catalogue contains 35 English defaults and 34 additional country-language variants. Bangladesh and Pakistan are geographic exclusions. Market and language assignments are in [MARKETS.json](MARKETS.json).

Generate the review folder outside the repository and open its `index.html`. Each page includes localized content, the disabled enquiry form, optional measurement choices and verified contact links. The working enquiry form linked from the previews is the current English funnel. The catalogue includes localized feedback messages for later native integration.

```sh
python -B tools/offplan-lead-first/global-localization/compile_review.py --out /path/outside/repository/market-review
python -B tools/offplan-lead-first/global-localization/compile_review.py --out /path/outside/repository/market-review --verify
```

- `review-keywords.csv` maps 16 draft purchase intents and the eight observed UAE off-plan phrases into each variant, with exact and phrase matches. Repeated literal translations are consolidated within each country and language, with their source intent IDs retained.
- `previous-localized-keyword-drafts.json` preserves the earlier 62 authored candidates. The separate negative keyword glossary is for language review. It confers no keyword exclusion scope.
- `page-review.json` and `campaign-review.json` group proposed content paths, languages and geographic references. The five recorded paused budget pools total AED2,500 average per day. The other markets have no allocation in this package.

The drafts require competent language review and native WordPress integration before publication. Confirm staff response coverage, country eligibility, live enquiry and conversion delivery, applicable consent and privacy behavior, and Google Ads account acceptance before enabling ads. German and French coverage is being arranged. The Taiwan applicability review remains open. Verify China reach before allocating spend there.

Google's published supported ad languages omit Swahili, Nepali and Sinhala. Their website translations are included and their paid-language review rows are held. Release verification binds the English RSA, keywords and native destination for each market and the corresponding assets for each approved regional variant. Google Search applies automatic language matching. [Google Ads supported languages](https://support.google.com/google-ads/answer/6333734?hl=en) · [Search language matching](https://developers.google.com/google-ads/api/docs/targeting/criteria#language_targeting_criteria)

For United States and Canada housing campaigns, verify applicable restrictions on demographic and ZIP-code targeting. [Google Ads housing policy](https://support.google.com/adspolicy/answer/16701755?hl=en)

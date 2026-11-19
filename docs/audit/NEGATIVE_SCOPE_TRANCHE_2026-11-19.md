# Bounded negative applicability proposal — 19 November 2026

This is a private review candidate: **9 proposed exact negatives, 1 applicability hold, 0 approved and 0 applied**. All ten literals already exist in the accepted 14,000-record research set. No keyword is newly admitted, and no research record, approval or deployment field is changed.

Proposed target: saved campaign **24378494092**, `BSRE_V2_SEARCH_TENANTS_UAE_EN`, observed paused on 11 November. Only this saved campaign is proposed; the captured Owners, Buyers and Brand campaigns remain outside this proposal. No account-level or ad-group exclusion is proposed. The saved identity does not establish current live state or a canonical C0301-to-platform mapping.

| Existing research literal | Decision / match | Narrow applicability rationale |
| --- | --- | --- |
| apply for dubai property consultant job | PROPOSE / EXACT / campaign 24378494092 | Complete employment application, internship application, administrator-jobs or specialist-vacancy intent; no residential tenancy request. |
| apply for real estate internship dubai | PROPOSE / EXACT / campaign 24378494092 | Complete employment application, internship application, administrator-jobs or specialist-vacancy intent; no residential tenancy request. |
| commercial brokerage administrator jobs dubai | PROPOSE / EXACT / campaign 24378494092 | Complete employment application, internship application, administrator-jobs or specialist-vacancy intent; no residential tenancy request. |
| dubai leasing consultant job application | PROPOSE / EXACT / campaign 24378494092 | Complete employment application, internship application, administrator-jobs or specialist-vacancy intent; no residential tenancy request. |
| off plan sales specialist vacancy dubai | PROPOSE / EXACT / campaign 24378494092 | Complete employment application, internship application, administrator-jobs or specialist-vacancy intent; no residential tenancy request. |
| real estate conveyancer job application dubai | PROPOSE / EXACT / campaign 24378494092 | Complete employment application, internship application, administrator-jobs or specialist-vacancy intent; no residential tenancy request. |
| car rental dubai | PROPOSE / EXACT / campaign 24378494092 | Complete vehicle-rental intent; no residential tenancy request. |
| luxury car rental dubai | PROPOSE / EXACT / campaign 24378494092 | Complete vehicle-rental intent; no residential tenancy request. |
| monthly car rental dubai | PROPOSE / EXACT / campaign 24378494092 | Complete vehicle-rental intent; no residential tenancy request. |
| commercial sales and leasing consultant job dubai | HOLD / no scope selected | Singular consultant job can describe a commercial sales/leasing engagement; no application, vacancy or plural-jobs marker resolves that ambiguity. Preserve the existing research row. |

Campaign scope applies across all ad groups in that campaign. It is the narrowest saved entity supported here; ad-group ownership is unavailable. Broader scope is unnecessary for this tranche. Six employment proposals use whole role/application intent, never generic job, salary, vacancy, commercial or off-plan tokens. The three vehicle proposals never exclude generic rental or premises intent.

Negative EXACT requires the same terms in the same order without extra words. PHRASE allows extra words around the ordered terms, and BROAD can match all terms in a different order. Exact is deliberate: `car rental dubai office for lease` remains outside `[car rental dubai]`, while phrase/broad expansion could block that business-premises enquiry. Plurals, synonyms and additional variants are not silently added.

The official rule capture from 18 November is reused without a provider refresh: [negative matching](https://support.google.com/google-ads/answer/2453972?hl=en), [campaign/ad-group scope](https://support.google.com/google-ads/answer/7102995?hl=en). The repository checker is a lexical approximation; these bounded ASCII probes do not establish Google misspelling, symbol or close-variant equivalence. No live account matching or exclusion readback is claimed.

Bounded offline evidence covers 107 protected counterexamples and 963 proposal/query pairs, with zero local exact conflicts. Twenty cases reuse the existing authored protection file. The other 87 are explicitly authored tests, never observed queries or admissions. They include all eight service intents across all seven UAE emirates, plus separate future Oman and Saudi Arabia counterexamples. Additional examples preserve salary/affordability, payment plans, free floor plans, yield/service charges, schools, India/UK investors, complaints/reviews, landlord vacancy management and premises for vehicle businesses.

Protected examples include `rent apartment in sharjah`, `buy off plan commercial office in abu dhabi`, `sell my property in ajman`, `rent out my property in fujairah`, `affordable flat near my new job dubai`, `commercial sales and leasing consultant dubai`, and `monthly car rental dubai office space`. They assert protected intent, not service availability or a live target expansion.

Traceability: literals are matched by original research identity, source line and exact byte-pinned source projection. Employment source: `docs/audit/keyword-employment-education-2026-11-10/employment.json` (SHA-256 `34848eca2c291995570ba381850fac8ddbeac5f7878ff09777d879f228efa532`). Vehicle source: `docs/audit/keyword-exclusions-2026-11-10/software-services-products.json` (SHA-256 `23c440857a175a0674332b037d8acfedd550c2d060300cbad5b14a48acd5edaa`). Saved target: `docs/audit/ADS_NEW_CAMPAIGNS_READBACK_2026-11-11.json`. Current research identities were reconstructed from the accepted index chain; the selected ten are current and disjoint from the earlier 25 proposals and 20 held groups.

The prior 25 proposals and 20 held groups are preserved. Across the prior tranche and this tranche there are 34 proposed literals, plus this one new applicability hold; 13,965 current research identities have no proposal or this hold from these two tranches. This does not close G027. Full positive/protected-library conflict clearance is still G028 work. G029 exclusion review/approval and release/application remain separate and false. Ads stay paused and production is unchanged.

The separately reproduced structured-CSV parser defect and held current-entrypoint correction with the historical research core restored exactly are recorded in [the local parser parity receipt](NEGATIVE_CSV_PARSER_PARITY_2026-11-19.json). Its synthetic tests do not approve any real exclusion.

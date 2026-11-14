# Creative preparation evidence validator

This offline Python module checks a supplied creative preparation library against independently supplied native page/ad-group mappings, reviewed source commit, reviewer allowlist and asset inventory. It contains no provider client, uploader, serving configuration, account IDs or genuine creative inventory. Reports contain only counts, indexes and constant diagnostic codes; source copy, URLs and private review references are never echoed.

Master Plan section 12 requires preparing a control RSA and a distinct challenger for a documented experiment. It explicitly does not require simultaneous low-volume serving variants. This module checks the preparation pair only. The existing six serving-ad identities and one-RSA-per-group launch configuration are not changed. Activating an experiment or changing Ads requires separate authorization and exact serving-state acceptance.

## API and inputs

    evaluate_creatives(package, expected_groups, *, as_of, expected_commit,
                       authorized_reviewers, expected_assets=())

All timestamps use exact UTC seconds, for example 2026-11-10T12:00:00Z. The source commit must be 40 lowercase hexadecimal characters and must equal the caller's expected_commit. The function does not load Git or authenticate that commit: the caller must verify these supplied files are the reviewed source. Source commit labels cannot replace byte verification.

The package has exactly these fields:

- schema: bsre-creative-preparation-v1
- reviewed_commit: the exact reviewed source commit
- fixture_only: boolean provenance label; never a permission grant
- groups: complete expected preparation inventory

Each group has binding, claims, rsas and assets. A binding has exactly ad_group_key, campaign_key, landing_page_id, native_page_id, final_url, language and company_scope. It must equal its independently supplied expected_groups entry. URLs must be HTTPS without credentials, explicit ports or fragments. Language, destination, company scope and native identities match exactly. The module cannot prove that a supplied URL is a real native route or that the text is in the declared language; authenticate those facts independently.

Each group needs exactly one CONTROL and one CHALLENGER. Each RSA has rsa_id, role, binding, headlines, descriptions, path1, path2, experiment, copy_review and combination_review. Each text entry has text_id, text and a nonempty unique claim_ids list. The challenger has an experiment object containing reference, hypothesis and distinct_decision; the control's experiment is null. Reordered or recased copies do not constitute a distinct challenger. No semantic experiment quality or commercial effect is established.

Claims have claim_id, statement, source_reference, source_sha256 and review. Every copy entry must reference existing reviewed claims. Review subjects include exact text and claim-source bindings. Reviewers must come from the independently supplied authorized_reviewers allowlist; a package cannot authorize its own reviewer. Claim and review references remain in caller custody and are not opened by this module.

Every review receipt has decision, reviewer_id, reference, subject_sha256, observed_at_utc and valid_until_utc. PASS decisions must match the exact subject digest and satisfy observed_at <= as_of < valid_until. Missing, changed, expired or future receipts hold the library. Public helpers claim_subject, rsa_subject, combination_subject, asset_subject and digest define the exact subjects. The separate combination review binds the complete RSA, its experiment and reviewed claims with ALL_MATERIAL_COMBINATIONS coverage. It is evidence consistency, not a programmatic semantic assessment of every potential combination.

Copy and asset review observations must be at least as late as every claim review included in their subject. The immutable subjects include the complete group claim register, so the latest included claim review sets that floor. Combination review must also be at least as late as its copy review. Equal observation times are allowed; current validity alone cannot make a review that predates its dependencies acceptable.

Other assets have asset_id, kind, binding, destination, texts, source_reference, source_sha256, rights_reference and review. Supported kinds are SITELINK, CALLOUT, IMAGE, VIDEO, CALL, LOCATION and WHATSAPP. Each must match an independent expected_assets entry containing asset_id, kind, binding and destination. Empty or omitted expected assets cannot conceal assets present in the package, and omitted expected assets hold. Text assets require copy; source/rights references and an exact current review are required. Other format-specific lengths, image dimensions, video policy, staffed calls, WhatsApp functionality, inherited associations and actual rights require independent acceptance. This module does not implement their platform rules or infer them from a flag, URL or hash.

## Character and duplicate rules

Official Google documentation was checked on 10 November 2026:

- [Create responsive search ads](https://developers.google.com/google-ads/api/docs/responsive-search-ads/create-responsive-search-ads): 3–15 unique headlines of up to 30 characters; 2–4 unique descriptions of up to 90; optional display paths up to 15 each, with path2 requiring path1.
- [About responsive search ads](https://support.google.com/google-ads/answer/7684791?hl=en): double-width characters count twice.

The local counter uses Unicode East Asian Width W/F as two units and other supported characters as one. It is not UTF-8 bytes or UTF-16 code units. Combining marks, ambiguous-width characters, emoji/symbol sequences, controls, invisible characters and non-ASCII whitespace are held for an authoritative rendering/platform check instead of guessing their count. Straightforward Chinese/Japanese/Korean wide letters and full-width letters are supported. This deliberately holds some otherwise legitimate multilingual copy; it does not claim complete Google counting equivalence. Normalized NFKC/casefold/whitespace duplicates within each headline or description list hold. Text IDs must also be unique within an RSA.

Repeated normalized copy for the same other-asset kind in a group also holds even when it has a different asset ID or destination. For media-only assets, repeated source hashes of the same kind hold within a group. Reusing a reviewed asset in a different group is separately scoped by its independent inventory; this check does not infer a prohibited global duplicate.

Dynamic keyword insertion, customizers, countdown/location templates, pinning and unknown fields are unsupported and held. Expanded values and pinned position coverage need their own reviewed implementation; a short template does not demonstrate a valid expanded ad. The module does not request an Ads API validation call or claim Google policy approval.

## Result and focused verification

PASS means the supplied preparation library and current review bindings are structurally consistent. source_truth_verified, rights_verified, permission_granted, execution_authorized, serving_inventory_verified and production_ready always remain false, even on PASS. A named reviewer, reference or matching hash does not establish factual truth, actual approval, intellectual-property rights or delivery permission. Keep genuine evidence private and separately authenticated.

Run the focused synthetic suite from this directory:

    python -B -m unittest -v test_creative_validation.py

The test fixture builder supplies wholly synthetic IDs, an example.invalid native URL, source hashes and review records. Do not promote those fixtures into real Ads assets, claims or acceptance evidence.

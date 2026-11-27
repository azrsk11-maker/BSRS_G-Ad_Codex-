# Five-market paused campaign batch

**Already applied24November2026. Do not upload this Add batch again.** [Actual IDs/statuses/budgets](APPLIED.json) record all five poolsPaused atAED2,500total average/day. The full account readback is24campaigns:21Paused/3Removed/0Enabled. New campaign settings, children and destinations remain unfinished.

This is a provider-native campaign CSV, separate from the keyword/RSA review CSVs. It changes only the retained UAE Buyers campaign budget toAED1,000 while keeping itPaused, and adds distinct Paused off-plan campaign shells for Germany350/France300/India500/Taiwan350. The five proposed average daily pools totalAED2,500. No old service/legacy campaign or resale group is enabled. The owner authorized this off-plan five-market scope; country weights are an operator proposal without invented economics.

Google native Preview returned5successful changes/0errors on24November2026. The downloaded result preserved all five Paused statuses and marked every row `# OK`. [Context](CONTEXT.json) binds exact33headers, input/output hashes and the account. Preview is not application, launch, platform/legal approval, language review or functioning destinations. No ads, keywords, lead records, contact data or final URLs are in this batch.

Only use the batch in account573-038-4686 after reviewing the exact current preview. This is a one-shot Add/Edit batch: after Apply, reconcile the provider result and actual campaign IDs before any further upload. Do not replay it or the historical generators. All four new Campaign IDs are deliberately blank before creation. Preserve the original reviewed bytes as evidence after application rather than editing them into a replay file.

`Max CPC Bid Limit for Target IS` remains blank: that field does not set the Maximize Clicks cap. Before serving, verify/set CPC20, geographic presence, AI Maxoff, GoogleSearchonly, positive adjustments0 and daily10:00–19:00Dubai coverage; resolve actual native pages, consent/privacy/contact/delivery and all applicable release gates. Original resale group204397706314 and every non-offplan/legacy campaign remain paused; Removed stays removed. No Source merge or greenCI itself authorizes activation.

## UAE child prelaunch verification

Run `python -B tools/offplan-lead-first/check_uae_readback.py /path/to/private-readback.json` on a fresh, reconciled `bsre.offplan.uae-child-readback.v1` projection. It compares all enabled and paused UAE off-plan keyword rows and the single RSA to the pinned review evidence, checks the explicit resale pause, and screens the observed direct, account-level and shared exclusions. A match validates the saved scope. Fresh browser evidence, independent review, and the wider release gates still control activation.

For an authorized UAE release, pin fresh all-campaign and exact-parent all-status ad-group readbacks at each stage. The child capture uses `bsre.offplan.uae-all-ad-group-readback.v1`, with the account, UTC time, `campaign_or_ad_group_changes` false, provider `view_total`, and `ad_groups` rows containing `campaign_id`, `ad_group_id` and `explicit_status`. Its `view` records the exact `campaign_id`, `ad_group_statuses` as `["Enabled", "Paused", "Removed"]`, and empty `other_filters`. Use the complete frozen paused settings capture as the reference.

```text
python -B tools/offplan-lead-first/check_uae_activation_scope.py staged CAMPAIGNS CAMPAIGNS_SHA256 CHILDREN CHILDREN_SHA256 --reference PAUSED_REFERENCE --reference-sha256 REFERENCE_SHA256 --not-before "YYYY-MM-DD HH:MM:SS UTC"
```

`staged` checks the paused parent and enabled off-plan group. `enabled` checks the single enabled parent and off-plan group. If scope deviates during an authorized release, pause the UAE parent first and confirm containment. `rollback` also validates restoration of the off-plan group to Paused. All three stages require the resale group explicitly Paused and exact remaining campaign identities and statuses. Save captures within the applicable stage window. This check confirms entity scope. Separate readbacks cover individual ads, keywords, budgets, settings and live serving.

## Five-market activation scope readback

The reviewed scope file uses schema `bsre.offplan.activation-scope.v1`, the exact `account_id`, and a `markets` object keyed by the market codes eligible for that run. Each selected entry records its `campaign_id` and list of `offplan_ad_group_ids`. Verify these identities against the approved review before using them. Supply the full UAE child capture described above for every run. Use the same capture fields with schema `bsre.offplan.all-ad-group-readback.v1` for other selected markets. Keep raw captures and file hashes private.

```text
python -B tools/offplan-lead-first/check_offplan_activation_scope.py staged CAMPAIGNS CAMPAIGNS_SHA256 --reference PAUSED_REFERENCE --reference-sha256 REFERENCE_SHA256 --scope REVIEWED_SCOPE --scope-sha256 SCOPE_SHA256 --children AE UAE_CHILDREN UAE_SHA256 --not-before "YYYY-MM-DD HH:MM:SS UTC"
```

Repeat `--children MARKET FILE SHA256` for each other selected market. Save the `staged` match receipt and use `--prior FILE --prior-sha256 SHA256` for `serving`. Use the staged or serving receipt to verify `rollback`. Keep the same scope and reference pins and start the new observation window after the previous capture. Pause affected parents promptly when containment is needed, then capture rollback evidence.

The verifier compares the complete account roster, the five fixed budget amounts, visible Search settings and exact enabled group scope. Its enabled daily total describes the configured amounts of the enabled parents. Action-time approvals, budget resource identities, ad and keyword review, native page and tracking acceptance, staff capacity, and actual serving use separate evidence.

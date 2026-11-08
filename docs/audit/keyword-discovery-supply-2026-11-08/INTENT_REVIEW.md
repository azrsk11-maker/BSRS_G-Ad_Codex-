# Seller and landlord discovery intent review

Preliminary full-phrase review of the 31 identities in the [pinned supplemental capture](capture.json). Exact source phrases and placement references remain in [overlap.json](overlap.json). The four original capture batches and their classifications are separate. Reassess the one overlapping phrase here on its own evidence.

| Disposition | Possible service | Required evidence before admission |
|---|---|---|
| 7 seller candidates | Dubai residential or commercial seller representation | Actual service remit, reviewed seller destination, and separate coverage for commercial property and agent representation. |
| 7 landlord candidates | Dubai residential or commercial landlord representation | Actual landlord service remit and reviewed destination. Verify tenant sourcing, landlord representation, and commercial letting scope separately. |
| 6 owner geography holds | Possible seller or landlord representation outside Dubai | Verify Sharjah or Abu Dhabi service coverage and jurisdiction-specific facts before mapping. |
| 8 buyer holds | Possible Sharjah residential purchase | Separate from owner demand. Verify coverage and inventory. Explicit freehold terms also need title and eligibility evidence. |
| 3 ambiguous agency holds | Agent search with unresolved party or intent | Review buyer, tenant and owner interpretations. An agency term alone cannot establish supply intent. |

## Seller candidates

- `sell my property dubai`
- `sell my apartment dubai`
- `sell my villa dubai`
- `list my property for sale dubai`
- `property selling agent dubai`
- `sell my house in dubai`
- `sell my commercial property dubai`

## Landlord candidates

- `rent out my property dubai`
- `rent out my apartment dubai`
- `rent out my villa dubai`
- `find tenants for my property dubai`
- `landlord letting agent dubai`
- `property letting services dubai`
- `lease my commercial property dubai`

## Owner geography holds

- `sell property sharjah`
- `sell my property abu dhabi`
- `list property for sale abu dhabi`
- `rent out property abu dhabi`
- `landlord agent abu dhabi`
- `property letting agent sharjah`

## Buyer holds

- `sharjah villa for sale`
- `sharjah property for sale`
- `apartments for sale in sharjah`
- `flats for sale in sharjah`
- `freehold villa for sale in sharjah`
- `sharjah house for sale`
- `sharjah freehold property for sale`
- `flat for sale in sharjah al nahda`

## Ambiguous agency holds

- `dubai estate agent`
- `rental agents dubai`
- `dubai letting agents`

Keep all property and agency phrases available for protected-intent review. This pass proposes zero negatives and adds zero entries to either reviewed master. Service coverage, current factual evidence, exact campaign and page ownership, and independent review are still required. Planner ideas and returned seed phrases establish observed vocabulary only.

## Destination and existing keyword cross-check

The [dated ad URL readback](../ACCOUNT_AD_URL_READBACK_2026-11-07.json) maps Sellers `204397706394` to `/enquire/sell/` and Landlords `204397706554` to `/enquire/let/`, both under Owners `24367388382`. The [campaign status receipt](../ADS_PAUSED_READBACK_2026-11-08.json) records Owners paused. Fresh public requests returned HTTP 200 and an enquiry form marker for both paths. This checks route availability. Commercial service and end-to-end form acceptance require separate evidence.

| Candidates | Existing keyword comparison and disposition |
|---|---|
| Sell my property, apartment or villa in Dubai, and list my property for sale in Dubai | Four literal identities already appear in the dated Sellers keyword export. Retain as existing placements in review. |
| Rent out my property, apartment or villa in Dubai | Three literal identities already appear in the dated Landlords keyword export. Retain as existing placements in review. |
| Property selling agent Dubai, sell my house in Dubai, landlord letting agent Dubai, property letting services Dubai | Four additional literal identities have close intent overlap with existing agent, house or listing coverage. Evaluate incremental coverage before proposing another placement. |
| Find tenants for my property Dubai | Verify that tenant sourcing is offered and covered by the landlord workflow. |
| Sell or lease my commercial property Dubai | Hold for an explicit commercial owner mandate and suitable form. The preserved intake validator accepts Apartment, Townhouse, Villa and Other / to discuss, and both current public pages lack an explicit Commercial option. |

The seven literal overlaps come from the [dated keyword URL readback](../KEYWORD_URL_READBACK_2026-11-07.json) after removing Ads match wrappers. This comparison provides no live matching or incremental-demand assurance. The historical campaign has two service-specific ad destinations. Its mapping to the future one-entry-per-campaign architecture remains a separate owner decision.

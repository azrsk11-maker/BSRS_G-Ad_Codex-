# Source-linked keyword triage workbench

The queue contains all7,705distinct normalized phrases and all8,778source occurrences from the four pinned8November Keyword Planner captures. Metrics stay in their original captures; the queue keeps original phrase forms and every source reference without selecting preferred estimates. `INTERNAL-` IDs are deterministic SHA256queue identities, never Google campaign/ad-group/conversion IDs.

2,340 actual observed phrases received preliminary Codex semantic proposals, not business admission:

| Queue state | Count |
|---|---:|
| Positive review needed |1,075|
| Held for ambiguity or evidence |1,240|
| Full-phrase exact-negative review needed |25|
| Not yet assessed |5,365|

Both reviewed masters remain0of14,000. No review/approval/deployment counter increases. Positive proposals retain all five inventory/service, language, landing-page, claims and intent/geography admission gates as NOT_VERIFIED. No primary campaign/page mapping, match type or availability/price/affiliation promise is manufactured.

## Semantic findings

Discovery batch is provenance, not intent. Owner seeds returned buyer and tenant phrases; commercial seeds returned furniture. Proposals are based on the actual text. Generic `rent in dubai` and `long term rent dubai` are held because the asset is unspecified; `dubai rental properties` is held because segment/role is unresolved. An independent source review caught their original over-narrow residential labels; all three were corrected before publication.

Named entities, portal comparisons, valuations, price/term aspirations, short stays, shared/virtual offices and mixed property segments remain held until appropriate entity/service/provider, rights/claims and business evidence exist. Holding a phrase is not rejection or exclusion. A query containing cheap can still have property-purchase intent. Business Bay and hotel/holiday property-for-sale wording must not be lost through generic account exclusions.

## Narrow negative proposals - not approved scopes

| Observed query | Semantic reason |
|---|---|
| used furniture for sale dubai | Explicit goods or shopping query; scope still requires review |
| furniture sale dubai | Explicit goods or shopping query; scope still requires review |
| old furniture for sale dubai | Explicit goods or shopping query; scope still requires review |
| old furniture for sale in dubai | Explicit goods or shopping query; scope still requires review |
| annual car lease dubai | Vehicle, not premises |
| 3 day shopping sale dubai | Explicit goods or shopping query; scope still requires review |
| dubai jewellery shop online | Explicit goods or shopping query; scope still requires review |
| dubai online mobile sale | Explicit goods or shopping query; scope still requires review |
| dubai shopping festival sale | Explicit goods or shopping query; scope still requires review |
| online bicycle shop dubai | Vehicle, not premises |
| used apple laptop for sale in dubai | Explicit goods or shopping query; scope still requires review |
| used sunglasses for sale in dubai | Explicit goods or shopping query; scope still requires review |
| best electronics to buy in dubai | Explicit goods or shopping query; scope still requires review |
| dubai international shopping online | Explicit goods or shopping query; scope still requires review |
| dubai super sale 2022 online shopping | Explicit goods or shopping query; scope still requires review |
| garments sale in dubai | Explicit goods or shopping query; scope still requires review |
| iphone 14 pro for sale dubai | Explicit goods or shopping query; scope still requires review |
| old mobile sale in dubai | Explicit goods or shopping query; scope still requires review |
| used clothes for sale in dubai | Explicit goods or shopping query; scope still requires review |
| best shop to buy gold in dubai | Explicit goods or shopping query; scope still requires review |
| buy cycle in dubai | Vehicle, not premises |
| buy gold online dubai | Explicit goods or shopping query; scope still requires review |
| dubai electronic shopping online | Explicit goods or shopping query; scope still requires review |
| dubai sale iphone | Explicit goods or shopping query; scope still requires review |
| used mini cooper for sale in dubai | Vehicle, not premises |

Only the FULL phrases are proposed as EXACT candidates. Each retains CAMPAIGN-only scope, an empty campaign-key list and approved=false. No account-wide/shared-list exclusion or real campaign identity is inferred. Actual applicable service/campaign scope, risk assessment and business approval remain required. There are no invented job/course variants to fill a quota.

The local conservative matcher compares each exact proposal with all7,705observed phrases and1,205proposed protected phrases. Each currently matches only its own observed phrase, with zero protected collisions. This bounded lexical result is NOT Google matching assurance, complete service coverage, an approved protected-query corpus or permission to exclude anything.

Nine deliberately unsafe BROAD hypotheses produce159protected collisions: affordable1, business55, cheap35, cheapest10, free7, holiday8, hotel41, party1 and serviced1. These are lexical match instances, not unique people or platform matching assurance. They remain illegitimate/unapproved hypotheses, never legitimate exclusion candidates.

## Expanded semantic batch

The second batch assessed750previously unassessed real phrases, with separate writers and read-only peer review. It added442positive-review and308held proposals, with zero new negative proposals. The parent corrected four standalone `2 bedroom for rent...` queries to HOLD: bedroom wording alone does not establish a whole dwelling rather than rooms/shared accommodation. All prior90phrase records were retained; the later affordability consistency correction is recorded below.

Selection was the first750normalized unassessed phrases in lexical order, not a representative sample, priority/demand ranking or new provider research. This concentrates the batch on one/two-bedroom searches and must not be treated as evidence that other services have been covered. Monthly/price/portal/unknown-transaction and uncertain asset cases remain held, not excluded. No generic term is promoted into the negative master. Parent and peer review are preliminary code/research QA, not independent human PR approval or business admission.

## Broader corpus batch

The third batch assessed1,500additional observed phrases across the remaining lexical range. Starting from the6,865sorted unassessed normalized keys, select index `floor(i * 6865 / 1500)` for `i=0..1499`, then distribute selected keys round-robin to three separately owned500-row batches. Every source phrase is preserved, with read-only peer review and parent consistency review. This deterministic spread is not random, representative service coverage, search priority or new provider discovery.

Fourteen generic promotion/entity/acronym phrases initially proposed as exact negatives were held because the sold asset was unresolved: city-center/mall promotions, DSF, Nayomi, summer/three-day sales and Max Fashion warehouse sale. No retailer/provider identity is inferred. Two commercial/industrial land phrases are held pending the supported asset taxonomy; residential land's hold reason now correctly acknowledges explicit residential purchase intent. `apartment to sell dubai` is held for buyer/owner-role ambiguity. Three held bedroom queries had their rental-only service mappings corrected to purchase possibilities or no transaction mapping as appropriate.

Four new cheap-property phrases and the earlier `cheap apartments for sale in dubai` are held consistently for affordability/offer evidence. Their explicit property demand stays protected; lower-budget demand is not rejected. This changes one earlier disposition, not its source text or provenance. All other prior phrase records are retained. After corrections the new batch contributes586positive-review,894held and20full-phrase exact-negative proposals. The earlier affordability correction moves one prior positive to HOLD. No phrase enters either reviewed master, no owning campaign is assumed, and no scope is approved.

## Reproduction and gates

`proposals.json` preserves the2,340explicit draft decisions and reasons. `workbench.json` contains the complete deduplicated source-linked queue and diagnostics. `verify_workbench.py` pins both artifacts, reloads the independently pinned public capture, rebuilds every row/ref/diagnostic and requires exact equality. Required CI executes this verifier plus eight focused compiler tests. It never reads private raw exports, edits reviewed masters, connects to Ads or produces an upload file.

```sh
python -B docs/audit/keyword-triage-2026-11-08/verify_workbench.py
python -B -m unittest discover -s tools/keyword-system -p test_triage_workbench.py
```

Next: finish semantic triage, gather the five factual admission reviews and verified campaign/page/scope ownership, and expand genuinely supported research families. Owner decisions1/2remain relevant; code review or merge is not production authorization. No mechanical phrase multiplication, fabricated stock/search volume or silent reinterpretation of provider bid estimates is acceptable.


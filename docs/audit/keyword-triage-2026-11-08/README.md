# Source-linked keyword triage workbench

The queue contains all7,705distinct normalized phrases and all8,778source occurrences from the four pinned8November Keyword Planner captures. Metrics stay in their original captures; the queue keeps original phrase forms and every source reference without selecting preferred estimates. `INTERNAL-` IDs are deterministic SHA256queue identities, never Google campaign/ad-group/conversion IDs.

840 actual observed phrases received preliminary Codex semantic proposals, not business admission:

| Queue state | Count |
|---|---:|
| Positive review needed |490|
| Held for ambiguity or evidence |345|
| Full-phrase exact-negative review needed |5|
| Not yet assessed |6,865|

Both reviewed masters remain0of14,000. No review/approval/deployment counter increases. Positive proposals retain all five inventory/service, language, landing-page, claims and intent/geography admission gates as NOT_VERIFIED. No primary campaign/page mapping, match type or availability/price/affiliation promise is manufactured.

## Semantic findings

Discovery batch is provenance, not intent. Owner seeds returned buyer and tenant phrases; commercial seeds returned furniture. Proposals are based on the actual text. Generic `rent in dubai` and `long term rent dubai` are held because the asset is unspecified; `dubai rental properties` is held because segment/role is unresolved. An independent source review caught their original over-narrow residential labels; all three were corrected before publication.

Named entities, portal comparisons, valuations, price/term aspirations, short stays, shared/virtual offices and mixed property segments remain held until appropriate entity/service/provider, rights/claims and business evidence exist. Holding a phrase is not rejection or exclusion. A query containing cheap can still have property-purchase intent. Business Bay and hotel/holiday property-for-sale wording must not be lost through generic account exclusions.

## Narrow negative proposals - not approved scopes

| Observed query | Semantic reason |
|---|---|
| annual car lease dubai | Vehicle lease, not property lease |
| used furniture for sale dubai | Goods, not premises |
| furniture sale dubai | Goods, not premises |
| old furniture for sale dubai | Goods, not premises |
| old furniture for sale in dubai | Goods, not premises |

Only the FULL phrases are proposed as EXACT candidates. Each retains CAMPAIGN-only scope, an empty campaign-key list and approved=false. No account-wide/shared-list exclusion or real campaign identity is inferred. Actual applicable service/campaign scope, risk assessment and business approval remain required. There are no invented job/course variants to fill a quota.

The local conservative matcher compares each exact proposal with all7,705observed phrases and519proposed protected phrases. Each currently matches only its own observed phrase, with zero protected collisions. This bounded lexical result is NOT Google matching assurance, complete service coverage, an approved protected-query corpus or permission to exclude anything.

Seven deliberately unsafe BROAD hypotheses produce39protected collisions: business18, cheap3, cheapest2, free2, holiday1, hotel12 and serviced1. These are lexical match instances, not a count of unique people or platform matching assurance. They remain illegitimate/unapproved hypotheses, never legitimate exclusion candidates.

## Expanded semantic batch

The second batch assessed750previously unassessed real phrases, with separate writers and read-only peer review. It added442positive-review and308held proposals, with zero new negative proposals. The parent corrected four standalone `2 bedroom for rent...` queries to HOLD: bedroom wording alone does not establish a whole dwelling rather than rooms/shared accommodation. All prior90proposals are retained.

Selection was the first750normalized unassessed phrases in lexical order, not a representative sample, priority/demand ranking or new provider research. This concentrates the batch on one/two-bedroom searches and must not be treated as evidence that other services have been covered. Monthly/price/portal/unknown-transaction and uncertain asset cases remain held, not excluded. No generic term is promoted into the negative master. Parent and peer review are preliminary code/research QA, not independent human PR approval or business admission.

## Reproduction and gates

`proposals.json` preserves the840explicit draft decisions and reasons. `workbench.json` contains the complete deduplicated source-linked queue and diagnostics. `verify_workbench.py` pins both artifacts, reloads the independently pinned public capture, rebuilds every row/ref/diagnostic and requires exact equality. Required CI executes this verifier plus eight focused compiler tests. It never reads private raw exports, edits reviewed masters, connects to Ads or produces an upload file.

```sh
python -B docs/audit/keyword-triage-2026-11-08/verify_workbench.py
python -B -m unittest discover -s tools/keyword-system -p test_triage_workbench.py
```

Next: finish semantic triage, gather the five factual admission reviews and verified campaign/page/scope ownership, and expand genuinely supported research families. Owner decisions1/2remain relevant; code review or merge is not production authorization. No mechanical phrase multiplication, fabricated stock/search volume or silent reinterpretation of provider bid estimates is acceptable.

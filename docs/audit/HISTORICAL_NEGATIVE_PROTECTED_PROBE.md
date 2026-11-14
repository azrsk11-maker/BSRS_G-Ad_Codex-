# Historical negative screening for the four paused campaigns

These are proposed protected-intent examples for reviewer discussion. They were constructed from the approved funnel roles, without search terms, search volume or inventory claims. They have no reviewer approval and do not populate either keyword master.

| Funnel | Proposed protected phrase |
| --- | --- |
| buyers/off-plan | off plan apartment in dubai near schools |
| buyers/off-plan | buy dubai off plan property with payment plan |
| buyers/resale | buy resale apartment near metro dubai |
| buyers/resale | ready apartment for sale dubai mortgage |
| owners/sell | real estate agent to sell my dubai apartment |
| owners/sell | sell my property in dubai while overseas |
| owners/let | find tenants for my dubai apartment |
| owners/let | real estate agent to let my dubai villa |
| tenants/rent | rent apartment dubai near my new job |
| tenants/rent | dubai apartment rental near work and metro |
| brand | black swan real estate dubai |
| brand | black swan real estate dubai property enquiry |

The 9 November offline screen compares the nine archived negative candidates against all 12 examples before assigning scope. The existing simulator uses the six original phrase negatives and three original exact negatives from [historical intake](../../tools/keyword-system/staging/historical-negative-intake.json). The 108 comparisons found zero lexical conflicts. As controls, all nine negatives matched their own literal text, and the three exact negatives did not match that text with an added word.

Keep all nine candidates pending. The review still needs the current campaign or ad-group scope, inherited negatives, legitimate long-tail coverage against the reviewed positive master, and independent sign-off. Treat any changed match type or scope as a new review. This screen provides no platform approval or coverage certificate.

## Campaign crosswalk for read-only reconciliation

| Archived campaign label | Paused Real Estate campaign ID | Historical placements |
| --- | --- | ---: |
| BSRE_SEARCH_BUYERS_EN | 24372566774 | 6 phrase |
| BSRE_SEARCH_OWNERS_EN | 24367388382 | 6 phrase |
| BSRE_SEARCH_TENANTS_EN | 24378494092 | 6 phrase |
| BSRE_SEARCH_BRAND_EN | 24378494098 | 6 phrase, 3 exact |

The proposed crosswalk uses the historical service labels and the [paused campaign readback](ADS_PAUSED_READBACK_2026-11-08.json) for account 573-038-4686. The [inspected export summary](../PROGRESS.md) separately records 19 existing V2 exclusions, with four employment phrases per campaign and three exact Brand exclusions. It also records a 29-negative shared list attached only to six older campaigns in that export.

## Exact comparison against the saved 7 November export

The original private export matched the SHA-256 and 1,191-row count in the [targeting and negative readback](TARGETING_NEGATIVE_READBACK_2026-11-07.json). The report carries campaign names, which were joined to IDs using that readback. Comparing campaign, match type and unwrapped keyword text confirmed that all 19 exported V2 campaign exclusions are among the 27 archived placements.

The eight placements absent at the direct campaign level in that export are the phrase negatives **real estate interview questions** and **real estate vacancies**, each across all four campaigns. This is dated evidence. Recheck these eight placements and any account or manager exclusions before considering a change. Preserve all 19 observed exclusions during review. No candidates were approved or applied.

## Legacy shared-list counterexamples

The 29 broad exclusions from the saved readback produced zero matches against the initial 12 examples. A second screen used ordinary property and brand searches that contain terms from the list. The same simulator found seven matches across six searches in 174 comparisons.

| Funnel | Proposed protected search | Simulated broad exclusions |
| --- | --- | --- |
| Off-plan | buy off plan studio apartment in dubai | studio |
| Resale | buy resale studio in dubai near metro | studio |
| Sellers | sell my studio apartment in dubai | studio |
| Landlords | let my studio apartment in dubai | studio |
| Tenants | dubai rental studio near me | studio, near me |
| Brand | black swan real estate company dubai | company |

These are constructed examples, with no inventory or volume claims. The list had no V2 attachment in the saved export. The lexical counterexamples support holding any V2 reuse of the legacy list pending review of individual terms and their scopes. Live Google matching and current attachments require separate verification.

## Screening against observed Planner phrases

The existing matcher found **zero lexical conflicts in 5,130 comparisons** between the nine archived exclusions and the 570 distinct observed Planner phrases with a nonempty protected-intent flag in the [triage corpus](keyword-triage-2026-11-08/proposals.json). All nine own-text controls matched. The remaining 7,135 proposal rows were outside this screen. Campaign and ad-group scope remain unassigned, and independent review and coverage against the full reviewed positive library are still required. No exclusion was approved or applied.

## Full observed-corpus cross-check

The nine archived exclusions returned zero lexical matches against all 7,705 distinct Planner proposal phrases (69,345 comparisons), including the 570 provisionally protected phrases above. A separate local screen of the pinned October Search terms source returned zero lexical matches across its 3,691 disclosed distinct identities (33,219 comparisons). Only aggregate results are recorded here. The corpora overlap and their counts describe separate screens.

The narrow 570-phrase check is now reproduced by Foundation validation. On commit `a2052b3`, [Foundation validation](https://github.com/azrsk11-maker/BSRS_G-Ad_Codex-/actions/runs/42563114204) and the [isolated WordPress lab](https://github.com/azrsk11-maker/BSRS_G-Ad_Codex-/actions/runs/42563114213) passed. Neither expanded screen establishes effectiveness, current scope, or Google matching. The saved report omits undisclosed queries and covers one historical period. The nine candidates remain on hold pending scoped review.

# Property decision tools — native WordPress integration candidate

Master Plan §9 requires ten reusable tools that provide a useful result before requesting contact details. This directory implements all ten with user-entered figures, deterministic arithmetic and a native shortcode. It contains no property inventory, quoted tariffs, tax rules, financing approval, expected market returns, production identifiers or business claims. All inputs start blank; entering zero is an explicit assumption.

`engine.js` performs the arithmetic. `ui.js` provides the labelled forms, editable off-plan milestones, result breakdowns and model assumptions. `property-decision-tools.php` is an inactive-by-default WordPress integration candidate. `tools.css` is scoped to its rendered section. There are no dependencies or build step.

## Working models

All monetary amounts are AED. A different currency must not be mixed into these scenarios. Fees, taxes, operating costs and sale costs must be entered by the user where applicable; no jurisdiction-specific rate is implied.

| Tool ID | Calculation and boundaries |
| --- | --- |
| `net_yield` | Gross yield = scheduled annual rent / purchase price. Rent after vacancy = annual rent × (1 − vacancy percentage). Net income = rent after vacancy − annual operating costs. Net yield = net income / (purchase price + additional acquisition costs). No financing, tax or capital growth. |
| `cash_needed` | Completion cash = price − entered borrowing + nonrefundable costs + refundable deposits. Available cash target adds a separately retained reserve. Deposits and reserves are not labelled expenses. |
| `rent_buy` | Initial equity + buying costs + monthly loan payments × months + prorated running costs − expected sale equity. Sale equity = assumed sale price − remaining loan balance − selling costs. Compare with rent × months + total nonrefundable rental costs. Principal is represented through payments and exit equity, without treating the entire purchase price as an additional financed expense. This is an undiscounted cash comparison with no assumed appreciation or opportunity return. |
| `offplan_cashflow` | 1–24 user-entered payment milestones must total exactly 100%. Payments are sorted by elapsed month. Cumulative percentage allocation conserves every cent of the price. Balance = starting cash + monthly saving × elapsed months − upfront costs − cumulative price paid. Report the largest funding shortfall, including month-zero upfront costs. Savings are available before that month’s payments. No lending, income, savings interest or delays are inferred. |
| `ready_offplan` | For each cash-purchase scenario: assumed sale price − purchase price − acquisition costs − sale costs + prorated net rental income. Ready income runs for the whole entered horizon; off-plan income starts after the entered handover month. Negative net annual rental income is supported. Compare hypothetical results and show the minimum non-negative off-plan exit value needed to match or exceed the ready scenario. A pre-handover exit is a scenario assumption, not an assignment permission. |
| `rental_movein` | Immediate cash = actual first rent payment + refundable security/utility deposits + nonrefundable fees + moving costs. First-year expense = full annual rent + fees + moving costs; deposits are excluded. No standard deposit or cheque count is assumed. |
| `occupancy_cost` | Annual recurring cost = entered rent + service + utilities + insurance + other costs. First-year cash adds fit-out and deposit. Horizon cost = recurring × years + fit-out, excluding refundable deposits. Effective annual cost spreads fit-out evenly; divide by entered square metres for per-area cost. No residual value, escalation or discounting. |
| `office_fit` | Planning area = (people × desk area + shared area) × (1 + circulation allowance), rounded upwards to 0.01 m². Capacity is the whole number of desks fitting after shared area and the same allowance. Use comparable usable areas in m². This is not legal occupancy, fire, zoning or access advice. |
| `seller_proceeds` | Sale price − loan payoff − entered percentage-based selling fee − other selling costs. Negative proceeds are retained as a cash shortfall. Sale proceeds are not profit or company commission revenue. |
| `landlord_vacancy` | Rent received = full-year rent × (12 − vacant months) / 12. Net annual cash deducts fixed costs and one year’s letting costs. Refundable tenant deposits are shown separately as money held, never rent or profit. |

Costs that a model expressly excludes must not be assumed zero in a real decision. Comparison sale values and handover dates are visibly labelled assumptions. No tool chooses a property or recommends a financing product.

## Exact arithmetic and accessible behavior

- Parse decimal strings directly into integer cents or hundredths of a unit. Monetary multiplication, percentages and prorating use `BigInt`; results use deterministic half-up rounding, including losses. No floating-point accumulation of money occurs.
- Individual monetary inputs are bounded at AED 1 billion. Rates are 0–100%; vacancy months are 0–12; horizons are 1–600 months or 1–50 years. Net annual rental income in the ready/off-plan model also accepts losses down to AED −1 billion. Output conversion checks the safe-integer range.
- Reject separators, exponent notation, non-finite values, excess decimal places and missing inputs instead of silently coercing them. Borrowing cannot exceed purchase price in these models. A positive denominator is required for yields and per-area figures.
- Each input has an explicit label and format/limit hint. Fieldsets, keyboard controls, alert text, focused results, responsive result lists and a horizontally scrollable table support interaction. Multiple shortcode mounts have distinct IDs.
- Editing a figure, adding/removing a milestone, clearing or changing the tool discards earlier results. Native required-field rejection also clears results so an old scenario cannot remain visible beside different inputs. Cross-field error markers clear together when the scenario changes.
- Results and errors use text nodes, not HTML interpolation. No names, phone numbers or email addresses are requested. The forms have no submission names or action URL and are created only after their local event handlers are attached.

## Privacy and measurement

The engine/UI make no network calls and use no cookies, persistent storage, analytics queues, pixels, telemetry or conversion events. The optional `calculator_complete` hook is deliberately **not implemented**: the page’s reviewed consent and identity path must be integrated separately before any diagnostic measurement is considered. Calculation remains usable without measurement consent.

Inputs exist only in the current page’s memory/DOM. The clear button removes them from this tool’s form. This cannot promise erasure from browser extensions, screenshots, back/forward snapshots or unrelated scripts on an eventual host page. Before production integration, verify the actual site’s session replay, form analytics, consent boundaries, caching, content security policy and asset loading. These candidate files do not configure any of those services.

## Native integration

This is preparation within the approved isolated test lab. Installing, enabling or adding content to production still needs its own exact reviewed authorization.

In the synthetic lab, copy this directory to the existing WordPress plugin directory as `bsre-property-decision-tools/`. Set the explicit server-side integration constant `BSRE_PROPERTY_DECISION_TOOLS_ENABLED` to Boolean `true` before loading the plugin. Activate/include the candidate through the approved integration workflow. Without that constant the plugin registers no hooks or shortcode and enqueues no assets. Query parameters and shortcode attributes cannot enable it.

Use a native Shortcode block in a reviewed page:

```text
[bsre_property_decision_tools]
[bsre_property_decision_tools tool="rental_movein"]
```

The first presents the ten-tool selector; the second presents one tool. Other supported IDs appear in the model table. Unknown IDs produce no mount/assets. The shortcode enqueues only its own same-site stylesheet and two scripts, with the UI depending on the engine. It creates no pages, settings, endpoints, posts, schedules or lead records and does not alter existing forms or measurement. Native editor, theme, crawler/noindex and actual mobile/assistive-technology acceptance remain required for the chosen campaign page.

## Verification

```sh
node --test tools/property-decision-tools/engine.test.cjs tools/property-decision-tools/ui.test.cjs
php -n tools/property-decision-tools/php.test.php
php -n -l tools/property-decision-tools/property-decision-tools.php
```

Engine tests exercise independently calculated financial examples for all ten tools, refund/principal distinctions, losses, unit conversion, exact payment conservation, peak funding needs, invalid inputs and maximum-value bounds. UI tests execute the actual client handlers in a small DOM/event double, including native-invalid capture, stale-result removal, milestone changes, keyboard focus and zero transmission. The PHP contract uses local WordPress doubles.

`native-wordpress-test.php` must run only in the existing isolated synthetic WordPress lab **after** the WordPress installation phase, with the candidate copied into the actual synthetic plugin folder. Before loading WordPress it requires the lab CLI, non-root process, loopback-only interfaces and empty route table. Outer CI kernel isolation remains mandatory; these guards do not create isolation. It then loads actual WordPress and exercises disabled/default state, shortcode parsing for all ten tools, unique accessibility mounts, local asset URLs/dependencies, no inline measurement, no HTTP calls and zero SQL writes. It also rejects other database/origin configurations. This harness is provided for native CI; local double tests do not establish that it passed. No native browser, Google, production, legal review or market-data acceptance is claimed.

Rollback before deployment is removal of these local candidate files. For an authorized integration, remove the page’s shortcode and disable the integration constant/plugin; this tool has no persisted scenario data or owned records to restore. Preserve all unrelated page revisions, site configuration and enquiry records.

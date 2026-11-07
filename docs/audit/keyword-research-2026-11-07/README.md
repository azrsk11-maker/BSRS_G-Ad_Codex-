# Authentic Keyword Planner research capture

On 7 November 2026, the authenticated Real Estate account `573-038-4686` submitted all **41 original historical phrases** to Google Keyword Planner's **Get search volume and forecasts** tool. The downloaded historical statistics contain **37 keyword rows**, all exact canonical matches to submitted phrases, plus two aggregate rows. This adds **zero reviewed, approved or deployed keywords**. The historical intake and empty reviewed masters remain unchanged.

Google automatically created non-serving research plan `1444037307`. **Create campaign was not used**; no live campaign setting, budget or advertising activation was changed by this capture.

## Observed context

| Setting | Observation |
|---|---|
| Location | United Arab Emirates |
| Network display | Google |
| Language display | **All languages**, disabled control; English-only research is not verified |
| Historical period | **1 October 2025–30 September 2026**, matching the CSV date header |
| UI observation | 7 November 2026, 07:22–07:23 UTC; minute precision |
| Currency in keyword rows | AED |

These are the Planner research settings, not a claim about live campaign language or targeting. No restriction to English should be inferred from English input phrases.

## Evidence and public projection

[capture.json](capture.json) records context, the public metric projection, all 41 input identities and the exact-match reconciliation. The original private download is **not committed**. It is a 6,708-byte UTF-16 tab-delimited export, despite its `.csv` extension:

- Original basename: `Keyword Stats 2026-11-07 at 11_23_21.csv`
- Original SHA256: `9fad4616519cecd7756e3f32afc26172251d1f78cb117721160683652525e923`
- Historical intake SHA256: `2fb4fc05496184628c6cab7e900f4bf4c62426e0a84f8c8f9c73302f3f76308e`

The projection excludes these four account-specific columns in their entirety: **Ad impression share**, **Organic average position**, **Organic impression share**, and **In Account**. It also excludes the numeric contents of the two non-keyword aggregate records at source lines 4 and 5 (`All` and `United Arab Emirates`). All 37 retained keyword records preserve the other 22 column labels exactly, including the twelve monthly labels. Empty cells become JSON `null`; other values remain the exact exported strings, with no rounding or numeric reinterpretation. No prospect, transaction, financial-performance or contact record is included.

Historical platform estimates are not actual Black Swan campaign results or first-party customer search queries. The low/high top-of-page bid estimates remain under their own labels; they are not relabeled as actual CPC. Do not sum these rows into unique demand, leads, qualifications or revenue. Source freshness expiry, business fit, inventory/service evidence, current campaign/page mapping and the five admission reviews remain unresolved.

## Four inputs without a separate exact export row

| Historical candidate | Submitted phrase |
|---|---|
| `LEGACY-POS-0003` | blackswan real estate |
| `LEGACY-POS-0024` | apartments for rent dubai |
| `LEGACY-POS-0026` | villas for rent dubai |
| `LEGACY-POS-0028` | dubai rental properties |

No authoritative grouping evidence was obtained. Their `grouped_under` values remain `null`; no metric from another row is assigned to them. Missing separate rows do not mean zero demand. No unrequested keyword appears among the 37 returned rows.

## Reproduce the verification

From this directory, with Python 3:

```sh
python -B verify_capture.py
python -B verify_capture.py --raw-export '<private original downloaded CSV>'
```

The first command checks committed projection structure, field exclusions, source locators, digests and reconciliation against the pinned historical intake. It reports **PUBLIC_PROJECTION_CONSISTENCY_ONLY** and `private_source_verified: false`. It cannot establish original metric authenticity without the private file.

The second reads the private export once, requires its exact pinned bytes, reprojects/reconciles it and compares the result with the committed capture. It reports **SOURCE_BYTES_AND_PUBLIC_PROJECTION**. The verifier is read-only: no API, master changes, source-file edits, forecast creation, deployment or upload is available. Internal digests establish consistency; they are not reviewer authentication or production permission.

Both verification modes were exercised against this capture. Bounded checks also reject a changed source byte, a changed retained metric, a changed input mapping and a leaked excluded column; a synthetic sentinel in all four excluded columns never enters the public projection. The capture and pinned intake use strict JSON parsing: duplicate keys cannot conceal an excluded field behind a later replacement, and non-finite numeric constants are rejected. The duplicate-projection failure identified in peer review has a passing focused rejection check. These checks concern this actual capture only, not a new general import framework.

# Asset association configuration audit

[capture.json](capture.json) preserves all 17 account-level associations and all 114 associations belonging to the four V2 campaign IDs. It contains configuration only. The complete 1,452-row CSV remains private; the other 1,321 rows are represented only by counts. No live serving configuration or website setting was changed. Report view filters/columns were adjusted for this read-only audit.

## Source and selection

- Account: `573-038-4686`, authenticated Real Estate account.
- Source basename: `Asset association report.csv`.
- Source size: **265,808 bytes**.
- Source SHA256: `7a6a3afe26609b996d8e62afa4f2c820420651ebe848aaa2578e32f3945065ef`.
- UI view: All campaigns; Asset status **Enabled, Paused**; Asset type **All**; all five association levels.
- Export date preamble: **31 October–6 November 2026**. This is report-selector metadata, not campaign performance or proof of status throughout that period. The readback date is 7 November; an exact observation time is not asserted.

The 14 exported columns are preserved without renaming: `Asset status`, `Asset`, `Asset type`, `Level`, `Status`, `Status reason`, `Added by`, `Last updated`, `Item ID`, `Campaign ID`, `Ad group ID`, `Policy details`, `Campaign`, `Ad group`.

Every retained configuration value is the original string, including blank strings, multiline asset text, narrow spaces and placeholder status reasons. `source_record` is the one-based logical CSV data-record position after the header, not a physical line number. There are no performance columns, prospect responses, phone numbers, email addresses or private machine paths in the retained projection. No records were silently deduplicated.

| Exported level | Source rows | Retained rows |
|---|---:|---:|
| Account | 17 | 17 |
| Campaign | 206 | 0 |
| Ad | 1,165 | 114 V2 |
| Asset group | 63 | 0 |
| Ad group | 1 | 0 |
| **Total** | **1,452** | **131** |

V2 selection uses exact campaign-ID membership from the existing campaign baseline, followed by exact campaign-name verification. The baseline file and its checksum are recorded in the capture. No ad IDs are inferred from component IDs.

## Account associations

All **17** have `Asset status: Paused`, `Status: Paused`, and `Status reason: Paused`; all were added by **Advertiser**. They comprise **15 sitelinks, one lead form and one business logo**.

Every sitelink contains `https://lplife.blackswanrealestate.ae/` within its multiline **Asset** cell. Although the CSV has no dedicated Final URL column, it does contain these URL strings. Their presence does not verify redirects, current effective routing or native-page acceptance. Repeated sitelink copy has different Item IDs: About Us ×5, Contact Black Swan ×5, Dubai Property Investment ×4 and Buy Property ×1. These are distinct exported associations, not duplicate rows.

The paused lead form is **Buy Property in Dubai**, Item ID `424492800514`. Its privacy terms, questions, delivery destination and lead-ID reconciliation are not exposed here. The logo is Item ID `409031914620`; its exported image URL is preserved, without claiming rights or business approval. Paused account assets are not described as active V2 inheritance.

## V2 component associations

All **114** are **Ad-level** associations added by **Advertiser**: **90 headlines and 24 descriptions**. Each shows `Asset status: Enabled` and `Status: Not eligible`. Those are different status dimensions; **Enabled components do not establish that an ad serves**. The reason field is literally ` --; --; --`, so this export does not explain ineligibility. Empty Policy details do not establish policy approval.

| Campaign ID | Role | Ad-group sets | Components |
|---|---|---:|---:|
| `24372566774` | Buyers | 2 | 38 |
| `24367388382` | Owners | 2 | 38 |
| `24378494092` | Tenants | 1 | 19 |
| `24378494098` | Brand | 1 | 19 |

Each of the six ad-group sets has 15 headline and four description rows. This shape alone does **not** identify six RSAs or their ad IDs; the separate ad-table readback is required. There are **96 distinct Item IDs** across 114 rows, with no conflicting type/text for a reused Item ID and no exact duplicate retained rows. The complete source has 289 repeated full rows beyond their first occurrence, all in omitted scopes. Their cause cannot be established from this export, which lacks ad IDs; no duplicate-ad or duplicate-conversion conclusion follows.

## Method, verification and limits

The export was read as one immutable byte snapshot, checked against the supplied checksum, decoded with UTF-8 BOM handling, and parsed with Python's standard-library CSV reader. The preamble, unique 14-column header and all 1,452 record widths were checked. Exact campaign IDs selected V2; Account level selected the account subset. Every selected cell was retained, and scope/status/type/group/duplicate counts were recomputed. The original export was not modified or copied into the repository.

A bounded independent reconstruction compares all **131 × 14 retained cells** and logical source locators with the original download, then recomputes the summaries. No new parser framework, schema or permanent test module is introduced. Reproduction requires the private source for source authenticity; the committed JSON alone cannot authenticate its original values.

This observation does not verify phone staffing, WhatsApp delivery, hosted-form routing, image rights, claim accuracy, redirects, consent, tracking, auto-created-asset settings or manager controls. It contains no actual ad Final URL field and cannot replace the separate detailed ad/URL readback. Production release remains a separate action with its existing acceptance and authorization gates.

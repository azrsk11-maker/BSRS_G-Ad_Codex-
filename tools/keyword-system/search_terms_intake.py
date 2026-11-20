"""Private, bounded intake of the October 2026 historical Search terms report.

Only query and placement context leave the raw reader. Performance, financial
and conversion cells are discarded, without interpretation or aggregation.
Heuristic flags never establish that an unflagged record is safe to disclose.
"""
from __future__ import annotations

from collections import Counter
import csv
import hashlib
import io
from pathlib import Path
import re
import unicodedata

from keyword_audit import normalize

MAX_BYTES = 16 * 1024 * 1024
MAX_ROWS = 20_000
TITLE = "Search terms report"
DATE_HEADER = "October 1, 2026 - October 31, 2026"
COLUMNS = ("Search term", "Match type", "Added/Excluded", "Campaign", "Ad group",
           "Clicks", "Impr.", "CTR", "Currency code", "Avg. CPC", "Cost",
           "Campaign type", "Conv. rate", "Conversions", "Cost / conv.")
FOOTERS = ("Total: Search terms", "Total: Other search terms", "Total: Account",
           "Total: Search", "Total: Performance Max")
PLACEMENT_COLUMNS = ("Match type", "Added/Excluded", "Campaign", "Ad group", "Campaign type")
AUTHORITIES = {"public_disclosure_authorized": False, "deployment_authorized": False,
               "negative_authorized": False, "qualification_authorized": False}


def _need(ok, code):
    if not ok:
        raise ValueError(code)


def _blank(value):
    return value.strip() in {"", "--"}


def _privacy_flags(values):
    """Flag obvious candidates across retained cells; deliberately not a DLP gate."""
    flags = set()
    for value in values:
        if re.search(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            flags.add("email_candidate")
        if any(sum(c.isdigit() for c in m.group()) >= 7 for m in
               re.finditer(r"(?<!\w)\+?\d[\d\s().-]{5,}\d(?!\w)", value)):
            flags.add("phone_candidate")
        if re.search(r"(?:https?://|www\.|\b(?:[a-z0-9-]+\.)+[a-z]{2,63}\b)", value, re.I):
            flags.add("url_candidate")
        if re.search(r"\b(?:api[_ -]?key|token|secret|password)\s*[:=]\s*\S+|"
                     r"\b(?:sk-|ghp_|github_pat_|AKIA)[A-Za-z0-9_-]{12,}\b|"
                     r"\b[A-Za-z0-9_-]{32,}\b", value, re.I):
            flags.add("token_candidate")
        if any(unicodedata.category(c).startswith("C") for c in value):
            flags.add("control_character_candidate")
        if value.lstrip().startswith(("=", "+", "-", "@")) and not _blank(value):
            flags.add("spreadsheet_formula_candidate")
    return sorted(flags)


def parse_search_terms(path) -> dict:
    """Return a PRIVATE projection and count-only summary; never write or connect.

    Accept UTF-8 with an optional BOM and the exact dated, 15-column report.
    Source lines are one-based physical CSV starting lines, including quoted
    multiline records. Blank ad groups are retained for placements such as
    Performance Max, without inferring their campaign type or qualification.

    Raw/normalized repeated counts measure query occurrences beyond the first;
    Duplicate placement rows use exact query plus ALL retained placement cells
    (match, added/excluded, campaign, group, type). Repeated query/campaign/group
    contexts ignore match, added/excluded and type differences. Campaign/group
    labels are report strings, never resource identities; duplicate resource
    names cannot be disambiguated by this source. Blank-group pairs are counted
    separately from nonblank pairs, retaining distinct literal empty/-- labels.
    """
    try:
        with Path(path).open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
    except OSError:
        raise ValueError("SEARCH_TERMS_SOURCE_UNREADABLE") from None
    _need(len(raw) <= MAX_BYTES, "SEARCH_TERMS_BYTE_LIMIT")
    try:
        decoded = raw.decode("utf-8-sig", errors="strict")
    except UnicodeError:
        raise ValueError("SEARCH_TERMS_ENCODING") from None
    reader = csv.reader(io.StringIO(decoded, newline=""), delimiter=",", strict=True)
    records, footer_counts = [], Counter()
    row_count = 0
    try:
        _need(next(reader) == [TITLE], "SEARCH_TERMS_TITLE")
        _need(next(reader) == [DATE_HEADER], "SEARCH_TERMS_DATE")
        _need(next(reader) == list(COLUMNS), "SEARCH_TERMS_COLUMNS")
        while True:
            source_line = reader.line_num + 1
            row = next(reader, None)
            if row is None:
                break
            row_count += 1
            _need(row_count <= MAX_ROWS, "SEARCH_TERMS_ROW_LIMIT")
            _need(len(row) == len(COLUMNS), "SEARCH_TERMS_ROW_WIDTH")
            term, match, added, campaign, ad_group = row[:5]
            placement_empty = all(_blank(v) for v in row[1:5])
            if term in FOOTERS and placement_empty:
                footer_counts[term] += 1
                _need(footer_counts[term] == 1, "SEARCH_TERMS_DUPLICATE_FOOTER")
                continue
            # Exact known-label collisions are genuine terms when placement
            # fields establish a real row. Unknown total-like rows fail closed.
            aggregate_like = re.match(r"\s*totals?\s*:", term, re.I) is not None
            _need(not aggregate_like or term in FOOTERS, "SEARCH_TERMS_UNKNOWN_AGGREGATE")
            _need(bool(term.strip()) and bool(normalize(term)), "SEARCH_TERMS_EMPTY_QUERY")
            _need(not _blank(match) and not _blank(added) and not _blank(campaign)
                  and not _blank(row[11]), "SEARCH_TERMS_PLACEMENT")
            placement = dict(zip(PLACEMENT_COLUMNS, (match, added, campaign, ad_group, row[11])))
            records.append({"source_line": source_line, "search_term": term,
                "normalized_search_term": normalize(term), "placement": placement,
                "privacy_flags": _privacy_flags([term, *placement.values()]),
                "manual_disclosure_review_required": True, **AUTHORITIES})
    except (csv.Error, StopIteration):
        raise ValueError("SEARCH_TERMS_CSV_STRUCTURE") from None
    raw_terms = {r["search_term"] for r in records}
    identities = {r["normalized_search_term"] for r in records}
    placement_ids = {(r["search_term"], *r["placement"].values()) for r in records}
    query_contexts = {(r["search_term"], r["placement"]["Campaign"], r["placement"]["Ad group"])
                      for r in records}
    campaigns = {r["placement"]["Campaign"] for r in records}
    all_pairs = {(r["placement"]["Campaign"], r["placement"]["Ad group"]) for r in records}
    ad_groups = {(r["placement"]["Campaign"], r["placement"]["Ad group"])
                 for r in records if not _blank(r["placement"]["Ad group"])}
    group_labels = {r["placement"]["Ad group"] for r in records if not _blank(r["placement"]["Ad group"])}
    summary = {"source_rows": row_count, "query_placement_rows": len(records),
        "distinct_raw_search_terms": len(raw_terms),
        "distinct_normalized_search_terms": len(identities),
        "repeated_raw_query_occurrences": len(records) - len(raw_terms),
        "repeated_normalized_query_occurrences": len(records) - len(identities),
        "duplicate_query_placement_rows": len(records) - len(placement_ids),
        "repeated_query_campaign_ad_group_context_rows": len(records) - len(query_contexts),
        "distinct_campaign_labels": len(campaigns),
        "distinct_nonblank_campaign_ad_group_label_pairs": len(ad_groups),
        "distinct_campaign_ad_group_label_pairs_including_blank": len(all_pairs),
        "distinct_nonblank_ad_group_labels": len(group_labels),
        "blank_ad_group_rows": sum(_blank(r["placement"]["Ad group"]) for r in records),
        "footer_rows": sum(footer_counts.values()),
        "footer_counts": {label: footer_counts[label] for label in FOOTERS},
        "privacy_flagged_records": sum(bool(r["privacy_flags"]) for r in records),
        "manual_disclosure_review_required_records": len(records)}
    return {"scope": "PRIVATE_HISTORICAL_SEARCH_TERMS_INTAKE",
        "source_sha256": hashlib.sha256(raw).hexdigest(), "source_bytes": len(raw),
        "encoding": "utf-8-sig", "report_title": TITLE, "date_header": DATE_HEADER,
        "records": records, "summary": summary,
        "controls": {**AUTHORITIES, "all_records_require_manual_disclosure_review": True,
                     "unflagged_records_are_not_verified_safe": True,
                     "performance_financial_conversion_cells_retained": False}}

"""Bounded offline projection of Keyword Planner Discovery UTF-16 TSV exports.

Metric strings are provider historical estimates, not actual performance or CPC.
Account-specific fields are discarded. Parsing supplies no review, approval,
campaign mapping or deployment authority, and never writes the source or output.
"""
from __future__ import annotations

import argparse
import calendar
import csv
from datetime import date
import hashlib
import io
import json
from pathlib import Path
import re
import unicodedata

MAX_BYTES = 16 * 1024 * 1024
MAX_RECORDS = 20_000
BASE_COLUMNS = (
    "Keyword", "Currency", "Avg. monthly searches", "Three month change",
    "YoY change", "Competition", "Competition (indexed value)",
    "Top of page bid (low range)", "Top of page bid (high range)",
    "Ad impression share", "Organic impression share", "Organic average position",
    "In account?", "In plan?",
)
EXCLUDED_COLUMNS = frozenset((
    "Ad impression share", "Organic impression share", "Organic average position",
    "In account?", "In plan?",
))
MONTHS = ("January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December")
MONTH_ABBREVIATIONS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug",
                       "Sep", "Oct", "Nov", "Dec")


def _monthly_columns(header):
    match = re.fullmatch(r"([A-Za-z]+) ([1-9][0-9]?), ([0-9]{4}) - "
                         r"([A-Za-z]+) ([1-9][0-9]?), ([0-9]{4})", header)
    if not match:
        raise ValueError("Invalid Discovery date header")
    try:
        sm, sd, sy, em, ed, ey = match.groups()
        start = date(int(sy), MONTHS.index(sm) + 1, int(sd))
        end = date(int(ey), MONTHS.index(em) + 1, int(ed))
    except (ValueError, OverflowError):
        raise ValueError("Invalid Discovery date header") from None
    start_month = start.year * 12 + start.month - 1
    end_month = end.year * 12 + end.month - 1
    if (start.day != 1 or end.day != calendar.monthrange(end.year, end.month)[1]
            or end_month - start_month != 11):
        raise ValueError("Discovery date range must cover twelve complete months")
    columns = []
    for ordinal in range(start_month, end_month + 1):
        year, month = divmod(ordinal, 12)
        columns.append(f"Searches: {MONTH_ABBREVIATIONS[month]} {year}")
    return columns


def _normalized_keyword(value):
    if not value or any(unicodedata.category(char).startswith("C") for char in value):
        raise ValueError("Invalid Discovery keyword")
    canonical = unicodedata.normalize("NFKC", value).strip()
    if len(canonical) >= 2 and (canonical[0], canonical[-1]) in {("[", "]"), ('"', '"')}:
        canonical = canonical[1:-1].strip()
    normalized = " ".join(canonical.casefold().split())
    if not normalized:
        raise ValueError("Invalid Discovery keyword")
    return normalized


def parse_discovery(path) -> dict:
    """Return exact public strings and immutable-source provenance, or fail closed.

    ``source_line`` is the one-based starting physical line in the source TSV.
    Duplicate groups contain normalized text and all matching source lines;
    every original record remains present in source order. Only empty cells
    become None. Errors never contain source cell values or private paths.
    """
    source = Path(path)
    try:
        with source.open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
    except OSError:
        raise ValueError("Cannot read Discovery source") from None
    if len(raw) > MAX_BYTES:
        raise ValueError("Discovery source exceeds byte limit")
    if not raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        raise ValueError("Discovery source requires UTF-16 BOM")
    try:
        decoded = raw.decode("utf-16", errors="strict")
    except UnicodeError:
        raise ValueError("Invalid Discovery source encoding") from None
    reader = csv.reader(io.StringIO(decoded, newline=""), delimiter="\t", strict=True)
    try:
        title = next(reader)
        if len(title) != 1 or not re.fullmatch(
                r"Keyword Stats [0-9]{4}-[0-9]{2}-[0-9]{2} at [0-9]{2}_[0-9]{2}_[0-9]{2}", title[0]):
            raise ValueError("Invalid Discovery title header")
        date_row = next(reader)
        if len(date_row) != 1:
            raise ValueError("Invalid Discovery date header")
        monthly = _monthly_columns(date_row[0])
        labels = next(reader)
        expected = set(BASE_COLUMNS) | set(monthly)
        if len(labels) != len(expected) or len(set(labels)) != len(labels) or set(labels) != expected:
            raise ValueError("Invalid Discovery column headers")
        public = [label for label in labels if label not in EXCLUDED_COLUMNS]
        excluded = [label for label in labels if label in EXCLUDED_COLUMNS]
        positions = [(index, label) for index, label in enumerate(labels) if label in public]
        keyword_index = labels.index("Keyword")
        records = []
        groups = {}
        while True:
            source_line = reader.line_num + 1
            row = next(reader, None)
            if row is None:
                break
            if len(records) >= MAX_RECORDS:
                raise ValueError("Discovery source exceeds record limit")
            if len(row) != len(labels):
                raise ValueError("Invalid Discovery record width")
            normalized = _normalized_keyword(row[keyword_index])
            groups.setdefault(normalized, []).append(source_line)
            records.append({"source_line": source_line,
                            "values": {label: row[index] if row[index] != "" else None
                                       for index, label in positions}})
    except (csv.Error, StopIteration):
        raise ValueError("Malformed Discovery TSV structure") from None
    return {
        "source_basename": source.name,
        "source_bytes": len(raw),
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "date_header": date_row[0],
        "column_labels": labels,
        "public_columns": public,
        "excluded_columns": excluded,
        "record_count": len(records),
        "distinct_normalized_count": len(groups),
        "duplicate_groups": [{"normalized_keyword": text, "source_lines": lines}
                             for text, lines in groups.items() if len(lines) > 1],
        "records": records,
    }

def main():
    parser = argparse.ArgumentParser(description="Validate Discovery exports and emit count-only receipts.")
    parser.add_argument("exports", nargs="+", type=Path)
    args = parser.parse_args()
    receipts = []
    for index, path in enumerate(args.exports, 1):
        try:
            capture = parse_discovery(path)
        except ValueError:
            receipts.append({"input": index, "passed": False, "error": "INVALID_DISCOVERY_EXPORT"})
            continue
        receipts.append({"input": index, "passed": True, "sha256": capture["source_sha256"],
                         "bytes": capture["source_bytes"], "rows": capture["record_count"],
                         "distinct": capture["distinct_normalized_count"],
                         "duplicate_groups": len(capture["duplicate_groups"])})
    passed = all(receipt["passed"] for receipt in receipts)
    print(json.dumps({"passed": passed, "inputs": receipts,
                      "account_context_verified": False, "deployment_authorized": False}))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())

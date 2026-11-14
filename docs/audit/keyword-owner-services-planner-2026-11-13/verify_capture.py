"""Pinned owner-services Planner source verification; no writer or admission.

The optional private raw argument proves complete cell-for-cell projection.
Public verification alone establishes local consistency, not provider custody.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools/keyword-system"))
from keyword_audit import parse_json_bytes
import supplemental_discovery as sd

TOPIC = 'owner-services'
BATCH_ID = 'BSRE-KP-OWNER-SERVICES-20261113-01'
SOURCE_SHA256 = 'c0ccc1d5ef196db4ed2f466a564f441c20270a0f95650e8c1545b5bbb8b94c0d'
SOURCE_BYTES = 24210
SOURCE_ROWS = 147
SOURCE_DATE_HEADER = "November 1, 2025 - October 31, 2026"
SOURCE_PUBLIC_ALIAS = 'keyword-stats-owner-services-2026-11-13.csv'
SEEDS = ['sell my property dubai', 'sell apartment dubai', 'sell villa dubai', 'property valuation dubai', 'list property dubai', 'landlord services dubai', 'rent out my property dubai', 'let my apartment dubai', 'property management dubai', 'find tenants dubai']
PINS = {'owner-services.json': '0c4ed2af3a80d3521267fc9ba683925499d4fcef9c20dea4b279110994317f75', 'capture.json': 'a3c1a001ef0e3f37591718b7102bd156b94fd0bc43de8821cdf64d5d7184e403'}
DEPENDENCIES = {
    "tools/keyword-system/planner_discovery.py": "952423aac9ed3d1a4cb23185dd8da2a5451d19f7166fc73ce1c2b86391aadf9b",
    "tools/keyword-system/supplemental_discovery.py": "727230214dd3537089a093e0ad0a819e62986db8ca310e6856714403269106bf",
    "tools/keyword-system/keyword_audit.py": "ef6ce0535c8ce5cd83f50e169d26328cd763a236cfcbee4919f927c6fd8cd8d6",
}
# This commercial capture uses the existing 8 MiB public bound; no old source/bound changes.
MAX_PUBLIC_BYTES = 8 * 1024 * 1024


def need(condition, code):
    if not condition:
        raise ValueError(code)


def read_bound(path, bound=MAX_PUBLIC_BYTES):
    with Path(path).open("rb") as stream:
        blob = stream.read(bound + 1)
    need(0 < len(blob) <= bound, "PUBLIC_BYTE_BOUND")
    return blob


def pinned_json(name, blob):
    need(name in PINS and len(blob) <= MAX_PUBLIC_BYTES
         and hashlib.sha256(blob).hexdigest() == PINS[name], "PUBLIC_PIN_CHANGED")
    return parse_json_bytes(blob)


def validate_batch(batch):
    sd._batch(batch)
    projection = batch["source_projection"]
    expected = {
        "source_sha256": SOURCE_SHA256,
        "source_bytes": SOURCE_BYTES,
        "source_basename": SOURCE_PUBLIC_ALIAS,
        "date_header": SOURCE_DATE_HEADER,
        "record_count": SOURCE_ROWS,
        "distinct_normalized_count": SOURCE_ROWS,
        "duplicate_groups": [],
    }
    need(sd._exact({key: projection[key] for key in expected}, expected), "ACTUAL_SOURCE_BOUNDARY")
    need(batch["topic"] == TOPIC and batch["batch_id"] == BATCH_ID, "BATCH_IDENTITY")
    need(sd._exact(batch["input_seeds"], SEEDS), "EXACT_OBSERVED_SEEDS")
    need(sd._exact(batch["seed_reconciliation"], {"exact_returned": 10, "without_separate_exact_row": []}),
         "EXACT_SEED_RELATIONSHIP")
    need([r["source_line"] for r in projection["records"]] == list(range(4, SOURCE_ROWS + 4)),
         "EXACT_SOURCE_ORDER_AND_PHYSICAL_LINES")
    need([projection["records"][n-1]["values"]["Keyword"] for n in [142,1,2,3,143,144,145,146,4,147]] == SEEDS,
         "OBSERVED_SEED_ORDINALS_PRESERVED")


def verify(source=None):
    for name, digest in DEPENDENCIES.items():
        need(hashlib.sha256(read_bound(ROOT / name)).hexdigest() == digest, "DEPENDENCY_PIN_CHANGED")
    public = {name: pinned_json(name, read_bound(HERE / name)) for name in PINS}
    validate_batch(public[TOPIC + ".json"])
    sources = {} if source is None else {TOPIC: source}
    receipt = sd.verify_capture(HERE, PINS, sources)
    return dict(receipt, source_date_header=SOURCE_DATE_HEADER,
                source_bytes=SOURCE_BYTES, source_sha256=SOURCE_SHA256,
                public_columns=21, excluded_account_specific_columns=5,
                dependency_pins_verified=len(DEPENDENCIES), exact_seed_rows=10,
                all_source_occurrences_retained=True, semantic_review_complete=False,
                current_library_membership_verified=False)


def self_check():
    original = pinned_json(TOPIC + ".json", read_bound(HERE / (TOPIC + ".json")))
    validate_batch(original)
    mutations = (
        ("NUMERIC_PUBLIC_CELL", lambda b: b["source_projection"]["records"][0]["values"].__setitem__("Avg. monthly searches", 50)),
        ("DROPPED_SOURCE_OCCURRENCE", lambda b: b["source_projection"]["records"].pop()),
        ("SOURCE_LINE_DRIFT", lambda b: b["source_projection"]["records"][0].__setitem__("source_line", 5)),
        ("ACCOUNT_SPECIFIC_CELL_REINTRODUCED", lambda b: b["source_projection"]["records"][0]["values"].__setitem__("In account?", "Yes")),
        ("AUTHORITY_FLIP", lambda b: b["controls"].__setitem__("approved", True)),
        ("BOOLEAN_REPLACED_BY_NUMBER", lambda b: b["controls"].__setitem__("reviewed", 0)),
        ("SEED_CHANGED", lambda b: b["input_seeds"].__setitem__(0, "manufactured seed")),
        ("PERIOD_DRIFT", lambda b: b["source_projection"].__setitem__("date_header", "October 1, 2025 - September 30, 2026")),
        ("SOURCE_HASH_DRIFT", lambda b: b["source_projection"].__setitem__("source_sha256", "0" * 64)),
        ("UI_COUNT_DERIVED_OR_CHANGED", lambda b: b["ui_context"].__setitem__("ui_idea_count", 146)),
        ("SOURCE_ORDER_REVERSED", lambda b: b["source_projection"]["records"].reverse()),
    )
    rejected = []
    for name, mutate in mutations:
        changed = copy.deepcopy(original)
        mutate(changed)
        try:
            validate_batch(changed)
        except (ValueError, KeyError, TypeError):
            rejected.append(name)
        else:
            raise ValueError("STRUCTURAL_TAMPER_NOT_REJECTED")
    changed = copy.deepcopy(original)
    changed["source_projection"]["records"][0]["values"]["Avg. monthly searches"] = "50000"
    changed_blob = (json.dumps(changed, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    try:
        pinned_json(TOPIC + ".json", changed_blob)
    except ValueError:
        rejected.append("ALTERED_METRIC_STRING_PIN")
    else:
        raise ValueError("METRIC_TAMPER_NOT_REJECTED")
    return {"passed": True, "in_memory_mutations_rejected": len(rejected), "checks": rejected,
            "scope": "PUBLIC_SOURCE_DIAGNOSTIC_NOT_SEMANTIC_REVIEW_OR_ADMISSION"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, metavar="PRIVATE_PATH")
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    started = time.perf_counter()
    try:
        result = verify(args.source)
        if args.self_check:
            result["tamper_diagnostic"] = self_check()
        result["measured_elapsed_seconds"] = round(time.perf_counter() - started, 6)
        print(json.dumps(result, sort_keys=True))
    except Exception as error:
        # Never print input paths, source cells, account parameters or exception text.
        print(json.dumps({"passed": False, "code": "OWNER_SERVICES_CAPTURE_FAILED",
                          "error_type": type(error).__name__, "deployment_authorized": False}))
        raise SystemExit(1)


if __name__ == "__main__":
    main()

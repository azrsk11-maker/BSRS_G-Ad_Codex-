"""Pinned specialized-service Planner source verification; no writer or admission.

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

TOPIC = 'service-installation'
BATCH_ID = 'BSRE-KP-SERVICE-INSTALLATION-20261113-01'
SOURCE_SHA256 = '4dda5a60cfbb680edff4d2b6c17319f55afb41055968052bb18e6b3d883f5078'
SOURCE_BYTES = 845492
SOURCE_ROWS = 6053
SOURCE_DATE_HEADER = "November 1, 2025 - October 31, 2026"
SOURCE_PUBLIC_ALIAS = 'keyword-stats-service-installation-2026-11-13.csv'
SEEDS = ['fire alarm installation', 'cctv installation', 'swimming pool cleaning service', 'irrigation system repair', 'grease trap cleaning', 'septic tank pumping', 'air duct cleaning', 'termite treatment', 'cockroach exterminator', 'bed bug removal']
PINS = {'service-installation.json': '91b8edcdcc6b8ab216c89ba2b1c9674ced8bcaf2be93d9f3ffe47795c1c75392', 'capture.json': '3e6f99d8cce615ab77549c2e33b1edce93605f78e7fb4b034fb9e9440e6f12ea'}
DEPENDENCIES = {
    "tools/keyword-system/planner_discovery.py": "952423aac9ed3d1a4cb23185dd8da2a5451d19f7166fc73ce1c2b86391aadf9b",
    "tools/keyword-system/supplemental_discovery.py": "727230214dd3537089a093e0ad0a819e62986db8ca310e6856714403269106bf",
    "tools/keyword-system/keyword_audit.py": "ef6ce0535c8ce5cd83f50e169d26328cd763a236cfcbee4919f927c6fd8cd8d6",
}
# This exact 6,053-row projection is 5,448,286 bytes; no old bound changes.
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
    need([r["values"]["Keyword"] for r in projection["records"][:10]] == SEEDS,
         "OBSERVED_FIRST_TEN_COMPLETE_SEED_ROWS")


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
        ("UI_COUNT_DERIVED_OR_CHANGED", lambda b: b["ui_context"].__setitem__("ui_idea_count", 6052)),
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
        print(json.dumps({"passed": False, "code": "SERVICE_INSTALLATION_CAPTURE_FAILED",
                          "error_type": type(error).__name__, "deployment_authorized": False}))
        raise SystemExit(1)


if __name__ == "__main__":
    main()

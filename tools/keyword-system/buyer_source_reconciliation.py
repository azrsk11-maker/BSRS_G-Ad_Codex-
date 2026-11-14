"""Read-only reconciliation of captured buyer wording, never keyword admission.

Lexical attention is deliberately broader than exact-literal overlap. Neither
an unmatched phrase nor a shared key proves a distinct concept, service coverage
or Google matching behavior. Every original occurrence remains independently
addressable; metrics stay in their pinned source, without aggregation.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path
import time

import keyword_audit as ka
import positive_service_packet as historical
import source_membership_diagnostic as lexical
import supplemental_discovery as sd

ROOT = Path(__file__).resolve().parents[2]
FOLDER = "docs/audit/keyword-buyer-property-planner-2026-11-13"
PRIOR = "docs/audit/keyword-buyer-offplan-planner-2026-11-12/source.json"
REPORT = FOLDER + "/reconciliation.json"
REPORT_SHA256 = '2c3d0c830502435521c65fe8fa8ecba6d92bb83850db44e8dba5d68dfd1d9a60'
SOURCE_VERIFIER_SHA256 = "4435ee1eb77ff54a649f403ee5d8266e648415c578cf0b1167319a3680e952cc"
PRIOR_SHA256 = "1a310b01460daa461c78b3ecdb19f5069cb74217187d01d608b513af5a128bfb"
DEPENDENCIES = {
    "tools/keyword-system/source_membership_diagnostic.py": "bd8bafb4c49d23185b8cff91112e1c79679ae39bd9def9974e6d911ed891e41c",
    "tools/keyword-system/positive_service_packet.py": "5e69857f2e33e6a2686ad68ba430238bdac6bbe2d89bf6dd2340b9616cad36bd",
    "tools/keyword-system/historical_intake.py": "078bad6db2fc0b7bd2e74df6b66e8adde94c2a262dfa0f2c2d96378d609a7c99",
    "tools/keyword-system/keyword_text_compatibility.py": "723988151adfeae8f2a6efeb073a399451eefcbfe1d3f8c311e0e168fd56763f",
}
METHODS = lexical.METHODS + ("in_preposition_omission_attention",)
MAX_BYTES = 8 * 1024 * 1024


def need(condition, code):
    if not condition:
        raise ValueError(code)


def read_bound(path):
    with Path(path).open("rb") as stream:
        blob = stream.read(MAX_BYTES + 1)
    need(0 < len(blob) <= MAX_BYTES, "INPUT_BYTE_BOUND")
    return blob


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def attention_keys(text):
    """The fifth key only flags removal of the literal preposition 'in'."""
    values = lexical.keys(text)
    return values + (tuple(token for token in values[1] if token != "in"),)


def load_inputs():
    """Re-read complete source bytes and dependency pins on every invocation."""
    for path, expected in DEPENDENCIES.items():
        need(hashlib.sha256(read_bound(ROOT / path)).hexdigest() == expected,
             "DEPENDENCY_PIN_CHANGED")
    verifier_path = ROOT / FOLDER / "verify_capture.py"
    need(hashlib.sha256(read_bound(verifier_path)).hexdigest() == SOURCE_VERIFIER_SHA256,
         "SOURCE_VERIFIER_PIN_CHANGED")
    spec = importlib.util.spec_from_file_location("buyer_capture_fresh", verifier_path)
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    receipt = verifier.verify()
    batch = verifier.pinned_json("buyer-property.json", read_bound(ROOT / FOLDER / "buyer-property.json"))
    verifier.validate_batch(batch)
    history = historical.load_history(read_bound(ROOT / historical.HISTORY))
    prior_blob = read_bound(ROOT / PRIOR)
    need(hashlib.sha256(prior_blob).hexdigest() == PRIOR_SHA256, "PRIOR_SOURCE_PIN_CHANGED")
    prior = ka.parse_json_bytes(prior_blob)
    need(len(prior["rows"]) == 6 and prior["account_id"] == "573-038-4686",
         "PRIOR_CAPTURE_POPULATION")
    return batch, history, prior, receipt


def _compute(batch, history, prior, receipt):
    """Pure indexed join; callers must obtain inputs through load_inputs."""
    records = batch["source_projection"]["records"]
    external = []
    for candidate in history["candidates"]:
        for variant_index, literal in enumerate(candidate["original_text_variants"], 1):
            external.append({"reference": candidate["candidate_id"] + ":variant:" + str(variant_index),
                             "population": "historical_candidate", "original_literal": literal,
                             "candidate_id": candidate["candidate_id"],
                             "placement_ids": candidate["placement_ids"]})
    for row in prior["rows"]:
        external.append({"reference": "prior-buyer:ordinal:" + str(row["source_ordinal"]),
                         "population": "prior_buyer_capture", "original_literal": row["cells"][1],
                         "source_ordinal": row["source_ordinal"], "row_kind": row["row_kind"],
                         "complete_cells_sha256": digest(row["cells"])})
    indexes = {method: defaultdict(list) for method in METHODS}
    for row in external:
        for method, key in zip(METHODS, attention_keys(row["original_literal"])):
            indexes[method][key].append(row["reference"])
    peer_indexes = {method: defaultdict(list) for method in METHODS}
    row_keys = []
    for ordinal, row in enumerate(records, 1):
        values = attention_keys(row["values"]["Keyword"])
        row_keys.append(values)
        for method, key in zip(METHODS, values):
            peer_indexes[method][key].append(ordinal)
    comparisons = []
    exact_legacy = []; exact_prior = []; attention = []; unmatched = []
    method_counts = {method: {"rows_with_external_matches": 0, "rows_with_source_peers": 0}
                     for method in METHODS}
    for ordinal, (row, values) in enumerate(zip(records, row_keys), 1):
        joins = []
        for method, key in zip(METHODS, values):
            refs = sorted(indexes[method].get(key, ()))
            peers = [n for n in peer_indexes[method][key] if n != ordinal]
            method_counts[method]["rows_with_external_matches"] += int(bool(refs))
            method_counts[method]["rows_with_source_peers"] += int(bool(peers))
            joins.append({"method": method, "external_references": refs, "source_peer_ordinals": peers})
        exact = joins[0]["external_references"]
        legacy_hit = any(ref.startswith("LEGACY-POS-") for ref in exact)
        prior_hit = any(ref.startswith("prior-buyer:") for ref in exact)
        has_attention = any(join["external_references"] or join["source_peer_ordinals"] for join in joins[1:])
        if legacy_hit:
            exact_legacy.append(ordinal)
        if prior_hit:
            exact_prior.append(ordinal)
        if has_attention:
            attention.append(ordinal)
        if not (legacy_hit or prior_hit or has_attention or joins[0]["source_peer_ordinals"]):
            unmatched.append(ordinal)
        comparisons.append({"source_ordinal": ordinal, "source_line": row["source_line"],
                            "original_literal": row["values"]["Keyword"],
                            "original_literal_sha256": hashlib.sha256(row["values"]["Keyword"].encode("utf-8")).hexdigest(),
                            "complete_public_values_sha256": digest(row["values"]),
                            "normalized_literal_matches_historical": legacy_hit,
                            "normalized_literal_matches_prior_capture": prior_hit,
                            "lexical_attention_required": has_attention,
                            "semantic_review": "UNASSESSED_NOT_ADMITTED", "joins": joins})
    peer_groups = {method: [ordinals for _, ordinals in sorted(peer_indexes[method].items())
                            if len(ordinals) > 1] for method in METHODS}
    return {
        "schema_version": 1, "scope": "BUYER_SOURCE_LEXICAL_RECONCILIATION_ONLY",
        "inputs": {"buyer_public_path": FOLDER + "/buyer-property.json",
                   "buyer_public_sha256": "2876c299228dff45b764a0b85f43ac9de316153dae846c372ebcea889ddbff89",
                   "buyer_raw_sha256": receipt["source_sha256"],
                   "historical_intake_path": historical.HISTORY, "historical_intake_sha256": historical.HISTORY_SHA256,
                   "prior_buyer_path": PRIOR, "prior_buyer_sha256": PRIOR_SHA256},
        "counts": {"source_occurrences": len(records), "source_public_cells": 21 * len(records),
                   "historical_candidates": len(history["candidates"]), "historical_literal_forms": len(external) - 6,
                   "historical_placements": len(history["placements"]), "prior_buyer_occurrences": 6,
                   "normalized_literal_matches_historical": len(exact_legacy),
                   "normalized_literal_matches_prior_capture": len(exact_prior),
                   "rows_with_lexical_attention": len(attention),
                   "unmatched_unassessed_rows": len(unmatched), "confirmed_novel_canonicals": None,
                   "positive_admissions_added": 0, "approvals_added": 0, "deployed_added": 0},
        "comparison_methods": list(METHODS), "method_counts": method_counts,
        "ordinal_sets": {"normalized_literal_matches_historical": exact_legacy,
                         "normalized_literal_matches_prior_capture": exact_prior,
                         "lexical_attention": attention, "unmatched_unassessed": unmatched},
        "external_literal_references": external, "within_source_attention_groups": peer_groups,
        "source_occurrences": comparisons,
        "interpretation": {
            "normalized_literal": "NFKC, case/whitespace and one matching exact/phrase wrapper only; not a distinct-concept or Google-match decision",
            "other_methods": "Review attention only; never automatic merging, rejection or admission",
            "in_preposition_omission_attention": "Remove the literal token in; retain both complete originals and source metrics",
            "unmatched": "No match among these named inputs and methods; not proven novel or service-eligible",
            "metrics": "Historical source strings retained in pinned capture; no aggregation, numeric inference or actual account CPC",
        },
        "controls": {"all_source_occurrences_retained": True, "historical_sources_unchanged": True,
                     "current_library_membership_verified": False, "current_negative_conflicts_tested": False,
                     "semantic_review_complete": False, "google_equivalence_verified": False,
                     "business_evidence_verified": False, "campaign_or_page_mapping_assigned": False,
                     "admission_approved": False, "deployment_authorized": False,
                     "source_contribution_only_not_current_library_totals": True},
    }


def build_report():
    return _compute(*load_inputs())


def validate_report(report):
    need(sd._exact(report, build_report()), "RECONCILIATION_DIFFERS_FROM_FRESH_SOURCES")


def verify_report(blob=None):
    blob = read_bound(ROOT / REPORT) if blob is None else blob
    need(type(blob) is bytes and 0 < len(blob) <= MAX_BYTES
         and hashlib.sha256(blob).hexdigest() == REPORT_SHA256, "REPORT_PIN_CHANGED")
    report = ka.parse_json_bytes(blob)
    validate_report(report)
    return {"passed": True, "scope": report["scope"], "counts": report["counts"],
            "deployment_authorized": False}


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    started = time.perf_counter()
    try:
        result = verify_report()
        result["measured_elapsed_seconds"] = round(time.perf_counter() - started, 6)
        print(json.dumps(result, sort_keys=True))
    except Exception as error:
        print(json.dumps({"passed": False, "code": "BUYER_RECONCILIATION_FAILED",
                          "error_type": type(error).__name__, "deployment_authorized": False}))
        raise SystemExit(1)


if __name__ == "__main__":
    main()

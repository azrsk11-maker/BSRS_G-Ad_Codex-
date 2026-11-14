"""Fresh all-current negative research screen for the complete buyer capture.

Checks the existing lexical negative model, before scope is bound. Potential
matches are review holds, not evidence that a live exclusion applies. Clear
wording is not positive admission, semantic equivalence or launch readiness.
"""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import time

import buyer_source_reconciliation as buyer
import current_negative_library as current
import keyword_audit as ka
import negative_admission as first

ROOT = Path(__file__).resolve().parents[2]
FOLDER = "docs/audit/keyword-buyer-negative-screen-2026-11-13"
REPORT = FOLDER + "/screen.json"
REPORT_SHA256 = "6db250807797e7e9e14efffcd2f823fb1d45fa817c14764658cd9f4527767e49"
CURRENT_SHA256 = "1dd9cd9a93f5cb78695846be7cf0767864c8d5bb20e94ab4a731a71f07ba27ae"
DEPENDENCIES = {
    "tools/keyword-system/current_negative_library.py": "77122074aae8dbd050e4e00d4f659870aff107449461ade9e5edfa7fdfc94795",
    "tools/keyword-system/buyer_source_reconciliation.py": "21b8f4af1107a28c0851e8456c5f7a264a27bad466e9619e306736b612eafdd8",
    "tools/keyword-system/keyword_audit.py": "ef6ce0535c8ce5cd83f50e169d26328cd763a236cfcbee4919f927c6fd8cd8d6",
}


def need(condition, code):
    if not condition:
        raise ValueError(code)


def index_negatives(records):
    """No normalized-body rewrite; index immutable lexical tokens only."""
    need(type(records) is list and bool(records), "EMPTY_NEGATIVE_POPULATION")
    identities = set(); exact = defaultdict(list); other = []
    for row in records:
        identity = row["keyword_id"]
        need(type(identity) is str and identity and identity not in identities,
             "INVALID_OR_DUPLICATE_NEGATIVE_IDENTITY")
        identities.add(identity)
        need(type(row["original_text"]) is str and bool(ka.tokens(row["original_text"])),
             "INVALID_NEGATIVE_LITERAL")
        need(row["match_type"] in ("EXACT", "PHRASE", "BROAD"), "INVALID_MATCH_TYPE")
        if row["match_type"] == "EXACT":
            exact[tuple(ka.tokens(row["original_text"]))].append(identity)
        else:
            other.append(row)
    return exact, other


def scan_rows(records, rows):
    """All records and source occurrences; mixed match types retain the model."""
    exact, other = index_negatives(records)
    need(type(rows) is list and bool(rows), "EMPTY_SOURCE_POPULATION")
    result = []; seen_lines = set()
    for ordinal, row in enumerate(rows, 1):
        line = row["source_line"]; literal = row["values"]["Keyword"]
        need(type(line) is int and line > 0 and line not in seen_lines, "INVALID_SOURCE_LINE")
        seen_lines.add(line)
        need(type(literal) is str and bool(ka.tokens(literal)), "INVALID_SOURCE_LITERAL")
        matched = list(exact.get(tuple(ka.tokens(literal)), ()))
        matched.extend(r["keyword_id"] for r in other
                       if ka.negative_matches(r["original_text"], r["match_type"], literal))
        result.append({"source_ordinal": ordinal, "source_line": line,
                       "original_literal_sha256": hashlib.sha256(literal.encode("utf-8")).hexdigest(),
                       "potential_negative_ids": sorted(matched),
                       "lexical_state": "POTENTIAL_CONFLICT_HOLD" if matched else "NO_LEXICAL_MATCH_IN_NAMED_RESEARCH",
                       "actual_scope_applicability": "UNVERIFIED_NO_DEPLOYMENT_BINDING",
                       "positive_admission_granted": False})
    return result


def load_sources():
    for path, expected in DEPENDENCIES.items():
        need(hashlib.sha256(buyer.read_bound(ROOT / path)).hexdigest() == expected,
             "DEPENDENCY_PIN_CHANGED")
    buyer.verify_report()
    batch, _, _, _ = buyer.load_inputs()
    # Complete public API: all history, reviews, source pins and saved outputs are
    # freshly reconstructed. No serialized master or prior verdict is accepted.
    base = current.reconstruct()
    need(hashlib.sha256(first.canonical(base)).hexdigest() == CURRENT_SHA256,
         "COMPLETE_CURRENT_NEGATIVE_STATE_CHANGED")
    expected = (14000, 18, 19115, 35, 360, 1)
    need(tuple(len(base[k]) for k in ("records", "archived_records", "protected_queries",
                                     "sources", "campaigns", "campaign_context")) == expected,
         "COMPLETE_CURRENT_POPULATIONS_CHANGED")
    need(sum(len(r["provenance_occurrences"]) for r in base["records"]) == 14213,
         "CURRENT_PROVENANCE_OCCURRENCES_CHANGED")
    return base, batch


def assemble(base, batch):
    rows = batch["source_projection"]["records"]
    active = scan_rows(base["records"], rows)
    archived = scan_rows(base["archived_records"], rows)
    active_rows = [r["source_ordinal"] for r in active if r["potential_negative_ids"]]
    archived_rows = [r["source_ordinal"] for r in archived if r["potential_negative_ids"]]
    matched_ids = sorted({identity for row in active for identity in row["potential_negative_ids"]})
    by_id = {r["keyword_id"]: r for r in base["records"]}
    return {
        "schema_version": 1, "scope": "ALL_CURRENT_RESEARCH_NEGATIVES_LEXICAL_SCREEN_NOT_LIVE_SCOPE_ACCEPTANCE",
        "inputs": {"buyer_source_sha256": buyer.build_report()["inputs"]["buyer_public_sha256"],
                   "complete_current_negative_sha256": CURRENT_SHA256,
                   "source_occurrences": len(rows), "research_negatives": len(base["records"]),
                   "archived_negative_records": len(base["archived_records"]),
                   "protected_queries_in_verified_history": len(base["protected_queries"]),
                   "research_source_registrations": len(base["sources"]),
                   "provenance_occurrences": sum(len(r["provenance_occurrences"]) for r in base["records"]),
                   "planned_campaigns": len(base["campaigns"]),
                   "match_types": dict(sorted(Counter(r["match_type"] for r in base["records"]).items()))},
        "current_research_comparisons": active, "archived_research_comparisons": archived,
        "current_conflict_source_ordinals": active_rows, "archived_overlap_source_ordinals": archived_rows,
        "potential_current_conflict_records": [{key: by_id[identity][key] for key in
            ("keyword_id", "original_text", "match_type", "scope_type", "scope_target",
             "eligible_campaigns", "ineligible_campaigns", "approval_state", "review_state")}
            for identity in matched_ids],
        "counts": {"current_potential_conflict_rows": len(active_rows),
                   "current_potential_conflict_records": len(matched_ids),
                   "archived_overlap_rows": len(archived_rows),
                   "source_occurrences_screened": len(rows),
                   "positive_admissions_added": 0, "negative_changes": 0, "approvals_added": 0, "deployed_added": 0},
        "controls": {"complete_current_history_freshly_verified": True,
                     "every_source_occurrence_retained": True,
                     "actual_campaign_binding_verified": False, "actual_scope_applicability_verified": False,
                     "google_matching_equivalence_verified": False, "semantic_review_complete": False,
                     "business_evidence_verified": False, "positive_admission_approved": False,
                     "negative_approval_granted": False, "deployment_authorized": False,
                     "current_negative_count_unchanged": True},
        "limits": ["Lexical model only, not Google close variants or semantic conflicts",
                   "Potential matches are conservative holds before actual campaign/ad-group exclusion scope is bound",
                   "Archived matches never reactivate an exclusion",
                   "Clear wording does not establish buyer intent, novelty, approved service, inventory, claims, language or destination",
                   "Research approval and live deployment remain separate; no actual Ads setting is read or changed here"],
    }


def build_report():
    return assemble(*load_sources())


def verify_saved():
    blob = buyer.read_bound(ROOT / REPORT)
    need(hashlib.sha256(blob).hexdigest() == REPORT_SHA256, "REPORT_PIN_CHANGED")
    report = ka.parse_json_bytes(blob)
    need(buyer.sd._exact(report, build_report()), "REPORT_DIFFERS_FROM_FRESH_COMPLETE_SOURCES")
    return {"passed": True, "scope": report["scope"], "counts": report["counts"],
            "deployment_authorized": False}


if __name__ == "__main__":
    started = time.perf_counter()
    try:
        result = verify_saved()
        result["measured_elapsed_seconds"] = round(time.perf_counter() - started, 6)
        print(json.dumps(result, sort_keys=True))
    except Exception as error:
        print(json.dumps({"passed": False, "code": "BUYER_NEGATIVE_SCREEN_FAILED",
                          "error_type": type(error).__name__, "deployment_authorized": False}))
        raise SystemExit(1)

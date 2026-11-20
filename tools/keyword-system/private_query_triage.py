"""PRIVATE, read-only historical-query triage; no disclosure or admission gate.

Both returned artifacts remain private. Only the strict count summary omits
query text, source labels, paths and internal identities. Nothing is written.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re

from keyword_audit import normalize
from search_terms_intake import parse_search_terms
import triage_workbench as tw

SCOPE = "PRIVATE_HISTORICAL_QUERY_TRIAGE_NOT_DISCLOSURE_OR_ADMISSION"
PRIVACY_HOLD_REASON = (
    "Disclosure review is required because retained source text has a privacy "
    "candidate flag. This automatic hold makes no negative or eligibility decision."
)
AUTHORITY = {"public_disclosure_authorized": False, "deployment_authorized": False,
             "negative_authorized": False, "qualification_authorized": False}
COUNT_FIELDS = frozenset({
    "source_bytes", "unique_query_identities", "query_occurrences", "manual_intent_proposals",
    "automatic_privacy_hold_identities", "automatic_privacy_hold_occurrences",
    "privacy_flagged_source_records", "positive_review_identities", "hold_identities",
    "negative_exact_review_identities", "unassessed_identities",
    "manual_disclosure_review_required_occurrences", "protected_phrase_identities",
    "exact_negative_candidate_identities", "exact_lexical_match_instances",
    "exact_protected_lexical_collision_instances", "unsafe_generic_hypotheses_count",
    "unsafe_generic_lexical_collision_instances", "reviewed_positive", "reviewed_negative",
    "approved_positive", "approved_negative", "admitted_positive", "admitted_negative",
    "master_additions", "deployed",
})
BOOLEAN_FIELDS = frozenset({"complete_intent_triage", "complete_input_required",
                            "lexical_scope_verified", "resource_ids_verified", *AUTHORITY})


def _need(condition, code):
    if not condition:
        raise ValueError(code)


def _read_source(source_path):
    # Raise outside the handler so even exception context cannot retain source
    # cell/path text from a dependency's error message.
    try:
        return parse_search_terms(source_path)
    except Exception:
        pass
    raise ValueError("PRIVATE_HISTORY_SOURCE_INVALID")


def _copy_document(document):
    try:
        return deepcopy(document)
    except Exception:
        pass
    raise ValueError("PRIVATE_HISTORY_PROPOSALS_INVALID")


def _compile(corpus, document):
    try:
        return tw.compile_workbench(corpus, document)
    except Exception:
        pass
    raise ValueError("PRIVATE_HISTORY_PROPOSALS_INVALID")


def compile_private_history(source_path, proposal_document, require_complete=True):
    """Compile a private report projection and strict count-only summary.

    Manual proposals use the ordinary seven-field preliminary schema and dated
    document envelope. Every unflagged normalized identity needs one proposal
    by default. ``require_complete=False`` preserves unproposed UNASSESSED rows.
    Privacy flags are unioned over every occurrence, including placement flags;
    a flagged identity cannot receive a manual intent proposal of any kind.

    Source hashes/internal queue identities never identify Google resources.
    Unflagged records still require manual disclosure review. There is no writer,
    network client, approved master, public exporter or automatic exclusion.
    """
    _need(type(require_complete) is bool, "PRIVATE_HISTORY_COMPLETENESS_TYPE")
    private = _read_source(source_path)
    document = _copy_document(proposal_document)
    _need(isinstance(document, dict) and set(document) ==
          {"version", "scope", "proposed_on", "proposals"}, "PRIVATE_HISTORY_PROPOSALS_INVALID")
    _need(type(document["version"]) is int and document["version"] == 1
          and document["scope"] == tw.SCOPE and document["proposed_on"] == tw.DAY
          and isinstance(document["proposals"], list), "PRIVATE_HISTORY_PROPOSALS_INVALID")

    sha = private["source_sha256"]
    batch = "PRIVATE-REPORT-" + sha
    entries, flags = {}, {}
    for record in private["records"]:
        key, original = record["normalized_search_term"], record["search_term"]
        entry = entries.setdefault(key, {"original_forms": [], "source_refs": []})
        if original not in entry["original_forms"]:
            entry["original_forms"].append(original)
        entry["source_refs"].append({"batch": batch, "source_line": record["source_line"]})
        flags.setdefault(key, set()).update(record["privacy_flags"])
    # Only the actual basename enters this PRIVATE source manifest, never its
    # directory. Placement strings and all discarded metric cells stay absent.
    corpus = {"sources": {batch: {"file": Path(source_path).name, "sha256": sha}},
              "entries": entries}
    flagged = {key for key, values in flags.items() if values}
    manual = set()
    for proposal in document["proposals"]:
        _need(isinstance(proposal, dict) and set(proposal) == tw.PROPOSAL_FIELDS
              and isinstance(proposal["text"], str), "PRIVATE_HISTORY_PROPOSALS_INVALID")
        key = normalize(proposal["text"])
        _need(key in entries, "PRIVATE_HISTORY_UNKNOWN_QUERY")
        _need(key not in manual, "PRIVATE_HISTORY_DUPLICATE_QUERY")
        _need(key not in flagged, "PRIVATE_HISTORY_PRIVACY_OVERRIDE_FORBIDDEN")
        manual.add(key)
    if require_complete:
        _need(manual == set(entries) - flagged, "PRIVATE_HISTORY_INCOMPLETE_PROPOSALS")

    for key in sorted(flagged):
        document["proposals"].append({
            "text": entries[key]["original_forms"][0], "disposition": "HOLD",
            "intent": "DISCLOSURE_REVIEW_REQUIRED", "possible_services": [],
            "reason": PRIVACY_HOLD_REASON, "negative_scope_proposal": None,
            "protect_against_generic": [],
        })
    workbench = _compile(corpus, document)
    workbench["scope"] = SCOPE
    workbench["resource_identity_status"] = "NOT_VERIFIED"
    workbench["controls"].update({
        **AUTHORITY, "private_only": True,
        "all_records_require_manual_disclosure_review": True,
        "unflagged_records_are_not_verified_safe": True,
        "automatic_privacy_holds_are_not_negative_or_eligibility_decisions": True,
        "resource_ids_verified": False,
    })
    for row in workbench["queue"]:
        row.update({"privacy_flags": sorted(flags[row["normalized_text"]]),
                    "manual_disclosure_review_required": True,
                    "resource_ids_verified": False, **AUTHORITY})

    disposition = workbench["summary"]["dispositions"]
    diagnostics = workbench["diagnostics"]
    exact, generic = diagnostics["exact_negative_tests"], diagnostics["unsafe_generic_tests"]
    summary = {
        "source_sha256": sha, "source_bytes": private["source_bytes"],
        "unique_query_identities": len(entries),
        "query_occurrences": sum(len(e["source_refs"]) for e in entries.values()),
        "manual_intent_proposals": len(manual),
        "automatic_privacy_hold_identities": len(flagged),
        "automatic_privacy_hold_occurrences": sum(len(entries[k]["source_refs"]) for k in flagged),
        "privacy_flagged_source_records": private["summary"]["privacy_flagged_records"],
        "positive_review_identities": disposition["POSITIVE_REVIEW"],
        "hold_identities": disposition["HOLD"],
        "negative_exact_review_identities": disposition["NEGATIVE_EXACT_REVIEW"],
        "unassessed_identities": disposition["UNASSESSED"],
        "complete_intent_triage": disposition["UNASSESSED"] == 0,
        "complete_input_required": require_complete,
        "manual_disclosure_review_required_occurrences": len(private["records"]),
        "protected_phrase_identities": len(diagnostics["protected_phrases"]),
        "exact_negative_candidate_identities": len(exact),
        "exact_lexical_match_instances": sum(len(t["observed_lexical_matches"]) for t in exact),
        "exact_protected_lexical_collision_instances": sum(len(t["protected_lexical_collisions"]) for t in exact),
        "unsafe_generic_hypotheses_count": len(generic),
        "unsafe_generic_lexical_collision_instances": sum(len(t["protected_lexical_collisions"]) for t in generic),
        "lexical_scope_verified": False, "resource_ids_verified": False,
        "reviewed_positive": 0, "reviewed_negative": 0,
        "approved_positive": 0, "approved_negative": 0,
        "admitted_positive": 0, "admitted_negative": 0, "master_additions": 0, "deployed": 0,
        **AUTHORITY,
    }
    _need(set(summary) == COUNT_FIELDS | BOOLEAN_FIELDS | {"source_sha256"}
          and all(type(summary[k]) is int and summary[k] >= 0 for k in COUNT_FIELDS)
          and all(type(summary[k]) is bool for k in BOOLEAN_FIELDS)
          and isinstance(summary["source_sha256"], str)
          and re.fullmatch(r"[0-9a-f]{64}", summary["source_sha256"]) is not None,
          "PRIVATE_HISTORY_SUMMARY_INVALID")
    return {"scope": SCOPE, "private_workbench": workbench, "count_summary": summary}

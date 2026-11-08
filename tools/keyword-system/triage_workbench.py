"""Read-only preliminary triage compiler. No master admission or platform writer.

Lexical diagnostics are conservative local tests, not Google matching results.
The public Discovery verifier must pass before any corpus is constructed.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import importlib.util
from pathlib import Path
import re

from keyword_audit import ADMISSION_PURPOSES, negative_matches, normalize, parse_json_bytes, tokens

CAPTURE = Path("docs/audit/keyword-discovery-2026-11-08")
SCOPE = "CODEX_PRELIMINARY_TRIAGE"
DAY = "2026-11-08"
DISPOSITIONS = {"POSITIVE_REVIEW", "NEGATIVE_EXACT_REVIEW", "HOLD"}
PROPOSAL_FIELDS = {"text", "disposition", "intent", "possible_services", "reason",
                   "negative_scope_proposal", "protect_against_generic"}
NEGATIVE_SCOPE = {"type": "CAMPAIGN", "campaign_keys": [], "approved": False, "match_type": "EXACT"}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def load_corpus(root: Path) -> dict:
    """Verify the dated capture, then retain every occurrence, without metrics."""
    folder = Path(root).resolve() / CAPTURE
    spec = importlib.util.spec_from_file_location("dated_triage_capture_verifier", folder / "verify_capture.py")
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    verified = verifier.verify()
    need(verified.get("passed") is True, "Capture verification did not pass")
    index_blob = (folder / "capture.json").read_bytes()
    need(hashlib.sha256(index_blob).hexdigest() == verifier.PINS["capture.json"], "Capture index changed after verification")
    index = parse_json_bytes(index_blob)
    sources, entries = {}, {}
    for item in index["source_files"]:
        batch = item["batch_id"]
        need(batch not in sources, "Duplicate batch")
        blob = (folder / item["file"]).read_bytes()
        need(hashlib.sha256(blob).hexdigest() == item["sha256"], "Capture changed after verification")
        sources[batch] = {"file": (CAPTURE / item["file"]).as_posix(), "sha256": item["sha256"]}
        for record in parse_json_bytes(blob)["source_projection"]["records"]:
            original = record["values"]["Keyword"]
            key = normalize(original)
            entry = entries.setdefault(key, {"original_forms": [], "source_refs": []})
            if original not in entry["original_forms"]:
                entry["original_forms"].append(original)
            entry["source_refs"].append({"batch": batch, "source_line": record["source_line"]})
    need(len(entries) == verified["distinct_phrases"] and
         sum(len(e["source_refs"]) for e in entries.values()) == verified["export_rows"], "Corpus coverage mismatch")
    return {"sources": sources, "entries": entries}


def _validate_corpus(corpus):
    need(isinstance(corpus, dict) and set(corpus) == {"sources", "entries"}, "Unexpected corpus fields")
    sources, entries = corpus["sources"], corpus["entries"]
    need(isinstance(sources, dict) and isinstance(entries, dict), "Invalid corpus")
    for batch, source in sources.items():
        need(isinstance(batch, str) and bool(batch) and isinstance(source, dict) and
             set(source) == {"file", "sha256"} and isinstance(source["file"], str) and
             isinstance(source["sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", source["sha256"]), "Invalid source")
    seen = set()
    for key, entry in entries.items():
        need(isinstance(key, str) and key == normalize(key) and bool(tokens(key)), "Invalid canonical key")
        need(isinstance(entry, dict) and set(entry) == {"original_forms", "source_refs"}, "Unexpected entry fields")
        forms, refs = entry["original_forms"], entry["source_refs"]
        need(isinstance(forms, list) and bool(forms) and all(isinstance(f, str) and normalize(f) == key for f in forms)
             and len(set(forms)) == len(forms), "Invalid original forms")
        need(isinstance(refs, list) and len(refs) >= len(forms), "Missing source occurrences")
        for ref in refs:
            need(isinstance(ref, dict) and set(ref) == {"batch", "source_line"} and ref["batch"] in sources
                 and type(ref["source_line"]) is int and ref["source_line"] >= 4, "Invalid source reference")
            identity = (ref["batch"], ref["source_line"])
            need(identity not in seen, "Duplicate source occurrence")
            seen.add(identity)


def compile_workbench(corpus: dict, proposals: dict) -> dict:
    """Compile one row per observed canonical phrase; input assertions confer no authority."""
    _validate_corpus(corpus)
    need(isinstance(proposals, dict) and set(proposals) == {"version", "scope", "proposed_on", "proposals"},
         "Unexpected proposal document fields")
    need(type(proposals["version"]) is int and proposals["version"] == 1 and proposals["scope"] == SCOPE
         and proposals["proposed_on"] == DAY and isinstance(proposals["proposals"], list), "Invalid proposal document")
    schema = parse_json_bytes(Path(__file__).with_name("research.schema.json").read_bytes())
    services = set(schema["$defs"]["services"]["items"]["enum"])
    assessments = {}
    for proposal in proposals["proposals"]:
        need(isinstance(proposal, dict) and set(proposal) == PROPOSAL_FIELDS, "Unexpected proposal fields")
        for field in ("text", "intent", "reason"):
            need(isinstance(proposal[field], str) and bool(proposal[field].strip()), "Missing " + field)
        key = normalize(proposal["text"])
        need(key in corpus["entries"], "Proposal absent from observed corpus: " + key)
        need(key not in assessments, "Duplicate canonical proposal: " + key)
        need(proposal["disposition"] in DISPOSITIONS, "Unsupported disposition")
        selected = proposal["possible_services"]
        need(isinstance(selected, list) and all(isinstance(s, str) and s in services for s in selected)
             and len(set(selected)) == len(selected), "Invalid possible services")
        protection = proposal["protect_against_generic"]
        need(isinstance(protection, list) and all(isinstance(s, str) and bool(tokens(s)) for s in protection)
             and len(set(map(normalize, protection))) == len(protection), "Invalid generic protection")
        scope = proposal["negative_scope_proposal"]
        if proposal["disposition"] == "NEGATIVE_EXACT_REVIEW":
            need(isinstance(scope, dict) and scope == NEGATIVE_SCOPE and scope["approved"] is False,
                 "Negative proposal must retain unapproved empty campaign scope and EXACT")
        else:
            need(scope is None, "Only negative proposals may propose scope")
        assessments[key] = deepcopy(proposal)

    queue = []
    for key, entry in sorted(corpus["entries"].items()):
        assessment = assessments.get(key)
        disposition = assessment["disposition"] if assessment else "UNASSESSED"
        queue.append({"queue_id": "INTERNAL-" + hashlib.sha256(key.encode("utf-8")).hexdigest(),
                      "normalized_text": key, **deepcopy(entry), "disposition": disposition,
                      "assessment": assessment,
                      "admission_gates": {gate: "NOT_VERIFIED" for gate in sorted(ADMISSION_PURPOSES)}
                      if disposition == "POSITIVE_REVIEW" else None})
    protected = {k for k, p in assessments.items() if p["disposition"] == "POSITIVE_REVIEW" or
                 (p["disposition"] == "HOLD" and p["protect_against_generic"])}
    exact_tests = []
    for key, proposal in sorted(assessments.items()):
        if proposal["disposition"] != "NEGATIVE_EXACT_REVIEW":
            continue
        hits = [query for query in sorted(corpus["entries"]) if negative_matches(key, "EXACT", query)]
        exact_tests.append({"negative": key, "negative_scope_proposal": deepcopy(NEGATIVE_SCOPE),
                            "observed_phrases_tested": len(corpus["entries"]), "observed_lexical_matches": hits,
                            "protected_lexical_collisions": sorted(set(hits) & protected)})
    generic = sorted({normalize(term) for p in assessments.values() for term in p["protect_against_generic"]})
    unsafe_tests = [{"attempted_generic": term, "hypothetical_match_type": "BROAD",
                     "protected_phrases_tested": len(protected),
                     "protected_lexical_collisions": [q for q in sorted(protected) if negative_matches(term, "BROAD", q)],
                     "legitimate_exclusion": False, "scope_approved": False} for term in generic]
    counts = Counter(row["disposition"] for row in queue)
    return {"version": 1, "scope": SCOPE, "proposed_on": DAY, "sources": deepcopy(corpus["sources"]),
            "queue": queue,
            "summary": {"unique_phrases": len(queue), "source_occurrences": sum(len(r["source_refs"]) for r in queue),
                        "dispositions": {state: counts[state] for state in sorted(DISPOSITIONS | {"UNASSESSED"})},
                        "reviewed_positive": 0, "reviewed_negative": 0, "approved_positive": 0,
                        "approved_negative": 0, "deployed": 0, "master_additions": 0},
            "controls": {"reviewed": False, "approved": False, "deployed": False, "master_additions": 0,
                         "deployment_authorized": False, "live_campaign_changes": False},
            "diagnostics": {"basis": "CONSERVATIVE_LEXICAL_ONLY_NOT_PLATFORM_MATCHING",
                            "scope_verified": False, "protected_phrases": sorted(protected),
                            "exact_negative_tests": exact_tests, "unsafe_generic_tests": unsafe_tests}}

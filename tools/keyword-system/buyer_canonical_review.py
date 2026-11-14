"""Source-bound wording comparisons and explicit AI review; never admission.

Candidate keys are deliberately attention-only. They preserve transaction and
constraint words; numbered names are not bedroom counts. Components are not
canonical entities, distinct keywords, platform equivalence or merge authority.
"""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re

import buyer_full_intent_review as full

ROOT = Path(__file__).resolve().parents[2]
FOLDER = "docs/audit/keyword-buyer-canonical-review-2026-11-13"
MANUAL_SHA256 = "9dfcd707cd01f876c1f451590865997261e156a63960dd3f08263e11df7d6471"
OUTPUT_PINS = {"candidates.json": "1e73e554543e27c70fadcd386ee33dea7c70057f345358f8b9ea8f57e85c7230", "review.json": "e49efc10088d3d20fc12f188c96086035d80bc0abf3b7956ae2be2ab151095ac"}
DEPENDENCIES = {
    "tools/keyword-system/buyer_full_intent_review.py": "0286c12e037e949491f31027417ae74fbe1f790b57dc819f1e05a494d9d204b0",
    "tools/keyword-system/source_membership_diagnostic.py": "bd8bafb4c49d23185b8cff91112e1c79679ae39bd9def9974e6d911ed891e41c",
}
OLD_METHODS = full.prior.buyer.lexical.METHODS + ("in_preposition_omission_attention",)
NEW_METHODS = ("inflection_room_format_attention", "apartment_vocabulary_attention", "bhk_definition_attention")
METHODS = OLD_METHODS + NEW_METHODS
PLURALS = {"apartments": "apartment", "flats": "flat", "villas": "villa", "houses": "house",
           "homes": "home", "townhouses": "townhouse", "townhomes": "townhome", "penthouses": "penthouse",
           "properties": "property", "condos": "condo", "condominiums": "condominium",
           "duplexes": "duplex", "bedrooms": "bedroom", "beds": "bed"}
NUMBER_WORDS = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6"}
ROOM_WORDS = {"bed", "beds", "bedroom", "bedrooms", "br", "bhk"}
COMPACT_ROOM = re.compile(r"([1-9][0-9]?)(bhk|br|bed|bedroom|bedrooms)\Z")
DECISIONS = {
    "EXACT_SOURCE_WORDING_REUSE_ONLY": "Same retained wording in another research source; no new literal, approval or mapping inherited.",
    "REVIEWED_SURFACE_INTENT_VARIANTS_PENDING_SUBJECT": "Complete wording supports the same preliminary purchase/development decision with surface order/format/inflection variation. Actual entity, asset, quantity, subject and business scope remain unverified; no canonical merge.",
    "HOLD_ENTITY_OR_LOCATION_RELATION": "A named location, entity spelling/segmentation or attachment needs factual subject disambiguation before a canonical decision.",
    "HOLD_ROOM_OR_PROPERTY_DEFINITION": "BHK/bedroom, property vocabulary, quantity or asset-definition differences need subject/family review; shared keys do not prove equivalence.",
    "HOLD_ROLE_OR_CONSTRAINT_MEANING": "Role, transaction or constraint context is unresolved; preserve every source and hold for full subject review.",
}


def need(condition, code):
    if not condition:
        raise ValueError(code)


def room_tokens(text):
    original = full.prior.ka.tokens(text)
    words = []
    for i, token in enumerate(original):
        compact = COMPACT_ROOM.fullmatch(token)
        if compact:
            words.extend((compact.group(1), compact.group(2)))
        elif token in NUMBER_WORDS and i + 1 < len(original) and original[i + 1] in ROOM_WORDS:
            words.append(NUMBER_WORDS[token])
        elif token == "realestate":
            words.extend(("real", "estate"))
        elif token == "offplan":
            words.extend(("off", "plan"))
        else:
            words.append(token)
    result = []; i = 0
    while i < len(words):
        if i + 1 < len(words) and words[i] == "town" and words[i + 1] in ("house", "houses"):
            result.append("townhouse"); i += 2
        else:
            result.append(PLURALS.get(words[i], words[i])); i += 1
    return result


def candidate_keys(text):
    old = full.prior.buyer.attention_keys(text)
    formatted = room_tokens(text)
    apartment = [("apartment" if w in ("flat", "apt") else
                  "bedroom" if w in ("bed", "br") and i > 0 and formatted[i - 1].isdigit() else w)
                 for i, w in enumerate(formatted)]
    bhk = ["bedroom" if w == "bhk" and i > 0 and apartment[i - 1].isdigit() else w
           for i, w in enumerate(apartment)]
    # Omitting only 'in' is an existing review-attention method, not a match rule.
    return old + tuple(tuple(sorted(w for w in values if w != "in"))
                       for values in (formatted, apartment, bhk))


def load_material():
    for path, expected in DEPENDENCIES.items():
        need(hashlib.sha256(full.prior.buyer.read_bound(ROOT / path)).hexdigest() == expected,
             "DEPENDENCY_PIN_CHANGED")
    material = full.load_material()
    expected = full.assemble(*material)
    for name, pin in full.OUTPUT_PINS.items():
        blob = full.prior.buyer.read_bound(ROOT / full.FOLDER / name)
        need(hashlib.sha256(blob).hexdigest() == pin, "COMPLETE_PRELIMINARY_OUTPUT_PIN_CHANGED")
        need(full.prior.buyer.sd._exact(full.prior.ka.parse_json_bytes(blob), expected[name]),
             "COMPLETE_PRELIMINARY_FRESH_SOURCE_MISMATCH")
    return material, expected


def candidate_graph(review, reconciliation):
    rows = review["records"]
    source = {"s:" + str(r["source_ordinal"]): r for r in rows}
    external = {"e:" + r["reference"]: r for r in reconciliation["external_literal_references"]}
    literals = {key: row["original_literal"] for key, row in {**source, **external}.items()}
    indexes = {method: defaultdict(list) for method in METHODS}
    for identity, literal in literals.items():
        for method, key in zip(METHODS, candidate_keys(literal)):
            indexes[method][key].append(identity)
    adj = defaultdict(set)
    # Star links retain complete key membership without an unnecessary clique.
    memberships = []
    for method in METHODS:
        for key, members in indexes[method].items():
            if len(members) < 2:
                continue
            ordered = sorted(members)
            memberships.append({"method": method, "members": ordered})
            for identity in ordered[1:]:
                a, b = ordered[0], identity
                adj[a].add(b); adj[b].add(a)
    seen = set(); groups = []
    buyer_ids = {key for key, row in source.items() if row["decision"] == full.DEFAULT}
    for start in sorted(adj):
        if start in seen:
            continue
        todo = [start]; component = []; seen.add(start)
        while todo:
            identity = todo.pop(); component.append(identity)
            for peer in sorted(adj[identity]):
                if peer not in seen:
                    seen.add(peer); todo.append(peer)
        buyers = sorted(int(key[2:]) for key in component if key in buyer_ids)
        if not buyers:
            continue
        members = set(component)
        ordinals = sorted(int(key[2:]) for key in members if key.startswith("s:"))
        refs = sorted(key for key in members if key.startswith("e:"))
        groups.append({"buyer_ordinals": buyers, "source_ordinals": ordinals,
                       "external_references": [key[2:] for key in refs],
                       "source_literals": [{key: source["s:" + str(n)][key] for key in
                                            ("source_ordinal", "original_literal", "decision")} for n in ordinals],
                       "external_literals": [external[key] for key in refs],
                       "key_memberships": [m for m in memberships if set(m["members"]) <= members],
                       "held_source_peer_ordinals": [n for n in ordinals if "s:" + str(n) not in buyer_ids]})
    groups.sort(key=lambda g: min(g["buyer_ordinals"]))
    for i, group in enumerate(groups, 1):
        group["component_id"] = "BUYER-COMP-" + str(i).zfill(3)
    grouped = {n for group in groups for n in group["buyer_ordinals"]}
    unmatched = sorted(int(key[2:]) for key in buyer_ids if int(key[2:]) not in grouped)
    return {"schema_version": 1, "scope": "COMPLETE_CANDIDATE_COMPARISON_NOT_CANONICAL_MERGE",
            "complete_preliminary_review_sha256": full.OUTPUT_PINS["review.json"],
            "counts": {"source_occurrences_compared": len(source), "external_literal_forms_compared": len(external),
                       "conditional_buyer_occurrences_compared": len(buyer_ids), "components": len(groups),
                       "buyer_occurrences_in_components": len(grouped), "unmatched_buyer_occurrences": len(unmatched),
                       "held_source_peers": sum(len(g["held_source_peer_ordinals"]) for g in groups)},
            "methods": list(METHODS), "components": groups, "unmatched_buyer_ordinals": unmatched,
            "controls": {"all_source_peers_compared": True, "groups_are_candidate_context_not_entities": True,
                         "semantic_equivalence_verified": False, "google_matching_equivalence_verified": False,
                         "automatic_canonical_merge_allowed": False, "confirmed_novel_canonicals": None,
                         "held_peers_promoted": False, "actual_campaign_or_page_mapping_verified": False,
                         "positive_admissions_added": 0, "negative_changes": 0, "deployment_authorized": False}}


def build_candidates():
    material, outputs = load_material()
    return candidate_graph(outputs["review.json"], material[3])


def build_outputs():
    graph = build_candidates()
    blob = full.prior.buyer.read_bound(ROOT / FOLDER / "manual-review.json")
    need(hashlib.sha256(blob).hexdigest() == MANUAL_SHA256, "MANUAL_REVIEW_PIN_CHANGED")
    manual = full.prior.ka.parse_json_bytes(blob)
    need(manual["reviewer"] == "Lead AI — wording context only, not independent human approval" and
         manual["reviewed_on_dubai"] == "2026-11-13" and
         manual["complete_preliminary_review_sha256"] == full.OUTPUT_PINS["review.json"] and
         manual["all_component_literals_and_peers_read"] is True,
         "MANUAL_REVIEW_SCOPE_CHANGED")
    need([r["component_id"] for r in manual["decisions"]] == [g["component_id"] for g in graph["components"]],
         "MANUAL_COMPONENT_COVERAGE_CHANGED")
    reviewed = []
    for decision, group in zip(manual["decisions"], graph["components"]):
        need(set(decision) == {"component_id", "buyer_ordinals", "source_ordinals", "external_references", "decision", "review_note"} and
             isinstance(decision["review_note"], str) and bool(decision["review_note"].strip()) and
             decision["decision"] in DECISIONS and
             full.prior.buyer.sd._exact(decision["buyer_ordinals"], group["buyer_ordinals"]) and
             full.prior.buyer.sd._exact(decision["source_ordinals"], group["source_ordinals"]) and
             full.prior.buyer.sd._exact(decision["external_references"], group["external_references"]),
             "MANUAL_COMPLETE_CONTEXT_BINDING_CHANGED")
        if decision["decision"] == "EXACT_SOURCE_WORDING_REUSE_ONLY":
            exact_source = {full.prior.ka.normalize(r["original_literal"]) for r in group["source_literals"]}
            exact_external = {full.prior.ka.normalize(r["original_literal"]) for r in group["external_literals"]}
            need(bool(exact_source) and exact_source <= exact_external and len(exact_source) == 1,
                 "EXACT_REUSE_REQUIRES_COMPLETE_LITERAL_MATCH")
        need(not group["held_source_peer_ordinals"] or decision["decision"].startswith("HOLD_"),
             "HELD_SOURCE_PEER_CONTEXT_MUST_REMAIN_HELD")
        reviewed.append(dict(decision, rationale=DECISIONS[decision["decision"]],
                             subject_identity_verified=False, canonical_merge_approved=False,
                             independent_approval=False, positive_admission_granted=False))
    review = {"schema_version": 1, "scope": "LEAD_AI_WORDING_CONTEXT_REVIEW_NOT_CANONICAL_OR_BUSINESS_ADMISSION",
              "manual_sha256": MANUAL_SHA256, "complete_preliminary_review_sha256": full.OUTPUT_PINS["review.json"],
              "complete_candidate_graph_sha256": full.prior.buyer.digest(graph),
              "counts": graph["counts"], "decision_counts": dict(sorted(Counter(r["decision"] for r in reviewed).items())),
              "reviewed_components": reviewed, "unmatched_buyer_ordinals": graph["unmatched_buyer_ordinals"],
              "controls": graph["controls"], "reviewer": manual["reviewer"], "reviewed_on_dubai": manual["reviewed_on_dubai"],
              "limits": "Complete literals and all component peers were read. Wording context does not prove actual entity/asset/quantity or service scope. Components are transitive candidate contexts, never automatic equivalence or canonical counts. Unmatched remains unproven novel; retain every metric/variant and complete the existing subject-bound/actual-scope reviews before admission."}
    return {"candidates.json": graph, "review.json": review}


def validate_outputs(outputs):
    need(full.prior.buyer.sd._exact(outputs, build_outputs()), "CANONICAL_REVIEW_DIFFERS_FROM_FRESH_INPUTS")


def verify_saved():
    outputs = {}
    for name, pin in OUTPUT_PINS.items():
        blob = full.prior.buyer.read_bound(ROOT / FOLDER / name)
        need(hashlib.sha256(blob).hexdigest() == pin, "OUTPUT_PIN_CHANGED")
        outputs[name] = full.prior.ka.parse_json_bytes(blob)
    validate_outputs(outputs)
    return {"passed": True, "counts": outputs["review.json"]["counts"],
            "decision_counts": outputs["review.json"]["decision_counts"], "deployment_authorized": False}


if __name__ == "__main__":
    try:
        print(json.dumps(verify_saved(), sort_keys=True))
    except Exception as error:
        print(json.dumps({"passed": False, "code": "BUYER_CANONICAL_REVIEW_FAILED",
                          "error_type": type(error).__name__, "deployment_authorized": False}))
        raise SystemExit(1)

"""Complete preliminary literal review; canonical/business admission stays held.

Retain the earlier400-row assessment verbatim, add the remaining2795 inspected
literals, and expose a candidate work queue without merging concepts or claiming
stock, scope, current exclusion acceptance or independent approval.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path

import buyer_intent_review as prior

ROOT = Path(__file__).resolve().parents[2]
FOLDER = "docs/audit/keyword-buyer-complete-intent-review-2026-11-13"
MANUAL = FOLDER + "/manual-classifications.json"
MANUAL_SHA256 = "54b34e15cef5bfe60d0756bc37f3a3b9e3b757c7e568d9a7a3fa0fcd33806183"
OUTPUT_PINS = {"review.json": "e0f89ea7c1d63bddcc12365b3bf434ec73f668ecd780a451934e05f7ad51df6d", "canonical-queue.json": "adebcb2173c3c423844589bddaf37caa757d833c379feffb02f0b08248f47833"}
DEFAULT = "CONDITIONAL_PROPERTY_BUYER_RESEARCH"
RENAMES = {prior.DEFAULT: DEFAULT,
           "BROKER_SELECTION_ROLE_UNRESOLVED_HOLD": "PROPERTY_SERVICE_SELECTION_ROLE_UNRESOLVED_HOLD",
           "COMMERCIAL_LAND_OR_BUILDING_SCOPE_HOLD": "OTHER_ASSET_OR_COMMERCIAL_SCOPE_HOLD"}
DEPENDENCIES = {
    "tools/keyword-system/buyer_intent_review.py": "ee74db4b373d0693c459ec5dd12ccad2484bfcb71704e45da99024ac50cb44e4",
    "tools/keyword-system/buyer_negative_conflicts.py": "c3faf9a64bbd93aaff8b0686f4fb9208fb9c159b496ba041ed0a7fc951b0b90b",
}
REASONS = {RENAMES.get(key, key): value for key, value in prior.REASONS.items()}
REASONS.update({
    DEFAULT: "Complete wording supports a preliminary property purchase, development or investment research hypothesis. Asset family, canonical identity, actual stock/services, rights, claims, language and destination remain unverified.",
    "AMBIGUOUS_PROPERTY_ENTITY_OR_PRICE_HOLD": "A name, price, location, profile, definition, reported transaction or mixed-role topic alone does not establish a buyer decision or available stock. Disambiguate the full literal and subject; do not invent an entity or buyer.",
    "PROPERTY_SERVICE_SELECTION_ROLE_UNRESOLVED_HOLD": "Selection of a property service/company/provider may concern different roles and capabilities; verify the decision and genuine service before mapping.",
    "OTHER_ASSET_OR_COMMERCIAL_SCOPE_HOLD": "Commercial premises, land, whole buildings/floors or specialized assets such as floating villas, islands, farms and hotel-apartment investments need specific asset/service, authority and operational review. This is a scope hold, not a verified legal asset classification.",
    "FINANCE_INTERNATIONAL_OR_STALE_CONTEXT_HOLD": "Funding, investment-product or tenure models, ownership/registration rules, distress/urgency, country/currency or an old year need dated subject evidence and commercial/legal review. No legal, finance, availability or current-claim conclusion.",
    "NON_PROPERTY_TRANSACTION_SCOPE_HOLD": "Wording concerns acquisition of a real-estate company/business, not a property listing. Keep outside the property-transaction implementation; no Business Setup workflow or exclusion is created.",
    "EVENT_PURPOSE_OR_SHORT_STAY_SERVICE_HOLD": "Explicit party/event, holiday or daily-accommodation purpose needs a separately supported service/operator, rights, business case and booking acceptance. This phrase is not a confirmed booking or an ordinary tenant-funnel mapping.",
})


def need(condition, code):
    if not condition:
        raise ValueError(code)


def load_material():
    """Read all pinned inputs fresh; reuse loaded data within this invocation only."""
    for path, expected in DEPENDENCIES.items():
        need(hashlib.sha256(prior.buyer.read_bound(ROOT / path)).hexdigest() == expected,
             "DEPENDENCY_PIN_CHANGED")
    material = prior.load_material()
    old_blob = prior.buyer.read_bound(ROOT / prior.REPORT)
    need(hashlib.sha256(old_blob).hexdigest() == prior.REPORT_SHA256, "PRIOR_REVIEW_PIN_CHANGED")
    old = prior.ka.parse_json_bytes(old_blob)
    need(prior.buyer.sd._exact(old, prior.assemble(*material)), "PRIOR_REVIEW_FRESH_SOURCE_MISMATCH")
    blob = prior.buyer.read_bound(ROOT / MANUAL)
    need(hashlib.sha256(blob).hexdigest() == MANUAL_SHA256, "MANUAL_PIN_CHANGED")
    manual = prior.ka.parse_json_bytes(blob)
    need(prior.buyer.sd._exact(manual["label_refinements"], RENAMES), "LABEL_REFINEMENT_CHANGED")
    need((manual["source_occurrences"], manual["complete_literals_preliminarily_reviewed"],
          manual["prior_complete_literals_retained"], manual["additional_complete_literals_read"],
          manual["outside_cohort_occurrences_unassessed"]) == (3195, 3195, 400, 2795, 0),
         "COMPLETE_REVIEW_POPULATIONS_CHANGED")
    return manual, material[1], material[2], material[3], old


def assemble(manual, batch, negative, reconciliation, old):
    assignments = {}
    for category, ordinals in manual["explicit_exception_ordinals"].items():
        need(category in REASONS and category != DEFAULT and type(ordinals) is list,
             "UNSUPPORTED_REVIEW_CATEGORY")
        for ordinal in ordinals:
            need(type(ordinal) is int and 1 <= ordinal <= 3195 and ordinal not in assignments,
                 "INVALID_OR_OVERLAPPING_REVIEW_ORDINAL")
            assignments[ordinal] = category
    cohorts = manual["review_cohorts"]; expected = 1
    for cohort in cohorts:
        need(type(cohort["first"]) is int and type(cohort["last"]) is int
             and cohort["first"] == expected and cohort["last"] >= expected, "GAPPED_REVIEW_COHORTS")
        expected = cohort["last"] + 1
    need(expected == 3196 and len(cohorts) == 7, "INCOMPLETE_REVIEW_COHORTS")
    rows = batch["source_projection"]["records"]
    need(len(rows) == len(reconciliation["source_occurrences"]) == 3195, "COMPLETE_CAPTURE_REQUIRED")
    records = []; queue = []
    for ordinal, row in enumerate(rows, 1):
        literal = row["values"]["Keyword"]; category = assignments.get(ordinal, DEFAULT)
        joined = reconciliation["source_occurrences"][ordinal - 1]
        need(joined["source_ordinal"] == ordinal and joined["source_line"] == row["source_line"]
             and joined["original_literal"] == literal, "SOURCE_RECONCILIATION_CHANGED")
        inherited = old["records"][ordinal - 1] if ordinal <= 400 else None
        if inherited is not None:
            need(inherited["original_literal"] == literal
                 and category == RENAMES.get(inherited["decision"], inherited["decision"]),
                 "PRIOR_400_CLASSIFICATION_CHANGED")
        records.append({"source_ordinal": ordinal, "source_line": row["source_line"],
                        "original_literal": literal, "complete_public_values_sha256": prior.buyer.digest(row["values"]),
                        "source_kind": "RESEARCH_HYPOTHESIS", "decision": category, "rationale": REASONS[category],
                        "retained_prior_decision": None if inherited is None else inherited["decision"],
                        "lexical_attention_required": joined["lexical_attention_required"],
                        "canonical_novelty": "UNRESOLVED_NOT_COUNTED", "asset_family": None,
                        "primary_campaign": None, "ad_group": None, "native_page": None,
                        "actual_volume": None, "actual_cpc": None, "business_evidence_verified": False,
                        "five_subject_bound_reviews_complete": False, "admitted": False,
                        "approved": False, "deployed": False})
        if category == DEFAULT:
            exact_refs = joined["joins"][0]["external_references"]
            queue.append({"source_ordinal": ordinal, "source_line": row["source_line"], "original_literal": literal,
                          "priority": "EXISTING_LITERAL_CONTEXT" if exact_refs else
                                      "VARIANT_CONTEXT" if joined["lexical_attention_required"] else
                                      "UNASSESSED_SEMANTIC_CANONICAL_CONTEXT",
                          "joins": joined["joins"], "canonical_decision": "UNRESOLVED",
                          "confirmed_novel_canonical": None, "positive_admission_granted": False})
    counts = dict(sorted(Counter(r["decision"] for r in records).items()))
    need(prior.buyer.sd._exact(counts, manual["category_counts"]), "CATEGORY_COUNTS_CHANGED")
    controls = {"all_complete_literals_preliminarily_assessed": True, "all_source_occurrences_retained": True,
                "semantic_canonicalization_complete": False, "full_admission_review_complete": False,
                "independent_human_review_complete": False, "business_evidence_verified": False,
                "five_subject_bound_reviews_complete": False, "actual_campaign_or_page_mapping_assigned": False,
                "fresh_applicable_exclusion_scope_acceptance": False, "negative_exclusions_proposed": False,
                "positive_master_changed": False, "negative_master_changed": False, "deployment_authorized": False}
    review = {"schema_version": 1, "scope": "COMPLETE_PRELIMINARY_LITERAL_REVIEW_NOT_CANONICAL_OR_BUSINESS_ADMISSION",
              "source": {"public_capture_sha256": manual["source_public_sha256"],
                         "manual_sha256": MANUAL_SHA256, "prior_400_review_sha256": prior.REPORT_SHA256,
                         "prior_400_manual_sha256": prior.MANUAL_SHA256,
                         "reconciliation_sha256": prior.buyer.REPORT_SHA256,
                         "recorded_all_source_negative_screen_sha256": prior.screen.REPORT_SHA256},
              "reviewer": manual["reviewer"], "reviewed_on_dubai": manual["reviewed_on_dubai"],
              "counts": {"source_occurrences": 3195, "complete_literals_preliminarily_reviewed": 3195,
                         "prior_complete_literals_retained": 400, "additional_complete_literals_read": 2795,
                         "outside_cohort_occurrences_unassessed": 0, "conditional_buyer_research": len(queue),
                         "other_review_holds": 3195 - len(queue), "categories": counts,
                         "confirmed_novel_canonicals": None, "positive_admissions_added": 0,
                         "independent_approvals_added": 0, "deployed_added": 0},
              "label_refinements": RENAMES, "review_cohorts": cohorts, "records": records,
              "controls": controls,
              "negative_evidence_limit": "The unchanged pinned screen is prior local all-source evidence, not a cached verdict for admission. Actual applicable scope must be bound and freshly tested before any admission/export.",
              "next_requirements": ["Resolve canonical/variant decisions using all source peers, prior candidates and source metrics without automatic merges",
                                    "Complete genuine inventory/service, language, landing-page, claims and intent/geography subject-bound reviews",
                                    "Bind actual proposed campaign/ad-group/native-page and every applicable exclusion, then freshly screen",
                                    "Obtain independent approval and separate production/tracking/Ads/spending authorization after all release gates"]}
    work = {"schema_version": 1, "scope": "UNAPPROVED_CANONICAL_WORK_QUEUE_NOT_DISTINCT_KEYWORD_LIBRARY",
            "manual_sha256": MANUAL_SHA256, "source_occurrences": 3195,
            "conditional_candidate_occurrences": len(queue),
            "prior_literal_context_rows": sum(r["priority"] == "EXISTING_LITERAL_CONTEXT" for r in queue),
            "variant_context_rows": sum(r["priority"] == "VARIANT_CONTEXT" for r in queue),
            "unassessed_canonical_context_rows": sum(r["priority"] == "UNASSESSED_SEMANTIC_CANONICAL_CONTEXT" for r in queue),
            "confirmed_novel_canonicals": None, "candidate_occurrences": queue,
            "controls": controls,
            "limits": "All existing four lexical keys and the attention-only in-preposition key are retained. Every peer, including held source rows, participates. A shared key is not semantic or Google equivalence. Unmatched is not novel; do not sum source estimates or count a work item as an admitted keyword."}
    return {"review.json": review, "canonical-queue.json": work}


def build_outputs():
    return assemble(*load_material())


def validate_outputs(outputs):
    need(prior.buyer.sd._exact(outputs, build_outputs()), "FULL_REVIEW_DIFFERS_FROM_FRESH_PINNED_INPUTS")


def verify_saved():
    outputs = {}
    for name, expected in OUTPUT_PINS.items():
        blob = prior.buyer.read_bound(ROOT / FOLDER / name)
        need(hashlib.sha256(blob).hexdigest() == expected, "OUTPUT_PIN_CHANGED")
        outputs[name] = prior.ka.parse_json_bytes(blob)
    validate_outputs(outputs)
    return {"passed": True, "scope": outputs["review.json"]["scope"],
            "counts": outputs["review.json"]["counts"], "deployment_authorized": False}


if __name__ == "__main__":
    try:
        print(json.dumps(verify_saved(), sort_keys=True))
    except Exception as error:
        print(json.dumps({"passed": False, "code": "BUYER_COMPLETE_INTENT_REVIEW_FAILED",
                          "error_type": type(error).__name__, "deployment_authorized": False}))
        raise SystemExit(1)

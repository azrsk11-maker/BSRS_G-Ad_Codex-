"""Reproduce a bounded AI literal review, not the positive admission engine."""
from collections import Counter
import hashlib
import json
from pathlib import Path

import buyer_source_reconciliation as buyer
import buyer_negative_conflicts as screen
import keyword_audit as ka

ROOT = Path(__file__).resolve().parents[2]
FOLDER = "docs/audit/keyword-buyer-intent-review-2026-11-13"
MANUAL = FOLDER + "/manual-classifications.json"
MANUAL_SHA256 = "43d33ba277dd3fd0e8d874f67cff288d51514de430e26f16e183afd7e908df7d"
REPORT = FOLDER + "/review.json"
REPORT_SHA256 = "484e1389b36736e9b6bdc3036ae316869fee041cad02b4e78d14b424ad9d9d06"
DEFAULT = "CONDITIONAL_RESIDENTIAL_BUYER_RESEARCH"
REASONS = {
    DEFAULT: "Complete wording supports a preliminary residential purchase, off-plan/new-development or investment research hypothesis; actual service, named subject, stock, claims, language, canonical identity and destination remain unverified.",
    "AMBIGUOUS_PROPERTY_ENTITY_OR_PRICE_HOLD": "Entity, property, locality, price or availability wording alone does not establish the role or transaction. Retain for factual and intent review; no verified entity or inventory claim.",
    "TENANT_RENTAL_RESEARCH_HOLD": "Wording concerns renting rather than the buyer funnel. Consider the appropriate tenant service only after its own evidence and mapping; small stated prices are source wording, not availability or an exclusion.",
    "PORTAL_OR_PROVIDER_NAVIGATION_REVIEW_HOLD": "A portal/provider/competitor reference needs navigation-versus-comparison and commercial-fit review. This is not a brand exclusion or permission to use another party's assets.",
    "COMMERCIAL_LAND_OR_BUILDING_SCOPE_HOLD": "Commercial premises, land or whole-building research needs the appropriate separate planning family and genuine service/mandate evidence; do not silently route to a residential page.",
    "OWNER_SELLER_RESEARCH_HOLD": "Explicit property-selling wording supports an owner-service hypothesis, not a buyer-funnel mapping; seller scope and authority remain unverified.",
    "BROKER_SELECTION_ROLE_UNRESOLVED_HOLD": "Broker selection may concern different audience roles. Verify the decision and service before choosing a campaign or page.",
    "DIRECT_OWNER_COMMERCIAL_FIT_HOLD": "Buyer wording seeks an owner-direct transaction. Verify brokerage fit and lawful authority; do not mislabel this as an owner's enquiry or add a negative automatically.",
    "FINANCE_INTERNATIONAL_OR_STALE_CONTEXT_HOLD": "Funding promises, repossession, foreign-buyer process, currency/origin or an old year need specific dated evidence and commercial/jurisdiction review. No financing, availability, conversion-rate or current-claim inference.",
}


def need(condition, code):
    if not condition:
        raise ValueError(code)


def load_material():
    buyer.verify_report()
    batch, _, _, _ = buyer.load_inputs()
    manual_blob = buyer.read_bound(ROOT / MANUAL)
    need(hashlib.sha256(manual_blob).hexdigest() == MANUAL_SHA256, "MANUAL_REVIEW_PIN_CHANGED")
    manual = ka.parse_json_bytes(manual_blob)
    need(manual["reviewed_source_occurrences"] == 400 and manual["source_ordinal_first"] == 1
         and manual["source_ordinal_last"] == 400 and manual["outside_cohort_occurrences_unassessed"] == 2795
         and manual["full_capture_occurrences"] == 3195 and manual["default_for_inspected_cohort_only"] == DEFAULT,
         "REVIEW_COHORT_CHANGED")
    blob = buyer.read_bound(ROOT / screen.REPORT)
    need(hashlib.sha256(blob).hexdigest() == screen.REPORT_SHA256, "RECORDED_NEGATIVE_SCREEN_PIN_CHANGED")
    negative = ka.parse_json_bytes(blob)
    need(negative["inputs"]["complete_current_negative_sha256"] == screen.CURRENT_SHA256
         and negative["counts"]["source_occurrences_screened"] == 3195
         and negative["counts"]["current_potential_conflict_rows"] == 0,
         "RECORDED_NEGATIVE_SCREEN_CHANGED")
    reconciliation = ka.parse_json_bytes(buyer.read_bound(ROOT / buyer.REPORT))
    need(hashlib.sha256(buyer.read_bound(ROOT / buyer.REPORT)).hexdigest() == buyer.REPORT_SHA256,
         "BUYER_RECONCILIATION_PIN_CHANGED")
    return manual, batch, negative, reconciliation


def assemble(manual, batch, negative, reconciliation):
    assignments = {}
    for category, ordinals in manual["explicit_exception_ordinals"].items():
        need(category in REASONS and category != DEFAULT and type(ordinals) is list,
             "UNSUPPORTED_REVIEW_CATEGORY")
        for ordinal in ordinals:
            need(type(ordinal) is int and 1 <= ordinal <= 400 and ordinal not in assignments,
                 "INVALID_OR_OVERLAPPING_REVIEW_ORDINAL")
            assignments[ordinal] = category
    result = []
    rows = batch["source_projection"]["records"]
    need(len(rows) == 3195, "COMPLETE_CAPTURE_REQUIRED")
    for ordinal, row in enumerate(rows[:400], 1):
        category = assignments.get(ordinal, DEFAULT)
        literal = row["values"]["Keyword"]
        source_join = reconciliation["source_occurrences"][ordinal - 1]
        need(source_join["source_ordinal"] == ordinal and source_join["original_literal"] == literal,
             "REVIEW_SOURCE_RECONCILIATION_CHANGED")
        result.append({"source_ordinal": ordinal, "source_line": row["source_line"],
                       "original_literal": literal, "complete_public_values_sha256": buyer.digest(row["values"]),
                       "source_kind": "RESEARCH_HYPOTHESIS", "decision": category,
                       "rationale": REASONS[category],
                       "lexical_attention_required": source_join["lexical_attention_required"],
                       "known_normalized_literal_matches_historical": source_join["normalized_literal_matches_historical"],
                       "known_normalized_literal_matches_prior_capture": source_join["normalized_literal_matches_prior_capture"],
                       "canonical_novelty": "UNRESOLVED_NOT_COUNTED", "primary_campaign": None,
                       "ad_group": None, "native_page": None, "actual_volume": None, "actual_cpc": None,
                       "five_subject_bound_reviews_complete": False, "admitted": False,
                       "approved": False, "deployed": False})
    counts = dict(sorted(Counter(r["decision"] for r in result).items()))
    need(buyer.sd._exact(counts, dict(sorted(manual["category_counts"].items()))), "MANUAL_CATEGORY_COUNTS_CHANGED")
    return {"schema_version": 1, "scope": "FIRST_400_COMPLETE_LITERALS_LEAD_AI_PRELIMINARY_REVIEW_ONLY",
            "source": {"public_capture_sha256": "2876c299228dff45b764a0b85f43ac9de316153dae846c372ebcea889ddbff89",
                       "manual_classification_sha256": MANUAL_SHA256,
                       "reconciliation_sha256": buyer.REPORT_SHA256,
                       "recorded_full_negative_screen_sha256": screen.REPORT_SHA256},
            "reviewer": manual["reviewer"], "reviewed_on_dubai": manual["review_date_dubai"],
            "counts": {"full_capture_occurrences": 3195, "complete_literals_preliminarily_reviewed": 400,
                       "outside_cohort_occurrences_unassessed": 2795, "conditional_buyer_research": counts[DEFAULT],
                       "held_for_other_review": 400 - counts[DEFAULT], "categories": counts,
                       "positive_admissions_added": 0, "independent_approvals_added": 0,
                       "exclusions_proposed": 0, "deployed_added": 0},
            "records": result,
            "controls": {"source_order_and_complete_literals_retained": True,
                         "full_capture_semantic_review_complete": False, "semantic_canonicalization_complete": False,
                         "independent_human_review_complete": False, "business_evidence_verified": False,
                         "five_subject_bound_reviews_complete": False, "actual_campaign_mapping_assigned": False,
                         "actual_exclusion_scope_bound": False, "deployment_authorized": False,
                         "positive_master_changed": False, "negative_master_changed": False},
            "negative_evidence_limit": "Pinned receipt of the separate full fresh reconstruction and all3195-row screen. This fast semantic-review verifier does not repeat current history and grants no current scope or admission acceptance.",
            "required_next": ["Read the remaining2795 complete source literals without assuming this first cohort is representative",
                              "Resolve canonical/variant relationships without dropping original source occurrences or summing metrics",
                              "Complete the existing inventory/service, language, landing-page, claims and intent/geography subject-bound reviews",
                              "Bind actual proposed campaign/ad-group/page and applicable exclusions, then freshly screen before admission",
                              "Obtain independent review and separate production/Ads authorizations after all release gates pass"]}


def build_review():
    return assemble(*load_material())


def validate_review(review):
    need(buyer.sd._exact(review, build_review()), "REVIEW_DIFFERS_FROM_PINNED_COMPLETE_LITERALS")


def verify_saved():
    blob = buyer.read_bound(ROOT / REPORT)
    need(hashlib.sha256(blob).hexdigest() == REPORT_SHA256, "REVIEW_REPORT_PIN_CHANGED")
    review = ka.parse_json_bytes(blob)
    validate_review(review)
    return {"passed": True, "counts": review["counts"], "deployment_authorized": False,
            "full_capture_semantic_review_complete": False}


if __name__ == "__main__":
    try:
        print(json.dumps(verify_saved(), sort_keys=True))
    except Exception as error:
        print(json.dumps({"passed": False, "code": "BUYER_INTENT_REVIEW_FAILED",
                          "error_type": type(error).__name__, "deployment_authorized": False}))
        raise SystemExit(1)

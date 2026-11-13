"""Reproduce held workorders for genuine historical owner-service candidates.

This is an intake aid, not a second admission engine. Actual completed reviews
must use keyword_audit's five subject-bound reviews and content-evidence checks.
The default two-seed packet stays unchanged. Explicit selections remain held.
No file writer, network call, master update or platform export is provided.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import historical_intake
import keyword_audit

ROOT = Path(__file__).resolve().parents[2]
HISTORY = "tools/keyword-system/staging/historical-intake.json"
HISTORY_SHA256 = "2fb4fc05496184628c6cab7e900f4bf4c62426e0a84f8c8f9c73302f3f76308e"
PACKET = "docs/audit/positive-service-intake-2026-11-11/packet.json"
SEEDS = {"LEGACY-POS-0030": "sell my property dubai",
         "LEGACY-POS-0036": "rent out my property dubai"}
REQUIREMENTS = {
    "inventory_service": ["Dated evidence of the actual lawful advisory or owner-mandate service and supported property scope",
                          "Applicable authority, mandates and permit requirements; no individual property claim without its evidence"],
    "language": ["Verified language support across the exact ad, page and staff sales workflow"],
    "landing_page": ["Reviewed campaign/ad-group/page binding and actual native WordPress destination",
                     "Versioned page content and relevant functional, consent and CTA acceptance evidence"],
    "claims": ["Exact proposed ad/page claims with dated evidence and asset rights where relevant"],
    "intent_geography": ["Reviewed owner-service intent, family/signals, destination emirates, audience origin and supported segment"],
}


def canonical_sha256(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def load_history(content):
    if hashlib.sha256(content).hexdigest() != HISTORY_SHA256:
        raise ValueError("Historical intake bytes differ from the reviewed source")
    history = keyword_audit.parse_json_bytes(content)
    historical_intake.validate_intake(history)
    if len(history["candidates"]) != 41 or len(history["placements"]) != 82:
        raise ValueError("Canonical candidate and placement populations changed")
    return history


def build_packet(root=ROOT, candidate_ids=None):
    """Freshly bind source and immutable specification; never claim eligibility."""
    root = Path(root)
    history = load_history((root / HISTORY).read_bytes())
    contract = keyword_audit.load_positive_contract(root / "docs/google-ads")
    if set(REQUIREMENTS) != keyword_audit.ADMISSION_PURPOSES:
        raise ValueError("Intake purposes differ from the real admission contract")
    candidates = {row["candidate_id"]: row for row in history["candidates"]}
    placements = {row["placement_id"]: row for row in history["placements"]}
    selected = list(SEEDS) if candidate_ids is None else candidate_ids
    if (not isinstance(selected, list) or not selected
            or any(not isinstance(identity, str) for identity in selected)
            or len(set(selected)) != len(selected)):
        raise ValueError("Select unique nonempty historical candidate IDs")
    if any(identity not in candidates for identity in selected):
        raise ValueError("Unknown historical candidate ID")
    # These evidence requirements are owner-service specific. Historical role
    # is a selection boundary, never a current campaign or service approval.
    for identity in selected:
        if any(placements[p]["original_keyword_fields"]["Campaign"] != "BSRE_SEARCH_OWNERS_EN"
               for p in candidates[identity]["placement_ids"]):
            raise ValueError("Owner-service workorders require historical owner placements")
    # Stable source order prevents caller ordering from changing the workorder.
    selected = [identity for identity in candidates if identity in selected]
    rows = []
    for identity in selected:
        candidate = candidates[identity]
        literal = candidate["original_text"]
        if identity in SEEDS and (literal != SEEDS[identity] or candidate["normalized_text"] != SEEDS[identity]):
            raise ValueError("Selected seed no longer matches its observed literal")
        occurrences = []
        for placement_id in candidate["placement_ids"]:
            placement = placements[placement_id]
            occurrences.append({"placement_id": placement_id,
                                "placement_sha256": canonical_sha256(placement),
                                "keyword_source_locator": placement["keyword_source_locator"],
                                "metadata_source_locator": placement["metadata_source_locator"],
                                "historical_match_type": placement["original_keyword_fields"]["Criterion Type"]})
        rows.append({"candidate_id": identity, "original_text": literal,
                     "source_candidate_sha256": canonical_sha256(candidate),
                     "historical_occurrences": occurrences,
                     "status": "HELD_MISSING_BUSINESS_EVIDENCE_AND_BINDINGS",
                     "binding_overlay_required": dict.fromkeys([
                         "primary_campaign_key", "ad_group_key", "landing_page_id", "family_code",
                         "signal_ids", "property_destination", "audience_origin", "language",
                         "property_segment", "transaction_intent", "intent_tier", "actual_landing_url",
                         "actual_google_campaign_id", "context_evidence_ref", "context_reviewed_on",
                         "context_valid_until", "research_source_observed_on", "volume", "cpc"]),
                     "admission_reviews_required": {purpose: {
                         "status": "NOT_REVIEWED", "reviewer": None, "evidence_ref": None,
                         "source_id": None, "reviewed_on": None, "valid_until": None,
                         "subject_sha256": None, "required_evidence": REQUIREMENTS[purpose]}
                         for purpose in sorted(keyword_audit.ADMISSION_PURPOSES)}})
    return {"schema": "bsre-positive-service-intake-workorder-v1", "evidence_intake_only": True,
            "scope": ("TWO_EXISTING_CANONICAL_SEEDS_NOT_MASTER_OR_LAUNCH_COHORT" if candidate_ids is None
                      else "SELECTED_HISTORICAL_OWNER_CANDIDATES_NOT_MASTER_OR_LAUNCH_COHORT"),
            "source": {"path": HISTORY, "raw_sha256": HISTORY_SHA256,
                       "archive_sha256": history["source"]["archive_sha256"],
                       "canonical_candidates": 41, "historical_placements": 82,
                       "freshness_verified": False},
            "source_contract_sha256": contract["source_sha256"],
            "ownership_decision_ref": "docs/decisions/OWNER_DECISIONS.md#dec-02-factual-ownership-and-private-evidence-location--11-november-2026-dubai",
            "nominated_factual_reviewer_and_update_owner": "Amit",
            "private_evidence_location_reference": "BSRE-EVIDENCE-ROOT-20261111",
            "review_semantics": {"admission_function": "keyword_audit.validate_positive_admission",
                                 "subject_function": "keyword_audit.positive_admission_subject",
                                 "content_function": "content_evidence.evaluate_content_evidence",
                                 "completed_review_requires": ["PASS", "named reviewer", "dated non-hypothesis source", "freshness window", "exact subject hash"],
                                 "language_extra_field": "ad_page_sales_supported=true",
                                 "service_offer_basis_options": ["advisory_offer", "owner_mandate_service", "verified_inventory"],
                                 "specific_inventory_required_for_generic_service": False},
            "rows": rows,
            "counts": {"selected_canonical_seeds": len(rows),
                       "historical_occurrences": sum(len(row["historical_occurrences"]) for row in rows),
                       "reviewed_positive_contribution": 0, "approved_contribution": 0, "deployed_contribution": 0},
            "deployment_export_allowed": False, "production_authorization": False,
            "limits": ["Source consistency does not authenticate business evidence, reviewer credentials or regulatory compliance",
                       "Historical campaigns, match placements and proposed URLs do not assign current 360/V2/live ownership",
                       "Nominating Amit grants no folder/workbook permission and approves no claim or page",
                       "Complete real reviews through the existing admission contract; this generated workorder is not an editable approval document"]}


def verify_packet(content, root=ROOT, candidate_ids=None):
    expected = build_packet(root, candidate_ids)
    actual = keyword_audit.parse_json_bytes(content)
    if actual != expected:
        raise ValueError("Intake packet differs from freshly reconstructed source-bound held workorder")
    return {"status": "PASS_INTAKE_CONSISTENCY_ONLY", **expected["counts"],
            "business_evidence_accepted": False, "master_admission_allowed": False,
            "deployment_export_allowed": False, "packet_canonical_sha256": canonical_sha256(actual)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", type=Path, default=ROOT / PACKET)
    parser.add_argument("--candidate-id", action="append", help="Existing historical owner candidate ID; repeat for a selected workorder")
    parser.add_argument("--emit-workorder", action="store_true", help="Print held source-bound workorder instead of a verification receipt")
    args = parser.parse_args()
    if args.emit_workorder:
        result = build_packet(candidate_ids=args.candidate_id)
    else:
        result = verify_packet(args.verify.read_bytes(), candidate_ids=args.candidate_id)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()

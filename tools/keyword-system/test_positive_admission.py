"""Synthetic-only admission fixtures; never business facts or actual approvals."""
import copy
from datetime import date
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import keyword_audit as ka

TODAY = date(2026, 11, 7)


def complete_sources(rows):
    result = copy.deepcopy(rows)
    result.append({"source_id": "QA-ADMISSION-SOURCE", "kind": "first_party_observed", "approved_for_research": True,
                   "evidence_ref": "TEST_ONLY:simulated-business-review", "observed_on": "2026-11-01", "valid_until": "2026-12-01"})
    return result


def complete_campaigns(rows):
    result = copy.deepcopy(rows)
    for row in result:
        row.update(family_code="RNT", property_destination=["Dubai"], audience_origin="UAE", language="en")
    return result


def complete_positive(row, campaigns, contexts, sources):
    """Refresh synthetic review evidence explicitly after a fixture edit."""
    result = copy.deepcopy(row)
    additions = {"family_code": "RNT", "signal_ids": ["SIG-013"], "property_destination": ["Dubai"],
                 "audience_origin": "UAE", "property_segment": "residential_rental", "transaction_intent": "TEST_ONLY:annual tenancy enquiry",
                 "intent_tier": "TEST_ONLY:immediate rental requirement"}
    for key, value in additions.items():
        result.setdefault(key, value)
    result["admission_reviews"] = {purpose: {"status": "PASS", "reviewer": "qa-admission-reviewer",
                                          "evidence_ref": "TEST_ONLY:" + purpose, "source_id": "QA-ADMISSION-SOURCE",
                                          "reviewed_on": "2026-11-02", "valid_until": "2026-12-01"} for purpose in ka.ADMISSION_PURPOSES}
    result["admission_reviews"]["inventory_service"]["offer_basis"] = "advisory_offer"
    result["admission_reviews"]["language"]["ad_page_sales_supported"] = True
    campaign = next((item for item in campaigns if item["campaign_key"] == result["primary_campaign_key"]), {})
    context = next((item for item in contexts if item["campaign_key"] == result["primary_campaign_key"]), {})
    digest = ka.positive_admission_subject(result, campaign, context, sources, ka.load_positive_contract())
    for review in result["admission_reviews"].values():
        review["subject_sha256"] = digest
    return result


def fixture():
    sources = complete_sources([{"source_id": "QA-SOURCE", "kind": "research_hypothesis", "approved_for_research": True,
                                 "evidence_ref": "TEST_ONLY:source", "observed_on": "2026-11-01", "valid_until": "2026-12-01"}])
    campaigns = complete_campaigns([{"campaign_key": "QA-C1", "landing_page_id": "QA-LP1"}])
    contexts = [{"campaign_key": "QA-C1", "services": ["residential_rental"], "evidence_ref": "TEST_ONLY:scope",
                 "reviewed_on": "2026-11-01", "valid_until": "2026-12-01"}]
    row = {"keyword_id": "QA-P1", "original_text": "apartment rental near school", "language": "en", "match_type": "PHRASE",
           "source_id": "QA-SOURCE", "source_reference": "TEST_ONLY:reference", "evidence_ref": "TEST_ONLY:research",
           "review_state": "REVIEWED", "reviewer": "qa-researcher", "reviewed_on": "2026-11-01", "valid_until": "2026-12-01",
           "volume": None, "cpc": None, "primary_campaign_key": "QA-C1", "ad_group_key": "QA-G1", "landing_page_id": "QA-LP1"}
    return complete_positive(row, campaigns, contexts, sources), sources, campaigns, contexts


def run(row, sources, campaigns, contexts):
    return ka.audit("positive", [row], sources, campaigns, contexts, [], TODAY)


class PositiveAdmissionTests(unittest.TestCase):
    def assertHeld(self, values):
        result = run(*values)
        self.assertEqual(result["reviewed_eligible_rows"], 0)
        self.assertFalse(result["exact_target_pass"])
        self.assertFalse(result["deployment_export_allowed"])
        return result

    def test_source_contract_read_not_invented_or_copied_taxonomy(self):
        contract = ka.load_positive_contract()
        self.assertEqual(len(contract["signals"]), 70)
        self.assertEqual(len(contract["families"]), 15)
        self.assertEqual(len(contract["destinations"]), 7)
        self.assertEqual(sum(item["positive_research_target"] for item in contract["families"].values()), 14000)
        self.assertEqual(contract["signals"]["SIG-013"]["signal"], "Bedrooms and household requirements")
        self.assertEqual(len(contract["source_sha256"]), 4)

    def test_source_contract_loaded_once_per_audit_not_per_keyword(self):
        row, sources, campaigns, contexts = fixture()
        rows = []
        for number in range(3):
            candidate = copy.deepcopy(row)
            candidate["keyword_id"] = "QA-P" + str(number)
            candidate["original_text"] += " synthetic" + str(number)
            rows.append(complete_positive(candidate, campaigns, contexts, sources))
        with mock.patch.object(ka, "load_positive_contract", wraps=ka.load_positive_contract) as loader:
            result = ka.audit("positive", rows, sources, campaigns, contexts, [], TODAY)
        self.assertEqual(result["reviewed_eligible_rows"], 3)
        self.assertEqual(loader.call_count, 1)

    def test_complete_research_admission_remains_not_live_or_full_master(self):
        values = fixture()
        before = copy.deepcopy(values)
        result = run(*values)
        self.assertTrue(result["structural_pass"])
        self.assertEqual(result["reviewed_eligible_rows"], 1)
        self.assertEqual(result["deficit"], 13999)
        self.assertFalse(result["exact_target_pass"])
        self.assertFalse(result["production_writes_available"])
        self.assertIn("hypothesis", result["records"][0]["warnings"][0])
        self.assertEqual(values, before)

    def test_every_new_field_is_mandatory_not_silently_defaulted(self):
        for key in ka.POSITIVE_FIELDS - {"primary_campaign_key", "ad_group_key", "landing_page_id"}:
            values = fixture()
            values[0].pop(key)
            with self.subTest(key=key):
                self.assertHeld(values)

    def test_unknown_family_signal_segment_and_destination_hold(self):
        for field, value in [("family_code", "UNKNOWN"), ("signal_ids", ["SIG-999"]), ("signal_ids", ["SIG-013", "SIG-013"]),
                             ("property_segment", "property_management"), ("property_destination", ["London"]),
                             ("property_destination", ["Dubai", "Dubai"]), ("intent_tier", "SOURCE_REQUIRED")]:
            row, sources, campaigns, contexts = fixture()
            row[field] = value
            row = complete_positive(row, campaigns, contexts, sources)
            with self.subTest(field=field, value=value):
                self.assertHeld((row, sources, campaigns, contexts))

    def test_planning_nulls_do_not_become_approved_business_bindings(self):
        for field in ["family_code", "property_destination", "audience_origin", "language"]:
            row, sources, campaigns, contexts = fixture()
            campaigns[0][field] = None
            row = complete_positive(row, campaigns, contexts, sources)
            self.assertHeld((row, sources, campaigns, contexts))

    def test_origin_is_separate_from_destination_and_needs_review(self):
        row, sources, campaigns, contexts = fixture()
        row["audience_origin"] = campaigns[0]["audience_origin"] = "TEST_ONLY:India-origin audience"
        row = complete_positive(row, campaigns, contexts, sources)
        self.assertTrue(run(row, sources, campaigns, contexts)["structural_pass"])
        row["property_destination"] = ["India"]
        row = complete_positive(row, campaigns, contexts, sources)
        self.assertHeld((row, sources, campaigns, contexts))

    def test_all_five_reviews_need_pass_not_missing_pending_or_fail(self):
        for purpose in ka.ADMISSION_PURPOSES:
            for mode in ["missing", "pending", "fail", "empty-evidence", "missing-reviewer"]:
                values = fixture()
                reviews = values[0]["admission_reviews"]
                if mode == "missing":
                    reviews.pop(purpose)
                elif mode in ["pending", "fail"]:
                    reviews[purpose]["status"] = mode.upper()
                elif mode == "empty-evidence":
                    reviews[purpose]["evidence_ref"] = ""
                else:
                    reviews[purpose].pop("reviewer")
                with self.subTest(purpose=purpose, mode=mode):
                    self.assertHeld(values)

    def test_invisible_control_and_punctuation_only_admission_text_hold(self):
        for text in ["\u200b", "\x00", "---"]:
            for field in ["reviewer", "evidence_ref", "intent_tier", "transaction_intent", "audience_origin"]:
                row, sources, campaigns, contexts = fixture()
                if field in ["reviewer", "evidence_ref"]:
                    row["admission_reviews"]["claims"][field] = text
                else:
                    row[field] = text
                    if field == "audience_origin":
                        campaigns[0][field] = text
                    row = complete_positive(row, campaigns, contexts, sources)
                with self.subTest(text=repr(text), field=field):
                    self.assertHeld((row, sources, campaigns, contexts))

    def test_legacy_positive_research_and_source_text_cannot_bypass_admission(self):
        fields = ["reviewer", "source_reference", "evidence_ref", "keyword_id", "ad_group_key", "primary_source", "context_source"]
        for text in ["\u200b", "\x00", "---", "reference\nsecond line"]:
            for field in fields:
                row, sources, campaigns, contexts = fixture()
                if field == "primary_source":
                    sources[0]["evidence_ref"] = text
                elif field == "context_source":
                    contexts[0]["evidence_ref"] = text
                else:
                    row[field] = text
                row = complete_positive(row, campaigns, contexts, sources)
                with self.subTest(text=repr(text), field=field):
                    self.assertHeld((row, sources, campaigns, contexts))

    def test_review_expiry_future_predating_and_source_expiry_hold(self):
        for field, value in [("valid_until", "2026-11-06"), ("reviewed_on", "2026-11-08"), ("reviewed_on", "2026-10-31")]:
            values = fixture()
            values[0]["admission_reviews"]["claims"][field] = value
            self.assertHeld(values)
        row, sources, campaigns, contexts = fixture()
        sources[1]["valid_until"] = "2026-11-06"
        row = complete_positive(row, campaigns, contexts, sources)
        self.assertHeld((row, sources, campaigns, contexts))

    def test_hypothesis_source_cannot_confirm_actual_service_language_or_claims(self):
        row, sources, campaigns, contexts = fixture()
        sources[1]["kind"] = "research_hypothesis"
        row = complete_positive(row, campaigns, contexts, sources)
        self.assertHeld((row, sources, campaigns, contexts))

    def test_admission_cannot_predate_primary_or_metric_evidence_even_if_rehashed(self):
        for evidence in ["primary", "metric"]:
            row, sources, campaigns, contexts = fixture()
            if evidence == "primary":
                sources[0]["observed_on"] = "2026-11-03"
            else:
                row["volume"] = 5
                row["metric_evidence"] = {"volume": {"provider": "TEST_ONLY:provider", "reference": "TEST_ONLY:metric",
                                                     "observed_on": "2026-11-03", "valid_until": "2026-12-01"}}
            row = complete_positive(row, campaigns, contexts, sources)
            self.assertHeld((row, sources, campaigns, contexts))

    def test_content_campaign_context_and_source_changes_break_review_binding(self):
        for kind in ["row", "campaign", "context", "source"]:
            row, sources, campaigns, contexts = fixture()
            if kind == "row":
                row["original_text"] += " today"
            elif kind == "campaign":
                campaigns[0]["evidence_version"] = "TEST_ONLY:changed"
            elif kind == "context":
                contexts[0]["evidence_ref"] += ":changed"
            else:
                sources[1]["evidence_ref"] += ":changed"
            with self.subTest(kind=kind):
                report = self.assertHeld((row, sources, campaigns, contexts))
                self.assertTrue(any("does not bind" in error for error in report["records"][0]["errors"]))

    def test_language_requires_complete_ad_page_sales_support(self):
        for code in ["en", "ar", "hi"]:
            row, sources, campaigns, contexts = fixture()
            row["language"] = campaigns[0]["language"] = code
            row = complete_positive(row, campaigns, contexts, sources)
            self.assertTrue(run(row, sources, campaigns, contexts)["structural_pass"])
            row["admission_reviews"]["language"]["ad_page_sales_supported"] = False
            self.assertHeld((row, sources, campaigns, contexts))
        row, sources, campaigns, contexts = fixture()
        row["language"] = campaigns[0]["language"] = "not a language tag"
        row = complete_positive(row, campaigns, contexts, sources)
        self.assertHeld((row, sources, campaigns, contexts))

    def test_inventory_advisory_and_owner_mandate_paths_without_fake_stock(self):
        for basis in ["verified_inventory", "advisory_offer", "owner_mandate_service"]:
            values = fixture()
            values[0]["admission_reviews"]["inventory_service"]["offer_basis"] = basis
            self.assertTrue(run(*values)["structural_pass"])
            self.assertNotIn("inventory_id", values[0])
        values = fixture()
        values[0]["admission_reviews"]["inventory_service"]["offer_basis"] = "unknown"
        self.assertHeld(values)

    def test_segment_requires_current_service_context(self):
        row, sources, campaigns, contexts = fixture()
        contexts[0]["services"] = ["commercial_ready"]
        row = complete_positive(row, campaigns, contexts, sources)
        self.assertHeld((row, sources, campaigns, contexts))

    def test_family_reconciliation_no_filler_or_silent_reallocation(self):
        contract = ka.load_positive_contract()
        empty = ka.positive_family_reconciliation([], contract)
        self.assertEqual(sum(row["deficit"] for row in empty["families"]), 14000)
        self.assertFalse(empty["exact_family_targets_pass"])
        excess = ka.positive_family_reconciliation([{"family_code": "RNT"}] * 1001, contract)
        self.assertFalse(excess["within_allocations"])
        self.assertEqual(next(row for row in excess["families"] if row["family_code"] == "RNT")["excess"], 1)
        # Count arithmetic only, explicitly synthetic; no keyword text or approval produced.
        counts = [{"family_code": code} for code, family in contract["families"].items() for _ in range(family["positive_research_target"])]
        self.assertTrue(ka.positive_family_reconciliation(counts, contract)["exact_family_targets_pass"])
        counts[0]["family_code"] = "RNT"
        self.assertFalse(ka.positive_family_reconciliation(counts, contract)["exact_family_targets_pass"])

    def test_modified_immutable_source_fails_checksum(self):
        original = Path(ka.__file__).resolve().parents[2] / "docs" / "google-ads"
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ["artifact_manifest.json", "company_config.json", "page_family_allocation.json", "positive_intent_taxonomy.json"]:
                (root / name).write_bytes((original / name).read_bytes())
            (root / "positive_intent_taxonomy.json").write_bytes(b"[]")
            with self.assertRaisesRegex(ValueError, "source hash mismatch"):
                ka.load_positive_contract(root)
        values = fixture()
        with mock.patch.object(ka, "load_positive_contract", side_effect=OSError("TEST_ONLY:missing spec")):
            self.assertHeld(values)

    def test_schema_and_runtime_positive_fields_match(self):
        schema = json.loads(Path(ka.__file__).with_name("research.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(set(schema["$defs"]["positive"]["required"]), ka.POSITIVE_FIELDS)
        reviews = schema["$defs"]["positive"]["properties"]["admission_reviews"]
        self.assertEqual(set(reviews["required"]), ka.ADMISSION_PURPOSES)


if __name__ == "__main__":
    unittest.main()

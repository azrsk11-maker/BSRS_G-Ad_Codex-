"""Synthetic-only adversarial tests. Fixtures are not research master rows."""
import copy
import csv
from datetime import date
import json
import os
from pathlib import Path
import tempfile
import unittest

import keyword_audit as ka
from test_positive_admission import complete_campaigns, complete_positive, complete_sources

TODAY = date(2026, 11, 7)
SOURCES = [{"source_id": "QA-SOURCE", "kind": "research_hypothesis", "approved_for_research": True,
            "evidence_ref": "TEST_ONLY:source-fixture", "observed_on": "2026-11-01", "valid_until": "2026-12-01"}]
CAMPAIGNS = [{"campaign_key": "QA-C1", "landing_page_id": "QA-LP1"}, {"campaign_key": "QA-C2", "landing_page_id": "QA-LP2"}]
CONTEXT = [{"campaign_key": key, "services": ["residential_rental"], "evidence_ref": "TEST_ONLY:scope",
            "reviewed_on": "2026-11-01", "valid_until": "2026-12-01"} for key in ["QA-C1", "QA-C2"]]
PROTECTED = [{"query_id": "QA-Q1", "text": "apartment rental near school", "campaign_keys": ["QA-C1", "QA-C2"],
              "services": ["residential_rental"], "must_serve": True, "evidence_ref": "TEST_ONLY:intent",
              "reviewed_on": "2026-11-01", "valid_until": "2026-12-01"}]
SCOPE_BINDINGS = {"account_id": "573-038-4686", "evidence_ref": "TEST_ONLY:account-not-live-verification",
                  "verified_on": "2026-11-01", "valid_until": "2026-12-01",
                  "campaigns": {"QA-C1": {"google_campaign_id": "1001", "evidence_ref": "TEST_ONLY:campaign",
                                           "ad_groups": {"QA-G1": {"google_ad_group_id": "2001", "evidence_ref": "TEST_ONLY:group"}}},
                                "QA-C2": {"google_campaign_id": "1002", "evidence_ref": "TEST_ONLY:campaign"}},
                  "shared_lists": {"QA-LIST": {"google_shared_list_id": "3001", "evidence_ref": "TEST_ONLY:list", "campaign_keys": ["QA-C1"]}}}
SOURCES = complete_sources(SOURCES)
CAMPAIGNS = complete_campaigns(CAMPAIGNS)


def positive():
    row = {"keyword_id": "QA-P1", "original_text": "apartment rental near school", "language": "en", "match_type": "PHRASE",
            "source_id": "QA-SOURCE", "source_reference": "TEST_ONLY:reference", "evidence_ref": "TEST_ONLY:review",
            "review_state": "REVIEWED", "reviewer": "qa-researcher", "reviewed_on": "2026-11-01", "valid_until": "2026-12-01",
            "volume": None, "cpc": None, "primary_campaign_key": "QA-C1", "ad_group_key": "QA-GROUP1", "landing_page_id": "QA-LP1"}
    return complete_positive(row, CAMPAIGNS, CONTEXT, SOURCES)


def negative():
    row = positive()
    for key in ka.POSITIVE_FIELDS:
        row.pop(key)
    row.update(keyword_id="QA-N1", negative_id="QA-N1", original_text="broker exam course", normalized_text="broker exam course",
               source_type="research_hypothesis", observed_query=None, observation_date=None, reason_code="ACADEMIC_ONLY",
               service_applicability=["residential_rental"], eligible_campaigns=["QA-C1"], ineligible_campaigns=["QA-C2"],
               scope_type="CAMPAIGN", scope_target={"campaign_key": "QA-C1"}, risk_level="LOW", protected_query_conflicts=[],
               estimated_lost_coverage=None, approval_state="APPROVED", approval_reference="TEST_ONLY:independent-review",
               approval_reviewer="qa-second-reviewer", approved_on="2026-11-02",
               deployed_resource_ids=[], deployed_at=None, rollback_reference=None)
    return row


def audit(kind, rows, **changes):
    inputs = dict(sources=copy.deepcopy(SOURCES), campaigns=copy.deepcopy(CAMPAIGNS), campaign_context=copy.deepcopy(CONTEXT),
                  protected_queries=copy.deepcopy(PROTECTED), at=TODAY)
    inputs["scope_bindings"] = copy.deepcopy(SCOPE_BINDINGS)
    inputs.update(changes)
    return ka.audit(kind, rows, **inputs)


class KeywordAuditTests(unittest.TestCase):
    def test_reviewed_count_separate_from_14000_and_deployment(self):
        report = audit("positive", [positive()])
        self.assertTrue(report["structural_pass"])
        self.assertEqual(report["reviewed_eligible_rows"], 1)
        self.assertEqual(report["deficit"], 13999)
        self.assertFalse(report["exact_target_pass"])
        self.assertFalse(report["deployment_export_allowed"])

    def test_empty_library_is_honest_deficit(self):
        report = audit("positive", [])
        self.assertEqual(report["reviewed_eligible_rows"], 0)
        self.assertEqual(report["deficit"], 14000)

    def test_nfkc_casefold_wrappers_and_language_do_not_create_unique(self):
        a, b = positive(), positive()
        a.update(original_text="[ＦＬＡＴ　ＤＵＢＡＩ]", match_type="EXACT")
        b.update(keyword_id="QA-P2", original_text='  "flat  dubai" ', language="ar")
        report = audit("positive", [a, b])
        self.assertEqual(report["distinct_nonblank_phrases"], 1)
        self.assertEqual(report["reviewed_eligible_rows"], 0)

    def test_wrappers_conflicting_with_match_type_hold(self):
        row = positive()
        row["original_text"] = "[apartment]"
        self.assertFalse(audit("positive", [row])["structural_pass"])

    def test_blank_placeholder_and_invisible_text_hold(self):
        for text in [" ", "SOURCE_REQUIRED", "apartment\u200brental", "[[apartment]]"]:
            row = positive()
            row["original_text"] = text
            with self.subTest(text=text):
                self.assertEqual(audit("positive", [row])["reviewed_eligible_rows"], 0)

    def test_candidate_rejected_held_do_not_count(self):
        for state in ["CANDIDATE", "REJECTED", "HELD"]:
            row = positive()
            row["review_state"] = state
            self.assertEqual(audit("positive", [row])["reviewed_eligible_rows"], 0)

    def test_stale_or_future_source_holds(self):
        for field, value in [("valid_until", "2026-11-06"), ("observed_on", "2026-11-08")]:
            sources = copy.deepcopy(SOURCES)
            sources[0][field] = value
            self.assertEqual(audit("positive", [positive()], sources=sources)["reviewed_eligible_rows"], 0)

    def test_missing_source_evidence_and_duplicate_source_id_hold(self):
        sources = copy.deepcopy(SOURCES)
        sources[0]["evidence_ref"] = ""
        self.assertFalse(audit("positive", [positive()], sources=sources)["structural_pass"])
        self.assertFalse(audit("positive", [positive()], sources=SOURCES + SOURCES)["structural_pass"])

    def test_wrong_page_and_unknown_campaign_hold(self):
        row = positive()
        row["landing_page_id"] = "QA-LP2"
        self.assertFalse(audit("positive", [row])["structural_pass"])
        row["primary_campaign_key"] = "UNKNOWN"
        self.assertFalse(audit("positive", [row])["structural_pass"])

    def test_duplicate_campaign_page_identity_holds(self):
        campaigns = copy.deepcopy(CAMPAIGNS)
        campaigns[1]["landing_page_id"] = "QA-LP1"
        self.assertFalse(audit("positive", [positive()], campaigns=campaigns)["structural_pass"])

    def test_invented_volume_and_nonfinite_cpc_hold(self):
        row = positive()
        row["volume"] = 100
        self.assertFalse(audit("positive", [row])["structural_pass"])
        row["volume"], row["cpc"] = None, float("inf")
        self.assertFalse(audit("positive", [row])["structural_pass"])

    def test_verified_metric_source_and_hypothesis_label_preserved(self):
        row = positive()
        row["volume"] = 100
        row["metric_evidence"] = {"volume": {"provider": "TEST_ONLY:provider", "reference": "TEST_ONLY:metric",
                                               "observed_on": "2026-11-01", "valid_until": "2026-12-01"}}
        row = complete_positive(row, CAMPAIGNS, CONTEXT, SOURCES)
        report = audit("positive", [row])
        self.assertTrue(report["structural_pass"])
        self.assertIn("hypothesis", report["records"][0]["warnings"][0])

    def test_valid_negative_narrow_scope(self):
        report = audit("negative", [negative()])
        self.assertTrue(report["structural_pass"])
        self.assertEqual(report["approved_exclusion_rows"], 1)

    def test_missing_live_binding_preserves_research_but_not_approval_readiness(self):
        report = audit("negative", [negative()], scope_bindings=None)
        self.assertEqual(report["reviewed_eligible_rows"], 1)
        self.assertEqual(report["approved_exclusion_rows"], 0)

    def test_wrong_account_unknown_adgroup_and_list_cannot_pass_approval_readiness(self):
        changes = [{"scope_type": "ACCOUNT", "scope_target": {"account_id": "WRONG_BUSINESS_ACCOUNT"},
                    "eligible_campaigns": ["QA-C1", "QA-C2"], "ineligible_campaigns": []},
                   {"scope_type": "AD_GROUP", "scope_target": {"campaign_key": "QA-C1", "ad_group_key": "UNKNOWN"}},
                   {"scope_type": "SHARED_LIST", "scope_target": {"list_key": "UNKNOWN"}}]
        for change in changes:
            row = negative()
            row.update(change)
            report = audit("negative", [row])
            self.assertEqual(report["reviewed_eligible_rows"], 1)
            self.assertEqual(report["approved_exclusion_rows"], 0)

    def test_verified_adgroup_list_and_account_scope_binding(self):
        changes = [{"scope_type": "ACCOUNT", "scope_target": {"account_id": "5730384686"},
                    "eligible_campaigns": ["QA-C1", "QA-C2"], "ineligible_campaigns": []},
                   {"scope_type": "AD_GROUP", "scope_target": {"campaign_key": "QA-C1", "ad_group_key": "QA-G1"}},
                   {"scope_type": "SHARED_LIST", "scope_target": {"list_key": "QA-LIST"}}]
        for change in changes:
            row = negative()
            row.update(change)
            self.assertEqual(audit("negative", [row])["approved_exclusion_rows"], 1)

    def test_shared_list_extra_association_holds(self):
        row = negative()
        row.update(scope_type="SHARED_LIST", scope_target={"list_key": "QA-LIST"})
        bindings = copy.deepcopy(SCOPE_BINDINGS)
        bindings["shared_lists"]["QA-LIST"]["campaign_keys"].append("QA-C2")
        self.assertEqual(audit("negative", [row], scope_bindings=bindings)["approved_exclusion_rows"], 0)

    def test_token_index_avoids_unrelated_lexical_comparisons(self):
        report = audit("negative", [negative()])
        self.assertEqual(report["lexical_comparisons_executed"], 0)
        self.assertFalse(report["positive_library_coverage_verified"])

    def test_platform_caps_hold_proposals_without_changing_research_target(self):
        account = [{"scope_type": "ACCOUNT", "scope_target": {}}] * 1001
        self.assertFalse(ka.proposed_capacity(account)["known_overflow_pass"])
        shared = [{"scope_type": "SHARED_LIST", "scope_target": {"list_key": "QA-LIST"}}] * 5001
        self.assertFalse(ka.proposed_capacity(shared)["known_overflow_pass"])
        lists = [{"scope_type": "SHARED_LIST", "scope_target": {"list_key": "QA-LIST-" + str(i)}} for i in range(21)]
        self.assertFalse(ka.proposed_capacity(lists)["known_overflow_pass"])
        campaign = [{"scope_type": "CAMPAIGN", "scope_target": {"campaign_key": "QA-C1"}}] * 10001
        self.assertFalse(ka.proposed_capacity(campaign)["known_overflow_pass"])
        self.assertFalse(ka.proposed_capacity([])["live_remaining_capacity_verified"])

    def test_unapproved_or_self_approved_negative_holds(self):
        row = negative()
        row["approval_state"] = "PENDING"
        report = audit("negative", [row])
        self.assertTrue(report["structural_pass"])
        self.assertEqual(report["reviewed_eligible_rows"], 1)
        self.assertEqual(report["approved_exclusion_rows"], 0)
        row["approval_state"], row["approval_reviewer"] = "APPROVED", row["reviewer"]
        self.assertEqual(audit("negative", [row])["approved_exclusion_rows"], 0)

    def test_scope_overlap_unknown_and_account_expansion_hold(self):
        for changes in [{"eligible_campaigns": ["QA-C1", "QA-C2"]}, {"eligible_campaigns": ["UNKNOWN"]},
                        {"scope_type": "ACCOUNT", "scope_target": {"account_id": "TEST_ONLY"}}]:
            row = negative()
            row.update(changes)
            self.assertFalse(audit("negative", [row])["structural_pass"])

    def test_missing_services_and_protected_coverage_hold(self):
        self.assertFalse(audit("negative", [negative()], campaign_context=[])["structural_pass"])
        self.assertFalse(audit("negative", [negative()], protected_queries=[])["structural_pass"])

    def test_stale_protected_corpus_holds(self):
        queries = copy.deepcopy(PROTECTED)
        queries[0]["valid_until"] = "2026-11-06"
        self.assertFalse(audit("negative", [negative()], protected_queries=queries)["structural_pass"])

    def test_protected_conflict_detected_even_when_declared_clear(self):
        row = negative()
        row.update(original_text="rental", normalized_text="rental", risk_level="HIGH")
        report = audit("negative", [row])
        self.assertFalse(report["structural_pass"])
        self.assertEqual(report["protected_conflicts"][0]["protected_query_id"], "QA-Q1")

    def test_campaign_exclusion_prevents_unrelated_query_conflict(self):
        queries = copy.deepcopy(PROTECTED)
        queries.append({**queries[0], "query_id": "QA-Q2", "text": "broker exam course", "campaign_keys": ["QA-C2"]})
        report = audit("negative", [negative()], protected_queries=queries)
        self.assertTrue(report["structural_pass"])
        self.assertEqual(report["protected_conflicts"], [])

    def test_negative_exact_phrase_broad_semantics(self):
        self.assertFalse(ka.negative_matches("office rent", "EXACT", "office rent dubai"))
        self.assertTrue(ka.negative_matches("office rent", "PHRASE", "best office rent dubai"))
        self.assertFalse(ka.negative_matches("office rent", "PHRASE", "rent an office"))
        self.assertTrue(ka.negative_matches("office rent", "BROAD", "rent an office"))
        self.assertFalse(ka.negative_matches("office", "EXACT", "offices"))

    def test_protected_token_needs_high_review_even_without_match(self):
        row = negative()
        row.update(original_text="salary broker annual", normalized_text="salary broker annual")
        self.assertFalse(audit("negative", [row])["structural_pass"])

    def test_false_deployed_state_holds(self):
        row = negative()
        row["deployed_resource_ids"] = ["invented"]
        self.assertFalse(audit("negative", [row])["structural_pass"])

    def test_malformed_scope_fails_closed(self):
        queries = copy.deepcopy(PROTECTED)
        queries[0]["campaign_keys"] = [["QA-C1"]]
        with self.assertRaises(ValueError):
            audit("negative", [negative()], protected_queries=queries)

    def test_csv_json_ingestion_keeps_original_and_typed_scope(self):
        row = negative()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "fixture.csv"
            encoded = {key: json.dumps(value) if key in ka.JSON_FIELDS else "" if value is None else value for key, value in row.items()}
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(encoded))
                writer.writeheader()
                writer.writerow(encoded)
            self.assertEqual(ka.read_records(path), [row])
            json_path = Path(folder) / "fixture.json"
            json_path.write_text(json.dumps([row]), encoding="utf-8")
            self.assertEqual(ka.read_records(json_path), [row])

    def test_duplicate_json_key_and_csv_header_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.json"
            path.write_text('[{"keyword_id":"one","keyword_id":"two"}]', encoding="utf-8")
            with self.assertRaises(ValueError):
                ka.read_records(path)
            path = Path(folder) / "bad.csv"
            path.write_text("keyword_id,keyword_id\none,two\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                ka.read_records(path)

    def test_output_cannot_overwrite_input_or_hardlink(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "input.json"
            path.write_text("[]", encoding="utf-8")
            with self.assertRaises(ValueError):
                ka.ensure_output_is_not_input(path, [path])
            alias = Path(folder) / "alias.json"
            os.link(path, alias)
            with self.assertRaises(ValueError):
                ka.ensure_output_is_not_input(alias, [path])
            self.assertEqual(path.read_text(encoding="utf-8"), "[]")

    def test_release_cannot_be_authorized_by_count_or_tests(self):
        good = {"kind": "positive", "reviewed_eligible_rows": 14000, "exact_target_pass": True, "structural_pass": True}
        negative_report = {**good, "kind": "negative"}
        gate = ka.release_gate(good, negative_report, {"decisions": {}})
        self.assertFalse(gate["deployment_export_allowed"])
        self.assertTrue(any("separate approval missing" in x for x in gate["reasons"]))
        approvals = {"decisions": {key: {"approved": True, "owner_decision_reference": "TEST_ONLY:not-authority"}
                                  for key in ["ads_settings_change", "budget", "page_publication", "live_tracking"]}}
        self.assertFalse(ka.release_gate(good, negative_report, approvals)["deployment_export_allowed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""Synthetic-only private historical-query adapter checks; no actual records."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import private_query_triage as adapter
from test_search_terms_intake import fixture, row, PRIVATE_METRIC


def proposal(text, disposition="HOLD", protect=None):
    return {"text": text, "disposition": disposition, "intent": "TEST_ONLY intent",
            "possible_services": ["residential_rental"] if disposition == "POSITIVE_REVIEW" else [],
            "reason": "TEST_ONLY requires independent factual admission and disclosure review",
            "negative_scope_proposal": copy.deepcopy(adapter.tw.NEGATIVE_SCOPE)
            if disposition == "NEGATIVE_EXACT_REVIEW" else None,
            "protect_against_generic": list(protect or [])}


def document(*items):
    return {"version": 1, "scope": adapter.tw.SCOPE, "proposed_on": adapter.tw.DAY,
            "proposals": list(items)}


class PrivateQueryTriageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "TEST_ONLY private source.csv"

    def write(self, rows):
        self.path.write_bytes(fixture(rows))

    def compile(self, doc, complete=True):
        before = self.path.read_bytes()
        result = adapter.compile_private_history(self.path, doc, complete)
        self.assertEqual(self.path.read_bytes(), before)
        return result

    def reject(self, doc, code="PRIVATE_HISTORY_PROPOSALS_INVALID", complete=True):
        with self.assertRaises(ValueError) as caught:
            self.compile(doc, complete)
        self.assertEqual(str(caught.exception), code)
        self.assertIsNone(caught.exception.__cause__)
        self.assertIsNone(caught.exception.__context__)

    def test_duplicate_forms_physical_refs_metric_and_placement_discard(self):
        first = row(" ＳＹＮＴＨＥＴＩＣ flat ", "TEST_ONLY_CAMPAIGN_SECRET", "TEST_ONLY_GROUP_SECRET")
        first[5] = PRIVATE_METRIC + "\nTEST_ONLY_second_metric_line"
        self.write([first, row("synthetic flat"), row("synthetic goods")])
        result = self.compile(document(proposal("synthetic flat", "POSITIVE_REVIEW"),
                                       proposal("synthetic goods", "NEGATIVE_EXACT_REVIEW")))
        wb = result["private_workbench"]
        item = next(r for r in wb["queue"] if r["normalized_text"] == "synthetic flat")
        self.assertEqual(item["original_forms"], [first[0], "synthetic flat"])
        self.assertEqual([r["source_line"] for r in item["source_refs"]], [4, 6])
        self.assertEqual(sum(len(r["source_refs"]) for r in wb["queue"]), 3)
        batch = "PRIVATE-REPORT-" + result["count_summary"]["source_sha256"]
        self.assertEqual(wb["sources"], {batch: {"file": self.path.name,
                                               "sha256": result["count_summary"]["source_sha256"]}})
        encoded = json.dumps(wb)
        for value in [PRIVATE_METRIC, "TEST_ONLY_CAMPAIGN_SECRET", "TEST_ONLY_GROUP_SECRET", str(self.path.parent)]:
            self.assertNotIn(value, encoded)
        self.assertEqual(wb["resource_identity_status"], "NOT_VERIFIED")
        self.assertTrue(wb["controls"]["private_only"])
        self.assertTrue(all(v == "NOT_VERIFIED" for v in item["admission_gates"].values()))

    def test_privacy_flag_union_auto_hold_and_manual_override_denial(self):
        flagged_placement = row("Synthetic ordinary", "TEST_ONLY_person@example.invalid")
        self.write([row("SYNTHETIC ordinary"), flagged_placement, row("synthetic remaining")])
        result = self.compile(document(proposal("synthetic remaining")))
        held = next(r for r in result["private_workbench"]["queue"]
                    if r["normalized_text"] == "synthetic ordinary")
        self.assertEqual(held["disposition"], "HOLD")
        self.assertEqual(held["assessment"]["text"], "SYNTHETIC ordinary")
        self.assertEqual(held["assessment"]["intent"], "DISCLOSURE_REVIEW_REQUIRED")
        self.assertEqual(held["assessment"]["reason"], adapter.PRIVACY_HOLD_REASON)
        self.assertEqual(held["assessment"]["possible_services"], [])
        self.assertIsNone(held["assessment"]["negative_scope_proposal"])
        self.assertIn("email_candidate", held["privacy_flags"])
        count = result["count_summary"]
        self.assertEqual(count["automatic_privacy_hold_identities"], 1)
        self.assertEqual(count["automatic_privacy_hold_occurrences"], 2)
        self.assertEqual(count["privacy_flagged_source_records"], 1)
        self.assertEqual(count["manual_disclosure_review_required_occurrences"], 3)
        for disposition in ["POSITIVE_REVIEW", "HOLD", "NEGATIVE_EXACT_REVIEW"]:
            self.reject(document(proposal("synthetic ordinary", disposition)),
                        "PRIVATE_HISTORY_PRIVACY_OVERRIDE_FORBIDDEN", False)

    def test_complete_default_partial_unassessed_and_boolean_requirement(self):
        self.write([row("synthetic first"), row("synthetic second")])
        self.reject(document(proposal("synthetic first")), "PRIVATE_HISTORY_INCOMPLETE_PROPOSALS")
        partial = self.compile(document(proposal("synthetic first")), False)
        self.assertEqual(partial["count_summary"]["unassessed_identities"], 1)
        self.assertFalse(partial["count_summary"]["complete_intent_triage"])
        self.assertEqual(sum(r["assessment"] is None for r in partial["private_workbench"]["queue"]), 1)
        complete = self.compile(document(proposal("synthetic first"), proposal("synthetic second")))
        self.assertTrue(complete["count_summary"]["complete_intent_triage"])
        for value in [None, 0, 1, "false"]:
            self.reject(document(), "PRIVATE_HISTORY_COMPLETENESS_TYPE", value)

    def test_unknown_duplicate_extra_authority_and_compiler_errors_are_redacted(self):
        self.write([row("synthetic first")])
        self.reject(document(proposal("TEST_ONLY_unknown_private_query")), "PRIVATE_HISTORY_UNKNOWN_QUERY")
        self.reject(document(proposal("synthetic first"), proposal("SYNTHETIC first")),
                    "PRIVATE_HISTORY_DUPLICATE_QUERY")
        attempts = [None, [], {**document(), "approved": True}]
        for field, value in [("approved", True), ("campaign_id", "TEST_ONLY_no_resource"),
                             ("volume", 9), ("source", str(self.path))]:
            item = proposal("synthetic first"); item[field] = value
            attempts.append(document(item))
        item = proposal("synthetic first"); item["possible_services"] = ["TEST_ONLY_invalid_service"]
        attempts.append(document(item))
        for attempt in attempts:
            self.reject(attempt)
        with patch.object(adapter.tw, "compile_workbench", side_effect=ValueError("TEST_ONLY_private_query_and_path")):
            self.reject(document(proposal("synthetic first")))
        with patch.object(adapter, "parse_search_terms", side_effect=ValueError("TEST_ONLY_private_query_and_path")):
            self.reject(document(), "PRIVATE_HISTORY_SOURCE_INVALID")

    def test_deepcopy_inputs_results_zero_authority_and_all_manual_review(self):
        self.write([row("synthetic flat")])
        doc = document(proposal("synthetic flat", "POSITIVE_REVIEW", ["synthetic"]))
        before = copy.deepcopy(doc)
        result = self.compile(doc)
        self.assertEqual(doc, before)
        wb = result["private_workbench"]
        for item in wb["queue"]:
            self.assertTrue(item["manual_disclosure_review_required"])
            self.assertFalse(item["resource_ids_verified"])
            for key in adapter.AUTHORITY:
                self.assertIs(item[key], False)
        self.assertTrue(wb["controls"]["unflagged_records_are_not_verified_safe"])
        wb["queue"][0]["assessment"]["protect_against_generic"].append("TEST_ONLY_mutation")
        wb["queue"][0]["original_forms"].clear()
        self.assertEqual(doc, before)
        again = self.compile(doc)
        self.assertEqual(again["private_workbench"]["queue"][0]["original_forms"], ["synthetic flat"])
        for key in ["reviewed_positive", "reviewed_negative", "approved_positive", "approved_negative",
                    "admitted_positive", "admitted_negative", "master_additions", "deployed"]:
            self.assertEqual(again["count_summary"][key], 0)
        for key in adapter.AUTHORITY:
            self.assertIs(again["count_summary"][key], False)

    def test_exact_scope_and_count_only_collision_diagnostics(self):
        self.write([row("synthetic flat"), row("synthetic-flat")])
        doc = document(proposal("synthetic flat", "POSITIVE_REVIEW", ["synthetic"]),
                       proposal("synthetic-flat", "NEGATIVE_EXACT_REVIEW"))
        result = self.compile(doc)
        count = result["count_summary"]
        self.assertEqual(count["exact_negative_candidate_identities"], 1)
        self.assertEqual(count["exact_lexical_match_instances"], 2)
        self.assertEqual(count["exact_protected_lexical_collision_instances"], 1)
        self.assertEqual(count["unsafe_generic_lexical_collision_instances"], 1)
        self.assertFalse(count["lexical_scope_verified"])
        for field, value in [("approved", True), ("approved", 0), ("type", "ACCOUNT"),
                             ("campaign_keys", ["TEST_ONLY_no_campaign"]), ("match_type", "BROAD")]:
            altered = copy.deepcopy(doc)
            altered["proposals"][1]["negative_scope_proposal"][field] = value
            self.reject(altered)
        self.assertEqual(set(count), adapter.COUNT_FIELDS | adapter.BOOLEAN_FIELDS | {"source_sha256"})
        self.assertTrue(all(type(v) in {str, int, bool} for v in count.values()))
        self.assertTrue(all(not isinstance(v, str) or key == "source_sha256" for key, v in count.items()))
        encoded = json.dumps(count)
        for private_value in ["synthetic", "synthetic flat", self.path.name, str(self.path), "PRIVATE-REPORT-", "INTERNAL-"]:
            self.assertNotIn(private_value, encoded)


if __name__ == "__main__":
    unittest.main()

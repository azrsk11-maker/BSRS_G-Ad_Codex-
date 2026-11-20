"""Synthetic preliminary triage fixtures, plus pinned public-capture coverage."""
import copy
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import triage_workbench as tw


def corpus():
    # TEST_ONLY, never a research master or platform identifier.
    return {"sources": {"TEST_ONLY_A": {"file": "TEST_ONLY/a.json", "sha256": "a" * 64},
                        "TEST_ONLY_B": {"file": "TEST_ONLY/b.json", "sha256": "b" * 64}},
            "entries": {
                "cheap flat": {"original_forms": ["[ＣＨＥＡＰ flat]", '"cheap flat"'],
                               "source_refs": [{"batch": "TEST_ONLY_A", "source_line": 4},
                                               {"batch": "TEST_ONLY_B", "source_line": 4}]},
                "cheap-flat": {"original_forms": ["cheap-flat"],
                               "source_refs": [{"batch": "TEST_ONLY_A", "source_line": 5}]},
                "hotel apartment": {"original_forms": ["hotel apartment"],
                                    "source_refs": [{"batch": "TEST_ONLY_A", "source_line": 6}]},
                "business bay office": {"original_forms": ["business bay office"],
                                        "source_refs": [{"batch": "TEST_ONLY_B", "source_line": 5}]},
                "unassessed": {"original_forms": ["unassessed"],
                               "source_refs": [{"batch": "TEST_ONLY_B", "source_line": 6}]}}}


def proposal(text, disposition="POSITIVE_REVIEW", protect=None):
    return {"text": text, "disposition": disposition, "intent": "TEST_ONLY preliminary intent",
            "possible_services": ["residential_rental"], "reason": "TEST_ONLY requires independent evidence",
            "negative_scope_proposal": copy.deepcopy(tw.NEGATIVE_SCOPE) if disposition == "NEGATIVE_EXACT_REVIEW" else None,
            "protect_against_generic": protect or []}


def document(*rows):
    return {"version": 1, "scope": tw.SCOPE, "proposed_on": tw.DAY, "proposals": list(rows)}


class TriageWorkbenchTests(unittest.TestCase):
    def test_exact_token_aliases_keep_order_and_independent_result_lists(self):
        result = tw.compile_workbench(corpus(), document(
            proposal("cheap flat", "NEGATIVE_EXACT_REVIEW"),
            proposal("cheap-flat", "NEGATIVE_EXACT_REVIEW")))
        first, second = result["diagnostics"]["exact_negative_tests"]
        self.assertEqual(first["observed_lexical_matches"], ["cheap flat", "cheap-flat"])
        self.assertEqual(second["observed_lexical_matches"], first["observed_lexical_matches"])
        first["observed_lexical_matches"].clear()
        self.assertEqual(second["observed_lexical_matches"], ["cheap flat", "cheap-flat"])

    def test_verified_capture_preserves_all_occurrences_without_metrics(self):
        result = tw.load_corpus(Path(__file__).resolve().parents[2])
        self.assertEqual(len(result["sources"]), 4)
        self.assertEqual(len(result["entries"]), 7705)
        self.assertEqual(sum(len(e["source_refs"]) for e in result["entries"].values()), 8778)
        self.assertTrue(all(set(e) == {"original_forms", "source_refs"} for e in result["entries"].values()))
        tw._validate_corpus(result)

    def test_verifier_failure_prevents_any_capture_read(self):
        verifier = SimpleNamespace(verify=Mock(return_value={"passed": False}))
        spec = SimpleNamespace(loader=SimpleNamespace(exec_module=Mock()))
        with patch.object(tw.importlib.util, "spec_from_file_location", return_value=spec), \
             patch.object(tw.importlib.util, "module_from_spec", return_value=verifier), \
             patch.object(Path, "read_bytes") as read:
            with self.assertRaisesRegex(ValueError, "verification did not pass"):
                tw.load_corpus(Path("TEST_ONLY_missing"))
        verifier.verify.assert_called_once_with()
        read.assert_not_called()

    def test_unicode_wrapper_identity_all_forms_and_zero_authority(self):
        source = corpus()
        before = copy.deepcopy(source)
        result = tw.compile_workbench(source, document(proposal('"ＣＨＥＡＰ   FLAT"', protect=["cheap"])))
        row = next(r for r in result["queue"] if r["normalized_text"] == "cheap flat")
        self.assertEqual(row["original_forms"], before["entries"]["cheap flat"]["original_forms"])
        self.assertEqual(len(row["source_refs"]), 2)
        self.assertEqual(set(row["admission_gates"]), tw.ADMISSION_PURPOSES)
        self.assertEqual(set(row["admission_gates"].values()), {"NOT_VERIFIED"})
        self.assertEqual(result["summary"]["dispositions"]["UNASSESSED"], 4)
        self.assertEqual(result["summary"]["source_occurrences"], 6)
        self.assertTrue(all(v is False or type(v) is int and v == 0 for v in result["controls"].values()))
        self.assertEqual(source, before)
        result["queue"][0]["original_forms"].append("mutation")
        self.assertEqual(source, before)

    def test_queue_ids_stable_across_input_order(self):
        first = tw.compile_workbench(corpus(), document())
        reversed_corpus = corpus()
        reversed_corpus["entries"] = dict(reversed(list(reversed_corpus["entries"].items())))
        self.assertEqual(first, tw.compile_workbench(reversed_corpus, document()))
        self.assertTrue(all(r["queue_id"].startswith("INTERNAL-") and len(r["queue_id"]) == 73 for r in first["queue"]))

    def test_duplicate_canonical_proposals_and_missing_observation_fail(self):
        for rows in [(proposal("cheap flat"), proposal("[ＣＨＥＡＰ flat]", "HOLD")), (proposal("invented phrase"),)]:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                tw.compile_workbench(corpus(), document(*rows))

    def test_approval_scope_metrics_and_service_tampering_fail(self):
        attempts = []
        for field, value in [("approved", True), ("reviewer", "invented"), ("volume", 100), ("match_type", "BROAD")]:
            item = proposal("cheap flat")
            item[field] = value
            attempts.append(document(item))
        for field, value in [("approved", True), ("approved", 0), ("campaign_keys", ["invented"]),
                             ("match_type", "BROAD"), ("type", "ACCOUNT")]:
            item = proposal("cheap-flat", "NEGATIVE_EXACT_REVIEW")
            item["negative_scope_proposal"][field] = value
            attempts.append(document(item))
        item = proposal("cheap flat")
        item["possible_services"] = ["business_setup"]
        attempts.append(document(item))
        item = document()
        item["approved"] = True
        attempts.append(item)
        for attempt in attempts:
            with self.subTest(attempt=attempt), self.assertRaises(ValueError):
                tw.compile_workbench(corpus(), attempt)

    def test_exact_negatives_check_whole_corpus_and_protection_without_scope_authority(self):
        result = tw.compile_workbench(corpus(), document(proposal("cheap flat", protect=["cheap"]),
            proposal("cheap-flat", "NEGATIVE_EXACT_REVIEW"),
            proposal("hotel apartment", "HOLD", ["hotel"]),
            proposal("business bay office", protect=["business"])))
        diag = result["diagnostics"]
        exact = diag["exact_negative_tests"][0]
        self.assertEqual(exact["observed_phrases_tested"], 5)
        self.assertEqual(exact["observed_lexical_matches"], ["cheap flat", "cheap-flat"])
        self.assertEqual(exact["protected_lexical_collisions"], ["cheap flat"])
        self.assertEqual(exact["negative_scope_proposal"], tw.NEGATIVE_SCOPE)
        self.assertFalse(diag["scope_verified"])
        generic = {r["attempted_generic"]: r for r in diag["unsafe_generic_tests"]}
        for term, query in [("business", "business bay office"), ("cheap", "cheap flat"), ("hotel", "hotel apartment")]:
            self.assertEqual(generic[term]["protected_lexical_collisions"], [query])
            self.assertFalse(generic[term]["legitimate_exclusion"])
            self.assertFalse(generic[term]["scope_approved"])

    def test_corpus_reference_loss_duplication_and_authority_fields_fail(self):
        attempts = []
        item = corpus()
        item["entries"]["cheap flat"]["source_refs"].pop()
        attempts.append(item)
        item = corpus()
        item["entries"]["unassessed"]["source_refs"] = [{"batch": "TEST_ONLY_A", "source_line": 4}]
        attempts.append(item)
        item = corpus()
        item["entries"]["cheap flat"]["approved"] = True
        attempts.append(item)
        for attempt in attempts:
            with self.subTest(attempt=attempt), self.assertRaises(ValueError):
                tw.compile_workbench(attempt, document())


if __name__ == "__main__":
    unittest.main()

"""Meaningful lexical-model, completeness and fresh-state failure contracts."""
import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch

import buyer_negative_conflicts as screen


def record(identity, text, mode="EXACT"):
    return {"keyword_id": identity, "original_text": text, "match_type": mode}


def rows(*texts):
    return [{"source_line": n + 3, "values": {"Keyword": text}}
            for n, text in enumerate(texts, 1)]


class BuyerNegativeConflictTests(unittest.TestCase):
    def test_exact_is_complete_tokens_not_substring(self):
        result = screen.scan_rows([record("n1", "estate agent salary")],
                                  rows("estate agent salary", "estate agent salary dubai", "estate agency salary"))
        self.assertEqual([r["potential_negative_ids"] for r in result], [["n1"], [], []])

    def test_phrase_order_and_broad_permutation_preserve_existing_model(self):
        negatives = [record("p", "agent salary", "PHRASE"), record("b", "agent salary", "BROAD")]
        queries = rows("dubai agent salary", "salary dubai agent", "agent yearly salary")
        result = screen.scan_rows(negatives, queries)
        self.assertEqual([r["potential_negative_ids"] for r in result], [["b", "p"], ["b"], ["b"]])

    def test_unicode_wrappers_whitespace_and_case_use_token_model(self):
        result = screen.scan_rows([record("n", '[Ａgent   Salary]')], rows('"agent salary"', 'AGENT\tSALARY'))
        self.assertEqual([r["potential_negative_ids"] for r in result], [["n"], ["n"]])

    def test_broad_repeated_token_behavior_matches_existing_model(self):
        result = screen.scan_rows([record("n", "agent agent", "BROAD")], rows("agent salary"))
        self.assertEqual(result[0]["potential_negative_ids"], ["n"])

    def test_complete_indexed_results_agree_with_cartesian_existing_model(self):
        negatives = [record("a", "buy apartment dubai"), record("b", "agent salary", "PHRASE"),
                     record("c", "salary agent", "BROAD"), record("d", "property agent job"),
                     record("e", "property sale", "PHRASE")]
        queries = rows("buy apartment dubai", "buy apartment dubai marina", "salary agent dubai",
                       "agent salary", "property sale dubai", "property agent job", "property-agent-job",
                       "agent job property", "apartment for sale dubai")
        result = screen.scan_rows(negatives, queries)
        for source, compared in zip(queries, result):
            expected = sorted(r["keyword_id"] for r in negatives if screen.ka.negative_matches(
                r["original_text"], r["match_type"], source["values"]["Keyword"]))
            self.assertEqual(compared["potential_negative_ids"], expected)

    def test_duplicate_literals_keep_separate_ordinals_and_physical_lines(self):
        result = screen.scan_rows([record("a", "buy apartment dubai")],
                                  rows("buy apartment dubai", "buy apartment dubai"))
        self.assertEqual([r["source_ordinal"] for r in result], [1, 2])
        self.assertEqual([r["source_line"] for r in result], [4, 5])
        self.assertEqual([r["potential_negative_ids"] for r in result], [["a"], ["a"]])

    def test_punctuation_behavior_is_not_literal_identity_or_google_equivalence(self):
        result = screen.scan_rows([record("a", "property-agent-job")], rows("property agent job"))
        self.assertEqual(result[0]["potential_negative_ids"], ["a"])
        self.assertEqual(result[0]["actual_scope_applicability"], "UNVERIFIED_NO_DEPLOYMENT_BINDING")

    def test_even_a_clear_phrase_has_no_positive_admission_or_bound_scope(self):
        result = screen.scan_rows([record("a", "agent salary")], rows("apartment for sale dubai"))
        self.assertEqual(result[0]["potential_negative_ids"], [])
        self.assertIs(result[0]["positive_admission_granted"], False)
        self.assertEqual(result[0]["actual_scope_applicability"], "UNVERIFIED_NO_DEPLOYMENT_BINDING")

    def test_wrong_match_type_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "INVALID_MATCH_TYPE"):
            screen.scan_rows([record("n", "agent salary", "AUTO")], rows("agent salary"))

    def test_duplicate_negative_id_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "NEGATIVE_IDENTITY"):
            screen.scan_rows([record("n", "agent salary"), record("n", "agent job")], rows("agent salary"))

    def test_empty_negative_population_cannot_claim_clear_screen(self):
        with self.assertRaisesRegex(ValueError, "EMPTY_NEGATIVE_POPULATION"):
            screen.scan_rows([], rows("buy property dubai"))

    def test_empty_or_invalid_source_cannot_claim_coverage(self):
        with self.assertRaisesRegex(ValueError, "EMPTY_SOURCE_POPULATION"):
            screen.scan_rows([record("n", "salary")], [])
        with self.assertRaisesRegex(ValueError, "INVALID_SOURCE_LITERAL"):
            screen.scan_rows([record("n", "salary")], rows(""))

    def test_boolean_and_duplicate_physical_lines_fail_closed(self):
        for lines in ((True, 5), (4, 4)):
            queries = rows("apartment sale", "villa sale")
            for row, line in zip(queries, lines):
                row["source_line"] = line
            with self.assertRaisesRegex(ValueError, "INVALID_SOURCE_LINE"):
                screen.scan_rows([record("n", "salary")], queries)

    def test_complete_original_literal_hash_preserved(self):
        literal = "Buy   Apartment in Dubai"
        result = screen.scan_rows([record("n", "salary")], rows(literal))
        self.assertEqual(result[0]["original_literal_sha256"], hashlib.sha256(literal.encode()).hexdigest())

    def test_fresh_source_dependency_check_precedes_current_reconstruction(self):
        original = screen.buyer.read_bound
        target = screen.ROOT / next(iter(screen.DEPENDENCIES))
        with patch.object(screen.buyer, "read_bound", side_effect=lambda p: original(p) + (b" " if Path(p) == target else b"")), \
                patch.object(screen.current, "reconstruct") as reconstruct:
            with self.assertRaisesRegex(ValueError, "DEPENDENCY_PIN_CHANGED"):
                screen.load_sources()
            reconstruct.assert_not_called()

    def test_current_state_verdict_is_never_reused_after_changed_state(self):
        with patch.object(screen.current, "reconstruct", return_value={"records": []}) as reconstruct:
            with self.assertRaisesRegex(ValueError, "COMPLETE_CURRENT_NEGATIVE_STATE_CHANGED"):
                screen.load_sources()
            self.assertEqual(reconstruct.call_count, 1)

    def test_failed_current_reconstruction_does_not_fall_back_to_saved_report(self):
        with patch.object(screen.current, "reconstruct", side_effect=ValueError("FRESH_SOURCE_FAILED")):
            with self.assertRaisesRegex(ValueError, "FRESH_SOURCE_FAILED"):
                screen.build_report()


if __name__ == "__main__":
    unittest.main()

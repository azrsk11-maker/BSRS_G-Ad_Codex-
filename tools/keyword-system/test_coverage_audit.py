"""Synthetic in-memory corpus fixtures; never research masters or Google input."""
import copy
import contextlib
from datetime import date
import hashlib
import io
import itertools
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import coverage_audit as ca
import keyword_audit as ka
from test_keyword_audit import positive, negative, SOURCES, CAMPAIGNS, CONTEXT, SCOPE_BINDINGS, TODAY


def fixture():
    p = positive()
    p["ad_group_key"] = "QA-G1"
    q = {"query_id": "QA-Q1", "text": "apartment rental near school with parking", "positive_ids": ["QA-P1"],
         "campaign_keys": ["QA-C1"], "services": ["residential_rental"], "must_serve": True,
         "source_id": "QA-SOURCE", "source_reference": "TEST_ONLY:long-tail", "review_state": "REVIEWED",
         "reviewer": "qa-query-reviewer", "evidence_ref": "TEST_ONLY:intent", "query_kind": "LONG_TAIL",
         "reviewed_on": "2026-11-01", "valid_until": "2026-12-01"}
    data = {"positive_library": [p], "negative_library": [negative()], "protected_queries": [q],
            "sources": copy.deepcopy(SOURCES), "campaigns": copy.deepcopy(CAMPAIGNS),
            "campaign_context": copy.deepcopy(CONTEXT), "scope_bindings": copy.deepcopy(SCOPE_BINDINGS)}
    review = {"version": "1.0", "matcher_version": ca.MATCHER_VERSION, "coverage_claim": ca.CLAIM,
              "review_state": "REVIEWED", "reviewer": "qa-independent-coverage-reviewer", "evidence_ref": "TEST_ONLY:coverage",
              "reviewed_on": "2026-11-03", "valid_until": "2026-12-01",
              "ad_group_designs": [{"campaign_key": "QA-C1", "ad_group_key": "QA-G1", "landing_page_id": "QA-LP1",
                                    "reviewer": "qa-design-reviewer", "evidence_ref": "TEST_ONLY:design",
                                    "reviewed_on": "2026-11-01", "valid_until": "2026-12-01"}]}
    bind(data, review)
    return data, review


def bind(data, review):
    """Synthetic independent-review fixture only; not an approval generator."""
    review["bindings"] = {role: ca.canonical_sha256(data[role]) for role in ca.BINDING_ROLES}
    review["expected_positive_ids"] = [row["keyword_id"] for row in data["positive_library"]]
    review["expected_query_ids"] = [row["query_id"] for row in data["protected_queries"]]


def run(data, review):
    return ka.audit("negative", data["negative_library"], data["sources"], data["campaigns"],
                    data["campaign_context"], data["protected_queries"], TODAY, data["scope_bindings"],
                    data["positive_library"], review)


class SuppliedCoverageTests(unittest.TestCase):
    def assertHeld(self, data, review):
        report = run(data, review)
        self.assertFalse(report["positive_library_coverage_verified"])
        self.assertEqual(report["approved_exclusion_rows"], 0)
        self.assertFalse(report["deployment_export_allowed"])
        return report["supplied_library_coverage"]

    def test_full_supplied_dataset_pass_is_bounded_not_master_or_deployment(self):
        data, review = fixture()
        report = run(data, review)
        coverage = report["supplied_library_coverage"]
        self.assertTrue(coverage["evaluation_complete"])
        self.assertTrue(report["positive_library_coverage_verified"])
        self.assertEqual(coverage["indexed_cases"], 2)
        self.assertEqual(coverage["positive_ownership"][0]["ad_group_key"], "QA-G1")
        self.assertEqual(report["reviewed_eligible_rows"], 1)
        self.assertEqual(report["deficit"], 13999)
        self.assertFalse(report["exact_target_pass"])
        self.assertFalse(report["deployment_export_allowed"])
        self.assertEqual(data["positive_library"][0]["original_text"], "apartment rental near school")

    def test_bounded_coverage_does_not_manufacture_exclusion_approval(self):
        data, review = fixture()
        data["negative_library"][0].update(approval_state="PENDING", approval_reference=None, approval_reviewer=None, approved_on=None)
        bind(data, review)
        report = run(data, review)
        self.assertTrue(report["positive_library_coverage_verified"])
        self.assertEqual(report["reviewed_eligible_rows"], 1)
        self.assertEqual(report["approved_exclusion_rows"], 0)
        self.assertFalse(report["deployment_export_allowed"])

    def test_omitted_or_partial_certificate_never_passes(self):
        data, review = fixture()
        for key in ["bindings", "expected_positive_ids", "expected_query_ids", "ad_group_designs", "evidence_ref", "reviewer"]:
            changed = copy.deepcopy(review)
            changed.pop(key)
            with self.subTest(key=key):
                self.assertHeld(data, changed)
        self.assertHeld(data, None)
        missing = copy.deepcopy(data)
        missing["positive_library"] = None
        self.assertHeld(missing, review)

    def test_empty_positive_negative_or_corpus_fail_even_rebound(self):
        for role in ["positive_library", "negative_library", "protected_queries"]:
            data, review = fixture()
            data[role] = []
            bind(data, review)
            with self.subTest(role=role):
                self.assertHeld(data, review)

    def test_each_exact_input_hash_is_binding_not_an_assertion(self):
        for role in ca.BINDING_ROLES:
            data, review = fixture()
            if isinstance(data[role], list):
                data[role][0]["changed_after_review"] = True
            else:
                data[role]["changed_after_review"] = True
            with self.subTest(role=role):
                result = self.assertHeld(data, review)
                self.assertIn("canonical SHA256 binding mismatch: " + role, result["errors"])

    def test_missing_or_extra_bound_role_fails(self):
        for mode in ["missing", "extra"]:
            data, review = fixture()
            if mode == "missing":
                review["bindings"].pop("scope_bindings")
            else:
                review["bindings"]["ignored"] = "0" * 64
            self.assertHeld(data, review)

    def test_manifest_cannot_silently_omit_identity_even_with_new_hash(self):
        data, review = fixture()
        review["expected_positive_ids"].append("QA-P-MISSING")
        self.assertHeld(data, review)
        data, review = fixture()
        review["expected_query_ids"].append("QA-Q-MISSING")
        self.assertHeld(data, review)

    def test_stale_future_and_predated_review_fail(self):
        for target, key, value in [("review", "valid_until", "2026-11-06"), ("review", "reviewed_on", "2026-11-08"),
                                   ("review", "reviewed_on", "2026-10-31"), ("protected_queries", "valid_until", "2026-11-06"),
                                   ("positive_library", "valid_until", "2026-11-06"), ("sources", "valid_until", "2026-11-06"),
                                   ("campaign_context", "valid_until", "2026-11-06")]:
            data, review = fixture()
            (review if target == "review" else data[target][0])[key] = value
            bind(data, review)
            with self.subTest(target=target, key=key):
                self.assertHeld(data, review)

    def test_unreviewed_historical_candidates_are_never_promoted(self):
        data, review = fixture()
        data["positive_library"][0]["review_state"] = "CANDIDATE"
        bind(data, review)
        coverage = self.assertHeld(data, review)
        self.assertFalse(coverage["evaluation_complete"])
        self.assertEqual(data["positive_library"][0]["review_state"], "CANDIDATE")

    def test_duplicate_positive_id_or_normalized_text_fails_whole_coverage(self):
        for mode in ["id", "text"]:
            data, review = fixture()
            other = copy.deepcopy(data["positive_library"][0])
            if mode == "id":
                other["original_text"] += " marina"
            else:
                other["keyword_id"] = "QA-P2"
                other["original_text"] = '"APARTMENT  RENTAL NEAR SCHOOL"'
            data["positive_library"].append(other)
            bind(data, review)
            self.assertHeld(data, review)

    def test_duplicate_query_id_text_or_scope_members_fail(self):
        for mode in ["id", "text", "scope", "positive_ids"]:
            data, review = fixture()
            if mode in ["id", "text"]:
                other = copy.deepcopy(data["protected_queries"][0])
                if mode == "id":
                    other["text"] += " today"
                else:
                    other["query_id"] = "QA-Q2"
                    other["text"] = other["text"].upper()
                data["protected_queries"].append(other)
            else:
                key = "campaign_keys" if mode == "scope" else "positive_ids"
                data["protected_queries"][0][key] *= 2
            bind(data, review)
            self.assertHeld(data, review)

    def test_unmapped_page_group_campaign_query_positive_and_source_fail(self):
        edits = [("positive_library", "landing_page_id", "QA-WRONG"), ("positive_library", "ad_group_key", "QA-UNKNOWN"),
                 ("protected_queries", "positive_ids", ["QA-UNKNOWN"]), ("protected_queries", "campaign_keys", ["QA-C2"]),
                 ("protected_queries", "source_id", "QA-UNKNOWN"), ("protected_queries", "source_reference", ""),
                 ("protected_queries", "review_state", "CANDIDATE"), ("protected_queries", "services", ["commercial_leasing"])]
        for role, field, value in edits:
            data, review = fixture()
            data[role][0][field] = value
            bind(data, review)
            with self.subTest(role=role, field=field):
                self.assertHeld(data, review)

    def test_duplicate_or_stale_design_and_self_review_fail(self):
        for mode in ["duplicate", "stale", "self-review"]:
            data, review = fixture()
            if mode == "duplicate":
                review["ad_group_designs"] *= 2
            elif mode == "stale":
                review["ad_group_designs"][0]["valid_until"] = "2026-11-06"
            else:
                review["reviewer"] = data["positive_library"][0]["reviewer"].upper()
            self.assertHeld(data, review)

    def test_every_positive_needs_genuine_longer_mapped_case(self):
        for text, kind in [("apartment rental near school", "LONG_TAIL"), ("unrelated phrase has many extra words today", "LONG_TAIL"),
                           ("apartment rental near school with parking", "COUNTEREXAMPLE")]:
            data, review = fixture()
            data["protected_queries"][0].update(text=text, query_kind=kind)
            bind(data, review)
            self.assertHeld(data, review)

    def test_zero_token_inputs_never_count_or_certify(self):
        for kind in ["positive", "negative", "query"]:
            data, review = fixture()
            if kind == "query":
                data["protected_queries"][0]["text"] = "!!!"
            else:
                data[kind + "_library"][0]["original_text"] = "!!!"
                if kind == "negative":
                    data["negative_library"][0]["normalized_text"] = "!!!"
            bind(data, review)
            self.assertHeld(data, review)
        self.assertEqual(ka.audit("positive", [{**positive(), "original_text": "!!!"}], SOURCES, CAMPAIGNS, CONTEXT, [], TODAY)["reviewed_eligible_rows"], 0)

    def test_literal_conflict_detected_even_when_long_tail_does_not_exact_match(self):
        data, review = fixture()
        text = data["positive_library"][0]["original_text"]
        data["negative_library"][0].update(original_text=text, normalized_text=text, match_type="EXACT", risk_level="HIGH")
        bind(data, review)
        coverage = self.assertHeld(data, review)
        self.assertTrue(coverage["evaluation_complete"])
        self.assertEqual([row["case_kind"] for row in coverage["conflicts"]], ["POSITIVE_LITERAL"])

    def test_long_tail_conflict_namespace_cannot_overwrite_positive_same_id(self):
        data, review = fixture()
        data["protected_queries"][0]["query_id"] = "QA-P1"
        text = data["positive_library"][0]["original_text"]
        data["negative_library"][0].update(original_text=text, normalized_text=text, risk_level="HIGH", protected_query_conflicts=["QA-P1"])
        bind(data, review)
        coverage = self.assertHeld(data, review)
        self.assertTrue(coverage["evaluation_complete"])
        self.assertEqual({(row["case_kind"], row["case_id"]) for row in coverage["conflicts"]}, {("POSITIVE_LITERAL", "QA-P1"), ("PROTECTED_QUERY", "QA-P1")})

    def test_negative_scope_change_invalidates_binding_and_missing_campaign_holds(self):
        data, review = fixture()
        n = data["negative_library"][0]
        n.update(eligible_campaigns=["QA-C2"], ineligible_campaigns=["QA-C1"], scope_target={"campaign_key": "QA-C2"})
        self.assertHeld(data, review)
        bind(data, review)
        self.assertHeld(data, review)

    def test_missing_wrong_stale_or_incomplete_platform_scope_binding_holds(self):
        for mode in ["missing", "wrong-account", "stale", "unknown-campaign", "unverified-list"]:
            data, review = fixture()
            if mode == "missing":
                data["scope_bindings"] = None
            elif mode == "wrong-account":
                data["scope_bindings"]["account_id"] = "111-111-1111"
            elif mode == "stale":
                data["scope_bindings"]["valid_until"] = "2026-11-06"
            elif mode == "unknown-campaign":
                data["scope_bindings"]["campaigns"].pop("QA-C1")
            else:
                data["negative_library"][0].update(scope_type="SHARED_LIST", scope_target={"list_key": "QA-UNKNOWN"})
            bind(data, review)
            with self.subTest(mode=mode):
                self.assertHeld(data, review)

    def test_adgroup_requires_design_and_conservatively_checks_whole_campaign(self):
        data, review = fixture()
        n = data["negative_library"][0]
        n.update(scope_type="AD_GROUP", scope_target={"campaign_key": "QA-C1", "ad_group_key": "QA-UNKNOWN"})
        bind(data, review)
        self.assertHeld(data, review)
        n["scope_target"]["ad_group_key"] = "QA-G1"
        n.update(original_text="parking", normalized_text="parking", protected_query_conflicts=["QA-Q1"])
        bind(data, review)
        coverage = self.assertHeld(data, review)
        self.assertEqual(coverage["conflicts"][0]["case_kind"], "PROTECTED_QUERY")

    def test_matcher_version_and_overbroad_claim_fail(self):
        for key in ["matcher_version", "coverage_claim"]:
            data, review = fixture()
            review[key] = "GOOGLE_ALL_SEARCHES_VERIFIED"
            self.assertHeld(data, review)

    def test_exact_canonical_hash_ignores_object_order_not_array_order(self):
        self.assertEqual(ca.canonical_sha256({"a": 1, "b": 2}), ca.canonical_sha256({"b": 2, "a": 1}))
        self.assertNotEqual(ca.canonical_sha256([1, 2]), ca.canonical_sha256([2, 1]))
        with self.assertRaises(ValueError):
            ca.canonical_sha256(float("nan"))

    def test_schema_binding_and_matcher_contract_matches_runtime(self):
        schema = json.loads(Path(ca.__file__).with_name("coverage-review.schema.json").read_text(encoding="utf-8"))
        fields = schema["properties"]
        self.assertEqual(set(fields["bindings"]["required"]), set(ca.BINDING_ROLES))
        self.assertEqual(fields["matcher_version"]["const"], ca.MATCHER_VERSION)
        self.assertEqual(fields["coverage_claim"]["const"], ca.CLAIM)
        self.assertFalse(fields["bindings"]["additionalProperties"])

    def test_index_equals_bruteforce_for_all_defined_match_modes_and_scopes(self):
        texts = ["flat rent", "rent flat", "flat flat", "flat flat rent", "flat, rent", "[ＦＬＡＴ　ＲＥＮＴ]", "rent", "!!!", "flat rent parking"]
        cases = [{"case_kind": "POSITIVE_LITERAL" if i % 2 else "PROTECTED_QUERY", "case_id": "QA-" + str(i), "text": text,
                  "positive_ids": ["QA-P"], "campaign_keys": scope}
                 for i, (text, scope) in enumerate(itertools.product(texts, [["QA-C1"], ["QA-C2"], ["QA-C1", "QA-C2"]]))]
        negatives = [{"keyword_id": "QA-N" + str(i), "original_text": text, "match_type": match, "eligible_campaigns": scope}
                     for i, (text, match, scope) in enumerate(itertools.product(texts, sorted(ka.MATCH_TYPES), [["QA-C1"], ["QA-C2"], ["QA-C1", "QA-C2"]]))]
        expected = {(number, case["case_kind"], case["case_id"]) for number, negative_row in enumerate(negatives, 1) for case in cases
                    if set(negative_row["eligible_campaigns"]) & set(case["campaign_keys"]) and ka.negative_matches(negative_row["original_text"], negative_row["match_type"], case["text"])}
        result = ca.simulate_scoped(negatives, cases)
        self.assertEqual({(row["negative_row"], row["case_kind"], row["case_id"]) for row in result["conflicts"]}, expected)
        self.assertLess(result["lexical_comparisons_executed"], result["applicable_case_pairs"])

    def test_sparse_thousand_by_two_thousand_scale_uses_postings(self):
        cases = [{"case_kind": kind, "case_id": "QA-" + str(i), "text": "synthetic term" + str(i) + suffix,
                  "positive_ids": ["QA-P" + str(i)], "campaign_keys": ["QA-C1"]}
                 for i in range(1000) for kind, suffix in [("POSITIVE_LITERAL", ""), ("PROTECTED_QUERY", " extension")]]
        negatives = [{"keyword_id": "QA-N" + str(i), "original_text": "term" + str(i), "match_type": "PHRASE", "eligible_campaigns": ["QA-C1"]} for i in range(1000)]
        result = ca.simulate_scoped(negatives, cases)
        self.assertEqual(result["applicable_case_pairs"], 2_000_000)
        self.assertEqual(result["lexical_comparisons_executed"], 2000)
        self.assertEqual(len(result["conflicts"]), 2000)

    def test_cli_binds_all_inputs_without_modifying_them(self):
        data, review = fixture()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            paths = {}
            for key, value in {**data, "review": review}.items():
                paths[key] = root / (key + ".json")
                paths[key].write_text(json.dumps(value), encoding="utf-8")
            before = {key: path.read_bytes() for key, path in paths.items()}
            output = root / "report.json"
            options = {"--input": "negative_library", "--sources": "sources", "--campaigns": "campaigns", "--campaign-context": "campaign_context",
                       "--protected": "protected_queries", "--scope-bindings": "scope_bindings", "--positive-library": "positive_library", "--coverage-review": "review"}
            command = [sys.executable, "-B", str(Path(ka.__file__)), "--kind", "negative", "--as-of", TODAY.isoformat(), "--output", str(output)]
            for option, role in options.items():
                command.extend([option, str(paths[role])])
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(report["positive_library_coverage_verified"])
            self.assertEqual(len(report["input_sha256"]), 8)
            self.assertEqual(before, {key: path.read_bytes() for key, path in paths.items()})
            summary = json.loads(result.stdout)
            self.assertNotIn("positive_ownership", summary["supplied_library_coverage"])
            self.assertNotIn("conflicts", summary["supplied_library_coverage"])

    def test_cli_raw_hashes_describe_same_bytes_as_parser_during_concurrent_edit(self):
        data, _ = fixture()
        for extension in [".json", ".csv"]:
            with self.subTest(extension=extension), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                record_path = root / ("positive" + extension)
                if extension == ".json":
                    record_path.write_bytes(json.dumps(data["positive_library"]).encode("utf-8"))
                else:
                    import csv
                    with record_path.open("w", newline="", encoding="utf-8-sig") as handle:
                        row = data["positive_library"][0]
                        writer = csv.DictWriter(handle, fieldnames=list(row))
                        writer.writeheader()
                        writer.writerow({key: "" if value is None else value for key, value in row.items()})
                paths = {"records": record_path}
                for key in ["sources", "campaigns", "campaign_context", "protected_queries"]:
                    paths[key] = root / (key + ".json")
                    paths[key].write_bytes(json.dumps(data[key]).encode("utf-8"))
                before = {key: path.read_bytes() for key, path in paths.items()}
                output = root / "report.json"
                options = {"--input": "records", "--sources": "sources", "--campaigns": "campaigns",
                           "--campaign-context": "campaign_context", "--protected": "protected_queries"}
                argv = ["keyword_audit.py", "--kind", "positive", "--as-of", TODAY.isoformat(), "--output", str(output)]
                for option, key in options.items():
                    argv.extend([option, str(paths[key])])
                original_audit = ka.audit

                def concurrent_edit(*args, **kwargs):
                    for path in paths.values():
                        path.write_bytes(b"[]")
                    return original_audit(*args, **kwargs)

                with mock.patch.object(sys, "argv", argv), mock.patch.object(ka, "audit", side_effect=concurrent_edit), contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(ka.main(), 0)
                report = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(report["reviewed_eligible_rows"], 1)
                self.assertEqual({key: item["sha256"] for key, item in report["input_sha256"].items()},
                                 {key: hashlib.sha256(content).hexdigest() for key, content in before.items()})
                self.assertNotEqual(report["input_sha256"]["records"]["sha256"], hashlib.sha256(record_path.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()

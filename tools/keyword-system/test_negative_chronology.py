"""Synthetic date-consistency regressions; no genuine keyword evidence/approval."""
import copy
import unittest

from test_keyword_audit import (audit, negative, positive, SOURCES, CONTEXT,
                                PROTECTED, SCOPE_BINDINGS)


class NegativeChronologyTests(unittest.TestCase):
    def assert_counts(self, report, researched, approved):
        self.assertEqual(report["reviewed_eligible_rows"], researched)
        self.assertEqual(report["approved_exclusion_rows"], approved)
        self.assertFalse(report["deployment_export_allowed"])
        self.assertFalse(report["production_writes_available"])

    def test_source_observed_after_research_and_approval_rejects_research(self):
        sources = copy.deepcopy(SOURCES)
        sources[0]["observed_on"] = "2026-11-06"
        result = audit("negative", [negative()], sources=sources)
        self.assert_counts(result, 0, 0)
        self.assertIn("negative research review predates its source/query/metric evidence", result["records"][0]["errors"])

    def test_approval_before_research_preserves_research_only(self):
        row = negative()
        row["approved_on"] = "2026-10-31"
        result = audit("negative", [row])
        self.assert_counts(result, 1, 0)
        self.assertTrue(result["structural_pass"])
        self.assertTrue(any(hold.startswith("exclusion approval:") for hold in result["records"][0]["deployment_holds"]))

    def test_observed_query_after_research_and_approval_rejects_research(self):
        for kind in ("first_party_observed", "authorized_partner_observed"):
            with self.subTest(kind=kind):
                row = negative()
                row.update(source_type=kind, observed_query=row["original_text"], observation_date="2026-11-06")
                sources = copy.deepcopy(SOURCES)
                sources[0]["kind"] = kind
                self.assert_counts(audit("negative", [row], sources=sources), 0, 0)

    def test_claimed_observation_on_hypothesis_is_not_ignored(self):
        row = negative()
        row.update(observed_query=row["original_text"], observation_date="2026-11-06")
        self.assert_counts(audit("negative", [row]), 0, 0)

    def test_used_metric_after_research_rejects_research(self):
        for metric in ("volume", "cpc"):
            with self.subTest(metric=metric):
                row = negative()
                row[metric] = 10
                row["metric_evidence"] = {metric: {"provider": "TEST_ONLY:provider", "reference": "TEST_ONLY:metric",
                                                       "observed_on": "2026-11-06", "valid_until": "2026-12-01"}}
                self.assert_counts(audit("negative", [row]), 0, 0)

    def test_unused_metric_metadata_does_not_become_an_observation(self):
        row = negative()
        row["metric_evidence"] = {"volume": {"observed_on": "2026-11-06"}}
        self.assert_counts(audit("negative", [row]), 1, 1)

    def test_same_day_source_query_metric_research_and_approval_are_consistent(self):
        row = negative()
        row.update(source_type="first_party_observed", observed_query=row["original_text"],
                   observation_date="2026-11-01", approved_on="2026-11-01", volume=10)
        row["metric_evidence"] = {"volume": {"provider": "TEST_ONLY:provider", "reference": "TEST_ONLY:metric",
                                               "observed_on": "2026-11-01", "valid_until": "2026-12-01"}}
        sources = copy.deepcopy(SOURCES)
        sources[0]["kind"] = "first_party_observed"
        self.assert_counts(audit("negative", [row], sources=sources), 1, 1)

    def test_later_scope_context_or_protected_review_holds_only_approval(self):
        variants = []
        bindings = copy.deepcopy(SCOPE_BINDINGS)
        bindings["verified_on"] = "2026-11-06"
        variants.append({"scope_bindings": bindings})
        contexts = copy.deepcopy(CONTEXT)
        contexts[0]["reviewed_on"] = "2026-11-06"
        variants.append({"campaign_context": contexts})
        queries = copy.deepcopy(PROTECTED)
        queries[0]["reviewed_on"] = "2026-11-06"
        variants.append({"protected_queries": queries})
        for changes in variants:
            with self.subTest(role=next(iter(changes))):
                self.assert_counts(audit("negative", [negative()], **changes), 1, 0)
                row = negative()
                row["approved_on"] = "2026-11-06"
                self.assert_counts(audit("negative", [row], **changes), 1, 1)

    def test_unrelated_campaign_and_query_reviews_do_not_hold_narrow_scope(self):
        contexts = copy.deepcopy(CONTEXT)
        contexts[1]["reviewed_on"] = "2026-11-06"
        queries = copy.deepcopy(PROTECTED)
        queries.append({**queries[0], "query_id": "QA-Q2", "campaign_keys": ["QA-C2"], "reviewed_on": "2026-11-06"})
        self.assert_counts(audit("negative", [negative()], campaign_context=contexts, protected_queries=queries), 1, 1)

    def test_missing_or_malformed_research_dependency_dates_hold(self):
        for value in (None, "bad", "2026-02-30", "2026-11-01T00:00:00Z", 20261101):
            with self.subTest(value=value):
                sources = copy.deepcopy(SOURCES)
                sources[0]["observed_on"] = value
                self.assert_counts(audit("negative", [negative()], sources=sources), 0, 0)
                row = negative()
                row.update(source_type="first_party_observed", observed_query=row["original_text"], observation_date=value)
                sources[0].update(kind="first_party_observed", observed_on="2026-11-01")
                self.assert_counts(audit("negative", [row], sources=sources), 0, 0)

    def test_missing_or_malformed_approval_dates_preserve_research_only(self):
        for value in (None, "bad", "2026-02-30", 20261101):
            with self.subTest(value=value):
                row = negative()
                row["approved_on"] = value
                self.assert_counts(audit("negative", [row]), 1, 0)

    def test_missing_used_metric_observation_date_rejects_research(self):
        for value in (None, "bad", "2026-02-30"):
            with self.subTest(value=value):
                row = negative()
                row.update(volume=10, metric_evidence={"volume": {"provider": "TEST_ONLY:provider", "reference": "TEST_ONLY:metric",
                                                                     "observed_on": value, "valid_until": "2026-12-01"}})
                self.assert_counts(audit("negative", [row]), 0, 0)

    def test_missing_scope_date_holds_approval_without_invalidating_research(self):
        bindings = copy.deepcopy(SCOPE_BINDINGS)
        bindings.pop("verified_on")
        self.assert_counts(audit("negative", [negative()], scope_bindings=bindings), 1, 0)

    def test_original_valid_negative_and_positive_unchanged(self):
        self.assert_counts(audit("negative", [negative()]), 1, 1)
        result = audit("positive", [positive()])
        self.assertTrue(result["structural_pass"])
        self.assertEqual(result["reviewed_eligible_rows"], 1)
        self.assertIsNone(result["approved_exclusion_rows"])

    def test_approval_chronology_hold_does_not_invalidate_research_coverage(self):
        from test_coverage_audit import fixture, bind, run
        data, review = fixture()
        data["negative_library"][0]["approved_on"] = "2026-10-31"
        bind(data, review)
        result = run(data, review)
        self.assert_counts(result, 1, 0)
        self.assertTrue(result["positive_library_coverage_verified"])

    def test_chronology_check_does_not_mutate_source_record_or_support(self):
        row, sources, contexts, queries, bindings = negative(), copy.deepcopy(SOURCES), copy.deepcopy(CONTEXT), copy.deepcopy(PROTECTED), copy.deepcopy(SCOPE_BINDINGS)
        before = copy.deepcopy((row, sources, contexts, queries, bindings))
        audit("negative", [row], sources=sources, campaign_context=contexts, protected_queries=queries, scope_bindings=bindings)
        self.assertEqual((row, sources, contexts, queries, bindings), before)

    def test_additional_negative_does_not_reread_corpus_review_dates(self):
        class CountedQuery(dict):
            def get(self, key, default=None):
                if key == "reviewed_on":
                    reads.append(key)
                return super().get(key, default)

        reads = []
        queries = [CountedQuery(query) for query in copy.deepcopy(PROTECTED)]
        self.assert_counts(audit("negative", [negative()], protected_queries=queries), 1, 1)
        first_count = len(reads)
        reads.clear()
        second = negative()
        second.update(keyword_id="QA-N2", negative_id="QA-N2", original_text="broker licensing exam",
                      normalized_text="broker licensing exam")
        self.assert_counts(audit("negative", [negative(), second], protected_queries=queries), 2, 2)
        self.assertEqual(len(reads), first_count)


if __name__ == "__main__":
    unittest.main()

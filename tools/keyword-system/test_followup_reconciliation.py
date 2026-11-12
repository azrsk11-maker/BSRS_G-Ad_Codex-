import copy
import json
import os
from pathlib import Path
import tempfile
import unittest

import followup_reconciliation as f


class FollowupReconciliationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = f.load_sources()
        cls.report = f.reconcile_sources(cls.sources)
        cls.review = f.load_review(f.ROOT / "docs/audit/keyword-employment-followup-reconciled-2026-11-11/review.json")
        cls.baseline_report = (f.ROOT / f.BASELINE_REPORT["file"]).read_bytes()

    def test_same_cohort_is_deduplicated_without_losing_occurrences(self):
        self.assertEqual(self.report["counts"]["canonical_phrases"], 444)
        self.assertEqual(self.report["counts"]["source_occurrences"], 888)
        self.assertEqual(len({r["canonical_id"] for r in self.report["records"]}), 444)
        for record in self.report["records"]:
            self.assertEqual([p["source_key"] for p in record["provenance_occurrences"]], list(f.SOURCES))

    def test_every_original_preview_verdict_is_preserved(self):
        original = {}
        for key, spec in f.SOURCES.items():
            preview = json.loads(self.sources[key]["semantic-review-preview.json"])
            original[key] = {row["source_line"]: row for row in preview["records"]}
        for record in self.report["records"]:
            for assessment in record["preview_assessments"]:
                row = assessment["original_assessment"]
                self.assertEqual(row, original[assessment["source_key"]][row["source_line"]])

    def test_conflicting_preview_decisions_stay_held(self):
        rows = {r["normalized_keyword"]: r for r in self.report["records"]}
        row = rows["estate caretaker jobs"]
        self.assertEqual(row["preview_state"], "DISAGREEMENT_HOLD")
        self.assertEqual({a["original_assessment"]["disposition"] for a in row["preview_assessments"]},
                         {"HOLD", "NEGATIVE_EXACT_REVIEW"})
        self.assertTrue(row["semantic_review_required"])
        self.assertTrue(row["assessment_content_differs"])
        self.assertGreater(self.report["counts"]["disagreement_hold"], 0)

    def test_reconciliation_never_promotes_research_or_serving_authority(self):
        self.assertEqual(self.report["master_contribution"], f.MASTER)
        self.assertEqual(self.report["controls"], f.CONTROLS)
        self.assertTrue(all(value == 0 for value in self.report["master_contribution"].values()))
        self.assertFalse(self.report["controls"]["current_library_overlap_verified"])

    def test_any_source_or_preview_byte_change_fails_before_reconciliation(self):
        for key, spec in f.SOURCES.items():
            for name in spec["pins"]:
                with self.subTest(source=key, file=name):
                    altered = copy.deepcopy(self.sources)
                    altered[key][name] += b"\n"
                    with self.assertRaisesRegex(ValueError, "SOURCE_BYTES_CHANGED"):
                        f.reconcile_sources(altered)

    def test_missing_or_duplicated_capture_cannot_supply_provenance(self):
        altered = {"followup-1": self.sources["followup-1"]}
        with self.assertRaisesRegex(ValueError, "SOURCE_SET"):
            f.reconcile_sources(altered)
        altered["followup-2"] = altered["followup-1"]
        with self.assertRaisesRegex(ValueError, "SOURCE_FILES"):
            f.reconcile_sources(altered)

    def test_writer_creates_only_a_new_explicit_output(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "result.json"
            f.write_new_report(self.report, path)
            before = path.read_bytes()
            self.assertEqual(json.loads(before), self.report)
            with self.assertRaisesRegex(ValueError, "OUTPUT_EXISTS"):
                f.write_new_report(self.report, path)
            self.assertEqual(path.read_bytes(), before)
            source_path = f.ROOT / f.SOURCES["followup-1"]["folder"] / "new-result.json"
            with self.assertRaisesRegex(ValueError, "SOURCE_OVERWRITE_FORBIDDEN"):
                f.write_new_report(self.report, source_path)
            self.assertFalse(source_path.exists())

    def test_existing_hardlink_output_cannot_overwrite_original(self):
        with tempfile.TemporaryDirectory() as temp:
            original, alias = Path(temp) / "source.json", Path(temp) / "alias.json"
            original.write_bytes(b"unchanged")
            try:
                os.link(original, alias)
            except OSError:
                self.skipTest("Hardlinks unavailable on this filesystem")
            with self.assertRaisesRegex(ValueError, "OUTPUT_EXISTS"):
                f.write_new_report(self.report, alias)
            self.assertEqual(original.read_bytes(), b"unchanged")

    def test_symlink_ancestor_output_cannot_write_through_alias(self):
        with tempfile.TemporaryDirectory() as temp:
            real, alias = Path(temp) / "real", Path(temp) / "alias"
            (real / "child").mkdir(parents=True)
            try:
                alias.symlink_to(real, target_is_directory=True)
            except OSError:
                self.skipTest("Symlinks unavailable on this platform")
            with self.assertRaisesRegex(ValueError, "OUTPUT_PARENT"):
                f.write_new_report(self.report, alias / "child" / "result.json")
            self.assertFalse((real / "child" / "result.json").exists())

    def test_writer_rejects_changed_authority_flags(self):
        report = copy.deepcopy(self.report)
        report["controls"]["admission_authorized"] = True
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "result.json"
            with self.assertRaisesRegex(ValueError, "REPORT_AUTHORITY"):
                f.write_new_report(report, path)
            self.assertFalse(path.exists())

    def test_prepared_review_validates_as_dated_snapshot_only(self):
        summary = f.validate_preliminary_review(self.review, self.report, self.baseline_report)
        self.assertTrue(summary["source_bound_review_valid"])
        self.assertEqual(summary["counts"]["negative_exact_review"], 191)
        self.assertEqual(summary["counts"]["hold"], 235)
        self.assertEqual(summary["counts"]["preview_disagreement_holds"], 79)
        self.assertFalse(summary["current_library_membership_verified"])
        self.assertTrue(summary["membership_is_observed_snapshot"])

    def test_review_identity_cannot_be_forged_missing_or_duplicated(self):
        for change in ("forged", "missing", "duplicate", "wrong_text"):
            with self.subTest(change=change):
                review = copy.deepcopy(self.review)
                if change == "forged":
                    review["records"][0]["canonical_id"] = "KW-" + "0" * 64
                elif change == "missing":
                    review["records"].pop()
                elif change == "duplicate":
                    review["records"][1] = copy.deepcopy(review["records"][0])
                else:
                    review["records"][0]["original_text"] = "forged source text"
                with self.assertRaisesRegex(ValueError, "REVIEW_ROWS|REVIEW_IDENTITY_BINDING"):
                    f.validate_preliminary_review(review, self.report, self.baseline_report)

    def test_preview_disagreement_cannot_be_promoted(self):
        review = copy.deepcopy(self.review)
        row = next(r for r in review["records"] if r["preview_state"] == "DISAGREEMENT_HOLD"
                   and r["baseline_membership"] == "NOVEL_UNPROTECTED")
        row["disposition"] = "NEGATIVE_EXACT_REVIEW"
        row["match_type_proposal"] = "EXACT"
        with self.assertRaisesRegex(ValueError, "PREVIEW_DISAGREEMENT_BYPASS"):
            f.validate_preliminary_review(review, self.report, self.baseline_report)

    def test_protected_row_cannot_be_negative_or_relabelled_novel(self):
        for relabel in (False, True):
            with self.subTest(relabel=relabel):
                review = copy.deepcopy(self.review)
                row = next(r for r in review["records"] if r["baseline_membership"] == "EXISTING_PROTECTED"
                           and r["preview_state"] != "DISAGREEMENT_HOLD")
                if relabel:
                    row["baseline_membership"] = "NOVEL_UNPROTECTED"
                else:
                    row["disposition"] = "NEGATIVE_EXACT_REVIEW"
                    row["match_type_proposal"] = "EXACT"
                with self.assertRaisesRegex(ValueError, "PROTECTED_NEGATIVE_BYPASS|BASELINE_MEMBERSHIP_SNAPSHOT_CHANGED"):
                    f.validate_preliminary_review(review, self.report, self.baseline_report)

    def test_review_authority_counts_source_refs_and_baseline_tampering_fail(self):
        for change in ("authority", "master", "counts", "source_ref", "baseline", "freshness"):
            with self.subTest(change=change):
                review = copy.deepcopy(self.review)
                if change == "authority":
                    review["controls"]["negative_admission_granted"] = True
                elif change == "master":
                    review["master_contribution"]["reviewed_negative"] = 191
                elif change == "counts":
                    review["counts"]["hold"] += 1
                elif change == "source_ref":
                    review["source_refs"][0]["source_sha256"] = "0" * 64
                elif change == "baseline":
                    review["baseline"]["library_report"]["sha256"] = "0" * 64
                else:
                    review["baseline"]["current_membership_requires_fresh_verification"] = False
                with self.assertRaises(ValueError):
                    f.validate_preliminary_review(review, self.report, self.baseline_report)
        with self.assertRaisesRegex(ValueError, "BASELINE_REPORT_CHANGED"):
            f.validate_preliminary_review(self.review, self.report, self.baseline_report + b"\n")

    def test_malformed_membership_and_unknown_fields_fail_safely(self):
        review = copy.deepcopy(self.review)
        review["records"][0]["baseline_membership"] = []
        with self.assertRaisesRegex(ValueError, "REVIEW_DISPOSITION"):
            f.validate_preliminary_review(review, self.report, self.baseline_report)
        review = copy.deepcopy(self.review)
        review["production_authorized"] = True
        with self.assertRaisesRegex(ValueError, "REVIEW_FIELDS"):
            f.validate_preliminary_review(review, self.report, self.baseline_report)


if __name__ == "__main__":
    unittest.main()

"""Offline provenance and non-promotion checks; no external services or real data writes."""
import contextlib
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import warnings
import zipfile

import historical_negative_intake as h
from keyword_audit import negative_matches


STAGING = Path(__file__).with_name("staging")
AUDIT = Path(__file__).resolve().parents[2] / "docs/audit"


def document():
    return json.loads((STAGING / "historical-negative-intake.json").read_text(encoding="utf-8"))


def original_member_bytes():
    # Reconstruct preserved evidence, never invent keywords or require the owner's local ZIP.
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=h.FIELDS, lineterminator="\r\n")
    writer.writeheader()
    writer.writerows(row["original_negative_fields"] for row in document()["placements"])
    return ("\ufeff" + stream.getvalue()).encode("utf-8")


def archive_bytes(entries):
    buffer = io.BytesIO()
    with warnings.catch_warnings(), zipfile.ZipFile(buffer, "w") as archive:
        warnings.simplefilter("ignore", UserWarning)
        for name, content in entries:
            archive.writestr(name, content)
    return buffer.getvalue()


class HistoricalNegativeIntakeTests(unittest.TestCase):
    def test_historical_negatives_against_proposed_protected_phrases(self):
        audit = AUDIT / "HISTORICAL_NEGATIVE_PROTECTED_PROBE.md"
        rows = [line.split("|")[1:3] for line in audit.read_text(encoding="utf-8").splitlines()
                if line.startswith(("| buyers/", "| owners/", "| tenants/", "| brand "))]
        phrases = [phrase.strip() for _, phrase in rows]
        self.assertEqual(len(phrases), 12)
        self.assertEqual(len(set(phrases)), 12)
        candidates = document()["candidates"]
        modes = {"Negative phrase": "PHRASE", "Negative exact": "EXACT"}
        negatives = [(row["original_text"], modes[mode]) for row in candidates
                     for mode in row["historical_match_types_seen"]]
        self.assertEqual(len(negatives), 9)
        self.assertEqual(sum(mode == "EXACT" for _, mode in negatives), 3)
        for text, mode in negatives:
            with self.subTest(text=text, mode=mode):
                self.assertTrue(negative_matches(text, mode, text))
                if mode == "EXACT":
                    self.assertFalse(negative_matches(text, mode, text + " dubai"))
                self.assertEqual([phrase for phrase in phrases if negative_matches(text, mode, phrase)], [])

    def test_legacy_broad_list_matches_protected_counterexamples(self):
        evidence = json.loads((AUDIT / "TARGETING_NEGATIVE_READBACK_2026-11-07.json").read_text(encoding="utf-8"))
        shared = evidence["shared_list"]
        self.assertFalse(shared["attached_to_v2_campaigns_in_this_account_export"])
        terms = shared["keywords_in_export_order"]
        self.assertEqual(len(set(terms)), 29)
        audit = (AUDIT / "HISTORICAL_NEGATIVE_PROTECTED_PROBE.md").read_text(encoding="utf-8")
        section = audit.split("## Legacy shared-list counterexamples\n", 1)[1]
        examples = [line.split("|")[1:4] for line in section.splitlines()
                    if line.startswith(("| Off-plan ", "| Resale ", "| Sellers ", "| Landlords ", "| Tenants ", "| Brand "))]
        self.assertEqual(len(examples), 6)
        self.assertEqual(len({funnel for funnel, _, _ in examples}), 6)
        for _, phrase, expected in examples:
            with self.subTest(phrase=phrase):
                matches = {term for term in terms if negative_matches(term, "BROAD", phrase.strip())}
                self.assertEqual(matches, {term.strip() for term in expected.split(",")})

    def test_reconstruction_matches_exact_pinned_source_and_staging(self):
        raw = original_member_bytes()
        self.assertEqual(len(raw), h.MEMBER_BYTES)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), h.MEMBER_SHA256)
        self.assertEqual(h.assemble(raw, "2026-11-07"), document())
        report = h.validate_intake(document())
        self.assertEqual((report["historical_placements"], report["distinct_unreviewed_candidates"]), (27, 9))
        self.assertEqual(report["reviewed_negative_rows"], 0)
        self.assertEqual(report["approved_exclusion_rows"], 0)
        self.assertEqual(report["reviewed_negative_deficit"], 14000)
        self.assertFalse(report["deployment_export_allowed"])

    def test_validation_report_binds_actual_staging_bytes(self):
        raw = (STAGING / "historical-negative-intake.json").read_bytes()
        report = json.loads((STAGING / "negative-intake-validation.json").read_text(encoding="utf-8"))
        self.assertEqual(report.pop("intake_sha256"), hashlib.sha256(raw).hexdigest())
        self.assertEqual(report, h.validate_intake(json.loads(raw)))

    def test_every_original_scope_reason_and_risk_remains_a_historical_claim(self):
        d = document()
        self.assertTrue(all(p["original_negative_fields"]["Decision"].startswith("CANDIDATE ONLY") for p in d["placements"]))
        self.assertTrue(all(p["original_negative_fields"]["Scope"] == "Campaign only" for p in d["placements"]))
        self.assertTrue(all(p["original_negative_fields"]["Reason"] for p in d["placements"]))
        for candidate in d["candidates"]:
            self.assertEqual(candidate["historical_risk_claims_seen"], ["LOW"])
            self.assertIsNone(candidate["current_risk_level"])
            self.assertIsNone(candidate["current_scope_target"])
            self.assertIsNone(candidate["current_protected_query_conflicts"])
            self.assertEqual(candidate["protected_intent_test_status"], "NOT_PERFORMED")

    def test_original_claim_or_locator_mutation_rejected_even_if_regrouped(self):
        for field, value in [("Scope", "Account"), ("Risk", "HIGH"), ("Reason", "replacement"),
                             ("Keyword", "replacement"), ("Campaign", "CURRENT-CAMPAIGN")]:
            d = document()
            d["placements"][0]["original_negative_fields"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                h.validate_intake(d)
        d = document()
        d["placements"][0]["source_locator"]["start_line"] = 3
        with self.assertRaises(ValueError):
            h.validate_intake(d)

    def test_source_envelope_and_freshness_cannot_be_rewritten(self):
        for field, value in [("archive_sha256", "0" * 64), ("freshness_verified", True),
                             ("canonical_original_records_sha256", "0" * 64),
                             ("source_classification", "CURRENT_ACCOUNT_EVIDENCE")]:
            d = document()
            d["source"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                h.validate_intake(d)

    def test_candidate_review_approval_metrics_mapping_cannot_be_promoted(self):
        edits = {"review_state": "REVIEWED", "approval_state": "APPROVED", "volume": 50,
                 "current_risk_level": "LOW", "current_scope_type": "CAMPAIGN",
                 "current_eligible_campaigns": ["CURRENT-CAMPAIGN"], "approval_reference": "approved",
                 "current_protected_query_conflicts": [], "source_kind": "first_party_observed",
                 "deployed_resource_ids_from_this_intake": ["123"]}
        for field, value in edits.items():
            d = document()
            d["candidates"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                h.validate_intake(d)

    def test_counts_false_authority_and_extra_fields_are_rejected(self):
        for field in ["reviewed_negative_rows", "approved_exclusion_rows", "deployed_rows_from_this_intake"]:
            d = document()
            d["counts"][field] = 1
            with self.subTest(field=field), self.assertRaises(ValueError):
                h.validate_intake(d)
        for field in ["current_scope_assigned", "deployment_export_allowed", "production_writes_available"]:
            d = document()
            d[field] = True
            with self.subTest(field=field), self.assertRaises(ValueError):
                h.validate_intake(d)
        d = document()
        d["counts"]["reviewed_negative_rows"] = False  # JSON false must not equal numeric zero.
        with self.assertRaises(ValueError):
            h.validate_intake(d)
        d = document()
        d["live_approved"] = True
        with self.assertRaises(ValueError):
            h.validate_intake(d)

    def test_omission_reordering_and_relabeling_do_not_preserve_provenance(self):
        for mode in ["omit-placement", "reverse-placements", "reverse-candidates", "duplicate-placement", "rename-id"]:
            d = document()
            if mode == "omit-placement":
                d["placements"].pop()
            elif mode == "reverse-placements":
                d["placements"].reverse()
            elif mode == "reverse-candidates":
                d["candidates"].reverse()
                for i, row in enumerate(d["candidates"], 1):
                    row["candidate_id"] = f"LEGACY-NEG-{i:04}"
            elif mode == "duplicate-placement":
                d["candidates"][0]["placement_ids"].append(d["candidates"][0]["placement_ids"][0])
            else:
                d["placements"][0]["placement_id"] = "RENAMED"
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                h.validate_intake(d)

    def test_validation_is_read_only_and_dates_are_strict(self):
        d = document()
        before = copy.deepcopy(d)
        h.validate_intake(d)
        self.assertEqual(d, before)
        for value in ["2026-2-3", "2026-02-30", None]:
            d["intake_date"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                h.validate_intake(d)

    def test_changed_member_bytes_rejected_before_parsing(self):
        raw = original_member_bytes()
        for changed in [raw[:-1], raw.replace(b"LOW", b"BAD", 1)]:
            with self.assertRaises(ValueError):
                h.assemble(changed, "2026-11-07")

    def test_selected_copies_are_checked_and_no_extraction_occurs(self):
        raw = original_member_bytes()
        payload = archive_bytes([(h.PRIMARY, raw), (h.DUPLICATE_COPY, raw), ("../never-extracted", b"TEST_ONLY")])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "synthetic-test-only.zip"
            path.write_bytes(payload)
            # Archive pin override is isolated to synthetic ZIP container structure tests.
            with mock.patch.object(h, "ARCHIVE_SHA256", hashlib.sha256(payload).hexdigest()):
                self.assertEqual(h.read_pinned_archive(path), raw)
            self.assertEqual([p.name for p in Path(folder).iterdir()], [path.name])

    def test_archive_duplicate_missing_and_changed_members_fail_closed(self):
        raw = original_member_bytes()
        scenarios = [[(h.PRIMARY, raw)], [(h.PRIMARY, raw), (h.PRIMARY, raw), (h.DUPLICATE_COPY, raw)],
                     [(h.PRIMARY, raw), (h.DUPLICATE_COPY, raw.replace(b"LOW", b"BAD", 1))],
                     [(h.PRIMARY, raw), (h.DUPLICATE_COPY, raw[:-1])]]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "synthetic-test-only.zip"
            for entries in scenarios:
                payload = archive_bytes(entries)
                path.write_bytes(payload)
                with self.subTest(entries=len(entries)), mock.patch.object(h, "ARCHIVE_SHA256", hashlib.sha256(payload).hexdigest()), self.assertRaises(ValueError):
                    h.read_pinned_archive(path)

    def test_unpinned_or_oversized_archive_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "synthetic-test-only.zip"
            for payload in [b"changed", b"x" * (h.MAX_ARCHIVE_BYTES + 1)]:
                path.write_bytes(payload)
                with self.assertRaises(ValueError):
                    h.read_pinned_archive(path)

    def test_cli_refuses_input_or_output_alias_before_source_read(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            archive = root / "original.zip"
            archive.write_bytes(b"UNCHANGED")
            for output, report in [(archive, root / "report.json"), (root / "same.json", root / "same.json"),
                                   (root / "intake.json", archive)]:
                argv = ["historical_negative_intake.py", "--archive", str(archive), "--intake-date", "2026-11-07",
                        "--output", str(output), "--report", str(report)]
                with mock.patch.object(sys, "argv", argv), mock.patch.object(h, "read_pinned_archive") as reader, self.assertRaises(ValueError):
                    h.main()
                reader.assert_not_called()
                self.assertEqual(archive.read_bytes(), b"UNCHANGED")

    def test_cli_reproducible_writes_hash_exact_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            archive, output, report_path = [root / name for name in ["source.zip", "intake.json", "report.json"]]
            archive.write_bytes(b"SYNTHETIC_CONTAINER_TEST_ONLY")
            argv = ["historical_negative_intake.py", "--archive", str(archive), "--intake-date", "2026-11-07",
                    "--output", str(output), "--report", str(report_path)]
            with mock.patch.object(sys, "argv", argv), mock.patch.object(h, "read_pinned_archive", return_value=original_member_bytes()), contextlib.redirect_stdout(io.StringIO()):
                h.main()
            self.assertEqual(output.read_bytes(), (STAGING / "historical-negative-intake.json").read_bytes())
            self.assertEqual(report_path.read_bytes(), (STAGING / "negative-intake-validation.json").read_bytes())
            self.assertEqual(archive.read_bytes(), b"SYNTHETIC_CONTAINER_TEST_ONLY")


if __name__ == "__main__":
    unittest.main()

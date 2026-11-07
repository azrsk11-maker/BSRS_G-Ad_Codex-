"""Synthetic-only transformation tests plus read-only checks of the staged artifact."""
import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import historical_intake as hi
import keyword_audit as ka


def csv_bytes(fields, rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\r\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def fixture(text="synthetic property enquiry"):
    keywords = [{"Campaign": "QA_ONLY_CAMPAIGN", "Campaign status": "Paused", "Ad group": "QA_ONLY_GROUP",
                 "Ad group status": "Paused", "Keyword": text, "Criterion Type": match, "Status": "Paused"}
                for match in ["Exact", "Phrase"]]
    metadata = [{"Campaign": row["Campaign"], "Ad group": row["Ad group"], "Keyword": row["Keyword"],
                 "Match type": row["Criterion Type"], "Role": "QA_ONLY", "Proposed final URL": "https://example.invalid/qa/",
                 "Readiness": "QA_ONLY_UNAPPROVED", "Reason": "SYNTHETIC_TEST_ONLY", "Live-account evidence": "NOT VERIFIED"}
                for row in keywords]
    return keywords, metadata


def assemble(keywords=None, metadata=None):
    default_keywords, default_metadata = fixture()
    return hi.assemble(csv_bytes(hi.KEYWORD_FIELDS, default_keywords if keywords is None else keywords),
                       csv_bytes(hi.METADATA_FIELDS, default_metadata if metadata is None else metadata),
                       "2026-11-07", hi.expected_source_envelope())


class HistoricalIntakeTests(unittest.TestCase):
    def test_match_placements_are_one_unreviewed_phrase(self):
        document = assemble()
        self.assertEqual(document["counts"]["historical_placements"], 2)
        self.assertEqual(document["counts"]["distinct_unreviewed_candidates"], 1)
        self.assertEqual(document["candidates"][0]["match_types_seen"], ["EXACT", "PHRASE"])
        self.assertEqual(document["counts"]["reviewed_positive_rows"], 0)
        self.assertEqual(document["counts"]["reviewed_positive_deficit"], 14000)

    def test_original_text_and_metadata_preserved_exactly(self):
        keywords, metadata = fixture("  ＳＹＮＴＨＥＴＩＣ   property enquiry  ")
        document = assemble(keywords, metadata)
        self.assertEqual(document["placements"][0]["original_keyword_fields"], keywords[0])
        self.assertEqual(document["placements"][0]["original_metadata_fields"], metadata[0])
        self.assertEqual(document["candidates"][0]["original_text"], keywords[0]["Keyword"])
        self.assertEqual(document["candidates"][0]["normalized_text"], "synthetic property enquiry")

    def test_unicode_original_variants_not_lost(self):
        keywords, metadata = fixture()
        keywords[1]["Keyword"] = "ＳＹＮＴＨＥＴＩＣ PROPERTY ENQUIRY"
        metadata[1]["Keyword"] = keywords[1]["Keyword"]
        document = assemble(keywords, metadata)
        self.assertEqual(len(document["candidates"]), 1)
        self.assertEqual(len(document["candidates"][0]["original_text_variants"]), 2)

    def test_metadata_join_not_based_on_order(self):
        keywords, metadata = fixture()
        document = assemble(keywords, list(reversed(metadata)))
        self.assertEqual(document["placements"][0]["metadata_source_locator"]["record_ordinal"], 2)
        self.assertEqual(document["placements"][0]["original_metadata_fields"]["Match type"], "Exact")

    def test_duplicate_or_unmatched_metadata_rejected(self):
        keywords, metadata = fixture()
        with self.assertRaises(ValueError):
            assemble(keywords, metadata + metadata[:1])
        with self.assertRaises(ValueError):
            assemble(keywords, metadata[:1])
        with self.assertRaises(ValueError):
            assemble(keywords[:1], metadata)

    def test_status_and_live_evidence_changes_fail_closed(self):
        keywords, metadata = fixture()
        keywords[0]["Status"] = "Enabled"
        with self.assertRaises(ValueError):
            assemble(keywords, metadata)
        keywords, metadata = fixture()
        metadata[0]["Live-account evidence"] = "VERIFIED"
        with self.assertRaises(ValueError):
            assemble(keywords, metadata)

    def test_source_envelope_tampering_fails_closed(self):
        for change in ["missing", "freshness", "archive_hash", "member_hash"]:
            document = assemble()
            if change == "missing":
                document.pop("source")
            elif change == "freshness":
                document["source"]["freshness_verified"] = True
            elif change == "archive_hash":
                document["source"]["archive_sha256"] = "0" * 64
            else:
                document["source"]["selected_members"][0]["sha256"] = "0" * 64
            with self.subTest(change=change), self.assertRaises(ValueError):
                hi.validate_intake(document)

    def test_candidate_provenance_cannot_be_relabelled_observed(self):
        for field, value in [("source_kind", "first_party_observed"), ("source_id", "UNVERIFIED_REPLACEMENT")]:
            document = assemble()
            document["candidates"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                hi.validate_intake(document)

    def test_first_occurrence_identity_and_placement_order_preserved(self):
        a, am = fixture()
        b, bm = fixture("another synthetic phrase")
        document = assemble(a + b, am + bm)
        document["candidates"].reverse()
        for index, candidate in enumerate(document["candidates"], 1):
            candidate["candidate_id"] = f"LEGACY-POS-{index:04}"
        with self.assertRaises(ValueError):
            hi.validate_intake(document)
        document = assemble()
        document["candidates"][0]["placement_ids"].reverse()
        with self.assertRaises(ValueError):
            hi.validate_intake(document)

    def test_new_mapping_metrics_or_review_cannot_be_inferred(self):
        for key, value in [("primary_campaign_key", "BSRE-C0001"), ("volume", 1000), ("language", "en"), ("reviewer", "someone")]:
            document = assemble()
            document["candidates"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                hi.validate_intake(document)

    def test_completion_and_approval_claims_rejected(self):
        for change in ["count", "review", "approval", "deployment"]:
            document = assemble()
            if change == "count":
                document["counts"]["reviewed_positive_rows"] = 1
            elif change == "review":
                document["candidates"][0]["review_state"] = "REVIEWED"
            elif change == "approval":
                document["candidates"][0]["approval_state"] = "APPROVED"
            else:
                document["deployment_export_allowed"] = True
            with self.subTest(change=change), self.assertRaises(ValueError):
                hi.validate_intake(document)

    def test_lost_or_reused_placement_rejected(self):
        document = assemble()
        document["candidates"][0]["placement_ids"].pop()
        with self.assertRaises(ValueError):
            hi.validate_intake(document)
        document = assemble()
        document["candidates"][0]["placement_ids"].append(document["candidates"][0]["placement_ids"][0])
        with self.assertRaises(ValueError):
            hi.validate_intake(document)

    def test_archive_checksum_blocks_replacement_before_zip_read(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / "not-the-reviewed-archive.zip"
            archive.write_bytes(b"SYNTHETIC_TEST_ONLY_NOT_A_ZIP")
            with self.assertRaisesRegex(ValueError, "Archive checksum changed"):
                hi.read_pinned_archive(archive)

    def test_current_reviewed_validator_still_excludes_candidates(self):
        candidate = assemble()["candidates"][0]
        # Projection is for a negative-control test, never a promotion operation.
        record = {**candidate, "keyword_id": candidate["candidate_id"], "match_type": "EXACT",
                  "source_reference": "QA_ONLY", "evidence_ref": "QA_ONLY"}
        report = ka.audit("positive", [record], [], [], [], [], hi.date(2026, 11, 7))
        self.assertEqual(report["reviewed_eligible_rows"], 0)
        self.assertFalse(report["exact_target_pass"])
        self.assertFalse(report["deployment_export_allowed"])

    def test_saved_staging_artifact_counts_and_provenance(self):
        path = Path(__file__).parent / "staging" / "historical-intake.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        result = hi.validate_intake(document)
        self.assertEqual(result["historical_placements"], 82)
        self.assertEqual(result["distinct_unreviewed_candidates"], 41)
        self.assertEqual(document["source"]["archive_sha256"], hi.ARCHIVE_SHA256)
        self.assertEqual({row["member"]: {k: row[k] for k in ["sha256", "bytes"]} for row in document["source"]["selected_members"]}, hi.MEMBERS)
        report = json.loads((path.parent / "intake-validation.json").read_text(encoding="utf-8"))
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), report["intake_sha256"])
        text = path.read_text(encoding="utf-8")
        self.assertNotIn("C:/", text)
        self.assertNotIn("C:\\\\", text)
        self.assertNotIn("@", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)

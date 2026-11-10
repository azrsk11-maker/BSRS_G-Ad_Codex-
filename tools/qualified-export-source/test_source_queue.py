"""Temporary synthetic SQLite/evidence only; never produces provider conversions."""
import copy
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

import source_queue as source

NOW = datetime(2026, 11, 9, 12, tzinfo=timezone.utc)
OID = "11111111-1111-4111-8111-111111111111"


def fixture():
    row = {"outcome_id": OID, "lead_id": "SYNTHETIC-LEAD-001",
           "canonical_lead_id": "SYNTHETIC-LEAD-001", "person_key": "SYNTHETIC-PERSON-001",
           "person_dedup_confirmed": True, "role": "off_plan", "stage": "qualified_prospect",
           "occurred_at_utc": "2026-11-01T08:00:00.123456Z",
           "occurred_at_dubai": "2026-11-01T12:00:00.123456+04:00",
           "recorded_at_utc": "2026-11-01T08:10:00Z", "recorded_by": "SYNTHETIC-STAFF",
           "qualification_status": "QUALIFIED", "qualification_reason": "Synthetic fixture only",
           "contact_confirmed": True, "budget_inventory_fit_confirmed": True,
           "timeline_confirmed": True, "is_test": False, "source_evidence_reference": "SYNTHETIC-SOURCE",
           "export_state": "READY", "privacy_evidence_reference": "SYNTHETIC-PURPOSE",
           "ad_user_data": "GRANTED", "ad_personalization": "DENIED", "click_id_type": "GCLID",
           "click_id": "SYNTHETIC_NEVER_UPLOAD_Case-Sensitive.1", "conversion_action_id": "7878013428",
           "conversion_name": "qualified_lead", "order_id": "BSRE:" + OID}
    ledger = {"fixture_only": True, "history_complete": True,
              "history_evidence_reference": "SYNTHETIC-WHOLE-HISTORY",
              "intake": [{"lead_id": row["lead_id"], "role": row["role"],
                          "accepted_at_utc": "2026-11-01T07:00:00Z", "is_test": False}], "records": [row]}
    purpose = [{"lead_id": row["lead_id"], "evidence_id": "SYNTHETIC-PURPOSE",
                "decision_version": "synthetic-v1", "notice_version": "synthetic-v1",
                "observed_at_utc": "2026-11-01T06:55:00Z", "expires_at_utc": "2027-01-01T00:00:00Z",
                "acknowledged": True, "measurement_eligible": True, "ad_measurement": True,
                "ad_user_data": "GRANTED", "ad_personalization": "DENIED", "withdrawn_at_utc": None,
                "click_id_type": "GCLID", "click_id": row["click_id"],
                "attribution_captured_at_utc": "2026-11-01T06:56:00Z", "record_integrity_verified": True}]
    binding = {"customer_id": "573-038-4686", "conversion_owner_customer_id": "573-038-4686",
               "conversion_action_id": "7878013428", "conversion_name": "qualified_lead",
               "mapping_verified": True, "stage_key": "qualified_lead", "identifier_route": "GCLID_ONLY"}
    retention = {"schema": "bsre-qualified-retention-review-v1", "fixture_only": True,
                 "ledger_sha256": None, "history_incomplete": False, "history_marker_verified": True,
                 "history_marker_evidence_reference": "SYNTHETIC-RETENTION-READBACK",
                 "history_marker_read_at_utc": "2026-11-09T11:00:00Z",
                 "records": [{"outcome_id": OID, "closed_at_utc": None,
                              "retention_due_at_utc": "2026-12-01T00:00:00Z", "review_verified": True,
                              "evidence_reference": "SYNTHETIC-RETENTION"}]}
    return ledger, purpose, binding, retention


def snapshot(parts=None, **review_changes):
    ledger, purpose, binding, retention = copy.deepcopy(parts or fixture())
    raw = {"ledger": source.canonical(ledger).encode(), "purpose": source.canonical(purpose).encode(),
           "binding": source.canonical(binding).encode()}
    retention["ledger_sha256"] = source.digest(raw["ledger"])
    raw["retention"] = source.canonical(retention).encode()
    review = {"schema": "bsre-qualified-preparation-review-v1", "fixture_only": ledger["fixture_only"],
              **{key + "_sha256": source.digest(value) for key, value in raw.items()},
              "whole_history_reviewed": True, "permission_mapping_reviewed": True,
              "reviewer_reference": "SYNTHETIC-REVIEWER", "evidence_reference": "SYNTHETIC-REVIEW",
              "reviewed_at_utc": "2026-11-09T12:00:00Z", **review_changes}
    raw["review"] = source.canonical(review).encode()
    return source.Snapshot(raw)


class SourceQueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bsre-synthetic-qualified-")
        self.path = Path(self.temp.name) / "synthetic-only.sqlite"

    def tearDown(self):
        self.temp.cleanup()

    def reviewed(self, queue, item=None, now=NOW):
        item = item or snapshot()
        result = queue.stage(item, now)
        queue.mark_reviewed(OID, result["snapshot_sha256"], "SYNTHETIC-OWNER-REVIEW", now)
        return item

    def test_durable_idempotent_private_review_and_original_bytes(self):
        with source.PrivateQueue(self.path) as queue:
            item = self.reviewed(queue)
            original = queue.projection(item, NOW + timedelta(seconds=1))
            self.assertTrue(original["UPLOAD_PROHIBITED"])
            self.assertFalse(original["google_source_format_verified"])
            self.assertEqual(original["rows"][0]["original_gclid"], fixture()[0]["records"][0]["click_id"])
            self.assertEqual(original["rows"][0]["actual_qualified_at_utc"], "2026-11-01T08:00:00.123456Z")
            self.assertNotIn("conversion_time", original["rows"][0])
            self.assertNotIn("person_key", original["rows"][0])
        with source.PrivateQueue(self.path) as reopened:
            self.assertEqual(reopened.stage(item, NOW + timedelta(seconds=2))["states"], {"OWNER_REVIEWED": 1})
            self.assertEqual(len(reopened.projection(item, NOW + timedelta(seconds=3))["rows"]), 1)
            self.assertEqual(reopened.db.execute("SELECT count(*) FROM queue").fetchone()[0], 1)

    def test_review_never_confers_google_readiness(self):
        with source.PrivateQueue(self.path) as queue:
            item = snapshot()
            self.assertEqual(queue.projection(item, NOW)["rows"], [])
            self.reviewed(queue, item)
            result = queue.projection(item, NOW)
            self.assertEqual(result["artifact_type"], source.ARTIFACT)
            self.assertFalse(result["account_restricted_access_verified"])
            self.assertFalse(result["source_evidence_truth_independently_verified"])
            self.assertEqual(result["summary"]["network_calls"], 0)

    def test_changed_gclid_latches_conflict_and_preserves_original(self):
        with source.PrivateQueue(self.path) as queue:
            original = self.reviewed(queue)
            parts = fixture()
            parts[0]["records"][0]["click_id"] = parts[1][0]["click_id"] = "SYNTHETIC_DIFFERENT_NEVER_UPLOAD"
            altered = snapshot(parts)
            self.assertEqual(queue.projection(altered, NOW)["rows"], [])
            self.assertEqual(queue.projection(original, NOW)["rows"], [])
            row = queue.db.execute("SELECT * FROM queue").fetchone()
            self.assertEqual(json.loads(row["payload"])["original_gclid"], fixture()[0]["records"][0]["click_id"])
            self.assertTrue(row["identity_conflict_latched"])

    def test_changed_payload_cannot_hide_behind_temporary_ineligibility(self):
        with source.PrivateQueue(self.path) as queue:
            self.reviewed(queue)
            parts = fixture()
            parts[1][0]["ad_measurement"] = False
            queue.stage(snapshot(parts), NOW)
            parts[1][0]["ad_measurement"] = True
            parts[0]["records"][0]["click_id"] = parts[1][0]["click_id"] = "SYNTHETIC_CHANGED_AFTER_HOLD"
            self.assertIn("RESERVED_IDENTITY_CHANGED_REVIEW_REQUIRED", queue.stage(snapshot(parts), NOW)["hold_counts"])

    def test_cross_role_repeat_still_reserves_only_original_person(self):
        parts = fixture()
        later = copy.deepcopy(parts[0]["records"][0])
        later.update(outcome_id="22222222-2222-4222-8222-222222222222", lead_id="SYNTHETIC-LEAD-002",
                     role="seller", authority_confirmed=True, occurred_at_utc="2026-11-02T08:00:00Z",
                     occurred_at_dubai="2026-11-02T12:00:00+04:00", recorded_at_utc="2026-11-02T08:10:00Z")
        parts[0]["records"].append(later)
        parts[0]["intake"].append({"lead_id": later["lead_id"], "role": "seller",
                                   "accepted_at_utc": "2026-11-02T07:00:00Z", "is_test": False})
        with source.PrivateQueue(self.path) as queue:
            item = self.reviewed(queue, snapshot(parts))
            self.assertEqual([r["outcome_id"] for r in queue.projection(item, NOW)["rows"]], [OID])

    def test_unrelated_historical_hold_vetoes_all_rows(self):
        parts = fixture()
        bad = copy.deepcopy(parts[0]["records"][0])
        bad.update(outcome_id="22222222-2222-4222-8222-222222222222", person_key="SYNTHETIC-PERSON-002",
                   canonical_lead_id="SYNTHETIC-MISSING-INTAKE")
        parts[0]["records"].append(bad)
        with source.PrivateQueue(self.path) as queue:
            result = queue.stage(snapshot(parts), NOW)
            self.assertIn("WHOLE_HISTORY_HAS_UNRESOLVED_BUSINESS_HOLDS", result["hold_counts"])

    def test_exact_action_binding_rejects_accepted_action(self):
        parts = fixture()
        parts[2]["conversion_action_id"] = "7873290954"
        with source.PrivateQueue(self.path) as queue:
            result = queue.stage(snapshot(parts), NOW)
            self.assertIn("ACTION_BINDING_NOT_VERIFIED", result["hold_counts"])
            self.assertIsNone(queue.db.execute("SELECT payload FROM queue").fetchone()[0])

    def test_new_snapshot_requires_owner_review_again(self):
        with source.PrivateQueue(self.path) as queue:
            self.reviewed(queue)
            changed = snapshot(evidence_reference="SYNTHETIC-NEW-REVIEW")
            self.assertEqual(queue.projection(changed, NOW)["rows"], [])
            self.assertEqual(queue.summary()["states"], {"OWNER_REVIEW": 1})

    def test_exact_hash_review_rejects_tampered_input_before_write(self):
        item = snapshot()
        item.hashes["purpose"] = "a" * 64
        with source.PrivateQueue(self.path) as queue:
            with self.assertRaisesRegex(source.SourceError, "REVIEW_EXACT_INPUT_HASH_MISMATCH"):
                queue.stage(item, NOW)
            self.assertEqual(queue.summary()["states"], {})

    def test_withdrawal_is_durable_despite_removed_or_new_evidence(self):
        with source.PrivateQueue(self.path) as queue:
            original = self.reviewed(queue)
            parts = fixture()
            parts[1][0]["withdrawn_at_utc"] = "2026-11-09T11:00:00Z"
            self.assertEqual(queue.projection(snapshot(parts), NOW)["rows"], [])
            self.assertIsNone(queue.db.execute("SELECT payload FROM queue").fetchone()[0])
        with source.PrivateQueue(self.path) as reopened:
            self.assertIn("WITHDRAWAL_LATCHED", reopened.stage(original, NOW)["hold_counts"])
            self.assertEqual(reopened.projection(original, NOW)["rows"], [])

    def test_withdrawal_when_business_ineligible_cannot_revive(self):
        with source.PrivateQueue(self.path) as queue:
            original = self.reviewed(queue)
            parts = fixture()
            parts[0]["records"][0]["contact_confirmed"] = False
            parts[1][0]["withdrawn_at_utc"] = "2026-11-09T11:00:00Z"
            self.assertIn("WITHDRAWAL_LATCHED", queue.stage(snapshot(parts), NOW)["hold_counts"])
            self.assertIsNone(queue.db.execute("SELECT payload FROM queue").fetchone()[0])
            self.assertEqual(queue.projection(original, NOW)["rows"], [])

    def test_fresh_expiry_purges_and_records_no_person_tombstone(self):
        with source.PrivateQueue(self.path) as queue:
            item = self.reviewed(queue)
            expired = datetime(2026, 12, 1, tzinfo=timezone.utc)
            result = queue.projection(item, expired)
            self.assertEqual(result["rows"], [])
            self.assertTrue(result["summary"]["durable_history_gap"])
            self.assertEqual(queue.db.execute("SELECT count(*) FROM queue").fetchone()[0], 0)
            queue.stage(item, expired)
            self.assertEqual(queue.db.execute("SELECT count(*) FROM queue").fetchone()[0], 0)
        raw = self.path.read_bytes()
        self.assertNotIn(b"SYNTHETIC-PERSON-001", raw)
        self.assertNotIn(b"SYNTHETIC_NEVER_UPLOAD", raw)

    def test_purge_gap_survives_new_complete_attestation(self):
        with source.PrivateQueue(self.path) as queue:
            self.reviewed(queue)
            later = datetime(2026, 12, 2, tzinfo=timezone.utc)
            self.assertEqual(queue.purge(later)["private_rows_purged"], 1)
            parts = fixture()
            parts[3]["records"][0]["retention_due_at_utc"] = "2026-12-30T00:00:00Z"
            item = snapshot(parts)
            self.assertIn("DURABLE_HISTORY_GAP", queue.stage(item, later)["evaluation_hold_counts"])
            self.assertEqual(queue.db.execute("SELECT count(*) FROM queue").fetchone()[0], 0)
            with self.assertRaisesRegex(source.SourceError, "REVIEW_SNAPSHOT_MISMATCH"):
                queue.mark_reviewed(OID, item.sha256, "SYNTHETIC-OWNER", later)

    def test_authoritative_retention_gap_vetoes_first_run_and_latches(self):
        parts = fixture()
        parts[3]["history_incomplete"] = True
        with source.PrivateQueue(self.path) as queue:
            result = queue.stage(snapshot(parts), NOW)
            self.assertTrue(result["durable_history_gap"])
            self.assertIn("AUTHORITATIVE_RETENTION_HISTORY_NOT_COMPLETE", result["evaluation_hold_counts"])
            self.assertIn("DURABLE_HISTORY_GAP", queue.stage(snapshot(), NOW)["evaluation_hold_counts"])
            self.assertEqual(queue.db.execute("SELECT count(*) FROM queue").fetchone()[0], 0)

    def test_missing_retention_history_evidence_cannot_be_assumed_complete(self):
        parts = fixture()
        parts[3]["history_incomplete"] = None
        parts[3]["history_marker_verified"] = False
        with source.PrivateQueue(self.path) as queue:
            self.assertIn("AUTHORITATIVE_RETENTION_HISTORY_NOT_COMPLETE", queue.stage(snapshot(parts), NOW)["hold_counts"])

    def test_missing_reserved_person_marks_durable_gap(self):
        with source.PrivateQueue(self.path) as queue:
            self.reviewed(queue)
            parts = fixture()
            parts[0]["records"].clear()
            self.assertTrue(queue.stage(snapshot(parts), NOW)["durable_history_gap"])
            self.assertEqual(queue.projection(snapshot(), NOW)["rows"], [])

    def test_retention_cannot_exceed_twelve_calendar_months_after_closure(self):
        parts = fixture()
        parts[3]["records"][0].update(closed_at_utc="2025-11-08T00:00:00Z",
                                      retention_due_at_utc="2026-11-09T00:00:00Z")
        with self.assertRaisesRegex(source.SourceError, "TWELVE_MONTH_CLOSURE_RETENTION_REQUIRED"):
            snapshot(parts).evaluate(NOW)

    def test_stale_owner_review_and_backwards_clock_rejected(self):
        with source.PrivateQueue(self.path) as queue:
            item = snapshot()
            queue.stage(item, NOW + timedelta(seconds=2))
            with self.assertRaisesRegex(source.SourceError, "REVIEW_SNAPSHOT_MISMATCH"):
                queue.mark_reviewed(OID, "a" * 64, "SYNTHETIC-OWNER", NOW + timedelta(seconds=2))
            with self.assertRaisesRegex(source.SourceError, "QUEUE_TIME_CANNOT_MOVE_BACKWARDS"):
                queue.stage(item, NOW + timedelta(seconds=1))

    def test_fixture_classification_cannot_change_existing_queue(self):
        with source.PrivateQueue(self.path) as queue:
            queue.stage(snapshot(), NOW)
            parts = fixture()
            parts[0]["fixture_only"] = parts[3]["fixture_only"] = False
            with self.assertRaisesRegex(source.SourceError, "QUEUE_FIXTURE_CLASSIFICATION_MISMATCH"):
                queue.stage(snapshot(parts), NOW)
            self.assertTrue(queue.summary()["fixture_only"])

    def test_extra_contact_field_rejected_and_cli_never_leaks_values(self):
        parts = fixture()
        parts[1][0]["email"] = "synthetic-private@example.invalid"
        item = snapshot(parts)
        paths = {}
        for name in source.INPUT_NAMES:
            path = Path(self.temp.name) / (name + ".json")
            path.write_text(source.canonical(item.values[name]), encoding="utf-8")
            paths[name] = path
        args = ["stage", "--db", str(self.path), "--now", NOW.isoformat()]
        for name, path in paths.items():
            args += ["--" + name, str(path)]
        capture = io.StringIO()
        with redirect_stdout(capture):
            self.assertEqual(source.main(args), 2)
        self.assertNotIn("synthetic-private", capture.getvalue())
        self.assertNotIn(str(self.path), capture.getvalue())
        self.assertFalse(self.path.exists())

    def test_repository_output_is_rejected(self):
        with self.assertRaisesRegex(source.SourceError, "PRIVATE_OUTPUT_OUTSIDE_REPOSITORY_REQUIRED"):
            source.PrivateQueue(source.HERE / "must-never-exist.sqlite")

    def test_database_write_transaction_rolls_back_on_failure(self):
        with source.PrivateQueue(self.path) as queue:
            queue.db.execute("CREATE TRIGGER synthetic_failure BEFORE INSERT ON queue BEGIN SELECT RAISE(ABORT, 'synthetic'); END")
            with self.assertRaises(sqlite3.Error):
                queue.stage(snapshot(), NOW)
            self.assertEqual(queue.summary()["states"], {})
            self.assertIsNone(queue._meta("snapshot_sha256"))

    def test_two_connections_reserve_the_same_candidate_once(self):
        with source.PrivateQueue(self.path):
            pass
        def stage_independently(_):
            with source.PrivateQueue(self.path) as queue:
                return queue.stage(snapshot(), NOW)["states"]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(stage_independently, range(2)))
        self.assertEqual(results, [{"OWNER_REVIEW": 1}, {"OWNER_REVIEW": 1}])
        with source.PrivateQueue(self.path) as queue:
            self.assertEqual(queue.db.execute("SELECT count(*) FROM queue").fetchone()[0], 1)

    def test_unrelated_sqlite_file_is_rejected_without_schema_writes(self):
        unrelated = sqlite3.connect(self.path)
        try:
            unrelated.execute("CREATE TABLE unrelated (value TEXT)")
            unrelated.commit()
        finally:
            unrelated.close()
        before = self.path.read_bytes()
        with self.assertRaisesRegex(source.SourceError, "QUEUE_SCHEMA_MISMATCH"):
            source.PrivateQueue(self.path)
        self.assertEqual(self.path.read_bytes(), before)

    def test_later_permission_readback_requires_original_grant_at_capture(self):
        parts = fixture()
        original = copy.deepcopy(parts[1][0])
        parts[1][0]["observed_at_utc"] = "2026-11-09T11:00:00Z"
        with source.PrivateQueue(self.path) as queue:
            result = queue.stage(snapshot(parts), NOW)
            self.assertIn("ORIGINAL_PERMISSION_AT_CAPTURE_NOT_ESTABLISHED", result["hold_counts"])
            self.assertIsNone(queue.db.execute("SELECT payload FROM queue").fetchone()[0])
            parts[1].append(original)
            self.assertEqual(queue.stage(snapshot(parts), NOW)["states"], {"OWNER_REVIEW": 1})

    def test_denied_original_purpose_cannot_be_retroactively_granted(self):
        parts = fixture()
        original = copy.deepcopy(parts[1][0])
        original["ad_measurement"] = False
        parts[1][0]["observed_at_utc"] = "2026-11-09T11:00:00Z"
        parts[1].append(original)
        with source.PrivateQueue(self.path) as queue:
            self.assertIn("ORIGINAL_PERMISSION_AT_CAPTURE_NOT_ESTABLISHED", queue.stage(snapshot(parts), NOW)["hold_counts"])


if __name__ == "__main__":
    unittest.main()

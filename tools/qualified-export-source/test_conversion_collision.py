"""Synthetic regressions for the private qualified queue's conversion identity."""
import copy
from pathlib import Path
import tempfile
import unittest

import source_queue as source
from test_source_queue import NOW, OID, fixture, snapshot


SECOND = "22222222-2222-4222-8222-222222222222"
COLLISION = "QUALIFIED_CONVERSION_IDENTITY_COLLISION"


def two_outcomes():
    ledger, purpose, binding, retention = fixture()
    row = copy.deepcopy(ledger["records"][0])
    lead = "SYNTHETIC-LEAD-002"
    row.update(outcome_id=SECOND, lead_id=lead, canonical_lead_id=lead,
               person_key="SYNTHETIC-PERSON-002", order_id="BSRE:" + SECOND)
    ledger["records"].append(row)
    ledger["intake"].append({**ledger["intake"][0], "lead_id": lead})
    purpose.append({**purpose[0], "lead_id": lead})
    retention["records"].append({**retention["records"][0], "outcome_id": SECOND})
    return ledger, purpose, binding, retention


class ConversionCollisionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="bsre-synthetic-conversion-")
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)

    def test_two_ready_outcomes_with_one_conversion_identity_hold_both(self):
        parts = two_outcomes()
        second = parts[0]["records"][1]
        second["occurred_at_utc"] = "2026-11-01T08:00:00.1234560Z"
        for name, records in (("forward", parts[0]["records"]),
                              ("reverse", list(reversed(parts[0]["records"])))):
            with self.subTest(order=name), source.PrivateQueue(self.directory / name) as queue:
                ledger = {**parts[0], "records": records}
                item = snapshot((ledger, *parts[1:]))
                result = queue.stage(item, NOW)
                self.assertEqual(result["states"], {"HELD": 2})
                self.assertEqual(result["hold_counts"], {COLLISION: 2})
                self.assertEqual(queue.db.execute("SELECT count(payload) FROM queue").fetchone()[0], 0)
                for oid in (OID, SECOND):
                    with self.assertRaisesRegex(source.SourceError, "REVIEW_HELD_OR_EXPIRED"):
                        queue.mark_reviewed(oid, item.sha256, "SYNTHETIC-REVIEWER", NOW)
                projection = queue.projection(item, NOW)
                self.assertEqual(projection["rows"], [])
                self.assertIs(projection["UPLOAD_PROHIBITED"], True)
                business = source.audit_history(item.values["ledger"], NOW)
                self.assertEqual(business["counts"]["unambiguous_first_qualifications_in_supplied_window"], 2)

    def test_later_collision_invalidates_the_previous_exact_snapshot_review(self):
        with source.PrivateQueue(self.directory / "queue") as queue:
            first = snapshot()
            queue.stage(first, NOW)
            queue.mark_reviewed(OID, first.sha256, "SYNTHETIC-REVIEWER", NOW)
            original = queue.projection(first, NOW)["rows"][0]
            new = snapshot(two_outcomes())
            self.assertEqual(queue.projection(new, NOW)["rows"], [])
            self.assertEqual(queue.summary()["hold_counts"], {COLLISION: 2})
            self.assertEqual(queue.projection(first, NOW)["rows"], [])
            stored = queue.db.execute("SELECT payload, reviewed_snapshot_sha256 FROM queue WHERE outcome_id=?",
                                      (OID,)).fetchone()
            self.assertIsNone(stored["reviewed_snapshot_sha256"])
            self.assertEqual(source.strict_json_bytes(stored["payload"].encode())["actual_qualified_at_utc"],
                             original["actual_qualified_at_utc"])

    def test_prior_submitted_outcome_holds_distinct_ready_outcome(self):
        for state in ("EXPORTED", "PENDING_RESULT", "IMPORTED"):
            with self.subTest(state=state), source.PrivateQueue(self.directory / state) as queue:
                parts = two_outcomes()
                parts[0]["records"][0]["export_state"] = state
                item = snapshot(parts)
                result = queue.stage(item, NOW)
                self.assertEqual(result["states"], {"HELD": 2})
                self.assertEqual(result["hold_counts"][COLLISION], 1)
                self.assertEqual(result["hold_counts"]["NOT_READY_OR_ALREADY_EXPORTED"], 1)
                with self.assertRaisesRegex(source.SourceError, "REVIEW_HELD_OR_EXPIRED"):
                    queue.mark_reviewed(SECOND, item.sha256, "SYNTHETIC-REVIEWER", NOW)
                self.assertEqual(queue.projection(item, NOW)["rows"], [])

    def test_distinct_instant_or_click_case_preserves_original_bytes(self):
        for distinguish_by in ("time", "submicrosecond", "case"):
            with self.subTest(distinguish_by=distinguish_by), source.PrivateQueue(
                    self.directory / distinguish_by) as queue:
                parts = two_outcomes()
                second = parts[0]["records"][1]
                if distinguish_by == "time":
                    second.update(occurred_at_utc="2026-11-01T08:00:00.123455Z",
                                  occurred_at_dubai="2026-11-01T12:00:00.123455+04:00")
                elif distinguish_by == "submicrosecond":
                    second.update(occurred_at_utc="2026-11-01T08:00:00.1234561Z",
                                  occurred_at_dubai="2026-11-01T12:00:00.1234561+04:00")
                else:
                    second["click_id"] = parts[1][1]["click_id"] = second["click_id"].lower()
                item = snapshot(parts)
                self.assertEqual(queue.stage(item, NOW)["states"], {"OWNER_REVIEW": 2})
                for oid in (OID, SECOND):
                    queue.mark_reviewed(oid, item.sha256, "SYNTHETIC-REVIEWER", NOW)
                rows = queue.projection(item, NOW)["rows"]
                self.assertEqual(len(rows), 2)
                self.assertEqual(rows[1]["actual_qualified_at_utc"], second["occurred_at_utc"])
                self.assertEqual(rows[1]["original_gclid"], second["click_id"])

    def test_exact_ledger_retry_is_not_a_second_conversion(self):
        parts = fixture()
        parts[0]["records"].append(copy.deepcopy(parts[0]["records"][0]))
        item = snapshot(parts)
        with source.PrivateQueue(self.directory / "queue") as queue:
            self.assertEqual(queue.stage(item, NOW)["states"], {"OWNER_REVIEW": 1})
            queue.mark_reviewed(OID, item.sha256, "SYNTHETIC-REVIEWER", NOW)
            self.assertEqual(len(queue.projection(item, NOW)["rows"]), 1)

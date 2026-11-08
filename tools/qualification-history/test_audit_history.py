"""Synthetic tests only. No private history, network, or upload operation."""
import copy
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import audit_history as audit

HERE = Path(__file__).resolve().parent
NOW = datetime(2026, 11, 8, 12, tzinfo=timezone.utc)


def ledger_fixture():
    """Explicit synthetic data exercising the non-fixture attestation branch."""
    row = {
        "outcome_id": "11111111-1111-4111-8111-111111111111",
        "lead_id": "BSRE-SYNTHETIC-001",
        "canonical_lead_id": "BSRE-SYNTHETIC-001",
        "person_key": "SYNTHETIC-PERSON-001",
        "person_dedup_confirmed": True,
        "role": "off_plan",
        "stage": "qualified_prospect",
        "occurred_at_utc": "2026-11-01T08:00:00Z",
        "occurred_at_dubai": "2026-11-01T12:00:00+04:00",
        "recorded_at_utc": "2026-11-01T08:10:00Z",
        "recorded_by": "SYNTHETIC-REVIEWER",
        "qualification_status": "QUALIFIED",
        "qualification_reason": "Synthetic qualified record for local test only",
        "contact_confirmed": True,
        "budget_inventory_fit_confirmed": True,
        "timeline_confirmed": True,
        "is_test": False,
        "source_evidence_reference": "SYNTHETIC-SOURCE",
        "export_state": "NOT_READY",
    }
    return {
        "fixture_only": False,
        "history_complete": True,
        "history_evidence_reference": "SYNTHETIC-HISTORY-ATTESTATION",
        "intake": [{
            "lead_id": row["lead_id"], "role": row["role"],
            "accepted_at_utc": "2026-11-01T07:00:00Z", "is_test": False,
        }],
        "records": [row],
    }


def append_later_role(ledger):
    row = copy.deepcopy(ledger["records"][0])
    row.update({
        "outcome_id": "22222222-2222-4222-8222-222222222222",
        "lead_id": "BSRE-SYNTHETIC-002", "role": "seller", "authority_confirmed": True,
        "occurred_at_utc": "2026-11-02T08:00:00Z",
        "occurred_at_dubai": "2026-11-02T12:00:00+04:00",
        "recorded_at_utc": "2026-11-02T08:10:00Z",
    })
    ledger["intake"].append({
        "lead_id": row["lead_id"], "role": row["role"],
        "accepted_at_utc": "2026-11-02T07:00:00Z", "is_test": False,
    })
    ledger["records"].append(row)
    return row


def source_fixture(ledger, digest):
    row = ledger["records"][0]
    return {
        "schema": "bsre-qualified-source-review-v1", "fixture_only": ledger["fixture_only"],
        "ledger_sha256": digest,
        "records": [{
            "outcome_id": row["outcome_id"], "lead_id": row["lead_id"],
            "source_group": "OTHER_SOURCE", "evidence_kind": "OTHER_SOURCE_BUSINESS_REVIEW",
            "evidence_reference": "SYNTHETIC-SOURCE", "evidence_sha256": "a" * 64,
            "reviewer_reference": "SYNTHETIC-REVIEWER", "reviewed_at_utc": "2026-11-02T10:00:00Z",
            "review_verified": True, "customer_id": None, "campaign_id": None,
        }],
    }


class AuditHistoryTests(unittest.TestCase):
    def run_audit(self, ledger=None, **kwargs):
        return audit.audit_history(ledger if ledger is not None else ledger_fixture(), NOW, **kwargs)

    def test_complete_attestation_does_not_claim_independent_truth(self):
        result = self.run_audit()
        self.assertEqual(result["history"]["staff_attested_first_qualification_total"], 1)
        self.assertFalse(result["history"]["truth_independently_verified"])
        self.assertFalse(result["upload_supported"])
        self.assertEqual(result["provided_history_by_source"]["UNKNOWN_SOURCE"], 1)

    def test_cross_role_canonical_is_counted_once(self):
        ledger = ledger_fixture()
        append_later_role(ledger)
        result = self.run_audit(ledger)
        self.assertEqual(result["provided_history_by_role"], {"off_plan": 1})
        self.assertEqual(result["history"]["staff_attested_first_qualification_total"], 1)

    def test_full_history_dedup_precedes_date_window(self):
        ledger = ledger_fixture()
        append_later_role(ledger)
        result = self.run_audit(ledger, from_day="2026-11-02", to_day="2026-11-02")
        self.assertEqual(result["history"]["staff_attested_first_qualification_total"], 0)
        self.assertEqual(result["provided_history_by_dubai_day"], {})

    def test_duplicate_unchanged_retry_is_one(self):
        ledger = ledger_fixture()
        ledger["records"].append(copy.deepcopy(ledger["records"][0]))
        self.assertEqual(self.run_audit(ledger)["history"]["staff_attested_first_qualification_total"], 1)

    def test_role_mismatch_holds_total(self):
        ledger = ledger_fixture()
        ledger["intake"][0]["role"] = "resale"
        result = self.run_audit(ledger)
        self.assertEqual(result["outcome_hold_counts"]["ROLE_JOIN_MISMATCH"], 1)
        self.assertIsNone(result["history"]["staff_attested_first_qualification_total"])

    def test_boolean_strings_cannot_establish_confirmation(self):
        for field in ("contact_confirmed", "person_dedup_confirmed", "is_test"):
            with self.subTest(field=field):
                ledger = ledger_fixture()
                ledger["records"][0][field] = "true"
                result = self.run_audit(ledger)
                self.assertEqual(result["outcome_hold_counts"]["OUTCOME_SCHEMA_INVALID"], 1)
                self.assertIsNone(result["history"]["staff_attested_first_qualification_total"])
        ledger = ledger_fixture()
        ledger["intake"][0]["is_test"] = "false"
        with self.assertRaises(audit.AuditInputError):
            self.run_audit(ledger)

    def test_same_time_distinct_outcomes_hold_and_are_not_counted(self):
        ledger = ledger_fixture()
        duplicate = copy.deepcopy(ledger["records"][0])
        duplicate["outcome_id"] = "22222222-2222-4222-8222-222222222222"
        ledger["records"].append(duplicate)
        result = self.run_audit(ledger)
        self.assertEqual(result["counts"]["tied_first_qualification_people"], 1)
        self.assertEqual(result["counts"]["unambiguous_first_qualifications_in_supplied_window"], 0)
        self.assertEqual(sum(result["provided_history_by_source"].values()), 0)
        self.assertIsNone(result["history"]["staff_attested_first_qualification_total"])

    def test_conflicting_outcome_id_holds_person(self):
        ledger = ledger_fixture()
        duplicate = copy.deepcopy(ledger["records"][0])
        duplicate["recorded_by"] = "SYNTHETIC-CONFLICT"
        ledger["records"].append(duplicate)
        result = self.run_audit(ledger)
        self.assertEqual(result["outcome_hold_counts"]["CONFLICTING_OUTCOME_ID"], 1)
        self.assertEqual(result["counts"]["held_person_mappings"], 1)
        self.assertIsNone(result["history"]["staff_attested_first_qualification_total"])

    def test_conflicting_canonical_mapping_holds_person(self):
        ledger = ledger_fixture()
        later = append_later_role(ledger)
        later["canonical_lead_id"] = later["lead_id"]
        result = self.run_audit(ledger)
        self.assertEqual(result["counts"]["held_person_mappings"], 1)
        self.assertIsNone(result["history"]["staff_attested_first_qualification_total"])

    def test_incomplete_unreferenced_and_fixture_history_withholds_total(self):
        for update in ({"history_complete": False}, {"history_evidence_reference": None}, {"fixture_only": True}):
            with self.subTest(update=update):
                ledger = ledger_fixture()
                ledger.update(update)
                result = self.run_audit(ledger)
                self.assertEqual(result["counts"]["unambiguous_first_qualifications_in_supplied_window"], 1)
                self.assertIsNone(result["history"]["staff_attested_first_qualification_total"])
        ledger = ledger_fixture()
        ledger["history_evidence_reference"] = "   "
        with self.assertRaises(audit.AuditInputError):
            self.run_audit(ledger)

    def test_test_intake_is_excluded(self):
        ledger = ledger_fixture()
        ledger["intake"][0]["is_test"] = True
        result = self.run_audit(ledger)
        self.assertEqual(result["outcome_hold_counts"], {"TEST_RECORD": 1})
        self.assertEqual(result["history"]["staff_attested_first_qualification_total"], 0)

    def test_contact_intake_unknown_fields_and_schema_extras_rejected(self):
        ledger = ledger_fixture()
        ledger["intake"][0]["email"] = "private-canary@example.invalid"
        with self.assertRaises(audit.AuditInputError):
            self.run_audit(ledger)
        ledger = ledger_fixture()
        ledger["unexpected"] = "private-canary"
        with self.assertRaises(audit.AuditInputError):
            self.run_audit(ledger)
        ledger = ledger_fixture()
        ledger["records"][0]["unexpected"] = "private-canary"
        self.assertEqual(self.run_audit(ledger)["outcome_hold_counts"]["OUTCOME_SCHEMA_INVALID"], 1)

    def test_allowed_private_fields_and_identifiers_never_escape(self):
        ledger = ledger_fixture()
        ledger["records"][0].update({
            "staff_notes": "private-canary@example.invalid +971555000000",
            "privacy_evidence_reference": "SECRET-REFERENCE-CANARY",
            "click_id_type": "GCLID", "click_id": "SECRET-CLICK-CANARY",
        })
        encoded = json.dumps(self.run_audit(ledger))
        for value in list(ledger["records"][0].values()) + [ledger["history_evidence_reference"]]:
            if isinstance(value, str) and ("CANARY" in value or "SYNTHETIC" in value or "private-canary" in value):
                self.assertNotIn(value, encoded)
        self.assertNotIn(ledger["records"][0]["outcome_id"], encoded)

    def test_optional_source_review_is_bound_to_exact_ledger(self):
        ledger = ledger_fixture()
        digest = hashlib.sha256(json.dumps(ledger).encode()).hexdigest()
        source = source_fixture(ledger, digest)
        result = self.run_audit(ledger, source_review=source, ledger_sha256=digest)
        self.assertEqual(result["provided_history_by_source"]["OTHER_SOURCE"], 1)
        self.assertTrue(result["source_review_bound_to_ledger_bytes"])
        with self.assertRaises(audit.AuditInputError):
            self.run_audit(ledger, source_review=source, ledger_sha256="b" * 64)

    def test_ads_attribution_requires_existing_native_review(self):
        ledger = ledger_fixture()
        source = source_fixture(ledger, "a" * 64)
        source["records"][0].update({
            "source_group": "ADS_ATTRIBUTED", "evidence_kind": "GOOGLE_ADS_NATIVE_RECONCILIATION",
            "customer_id": "573-038-4686", "campaign_id": "24372566774",
        })
        result = self.run_audit(ledger, source_review=source, ledger_sha256="a" * 64)
        self.assertEqual(result["provided_history_by_source"]["ADS_ATTRIBUTED"], 1)
        source["records"][0]["customer_id"] = "UNAPPROVED-ACCOUNT"
        result = self.run_audit(ledger, source_review=source, ledger_sha256="a" * 64)
        self.assertEqual(result["provided_history_by_source"]["UNKNOWN_SOURCE"], 1)
        self.assertEqual(result["source_review_hold_counts"]["ADS_ACCOUNT_OR_CAMPAIGN_NOT_ALLOWLISTED"], 1)

    def test_row_bounds_and_boolean_envelope(self):
        ledger = ledger_fixture()
        with patch.object(audit, "MAX_ROWS", 0):
            with self.assertRaises(audit.AuditInputError):
                self.run_audit(ledger)
        ledger["history_complete"] = "true"
        with self.assertRaises(audit.AuditInputError):
            self.run_audit(ledger)

    def test_filters_and_now_are_explicit_valid_times(self):
        for kwargs in ({"from_day": "2026-1-1"}, {"to_day": "bad-private-canary"},
                       {"from_day": "2026-11-02", "to_day": "2026-11-01"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(audit.AuditInputError):
                self.run_audit(**kwargs)
        for invalid in (None, datetime(2026, 11, 8)):
            with self.subTest(invalid=invalid), self.assertRaises(audit.AuditInputError):
                audit.audit_history(ledger_fixture(), invalid)

    def run_cli(self, raw, extra_args=()):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "private-canary-ledger.json"
            path.write_bytes(raw)
            before = {file.name for file in Path(directory).iterdir()}
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                status = audit.main(["--ledger", str(path), "--now", "2026-11-08T12:00:00Z", *extra_args])
            self.assertEqual({file.name for file in Path(directory).iterdir()}, before)
            self.assertEqual(err.getvalue(), "")
            self.assertNotIn(str(path), out.getvalue())
            return status, json.loads(out.getvalue())

    def test_cli_is_stdout_only_aggregate_success(self):
        status, result = self.run_cli(json.dumps(ledger_fixture()).encode())
        self.assertEqual(status, 0)
        self.assertEqual(result["counts"]["outcome_rows_supplied"], 1)
        self.assertFalse(result["contains_record_identifiers_or_click_data"])

    def test_duplicate_key_nonfinite_malformed_and_private_error_are_safe(self):
        for raw in (b'{"secret-canary":1,"secret-canary":2}', b'{"secret-canary":NaN}',
                    b'{secret-canary', b'\xff'):
            with self.subTest(raw=raw):
                status, result = self.run_cli(raw)
                self.assertEqual(status, 2)
                self.assertNotIn("secret-canary", json.dumps(result))
        ledger = ledger_fixture()
        ledger["intake"][0]["email"] = "private-canary@example.invalid"
        status, result = self.run_cli(json.dumps(ledger).encode())
        self.assertEqual(status, 2)
        self.assertNotIn("private-canary", json.dumps(result))

    def test_file_bounds_and_argument_error_have_safe_codes(self):
        with patch.object(audit, "MAX_FILE_BYTES", 3):
            status, result = self.run_cli(b"1234")
        self.assertEqual(status, 2)
        self.assertEqual(result["code"], "INPUT_SIZE_LIMIT")
        status, result = self.run_cli(b"{}", ["--private-canary-argument"])
        self.assertEqual(status, 2)
        self.assertEqual(result["code"], "ARGUMENTS_INVALID")

    def test_reader_rejects_changed_input_and_unavailable_path(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "private-canary-ledger.json"
            path.write_bytes(b"{}")
            initial = path.lstat()
            before = SimpleNamespace(st_mode=initial.st_mode, st_size=2, st_mtime_ns=1,
                                     st_dev=initial.st_dev, st_ino=initial.st_ino)
            after = SimpleNamespace(st_mode=initial.st_mode, st_size=2, st_mtime_ns=2,
                                    st_dev=initial.st_dev, st_ino=initial.st_ino)
            with patch.object(audit.os, "fstat", side_effect=[before, after]):
                with self.assertRaisesRegex(audit.AuditInputError, "^INPUT_CHANGED_DURING_READ$"):
                    audit.read_bounded(path)
            with self.assertRaisesRegex(audit.AuditInputError, "^INPUT_UNAVAILABLE$"):
                audit.read_bounded(Path(directory) / "missing-private-canary.json")

    def test_nonregular_path_is_rejected_before_open(self):
        for mode in (stat.S_IFIFO, stat.S_IFCHR, stat.S_IFBLK, stat.S_IFSOCK, stat.S_IFDIR, stat.S_IFLNK):
            with self.subTest(mode=mode):
                metadata = SimpleNamespace(st_mode=mode)
                with patch.object(Path, "lstat", return_value=metadata), patch.object(audit.os, "open") as opener:
                    with self.assertRaisesRegex(audit.AuditInputError, "^INPUT_TYPE_NOT_REGULAR$"):
                        audit.read_bounded(Path("private-canary"))
                opener.assert_not_called()

    def test_nonregular_descriptor_is_rejected_before_read_and_closed(self):
        initial = SimpleNamespace(st_mode=stat.S_IFREG, st_size=2, st_dev=1, st_ino=1)
        special = SimpleNamespace(st_mode=stat.S_IFIFO)
        with patch.object(Path, "lstat", return_value=initial), \
                patch.object(audit.os, "open", return_value=99) as opener, \
                patch.object(audit.os, "fstat", return_value=special), \
                patch.object(audit.os, "fdopen") as reader, \
                patch.object(audit.os, "close") as closer, \
                patch.object(audit.os, "O_NONBLOCK", 1 << 24, create=True), \
                patch.object(audit.os, "O_NOFOLLOW", 1 << 25, create=True):
            with self.assertRaisesRegex(audit.AuditInputError, "^INPUT_TYPE_NOT_REGULAR$"):
                audit.read_bounded(Path("private-canary"))
        flags = opener.call_args.args[1]
        self.assertTrue(flags & (1 << 24))
        self.assertTrue(flags & (1 << 25))
        reader.assert_not_called()
        closer.assert_called_once_with(99)

    def test_changed_identity_before_read_is_rejected_and_closed(self):
        initial = SimpleNamespace(st_mode=stat.S_IFREG, st_size=2, st_dev=1, st_ino=1)
        changed = SimpleNamespace(st_mode=stat.S_IFREG, st_size=2, st_dev=1, st_ino=2)
        with patch.object(Path, "lstat", return_value=initial), \
                patch.object(audit.os, "open", return_value=99), \
                patch.object(audit.os, "fstat", return_value=changed), \
                patch.object(audit.os, "fdopen") as reader, \
                patch.object(audit.os, "close") as closer:
            with self.assertRaisesRegex(audit.AuditInputError, "^INPUT_CHANGED_DURING_READ$"):
                audit.read_bounded(Path("private-canary"))
        reader.assert_not_called()
        closer.assert_called_once_with(99)

    def test_source_provenance_matches_checked_in_derivatives(self):
        provenance = json.loads((HERE / "source-provenance.json").read_text())
        for item in provenance["sources"]:
            with self.subTest(path=item["derived_relative_path"]):
                digest = hashlib.sha256((HERE / item["derived_relative_path"]).read_bytes()).hexdigest()
                self.assertEqual(digest, item["derived_sha256"])
        core = (HERE / "qualification_core.py").read_text()
        self.assertNotIn("def main(", core)
        self.assertNotIn("write_text(", core)
        self.assertNotIn("write_bytes(", core)
        schema = json.loads((HERE / "schema" / "outcome-register-schema.json").read_text())
        self.assertEqual(len(schema["properties"]), 40)
        self.assertFalse(schema["additionalProperties"])


if __name__ == "__main__":
    unittest.main()

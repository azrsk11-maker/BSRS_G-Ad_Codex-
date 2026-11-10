"""Actual Python audit -> Node commercial report; temporary synthetic inputs only."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import audit_history as audit
from test_audit_history import NOW, append_later_role, ledger_fixture, source_fixture

REPORT = Path(__file__).resolve().parents[1] / "website-tracking/commercial-system/report.mjs"


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def review_fixture(ledger_raw, source_raw, **changes):
    ledger = json.loads(ledger_raw)
    return {"schema": "bsre-business-history-review-v1", "fixture_only": ledger["fixture_only"],
            "ledger_sha256": hashlib.sha256(ledger_raw).hexdigest(),
            "source_review_sha256": hashlib.sha256(source_raw).hexdigest() if source_raw is not None else None,
            "all_available_history_reviewed": True, "retention_history_incomplete": False,
            "retention_marker_verified": True, "observed_at_utc": "2026-11-08T11:00:00Z",
            "valid_until_utc": "2026-11-08T13:00:00Z", "reviewer_reference": "SYNTHETIC-REVIEWER",
            "evidence_reference": "SYNTHETIC-HISTORY-REVIEW", **changes}


def inputs_fixture():
    ledger = ledger_fixture()
    ledger["fixture_only"] = True
    append_later_role(ledger)  # Repeat across roles must never add a person.
    original = ledger["records"][0]
    for index, day in ((3, "2026-11-03"), (4, "2026-11-04")):
        row = copy.deepcopy(original)
        row.update(outcome_id=str(index) * 8 + "-" + str(index) * 4 + "-4" + str(index) * 3 +
                   "-8" + str(index) * 3 + "-" + str(index) * 12,
                   lead_id=f"SYNTHETIC-LEAD-{index}", canonical_lead_id=f"SYNTHETIC-LEAD-{index}",
                   person_key=f"SYNTHETIC-PERSON-{index}", occurred_at_utc=day + "T08:00:00Z",
                   occurred_at_dubai=day + "T12:00:00+04:00", recorded_at_utc=day + "T08:10:00Z")
        ledger["records"].append(row)
        ledger["intake"].append({"lead_id": row["lead_id"], "role": row["role"],
                                  "accepted_at_utc": day + "T07:00:00Z", "is_test": False})
    raw = encoded(ledger)
    source = source_fixture(ledger, hashlib.sha256(raw).hexdigest())
    source["records"][0].update(source_group="ADS_ATTRIBUTED", evidence_kind="GOOGLE_ADS_NATIVE_RECONCILIATION",
                                  customer_id="573-038-4686", campaign_id="24372566774")
    other = copy.deepcopy(source["records"][0])
    other.update(outcome_id=ledger["records"][2]["outcome_id"], lead_id=ledger["records"][2]["lead_id"],
                 source_group="OTHER_SOURCE", evidence_kind="OTHER_SOURCE_BUSINESS_REVIEW", customer_id=None,
                 campaign_id=None, reviewed_at_utc="2026-11-05T10:00:00Z")
    source["records"].append(other)  # Last person's source genuinely remains unknown.
    return ledger, source


def finance_fixture():
    return {"verified_export": True, "source_ref": "SYNTHETIC-FINANCE",
            "complete": {key: True for key in ("spend", "transactions", "collections", "qualifications", "opportunities")},
            "from": "2026-11-01T00:00:00+04:00", "to": "2026-12-01T00:00:00+04:00",
            "spend": [{"campaign_key": "BSRE-C0001", "date": "2026-11-07", "amount_minor": 10000,
                       "verified": True, "source_ref": "SYNTHETIC-SPEND"}],
            "transactions": [], "collections": [], "opportunities": []}


def policy_fixture():
    return {"approved": True, "approval_ref": "SYNTHETIC-FINANCE-DECISION", "currency": "AED", "timezone": "Asia/Dubai",
            "commission_basis": "gross_cash_including_vat", "refunds_basis": "net_of_vat",
            "cost_basis": "separate_not_already_netted", "media_basis": "actual_ads_cost_excluding_vat",
            "allocation_model": "explicit_transaction_weights_ppm"}


class CommercialIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bsre-synthetic-commercial-")
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def prepare(self, ledger=None, source=None, **review_changes):
        if ledger is None:
            ledger, source = inputs_fixture()
        ledger_raw = encoded(ledger)
        if source is not None:
            source = copy.deepcopy(source)
            source["ledger_sha256"] = hashlib.sha256(ledger_raw).hexdigest()
        source_raw = encoded(source) if source is not None else None
        business_raw = encoded(review_fixture(ledger_raw, source_raw, **review_changes))
        for name, raw in (("ledger", ledger_raw), ("source", source_raw), ("business", business_raw)):
            if raw is not None:
                (self.root / (name + ".json")).write_bytes(raw)
        return ledger_raw, source_raw, business_raw

    def run_node(self, finance=None, policy=None, history_overrides=None, receipt_mode=None):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node is required for the cross-runtime acceptance test")
        payload = {"input": finance or finance_fixture(), "policy": policy if policy is not None else policy_fixture(),
                   "history": {"python": sys.executable, "ledger_path": str(self.root / "ledger.json"),
                               "source_review_path": str(self.root / "source.json") if (self.root / "source.json").exists() else None,
                               "business_review_path": str(self.root / "business.json"), "now_utc": "2026-11-08T12:00:00Z"}}
        payload["history"].update(history_overrides or {})
        payload["receipt_mode"] = receipt_mode
        bridge = REPORT.with_name("history-bridge.mjs")
        script = ("import{readFileSync}from'node:fs';import{commercialReport,commercialReportFromHistory}from" +
                  json.dumps(REPORT.as_uri()) + ";import{readQualificationHistory}from" + json.dumps(bridge.as_uri()) +
                  ";const p=JSON.parse(readFileSync(0,'utf8'));"
                  "try{let r;if(p.receipt_mode){const a=await readQualificationHistory(p.history,{fromDay:'2026-11-01',toDay:'2026-11-30'});"
                  "let now=p.history.now_utc;if(p.receipt_mode==='replay')now='2026-11-08T12:00:01Z';"
                  "if(p.receipt_mode==='submillisecond')now='2026-11-08T12:00:00.000200Z';"
                  "if(p.receipt_mode==='window')p.input.to='2026-11-30T00:00:00+04:00';"
                  "r=commercialReport({...p.input,qualification_audit:a},p.policy,{now_utc:now});}"
                  "else r=await commercialReportFromHistory(p.input,p.policy,p.history);process.stdout.write(JSON.stringify(r));}"
                  "catch(e){process.stdout.write(JSON.stringify({error:e.message}));}")
        result = subprocess.run([node, "--input-type=module", "-e", script], input=encoded(payload),
                                capture_output=True, timeout=45, check=True)
        self.assertEqual(result.stderr, b"")
        return json.loads(result.stdout)

    def test_real_audit_drives_source_counts_and_native_campaign_aggregate(self):
        self.prepare()
        result = self.run_node()
        self.assertEqual(result["totals"]["first_ever_qualified_people"], 3)
        self.assertEqual(result["totals"]["first_ever_qualified_people_by_source"], {"ads": 1, "other": 1, "unknown": 1})
        self.assertEqual(result["qualification_evidence"]["native_campaign_counts"], {"24372566774": 1})
        self.assertEqual(result["totals"]["observed_period_ads_spend_per_first_qualification_aed"], 100)
        self.assertTrue(result["qualification_evidence"]["fixture_only"])
        self.assertFalse(result["qualification_evidence"]["source_truth_independently_verified"])
        self.assertEqual(result["network_calls"], 0)
        mapped = next(row for row in result["campaigns"] if row["campaign_key"] == "BSRE-C0001")
        self.assertIsNone(mapped["observed_period_spend_per_first_qualification_aed"])
        self.assertNotIn("SYNTHETIC-PERSON", json.dumps(result))
        self.assertNotIn("SYNTHETIC-LEAD", json.dumps(result))

    def test_business_counts_do_not_depend_on_advertising_permissions_or_export_state(self):
        ledger, source = inputs_fixture()
        for row in ledger["records"]:
            row.update(ad_user_data="DENIED", ad_personalization="DENIED", click_id_type="NONE",
                       click_id=None, export_state="NOT_READY", privacy_evidence_reference="SYNTHETIC-WITHDRAWN")
        self.prepare(ledger, source)
        self.assertEqual(self.run_node()["totals"]["first_ever_qualified_people"], 3)

    def test_selected_window_uses_whole_history_before_filtering(self):
        self.prepare()
        finance = finance_fixture()
        finance.update({"from": "2026-11-02T00:00:00+04:00", "to": "2026-11-03T00:00:00+04:00"})
        result = self.run_node(finance)
        self.assertEqual(result["totals"]["first_ever_qualified_people"], 0)
        self.assertIsNone(result["totals"]["observed_period_ads_spend_per_first_qualification_aed"])

    def test_unrelated_historical_business_hold_blocks_audited_report(self):
        ledger, source = inputs_fixture()
        ledger["records"][-1]["canonical_lead_id"] = "SYNTHETIC-MISSING"
        self.prepare(ledger, source)
        result = self.run_node()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("WHOLE_HISTORY_BUSINESS_HOLDS_UNRESOLVED", result["blockers"])

    def test_tie_outside_window_blocks_audited_report(self):
        ledger, source = inputs_fixture()
        tied = copy.deepcopy(ledger["records"][0])
        tied["outcome_id"] = "55555555-5555-4555-8555-555555555555"
        ledger["records"].append(tied)
        self.prepare(ledger, source)
        finance = finance_fixture()
        finance.update({"from": "2026-11-03T00:00:00+04:00", "to": "2026-11-05T00:00:00+04:00"})
        self.assertEqual(self.run_node(finance)["status"], "BLOCKED")

    def test_source_freshness_retention_and_completeness_are_fail_closed(self):
        for changes in ({"valid_until_utc": "2026-11-08T12:00:00Z"},
                        {"all_available_history_reviewed": False},
                        {"retention_history_incomplete": True}, {"retention_marker_verified": False}):
            with self.subTest(changes=changes):
                self.prepare(**changes)
                self.assertEqual(self.run_node()["status"], "BLOCKED")

    def test_post_review_truncation_rejects_exact_byte_binding_without_leak(self):
        ledger, _ = inputs_fixture()
        self.prepare(ledger, None)
        ledger = json.loads((self.root / "ledger.json").read_bytes())
        ledger["records"].pop()
        (self.root / "ledger.json").write_bytes(encoded(ledger))
        result = self.run_node()
        self.assertEqual(result, {"error": "QUALIFICATION_AUDIT_INPUT_REJECTED"})
        self.assertNotIn(str(self.root), json.dumps(result))

    def test_finance_policy_remains_required(self):
        self.prepare()
        result = self.run_node(policy={})
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("FINANCE_POLICY_APPROVAL_REQUIRED", result["blockers"])

    def test_incomplete_history_attestation_blocks_even_when_review_says_complete(self):
        ledger, source = inputs_fixture()
        ledger["history_complete"] = False
        self.prepare(ledger, source)
        self.assertIn("COMPLETE_HISTORY_NOT_ATTESTED", self.run_node()["blockers"])

    def test_missing_source_review_preserves_unknowns_instead_of_inventing_ads(self):
        ledger, _ = inputs_fixture()
        self.prepare(ledger, None)
        result = self.run_node()
        self.assertEqual(result["totals"]["first_ever_qualified_people_by_source"], {"ads": 0, "other": 0, "unknown": 3})
        self.assertIsNone(result["totals"]["observed_period_ads_spend_per_first_qualification_aed"])
        self.assertEqual(result["qualification_evidence"]["native_campaign_counts"], {})

    def test_inside_checkout_dotdot_prefix_is_not_a_private_directory(self):
        self.prepare()
        with tempfile.TemporaryDirectory(prefix="..SYNTHETIC-custody-", dir=REPORT.parents[3]) as directory:
            path = Path(directory) / "synthetic-ledger.json"
            path.write_bytes(b"{}")
            result = self.run_node(history_overrides={"ledger_path": str(path)})
        self.assertEqual(result, {"error": "PRIVATE_HISTORY_OUTSIDE_CHECKOUT_REQUIRED"})

    def test_receipt_cannot_be_reused_at_a_new_clock_or_different_window(self):
        self.prepare()
        self.assertEqual(self.run_node(receipt_mode="replay"), {"error": "QUALIFICATION_AUDIT_REFRESH_REQUIRED"})
        self.assertEqual(self.run_node(receipt_mode="window"), {"error": "QUALIFICATION_AUDIT_WINDOW_MISMATCH"})

    def test_synchronous_interpreter_error_never_exposes_supplied_value(self):
        self.prepare()
        result = self.run_node(history_overrides={"python": "SYNTHETIC-PRIVATE-EXECUTABLE\x00CANARY"})
        self.assertEqual(result, {"error": "QUALIFICATION_AUDIT_PROCESS_UNAVAILABLE"})
        self.assertNotIn("CANARY", json.dumps(result))

    def test_submillisecond_receipt_clock_is_exact_and_finer_precision_is_rejected(self):
        self.prepare()
        result = self.run_node(history_overrides={"now_utc": "2026-11-08T12:00:00.000100Z"},
                               receipt_mode="submillisecond")
        self.assertEqual(result, {"error": "QUALIFICATION_AUDIT_REFRESH_REQUIRED"})
        result = self.run_node(history_overrides={"now_utc": "2026-11-08T12:00:00.0001001Z"})
        self.assertEqual(result, {"error": "QUALIFICATION_AUDIT_CLOCK_AND_EXECUTABLE_REQUIRED"})

    def test_audit_provenance_and_aggregates_contain_no_private_records(self):
        raw, source_raw, business_raw = self.prepare()
        result = audit.audited_bytes(raw, NOW, "2026-11-01", "2026-11-30", source_raw, business_raw)
        aggregate = result["commercial_qualification_aggregate"]
        self.assertEqual(aggregate["holds"], [])
        self.assertTrue(aggregate["UPLOAD_PROHIBITED"])
        self.assertEqual(aggregate["provenance"]["ledger_sha256"], hashlib.sha256(raw).hexdigest())
        for name, value in aggregate["provenance"]["validator_components_sha256"].items():
            self.assertEqual(value, hashlib.sha256((audit.HERE / name).read_bytes()).hexdigest())
        for secret in ("SYNTHETIC-PERSON", "SYNTHETIC-LEAD", "SYNTHETIC-REVIEWER", "SYNTHETIC-SOURCE"):
            self.assertNotIn(secret, json.dumps(result))


if __name__ == "__main__":
    unittest.main()

"""Isolated synthetic packet tests. Never upload these fixtures or conversions."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

# Explicit synthetic-only fixture reuse; the production checker imports only the engine.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "content-evidence"))
from test_content_evidence import service_fixture, stamp_review
from content_evidence import canonical_sha256

from release_packet import ACCOUNT, ADS_SAFE_SETTINGS, CHECKS, CURRENT_CAMPAIGNS, GATES, LAUNCH_BUDGET_FILS, ORIGIN, OWNER, POSTFLIGHT_GATES, REPO, TRACKING_AFTER, digest, frozen_legacy_statuses, instant, load_json, validate, verify_file
from release_packet import AUTOMATION_SAFE_STATE, held_account_asset_ids, reviewed_launch_children
from release_packet import page_content_complete

COMMIT = "a" * 40
NOW = instant("2026-11-07T06:00:00Z")


class ReleasePacketTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.packet = self.fixture()

    def write(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
        return {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    def fixture(self, kind="WEBSITE_PUBLICATION"):
        artifact = self.write("artifacts/synthetic.json", {"test_only": True})
        self.source_hashes = {artifact["path"]: artifact["sha256"]}
        resources = [{"page_id": "BSRE-LP0001", "campaign_key": "BSRE-C0001", "campaign_id": "999999999", "wordpress_page_id": 999999, "url": ORIGIN + "/synthetic-only/"}]
        if kind.startswith("ADS_"):
            resources = [{"page_id": f"BSRE-LP{n:04}", "campaign_key": f"BSRE-C{n:04}", "campaign_id": campaign_id, "wordpress_page_id": 999000+n, "url": ORIGIN + f"/synthetic-only-{n}/"} for n, campaign_id in enumerate(sorted(CURRENT_CAMPAIGNS), 1)]
        inventory = {"schema_version": 1, "target_origin": ORIGIN, "pages": [{**resource,
            "gtm_container_id": "GTM-NW8WXKRF", "gtm_version": 2, "ga4_web_stream_id": "16159906474",
            "ga4_measurement_id": "G-W01P9W3NWE", "conversion_action_mapping": {
                "operational_event": "form_accepted", "ga4_event": "generate_lead",
                "ads_action_id": "99999999", "ads_route": "NATIVE_ADS_SECONDARY"},
            "cta_inventory": [{"cta_id": "TEST_ONLY:cta:" + resource["page_id"], "placement": "TEST_ONLY:hero", "destination": resource["url"]}]
            } for resource in resources]}
        inventory_ref = self.write("artifacts/page-tracking-inventory.json", inventory)
        self.source_hashes[inventory_ref["path"]] = inventory_ref["sha256"]
        artifacts = [artifact, inventory_ref]
        content_inventory_ref, content_ledger_ref = None, None
        if kind == "WEBSITE_PUBLICATION":
            content_rows, content_pages, content_records = [], [], []
            for resource in resources:
                name = "artifacts/" + resource["page_id"] + ".html"
                content_path = self.root / name
                content_path.write_text("<p>SYNTHETIC advisory content; not a real offer.</p>", encoding="utf-8")
                content_ref = {"path": name, "sha256": hashlib.sha256(content_path.read_bytes()).hexdigest()}
                artifacts.append(content_ref)
                self.source_hashes[name] = content_ref["sha256"]
                content_rows.append({"page_id": resource["page_id"], "campaign_key": resource["campaign_key"],
                                     "content_file": content_ref})
                ledger, _ = service_fixture()
                page = ledger["pages"][0]
                page.update(page_id=resource["page_id"], campaign_key=resource["campaign_key"],
                            content_sha256=content_ref["sha256"])
                evidence = ledger["records"][0]
                identity = "synthetic-service-" + resource["page_id"]
                evidence.update(evidence_id=identity, page_ids=[resource["page_id"]],
                                source_as_of_utc="2026-11-06T00:00:00Z", valid_until_utc="2026-11-07T08:00:00Z")
                stamp_review(evidence, reviewed_at="2026-11-07T02:00:00Z")
                page.update(evidence_ids=[identity], evidence_sha256_by_id={identity: canonical_sha256(evidence)})
                stamp_review(page, page=True, reviewed_at="2026-11-07T02:00:00Z")
                content_pages.append(page)
                content_records.append(evidence)
            content_inventory_ref = self.write("artifacts/page-content-inventory.json", {
                "schema_version": 1, "target_origin": ORIGIN, "pages": content_rows})
            artifacts.append(content_inventory_ref)
            self.source_hashes[content_inventory_ref["path"]] = content_inventory_ref["sha256"]
            content_ledger_ref = self.write("evidence/content-evidence-ledger.json", {
                "schema": "bsre-content-evidence-v1", "pages": content_pages, "records": content_records})
        page_ids = sorted(r["page_id"] for r in resources)
        rollback = self.write("recovery/synthetic.json", {"test_only": True, "commit": COMMIT, "resource_page_ids": page_ids, "target_origin": ORIGIN, "ads_account": ACCOUNT, "resources": resources, "previous_versions": {p: "synthetic-previous-version" for p in page_ids}})
        proposal = {"release_id": "BSRE-REL-SYNTHETIC-ONLY", "kind": kind,
            "created_at_utc": "2026-11-07T01:00:00Z", "commit": COMMIT,
            "operator": "synthetic-operator", "pusher": "synthetic-pusher",
            "target_origin": ORIGIN, "ads_account": ACCOUNT,
            "resources": resources,
            "artifacts": artifacts, "rollback": {"before_manifest": rollback, "instructions": self.write("recovery/instructions.md", {"test_only": True}),
                "preserve_accepted_records": True, "preserve_outbox": True, "reactivate_old_campaigns": False,
                "reapply_retention_before_reopen": True, "encrypted_owner_only_backup_days": 30},
            "post_release": {"readback_required": True, "pause_on_mismatch": True, "preserve_intake": True},
            "media_limits": None, "change": {"native_page_ids": sorted(r["wordpress_page_id"] for r in resources), "preserve_main_site": True, "reviewed_content_only": True}}
        if kind.startswith("ADS_"):
            proposal["media_limits"] = {"aggregate_average_daily_fils": 200000, "monthly_media_ceiling_fils": 6080000,
                "cash_risk_ceiling_fils": 3040000, "accepts_normal_overdelivery": True, "excluding_vat": True,
                "currency": "AED", "timezone": "Asia/Dubai", "old_campaigns_remain_paused_removed": True,
                "campaign_budgets": [{"campaign_id": r["campaign_id"], "average_daily_fils": LAUNCH_BUDGET_FILS[r["campaign_id"]]} for r in resources]}
            old = [{"id": identity, "status": status} for identity, status in frozen_legacy_statuses().items()]
            before = {"account": ACCOUNT, "observed_at_utc": "2026-11-07T02:00:00Z", "campaigns": old + [{"id": r["campaign_id"], "status": "PAUSED", "average_daily_fils": LAUNCH_BUDGET_FILS[r["campaign_id"]]} for r in resources]}
            for row in before["campaigns"]:
                if row["id"] in CURRENT_CAMPAIGNS:
                    row.update({"final_url": next(r["url"] for r in resources if r["campaign_id"] == row["id"]), "settings": copy.deepcopy(ADS_SAFE_SETTINGS), "max_cpc_fils": 500 if row["id"] == "24378494098" else 2000})
            after = copy.deepcopy(before)
            if kind == "ADS_ACTIVATION":
                for row in after["campaigns"]:
                    if row["id"] in CURRENT_CAMPAIGNS:
                        row["status"] = "ENABLED"
            proposal["change"] = {"before_state": self.write("scope/before.json", before), "after_state": self.write("scope/after.json", after)}
        elif kind == "TRACKING_PUBLICATION":
            proposal["change"] = {"gtm_container_id": "GTM-NW8WXKRF", "ga4_measurement_id": "G-W01P9W3NWE", "version_before": 1, "version_after": 2, "enhanced_matching": False, "personalization": False, "audience_exports": False, "accepted_enquiry_bidding": "SECONDARY_OUTSIDE_CUSTOM_GOALS", "configuration_diff": self.write("scope/tracking.json", {"target_container": "GTM-NW8WXKRF", "measurement_id": "G-W01P9W3NWE", "before_version": 1, "after_version": 2, "before": TRACKING_AFTER, "after": TRACKING_AFTER})}
        proposal_hash = digest(proposal)
        # Explicit migration of synthetic fixture data, never real page acceptance.
        matrix = {"schema_version": 1, "proposal_sha256": proposal_hash, "commit": COMMIT,
            "target_origin": ORIGIN, "production_synthetic_conversions": 0, "pages": []}
        for resource in inventory["pages"]:
            page = copy.deepcopy(resource)
            page.update(reviewer="synthetic-reviewer", method="AUTHENTICATED_STAGING_ACCEPTANCE",
                observed_at_utc="2026-11-07T02:00:00Z", valid_until_utc="2026-11-07T08:00:00Z",
                evidence_ref="TEST_ONLY:" + page["page_id"], results=[
                    {"test_id": f"WT-{n:03}", "status": "PASS", "evidence_ref": f"TEST_ONLY:{page['page_id']}:WT-{n:03}"}
                    for n in range(1, 31) if n not in {1, 3, 4, 9, 27}],
                journey_correlation={kind: {"lead_sha256": hashlib.sha256(("TEST_ONLY:lead:" + page["page_id"]).encode()).hexdigest(),
                    "source_sha256": hashlib.sha256(("TEST_ONLY:source:" + page["page_id"]).encode()).hexdigest()}
                    for kind in ("acceptance", "email", "sheet")})
            for cta in page["cta_inventory"]:
                cta.update(status="PASS", evidence_ref="TEST_ONLY:cta:" + page["page_id"])
            matrix["pages"].append(page)
        matrix_ref = self.write("evidence/page-tracking-matrix.json", matrix)
        evidence = []
        gates = GATES | (POSTFLIGHT_GATES if kind.startswith("ADS_") else set())
        if kind == "ADS_ACTIVATION":
            gates.update({"BRAND_POLICY", "SERVING_CHILDREN", "ASSET_HOLDS", "AUTOMATION"})
        for gate in sorted(gates):
            result = {"test_only": True, "gate_id": gate, "status": "PASS", "proposal_sha256": proposal_hash,
                "commit": COMMIT, "resource_page_ids": page_ids, "method": "AUTHENTICATED_STAGING_ACCEPTANCE",
                "reviewer": "synthetic-reviewer", "observed_at_utc": "2026-11-07T02:00:00Z", "valid_until_utc": "2026-11-07T08:00:00Z", "production_synthetic_conversions": 0}
            if gate == "WT-002":
                result.update(page_tracking_inventory=inventory_ref, page_tracking_matrix=matrix_ref)
            if gate == "KEYWORD_SCOPE":
                result["counts"] = {"unique_reviewed_positive": 14000, "unique_reviewed_negative": 14000, "planned_pairs": 360, "unresolved_protected_conflicts": 0}
                if kind == "ADS_ACTIVATION":
                    result.update(method="AUTHENTICATED_CONFIGURATION_READBACK", effective_exclusions={
                        "account": ACCOUNT, "readback_ref": "TEST_ONLY:effective-negatives",
                        "campaign_ids": sorted(CURRENT_CAMPAIGNS), "account_and_manager_scope_reviewed": True,
                        "legacy_shared_list_attached": False, "unresolved_effective_conflicts": 0,
                    })
            if gate == "QUALIFICATION_HISTORY" and kind == "ADS_ACTIVATION":
                result["qualified_import"] = {
                    "account": ACCOUNT, "conversion_action_id": "7878013428",
                    "route": "SCHEDULED_DATA_MANAGER_GCLID_ONLY", "export_only_access_verified": True,
                    "history_evidence_ref": "TEST_ONLY:history",
                    "source_access_readback_ref": "TEST_ONLY:source-access",
                    "schedule_readback_ref": "TEST_ONLY:schedule",
                }
            if gate == "RETENTION_RECOVERY" and kind == "ADS_ACTIVATION":
                result["retention_recovery"] = {
                    "mailbox": "marketing@blackswanrealestate.ae",
                    "mailbox_mode": "OWNER_CONTROLLED_EXACT_MANIFEST",
                    "mailbox_reconciliation_ref": "TEST_ONLY:mailbox-reconciliation",
                    "restore_rehearsal_ref": "TEST_ONLY:restore-rehearsal",
                    "backup_max_days": 30,
                    "reapply_deletions_before_reopen": True,
                }
            if gate == "SOURCE_TRUTH" and kind == "WEBSITE_PUBLICATION":
                result.update(method="OWNER_REVIEWED_BUSINESS_EVIDENCE",
                    page_content_inventory=content_inventory_ref, content_evidence_ledger=content_ledger_ref,
                    native_page_sources=[
                    {"page_id": resource["page_id"], "service_or_inventory_ref": "TEST_ONLY:inventory",
                     "claims_review_ref": "TEST_ONLY:claims", "asset_rights_review_ref": "TEST_ONLY:rights",
                     "update_owner_ref": "TEST_ONLY:update-owner"} for resource in resources
                ])
            if gate == "STAFF_CAPACITY" and kind == "ADS_ACTIVATION":
                result.update(method="OWNER_REVIEWED_BUSINESS_EVIDENCE", staff_capacity={
                    "completed_rehearsal_ref": "TEST_ONLY:rehearsal", "capacity_evidence_ref": "TEST_ONLY:capacity",
                    "workload_summary": self.write("workload-summary.json", {
                        "staffed_days_supplied": 2, "sample_date_gaps": 0, "total_arrivals": 200,
                        "total_completed": 200, "min_daily_completions_observed": 100,
                        "days_with_backlog_growth": 0, "max_closing_backlog": 0,
                        "sample_representativeness_verified": False,
                    }),
                    "measured_daily_capacity": 100, "reviewed_launch_daily_load": 90,
                    "peak_first_contact_sample_count": 15, "peak_first_contact_max_seconds": 1800,
                    "missing_first_attempt_count": 0, "late_first_attempt_count": 0,
                    "coverage": "DAILY_10:00_19:00_Asia/Dubai",
                    "pause_on_absence_or_unmanageable_backlog": True,
                })
            if gate == "BRAND_POLICY":
                result["method"] = "AUTHENTICATED_CONFIGURATION_READBACK"
                result["brand_policy"] = {"account": ACCOUNT, "campaign_id": "24378494098",
                    "ad_group_id": "204397706114", "ad_id": "828621612889", "policy_status": "APPROVED",
                    "final_url": next(r["url"] for r in resources if r["campaign_id"] == "24378494098")}
            if gate == "SERVING_CHILDREN":
                result["method"] = "AUTHENTICATED_CONFIGURATION_READBACK"
                result["account"] = ACCOUNT
                result["children"] = reviewed_launch_children()
                result["enabled_reviewed_children"] = {
                    "24372566774": {"ad_groups": 2, "ads": 2, "keywords": 34},
                    "24367388382": {"ad_groups": 2, "ads": 2, "keywords": 24},
                    "24378494092": {"ad_groups": 1, "ads": 1, "keywords": 16},
                    "24378494098": {"ad_groups": 1, "ads": 1, "keywords": 8},
                }
            if gate == "ASSET_HOLDS":
                result.update(method="AUTHENTICATED_CONFIGURATION_READBACK", account=ACCOUNT,
                              account_asset_statuses=dict.fromkeys(held_account_asset_ids(), "PAUSED"),
                              unreviewed_effective_asset_count=0)
            if gate == "AUTOMATION":
                result.update(method="AUTHENTICATED_CONFIGURATION_READBACK", account=ACCOUNT,
                              automation=copy.deepcopy(AUTOMATION_SAFE_STATE))
            evidence.append({"gate_id": gate, "file": self.write("evidence/" + gate + ".json", result)})
        packet = {"schema_version": 1, "proposal": proposal, "evidence": evidence,
            "review": {"repository": REPO, "commit": COMMIT, "approver": "synthetic-reviewer", "state": "APPROVED",
                "reviewed_at_utc": "2026-11-07T03:00:00Z", "checks": [{"name": n, "commit": COMMIT, "conclusion": "success"} for n in sorted(CHECKS)]},
            "decisions": [{"issue": n, "owner": OWNER, "state": "APPROVED", "proposal_sha256": proposal_hash,
                "comment_url": f"https://github.com/{REPO}/issues/{n}#issuecomment-999999", "decided_at_utc": "2026-11-07T03:00:00Z"} for n in range(1, 8)]}
        if kind == "ADS_ACTIVATION":
            packet["decisions"].append({**packet["decisions"][0], "issue": 11, "option": "A",
                "comment_url": f"https://github.com/{REPO}/issues/11#issuecomment-999999"})
        packet["approval"] = {"owner": OWNER, "kind": kind, "valid_from_utc": "2026-11-07T05:00:00Z", "expires_at_utc": "2026-11-07T07:00:00Z", "decided_at_utc": "2026-11-07T04:00:00Z", "comment_url": f"https://github.com/{REPO}/issues/1#issuecomment-999999"}
        self.reapprove(packet)
        return packet

    def reapprove(self, packet):
        value = digest({k: v for k, v in packet.items() if k != "approval"})
        packet["approval"]["packet_sha256"] = value
        packet["approval"]["statement"] = f"AUTHORIZE {packet['proposal']['kind']} {packet['proposal']['release_id']} {value}"

    def check(self, packet=None, **kw):
        return validate(packet or self.packet, self.root, now=NOW, checkout_head=kw.get("head", COMMIT), checkout_clean=kw.get("clean", True), source_hashes=kw.get("source_hashes", self.source_hashes))

    def change_evidence(self, gate, key, value):
        ref = next(r for r in self.packet["evidence"] if r["gate_id"] == gate)
        data = load_json(self.root / ref["file"]["path"])
        data[key] = value
        ref["file"] = self.write(ref["file"]["path"], data)
        self.reapprove(self.packet)

    def test_consistent_offline_packet_never_authorizes(self):
        result = self.check()
        self.assertTrue(result["packet_consistent"], result)
        self.assertFalse(result["execution_allowed"])
        self.assertFalse(result["release_authorized"])
        self.assertEqual(result["next_gate"], "AUTHENTICATED_OWNER_AND_PLATFORM_VERIFICATION")
        self.assertEqual(result["post_publication_readback_required"], ["WT-031", "WT-032"])

    def test_empty_or_malformed_packet_fails_closed(self):
        for packet in (None, [], {}, {"schema_version": 1}, {**self.packet, "extra": True}):
            with self.subTest(packet_type=type(packet).__name__):
                self.assertFalse(validate(packet, self.root)["packet_consistent"])

    def test_dirty_or_changed_head_invalidates_packet(self):
        self.assertFalse(self.check(clean=False)["packet_consistent"])
        self.assertFalse(self.check(head="b" * 40)["packet_consistent"])

    def test_artifact_bytes_must_match(self):
        (self.root / "artifacts/synthetic.json").write_text("changed")
        self.assertIn("MALFORMED_OR_UNREADABLE_PACKET:ValueError:ARTIFACT_HASH_MISMATCH", self.check()["errors"])

    def test_paths_cannot_read_other_locations(self):
        for name in ("../outside.json", "/outside.json", "C:/secret.json", "artifacts/../secret.json", ".git/config", "artifacts\\test.json", "artifacts//synthetic.json"):
            with self.subTest(name=name), self.assertRaises((ValueError, FileNotFoundError)):
                verify_file(self.root, {"path": name, "sha256": "a" * 64})

    def test_symlink_escape_is_rejected(self):
        link = self.root / "alias.json"
        try:
            link.symlink_to(self.root / "artifacts/synthetic.json")
        except OSError:
            self.skipTest("Host does not allow symlink creation; CI exercises this case")
        with self.assertRaisesRegex(ValueError, "SYMLINK"):
            verify_file(self.root, {"path": "alias.json", "sha256": self.packet["proposal"]["artifacts"][0]["sha256"]})

    def test_unreviewable_or_oversized_files_rejected(self):
        ref = self.write("secret.key", "synthetic")
        with self.assertRaisesRegex(ValueError, "FILE_TYPE"):
            verify_file(self.root, ref)
        (self.root / "large.json").write_bytes(b" " * 2000001)
        with self.assertRaisesRegex(ValueError, "TOO_LARGE"):
            load_json(self.root / "large.json")

    def test_duplicate_json_keys_and_nan_rejected(self):
        for value in ('{"a":1,"a":2}', '{"a":NaN}'):
            path = self.root / "invalid.json"
            path.write_text(value)
            with self.assertRaises(ValueError):
                load_json(path)

    def test_approval_cannot_transfer_to_another_action(self):
        self.packet["approval"]["kind"] = "TRACKING_PUBLICATION"
        self.assertIn("SEPARATE_EXACT_PACKET_APPROVAL_REQUIRED", self.check()["errors"])

    def test_proposal_change_invalidates_evidence_and_approval(self):
        self.packet["proposal"]["resources"][0]["url"] = ORIGIN + "/changed/"
        result = self.check()
        self.assertTrue(any(e.startswith("EVIDENCE_SCOPE_MISMATCH") for e in result["errors"]))
        self.assertIn("SEPARATE_EXACT_PACKET_APPROVAL_REQUIRED", result["errors"])

    def test_resource_bijection_and_planned_id_range(self):
        for key, value in (("page_id", "BSRE-LP0361"), ("campaign_key", "BSRE-C0002"), ("url", ORIGIN + "/?email=private"), ("wordpress_page_id", True)):
            packet = copy.deepcopy(self.packet)
            packet["proposal"]["resources"][0][key] = value
            self.assertFalse(self.check(packet)["packet_consistent"])
        self.packet["proposal"]["resources"].append(copy.deepcopy(self.packet["proposal"]["resources"][0]))
        self.assertIn("DEDICATED_CAMPAIGN_PAGE_BIJECTION", self.check()["errors"])

    def test_missing_or_duplicate_gate_cannot_be_waived(self):
        self.packet["evidence"].pop()
        self.assertIn("ALL_REQUIRED_GATES_EXACTLY_ONCE", self.check()["errors"])
        self.packet["evidence"].append(copy.deepcopy(self.packet["evidence"][0]))
        self.assertIn("ALL_REQUIRED_GATES_EXACTLY_ONCE", self.check()["errors"])

    def test_isolated_tests_do_not_close_runtime_gates(self):
        for method in ("LOCAL_UNIT_TEST", "PUBLIC_HTTP_GET", "CI_SUCCESS"):
            self.change_evidence("WT-014", "method", method)
            self.assertIn("COMPLETE_ACCEPTANCE_METHOD_REQUIRED:WT-014", self.check()["errors"])

    def test_partial_evidence_or_other_resource_fails(self):
        self.change_evidence("WT-014", "status", "PARTIAL")
        self.assertIn("GATE_NOT_PASS:WT-014", self.check()["errors"])
        self.change_evidence("WT-014", "resource_page_ids", ["BSRE-LP0002"])
        self.assertIn("EVIDENCE_SCOPE_MISMATCH:WT-014", self.check()["errors"])

    def test_stale_or_future_evidence_fails(self):
        for timestamp in ("2026-11-06T02:00:00Z", "2026-11-08T02:00:00Z"):
            self.change_evidence("WT-014", "observed_at_utc", timestamp)
            self.assertIn("EVIDENCE_TIME_OUTSIDE_PROPOSAL", self.check()["errors"])

    def test_master_keyword_deficit_still_blocks(self):
        self.change_evidence("KEYWORD_SCOPE", "counts", {"unique_reviewed_positive": 0, "unique_reviewed_negative": 0, "planned_pairs": 360, "unresolved_protected_conflicts": 0})
        self.assertIn("MASTER_COUNTS_OR_REVIEWED_POLICY_CHANGE_REQUIRED", self.check()["errors"])

    def test_synthetic_conversions_and_boolean_count_rejected(self):
        for count in (1, False, "0"):
            self.change_evidence("WT-014", "production_synthetic_conversions", count)
            self.assertIn("NO_SYNTHETIC_GOOGLE_CONVERSIONS", self.check()["errors"])

    def test_review_by_last_pusher_and_wrong_checks_rejected(self):
        self.packet["review"]["approver"] = "SYNTHETIC-PUSHER"
        self.packet["review"]["checks"][0]["commit"] = "b" * 40
        errors = self.check()["errors"]
        self.assertIn("INDEPENDENT_EXACT_HEAD_REVIEW_REQUIRED", errors)
        self.assertIn("EXACT_HEAD_REQUIRED_CHECKS", errors)

    def test_release_requires_isolated_wordpress_on_the_reviewed_head(self):
        checks = self.packet["review"]["checks"]
        checks[:] = [row for row in checks if row["name"] != "isolated-native-wordpress"]
        self.assertIn("EXACT_HEAD_REQUIRED_CHECKS", self.check()["errors"])

    def test_owner_decisions_must_exist_and_match(self):
        self.packet["decisions"].pop()
        self.packet["decisions"][0]["owner"] = "someone-else"
        self.packet["decisions"][1]["comment_url"] = "https://example.com/"
        errors = self.check()["errors"]
        for code in ("OWNER_DECISIONS_UNRESOLVED", "OWNER_DECISION_SCOPE_REQUIRED", "EXACT_OWNER_COMMENT_REFERENCE"):
            self.assertIn(code, errors)

    def test_window_expiry_and_approval_before_evidence(self):
        self.packet["approval"]["expires_at_utc"] = "2026-11-07T06:00:00Z"
        self.assertIn("APPROVAL_WINDOW_INVALID", self.check()["errors"])
        self.packet["approval"]["decided_at_utc"] = "2026-11-07T01:00:00Z"
        self.assertIn("APPROVAL_PRECEDES_EVIDENCE_OR_REVIEW", self.check()["errors"])

    def test_recovery_cannot_overwrite_intake_or_resume_old_ads(self):
        self.packet["proposal"]["rollback"]["preserve_outbox"] = False
        self.packet["proposal"]["rollback"]["reactivate_old_campaigns"] = True
        self.assertIn("SCOPED_RECOVERY_INVARIANTS", self.check()["errors"])

    def test_ads_require_post_publication_evidence(self):
        packet = self.fixture("ADS_ACTIVATION")
        self.assertTrue(self.check(packet)["packet_consistent"])
        packet["evidence"] = [e for e in packet["evidence"] if e["gate_id"] not in POSTFLIGHT_GATES]
        self.assertIn("ALL_REQUIRED_GATES_EXACTLY_ONCE", self.check(packet)["errors"])

    def test_budget_mutation_invalidates_approval(self):
        packet = self.fixture("ADS_ACTIVATION")
        packet["proposal"]["media_limits"]["aggregate_average_daily_fils"] += 1
        errors = self.check(packet)["errors"]
        self.assertIn("AGGREGATE_BUDGET_MISMATCH", errors)
        self.assertIn("SEPARATE_EXACT_PACKET_APPROVAL_REQUIRED", errors)

    def test_activation_requires_restricted_qualified_import_readback(self):
        for changes in ({"export_only_access_verified": False}, {"schedule_readback_ref": ""},
                        {"source_access_readback_ref": ""}, {"history_evidence_ref": ""},
                        {"account": "615-904-3329"}, {"conversion_action_id": "7873290954"},
                        {"route": "MANUAL_CSV"}):
            with self.subTest(changes=changes):
                packet = self.fixture("ADS_ACTIVATION")
                evidence = next(e for e in packet["evidence"] if e["gate_id"] == "QUALIFICATION_HISTORY")
                path = evidence["file"]["path"]
                result = json.loads((self.root / path).read_text(encoding="utf-8"))
                result["qualified_import"].update(changes)
                evidence["file"] = self.write(path, result)
                self.assertIn("RESTRICTED_QUALIFIED_IMPORT_READBACK_REQUIRED", self.check(packet)["errors"])

    def test_activation_requires_reviewed_retention_and_recovery_scope(self):
        for changes in ({"mailbox": "other@example.test"}, {"mailbox_mode": "AUTOMATED"},
                        {"mailbox_reconciliation_ref": ""}, {"restore_rehearsal_ref": ""},
                        {"backup_max_days": 31}, {"reapply_deletions_before_reopen": False}):
            with self.subTest(changes=changes):
                packet = self.fixture("ADS_ACTIVATION")
                evidence = next(e for e in packet["evidence"] if e["gate_id"] == "RETENTION_RECOVERY")
                path = evidence["file"]["path"]
                result = json.loads((self.root / path).read_text(encoding="utf-8"))
                result["retention_recovery"].update(changes)
                evidence["file"] = self.write(path, result)
                self.assertIn("REVIEWED_RETENTION_AND_RECOVERY_SCOPE_REQUIRED", self.check(packet)["errors"])

    def test_activation_requires_owner_language_option_a(self):
        packet = self.fixture("ADS_ACTIVATION")
        self.assertNotIn("ENGLISH_FIRST_AUTOMATIC_MATCHING_APPROVAL_REQUIRED", self.check(packet)["errors"])
        packet["decisions"][-1]["option"] = "B"
        self.reapprove(packet)
        self.assertIn("ENGLISH_FIRST_AUTOMATIC_MATCHING_APPROVAL_REQUIRED", self.check(packet)["errors"])
        packet["decisions"].pop()
        self.reapprove(packet)
        self.assertIn("OWNER_DECISIONS_UNRESOLVED", self.check(packet)["errors"])

    def test_activation_requires_exact_brand_ad_policy_readback(self):
        packet = self.fixture("ADS_ACTIVATION")
        self.assertTrue(self.check(packet)["packet_consistent"])
        evidence = next(e for e in packet["evidence"] if e["gate_id"] == "BRAND_POLICY")
        path = evidence["file"]["path"]
        result = json.loads((self.root / path).read_text(encoding="utf-8"))
        result["brand_policy"]["policy_status"] = "PENDING"
        evidence["file"] = self.write(path, result)
        self.assertIn("EXACT_BRAND_AD_POLICY_APPROVAL_REQUIRED", self.check(packet)["errors"])
        packet["evidence"].remove(evidence)
        self.assertIn("ALL_REQUIRED_GATES_EXACTLY_ONCE", self.check(packet)["errors"])

    def test_activation_rejects_paused_launch_keywords(self):
        packet = self.fixture("ADS_ACTIVATION")
        evidence = next(e for e in packet["evidence"] if e["gate_id"] == "SERVING_CHILDREN")
        path = evidence["file"]["path"]
        result = json.loads((self.root / path).read_text(encoding="utf-8"))
        result["enabled_reviewed_children"]["24378494098"]["keywords"] = 0
        evidence["file"] = self.write(path, result)
        self.assertIn("ALL_REVIEWED_LAUNCH_CHILDREN_MUST_ALREADY_BE_ENABLED", self.check(packet)["errors"])

    def test_activation_requires_rehearsal_and_capacity_above_reviewed_load(self):
        for changes in ({"completed_rehearsal_ref": ""}, {"measured_daily_capacity": 89}):
            with self.subTest(changes=changes):
                packet = self.fixture("ADS_ACTIVATION")
                evidence = next(e for e in packet["evidence"] if e["gate_id"] == "STAFF_CAPACITY")
                path = evidence["file"]["path"]
                result = json.loads((self.root / path).read_text(encoding="utf-8"))
                result["staff_capacity"].update(changes)
                evidence["file"] = self.write(path, result)
                self.assertIn("REHEARSED_STAFF_CAPACITY_MUST_COVER_REVIEWED_LAUNCH_LOAD", self.check(packet)["errors"])

    def test_activation_binds_capacity_to_workload_summary(self):
        packet = self.fixture("ADS_ACTIVATION")
        evidence = next(row for row in packet["evidence"] if row["gate_id"] == "STAFF_CAPACITY")
        path = evidence["file"]["path"]
        result = json.loads((self.root / path).read_text(encoding="utf-8"))
        result["staff_capacity"]["measured_daily_capacity"] = 101
        evidence["file"] = self.write(path, result)
        self.assertIn("REVIEWED_CAPACITY_MUST_MATCH_OBSERVED_WORKLOAD", self.check(packet)["errors"])
        result["staff_capacity"]["measured_daily_capacity"] = 100
        evidence["file"] = self.write(path, result)
        summary = self.root / result["staff_capacity"]["workload_summary"]["path"]
        summary.write_bytes(summary.read_bytes() + b" ")
        self.assertIn("MALFORMED_OR_UNREADABLE_PACKET:ValueError:ARTIFACT_HASH_MISMATCH", self.check(packet)["errors"])

    def test_activation_requires_current_effective_negative_scope(self):
        for changes in ({"readback_ref": ""}, {"legacy_shared_list_attached": True},
                        {"account_and_manager_scope_reviewed": False}, {"campaign_ids": []},
                        {"unresolved_effective_conflicts": False}):
            with self.subTest(changes=changes):
                packet = self.fixture("ADS_ACTIVATION")
                evidence = next(e for e in packet["evidence"] if e["gate_id"] == "KEYWORD_SCOPE")
                path = evidence["file"]["path"]
                result = json.loads((self.root / path).read_text(encoding="utf-8"))
                result["effective_exclusions"].update(changes)
                evidence["file"] = self.write(path, result)
                self.assertIn("EFFECTIVE_NEGATIVE_SCOPE_READBACK_REQUIRED", self.check(packet)["errors"])

    def test_activation_requires_observed_peak_first_contact_within_target(self):
        for changes in ({"peak_first_contact_sample_count": 0}, {"peak_first_contact_max_seconds": 1801},
                        {"peak_first_contact_max_seconds": None}, {"peak_first_contact_max_seconds": False},
                        {"missing_first_attempt_count": 1}, {"late_first_attempt_count": 1}):
            with self.subTest(changes=changes):
                packet = self.fixture("ADS_ACTIVATION")
                evidence = next(e for e in packet["evidence"] if e["gate_id"] == "STAFF_CAPACITY")
                path = evidence["file"]["path"]
                result = json.loads((self.root / path).read_text(encoding="utf-8"))
                result["staff_capacity"].update(changes)
                evidence["file"] = self.write(path, result)
                self.assertIn("PEAK_FIRST_CONTACT_EVIDENCE_WITHIN_30_MINUTES_REQUIRED", self.check(packet)["errors"])

    def test_activation_rejects_reenabled_held_account_lead_form(self):
        packet = self.fixture("ADS_ACTIVATION")
        evidence = next(e for e in packet["evidence"] if e["gate_id"] == "ASSET_HOLDS")
        path = evidence["file"]["path"]
        result = json.loads((self.root / path).read_text(encoding="utf-8"))
        result["account_asset_statuses"]["424492800514"] = "ENABLED"
        evidence["file"] = self.write(path, result)
        self.assertIn("KNOWN_ASSET_HOLDS_AND_EFFECTIVE_ASSOCIATIONS_REQUIRED", self.check(packet)["errors"])

    def test_activation_rejects_missing_manager_or_active_account_automation(self):
        for missing_manager in (True, False):
            with self.subTest(missing_manager=missing_manager):
                packet = self.fixture("ADS_ACTIVATION")
                evidence = next(e for e in packet["evidence"] if e["gate_id"] == "AUTOMATION")
                path = evidence["file"]["path"]
                result = json.loads((self.root / path).read_text(encoding="utf-8"))
                if missing_manager:
                    result["automation"].pop("manager_automation_with_launch_control")
                else:
                    result["automation"]["account_rules_with_launch_control"] = 1
                evidence["file"] = self.write(path, result)
                self.assertIn("ACCOUNT_MANAGER_AND_EXTERNAL_AUTOMATION_REVIEW_REQUIRED", self.check(packet)["errors"])

    def test_activation_rejects_same_count_keyword_substitution(self):
        packet = self.fixture("ADS_ACTIVATION")
        evidence = next(e for e in packet["evidence"] if e["gate_id"] == "SERVING_CHILDREN")
        path = evidence["file"]["path"]
        result = json.loads((self.root / path).read_text(encoding="utf-8"))
        result["children"]["keywords"][0]["id"] = "999999999"
        evidence["file"] = self.write(path, result)
        errors = self.check(packet)["errors"]
        self.assertIn("EXACT_REVIEWED_LAUNCH_CHILD_IDENTITIES_AND_STATUSES_REQUIRED", errors)
        self.assertNotIn("ALL_REVIEWED_LAUNCH_CHILDREN_MUST_ALREADY_BE_ENABLED", errors)

    def test_website_cannot_carry_spend_approval(self):
        self.packet["proposal"]["media_limits"] = {"aggregate_average_daily_fils": 200000}
        self.assertIn("WEBSITE_OR_TRACKING_CANNOT_AUTHORIZE_SPEND", self.check()["errors"])

    def test_activation_rejects_budget_redistribution_at_same_total(self):
        packet = self.fixture("ADS_ACTIVATION")
        proposal = packet["proposal"]
        budgets = proposal["media_limits"]["campaign_budgets"]
        budgets[0]["average_daily_fils"] += 100
        budgets[1]["average_daily_fils"] -= 100
        after = json.loads((self.root / "scope/after.json").read_text(encoding="utf-8"))
        adjusted = {b["campaign_id"]: b["average_daily_fils"] for b in budgets}
        for row in after["campaigns"]:
            if row["id"] in adjusted:
                row["average_daily_fils"] = adjusted[row["id"]]
        proposal["change"]["after_state"] = self.write("scope/after.json", after)
        errors = self.check(packet)["errors"]
        self.assertIn("APPROVED_LAUNCH_BUDGET_SPLIT_REQUIRED", errors)
        self.assertNotIn("AGGREGATE_BUDGET_MISMATCH", errors)
        self.assertNotIn("BUDGET_DIFF_MISMATCH", errors)

    def test_configuration_rejects_noninteger_daily_budget_in_after_state(self):
        packet = self.fixture("ADS_CONFIGURATION")
        ref = packet["proposal"]["change"]["after_state"]
        after = load_json(self.root / ref["path"])
        row = after["campaigns"][-1]
        row["average_daily_fils"] = float(row["average_daily_fils"])
        packet["proposal"]["change"]["after_state"] = self.write(ref["path"], after)
        self.assertIn("BUDGET_DIFF_MISMATCH", self.check(packet)["errors"])

    def test_legacy_state_cannot_change_json_number_type(self):
        packet = self.fixture("ADS_CONFIGURATION")
        change = packet["proposal"]["change"]
        for field, value in (("before_state", 100), ("after_state", 100.0)):
            ref = change[field]
            state = load_json(self.root / ref["path"])
            state["campaigns"][0]["average_daily_fils"] = value
            change[field] = self.write(ref["path"], state)
        self.assertIn("OLD_CAMPAIGN_BASELINE_MUST_STAY_FROZEN", self.check(packet)["errors"])

    def test_activation_cannot_also_configure_launch_budget(self):
        packet = self.fixture("ADS_ACTIVATION")
        before = json.loads((self.root / "scope/before.json").read_text(encoding="utf-8"))
        before["campaigns"][-1]["average_daily_fils"] -= 100
        packet["proposal"]["change"]["before_state"] = self.write("scope/before.json", before)
        self.assertIn("ACTIVATION_REQUIRES_PRECONFIGURED_LAUNCH_BUDGETS", self.check(packet)["errors"])

    def test_activation_cannot_also_repair_destination_or_targeting(self):
        for field in ("final_url", "settings", "max_cpc_fils"):
            with self.subTest(field=field):
                packet = self.fixture("ADS_ACTIVATION")
                before = json.loads((self.root / "scope/before.json").read_text(encoding="utf-8"))
                before["campaigns"][-1].pop(field)
                packet["proposal"]["change"]["before_state"] = self.write("scope/before.json", before)
                self.assertIn("ACTIVATION_MAY_CHANGE_ONLY_CAMPAIGN_STATUS", self.check(packet)["errors"])

    def test_activation_rejects_unapproved_strategy_even_if_unchanged(self):
        packet = self.fixture("ADS_ACTIVATION")
        change = packet["proposal"]["change"]
        for phase in ("before", "after"):
            path = f"scope/{phase}.json"
            state = json.loads((self.root / path).read_text(encoding="utf-8"))
            state["campaigns"][-1]["settings"]["bid_strategy"] = "MAXIMIZE_CONVERSIONS"
            change[f"{phase}_state"] = self.write(path, state)
        errors = self.check(packet)["errors"]
        self.assertIn("ADS_AFTER_STATE_CONTRADICTS_SCOPE", errors)
        self.assertNotIn("ACTIVATION_MAY_CHANGE_ONLY_CAMPAIGN_STATUS", errors)

    def test_matching_before_and_after_cannot_substitute_for_frozen_legacy_campaign(self):
        for replacement in ({"id": "999999999"}, {"status": "PAUSED"}):
            with self.subTest(replacement=replacement):
                packet = self.fixture("ADS_ACTIVATION")
                change = packet["proposal"]["change"]
                for phase in ("before", "after"):
                    name = f"scope/{phase}.json"
                    state = json.loads((self.root / name).read_text(encoding="utf-8"))
                    removed = next(row for row in state["campaigns"] if row["status"] == "REMOVED")
                    removed.update(replacement)
                    change[f"{phase}_state"] = self.write(name, state)
                self.assertIn("KNOWN_LEGACY_CAMPAIGN_IDS_AND_STATUSES_REQUIRED", self.check(packet)["errors"])

    def test_ignored_source_cannot_claim_reviewed_commit(self):
        self.assertIn("ARTIFACT_NOT_IN_REVIEWED_COMMIT", self.check(source_hashes={})["errors"])

    def test_changed_bytes_rejected_before_json_parse(self):
        ref = self.write("late.json", {"test_only": True})
        (self.root / "late.json").write_text('{"different":true}')
        with self.assertRaisesRegex(ValueError, "HASH_MISMATCH"):
            load_json(self.root / "late.json", ref["sha256"])

    def test_evidence_expiry_limits_approval_window(self):
        self.change_evidence("SOURCE_TRUTH", "valid_until_utc", "2026-11-07T06:30:00Z")
        self.assertIn("APPROVAL_OUTLIVES_EVIDENCE", self.check()["errors"])
        self.change_evidence("SOURCE_TRUTH", "valid_until_utc", "2026-11-07T05:30:00Z")
        self.assertIn("EVIDENCE_EXPIRED", self.check()["errors"])

    def test_rollback_manifest_requires_exact_versions(self):
        self.packet["proposal"]["rollback"]["before_manifest"] = self.write("recovery/empty.json", {})
        self.assertIn("EXACT_SCOPED_ROLLBACK_VERSIONS_REQUIRED", self.check()["errors"])

    def test_old_campaign_reactivation_and_mutation_are_blocked(self):
        packet = self.fixture("ADS_ACTIVATION")
        ref = packet["proposal"]["change"]["after_state"]
        data = load_json(self.root / ref["path"])
        data["campaigns"][0]["status"] = "ENABLED"
        packet["proposal"]["change"]["after_state"] = self.write(ref["path"], data)
        self.assertIn("OLD_CAMPAIGN_BASELINE_MUST_STAY_FROZEN", self.check(packet)["errors"])

    def test_three_campaign_exception_is_not_accepted(self):
        packet = self.fixture("ADS_ACTIVATION")
        packet["proposal"]["resources"].pop()
        self.assertIn("FULL_FOUR_CAMPAIGN_LAUNCH_REQUIRED", self.check(packet)["errors"])

    def test_tracking_requires_verified_container_and_safe_modes(self):
        packet = self.fixture("TRACKING_PUBLICATION")
        self.assertTrue(self.check(packet)["packet_consistent"])
        packet["proposal"]["change"]["gtm_container_id"] = "GTM-OTHER"
        packet["proposal"]["change"]["enhanced_matching"] = True
        errors = self.check(packet)["errors"]
        self.assertIn("VERIFIED_TRACKING_DESTINATIONS_REQUIRED", errors)
        self.assertIn("LAUNCH_MEASUREMENT_BOUNDARIES", errors)

    def test_configuration_cannot_activate_advertising(self):
        packet = self.fixture("ADS_CONFIGURATION")
        self.assertTrue(self.check(packet)["packet_consistent"])
        ref = packet["proposal"]["change"]["after_state"]
        data = load_json(self.root / ref["path"])
        data["campaigns"][-1]["status"] = "ENABLED"
        packet["proposal"]["change"]["after_state"] = self.write(ref["path"], data)
        self.assertIn("ADS_ACTION_STATUS_MISMATCH", self.check(packet)["errors"])

    def test_tracking_diff_cannot_contradict_safe_summary(self):
        packet = self.fixture("TRACKING_PUBLICATION")
        ref = packet["proposal"]["change"]["configuration_diff"]
        data = load_json(self.root / ref["path"])
        data["after"]["enhanced_matching"] = True
        packet["proposal"]["change"]["configuration_diff"] = self.write(ref["path"], data)
        self.assertIn("NORMALIZED_TRACKING_DIFF_CONTRADICTS_SAFE_SCOPE", self.check(packet)["errors"])

    def test_ads_diff_cannot_change_destination_or_enable_expansion(self):
        packet = self.fixture("ADS_ACTIVATION")
        ref = packet["proposal"]["change"]["after_state"]
        data = load_json(self.root / ref["path"])
        data["campaigns"][-1]["final_url"] = "https://wrong.example/"
        data["campaigns"][-1]["settings"]["ai_max"] = True
        packet["proposal"]["change"]["after_state"] = self.write(ref["path"], data)
        self.assertIn("ADS_AFTER_STATE_CONTRADICTS_SCOPE", self.check(packet)["errors"])

    def test_website_publication_requires_source_reviews_per_native_page(self):
        sources = [{"page_id": "BSRE-LP0001", "service_or_inventory_ref": "TEST_ONLY:inventory",
                    "claims_review_ref": "TEST_ONLY:claims", "asset_rights_review_ref": "TEST_ONLY:rights",
                    "update_owner_ref": "TEST_ONLY:update-owner"}]
        for invalid in ([], [{**sources[0], "page_id": "BSRE-LP0360"}],
                        [{**sources[0], "asset_rights_review_ref": ""}]):
            with self.subTest(invalid=invalid):
                self.packet = self.fixture("WEBSITE_PUBLICATION")
                self.change_evidence("SOURCE_TRUTH", "native_page_sources", invalid)
                self.assertIn("EXACT_NATIVE_PAGE_SOURCE_REVIEW_REQUIRED", self.check()["errors"])

    def content_inputs(self):
        reference = next(row for row in self.packet["evidence"] if row["gate_id"] == "SOURCE_TRUTH")
        receipt = load_json(self.root / reference["file"]["path"])
        ledger = load_json(self.root / receipt["content_evidence_ledger"]["path"])
        inventory = load_json(self.root / receipt["page_content_inventory"]["path"])
        return ledger, inventory, receipt

    def content_check(self, ledger, inventory, receipt, *, sources=None):
        return page_content_complete(ledger, inventory, self.packet["proposal"], receipt, self.root,
                                     self.source_hashes if sources is None else sources, NOW)

    def test_opaque_content_refs_and_forged_pass_summary_cannot_replace_ledger(self):
        for replacement in (None, {"all_pages_eligible": True}):
            with self.subTest(replacement=replacement):
                self.packet = self.fixture()
                if replacement is None:
                    reference = next(row for row in self.packet["evidence"] if row["gate_id"] == "SOURCE_TRUTH")
                    receipt = load_json(self.root / reference["file"]["path"])
                    del receipt["content_evidence_ledger"]
                    reference["file"] = self.write(reference["file"]["path"], receipt)
                    self.reapprove(self.packet)
                else:
                    self.change_evidence("SOURCE_TRUTH", "content_evidence_ledger",
                        self.write("evidence/forged-content-summary.json", replacement))
                self.assertIn("DATED_CONTENT_AND_RIGHTS_EVIDENCE_REQUIRED", self.check()["errors"])

    def test_actual_page_bytes_and_committed_content_binding_are_required(self):
        ledger, inventory, receipt = self.content_inputs()
        self.assertTrue(self.content_check(ledger, inventory, receipt))
        reference = inventory["pages"][0]["content_file"]
        sources = dict(self.source_hashes)
        del sources[reference["path"]]
        self.assertFalse(self.content_check(ledger, inventory, receipt, sources=sources))
        (self.root / reference["path"]).write_text("<p>Changed SYNTHETIC copy.</p>", encoding="utf-8")
        self.assertFalse(self.content_check(ledger, inventory, receipt))
        reference["sha256"] = hashlib.sha256((self.root / reference["path"]).read_bytes()).hexdigest()
        self.source_hashes[reference["path"]] = reference["sha256"]
        # Even a newly committed text hash cannot reuse the old page/evidence review.
        self.assertFalse(self.content_check(ledger, inventory, receipt))

    def test_content_inventory_requires_exact_pages_and_reviewable_text_files(self):
        ledger, inventory, receipt = self.content_inputs()
        for rows in ([], inventory["pages"] * 2,
                     [{**inventory["pages"][0], "page_id": "BSRE-LP0360"}],
                     [{**inventory["pages"][0], "campaign_key": "BSRE-C0360"}],
                     [{**inventory["pages"][0], "content_file": self.packet["proposal"]["artifacts"][0]}]):
            with self.subTest(rows=len(rows)):
                self.assertFalse(self.content_check(ledger, {**inventory, "pages": rows}, receipt))

    def test_content_inventory_itself_must_be_in_reviewed_commit(self):
        self.source_hashes.pop("artifacts/page-content-inventory.json")
        self.assertIn("PAGE_CONTENT_INVENTORY_NOT_IN_REVIEWED_COMMIT", self.check()["errors"])

    def test_source_expiry_and_receipt_lifetime_cannot_be_hidden_by_fresh_gate_receipt(self):
        for expiry in ("2026-11-07T06:00:00Z", "2026-11-07T07:00:00Z"):
            with self.subTest(expiry=expiry):
                ledger, inventory, receipt = self.content_inputs()
                record = ledger["records"][0]
                record["valid_until_utc"] = expiry
                stamp_review(record, reviewed_at="2026-11-07T02:00:00Z")
                ledger["pages"][0]["evidence_sha256_by_id"][record["evidence_id"]] = canonical_sha256(record)
                stamp_review(ledger["pages"][0], page=True, reviewed_at="2026-11-07T02:00:00Z")
                self.assertFalse(self.content_check(ledger, inventory, receipt))

    def test_content_reviews_recorded_after_receipt_cannot_be_backed_by_that_receipt(self):
        ledger, inventory, receipt = self.content_inputs()
        record = ledger["records"][0]
        stamp_review(record, reviewed_at="2026-11-07T02:00:01Z")
        ledger["pages"][0]["evidence_sha256_by_id"][record["evidence_id"]] = canonical_sha256(record)
        stamp_review(ledger["pages"][0], page=True, reviewed_at="2026-11-07T02:00:01Z")
        self.assertFalse(self.content_check(ledger, inventory, receipt))

    def test_content_ledger_accepts_equivalent_explicit_utc_alias(self):
        ledger, inventory, receipt = self.content_inputs()
        record = ledger["records"][0]
        for key in ("source_as_of_utc", "valid_until_utc"):
            record[key] = record[key].replace("Z", "+00:00")
        stamp_review(record, reviewed_at="2026-11-07T02:00:00+00:00")
        ledger["pages"][0]["evidence_sha256_by_id"][record["evidence_id"]] = canonical_sha256(record)
        stamp_review(ledger["pages"][0], page=True, reviewed_at="2026-11-07T02:00:00+00:00")
        self.assertTrue(self.content_check(ledger, inventory, receipt))

    def test_rollback_native_id_and_account_must_match(self):
        ref = self.packet["proposal"]["rollback"]["before_manifest"]
        data = load_json(self.root / ref["path"])
        data["resources"][0]["wordpress_page_id"] = 123
        data["ads_account"] = "123-456-7890"
        self.packet["proposal"]["rollback"]["before_manifest"] = self.write(ref["path"], data)
        self.assertIn("EXACT_SCOPED_ROLLBACK_VERSIONS_REQUIRED", self.check()["errors"])

    def change_matrix(self, mutate):
        reference = next(row for row in self.packet["evidence"] if row["gate_id"] == "WT-002")
        receipt = load_json(self.root / reference["file"]["path"])
        matrix_ref = receipt["page_tracking_matrix"]
        matrix = load_json(self.root / matrix_ref["path"])
        mutate(matrix)
        self.change_evidence("WT-002", "page_tracking_matrix", self.write(matrix_ref["path"], matrix))

    def test_page_ids_and_global_pass_do_not_replace_individual_acceptance(self):
        self.change_matrix(lambda matrix: matrix["pages"][0].pop("results"))
        self.assertIn("INDIVIDUAL_PAGE_TRACKING_ACCEPTANCE_REQUIRED", self.check()["errors"])

    def test_missing_or_unexecuted_page_matrix_fails_closed(self):
        reference = next(row for row in self.packet["evidence"] if row["gate_id"] == "WT-002")
        receipt = load_json(self.root / reference["file"]["path"])
        del receipt["page_tracking_matrix"]
        reference["file"] = self.write(reference["file"]["path"], receipt)
        self.assertIn("INDIVIDUAL_PAGE_TRACKING_ACCEPTANCE_REQUIRED", self.check()["errors"])
        self.packet = self.fixture()
        self.change_matrix(lambda matrix: matrix["pages"][0]["results"][0].update(status="NOT_EXECUTED", evidence_ref=None))
        self.assertIn("INDIVIDUAL_PAGE_TRACKING_ACCEPTANCE_REQUIRED", self.check()["errors"])

    def test_matrix_inventory_must_be_an_exact_reviewed_source_artifact(self):
        self.source_hashes.pop("artifacts/page-tracking-inventory.json")
        self.assertIn("PAGE_TRACKING_INVENTORY_NOT_IN_REVIEWED_COMMIT", self.check()["errors"])

    def test_matrix_rejects_wrong_destination_and_mismatched_delivery_correlation(self):
        for mutate in (lambda matrix: matrix["pages"][0]["cta_inventory"][0].update(destination=ORIGIN + "/wrong/"),
                       lambda matrix: matrix["pages"][0]["journey_correlation"]["sheet"].update(lead_sha256="e" * 64)):
            self.packet = self.fixture()
            self.change_matrix(mutate)
            self.assertIn("INDIVIDUAL_PAGE_TRACKING_ACCEPTANCE_REQUIRED", self.check()["errors"])

    def test_matrix_engine_unavailable_or_timed_out_never_uses_global_pass(self):
        with patch("release_packet.shutil.which", return_value=None):
            self.assertIn("INDIVIDUAL_PAGE_TRACKING_ACCEPTANCE_REQUIRED", self.check()["errors"])
        with patch("release_packet.subprocess.run", side_effect=__import__("subprocess").TimeoutExpired("node", 15)):
            self.assertIn("INDIVIDUAL_PAGE_TRACKING_ACCEPTANCE_REQUIRED", self.check()["errors"])


if __name__ == "__main__":
    unittest.main()

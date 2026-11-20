"""Labelled synthetic facts only; no actual business approval or inventory."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import content_evidence as c

NOW = "2026-11-10T12:00:00Z"


def stamp_review(subject, *, page=False, reviewer="synthetic-independent-reviewer",
                 reviewed_at="2026-11-10T09:00:00Z"):
    """Synthetic fixture helper; not part of the approval implementation API."""
    subject["review"] = {"reviewer": reviewer, "reviewed_at_utc": reviewed_at,
                         "evidence_ref": "synthetic-review-proof", "approved": True,
                         "subject_sha256": c.canonical_sha256({k: v for k, v in subject.items() if k != "review"})}
    if page:
        subject["review"].update(claims_complete=True, assets_complete=True)
    return subject


def record(identity, kind, details, pages=None, *, source_class="BUSINESS_EVIDENCE"):
    return stamp_review({"evidence_id": identity, "kind": kind, "page_ids": pages or ["BSRE-LP0001"],
                         "source_class": source_class, "source_ref": "synthetic-source-proof",
                         "source_sha256": hashlib.sha256(b"synthetic-source").hexdigest(),
                         "source_as_of_utc": "2026-11-09T00:00:00Z",
                         "valid_until_utc": "2026-11-11T00:00:00Z", "details": details})


def service_fixture():
    """Small deterministic synthetic input; callers must bind actual release artifacts."""
    expected = [{"page_id": "BSRE-LP0001", "campaign_key": "BSRE-C0001",
                 "content_sha256": hashlib.sha256(b"synthetic-content").hexdigest()}]
    page = dict(expected[0], content_author="synthetic-author", update_owner="synthetic-maintainer",
                offer_kind="BROKERAGE_SERVICE", inventory_presentation="NOT_APPLICABLE",
                evidence_ids=["service-one"], evidence_sha256_by_id={}, offer_inventory_ids=[], alternative_evidence_ids=[],
                disclosure_claim_id=None, alternative_claim_id=None)
    ledger = {"schema": c.SCHEMA, "pages": [stamp_review(page, page=True)],
              "records": [record("service-one", "BROKERAGE_SERVICE",
                                 {"service_key": "synthetic-letting", "description": "Synthetic advisory service; not a real offer."})]}
    page["evidence_sha256_by_id"]["service-one"] = c.canonical_sha256(ledger["records"][0])
    stamp_review(page, page=True)
    return ledger, expected


def inventory(identity, state="available"):
    return record(identity, "INVENTORY", {"property_id": "synthetic-property-" + identity,
                                           "availability_state": state, "asking_price_minor": None, "currency": "AED"})


def add_record(ledger, item):
    ledger["records"].append(item)
    ledger["pages"][0]["evidence_ids"].append(item["evidence_id"])
    ledger["pages"][0]["evidence_sha256_by_id"][item["evidence_id"]] = c.canonical_sha256(item)
    stamp_review(ledger["pages"][0], page=True)


def disclosed_fixture(advisory=False):
    ledger, expected = service_fixture()
    page = ledger["pages"][0]
    if not advisory:
        page["evidence_ids"] = []
        page["evidence_sha256_by_id"] = {}
        ledger["records"] = []
        add_record(ledger, inventory("alternative-one"))
    add_record(ledger, inventory("subject-one", "unavailable"))
    alternatives = ["service-one" if advisory else "alternative-one"]
    add_record(ledger, record("disclosure-one", "CLAIM", {"text": "Synthetic subject is unavailable.",
        "category": "AVAILABILITY_DISCLOSURE", "related_evidence_ids": ["subject-one"]}))
    add_record(ledger, record("alternative-description", "CLAIM", {"text": "Synthetic alternatives described for testing.",
        "category": "ALTERNATIVE_OFFER", "related_evidence_ids": alternatives}))
    page.update(offer_kind="PROPERTY_OFFER", inventory_presentation="DISCLOSED_UNAVAILABLE_WITH_ALTERNATIVES",
                offer_inventory_ids=["subject-one"], alternative_evidence_ids=alternatives,
                disclosure_claim_id="disclosure-one", alternative_claim_id="alternative-description")
    stamp_review(page, page=True)
    return ledger, expected


class ContentEvidenceTests(unittest.TestCase):
    def test_expected_pages_require_canonical_360_pairs(self):
        ledger, expected = service_fixture()
        for page_id, campaign in (("BSRE-LP0000", "BSRE-C0000"),
                                  ("BSRE-LP0361", "BSRE-C0361"),
                                  ("BSRE-LP0001", "BSRE-C0002")):
            with self.subTest(page_id=page_id, campaign=campaign):
                changed = [{**expected[0], "page_id": page_id, "campaign_key": campaign}]
                with self.assertRaisesRegex(c.ContentEvidenceError, "STABLE_PLANNED_PAIR_REQUIRED"):
                    c.evaluate_content_evidence(ledger, expected_pages=changed, now_utc=NOW)

    def evaluate(self, ledger=None, expected=None, now=NOW):
        if ledger is None:
            ledger, expected = service_fixture()
        return c.evaluate_content_evidence(ledger, expected_pages=expected, now_utc=now)

    def test_service_needs_no_buyer_inventory_and_never_grants_authentication(self):
        result = self.evaluate()
        self.assertTrue(result["all_pages_eligible"])
        self.assertFalse(result["authenticated_business_approval"])
        self.assertFalse(result["publication_authorized"])
        self.assertEqual((result["network_calls"], result["production_writes"]), (0, 0))

    def test_inputs_are_immutable_and_reports_repeat_exactly(self):
        ledger, expected = service_fixture()
        before = copy.deepcopy((ledger, expected))
        self.assertEqual(self.evaluate(ledger, expected), self.evaluate(ledger, expected))
        self.assertEqual(before, (ledger, expected))

    def test_exact_content_hash_and_campaign_are_required(self):
        for key, value in (("content_sha256", "a" * 64), ("campaign_key", "BSRE-C0002")):
            ledger, expected = service_fixture()
            ledger["pages"][0][key] = value
            stamp_review(ledger["pages"][0], page=True)
            self.assertIn("REVIEWED_CONTENT_IDENTITY_MISMATCH", self.evaluate(ledger, expected)["pages"][0]["reason_codes"])

    def test_exact_page_set_and_unique_campaigns(self):
        ledger, expected = service_fixture()
        with self.assertRaises(c.ContentEvidenceError):
            self.evaluate(ledger, [])
        expected[0]["page_id"] = "BSRE-LP0002"
        with self.assertRaises(c.ContentEvidenceError):
            self.evaluate(ledger, expected)

    def test_expiry_holds_at_exact_boundary_and_timestamp_edit_cannot_renew_review(self):
        ledger, expected = service_fixture()
        ledger["records"][0]["valid_until_utc"] = NOW
        result = self.evaluate(ledger, expected)
        self.assertIn("EVIDENCE_EXPIRED", result["pages"][0]["reason_codes"])
        self.assertIn("REVIEW_SUBJECT_CHANGED", result["pages"][0]["reason_codes"])
        ledger["records"][0]["valid_until_utc"] = "2026-12-01T00:00:00Z"
        self.assertFalse(self.evaluate(ledger, expected)["all_pages_eligible"])

    def test_shared_record_expiry_suppresses_all_and_only_affected_pages(self):
        ledger, expected = service_fixture()
        for number in (2, 3):
            page = copy.deepcopy(ledger["pages"][0])
            page.update(page_id=f"BSRE-LP{number:04}", campaign_key=f"BSRE-C{number:04}")
            if number == 3:
                page["evidence_ids"] = ["service-other"]
                page["evidence_sha256_by_id"] = {"service-other": "a" * 64}
            ledger["pages"].append(stamp_review(page, page=True))
            expected.append({k: page[k] for k in ("page_id", "campaign_key", "content_sha256")})
        shared = ledger["records"][0]
        shared["page_ids"].append("BSRE-LP0002")
        shared["valid_until_utc"] = "2026-11-10T11:59:59Z"
        stamp_review(shared)
        ledger["records"].append(record("service-other", "BROKERAGE_SERVICE",
            {"service_key": "synthetic-other", "description": "Synthetic advisory."}, ["BSRE-LP0003"]))
        ledger["pages"][2]["evidence_sha256_by_id"]["service-other"] = c.canonical_sha256(ledger["records"][-1])
        stamp_review(ledger["pages"][2], page=True)
        result = self.evaluate(ledger, expected)
        self.assertEqual([p["eligible"] for p in result["pages"]], [False, False, True])

    def test_future_source_and_review_are_not_current_evidence(self):
        ledger, expected = service_fixture()
        ledger["records"][0]["source_as_of_utc"] = "2026-11-10T13:00:00Z"
        stamp_review(ledger["records"][0], reviewed_at="2026-11-10T14:00:00Z")
        reasons = self.evaluate(ledger, expected)["pages"][0]["reason_codes"]
        self.assertIn("SOURCE_FROM_FUTURE", reasons)
        self.assertIn("REVIEW_FROM_FUTURE", reasons)

    def test_review_cannot_predate_source_or_evidence_review(self):
        ledger, expected = service_fixture()
        stamp_review(ledger["records"][0], reviewed_at="2026-11-10T10:00:00Z")
        self.assertIn("PAGE_REVIEW_PREDATES_EVIDENCE_REVIEW", self.evaluate(ledger, expected)["pages"][0]["reason_codes"])
        stamp_review(ledger["records"][0], reviewed_at="2026-11-08T00:00:00Z")
        self.assertIn("REVIEW_PREDATES_SOURCE", self.evaluate(ledger, expected)["pages"][0]["reason_codes"])

    def test_page_and_record_independent_review_and_completeness(self):
        for target in ("page", "record", "claims", "assets", "approval"):
            ledger, expected = service_fixture()
            if target == "page":
                ledger["pages"][0]["review"]["reviewer"] = "synthetic-author"
            elif target == "record":
                ledger["records"][0]["review"]["reviewer"] = "synthetic-author"
            elif target == "approval":
                ledger["records"][0]["review"]["approved"] = False
            else:
                ledger["pages"][0]["review"][target + "_complete"] = False
            with self.subTest(target=target):
                self.assertFalse(self.evaluate(ledger, expected)["all_pages_eligible"])

    def test_missing_record_holds_page_and_scope_cannot_be_widened_silently(self):
        ledger, expected = service_fixture()
        ledger["records"] = []
        result = self.evaluate(ledger, expected)
        self.assertEqual(result["pages"][0]["suppressed_evidence_ids"], ["service-one"])
        ledger, expected = service_fixture()
        ledger["records"][0]["page_ids"] = ["BSRE-LP0002"]
        with self.assertRaises(c.ContentEvidenceError):
            self.evaluate(ledger, expected)

    def test_public_research_does_not_establish_business_offer_or_rights(self):
        ledger, expected = service_fixture()
        ledger["records"][0]["source_class"] = "PUBLIC_RESEARCH"
        stamp_review(ledger["records"][0])
        self.assertFalse(self.evaluate(ledger, expected)["all_pages_eligible"])

    def test_official_legal_source_only_supports_legal_claim(self):
        ledger, expected = service_fixture()
        item = record("claim-one", "CLAIM", {"text": "Synthetic regulatory explanation.", "category": "LEGAL_REGULATORY",
                                               "related_evidence_ids": []}, source_class="OFFICIAL_AUTHORITY")
        add_record(ledger, item)
        self.assertTrue(self.evaluate(ledger, expected)["all_pages_eligible"])
        item["details"]["category"] = "PRICE"
        stamp_review(item)
        self.assertFalse(self.evaluate(ledger, expected)["all_pages_eligible"])

    def test_asset_rights_and_source_content_changes_invalidate_review(self):
        ledger, expected = service_fixture()
        item = record("asset-one", "ASSET_RIGHTS", {"asset_sha256": "a" * 64, "rights_basis": "LICENSED",
                                                    "licence_ref": "synthetic-licence", "permitted_use": "PAID_LANDING_PAGE"})
        add_record(ledger, item)
        self.assertTrue(self.evaluate(ledger, expected)["all_pages_eligible"])
        for field, value in (("source_sha256", "b" * 64), ("source_ref", "synthetic-different-source")):
            changed = copy.deepcopy(ledger)
            changed["records"][-1][field] = value
            self.assertFalse(self.evaluate(changed, expected)["all_pages_eligible"])

    def test_reapproved_replacement_record_cannot_reuse_old_page_review(self):
        ledger, expected = service_fixture()
        ledger["records"][0]["details"]["description"] = "Changed synthetic service."
        stamp_review(ledger["records"][0])
        result = self.evaluate(ledger, expected)
        self.assertIn("PAGE_EVIDENCE_BINDING_CHANGED", result["pages"][0]["reason_codes"])
        self.assertFalse(result["all_pages_eligible"])

    def test_claim_text_and_related_evidence_require_review_and_same_page_binding(self):
        ledger, expected = service_fixture()
        item = record("claim-one", "CLAIM", {"text": "Synthetic claim.", "category": "OTHER", "related_evidence_ids": []})
        add_record(ledger, item)
        item["details"]["text"] = "Changed synthetic claim."
        self.assertFalse(self.evaluate(ledger, expected)["all_pages_eligible"])
        item["details"]["related_evidence_ids"] = ["missing-evidence"]
        stamp_review(item)
        self.assertIn("RELATED_EVIDENCE_NOT_IN_PAGE", self.evaluate(ledger, expected)["pages"][0]["reason_codes"])

    def test_current_listing_requires_current_available_inventory(self):
        ledger, expected = service_fixture()
        add_record(ledger, inventory("inventory-one"))
        page = ledger["pages"][0]
        page.update(offer_kind="PROPERTY_OFFER", inventory_presentation="CURRENT_OFFER", offer_inventory_ids=["inventory-one"])
        stamp_review(page, page=True)
        self.assertTrue(self.evaluate(ledger, expected)["all_pages_eligible"])
        ledger["records"][-1]["details"]["availability_state"] = "unknown"
        stamp_review(ledger["records"][-1])
        result = self.evaluate(ledger, expected)
        self.assertFalse(result["all_pages_eligible"])
        self.assertEqual(result["pages"][0]["suppressed_current_offer_ids"], ["inventory-one"])

    def test_unavailable_disclosed_with_available_alternatives_or_real_advisory_is_supported(self):
        for advisory in (False, True):
            ledger, expected = disclosed_fixture(advisory)
            result = self.evaluate(ledger, expected)
            with self.subTest(advisory=advisory):
                self.assertTrue(result["all_pages_eligible"])
                self.assertEqual(result["pages"][0]["suppressed_current_offer_ids"], ["subject-one"])

    def test_unavailable_disclosure_and_alternative_words_must_bind_exact_subjects(self):
        for identity in ("disclosure-one", "alternative-description"):
            ledger, expected = disclosed_fixture()
            item = next(r for r in ledger["records"] if r["evidence_id"] == identity)
            item["details"]["related_evidence_ids"] = []
            stamp_review(item)
            with self.subTest(identity=identity):
                self.assertFalse(self.evaluate(ledger, expected)["all_pages_eligible"])

    def test_waitlist_or_unknown_alternative_cannot_be_current_stock(self):
        for state in ("waitlist", "unknown", "sold/rented", "unavailable"):
            ledger, expected = disclosed_fixture()
            item = ledger["records"][0]
            item["details"]["availability_state"] = state
            stamp_review(item)
            with self.subTest(state=state):
                self.assertFalse(self.evaluate(ledger, expected)["all_pages_eligible"])

    def test_invalid_shapes_bounds_and_nan_are_sanitized_failures(self):
        mutations = [lambda l: l.update(secret="private-marker"),
                     lambda l: l["pages"][0].update(secret="private-marker"),
                     lambda l: l["records"][0].update(kind=[]),
                     lambda l: l["records"].append(copy.deepcopy(l["records"][0])),
                     lambda l: l["pages"][0]["review"].update(approved="yes"),
                     lambda l: l["records"][0]["details"].update(description="private-marker\n"),
                     lambda l: l.update(pages=[])]
        for mutation in mutations:
            ledger, expected = service_fixture()
            mutation(ledger)
            with self.subTest(mutation=mutation), self.assertRaises(c.ContentEvidenceError) as raised:
                self.evaluate(ledger, expected)
            self.assertNotIn("private-marker", str(raised.exception))
        with self.assertRaises(c.ContentEvidenceError):
            c.canonical_sha256(float("nan"))

    def test_clock_is_explicit_real_calendar_utc_whole_seconds(self):
        for value in (None, "2026-11-10", "2026-02-30T00:00:00Z", "2026-11-10T12:00:00+04:00",
                      "2026-11-10T12:00:00.123Z", "2101-01-01T00:00:00Z"):
            with self.subTest(value=value), self.assertRaises(c.ContentEvidenceError):
                self.evaluate(now=value)
        self.assertTrue(self.evaluate(now=NOW.replace("Z", "+00:00"))["all_pages_eligible"])

    def test_no_private_text_source_reference_or_person_enters_report(self):
        ledger, expected = service_fixture()
        ledger["records"][0]["details"]["description"] = "PRIVATE_SOURCE_TEXT_MARKER"
        ledger["records"][0]["source_ref"] = "private-source-marker"
        ledger["pages"][0]["update_owner"] = "private-maintainer-marker"
        stamp_review(ledger["records"][0])
        stamp_review(ledger["pages"][0], page=True)
        output = json.dumps(self.evaluate(ledger, expected))
        for marker in ("PRIVATE_SOURCE_TEXT_MARKER", "private-source-marker", "private-maintainer-marker"):
            self.assertNotIn(marker, output)

    def test_cli_rejects_duplicate_keys_and_nonfinite_without_leaking_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger_path, expected_path = Path(temporary) / "ledger.json", Path(temporary) / "expected.json"
            expected_path.write_text("[]", encoding="utf-8")
            for raw in ('{"schema":"private-marker","schema":"other"}', '{"private-marker":NaN}'):
                ledger_path.write_text(raw, encoding="utf-8")
                result = subprocess.run([sys.executable, str(Path(c.__file__)), "--ledger", str(ledger_path),
                    "--expected-pages", str(expected_path), "--now-utc", NOW], capture_output=True, text=True)
                self.assertEqual(result.returncode, 2)
                self.assertNotIn("private-marker", result.stdout + result.stderr)
                self.assertFalse(json.loads(result.stdout)["publication_authorized"])


if __name__ == "__main__":
    unittest.main()

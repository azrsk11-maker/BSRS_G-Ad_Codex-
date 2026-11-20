"""Wholly synthetic preparation fixtures; no serving IDs or provider requests."""
import copy
import json
import unittest

import creative_validation as engine

NOW = "2026-11-10T12:00:00Z"
COMMIT = "a" * 40
REVIEWERS = ["SYNTHETIC-REVIEWER"]


def receipt(subject, **changes):
    return {"decision": "PASS", "reviewer_id": REVIEWERS[0], "reference": "SYNTHETIC-REVIEW",
            "subject_sha256": engine.digest(subject), "observed_at_utc": "2026-11-10T11:00:00Z",
            "valid_until_utc": "2026-11-11T11:00:00Z", **changes}


def sign(package):
    for group in package["groups"]:
        for claim in group["claims"]:
            claim["review"] = receipt(engine.claim_subject(group["binding"], claim))
        for rsa in group["rsas"]:
            rsa["copy_review"] = receipt(engine.rsa_subject(rsa, group["claims"]))
            rsa["combination_review"] = receipt(engine.combination_subject(rsa, group["claims"]))
        for asset in group["assets"]:
            asset["review"] = receipt(engine.asset_subject(asset, group["claims"]))
    return package


def fixture():
    binding = {"ad_group_key": "SYNTHETIC-GROUP", "campaign_key": "SYNTHETIC-CAMPAIGN",
               "landing_page_id": "SYNTHETIC-PAGE", "native_page_id": "SYNTHETIC-NATIVE-PAGE",
               "final_url": "https://synthetic.example.invalid/native-page/", "language": "en",
               "company_scope": "SYNTHETIC-COMPANY"}
    claim = {"claim_id": "SYNTHETIC-CLAIM", "statement": "Synthetic advisory service only.",
             "source_reference": "SYNTHETIC-SOURCE", "source_sha256": "b" * 64, "review": {}}
    def entry(index, text):
        return {"text_id": "SYNTHETIC-TEXT-" + str(index), "text": text, "claim_ids": [claim["claim_id"]]}
    control = {"rsa_id": "SYNTHETIC-CONTROL", "role": "CONTROL", "binding": copy.deepcopy(binding),
               "headlines": [entry(1, "Compare Property Choices"), entry(2, "Review Synthetic Options"),
                             entry(3, "Request A Shortlist")],
               "descriptions": [entry(4, "Compare synthetic options for this offline test."),
                                entry(5, "Review costs and next steps with the synthetic service.")],
               "path1": "property", "path2": "compare", "experiment": None,
               "copy_review": {}, "combination_review": {}}
    challenger = copy.deepcopy(control)
    challenger.update(rsa_id="SYNTHETIC-CHALLENGER", role="CHALLENGER",
                      experiment={"reference": "SYNTHETIC-EXPERIMENT", "hypothesis": "Test cost clarity.",
                                  "distinct_decision": "Compare cost clarity against shortlist framing."})
    challenger["headlines"][0]["text"] = "Understand Property Costs"
    asset = {"asset_id": "SYNTHETIC-ASSET", "kind": "CALLOUT", "binding": copy.deepcopy(binding),
             "destination": None, "texts": [entry(6, "Compare Options")],
             "source_reference": "SYNTHETIC-ASSET-SOURCE", "source_sha256": "c" * 64,
             "rights_reference": "SYNTHETIC-RIGHTS-REVIEW", "review": {}}
    package = {"schema": engine.SCHEMA, "reviewed_commit": COMMIT, "fixture_only": True,
               "groups": [{"binding": binding, "claims": [claim], "rsas": [control, challenger],
                           "assets": [asset]}]}
    assets = [{k: copy.deepcopy(asset[k]) for k in ("asset_id", "kind", "binding", "destination")}]
    return sign(package), [copy.deepcopy(binding)], assets


class CreativeValidationTests(unittest.TestCase):
    def setUp(self):
        self.package, self.groups, self.assets = fixture()

    def evaluate(self, **changes):
        options = dict(as_of=NOW, expected_commit=COMMIT, authorized_reviewers=REVIEWERS,
                       expected_assets=self.assets)
        options.update(changes)
        return engine.evaluate_creatives(self.package, self.groups, **options)

    def held(self, expected=None, **options):
        result = self.evaluate(**options)
        self.assertEqual(result["status"], "HOLD", result)
        if expected:
            self.assertEqual(result["errors"][0]["code"], expected)
        return result

    def test_synthetic_library_passes_without_truth_or_permission_claim(self):
        result = self.evaluate()
        self.assertEqual(result["status"], "PASS", result)
        self.assertEqual(result["counts"], {"groups": 1, "rsas": 2, "assets": 1})
        for flag in ("source_truth_verified", "rights_verified", "permission_granted",
                     "execution_authorized", "serving_inventory_verified", "production_ready"):
            self.assertIs(result[flag], False)

    def test_original_inputs_are_preserved(self):
        before = copy.deepcopy((self.package, self.groups, self.assets))
        self.evaluate()
        self.assertEqual(before, (self.package, self.groups, self.assets))

    def test_commit_cannot_be_relabelled(self):
        self.package["reviewed_commit"] = "d" * 40
        self.held("REVIEWED_COMMIT_MISMATCH")

    def test_expected_native_inventory_is_required(self):
        self.groups = []
        self.held("INDEPENDENT_GROUP_INVENTORY_REQUIRED")

    def test_expected_inventory_cannot_be_changed_by_package(self):
        self.package["groups"][0]["binding"]["final_url"] += "changed"
        self.held("GROUP_NATIVE_BINDING_MISMATCH")

    def test_rsa_destination_and_language_bind_exactly(self):
        for field, value in (("final_url", "https://other.example.invalid/"), ("language", "ar"),
                             ("native_page_id", "SYNTHETIC-OTHER"), ("company_scope", "SYNTHETIC-OTHER")):
            with self.subTest(field=field):
                self.setUp()
                self.package["groups"][0]["rsas"][0]["binding"][field] = value
                self.held("RSA_NATIVE_BINDING_MISMATCH")

    def test_native_url_rejects_credentials_and_fragments(self):
        for url in ("http://synthetic.example.invalid/", "https://secret@synthetic.example.invalid/",
                    "https://synthetic.example.invalid/#fragment", "https://bad host.invalid/",
                    "https://synthetic.example.invalid/hidden\npath"):
            with self.subTest(url=url):
                self.groups[0]["final_url"] = url
                self.held("INVALID_NATIVE_DESTINATION")

    def test_one_prepared_rsa_cannot_replace_control_and_challenger(self):
        self.package["groups"][0]["rsas"].pop()
        self.held("CONTROL_AND_CHALLENGER_REQUIRED")

    def test_control_and_challenger_must_be_different_beyond_reordering(self):
        group = self.package["groups"][0]
        group["rsas"][1]["headlines"] = list(reversed(copy.deepcopy(group["rsas"][0]["headlines"])))
        sign(self.package)
        self.held("DISTINCT_DOCUMENTED_CHALLENGER_REQUIRED")

    def test_challenger_needs_documented_decision(self):
        self.package["groups"][0]["rsas"][1]["experiment"]["distinct_decision"] = " "
        self.held("DOCUMENTED_CHALLENGER_REQUIRED")

    def test_counts_are_limits_for_supplied_copy(self):
        for field, count in (("headlines", 2), ("headlines", 16), ("descriptions", 1), ("descriptions", 5)):
            with self.subTest(field=field, count=count):
                self.setUp()
                rsa = self.package["groups"][0]["rsas"][0]
                rsa[field] = [{"text_id": "SYNTHETIC-" + str(i), "text": "Synthetic text " + str(i),
                               "claim_ids": ["SYNTHETIC-CLAIM"]} for i in range(count)]
                self.held("COPY_COUNT_OUTSIDE_LIMIT")

    def test_maximum_counts_accept_distinct_supplied_copy(self):
        rsa = self.package["groups"][0]["rsas"][0]
        for field, count in (("headlines", 15), ("descriptions", 4)):
            rsa[field] = [{"text_id": "SYNTHETIC-" + field + str(i), "text": "Synthetic text " + str(i),
                           "claim_ids": ["SYNTHETIC-CLAIM"]} for i in range(count)]
        sign(self.package)
        self.assertEqual(self.evaluate()["status"], "PASS")

    def test_ascii_and_double_width_character_boundaries(self):
        for field, text, passes in (("headlines", "A" * 30, True), ("headlines", "A" * 31, False),
                                    ("headlines", "房" * 15, True), ("headlines", "房" * 16, False),
                                    ("descriptions", "房" * 45, True), ("descriptions", "房" * 46, False)):
            with self.subTest(field=field, length=len(text)):
                self.setUp()
                self.package["groups"][0]["rsas"][0][field][0]["text"] = text
                sign(self.package)
                self.assertEqual(self.evaluate()["status"], "PASS" if passes else "HOLD")
        self.assertEqual(engine.text_units("A房Ｂ"), 5)
        self.assertEqual(engine.text_units("عقار"), 4)

    def test_ambiguous_emoji_combining_and_hidden_glyphs_hold(self):
        for text in ("Cafe\u0301", "Café", "Property\u200bOptions", "Homes 😀", "Line\nBreak"):
            with self.subTest(text=repr(text)):
                self.setUp()
                self.package["groups"][0]["rsas"][0]["headlines"][0]["text"] = text
                self.held("AMBIGUOUS_OR_UNSUPPORTED_GLYPH")

    def test_dynamic_insertion_is_not_guessed_from_template_length(self):
        self.package["groups"][0]["rsas"][0]["headlines"][0]["text"] = "{KeyWord:Property}"
        self.held("DYNAMIC_OR_TEMPLATE_COPY_UNSUPPORTED")

    def test_normalized_duplicates_hold(self):
        rsa = self.package["groups"][0]["rsas"][0]
        rsa["headlines"][1]["text"] = "compare property choices"
        self.held("DUPLICATE_COPY")

    def test_display_paths_have_limits_and_dependency(self):
        for first, second, code in (("A" * 16, "", "DISPLAY_PATH_OUTSIDE_LIMIT"),
                                    ("", "compare", "SECOND_PATH_REQUIRES_FIRST")):
            with self.subTest(code=code):
                self.setUp()
                self.package["groups"][0]["rsas"][0].update(path1=first, path2=second)
                self.held(code)

    def test_claim_reference_cannot_be_missing_or_unknown(self):
        for refs in ([], ["SYNTHETIC-MISSING"], ["SYNTHETIC-CLAIM", "SYNTHETIC-CLAIM"]):
            with self.subTest(refs=refs):
                self.package["groups"][0]["rsas"][0]["headlines"][0]["claim_ids"] = refs
                self.held("COPY_CLAIM_BINDING_REQUIRED")

    def test_claim_source_change_invalidates_review(self):
        self.package["groups"][0]["claims"][0]["source_sha256"] = "d" * 64
        self.held("REVIEW_SUBJECT_CHANGED")

    def test_copy_change_invalidates_exact_review(self):
        self.package["groups"][0]["rsas"][0]["headlines"][0]["text"] = "Changed Synthetic Copy"
        self.held("REVIEW_SUBJECT_CHANGED")

    def test_all_material_combinations_need_separate_bound_review(self):
        self.package["groups"][0]["rsas"][0]["combination_review"] = copy.deepcopy(
            self.package["groups"][0]["rsas"][0]["copy_review"])
        self.held("REVIEW_SUBJECT_CHANGED")

    def test_absent_or_expired_or_future_evidence_holds(self):
        for changes in ({"valid_until_utc": NOW}, {"observed_at_utc": "2026-11-11T00:00:00Z"}):
            with self.subTest(changes=changes):
                self.setUp()
                self.package["groups"][0]["claims"][0]["review"].update(changes)
                self.held("REVIEW_STALE_OR_FUTURE")
        self.package["groups"][0]["claims"][0]["review"] = {}
        self.held("REVIEW_RECEIPT_REQUIRED")

    def test_review_authority_is_supplied_independently(self):
        self.held("INDEPENDENT_REVIEWER_ALLOWLIST_REQUIRED", authorized_reviewers=[])
        self.package["groups"][0]["claims"][0]["review"]["reviewer_id"] = "SELF-ASSERTED"
        self.held("REVIEW_AUTHORITY_OR_DECISION_REQUIRED")

    def test_copy_review_cannot_predate_bound_claim_review(self):
        self.package["groups"][0]["rsas"][0]["copy_review"]["observed_at_utc"] = "2026-11-09T11:00:00Z"
        self.held("REVIEW_PREDATES_DEPENDENCY")

    def test_combination_review_cannot_predate_bound_claim_review(self):
        self.package["groups"][0]["rsas"][0]["combination_review"]["observed_at_utc"] = "2026-11-09T11:00:00Z"
        self.held("REVIEW_PREDATES_DEPENDENCY")

    def test_combination_review_cannot_predate_later_copy_review(self):
        rsa = self.package["groups"][0]["rsas"][0]
        rsa["copy_review"]["observed_at_utc"] = "2026-11-10T11:30:00Z"
        self.held("REVIEW_PREDATES_DEPENDENCY")

    def test_asset_review_cannot_predate_bound_claim_review(self):
        self.package["groups"][0]["assets"][0]["review"]["observed_at_utc"] = "2026-11-09T11:00:00Z"
        self.held("REVIEW_PREDATES_DEPENDENCY")

    def test_review_order_allows_equal_or_later_observations(self):
        group = self.package["groups"][0]
        for rsa in group["rsas"]:
            rsa["copy_review"]["observed_at_utc"] = "2026-11-10T11:10:00Z"
            rsa["combination_review"]["observed_at_utc"] = "2026-11-10T11:20:00Z"
        group["assets"][0]["review"]["observed_at_utc"] = "2026-11-10T11:05:00Z"
        self.assertEqual(self.evaluate()["status"], "PASS")

    def test_latest_included_claim_review_is_the_dependency_floor(self):
        group = self.package["groups"][0]
        later_claim = copy.deepcopy(group["claims"][0])
        later_claim["claim_id"] = "SYNTHETIC-LATER-CLAIM"
        group["claims"].append(later_claim)
        sign(self.package)
        later_claim["review"]["observed_at_utc"] = "2026-11-10T11:30:00Z"
        for rsa in group["rsas"]:
            rsa["copy_review"] = receipt(engine.rsa_subject(rsa, group["claims"]))
            rsa["combination_review"] = receipt(engine.combination_subject(rsa, group["claims"]))
        group["assets"][0]["review"] = receipt(engine.asset_subject(group["assets"][0], group["claims"]))
        self.held("REVIEW_PREDATES_DEPENDENCY")

    def test_asset_destination_and_scope_cannot_drift(self):
        self.package["groups"][0]["assets"][0]["destination"] = "https://wrong.example.invalid/"
        self.held("ASSET_DESTINATION_OR_INVENTORY_MISMATCH")

    def test_assets_require_current_exact_rights_review(self):
        asset = self.package["groups"][0]["assets"][0]
        asset["rights_reference"] = ""
        self.held("ASSET_SOURCE_AND_RIGHTS_REFERENCE_REQUIRED")
        asset["rights_reference"] = "SYNTHETIC-CHANGED-RIGHTS"
        self.held("REVIEW_SUBJECT_CHANGED")

    def test_missing_or_unexpected_assets_hold(self):
        self.package["groups"][0]["assets"] = []
        self.held("COMPLETE_CREATIVE_INVENTORY_REQUIRED")
        self.setUp()
        self.held("ASSET_DESTINATION_OR_INVENTORY_MISMATCH", expected_assets=[])

    def test_duplicate_asset_copy_with_new_identity_still_holds(self):
        duplicate = copy.deepcopy(self.package["groups"][0]["assets"][0])
        duplicate["asset_id"] = "SYNTHETIC-DUPLICATE-ASSET"
        duplicate["texts"][0]["text"] = "compare options"
        self.package["groups"][0]["assets"].append(duplicate)
        self.assets.append({k: copy.deepcopy(duplicate[k]) for k in
                            ("asset_id", "kind", "binding", "destination")})
        sign(self.package)
        self.held("DUPLICATE_ASSET_CONTENT")

    def test_sanitized_diagnostics_never_echo_copy_or_private_refs(self):
        marker = "PRIVATE-COPY-AND-REFERENCE-DO-NOT-REPORT"
        self.package["groups"][0]["claims"][0]["source_reference"] = marker
        result = self.held("REVIEW_SUBJECT_CHANGED")
        self.assertNotIn(marker, json.dumps(result))
        self.assertNotIn("example.invalid", json.dumps(result))
        self.assertNotIn("SYNTHETIC-REVIEWER", json.dumps(result))

    def test_malformed_input_produces_constant_hold(self):
        for value in (None, [], "private arbitrary error payload"):
            with self.subTest(value=value):
                result = engine.evaluate_creatives(value, self.groups, as_of=NOW, expected_commit=COMMIT,
                                                   authorized_reviewers=REVIEWERS)
                self.assertEqual(result["status"], "HOLD")
        self.package["groups"][0]["rsas"][0]["headlines"][0]["claim_ids"] = [{}]
        self.held("COPY_CLAIM_BINDING_REQUIRED")


if __name__ == "__main__":
    unittest.main()

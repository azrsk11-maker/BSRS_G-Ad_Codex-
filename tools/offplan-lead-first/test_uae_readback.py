import json
import unittest

from check_uae_readback import HERE, SOURCE, verify


class UAEReadbackTest(unittest.TestCase):
    def setUp(self):
        profile = json.loads((HERE / "global-localization/REFERENCES.json").read_bytes())["existing_uae_keywords"]
        original = json.loads((SOURCE / profile["path"]).read_bytes())
        campaign_id, ad_group_id = "24372566774", "204397706154"
        modes = {"Exact match": "EXACT", "Phrase match": "PHRASE"}
        self.readback = {
            "schema": "bsre.offplan.uae-child-readback.v1", "account": "573-038-4686",
            "campaignId": campaign_id, "adGroupId": ad_group_id,
            "campaignStatus": "Paused", "adGroupStatus": "Paused",
            "resaleAdGroup": {"id": "204397706314", "explicitStatus": "Paused", "servingScope": False},
            "keywordFilter": "Enabled, Paused", "keywordViewTotal": 16,
            "keywordRows": [
                [row["Keyword ID"], row["Keyword"][1:-1], modes[row["Match type"]], row["Keyword status"]]
                for row in original["keywords"]
                if (row["Campaign ID"], row["Ad group ID"]) == (campaign_id, ad_group_id)
            ],
            "adViewTotal": 1,
            "ad": {"id": "828621612892", "explicitStatus": "Paused", "type": "Responsive search ad",
                   "policyDetails": "Approved", "adStrength": "Pending",
                   "finalUrl": "https://blackswanrealestate.ae/enquire/off-plan/"},
            "negativeViewTotal": 1, "directNegatives": [["real estate jobs", "PHRASE", "Campaign"]],
            "accountLevelNegativeCount": 0, "sharedNegativeListViewTotal": 1,
            "sharedNegativeList": {"attachmentViewTotal": 1, "attachedCampaigns": ["Example legacy campaign"]},
            "settingsOrCampaignWrites": False, "testEnquiriesOrConversions": 0,
        }

    def test_matches_exact_saved_scope(self):
        result = verify(self.readback)
        self.assertEqual(result["keywordRows"], 16)
        self.assertEqual(result["directNegativeComparisons"], 16)

    def test_resale_cannot_enter_launch_scope(self):
        self.readback["resaleAdGroup"]["servingScope"] = True
        with self.assertRaisesRegex(ValueError, "Resale must be explicitly paused"):
            verify(self.readback)

    def test_incomplete_keyword_inventory_fails(self):
        self.readback["keywordRows"].pop()
        with self.assertRaisesRegex(ValueError, "Keyword inventory is incomplete"):
            verify(self.readback)

    def test_enabled_keyword_fails_even_if_its_id_and_text_match(self):
        self.readback["keywordRows"][0][3] = "Enabled"
        with self.assertRaisesRegex(ValueError, "Keyword ID, text, match type or status changed"):
            verify(self.readback)

    def test_resale_destination_fails_even_if_ad_id_matches(self):
        self.readback["ad"]["finalUrl"] = "https://blackswanrealestate.ae/enquire/resale/"
        with self.assertRaisesRegex(ValueError, "Unexpected ad, destination"):
            verify(self.readback)

    def test_protected_off_plan_terms_cannot_be_excluded(self):
        self.readback["directNegatives"][0] = ["off plan", "PHRASE", "Campaign"]
        with self.assertRaisesRegex(ValueError, "A direct negative conflicts"):
            verify(self.readback)

    def test_shared_list_attachment_to_launch_parent_fails(self):
        self.readback["sharedNegativeList"]["attachedCampaigns"] = ["BSRE_OFFPLAN_SEARCH_TW_ZH_TW"]
        with self.assertRaisesRegex(ValueError, "Shared negatives apply to an off-plan launch campaign"):
            verify(self.readback)


if __name__ == "__main__":
    unittest.main()

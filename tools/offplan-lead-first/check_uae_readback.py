"""Compare a saved prelaunch UAE Ads readback with reviewed Source evidence."""

import argparse
import hashlib
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[1]
MAX_READBACK_BYTES = 64 * 1024
sys.path.insert(0, str(SOURCE / "tools/keyword-system"))
from keyword_audit import negative_matches


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(evidence):
    launch = json.loads((HERE / "launch.json").read_bytes())["markets"][0]
    receipt = json.loads((HERE / "native-paused/APPLIED.json").read_bytes())
    require(evidence["schema"] == "bsre.offplan.uae-child-readback.v1", "Unexpected readback schema")
    require(evidence["account"] == receipt["account_id"], "Wrong Ads account")
    require(evidence["settingsOrCampaignWrites"] is False, "Readback must be read-only")
    require(evidence["testEnquiriesOrConversions"] == 0, "Readback must contain no test sends")
    require(
        (evidence["campaignId"], evidence["adGroupId"]) == (launch["campaign_id"], launch["offplan_ad_group_id"]),
        "Unexpected UAE serving scope",
    )
    require(evidence["campaignStatus"] == evidence["adGroupStatus"] == "Paused", "UAE scope must stay paused")
    require(
        evidence["resaleAdGroup"] == {"id": "204397706314", "explicitStatus": "Paused", "servingScope": False},
        "Resale must be explicitly paused and outside serving scope",
    )

    reference = json.loads((HERE / "global-localization/REFERENCES.json").read_bytes())["existing_uae_keywords"]
    original = (SOURCE / reference["path"]).read_bytes()
    require(hashlib.sha256(original).hexdigest() == reference["sha256"], "Prior keyword evidence changed")
    modes = {"Exact match": "EXACT", "Phrase match": "PHRASE"}
    expected = {
        (row["Keyword ID"], row["Keyword"][1:-1], modes[row["Match type"]], row["Keyword status"])
        for row in json.loads(original)["keywords"]
        if (row["Campaign ID"], row["Ad group ID"]) == (launch["campaign_id"], launch["offplan_ad_group_id"])
    }
    rows = evidence["keywordRows"]
    require(evidence["keywordFilter"] == "Enabled, Paused", "Readback must cover enabled and paused keywords")
    require(evidence["keywordViewTotal"] == len(rows) == len(expected) == 16, "Keyword inventory is incomplete")
    require({tuple(row) for row in rows} == expected, "Keyword ID, text, match type or status changed")
    ad = evidence["ad"]
    require(
        evidence["adViewTotal"] == 1 and ad["id"] == launch["ad_id"]
        and ad["finalUrl"] == launch["last_observed_final_url"] and ad["explicitStatus"] == "Paused"
        and ad["type"] == "Responsive search ad" and ad["policyDetails"] == "Approved",
        "Unexpected ad, destination, policy status or serving state",
    )

    direct = evidence["directNegatives"]
    require(evidence["negativeViewTotal"] == len(direct), "Negative keyword inventory is incomplete")
    for text, match, scope in direct:
        require(scope in {"Campaign", "Ad group"}, "Unexpected direct negative scope")
        require(text.strip() and match in {"EXACT", "PHRASE", "BROAD"}, "Invalid negative keyword")
        require(not any(negative_matches(text, match, row[1]) for row in rows), "A direct negative conflicts")
    require(evidence["accountLevelNegativeCount"] == 0, "Account-level negatives require separate review")
    shared = evidence["sharedNegativeList"]
    attached = set(shared["attachedCampaigns"])
    require(evidence["sharedNegativeListViewTotal"] == 1 and shared["attachmentViewTotal"] == len(attached)
            == len(shared["attachedCampaigns"]), "Shared negative attachment inventory is incomplete")
    require(not attached.intersection(row["name"] for row in receipt["campaigns"]),
            "Shared negatives apply to an off-plan launch campaign")
    return {"result": "MATCHED_SCOPED_SAVED_READBACK", "keywordRows": len(rows), "adRows": 1,
            "directNegativeComparisons": len(direct) * len(rows), "adStrength": ad["adStrength"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("readback", type=Path)
    args = parser.parse_args()
    try:
        with args.readback.open("rb") as stream:
            body = stream.read(MAX_READBACK_BYTES + 1)
        require(len(body) <= MAX_READBACK_BYTES, "Readback is too large")
        result = verify(json.loads(body))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"result": "HOLD", "reason": str(error)}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Join pinned, independently reviewed off-plan provider evidence offline."""

from argparse import ArgumentParser
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re

from check_gtm_exports import VerificationError, read_json, require
from check_gtm_publication import verify_publication


CONFIG_SCHEMA = "bsre.offplan.provider-configuration.v1"
PAID_SCHEMA = "bsre.offplan.genuine-paid-receipt.v1"
LAUNCH = Path(__file__).resolve().parents[1] / "launch.json"
FORWARD_SHA256 = "a059b35048a667097efb58d99f7c0143813e49e9f1f0bd4a41674dc1039c1131"
DESTINATION_SHA256 = "41a6bcda74817721ca274095fec574e7a588d0a9e4ba983d2c03f00ecf6a04c0"
GTM_CAPTURE_SHA256 = "be44e31eaf01516ffb6277a1f3d721cf38e96115f163b051d68315807a232877"
TEST_CAPTURE_SHA256 = "20666277a989f2632a4f3278319b857becb29b460a40ed86d781c1b056ac9aa5"
PAGE_ID = 26751
OBSERVATION = {"provenance", "observed_at_utc", "source_evidence_sha256"}


def fields(row, expected, label):
    require(isinstance(row, dict) and row.keys() == expected, f"Unexpected {label} fields")


def digest(value):
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) is not None


def pinned(path, expected, label):
    data, actual = read_json(path)
    require(digest(expected) and actual == expected, f"{label} SHA-256 mismatch")
    return data


def utc(value, now):
    require(isinstance(value, str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", value),
            "Expected an exact UTC timestamp")
    timestamp = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    require(timestamp <= now, "Evidence timestamp is in the future")
    return timestamp


def observe(row, extra, provenance, now):
    fields(row, OBSERVATION | extra, provenance)
    require(row["provenance"] == provenance and digest(row["source_evidence_sha256"]),
            "Required source provenance and evidence digest are missing")
    return utc(row["observed_at_utc"], now)


def distinct_sources(*rows):
    require(len({row["source_evidence_sha256"] for row in rows}) == len(rows),
            "Distinct observations must identify distinct source evidence")


def reviewed_scope():
    launch, _ = read_json(LAUNCH)
    policy = launch["accepted_conversion_policy"]
    uae, = [market for market in launch["markets"] if market["country_code"] == "AE"]
    return {
        "account": launch["account_id"], "action_id": policy["action_id"],
        "optimization": policy["optimization"], "count": policy["count"],
        "fallback_aed": policy["fallback_value_aed"], "duplicate_ga4_import": policy["duplicate_ga4_import"],
        "url": launch["site_origin"] + launch["english_funnel_path"],
        "campaign_id": uae["campaign_id"], "ad_group_id": uae["offplan_ad_group_id"], "ad_id": uae["ad_id"],
    }


def verify_configuration(data, scope, now, gtm_export, gtm_observation, gtm_capture):
    fields(data, {"schema", "wordpress", "ads", "gtm"}, "configuration")
    wordpress, ads, gtm = (data[key] for key in ("wordpress", "ads", "gtm"))
    wp_time = observe(wordpress, {"url", "page_id", "archive_sha256", "advertising_enabled"},
                      "AUTHENTICATED_HOST_AND_WORDPRESS_READBACK", now)
    ads_keys = {"account", "action_id", "optimization", "count", "fallback_aed", "duplicate_ga4_import"}
    ads_time = observe(ads, ads_keys | {"destination_sha256", "auto_tagging", "website_source", "account_level_goal"},
                       "AUTHENTICATED_GOOGLE_ADS_CONFIGURATION", now)
    gtm_time = observe(gtm, set(), "AUTHENTICATED_GTM_VERSIONS_READBACK", now)
    distinct_sources(wordpress, ads, gtm)
    require(wordpress["url"] == scope["url"] and wordpress["page_id"] == PAGE_ID
            and wordpress["archive_sha256"] == FORWARD_SHA256 and wordpress["advertising_enabled"] is True,
            "Exact deployed canonical page, forward package or advertising setting was not established")
    require(all(ads[key] == scope[key] for key in ads_keys)
            and type(ads["fallback_aed"]) is int and ads["duplicate_ga4_import"] is False
            and ads["destination_sha256"] == DESTINATION_SHA256 and ads["website_source"] is True
            and ads["account_level_goal"] is False and ads["auto_tagging"] is True,
            "Ads account, approved native action or configuration differs")
    publication = verify_publication(gtm_export, gtm_observation, gtm["source_evidence_sha256"],
                                     gtm_capture, GTM_CAPTURE_SHA256)
    require(gtm["observed_at_utc"] == publication["observed_at_utc"], "GTM observation times differ")
    return max(wp_time, ads_time, gtm_time), publication["live_version_id"]


def excluded_transaction(capture):
    test = pinned(capture, TEST_CAPTURE_SHA256, "Excluded TEST capture")
    event_id = test["event_id"]
    require(test["status"] == "ACCEPTED" and test["optional_purposes_denied"] is True
            and test["measurement_eligible"] is False and test["browser_conversion_code_executed"] is False
            and isinstance(event_id, str) and re.fullmatch(r"[A-Za-z0-9._:-]{1,64}", event_id),
            "Excluded delivery TEST receipt was not established")
    return sha256(event_id.encode("utf-8")).hexdigest()


def verify_paid(data, configuration_sha256, scope, configured_at, live_version, excluded, now):
    fields(data, {"schema", "configuration_sha256", "paid_click", "receipt", "provider"}, "paid evidence")
    require(data["schema"] == PAID_SCHEMA and data["configuration_sha256"] == configuration_sha256,
            "Paid evidence does not bind the reviewed configuration")
    click, receipt, provider = (data[key] for key in ("paid_click", "receipt", "provider"))
    click_keys = {"account", "campaign_id", "ad_group_id", "ad_id", "url"}
    click_link = {"click_id_kind", "click_id_sha256"}
    click_observed = observe(click, click_keys | click_link | {"clicked_at_utc"},
                             "AUTHENTICATED_GOOGLE_ADS_PAID_CLICK_READBACK", now)
    receipt_observed = observe(receipt, click_link | {"url", "page_id", "archive_sha256",
                                         "transaction_id_sha256", "accepted_at_utc", "record_kind",
                                         "measurement_eligible", "replayed"}, "VERIFIED_SIGNED_INTAKE_RECEIPT", now)
    provider_observed = observe(provider, click_link | {"account", "action_id", "destination_sha256", "live_gtm_version",
                                           "transaction_id_sha256", "producer", "conversion_at_utc",
                                           "attributed_count", "duplicate_count"},
                                "AUTHENTICATED_GOOGLE_ADS_ATTRIBUTION_AND_DEDUPLICATION", now)
    distinct_sources(click, receipt)
    distinct_sources(provider, receipt)
    require(all(click[key] == scope[key] for key in click_keys), "Paid click is outside the canonical UAE child scope")
    require(receipt["record_kind"] == "GENUINE_ENQUIRY" and receipt["measurement_eligible"] is True
            and receipt["replayed"] is False and receipt["url"] == scope["url"] and receipt["page_id"] == PAGE_ID
            and receipt["archive_sha256"] == FORWARD_SHA256,
            "Receipt is ineligible, a TEST or replay, or outside the reviewed route")
    require(provider["account"] == scope["account"] and provider["action_id"] == scope["action_id"]
            and provider["destination_sha256"] == DESTINATION_SHA256 and provider["live_gtm_version"] == live_version
            and provider["producer"] == "NATIVE_WEBSITE_ACTION"
            and type(provider["attributed_count"]) is int and provider["attributed_count"] == 1
            and type(provider["duplicate_count"]) is int and provider["duplicate_count"] == 0,
            "Approved native action or single attributed conversion and deduplication evidence differs")
    require(digest(click["click_id_sha256"]) and digest(receipt["transaction_id_sha256"])
            and click["click_id_kind"] in ("gclid", "gbraid", "wbraid")
            and all(click[key] == receipt[key] == provider[key] for key in click_link)
            and receipt["transaction_id_sha256"] == provider["transaction_id_sha256"],
            "Provider, paid click and signed receipt identifiers do not reconcile")
    require(receipt["transaction_id_sha256"] != excluded, "The approved delivery TEST is excluded")
    clicked = utc(click["clicked_at_utc"], now)
    accepted = utc(receipt["accepted_at_utc"], now)
    converted = utc(provider["conversion_at_utc"], now)
    require(configured_at <= clicked <= accepted <= converted
            and clicked <= click_observed and accepted <= receipt_observed and converted <= provider_observed,
            "Deployment, paid click, accepted receipt and provider evidence timestamps do not reconcile")


def review(configuration, configuration_sha256, *, gtm_export=None, gtm_observation=None, gtm_capture=None,
           paid_receipt=None, paid_sha256=None, excluded_test_capture=None):
    result = {"status": "HOLD", "configuration_evidence_matched": False, "paid_attribution_evidence_matched": False,
              "provider_independently_checked": False, "launch_ready": False, "activation_authorized": False}
    try:
        now = datetime.now(timezone.utc)
        config = pinned(configuration, configuration_sha256, "Configuration")
        require(config.get("schema") == CONFIG_SCHEMA, "No authenticated provider configuration bundle")
        require(all(path is not None for path in (gtm_export, gtm_observation, gtm_capture)),
                "Current GTM export, live observation and original capture are required")
        scope = reviewed_scope()
        configured_at, live_version = verify_configuration(config, scope, now, gtm_export, gtm_observation, gtm_capture)
        result.update(configuration_evidence_matched=True, configuration_sha256=configuration_sha256)
        require(paid_receipt is not None and paid_sha256 is not None, "Genuine paid receipt evidence is unavailable")
        require(excluded_test_capture is not None, "The pinned delivery TEST capture is required for exclusion")
        paid = pinned(paid_receipt, paid_sha256, "Paid evidence")
        excluded = excluded_transaction(excluded_test_capture)
        verify_paid(paid, configuration_sha256, scope, configured_at, live_version, excluded, now)
    except (OSError, KeyError, TypeError, ValueError) as error:
        result["reason"] = str(error) if isinstance(error, VerificationError) else "Invalid evidence or timestamp"
        return result
    result.update(status="MATCHED_GENUINE_PAID_RECEIPT_EVIDENCE", paid_attribution_evidence_matched=True,
                  paid_sha256=paid_sha256)
    return result


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("configuration", type=Path)
    parser.add_argument("configuration_sha256")
    parser.add_argument("--gtm-export", type=Path)
    parser.add_argument("--gtm-observation", type=Path)
    parser.add_argument("--gtm-capture", type=Path)
    parser.add_argument("--paid-receipt", type=Path)
    parser.add_argument("--paid-sha256")
    parser.add_argument("--excluded-test-capture", type=Path)
    result = review(**vars(parser.parse_args()))
    print(json.dumps(result))
    return 3 if result["status"] == "HOLD" else 0


if __name__ == "__main__":
    raise SystemExit(main())

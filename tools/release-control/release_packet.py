"""Read-only release-packet review. Offline evidence never grants authority."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess

OWNER = "azrsk11-maker"
REPO = "azrsk11-maker/BSRS_G-Ad_Codex-"
ORIGIN = "https://blackswanrealestate.ae"
ACCOUNT = "573-038-4686"
KINDS = {"WEBSITE_PUBLICATION", "TRACKING_PUBLICATION", "ADS_CONFIGURATION", "ADS_ACTIVATION"}
WT_GATES = {f"WT-{n:03}" for n in range(1, 31)}
POSTFLIGHT_GATES = {"WT-031", "WT-032"}
BRAND_POLICY_GATE = "BRAND_POLICY"
SERVING_CHILDREN_GATE = "SERVING_CHILDREN"
BRAND_CAMPAIGN_ID = "24378494098"
BRAND_AD_GROUP_ID = "204397706114"
BRAND_AD_ID = "828621612889"
LAUNCH_ENABLED_CHILD_COUNTS = {
    "24372566774": {"ad_groups": 2, "ads": 2, "keywords": 34},
    "24367388382": {"ad_groups": 2, "ads": 2, "keywords": 24},
    "24378494092": {"ad_groups": 1, "ads": 1, "keywords": 16},
    "24378494098": {"ad_groups": 1, "ads": 1, "keywords": 8},
}
EXTRA_GATES = {"SOURCE_TRUTH", "KEYWORD_SCOPE", "ROUTING_RETRY", "RETENTION_RECOVERY", "STAFF_CAPACITY", "QUALIFICATION_HISTORY", "SCOPED_ROLLBACK"}
GATES = WT_GATES | EXTRA_GATES
METHODS = {"AUTHENTICATED_STAGING_ACCEPTANCE", "AUTHENTICATED_CONFIGURATION_READBACK", "OWNER_REVIEWED_BUSINESS_EVIDENCE"}
CHECKS = {"offline-validation", "native-wordpress-check"}
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
LOGIN = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}\Z")
MAX_BYTES = 2_000_000
MAX_ARTIFACT_BYTES = 64_000_000
LAUNCH_BUDGET_FILS = {
    "24372566774": 120_000,
    "24367388382": 40_000,
    "24378494092": 30_000,
    "24378494098": 10_000,
}
CURRENT_CAMPAIGNS = set(LAUNCH_BUDGET_FILS)
FROZEN_BASELINE_PATH = Path(__file__).resolve().parents[2] / "docs/audit/CAMPAIGN_STATUS_BASELINE_2026-11-07.json"
TRACKING_AFTER = {"enhanced_matching": False, "personalization": False, "audience_exports": False,
    "accepted_enquiry_bidding": "SECONDARY_OUTSIDE_CUSTOM_GOALS", "auto_form_collection": False,
    "page_view_producers": 1, "accepted_enquiry_route": "NATIVE_ADS_SECONDARY", "qualified_import": "GCLID_ONLY_DATA_MANAGER"}
ADS_SAFE_SETTINGS = {"search_partners": False, "display_expansion": False, "ai_max": False,
    "final_url_expansion": False, "positive_bid_adjustment": 0, "country": "AE", "language": "en",
    "location_mode": "PRESENCE", "schedule": "DAILY_10:00_19:00_Asia/Dubai",
    "accepted_enquiry_is_secondary": True, "accepted_enquiry_in_custom_goal": False}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def load_json(path, expected_sha256=None):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("DUPLICATE_JSON_KEY")
            result[key] = value
        return result
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("JSON_TOO_LARGE")
    data = path.read_bytes()
    if len(data) > MAX_BYTES:
        raise ValueError("JSON_TOO_LARGE")
    if expected_sha256 is not None and hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError("ARTIFACT_HASH_MISMATCH")
    return json.loads(data.decode("utf-8-sig"), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("NONFINITE_JSON")))


def instant(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value):
        raise ValueError("UTC_SECONDS_REQUIRED")
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def frozen_legacy_statuses():
    baseline = load_json(FROZEN_BASELINE_PATH)
    campaigns = baseline["campaigns"]
    statuses = {row["id"]: row["status"].upper() for row in campaigns}
    legacy = {identity: status for identity, status in statuses.items() if identity not in CURRENT_CAMPAIGNS}
    if (baseline["account_id"] != ACCOUNT or len(statuses) != len(campaigns) or
            not CURRENT_CAMPAIGNS.issubset(statuses) or len(legacy) != 16 or
            set(legacy.values()) != {"PAUSED", "REMOVED"}):
        raise ValueError("INVALID_REVIEWED_FROZEN_BASELINE")
    return legacy


def verify_file(root, record):
    """Only explicit bounded repository-relative files; no symlink/private paths."""
    if not isinstance(record, dict) or set(record) != {"path", "sha256"}:
        raise ValueError("FILE_REFERENCE_SHAPE")
    name = record["path"]
    if not isinstance(name, str) or "\\" in name or ":" in name or not name:
        raise ValueError("RELATIVE_POSIX_PATH_REQUIRED")
    posix = PurePosixPath(name)
    if posix.is_absolute() or any(p in {".", "..", ".git", ".env"} or p.startswith(".") for p in posix.parts) or str(posix) != name:
        raise ValueError("UNSAFE_REFERENCE_PATH")
    expected = record["sha256"]
    if not isinstance(expected, str) or not SHA256.fullmatch(expected):
        raise ValueError("SHA256_REQUIRED")
    root = Path(root).resolve(strict=True)
    target = root
    for part in posix.parts:
        target = target / part
        if target.is_symlink():
            raise ValueError("SYMLINK_REFERENCE_FORBIDDEN")
    target = target.resolve(strict=True)
    if not target.is_relative_to(root) or not target.is_file() or target.stat().st_size > MAX_ARTIFACT_BYTES:
        raise ValueError("BOUNDED_LOCAL_FILE_REQUIRED")
    if target.suffix.lower() not in {".json", ".md", ".py", ".php", ".mjs", ".js", ".css", ".html", ".csv", ".yml", ".yaml"}:
        raise ValueError("UNREVIEWABLE_FILE_TYPE")
    hashed, length = hashlib.sha256(), 0
    with target.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            length += len(chunk)
            if length > MAX_ARTIFACT_BYTES:
                raise ValueError("ARTIFACT_TOO_LARGE")
            hashed.update(chunk)
    if hashed.hexdigest() != expected:
        raise ValueError("ARTIFACT_HASH_MISMATCH")
    return target


def validate(packet, root, *, now=None, checkout_head=None, checkout_clean=False, source_hashes=None):
    """Untrusted assertions can be consistent, never authenticated offline."""
    errors = []
    now = now or datetime.now(timezone.utc)
    def need(condition, code):
        if not condition:
            errors.append(code)
    def match(pattern, value):
        return isinstance(value, str) and pattern.fullmatch(value) is not None
    def rows(value, maximum=128):
        if not isinstance(value, list) or len(value) > maximum or not all(isinstance(x, dict) for x in value):
            raise ValueError("BOUNDED_OBJECT_LIST_REQUIRED")
        return value
    def file(record):
        return verify_file(root, record)
    def record_json(record):
        return load_json(file(record), record["sha256"])
    try:
        if not isinstance(packet, dict) or set(packet) != {"schema_version", "proposal", "evidence", "review", "decisions", "approval"}:
            raise ValueError("PACKET_SHAPE")
        need(type(packet["schema_version"]) is int and packet["schema_version"] == 1, "SCHEMA_VERSION")
        proposal = packet["proposal"]
        if not isinstance(proposal, dict) or set(proposal) != {"release_id", "kind", "created_at_utc", "commit", "operator", "pusher", "target_origin", "ads_account", "resources", "artifacts", "rollback", "post_release", "media_limits", "change"}:
            raise ValueError("PROPOSAL_SHAPE")
        need(isinstance(proposal["release_id"], str) and re.fullmatch(r"BSRE-REL-[A-Z0-9-]{1,60}", proposal["release_id"]), "RELEASE_ID")
        need(proposal["kind"] in KINDS, "SEPARATE_RELEASE_KIND")
        commit = proposal["commit"]
        need(match(COMMIT, commit) and commit == checkout_head and checkout_clean is True, "CLEAN_EXACT_CHECKOUT_REQUIRED")
        need(match(LOGIN, proposal["operator"]) and match(LOGIN, proposal["pusher"]), "OPERATOR_IDENTITY_REQUIRED")
        need(proposal["target_origin"] == ORIGIN and proposal["ads_account"] == ACCOUNT, "REAL_ESTATE_SCOPE_ONLY")
        created = instant(proposal["created_at_utc"])
        need(created <= now, "FUTURE_PROPOSAL")
        resources = rows(proposal["resources"], 360)
        need(bool(resources), "EXACT_RESOURCES_REQUIRED")
        resource_ids, urls, campaign_ids, native_ids = [], [], [], []
        for resource in resources:
            need(set(resource) == {"page_id", "campaign_key", "campaign_id", "wordpress_page_id", "url"}, "RESOURCE_SHAPE")
            page_id, campaign_id = resource.get("page_id"), resource.get("campaign_id")
            page_ok = isinstance(page_id, str) and re.fullmatch(r"BSRE-LP\d{4}", page_id) and 1 <= int(page_id[-4:]) <= 360
            need(page_ok and resource.get("campaign_key") == "BSRE-C" + page_id[-4:], "STABLE_PLANNED_PAIR_REQUIRED")
            need(isinstance(campaign_id, str) and re.fullmatch(r"[1-9]\d{5,19}", campaign_id), "VERIFIED_PLATFORM_CAMPAIGN_ID_REQUIRED")
            need(type(resource.get("wordpress_page_id")) is int and resource["wordpress_page_id"] > 0, "VERIFIED_WORDPRESS_ID_REQUIRED")
            url = resource.get("url")
            need(isinstance(url, str) and re.fullmatch(re.escape(ORIGIN) + r"/(?:[a-z0-9-]+/)+", url), "EXACT_NATIVE_CANONICAL_URL_REQUIRED")
            resource_ids.append(page_id); urls.append(url); campaign_ids.append(campaign_id); native_ids.append(resource.get("wordpress_page_id"))
        need(all(len(set(values)) == len(resources) for values in (resource_ids, urls, campaign_ids, native_ids)), "DEDICATED_CAMPAIGN_PAGE_BIJECTION")
        artifacts = rows(proposal["artifacts"])
        need(bool(artifacts) and len({x.get("path") for x in artifacts}) == len(artifacts), "UNIQUE_ARTIFACTS_REQUIRED")
        for artifact in artifacts:
            file(artifact)
            need(isinstance(source_hashes, dict) and source_hashes.get(artifact["path"]) == artifact["sha256"], "ARTIFACT_NOT_IN_REVIEWED_COMMIT")
        change = proposal["change"]
        need(isinstance(change, dict), "KIND_SPECIFIC_CHANGE_REQUIRED")
        if proposal["kind"] == "WEBSITE_PUBLICATION":
            need(change == {"native_page_ids": sorted(native_ids), "preserve_main_site": True, "reviewed_content_only": True}, "EXACT_NATIVE_PUBLICATION_SCOPE")
        elif proposal["kind"] == "TRACKING_PUBLICATION":
            need(change.get("gtm_container_id") == "GTM-NW8WXKRF" and change.get("ga4_measurement_id") == "G-W01P9W3NWE", "VERIFIED_TRACKING_DESTINATIONS_REQUIRED")
            need(type(change.get("version_before")) is int and type(change.get("version_after")) is int and 0 < change["version_before"] < change["version_after"], "EXACT_TRACKING_VERSION_TRANSITION")
            need(change.get("enhanced_matching") is False and change.get("personalization") is False and change.get("audience_exports") is False and change.get("accepted_enquiry_bidding") == "SECONDARY_OUTSIDE_CUSTOM_GOALS", "LAUNCH_MEASUREMENT_BOUNDARIES")
            diff = record_json(change["configuration_diff"])
            need(set(diff) == {"target_container", "measurement_id", "before_version", "after_version", "before", "after"} and diff.get("target_container") == change["gtm_container_id"] and diff.get("measurement_id") == change["ga4_measurement_id"] and diff.get("before_version") == change["version_before"] and diff.get("after_version") == change["version_after"], "TRACKING_CONFIGURATION_DIFF_REQUIRED")
            need(isinstance(diff.get("before"), dict) and set(diff["before"]) == set(TRACKING_AFTER) and digest(diff.get("after")) == digest(TRACKING_AFTER), "NORMALIZED_TRACKING_DIFF_CONTRADICTS_SAFE_SCOPE")
        elif proposal["kind"].startswith("ADS_"):
            need(set(campaign_ids).issubset(CURRENT_CAMPAIGNS), "CURRENT_NEW_CAMPAIGN_ALLOWLIST_ONLY")
            if proposal["kind"] == "ADS_ACTIVATION":
                need(set(campaign_ids) == CURRENT_CAMPAIGNS, "FULL_FOUR_CAMPAIGN_LAUNCH_REQUIRED")
            baseline = record_json(change["before_state"])
            after = record_json(change["after_state"])
            before_rows, after_rows = rows(baseline.get("campaigns")), rows(after.get("campaigns"))
            need(baseline.get("account") == ACCOUNT and after.get("account") == ACCOUNT and created <= instant(baseline.get("observed_at_utc")) <= now, "RECENT_REAL_ESTATE_BASELINE_REQUIRED")
            before_map = {r.get("id"): r for r in before_rows}
            after_map = {r.get("id"): r for r in after_rows}
            need(len(before_map) == len(before_rows) and len(after_map) == len(after_rows) and set(before_map) == set(after_map) and CURRENT_CAMPAIGNS.issubset(before_map), "COMPLETE_UNIQUE_BEFORE_AFTER_CAMPAIGNS")
            old_ids = set(before_map) - CURRENT_CAMPAIGNS
            frozen = frozen_legacy_statuses()
            need(all(before_map.get(i, {}).get("status") == status for i, status in frozen.items()),
                 "KNOWN_LEGACY_CAMPAIGN_IDS_AND_STATUSES_REQUIRED")
            need(all(before_map[i].get("status") in {"PAUSED", "REMOVED"} and before_map[i] == after_map.get(i) for i in old_ids), "OLD_CAMPAIGN_BASELINE_MUST_STAY_FROZEN")
            for campaign_id in CURRENT_CAMPAIGNS:
                before, after_row = before_map.get(campaign_id, {}), after_map.get(campaign_id, {})
                need(before.get("status") == "PAUSED", "NEW_CAMPAIGNS_START_PAUSED")
                if campaign_id in campaign_ids:
                    expected_status = "ENABLED" if proposal["kind"] == "ADS_ACTIVATION" else "PAUSED"
                    need(after_row.get("status") == expected_status, "ADS_ACTION_STATUS_MISMATCH")
                    need(set(after_row) == {"id", "status", "average_daily_fils", "final_url", "settings", "max_cpc_fils"}, "TYPED_ADS_AFTER_STATE_REQUIRED")
                    expected_url = next(r["url"] for r in resources if r["campaign_id"] == campaign_id)
                    need(after_row.get("final_url") == expected_url and digest(after_row.get("settings")) == digest(ADS_SAFE_SETTINGS), "ADS_AFTER_STATE_CONTRADICTS_SCOPE")
                    need(type(after_row.get("max_cpc_fils")) is int and after_row["max_cpc_fils"] == (500 if campaign_id == "24378494098" else 2000), "APPROVED_CPC_LIMIT_REQUIRED")
                    if proposal["kind"] == "ADS_ACTIVATION":
                        need(digest({**before, "status": "ENABLED"}) == digest(after_row),
                             "ACTIVATION_MAY_CHANGE_ONLY_CAMPAIGN_STATUS")
                else:
                    need(before == after_row, "OUT_OF_SCOPE_CAMPAIGN_CHANGE")
        rollback = proposal["rollback"]
        need(isinstance(rollback, dict) and set(rollback) == {"before_manifest", "instructions", "preserve_accepted_records", "preserve_outbox", "reactivate_old_campaigns", "reapply_retention_before_reopen", "encrypted_owner_only_backup_days"}, "ROLLBACK_SHAPE")
        recovery = record_json(rollback["before_manifest"])
        file(rollback["instructions"])
        need(recovery.get("commit") == commit and recovery.get("resource_page_ids") == sorted(resource_ids) and recovery.get("target_origin") == ORIGIN and recovery.get("ads_account") == ACCOUNT and recovery.get("resources") == resources and isinstance(recovery.get("previous_versions"), dict) and set(recovery["previous_versions"]) == set(resource_ids) and all(isinstance(v, str) and v.strip() for v in recovery["previous_versions"].values()), "EXACT_SCOPED_ROLLBACK_VERSIONS_REQUIRED")
        need(rollback["preserve_accepted_records"] is True and rollback["preserve_outbox"] is True and rollback["reactivate_old_campaigns"] is False and rollback["reapply_retention_before_reopen"] is True and type(rollback["encrypted_owner_only_backup_days"]) is int and rollback["encrypted_owner_only_backup_days"] == 30, "SCOPED_RECOVERY_INVARIANTS")
        need(proposal["post_release"] == {"readback_required": True, "pause_on_mismatch": True, "preserve_intake": True}, "POST_RELEASE_READBACK_REQUIRED")
        media = proposal["media_limits"]
        if proposal["kind"].startswith("ADS_"):
            need(isinstance(media, dict), "EXPLICIT_MEDIA_AUTHORITY_SCOPE")
            for field in ("aggregate_average_daily_fils", "monthly_media_ceiling_fils", "cash_risk_ceiling_fils"):
                need(type(media.get(field)) is int and media[field] > 0, "EXPLICIT_MEDIA_LIMIT_REQUIRED:" + field)
            need(media.get("accepts_normal_overdelivery") is True and media.get("currency") == "AED" and media.get("timezone") == "Asia/Dubai" and media.get("excluding_vat") is True, "EXPLICIT_BUDGET_SEMANTICS_REQUIRED")
            budgets = rows(media.get("campaign_budgets"), 360)
            need(len(budgets) == len(resources) and {b.get("campaign_id") for b in budgets} == set(campaign_ids) and all(type(b.get("average_daily_fils")) is int and b["average_daily_fils"] > 0 for b in budgets), "EXACT_CAMPAIGN_BUDGET_POOLS_REQUIRED")
            need(sum(b["average_daily_fils"] for b in budgets) == media["aggregate_average_daily_fils"], "AGGREGATE_BUDGET_MISMATCH")
            need(all(after_map.get(b["campaign_id"], {}).get("average_daily_fils") == b["average_daily_fils"] for b in budgets), "BUDGET_DIFF_MISMATCH")
            if proposal["kind"] == "ADS_ACTIVATION":
                need({b["campaign_id"]: b["average_daily_fils"] for b in budgets} == LAUNCH_BUDGET_FILS,
                     "APPROVED_LAUNCH_BUDGET_SPLIT_REQUIRED")
                need(all(type(before_map[i].get("average_daily_fils")) is int and
                         before_map[i]["average_daily_fils"] == amount for i, amount in LAUNCH_BUDGET_FILS.items()),
                     "ACTIVATION_REQUIRES_PRECONFIGURED_LAUNCH_BUDGETS")
            need(media.get("old_campaigns_remain_paused_removed") is True, "OLD_CAMPAIGNS_CANNOT_RESUME")
        else:
            need(media is None, "WEBSITE_OR_TRACKING_CANNOT_AUTHORIZE_SPEND")
        proposal_hash = digest(proposal)
        evidence = rows(packet["evidence"])
        required_gates = GATES | (POSTFLIGHT_GATES if proposal["kind"].startswith("ADS_") else set())
        if proposal["kind"] == "ADS_ACTIVATION":
            required_gates.update({BRAND_POLICY_GATE, SERVING_CHILDREN_GATE})
        need(len(evidence) == len(required_gates) and {x.get("gate_id") for x in evidence} == required_gates, "ALL_REQUIRED_GATES_EXACTLY_ONCE")
        latest_evidence = created
        evidence_expiries = []
        for row in evidence:
            if set(row) != {"gate_id", "file"}:
                raise ValueError("EVIDENCE_REFERENCE_SHAPE")
            result = record_json(row["file"])
            need(isinstance(result, dict), "EVIDENCE_OBJECT_REQUIRED")
            need(result.get("gate_id") == row["gate_id"] and result.get("status") == "PASS", "GATE_NOT_PASS:" + str(row["gate_id"]))
            need(result.get("proposal_sha256") == proposal_hash and result.get("commit") == commit and result.get("resource_page_ids") == sorted(resource_ids), "EVIDENCE_SCOPE_MISMATCH:" + str(row["gate_id"]))
            need(result.get("method") in METHODS and match(LOGIN, result.get("reviewer")), "COMPLETE_ACCEPTANCE_METHOD_REQUIRED:" + str(row["gate_id"]))
            if row["gate_id"] == BRAND_POLICY_GATE and proposal["kind"] == "ADS_ACTIVATION":
                brand_url = next((r["url"] for r in resources if r["campaign_id"] == BRAND_CAMPAIGN_ID), None)
                need(result.get("method") == "AUTHENTICATED_CONFIGURATION_READBACK" and brand_url is not None and
                     result.get("brand_policy") == {"account": ACCOUNT, "campaign_id": BRAND_CAMPAIGN_ID,
                         "ad_group_id": BRAND_AD_GROUP_ID, "ad_id": BRAND_AD_ID,
                         "final_url": brand_url, "policy_status": "APPROVED"},
                     "EXACT_BRAND_AD_POLICY_APPROVAL_REQUIRED")
            if row["gate_id"] == SERVING_CHILDREN_GATE and proposal["kind"] == "ADS_ACTIVATION":
                need(result.get("method") == "AUTHENTICATED_CONFIGURATION_READBACK" and
                     result.get("account") == ACCOUNT and
                     digest(result.get("enabled_reviewed_children")) == digest(LAUNCH_ENABLED_CHILD_COUNTS),
                     "ALL_REVIEWED_LAUNCH_CHILDREN_MUST_ALREADY_BE_ENABLED")
            observed = instant(result.get("observed_at_utc"))
            need(created <= observed <= now, "EVIDENCE_TIME_OUTSIDE_PROPOSAL")
            latest_evidence = max(latest_evidence, observed)
            expiry = instant(result.get("valid_until_utc"))
            need(now < expiry, "EVIDENCE_EXPIRED")
            evidence_expiries.append(expiry)
            need(type(result.get("production_synthetic_conversions")) is int and result["production_synthetic_conversions"] == 0, "NO_SYNTHETIC_GOOGLE_CONVERSIONS")
            if row["gate_id"] == "KEYWORD_SCOPE":
                counts = result.get("counts")
                need(isinstance(counts, dict) and all(type(v) is int for v in counts.values()) and counts == {"unique_reviewed_positive": 14000, "unique_reviewed_negative": 14000, "planned_pairs": 360, "unresolved_protected_conflicts": 0}, "MASTER_COUNTS_OR_REVIEWED_POLICY_CHANGE_REQUIRED")
        review = packet["review"]
        need(isinstance(review, dict) and review.get("commit") == commit and review.get("repository") == REPO and match(LOGIN, review.get("approver")) and review.get("approver", "").lower() != proposal["pusher"].lower() and review.get("state") == "APPROVED", "INDEPENDENT_EXACT_HEAD_REVIEW_REQUIRED")
        reviewed = instant(review.get("reviewed_at_utc"))
        need(created <= reviewed <= now, "REVIEW_TIME_INVALID")
        checks = rows(review.get("checks"), 10)
        need(len(checks) == len(CHECKS) and {c.get("name") for c in checks} == CHECKS and all(c.get("commit") == commit and c.get("conclusion") == "success" for c in checks), "EXACT_HEAD_REQUIRED_CHECKS")
        decisions = rows(packet["decisions"], 7)
        need(len(decisions) == 7 and all(type(d.get("issue")) is int for d in decisions) and {d.get("issue") for d in decisions} == set(range(1, 8)), "OWNER_DECISIONS_UNRESOLVED")
        latest_decision = created
        for decision in decisions:
            need(decision.get("owner") == OWNER and decision.get("state") == "APPROVED" and decision.get("proposal_sha256") == proposal_hash, "OWNER_DECISION_SCOPE_REQUIRED")
            need(isinstance(decision.get("comment_url"), str) and re.fullmatch(r"https://github\.com/" + re.escape(REPO) + r"/issues/" + str(decision.get("issue")) + r"#issuecomment-[1-9]\d*", decision["comment_url"]), "EXACT_OWNER_COMMENT_REFERENCE")
            decision_time = instant(decision.get("decided_at_utc"))
            need(created <= decision_time <= now, "OWNER_DECISION_TIME_INVALID")
            latest_decision = max(latest_decision, decision_time)
        approval = packet["approval"]
        packet_hash = digest({key: value for key, value in packet.items() if key != "approval"})
        need(isinstance(approval, dict) and approval.get("owner") == OWNER and approval.get("kind") == proposal["kind"] and approval.get("packet_sha256") == packet_hash, "SEPARATE_EXACT_PACKET_APPROVAL_REQUIRED")
        need(approval.get("statement") == f"AUTHORIZE {proposal['kind']} {proposal['release_id']} {packet_hash}", "EXACT_ACTION_STATEMENT_REQUIRED")
        start, end, decided = instant(approval.get("valid_from_utc")), instant(approval.get("expires_at_utc")), instant(approval.get("decided_at_utc"))
        need(created <= decided <= start <= now < end, "APPROVAL_WINDOW_INVALID")
        need(all(end <= expiry for expiry in evidence_expiries), "APPROVAL_OUTLIVES_EVIDENCE")
        need(max(latest_evidence, reviewed, latest_decision) <= decided, "APPROVAL_PRECEDES_EVIDENCE_OR_REVIEW")
        need(isinstance(approval.get("comment_url"), str) and re.fullmatch(r"https://github\.com/" + re.escape(REPO) + r"/issues/[1-9]\d*#issuecomment-[1-9]\d*", approval["comment_url"]), "OWNER_RELEASE_COMMENT_REQUIRED")
    except (KeyError, TypeError, ValueError, OSError, AttributeError) as exc:
        errors.append("MALFORMED_OR_UNREADABLE_PACKET:" + type(exc).__name__ + (":" + str(exc) if isinstance(exc, ValueError) else ""))
    return {"schema_version": 1, "phase": "PREFLIGHT_PACKET_REVIEW_ONLY", "packet_consistent": not errors, "errors": sorted(set(errors)),
            "execution_allowed": False, "release_authorized": False,
            "post_publication_readback_required": sorted(POSTFLIGHT_GATES),
            "next_gate": "AUTHENTICATED_OWNER_AND_PLATFORM_VERIFICATION" if not errors else "REPAIR_OR_COMPLETE_RELEASE_EVIDENCE",
            "limitations": "Local JSON, hashes and green tests cannot authenticate an owner approval, provider evidence, current permissions, or live readback. No network or production writer exists."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    try:
        def git(*arguments):
            return subprocess.run(["git", "-C", str(args.root), *arguments], check=True, capture_output=True, text=True, timeout=10).stdout.strip()
        packet = load_json(args.packet)
        head = git("rev-parse", "HEAD")
        source_hashes = {}
        for artifact in packet.get("proposal", {}).get("artifacts", []):
            verify_file(args.root, artifact)
            object_ref = head + ":" + artifact["path"]
            if int(git("cat-file", "-s", object_ref)) > MAX_ARTIFACT_BYTES:
                raise ValueError("COMMITTED_ARTIFACT_TOO_LARGE")
            blob = subprocess.run(["git", "-C", str(args.root), "show", object_ref], check=True, capture_output=True, timeout=10).stdout
            source_hashes[artifact["path"]] = hashlib.sha256(blob).hexdigest()
        result = validate(packet, args.root, checkout_head=head, checkout_clean=not git("status", "--porcelain", "--untracked-files=all"), source_hashes=source_hashes)
    except (OSError, ValueError, TypeError, AttributeError, KeyError, subprocess.SubprocessError):
        result = {"packet_consistent": False, "execution_allowed": False, "release_authorized": False, "errors": ["INPUT_OR_CHECKOUT_UNVERIFIED"]}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["packet_consistent"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

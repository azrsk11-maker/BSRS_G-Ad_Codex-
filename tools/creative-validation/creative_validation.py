"""Offline preparation checks; never authenticates truth, rights or permission."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urlsplit

SCHEMA = "bsre-creative-preparation-v1"
BINDING_FIELDS = {"ad_group_key", "campaign_key", "landing_page_id", "native_page_id",
                  "final_url", "language", "company_scope"}
REVIEW_FIELDS = {"decision", "reviewer_id", "reference", "subject_sha256",
                 "observed_at_utc", "valid_until_utc"}
KINDS = {"SITELINK", "CALLOUT", "IMAGE", "VIDEO", "CALL", "LOCATION", "WHATSAPP"}
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
MAX_GROUPS = 500


class Held(ValueError):
    """Only constant codes may appear in reports."""


def need(condition, code):
    if not condition:
        raise Held(code)


def digest(value):
    """Hash exact JSON values; hashes bind evidence but do not authenticate it."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def nonblank(value):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 4096


def instant(value):
    need(isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value),
         "UTC_TIMESTAMP_REQUIRED")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        raise Held("UTC_TIMESTAMP_REQUIRED") from None


def text_units(text):
    """W/F letters count twice; ambiguous/combining/symbol sequences hold."""
    need(nonblank(text) and text == text.strip(), "INVALID_COPY_TEXT")
    need(not any(token in text for token in ("{", "}", "<", ">", "[[", "]]")),
         "DYNAMIC_OR_TEMPLATE_COPY_UNSUPPORTED")
    total = 0
    for char in text:
        category = unicodedata.category(char)
        width = unicodedata.east_asian_width(char)
        need(not category.startswith(("C", "M")) and category not in {"So", "Sk"}
             and width != "A" and (not char.isspace() or char == " "),
             "AMBIGUOUS_OR_UNSUPPORTED_GLYPH")
        total += 2 if width in {"W", "F"} else 1
    return total


def normalized(text):
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def binding(value):
    need(isinstance(value, dict) and set(value) == BINDING_FIELDS
         and all(nonblank(v) for v in value.values()), "EXACT_NATIVE_BINDING_REQUIRED")
    try:
        need(not any(char.isspace() or unicodedata.category(char).startswith("C")
                     for char in value["final_url"]), "INVALID_NATIVE_DESTINATION")
        url = urlsplit(value["final_url"])
        need(url.scheme == "https" and bool(url.hostname) and url.username is None
             and url.password is None and url.port is None and not url.fragment,
             "INVALID_NATIVE_DESTINATION")
        host = url.hostname.encode("idna").decode("ascii")
        need(all(re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
                 for label in host.split(".")), "INVALID_NATIVE_DESTINATION")
    except ValueError:
        raise Held("INVALID_NATIVE_DESTINATION") from None
    need(re.fullmatch(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*", value["language"]) is not None,
         "INVALID_LANGUAGE_BINDING")
    return value


def claim_subject(group_binding, claim):
    return {"binding": group_binding, "claim": {k: v for k, v in claim.items() if k != "review"}}


def rsa_subject(rsa, claims):
    return {"rsa": {k: v for k, v in rsa.items() if k not in {"copy_review", "combination_review"}},
            "claims": claims}


def combination_subject(rsa, claims):
    return {"coverage": "ALL_MATERIAL_COMBINATIONS", "creative": rsa_subject(rsa, claims)}


def asset_subject(asset, claims):
    return {"asset": {k: v for k, v in asset.items() if k != "review"}, "claims": claims}


def reviewed(receipt, subject, now, reviewers, *, not_before=None):
    need(isinstance(receipt, dict) and set(receipt) == REVIEW_FIELDS, "REVIEW_RECEIPT_REQUIRED")
    need(receipt["decision"] == "PASS" and receipt["reviewer_id"] in reviewers
         and nonblank(receipt["reference"]), "REVIEW_AUTHORITY_OR_DECISION_REQUIRED")
    need(receipt["subject_sha256"] == digest(subject), "REVIEW_SUBJECT_CHANGED")
    observed, expires = instant(receipt["observed_at_utc"]), instant(receipt["valid_until_utc"])
    need(observed <= now < expires and observed < expires, "REVIEW_STALE_OR_FUTURE")
    need(not_before is None or observed >= not_before, "REVIEW_PREDATES_DEPENDENCY")
    return observed


def text_entries(entries, low, high, limit, claim_ids):
    need(isinstance(entries, list) and low <= len(entries) <= high, "COPY_COUNT_OUTSIDE_LIMIT")
    identities, values = set(), set()
    for row in entries:
        need(isinstance(row, dict) and set(row) == {"text_id", "text", "claim_ids"}
             and nonblank(row["text_id"]), "TEXT_ENTRY_SHAPE")
        need(row["text_id"] not in identities, "DUPLICATE_TEXT_ID")
        identities.add(row["text_id"])
        need(text_units(row["text"]) <= limit, "COPY_LENGTH_OUTSIDE_LIMIT")
        key = normalized(row["text"])
        need(key not in values, "DUPLICATE_COPY")
        values.add(key)
        refs = row["claim_ids"]
        need(isinstance(refs, list) and refs and all(isinstance(x, str) for x in refs)
             and len(set(refs)) == len(refs) and set(refs).issubset(claim_ids),
             "COPY_CLAIM_BINDING_REQUIRED")
    return identities, values


def validate_claims(claims, group_binding, now, reviewers):
    need(isinstance(claims, list) and 1 <= len(claims) <= 1000, "CLAIM_REGISTER_REQUIRED")
    identities = set()
    for row in claims:
        need(isinstance(row, dict) and set(row) == {"claim_id", "statement", "source_reference",
             "source_sha256", "review"} and all(nonblank(row[k]) for k in
             ("claim_id", "statement", "source_reference")), "CLAIM_EVIDENCE_REQUIRED")
        need(isinstance(row["source_sha256"], str) and SHA256.fullmatch(row["source_sha256"]),
             "CLAIM_SOURCE_HASH_REQUIRED")
        need(row["claim_id"] not in identities, "DUPLICATE_CLAIM_ID")
        identities.add(row["claim_id"])
        reviewed(row["review"], claim_subject(group_binding, row), now, reviewers)
    return identities


def validate_rsa(row, group_binding, claims, claim_ids, now, reviewers):
    fields = {"rsa_id", "role", "binding", "headlines", "descriptions", "path1", "path2",
              "experiment", "copy_review", "combination_review"}
    need(isinstance(row, dict) and set(row) == fields and nonblank(row["rsa_id"]), "RSA_SHAPE")
    need(row["binding"] == group_binding, "RSA_NATIVE_BINDING_MISMATCH")
    need(row["role"] in {"CONTROL", "CHALLENGER"}, "RSA_ROLE_REQUIRED")
    h_ids, headlines = text_entries(row["headlines"], 3, 15, 30, claim_ids)
    d_ids, descriptions = text_entries(row["descriptions"], 2, 4, 90, claim_ids)
    need(not h_ids.intersection(d_ids), "DUPLICATE_TEXT_ID")
    for field in ("path1", "path2"):
        need(isinstance(row[field], str), "DISPLAY_PATH_SHAPE")
        if row[field]:
            need(text_units(row[field]) <= 15 and not any(c in row[field] for c in "/?#"),
                 "DISPLAY_PATH_OUTSIDE_LIMIT")
    need(not row["path2"] or bool(row["path1"]), "SECOND_PATH_REQUIRES_FIRST")
    if row["role"] == "CONTROL":
        need(row["experiment"] is None, "CONTROL_EXPERIMENT_MUST_BE_NULL")
    else:
        experiment = row["experiment"]
        need(isinstance(experiment, dict) and set(experiment) == {"reference", "hypothesis", "distinct_decision"}
             and all(nonblank(v) for v in experiment.values()), "DOCUMENTED_CHALLENGER_REQUIRED")
    # Subjects include the complete reviewed claim register, not only labels.
    claims_observed = max(instant(claim["review"]["observed_at_utc"]) for claim in claims)
    copy_observed = reviewed(row["copy_review"], rsa_subject(row, claims), now, reviewers,
                             not_before=claims_observed)
    reviewed(row["combination_review"], combination_subject(row, claims), now, reviewers,
             not_before=max(claims_observed, copy_observed))
    return (headlines, descriptions)


def validate_asset(row, expected, group_binding, claims, claim_ids, now, reviewers):
    fields = {"asset_id", "kind", "binding", "destination", "texts", "source_reference",
              "source_sha256", "rights_reference", "review"}
    need(isinstance(row, dict) and set(row) == fields, "ASSET_SHAPE")
    need(row["kind"] in KINDS and row["binding"] == group_binding, "ASSET_SCOPE_MISMATCH")
    identity = {key: row[key] for key in ("asset_id", "kind", "binding", "destination")}
    need(identity == expected, "ASSET_DESTINATION_OR_INVENTORY_MISMATCH")
    need(nonblank(row["source_reference"]) and nonblank(row["rights_reference"])
         and isinstance(row["source_sha256"], str) and SHA256.fullmatch(row["source_sha256"]),
         "ASSET_SOURCE_AND_RIGHTS_REFERENCE_REQUIRED")
    need(isinstance(row["texts"], list) and len(row["texts"]) <= 20, "ASSET_TEXT_SHAPE")
    # Other formats have separate platform limits; the receipt must cover them.
    if row["texts"]:
        text_entries(row["texts"], 1, 20, 4096, claim_ids)
    need(row["kind"] not in {"SITELINK", "CALLOUT"} or row["texts"], "TEXT_ASSET_COPY_REQUIRED")
    claims_observed = max(instant(claim["review"]["observed_at_utc"]) for claim in claims)
    reviewed(row["review"], asset_subject(row, claims), now, reviewers, not_before=claims_observed)


def evaluate_creatives(package, expected_groups, *, as_of, expected_commit,
                       authorized_reviewers, expected_assets=()):
    """Evaluate supplied candidate library against independent caller inventories.

    Returned diagnostics contain only constant codes, indexes and counts. PASS
    means structural preparation evidence consistency, never factual approval.
    """
    report = {"schema": SCHEMA, "scope": "PREPARATION_ONLY", "status": "HOLD", "errors": [],
              "counts": {"groups": 0, "rsas": 0, "assets": 0}, "source_truth_verified": False,
              "rights_verified": False, "permission_granted": False, "execution_authorized": False,
              "serving_inventory_verified": False, "production_ready": False}
    group_index = None
    try:
        now = instant(as_of)
        need(isinstance(expected_commit, str) and COMMIT.fullmatch(expected_commit), "EXPECTED_COMMIT_REQUIRED")
        need(isinstance(authorized_reviewers, (list, tuple, set)) and authorized_reviewers
             and all(nonblank(v) for v in authorized_reviewers), "INDEPENDENT_REVIEWER_ALLOWLIST_REQUIRED")
        reviewers = set(authorized_reviewers)
        need(isinstance(package, dict) and set(package) == {"schema", "reviewed_commit", "fixture_only", "groups"}
             and package["schema"] == SCHEMA and type(package["fixture_only"]) is bool, "PACKAGE_SHAPE")
        need(package["reviewed_commit"] == expected_commit, "REVIEWED_COMMIT_MISMATCH")
        need(isinstance(expected_groups, (list, tuple)) and 1 <= len(expected_groups) <= MAX_GROUPS,
             "INDEPENDENT_GROUP_INVENTORY_REQUIRED")
        expected = {}
        for row in expected_groups:
            binding(row)
            need(row["ad_group_key"] not in expected, "DUPLICATE_EXPECTED_GROUP")
            expected[row["ad_group_key"]] = row
        need(isinstance(expected_assets, (list, tuple)) and len(expected_assets) <= 10000,
             "INDEPENDENT_ASSET_INVENTORY_REQUIRED")
        asset_inventory = {}
        for row in expected_assets:
            need(isinstance(row, dict) and set(row) == {"asset_id", "kind", "binding", "destination"}
                 and nonblank(row["asset_id"]) and row["kind"] in KINDS, "EXPECTED_ASSET_SHAPE")
            b = binding(row["binding"])
            need(b == expected.get(b["ad_group_key"]), "EXPECTED_ASSET_SCOPE_MISMATCH")
            need(row["asset_id"] not in asset_inventory, "DUPLICATE_EXPECTED_ASSET")
            need(row["destination"] is None or nonblank(row["destination"]), "EXPECTED_ASSET_DESTINATION_SHAPE")
            asset_inventory[row["asset_id"]] = row
        groups = package["groups"]
        need(isinstance(groups, list) and len(groups) == len(expected), "COMPLETE_GROUP_LIBRARY_REQUIRED")
        seen_groups, seen_rsas, seen_assets = set(), set(), set()
        for group_index, group in enumerate(groups):
            need(isinstance(group, dict) and set(group) == {"binding", "claims", "rsas", "assets"}, "GROUP_SHAPE")
            b = binding(group["binding"])
            need(b == expected.get(b["ad_group_key"]), "GROUP_NATIVE_BINDING_MISMATCH")
            need(b["ad_group_key"] not in seen_groups, "DUPLICATE_GROUP")
            seen_groups.add(b["ad_group_key"])
            claim_ids = validate_claims(group["claims"], b, now, reviewers)
            rsas = group["rsas"]
            need(isinstance(rsas, list) and len(rsas) == 2, "CONTROL_AND_CHALLENGER_REQUIRED")
            roles, signatures = set(), []
            for row in rsas:
                signature = validate_rsa(row, b, group["claims"], claim_ids, now, reviewers)
                need(row["role"] not in roles and row["rsa_id"] not in seen_rsas, "DUPLICATE_RSA_ROLE_OR_ID")
                roles.add(row["role"]); seen_rsas.add(row["rsa_id"]); signatures.append(signature)
            need(roles == {"CONTROL", "CHALLENGER"} and signatures[0] != signatures[1],
                 "DISTINCT_DOCUMENTED_CHALLENGER_REQUIRED")
            assets = group["assets"]
            need(isinstance(assets, list) and len(assets) <= 10000, "ASSET_LIBRARY_SHAPE")
            asset_content = set()
            for row in assets:
                need(isinstance(row, dict) and nonblank(row.get("asset_id")), "ASSET_SHAPE")
                key = row["asset_id"]
                need(key not in seen_assets, "DUPLICATE_ASSET_ID")
                validate_asset(row, asset_inventory.get(key), b, group["claims"], claim_ids, now, reviewers)
                copy_values = tuple(sorted(normalized(entry["text"]) for entry in row["texts"]))
                content = (row["kind"], copy_values or row["source_sha256"])
                need(content not in asset_content, "DUPLICATE_ASSET_CONTENT")
                asset_content.add(content)
                seen_assets.add(key)
            report["counts"] = {"groups": len(seen_groups), "rsas": len(seen_rsas), "assets": len(seen_assets)}
        need(seen_groups == set(expected) and seen_assets == set(asset_inventory), "COMPLETE_CREATIVE_INVENTORY_REQUIRED")
        report["status"] = "PASS"
    except Held as error:
        report["errors"].append({"code": str(error), "group_index": group_index})
    except (TypeError, ValueError, KeyError, OverflowError, RecursionError, UnicodeError):
        report["errors"].append({"code": "MALFORMED_INPUT", "group_index": group_index})
    return report

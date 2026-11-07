"""Offline research ingestion and fail-closed keyword/scope validation.

No network, Ads API, production writes, or platform-upload exporter is present.
Counts are reviewed library rows, never evidence of volume or platform approval.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import unicodedata

TARGET = 14000
REAL_ESTATE_CUSTOMER_ID = "5730384686"
MATCH_TYPES = {"EXACT", "PHRASE", "BROAD"}
STATES = {"CANDIDATE", "REVIEWED", "HELD", "REJECTED"}
SOURCE_KINDS = {"first_party_observed", "authorized_partner_observed", "official_reference", "research_hypothesis"}
SERVICES = {"residential_offplan", "residential_ready_secondary", "residential_rental", "commercial_offplan",
            "commercial_ready", "commercial_leasing", "seller_supply", "landlord_supply"}
PROTECTED_TOKENS = set("rent rental lease cheap affordable free mortgage salary vacancy guide reviews complaint floorplan brochure yield roi commercial office school india uk dubai sharjah ajman fujairah".split())
PROTECTED_PHRASES = {"payment plan", "floor plan", "service charges", "abu dhabi", "ras al khaimah", "umm al quwain"}
LIST_FIELDS = {"eligible_campaigns", "ineligible_campaigns", "service_applicability", "protected_query_conflicts", "deployed_resource_ids"}
JSON_FIELDS = LIST_FIELDS | {"scope_target", "metric_evidence"}
NULL_FIELDS = {"volume", "cpc", "observation_date", "observed_query", "estimated_lost_coverage", "deployed_at", "rollback_reference"}


def duplicate_safe_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key: " + key)
        result[key] = value
    return result


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=duplicate_safe_object,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Invalid number " + value)))


def normalize(text: str) -> str:
    if not isinstance(text, str):
        raise ValueError("Keyword text must be a string")
    value = unicodedata.normalize("NFKC", text).strip()
    # Strip one valid matching wrapper. Nested/mismatched wrappers are rejected later.
    if len(value) >= 2 and ((value[0], value[-1]) in {("[", "]"), ('"', '"')}):
        value = value[1:-1].strip()
    return " ".join(value.casefold().split())


def tokens(text):
    # Conservative lexical approximation, not Google's matching/close-variant engine.
    return re.findall(r"\w+", normalize(text), flags=re.UNICODE)


def negative_matches(text, match_type, query):
    negative, actual = tokens(text), tokens(query)
    if not negative or not actual:
        return False
    if match_type == "EXACT":
        return negative == actual
    if match_type == "PHRASE":
        return any(actual[i:i + len(negative)] == negative for i in range(len(actual) - len(negative) + 1))
    if match_type == "BROAD":
        return set(negative) <= set(actual)
    raise ValueError("Unsupported negative match type")


def read_records(path: Path):
    if path.suffix.lower() == ".json":
        result = load_json(path)
        if not isinstance(result, list):
            raise ValueError("JSON input must be an array of record objects")
    elif path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = reader.fieldnames or []
            if len(set(fields)) != len(fields):
                raise ValueError("Duplicate CSV header")
            result = []
            for record in reader:
                if None in record or any(value is None for value in record.values()):
                    raise ValueError("CSV row has mismatched column count")
                for key in JSON_FIELDS & record.keys():
                    record[key] = json.loads(record[key] or ("[]" if key in LIST_FIELDS else "{}"), object_pairs_hook=duplicate_safe_object)
                for key in NULL_FIELDS & record.keys():
                    if record[key] == "":
                        record[key] = None
                for key in {"volume", "cpc"} & record.keys():
                    if record[key] is not None:
                        record[key] = float(record[key])
                result.append(record)
    else:
        raise ValueError("Only JSON and CSV inputs are supported")
    if not all(isinstance(row, dict) for row in result):
        raise ValueError("Every input row must be an object")
    return result


def iso_day(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("Expected YYYY-MM-DD")
    return date.fromisoformat(value)


def nonblank(value):
    return isinstance(value, str) and bool(value.strip())


def customer_id(value):
    return value.replace("-", "") if isinstance(value, str) and re.fullmatch(r"(?:\d{10}|\d{3}-\d{3}-\d{4})", value) else None


def proposed_capacity(records):
    """Planning lower bounds, not a live remaining-capacity certificate.

Official Google limits accessed 2026-11-07: account list 1000, shared list
5000, 20 shared lists per account, 10000 negative keywords per campaign.
Existing/inherited resources and platform counting must be verified separately.
"""
    account_count, lists, campaign_direct = 0, Counter(), Counter()
    for row in records:
        scope, target = row.get("scope_type"), row.get("scope_target", {})
        if scope == "ACCOUNT":
            account_count += 1
        elif scope == "SHARED_LIST":
            lists[target.get("list_key")] += 1
        elif scope == "CAMPAIGN":
            campaign_direct[target.get("campaign_key")] += 1
    violations = []
    if account_count > 1000:
        violations.append({"scope": "ACCOUNT", "count": account_count, "limit": 1000})
    if len(lists) > 20:
        violations.append({"scope": "SHARED_LIST_COUNT", "count": len(lists), "limit": 20})
    for scope, counts, limit in [("SHARED_LIST", lists, 5000), ("CAMPAIGN_DIRECT_LOWER_BOUND", campaign_direct, 10000)]:
        for target, count in counts.items():
            if count > limit:
                violations.append({"scope": scope, "target": target, "count": count, "limit": limit})
    return {"source_checked_on": "2026-11-07", "account_proposed": account_count,
            "shared_lists_proposed": dict(lists), "campaign_direct_proposed": dict(campaign_direct),
            "known_overflows": violations, "known_overflow_pass": not violations,
            "live_remaining_capacity_verified": False,
            "limitation": "No existing/inherited inventory or platform combination accounting verified; no separate ad-group negative cap invented"}


def unique_index(rows, field, errors, label):
    result = {}
    for row in rows:
        if not isinstance(row, dict) or not nonblank(row.get(field)):
            errors.append(label + ": missing " + field)
        elif row[field] in result:
            errors.append(label + ": duplicate " + field + " " + row[field])
        else:
            result[row[field]] = row
    return result


def fresh(record, at, errors, label, start="observed_on", end="valid_until"):
    try:
        begin, expiry = iso_day(record.get(start)), iso_day(record.get(end))
        if begin > at or expiry < at or expiry < begin:
            errors.append(label + ": future, stale or reversed evidence dates")
    except (ValueError, TypeError):
        errors.append(label + ": missing/invalid evidence dates")


def audit(kind, records, sources, campaigns, campaign_context, protected_queries, at, scope_bindings=None):
    if kind not in {"positive", "negative"}:
        raise ValueError("kind must be positive or negative")
    if not isinstance(at, date):
        raise ValueError("audit date required")
    for label, items in [("records", records), ("sources", sources), ("campaigns", campaigns),
                         ("campaign context", campaign_context), ("protected queries", protected_queries)]:
        if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
            raise ValueError(label + " must be an array of objects")
    # Fail closed before any matching when structural types could obscure scope.
    for row in records:
        for key in ["keyword_id", "source_id", "primary_campaign_key", "negative_id", "scope_type"]:
            if key in row and row[key] is not None and not isinstance(row[key], str):
                raise ValueError(key + " must be a string")
    for query in protected_queries:
        for key in ["campaign_keys", "services"]:
            value = query.get(key)
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                raise ValueError("protected query " + key + " must be a string list")
    for context in campaign_context:
        if not isinstance(context.get("services"), list) or not all(isinstance(item, str) for item in context["services"]):
            raise ValueError("campaign context services must be a string list")
    global_errors = []
    source_index = unique_index(sources, "source_id", global_errors, "sources")
    campaign_index = unique_index(campaigns, "campaign_key", global_errors, "campaigns")
    context_index = unique_index(campaign_context, "campaign_key", global_errors, "campaign context")
    for key, row in campaign_index.items():
        if not nonblank(row.get("landing_page_id")):
            global_errors.append("campaigns: missing page identity " + key)
    pages = [row.get("landing_page_id") for row in campaign_index.values()]
    if len(set(pages)) != len(pages):
        global_errors.append("campaigns: designated page identities are not unique")

    query_index = unique_index(protected_queries, "query_id", global_errors, "protected queries")
    postings = defaultdict(set)
    coverage_by_campaign = defaultdict(set)
    lexical_comparisons = 0
    for key, query in query_index.items():
        if not nonblank(query.get("text")) or query.get("must_serve") is not True:
            global_errors.append("protected queries: text and must_serve=true required " + key)
        if not nonblank(query.get("evidence_ref")):
            global_errors.append("protected queries: evidence reference required " + key)
        fresh(query, at, global_errors, "protected query " + key, "reviewed_on")
        eligible = query.get("campaign_keys")
        if not isinstance(eligible, list) or not eligible or not set(eligible) <= set(campaign_index):
            global_errors.append("protected queries: known nonempty campaign coverage required " + key)
        services = query.get("services")
        if not isinstance(services, list) or not services or not set(services) <= SERVICES:
            global_errors.append("protected queries: known services required " + key)
        for token in tokens(query.get("text", "")):
            postings[token].add(key)
        for campaign_key in query.get("campaign_keys", []):
            coverage_by_campaign[campaign_key].update(query.get("services", []))

    bindings = scope_bindings if isinstance(scope_bindings, dict) else {}
    binding_errors = []
    bound_account = customer_id(bindings.get("account_id"))
    if bound_account != REAL_ESTATE_CUSTOMER_ID or not nonblank(bindings.get("evidence_ref")):
        binding_errors.append("verified Real Estate account scope binding missing")
    fresh(bindings, at, binding_errors, "scope bindings", "verified_on")

    duplicates = defaultdict(list)
    ids = Counter(row.get("keyword_id") for row in records if isinstance(row.get("keyword_id"), str))
    prepared = []
    for i, row in enumerate(records):
        try:
            normalized = normalize(row.get("original_text"))
        except ValueError:
            normalized = ""
        if normalized:
            duplicates[normalized].append(i)
        prepared.append(normalized)

    results, matrix, accepted = [], [], []
    required = {"keyword_id", "original_text", "language", "match_type", "source_id", "source_reference", "evidence_ref",
                "review_state", "reviewer", "reviewed_on", "valid_until", "volume", "cpc"}
    negative_required = {"negative_id", "normalized_text", "source_type", "observed_query", "observation_date", "reason_code",
                         "service_applicability", "eligible_campaigns", "ineligible_campaigns", "scope_type", "scope_target", "risk_level",
                         "protected_query_conflicts", "estimated_lost_coverage", "approval_state", "approval_reference", "approval_reviewer", "approved_on",
                         "deployed_resource_ids", "deployed_at", "rollback_reference"}
    for number, (row, norm) in enumerate(zip(records, prepared), 1):
        errors, warnings, deployment_holds = [], [], []
        missing = (required | (negative_required if kind == "negative" else {"primary_campaign_key", "ad_group_key", "landing_page_id"})) - set(row)
        if missing:
            errors.append("missing fields: " + ",".join(sorted(missing)))
        if not nonblank(row.get("keyword_id")) or ids[row.get("keyword_id")] != 1:
            errors.append("missing/duplicate keyword_id")
        if not norm or re.search(r"[\[\]\"]", norm) or norm in {"source_required", "tbd", "todo", "placeholder", "unknown"} or any(unicodedata.category(ch) in {"Cc", "Cf"} for ch in norm):
            errors.append("blank, placeholder or invalid match wrapper")
        if len(duplicates.get(norm, [])) > 1:
            errors.append("duplicate normalized phrase; wrappers and language do not create uniqueness")
        match = row.get("match_type")
        if match not in MATCH_TYPES:
            errors.append("unsupported match type")
        original = row.get("original_text", "")
        if isinstance(original, str):
            stripped = unicodedata.normalize("NFKC", original).strip()
            if stripped.startswith("[") and match != "EXACT" or stripped.startswith('"') and match != "PHRASE":
                errors.append("match wrapper conflicts with match_type")
        if not nonblank(row.get("language")) or row.get("review_state") not in STATES:
            errors.append("language and valid review_state required")
        if row.get("review_state") != "REVIEWED":
            errors.append("not reviewed; retained but excluded from reviewed count")
        for field in ["reviewer", "source_reference", "evidence_ref"]:
            if not nonblank(row.get(field)):
                errors.append("missing " + field)
        fresh(row, at, errors, "row", "reviewed_on")
        source = source_index.get(row.get("source_id"))
        if not source:
            errors.append("unknown source_id")
        else:
            if source.get("kind") not in SOURCE_KINDS or source.get("approved_for_research") is not True or not nonblank(source.get("evidence_ref")):
                errors.append("source kind, research approval and evidence required")
            fresh(source, at, errors, "source")
            if source.get("kind") == "research_hypothesis":
                warnings.append("hypothesis, not observed demand or measured volume")
        for metric in ("volume", "cpc"):
            value = row.get(metric)
            if value is not None:
                if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0 or value != value or value == float("inf"):
                    errors.append(metric + " must be null or a finite nonnegative number")
                evidence = row.get("metric_evidence", {}).get(metric, {}) if isinstance(row.get("metric_evidence", {}), dict) else {}
                if not nonblank(evidence.get("reference")) or not nonblank(evidence.get("provider")):
                    errors.append(metric + " lacks measured source evidence")
                fresh(evidence, at, errors, metric)

        if kind == "positive":
            campaign = campaign_index.get(row.get("primary_campaign_key"))
            if campaign is None or campaign.get("landing_page_id") != row.get("landing_page_id"):
                errors.append("unknown primary campaign or page ownership mismatch")
            if not nonblank(row.get("ad_group_key")):
                errors.append("ad_group_key required")
            if match == "BROAD":
                warnings.append("broad match research only; a separate approved experiment is required for deployment")
                deployment_holds.append("broad match requires separate experiment approval")
        else:
            if row.get("negative_id") != row.get("keyword_id"):
                errors.append("negative_id must equal immutable keyword_id")
            if row.get("normalized_text") != norm:
                errors.append("normalized_text does not match canonical normalization")
            if source and row.get("source_type") != source.get("kind"):
                errors.append("source_type differs from source registry")
            if not nonblank(row.get("reason_code")) or row.get("reason_code") in {"TIMEWASTER", "NO_CONVERSION"}:
                errors.append("auditable incompatibility reason required")
            if source and source.get("kind") in {"first_party_observed", "authorized_partner_observed"}:
                if not nonblank(row.get("observed_query")):
                    errors.append("observed source lacks actual query")
                try:
                    if iso_day(row.get("observation_date")) > at:
                        errors.append("observed query is future dated")
                except (ValueError, TypeError):
                    errors.append("observed query date invalid")
            eligible, ineligible = row.get("eligible_campaigns"), row.get("ineligible_campaigns")
            if not isinstance(eligible, list) or not eligible or any(not isinstance(x, str) for x in eligible):
                errors.append("eligible_campaigns must be nonempty string list")
                eligible = []
            if not isinstance(ineligible, list) or any(not isinstance(x, str) for x in ineligible):
                errors.append("ineligible_campaigns must be string list")
                ineligible = []
            if len(set(eligible)) != len(eligible) or len(set(ineligible)) != len(ineligible):
                errors.append("scope lists contain duplicates")
            if (set(eligible) | set(ineligible)) - set(campaign_index) or set(eligible) & set(ineligible):
                errors.append("unknown or overlapping eligible/ineligible campaign scope")
            services = row.get("service_applicability")
            if not isinstance(services, list) or not services or any(not isinstance(x, str) for x in services) or not set(services) <= SERVICES:
                errors.append("nonempty known service applicability required")
                services = []
            scope, target = row.get("scope_type"), row.get("scope_target")
            if scope not in {"ACCOUNT", "SHARED_LIST", "CAMPAIGN", "AD_GROUP"} or not isinstance(target, dict):
                errors.append("explicit supported scope/target required")
                target = {}
            if scope == "ACCOUNT" and (set(eligible) != set(campaign_index) or ineligible or not nonblank(target.get("account_id"))):
                errors.append("account scope must explicitly cover every registered campaign without exceptions")
            if scope in {"CAMPAIGN", "AD_GROUP"} and (eligible != [target.get("campaign_key")]):
                errors.append("campaign/adgroup target must match single eligible campaign")
            if scope == "AD_GROUP" and not nonblank(target.get("ad_group_key")):
                errors.append("adgroup scope requires explicit ad_group_key")
            if scope == "SHARED_LIST" and not nonblank(target.get("list_key")):
                errors.append("shared scope requires list_key")
            for key in eligible:
                context = context_index.get(key, {})
                if not nonblank(context.get("evidence_ref")) or not isinstance(context.get("services"), list) or not context.get("services") or not set(context.get("services", [])) <= set(services):
                    errors.append("service compatibility missing/incompatible for " + key)
                fresh(context, at, errors, "campaign context " + key, "reviewed_on")
                coverage = coverage_by_campaign[key]
                if not context.get("services") or not set(context.get("services", [])) <= coverage:
                    errors.append("protected-intent coverage missing for " + key)
            high_risk = bool(set(tokens(norm)) & PROTECTED_TOKENS) or any(phrase in norm for phrase in PROTECTED_PHRASES)
            if row.get("risk_level") not in {"LOW", "MEDIUM", "HIGH"} or high_risk and row.get("risk_level") != "HIGH":
                errors.append("risk level invalid or protected token requires HIGH review")
            if row.get("approval_state") not in {"PENDING", "APPROVED", "REJECTED"}:
                errors.append("unknown exclusion approval state")
            if row.get("approval_state") != "APPROVED" or not nonblank(row.get("approval_reference")):
                deployment_holds.append("exclusion approval missing; fail closed")
            if not nonblank(row.get("approval_reviewer")) or str(row.get("approval_reviewer", "")).strip().casefold() == str(row.get("reviewer", "")).strip().casefold():
                deployment_holds.append("independent exclusion approver required")
            fresh(row, at, deployment_holds, "exclusion approval", "approved_on")
            deployment_holds.extend(binding_errors)
            bound_campaigns = bindings.get("campaigns", {})
            if not isinstance(bound_campaigns, dict):
                bound_campaigns = {}
            for key in eligible:
                binding = bound_campaigns.get(key, {})
                if not isinstance(binding, dict) or not re.fullmatch(r"\d+", str(binding.get("google_campaign_id", ""))) or not nonblank(binding.get("evidence_ref")):
                    deployment_holds.append("verified platform campaign binding missing for " + key)
            if scope == "ACCOUNT" and customer_id(target.get("account_id")) != REAL_ESTATE_CUSTOMER_ID:
                deployment_holds.append("account target is not the verified Real Estate customer")
            if scope == "AD_GROUP":
                binding = bound_campaigns.get(target.get("campaign_key"), {})
                groups = binding.get("ad_groups", {}) if isinstance(binding, dict) else {}
                group = groups.get(target.get("ad_group_key"), {}) if isinstance(groups, dict) else {}
                if not isinstance(group, dict) or not re.fullmatch(r"\d+", str(group.get("google_ad_group_id", ""))) or not nonblank(group.get("evidence_ref")):
                    deployment_holds.append("ad-group ownership/platform binding unverified")
            if scope == "SHARED_LIST":
                lists = bindings.get("shared_lists", {})
                shared = lists.get(target.get("list_key"), {}) if isinstance(lists, dict) else {}
                associated = shared.get("campaign_keys", []) if isinstance(shared, dict) else []
                if not isinstance(shared, dict) or not re.fullmatch(r"\d+", str(shared.get("google_shared_list_id", ""))) or not nonblank(shared.get("evidence_ref")) or not isinstance(associated, list) or any(not isinstance(x, str) for x in associated) or set(associated) != set(eligible):
                    deployment_holds.append("shared-list ownership/complete association binding unverified")
            conflicts = []
            if match in MATCH_TYPES and norm:
                candidate_sets = [postings.get(token, set()) for token in set(tokens(norm))]
                possible = set.intersection(*candidate_sets) if candidate_sets else set()
                for key in sorted(possible):
                    query = query_index[key]
                    affected = sorted(set(eligible) & set(query.get("campaign_keys", [])))
                    if affected:
                        lexical_comparisons += 1
                    if affected and negative_matches(norm, match, query["text"]):
                        conflicts.append(key)
                        matrix.append({"negative_id": row.get("keyword_id"), "protected_query_id": key,
                                       "affected_campaign_keys": affected, "result": "CONFLICT_HOLD"})
            if conflicts:
                errors.append("protected query conflict; cannot deploy: " + ",".join(conflicts))
            if row.get("protected_query_conflicts") != conflicts:
                errors.append("declared conflicts differ from computed result")
            if row.get("deployed_resource_ids") != [] or row.get("deployed_at") is not None:
                errors.append("research input must not claim deployment; reconcile live state in separate register")
        valid = not errors and not global_errors
        results.append({"row": number, "keyword_id": row.get("keyword_id"), "normalized_text": norm,
                        "reviewed_eligible": valid, "exclusion_approved": kind == "negative" and valid and not deployment_holds,
                        "errors": errors, "warnings": warnings, "deployment_holds": deployment_holds})
        if valid:
            accepted.append(row)
    reviewed = len(accepted)
    return {
        "schema_version": "1.0", "kind": kind, "as_of": at.isoformat(), "scope": "OFFLINE_RESEARCH_ONLY",
        "input_rows": len(records), "distinct_nonblank_phrases": len(duplicates),
        "reviewed_eligible_rows": reviewed, "excluded_rows": len(records) - reviewed,
        "approved_exclusion_rows": sum(row["exclusion_approved"] for row in results) if kind == "negative" else None,
        "target": TARGET, "deficit": max(0, TARGET - reviewed), "excess": max(0, reviewed - TARGET),
        "exact_target_pass": reviewed == TARGET and not global_errors,
        "structural_pass": not global_errors and all(not row["errors"] for row in results),
        "deployment_export_allowed": False, "production_writes_available": False,
        "positive_library_coverage_verified": False,
        "protected_corpus_status": "PARTIAL_DECLARED_CORPUS_NOT_EXHAUSTIVE_OR_POSITIVE_MASTER_RECONCILED",
        "protected_queries_indexed": len(query_index), "lexical_comparisons_executed": lexical_comparisons,
        "global_errors": global_errors, "records": results, "protected_conflicts": matrix,
        "capacity": proposed_capacity(accepted) if kind == "negative" else None,
        "matching_limit": "Conservative lexical simulator; not Google close-variant/platform acceptance or proof corpus is complete",
    }


def release_gate(positive, negative, approval):
    """Readiness diagnostics only. Never interprets a fabricated approval as authority."""
    required = {"ads_settings_change", "budget", "page_publication", "live_tracking"}
    reasons = []
    for kind, report in [("positive", positive), ("negative", negative)]:
        if report.get("kind") != kind or report.get("reviewed_eligible_rows") != TARGET or report.get("exact_target_pass") is not True or report.get("structural_pass") is not True:
            reasons.append(kind + " reviewed exact-count/structure gate not passed")
    if negative.get("approved_exclusion_rows") != TARGET:
        reasons.append("negative exclusion approvals incomplete")
    if negative.get("positive_library_coverage_verified") is not True:
        reasons.append("complete positive-library/protected long-tail coverage not independently reconciled")
    if negative.get("capacity", {}).get("live_remaining_capacity_verified") is not True:
        reasons.append("native resource limits and existing/inherited remaining capacity not verified")
    decisions = approval.get("decisions", {}) if isinstance(approval, dict) else {}
    for key in sorted(required):
        decision = decisions.get(key, {})
        if decision.get("approved") is not True or not nonblank(decision.get("owner_decision_reference")):
            reasons.append(key + " separate approval missing")
    reasons.append("No runtime deployment/export capability implemented; use a separately reviewed release manifest and authorized executor")
    return {"deployment_export_allowed": False, "reasons": reasons}


def ensure_output_is_not_input(output, inputs):
    for path in inputs:
        if output.resolve() == path.resolve() or output.exists() and path.exists() and output.samefile(path):
            raise ValueError("Output cannot overwrite an input or its filesystem alias")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=["positive", "negative"], required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--campaigns", type=Path, required=True)
    parser.add_argument("--campaign-context", type=Path, required=True)
    parser.add_argument("--protected", type=Path, required=True)
    parser.add_argument("--as-of", type=iso_day, required=True)
    parser.add_argument("--scope-bindings", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    inputs = [args.input, args.sources, args.campaigns, args.campaign_context, args.protected]
    if args.scope_bindings:
        inputs.append(args.scope_bindings)
    try:
        ensure_output_is_not_input(args.output, inputs)
    except ValueError as error:
        parser.error(str(error))
    report = audit(args.kind, read_records(args.input), load_json(args.sources), load_json(args.campaigns),
                   load_json(args.campaign_context), load_json(args.protected), args.as_of,
                   load_json(args.scope_bindings) if args.scope_bindings else None)
    roles = ["records", "sources", "campaigns", "campaign_context", "protected_queries"] + (["scope_bindings"] if args.scope_bindings else [])
    report["input_sha256"] = {role: {"filename": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for role, p in zip(roles, inputs)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in {"records", "input_sha256", "protected_conflicts"}}, indent=2))
    return 0 if report["structural_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

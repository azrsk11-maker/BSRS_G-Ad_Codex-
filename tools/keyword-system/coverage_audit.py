"""Exact supplied-dataset coverage, never universal Google matching or approval.

The review document binds canonical JSON values (including row order), not file
formatting. The CLI separately records raw input-file SHA256. Review references
must still be authenticated by the owner; hashes cannot authenticate a reviewer.
"""
from collections import Counter, defaultdict
import hashlib
import json
import re
import unicodedata

import keyword_audit as ka

MATCHER_VERSION = "BSRE_LEXICAL_V1"
CLAIM = "COMPLETE_SUPPLIED_LIBRARY_AND_REVIEWED_CORPUS_ONLY"
BINDING_ROLES = ("positive_library", "negative_library", "sources", "campaigns",
                 "campaign_context", "protected_queries", "scope_bindings")


def canonical_sha256(value):
    """Stable object-key ordering; array order and every field are significant."""
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def string_list(value, nonempty=True):
    return (isinstance(value, list) and (bool(value) or not nonempty)
            and all(ka.nonblank(item) for item in value) and len(set(value)) == len(value))


def simulate_scoped(negatives, cases):
    """Evaluate all applicable cases using token AND + campaign postings.

    Namespaced identities are retained, so a positive ID equal to a query ID
    cannot overwrite evidence. AD_GROUP intentionally tests its whole campaign;
    this conservative overhold needs review, never an automatic bypass.
    """
    postings, scopes = defaultdict(set), defaultdict(set)
    for number, case in enumerate(cases):
        for token in set(ka.tokens(case["text"])):
            postings[token].add(number)
        for key in case["campaign_keys"]:
            scopes[key].add(number)
    scope_cache, conflicts = {}, []
    comparisons = applicable_pairs = 0
    for number, row in enumerate(negatives, 1):
        eligible = row.get("eligible_campaigns", [])
        if not string_list(eligible) or row.get("match_type") not in ka.MATCH_TYPES or not isinstance(row.get("original_text"), str):
            continue  # The structural audit makes coverage fail; never certifies a skipped row.
        keys = tuple(sorted(eligible))
        if keys not in scope_cache:
            scope_cache[keys] = set().union(*(scopes[key] for key in keys))
        applicable = scope_cache[keys]
        applicable_pairs += len(applicable)
        terms = set(ka.tokens(row["original_text"]))
        candidates = [postings.get(term, set()) for term in terms]
        if not candidates:
            continue
        candidates.append(applicable)
        candidates.sort(key=len)
        possible = candidates[0].copy()
        for posting in candidates[1:]:
            possible.intersection_update(posting)
            if not possible:
                break
        for index in sorted(possible):
            case = cases[index]
            comparisons += 1
            if ka.negative_matches(row["original_text"], row["match_type"], case["text"]):
                conflicts.append({"negative_row": number, "negative_id": row.get("keyword_id"),
                                  "case_kind": case["case_kind"], "case_id": case["case_id"],
                                  "positive_ids": case["positive_ids"],
                                  "affected_campaign_keys": sorted(set(keys) & set(case["campaign_keys"])),
                                  "result": "CONFLICT_HOLD"})
    return {"conflicts": conflicts, "indexed_cases": len(cases),
            "applicable_case_pairs": applicable_pairs, "lexical_comparisons_executed": comparisons,
            "pairs_pruned_by_token_index": applicable_pairs - comparisons}


def evaluate_coverage(positives, negatives, sources, campaigns, contexts, queries,
                      scope_bindings, review, positive_report, negative_report, at):
    errors = []
    input_values = dict(zip(BINDING_ROLES, [positives, negatives, sources, campaigns, contexts, queries, scope_bindings]))
    input_hashes = {role: canonical_sha256(value) for role, value in input_values.items()}
    valid_positives = isinstance(positives, list) and all(isinstance(row, dict) for row in positives)
    positives = positives if valid_positives else []
    if not valid_positives or not positives:
        errors.append("complete nonempty supplied positive library required")
    if not negatives:
        errors.append("nonempty negative library required to claim tested coverage")
    if not queries:
        errors.append("nonempty reviewed protected long-tail corpus required")
    if not positive_report or not positive_report.get("structural_pass") or positive_report.get("reviewed_eligible_rows") != len(positives):
        errors.append("every supplied positive row must pass research validation; no skipped/candidate/stale/unmapped rows")
    if not negative_report.get("structural_pass") or negative_report.get("reviewed_eligible_rows") != len(negatives):
        # Existing known query collisions are handled separately below, while any
        # other invalid negative makes complete evaluation unavailable.
        nonconflict_errors = negative_report.get("global_errors", []) + [error for row in negative_report.get("records", [])
                            for error in row["errors"] if not error.startswith(("protected query conflict;", "declared conflicts differ"))]
        if nonconflict_errors:
            errors.append("every supplied negative row must have valid research and explicit scope")
    # Missing exclusion approval does not invalidate a research simulation.
    # All other/unknown holds fail coverage closed rather than relying on an
    # exhaustive list of current scope-error strings.
    approval_only_holds = ("exclusion approval missing;", "independent exclusion approver required", "exclusion approval:")
    if any(not hold.startswith(approval_only_holds) for row in negative_report.get("records", []) for hold in row["deployment_holds"]):
        errors.append("dated Real Estate account/campaign/group/list scope bindings are incomplete or invalid")

    if not isinstance(review, dict):
        errors.append("coverage review object required")
        review = {}
    if review.get("version") != "1.0" or review.get("matcher_version") != MATCHER_VERSION or review.get("coverage_claim") != CLAIM:
        errors.append("review version, matcher and bounded coverage claim must match")
    if review.get("review_state") != "REVIEWED" or not ka.nonblank(review.get("reviewer")) or not ka.nonblank(review.get("evidence_ref")):
        errors.append("dated independent reviewed corpus evidence required")
    ka.fresh(review, at, errors, "coverage review", "reviewed_on")
    reviewers = {str(row.get("reviewer", "")).strip().casefold() for row in positives + negatives}
    if str(review.get("reviewer", "")).strip().casefold() in reviewers:
        errors.append("coverage reviewer must be independent of the positive/negative research reviewers")
    claims = review.get("bindings")
    if not isinstance(claims, dict) or set(claims) != set(BINDING_ROLES):
        errors.append("review must bind all and only the seven exact input roles")
        claims = {}
    for role, actual in input_hashes.items():
        if claims.get(role) != actual:
            errors.append("canonical SHA256 binding mismatch: " + role)
    positive_ids = [row.get("keyword_id") for row in positives]
    query_ids = [row.get("query_id") for row in queries]
    for role, actual_ids in [("expected_positive_ids", positive_ids), ("expected_query_ids", query_ids)]:
        if not string_list(review.get(role)) or review.get(role) != actual_ids:
            errors.append("complete ordered identity manifest mismatch: " + role)

    campaign_index = {row["campaign_key"]: row for row in campaigns if isinstance(row.get("campaign_key"), str)}
    context_index = {row["campaign_key"]: row for row in contexts if isinstance(row.get("campaign_key"), str)}
    source_index = {row["source_id"]: row for row in sources if isinstance(row.get("source_id"), str)}
    positive_index = {row["keyword_id"]: row for row in positives if isinstance(row.get("keyword_id"), str)}
    designs, design_index = review.get("ad_group_designs"), {}
    if not isinstance(designs, list) or not designs or not all(isinstance(row, dict) for row in designs):
        errors.append("reviewed ad-group design ownership registry required")
        designs = []
    for design in designs:
        campaign, group = design.get("campaign_key"), design.get("ad_group_key")
        if not ka.nonblank(campaign) or not ka.nonblank(group):
            errors.append("ad-group design needs string campaign/group identities")
            continue
        key = (campaign, group)
        if key in design_index:
            errors.append("duplicate ad-group design ownership")
        design_index[key] = design
        if campaign not in campaign_index or design.get("landing_page_id") != campaign_index[campaign].get("landing_page_id"):
            errors.append("ad-group design has unknown campaign or wrong designated page")
        if not ka.nonblank(design.get("evidence_ref")) or not ka.nonblank(design.get("reviewer")):
            errors.append("ad-group design ownership needs reviewer and evidence")
        ka.fresh(design, at, errors, "ad-group design", "reviewed_on")

    cases, coverage = [], defaultdict(list)
    for row in positives:
        key, campaign, group = row.get("keyword_id"), row.get("primary_campaign_key"), row.get("ad_group_key")
        if not all(isinstance(value, str) for value in [key, campaign, group]):
            errors.append("positive identity/ownership is malformed")
            continue
        if (campaign, group) not in design_index:
            errors.append("positive ad-group ownership is unmapped: " + key)
        context = context_index.get(campaign, {})
        if not context.get("services") or not set(context.get("services", [])) <= ka.SERVICES or not ka.nonblank(context.get("evidence_ref")):
            errors.append("positive campaign has no reviewed service context: " + key)
        ka.fresh(context, at, errors, "positive campaign context " + key, "reviewed_on")
        if isinstance(row.get("original_text"), str):
            cases.append({"case_kind": "POSITIVE_LITERAL", "case_id": key, "text": row["original_text"],
                          "positive_ids": [key], "campaign_keys": [campaign], "ad_group_key": group,
                          "landing_page_id": row.get("landing_page_id")})

    represented_campaigns = {row.get("primary_campaign_key") for row in positives if isinstance(row.get("primary_campaign_key"), str)}
    for row in negatives:
        eligible, target = row.get("eligible_campaigns"), row.get("scope_target")
        if string_list(eligible) and not set(eligible) <= represented_campaigns:
            errors.append("negative scope includes a campaign absent from the supplied positive library")
        if row.get("scope_type") == "AD_GROUP":
            if not isinstance(target, dict) or not all(isinstance(target.get(key), str) for key in ("campaign_key", "ad_group_key")) or (target["campaign_key"], target["ad_group_key"]) not in design_index:
                errors.append("negative ad-group scope is absent from reviewed design ownership")

    duplicate_texts = Counter(ka.normalize(query["text"]) for query in queries if isinstance(query.get("text"), str))
    for query in queries:
        key, text, mapped = query.get("query_id"), query.get("text"), query.get("positive_ids")
        if not isinstance(text, str):
            errors.append("protected query text is not a string")
            continue
        norm = ka.normalize(text)
        if not ka.tokens(text) or re.search(r'[\[\]"]', norm) or any(unicodedata.category(ch) in {"Cc", "Cf"} for ch in norm):
            errors.append("protected corpus has zero-token, invisible or malformed-wrapper text")
        if duplicate_texts[norm] != 1:
            errors.append("duplicate normalized protected query text; consolidate scope rather than count twice")
        if not string_list(mapped) or not set(mapped) <= set(positive_index):
            errors.append("protected query needs unique known positive_ids: " + str(key))
            continue
        expected_campaigns = {positive_index[identity].get("primary_campaign_key") for identity in mapped}
        if not string_list(query.get("campaign_keys")) or set(query["campaign_keys"]) != expected_campaigns:
            errors.append("protected query campaign scope differs from exact positive ownership: " + str(key))
        expected_services = set().union(*(set(context_index.get(campaign, {}).get("services", [])) for campaign in expected_campaigns))
        if not string_list(query.get("services")) or set(query["services"]) != expected_services:
            errors.append("protected query service scope differs from reviewed campaign context: " + str(key))
        if query.get("query_kind") not in {"LONG_TAIL", "COUNTEREXAMPLE"}:
            errors.append("reviewed query_kind LONG_TAIL or COUNTEREXAMPLE required")
        if query.get("review_state") != "REVIEWED" or not ka.nonblank(query.get("reviewer")) or not ka.nonblank(query.get("source_reference")):
            errors.append("protected query needs reviewed provenance and reviewer: " + str(key))
        source = source_index.get(query.get("source_id"), {})
        if source.get("kind") not in ka.SOURCE_KINDS or source.get("approved_for_research") is not True or not ka.nonblank(source.get("evidence_ref")):
            errors.append("protected query source evidence unavailable: " + str(key))
        ka.fresh(source, at, errors, "protected query source " + str(key))
        for identity in mapped:
            base = positive_index[identity].get("original_text")
            base_tokens = ka.tokens(base) if isinstance(base, str) else []
            actual_tokens = ka.tokens(text)
            if query.get("query_kind") == "LONG_TAIL":
                # A longer lexical extension is a minimum test fixture, not proof
                # of real demand, semantic quality or all possible close variants.
                if not base_tokens or len(actual_tokens) <= len(base_tokens) or not Counter(base_tokens) <= Counter(actual_tokens):
                    errors.append("long-tail must extend each linked positive literal with additional tokens: " + str(key))
                else:
                    coverage[identity].append(key)
        cases.append({"case_kind": "PROTECTED_QUERY", "case_id": key, "text": text,
                      "positive_ids": mapped, "campaign_keys": query.get("campaign_keys", [])})
    missing = [key for key in positive_ids if not isinstance(key, str) or not coverage[key]]
    if missing:
        errors.append("one or more supplied positives lack a reviewed mapped long-tail case")
    # A review cannot predate evidence it purports to review. Rechecking all input
    # dates each invocation also prevents replay after source/corpus expiry.
    try:
        reviewed_on = ka.iso_day(review.get("reviewed_on"))
        for row, field in ([(row, "reviewed_on") for row in positives + negatives + queries + designs + contexts]
                           + [(row, "observed_on") for row in sources]):
            if ka.iso_day(row.get(field)) > reviewed_on:
                errors.append("coverage review predates an input evidence/review date")
                break
    except (TypeError, ValueError):
        errors.append("coverage evidence contains invalid review dates")

    simulation = simulate_scoped(negatives, cases)
    errors = sorted(set(errors))
    complete = not errors
    conflict_free = complete and not simulation["conflicts"]
    return {"version": "1.0", "matcher_version": MATCHER_VERSION,
            "status": "VERIFIED_SUPPLIED_DATASETS_ONLY" if conflict_free else "CONFLICT_HOLD" if complete else "INCOMPLETE_OR_INVALID_CORPUS_HOLD",
            "as_of": at.isoformat(), "evaluation_complete": complete,
            "conflict_free_coverage_verified": conflict_free,
            "positive_library_rows": len(positives), "negative_library_rows": len(negatives),
            "protected_query_rows": len(queries), "positives_with_long_tail": sum(bool(items) for items in coverage.values()),
            "missing_long_tail_positive_ids": missing,
            "canonical_input_sha256": input_hashes, "review_sha256": canonical_sha256(review),
            "positive_ownership": [{key: row.get(key) for key in ("keyword_id", "primary_campaign_key", "ad_group_key", "landing_page_id")} for row in positives],
            "errors": errors, **simulation,
            "scope_policy": "All applicable supplied literals and queries; AD_GROUP conservatively tests its entire campaign",
            "limits": ["Only complete supplied datasets; not the 14000 target or all possible search queries",
                       "Lexical regression only; not Google intent/close-variant/misspelling/symbol matching",
                       "Review references and sources still require independent factual/authenticity verification",
                       "No proof of live inherited scope, platform capacity, approvals or deployment"],
            "deployment_export_allowed": False, "production_writes_available": False}

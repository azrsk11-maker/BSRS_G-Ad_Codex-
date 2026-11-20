"""Read-only content evidence consistency and suppression; never approval or publishing."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import unicodedata

SCHEMA = "bsre-content-evidence-v1"
ID = re.compile(r"[A-Za-z][A-Za-z0-9:_-]{0,99}\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")
PAGE = re.compile(r"BSRE-LP\d{4}\Z")
CAMPAIGN = re.compile(r"BSRE-C\d{4}\Z")
TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|\+00:00)\Z")
KINDS = {"CLAIM", "ASSET_RIGHTS", "INVENTORY", "BROKERAGE_SERVICE"}
CATEGORIES = {"PRICE", "YIELD", "PAYMENT_PLAN", "HANDOVER", "OWNERSHIP", "FINANCE",
              "RESIDENCY", "GUARANTEE", "REVIEW", "AFFILIATION", "LEGAL_REGULATORY",
              "AVAILABILITY_DISCLOSURE", "ALTERNATIVE_OFFER", "OTHER"}
AVAILABLE = {"available", "limited-confirmed"}
AVAILABILITY = AVAILABLE | {"waitlist", "sold/rented", "unavailable", "unknown"}
PAGE_FIELDS = {"page_id", "campaign_key", "content_sha256", "content_author", "update_owner",
               "offer_kind", "inventory_presentation", "evidence_ids", "evidence_sha256_by_id", "offer_inventory_ids",
               "alternative_evidence_ids", "disclosure_claim_id", "alternative_claim_id", "review"}
RECORD_FIELDS = {"evidence_id", "kind", "page_ids", "source_class", "source_ref", "source_sha256",
                 "source_as_of_utc", "valid_until_utc", "details", "review"}
REVIEW_FIELDS = {"reviewer", "reviewed_at_utc", "evidence_ref", "subject_sha256", "approved"}


class ContentEvidenceError(ValueError):
    """Stable non-sensitive code; never embeds input values or private source content."""


def require(condition, code):
    if not condition:
        raise ContentEvidenceError(code)


def canonical_sha256(value):
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                         allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise ContentEvidenceError("INVALID_JSON_VALUE") from None
    return hashlib.sha256(raw).hexdigest()


def _shape(value, fields):
    require(type(value) is dict and set(value) == fields, "INVALID_RECORD_FIELDS")


def _text(value, maximum=4000):
    require(isinstance(value, str) and 0 < len(value) <= maximum and value.strip() == value
            and not any(unicodedata.category(c).startswith("C") for c in value), "INVALID_TEXT")


def _id(value):
    require(isinstance(value, str) and ID.fullmatch(value) is not None, "INVALID_IDENTIFIER")


def _sha(value):
    require(isinstance(value, str) and SHA.fullmatch(value) is not None, "INVALID_DIGEST")


def _enum(value, options, code):
    require(isinstance(value, str) and value in options, code)


def _ids(value, maximum=1000, pattern=ID):
    require(type(value) is list and len(value) <= maximum and
            all(isinstance(v, str) and pattern.fullmatch(v) is not None for v in value)
            and len(value) == len(set(value)), "INVALID_ID_LIST")


def _instant(value):
    require(isinstance(value, str) and TIME.fullmatch(value) is not None,
            "UTC_WHOLE_SECOND_TIMESTAMP_REQUIRED")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        require(1970 <= result.year <= 2100, "CLOCK_OUT_OF_RANGE")
        return result
    except (ValueError, OverflowError):
        raise ContentEvidenceError("INVALID_CALENDAR_TIMESTAMP") from None


def _review_shape(review, page=False):
    fields = REVIEW_FIELDS | ({"claims_complete", "assets_complete"} if page else set())
    _shape(review, fields)
    _id(review["reviewer"])
    _id(review["evidence_ref"])
    _sha(review["subject_sha256"])
    _instant(review["reviewed_at_utc"])
    require(type(review["approved"]) is bool, "INVALID_REVIEW_DECISION")
    if page:
        require(all(type(review[k]) is bool for k in ("claims_complete", "assets_complete")),
                "INVALID_COMPLETENESS_ATTESTATION")


def _review_reasons(subject, now, author=None, page=False):
    review = subject["review"]
    reasons = []
    if review["approved"] is not True:
        reasons.append("REVIEW_APPROVAL_ATTESTATION_REQUIRED")
    if review["subject_sha256"] != canonical_sha256({k: v for k, v in subject.items() if k != "review"}):
        reasons.append("REVIEW_SUBJECT_CHANGED")
    if _instant(review["reviewed_at_utc"]) > now:
        reasons.append("REVIEW_FROM_FUTURE")
    if author is not None and review["reviewer"] == author:
        reasons.append("INDEPENDENT_CONTENT_REVIEW_REQUIRED")
    if page and (not review["claims_complete"] or not review["assets_complete"]):
        reasons.append("COMPLETE_CONTENT_AND_ASSET_ATTESTATION_REQUIRED")
    return reasons


def _record_shape(record):
    _shape(record, RECORD_FIELDS)
    _id(record["evidence_id"])
    _enum(record["kind"], KINDS, "INVALID_EVIDENCE_KIND")
    _ids(record["page_ids"], 360, PAGE)
    require(bool(record["page_ids"]), "EMPTY_EVIDENCE_SCOPE")
    _enum(record["source_class"], {"BUSINESS_EVIDENCE", "OFFICIAL_AUTHORITY", "PUBLIC_RESEARCH"}, "INVALID_SOURCE_CLASS")
    _id(record["source_ref"])
    _sha(record["source_sha256"])
    _instant(record["source_as_of_utc"])
    _instant(record["valid_until_utc"])
    _review_shape(record["review"])
    d = record["details"]
    if record["kind"] == "CLAIM":
        _shape(d, {"text", "category", "related_evidence_ids"})
        _text(d["text"])
        _enum(d["category"], CATEGORIES, "INVALID_CLAIM_CATEGORY")
        _ids(d["related_evidence_ids"])
    elif record["kind"] == "ASSET_RIGHTS":
        _shape(d, {"asset_sha256", "rights_basis", "licence_ref", "permitted_use"})
        _sha(d["asset_sha256"])
        _enum(d["rights_basis"], {"OWNED", "LICENSED"}, "INVALID_ASSET_RIGHTS_BASIS")
        _id(d["licence_ref"])
        require(d["permitted_use"] == "PAID_LANDING_PAGE", "INVALID_ASSET_USE")
    elif record["kind"] == "INVENTORY":
        _shape(d, {"property_id", "availability_state", "asking_price_minor", "currency"})
        _id(d["property_id"])
        _enum(d["availability_state"], AVAILABILITY, "INVALID_AVAILABILITY_STATE")
        price = d["asking_price_minor"]
        require(price is None or (type(price) is int and 0 <= price <= 10**15), "INVALID_PRICE_MINOR_UNITS")
        require(d["currency"] == "AED", "INVALID_INVENTORY_CURRENCY")
    else:
        _shape(d, {"service_key", "description"})
        _id(d["service_key"])
        _text(d["description"])


def _page_shape(page):
    _shape(page, PAGE_FIELDS)
    require(isinstance(page["page_id"], str) and PAGE.fullmatch(page["page_id"]) is not None,
            "INVALID_PAGE_ID")
    require(isinstance(page["campaign_key"], str) and CAMPAIGN.fullmatch(page["campaign_key"]) is not None,
            "INVALID_CAMPAIGN_KEY")
    _sha(page["content_sha256"])
    _id(page["content_author"])
    _id(page["update_owner"])
    _enum(page["offer_kind"], {"BROKERAGE_SERVICE", "PROPERTY_OFFER"}, "INVALID_OFFER_KIND")
    _enum(page["inventory_presentation"], {"NOT_APPLICABLE", "CURRENT_OFFER", "DISCLOSED_UNAVAILABLE_WITH_ALTERNATIVES"},
          "INVALID_INVENTORY_PRESENTATION")
    for key in ("evidence_ids", "offer_inventory_ids", "alternative_evidence_ids"):
        _ids(page[key])
    require(type(page["evidence_sha256_by_id"]) is dict and
            set(page["evidence_sha256_by_id"]) == set(page["evidence_ids"]), "EXACT_EVIDENCE_DIGEST_MAP_REQUIRED")
    for value in page["evidence_sha256_by_id"].values():
        _sha(value)
    for key in ("disclosure_claim_id", "alternative_claim_id"):
        if page[key] is not None:
            _id(page[key])
    _review_shape(page["review"], page=True)


def _record_reasons(record, now):
    reasons = _review_reasons(record, now)
    start, end = _instant(record["source_as_of_utc"]), _instant(record["valid_until_utc"])
    if not start < end:
        reasons.append("INVALID_EVIDENCE_WINDOW")
    if start > now:
        reasons.append("SOURCE_FROM_FUTURE")
    if now >= end:
        reasons.append("EVIDENCE_EXPIRED")
    if _instant(record["review"]["reviewed_at_utc"]) < start:
        reasons.append("REVIEW_PREDATES_SOURCE")
    permitted_source = record["source_class"] == "BUSINESS_EVIDENCE" or (
        record["source_class"] == "OFFICIAL_AUTHORITY" and record["kind"] == "CLAIM"
        and record["details"]["category"] == "LEGAL_REGULATORY")
    if not permitted_source:
        reasons.append("PUBLIC_RESEARCH_NOT_PUBLICATION_EVIDENCE")
    return reasons


def _presentation_reasons(page, records, invalid):
    reasons = []
    ids = set(page["evidence_ids"])
    subject, alternatives = page["offer_inventory_ids"], page["alternative_evidence_ids"]
    def valid(identity, kind):
        return identity in ids and identity in records and records[identity]["kind"] == kind and not invalid[identity]
    def available(identity):
        return valid(identity, "INVENTORY") and records[identity]["details"]["availability_state"] in AVAILABLE
    def linked_claim(identity, category, targets):
        return valid(identity, "CLAIM") and records[identity]["details"]["category"] == category and \
            set(records[identity]["details"]["related_evidence_ids"]) == set(targets)
    if page["offer_kind"] == "BROKERAGE_SERVICE":
        if page["inventory_presentation"] != "NOT_APPLICABLE" or subject or alternatives or \
                page["disclosure_claim_id"] is not None or page["alternative_claim_id"] is not None:
            reasons.append("INVALID_SERVICE_PRESENTATION")
        if not any(valid(i, "BROKERAGE_SERVICE") for i in ids):
            reasons.append("CURRENT_BROKERAGE_SERVICE_EVIDENCE_REQUIRED")
    elif page["inventory_presentation"] == "CURRENT_OFFER":
        if not subject or not all(available(i) for i in subject):
            reasons.append("CURRENT_AVAILABLE_OFFER_EVIDENCE_REQUIRED")
        if alternatives or page["disclosure_claim_id"] is not None or page["alternative_claim_id"] is not None:
            reasons.append("INVALID_CURRENT_OFFER_PRESENTATION")
    elif page["inventory_presentation"] == "DISCLOSED_UNAVAILABLE_WITH_ALTERNATIVES":
        if not subject or not all(valid(i, "INVENTORY") and records[i]["details"]["availability_state"] not in AVAILABLE for i in subject):
            reasons.append("UNAVAILABLE_SUBJECT_STATUS_EVIDENCE_REQUIRED")
        if not linked_claim(page["disclosure_claim_id"], "AVAILABILITY_DISCLOSURE", subject):
            reasons.append("EXACT_UNAVAILABLE_DISCLOSURE_REQUIRED")
        if not alternatives or not all(available(i) or valid(i, "BROKERAGE_SERVICE") for i in alternatives):
            reasons.append("CURRENT_ALTERNATIVE_OR_ADVISORY_EVIDENCE_REQUIRED")
        if set(subject) & set(alternatives):
            reasons.append("UNAVAILABLE_SUBJECT_CANNOT_BE_ITS_OWN_ALTERNATIVE")
        if not linked_claim(page["alternative_claim_id"], "ALTERNATIVE_OFFER", alternatives):
            reasons.append("EXACT_ALTERNATIVE_DESCRIPTION_REQUIRED")
    else:
        reasons.append("PROPERTY_PRESENTATION_REQUIRED")
    return reasons


def evaluate_content_evidence(ledger, *, expected_pages, now_utc):
    """Check supplied attestations against independently derived content identities.

    Invalid structure raises a sanitized ValueError. Valid but missing/stale/unreviewed
    evidence holds only affected pages. Neither an eligible result nor a hash proves
    authenticity, semantic completeness, regulatory compliance or publishing approval.
    """
    now = _instant(now_utc)
    _shape(ledger, {"schema", "pages", "records"})
    require(ledger["schema"] == SCHEMA, "UNSUPPORTED_LEDGER_SCHEMA")
    require(type(ledger["pages"]) is list and 0 < len(ledger["pages"]) <= 360, "BOUNDED_PAGE_SET_REQUIRED")
    require(type(ledger["records"]) is list and len(ledger["records"]) <= 20000, "BOUNDED_EVIDENCE_SET_REQUIRED")
    require(type(expected_pages) is list and len(expected_pages) == len(ledger["pages"]), "EXACT_EXPECTED_PAGE_SET_REQUIRED")
    expected = {}
    for page in expected_pages:
        _shape(page, {"page_id", "campaign_key", "content_sha256"})
        require(isinstance(page["page_id"], str) and PAGE.fullmatch(page["page_id"]) is not None, "INVALID_PAGE_ID")
        require(isinstance(page["campaign_key"], str) and CAMPAIGN.fullmatch(page["campaign_key"]) is not None, "INVALID_CAMPAIGN_KEY")
        require(1 <= int(page["page_id"][-4:]) <= 360 and
                page["campaign_key"] == "BSRE-C" + page["page_id"][-4:], "STABLE_PLANNED_PAIR_REQUIRED")
        _sha(page["content_sha256"])
        require(page["page_id"] not in expected, "DUPLICATE_EXPECTED_PAGE")
        expected[page["page_id"]] = page
    require(len({p["campaign_key"] for p in expected_pages}) == len(expected_pages), "DUPLICATE_EXPECTED_CAMPAIGN")
    pages = {}
    for page in ledger["pages"]:
        _page_shape(page)
        require(page["page_id"] not in pages, "DUPLICATE_LEDGER_PAGE")
        pages[page["page_id"]] = page
    require(set(pages) == set(expected), "EXACT_EXPECTED_PAGE_SET_REQUIRED")
    records, invalid = {}, {}
    for record in ledger["records"]:
        _record_shape(record)
        identity = record["evidence_id"]
        require(identity not in records, "DUPLICATE_EVIDENCE_ID")
        require(set(record["page_ids"]) <= set(pages), "EVIDENCE_SCOPE_OUTSIDE_EXPECTED_PAGES")
        records[identity] = record
        invalid[identity] = _record_reasons(record, now)
    bindings = {}
    for page_id, page in pages.items():
        for identity in page["evidence_ids"]:
            bindings.setdefault(identity, set()).add(page_id)
    for identity, record in records.items():
        require(bindings.get(identity, set()) == set(record["page_ids"]), "EVIDENCE_SCOPE_BINDING_MISMATCH")
    output = []
    for page_id in sorted(pages):
        page = pages[page_id]
        reasons = _review_reasons(page, now, page["content_author"], page=True)
        if any(page[k] != expected[page_id][k] for k in ("campaign_key", "content_sha256")):
            reasons.append("REVIEWED_CONTENT_IDENTITY_MISMATCH")
        suppressed, unavailable = [], []
        for identity in page["evidence_ids"]:
            if identity not in records:
                reasons.append("REFERENCED_EVIDENCE_MISSING")
                suppressed.append(identity)
                continue
            record = records[identity]
            record_reasons = list(invalid[identity])
            if page["evidence_sha256_by_id"][identity] != canonical_sha256(record):
                record_reasons.append("PAGE_EVIDENCE_BINDING_CHANGED")
            if record["review"]["reviewer"] == page["content_author"]:
                record_reasons.append("INDEPENDENT_CONTENT_REVIEW_REQUIRED")
            if record["kind"] == "CLAIM" and any(i not in page["evidence_ids"] or i not in records
                                                for i in record["details"]["related_evidence_ids"]):
                record_reasons.append("RELATED_EVIDENCE_NOT_IN_PAGE")
            if _instant(page["review"]["reviewed_at_utc"]) < _instant(record["review"]["reviewed_at_utc"]):
                record_reasons.append("PAGE_REVIEW_PREDATES_EVIDENCE_REVIEW")
            if record_reasons:
                reasons.extend(record_reasons)
                suppressed.append(identity)
            if record["kind"] == "INVENTORY" and (record_reasons or record["details"]["availability_state"] not in AVAILABLE):
                unavailable.append(identity)
        reasons.extend(_presentation_reasons(page, records, invalid))
        output.append({"page_id": page_id, "campaign_key": page["campaign_key"],
                       "content_sha256": page["content_sha256"], "eligible": not reasons,
                       "reason_codes": sorted(set(reasons)), "suppressed_evidence_ids": sorted(suppressed),
                       "suppressed_current_offer_ids": sorted(unavailable)})
    return {"schema": "bsre-content-evidence-report-v1", "ledger_sha256": canonical_sha256(ledger),
            "evaluated_at_utc": now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "all_pages_eligible": all(p["eligible"] for p in output), "pages": output,
            "authenticated_business_approval": False, "publication_authorized": False,
            "network_calls": 0, "production_writes": 0}


def _read(path):
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 8 * 1024 * 1024, "BOUNDED_REGULAR_INPUT_REQUIRED")
    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, "DUPLICATE_JSON_KEY")
            result[key] = value
        return result
    try:
        with path.open("rb") as stream:
            raw = stream.read(8 * 1024 * 1024 + 1)
        require(len(raw) <= 8 * 1024 * 1024, "BOUNDED_REGULAR_INPUT_REQUIRED")
        return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ContentEvidenceError("NONFINITE_JSON_VALUE")))
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError):
        raise ContentEvidenceError("INPUT_READ_FAILED") from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--expected-pages", type=Path, required=True)
    parser.add_argument("--now-utc", required=True)
    args = parser.parse_args()
    try:
        report = evaluate_content_evidence(_read(args.ledger), expected_pages=_read(args.expected_pages), now_utc=args.now_utc)
    except (ContentEvidenceError, OSError, TypeError, KeyError, RecursionError):
        print(json.dumps({"status": "HELD", "error": "CONTENT_EVIDENCE_INVALID_OR_UNREADABLE",
                          "publication_authorized": False, "production_writes": 0}))
        return 2
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0 if report["all_pages_eligible"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Bounded, read-only keyword text diagnostics; never platform acceptance.

Character length uses Python Unicode code points. Whitespace word counting uses
str.split(), a local review heuristic, not a verified Google server tokenizer.
Original and caller-provided prospective canonical text are profiled separately;
this module never normalizes, strips match syntax, rewrites or admits text.
"""
from collections import Counter
import hashlib
import json
import re


MAX_TEXT_CHARACTERS = 16384
MAX_ROWS = 100000
MAX_COLLECTION_CHARACTERS = 64 * 1024 * 1024
INVALID_SYMBOLS = frozenset(",!@%^()={};~`<>?\\|")
SOURCES = (
    "https://developers.google.com/google-ads/api/fields/v25/campaign_criterion",
    "https://developers.google.com/google-ads/api/reference/rpc/v25/KeywordInfo",
    "https://support.google.com/google-ads/answer/2453972",
)


def _need(condition, code):
    if not condition:
        raise ValueError(code)


def _text(value):
    _need(type(value) is str, "TEXT_MUST_BE_STRING")
    _need(len(value) <= MAX_TEXT_CHARACTERS, "TEXT_BOUND_EXCEEDED")
    # Reject malformed surrogate strings instead of implicitly repairing input.
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise ValueError("TEXT_MUST_BE_VALID_UNICODE") from exc
    return value


def _profile(text):
    text = _text(text)
    invalid = sorted(set(text) & INVALID_SYMBOLS)
    reasons, observations = [], []
    if len(text) > 80:
        reasons.append("DOCUMENTED_CHARACTER_LIMIT_EXCEEDED")
    if invalid:
        reasons.append("DOCUMENTED_INVALID_SYMBOLS")
    # Any embedded match punctuation remains visible, including outer wrappers.
    # Determining whether a caller intended wrappers belongs to a later review.
    if any(symbol in text for symbol in '[]"'):
        reasons.append("MATCH_SYNTAX_REQUIRES_REVIEW")
    words = len(text.split())
    if words > 10:
        reasons.append("WHITESPACE_WORD_LIMIT_REQUIRES_REVIEW")
    if not text.strip():
        reasons.append("BLANK_TEXT_REQUIRES_REVIEW")
    if "." in text:
        observations.append("PERIOD_IGNORED_OR_OPERATOR_SENSITIVE")
    if "+" in text:
        observations.append("PLUS_IGNORED_OR_OPERATOR_SENSITIVE")
    if text.lstrip().startswith("-"):
        observations.append("LEADING_MINUS_OPERATOR_SENSITIVE")
    if re.search(r"(?i)(?<!\w)site:", text):
        observations.append("SITE_OPERATOR_SENSITIVE")
    if re.search(r"(?<!\w)OR(?!\w)", text):
        observations.append("OR_OPERATOR_SENSITIVE")
    documented = any(reason.startswith("DOCUMENTED_") for reason in reasons)
    return {
        "text": text,
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "character_count": len(text),
        "whitespace_word_count": words,
        "invalid_symbols": invalid,
        "reason_codes": reasons,
        "observations": observations,
        "classification": "DOCUMENTED_INCOMPATIBILITY_DETECTED" if documented else (
            "REQUIRES_REVIEW" if reasons else "NO_KNOWN_INCOMPATIBILITY_DETECTED"),
    }


def profile_text(original_text, *, canonical_text=None):
    """Profile exact supplied strings independently; canonical_text is optional."""
    return {
        "original": _profile(original_text),
        "provided_canonical": None if canonical_text is None else _profile(canonical_text),
    }


def summarize(rows, *, text_field="original_text", canonical_field=None,
              context_purpose="UNSPECIFIED_RESEARCH_DIAGNOSTIC"):
    """Return row profiles and overlapping reason totals without mutating rows.

    rows must be a bounded list/tuple of dictionaries. Context is descriptive;
    archives and protections retain their original role and are never admitted.
    Only selected text fields are returned; other supplied metadata stays private.
    """
    _need(type(rows) in (list, tuple) and len(rows) <= MAX_ROWS, "COLLECTION_BOUND_OR_TYPE")
    _need(type(text_field) is str and bool(text_field), "TEXT_FIELD_REQUIRED")
    _need(canonical_field is None or (type(canonical_field) is str and bool(canonical_field)),
          "CANONICAL_FIELD_INVALID")
    _need(type(context_purpose) is str and bool(context_purpose.strip())
          and len(context_purpose) <= 256, "CONTEXT_PURPOSE_INVALID")
    size = 0
    # Validate total size before constructing the larger diagnostic output.
    for row in rows:
        _need(type(row) is dict and text_field in row, "ROW_OR_TEXT_FIELD_INVALID")
        size += len(_text(row[text_field]))
        if canonical_field is not None:
            _need(canonical_field in row, "CANONICAL_FIELD_MISSING")
            size += len(_text(row[canonical_field]))
        _need(size <= MAX_COLLECTION_CHARACTERS, "COLLECTION_TEXT_BOUND_EXCEEDED")
    profiles = [dict(row_index=index, **profile_text(row[text_field], canonical_text=(
        row[canonical_field] if canonical_field is not None else None)))
        for index, row in enumerate(rows)]
    totals = {}
    for field in ("original", "provided_canonical"):
        values = [row[field] for row in profiles if row[field] is not None]
        totals[field] = {
            "rows": len(values),
            "classifications": dict(sorted(Counter(v["classification"] for v in values).items())),
            "reason_counts": dict(sorted(Counter(r for v in values for r in v["reason_codes"]).items())),
            "observation_counts": dict(sorted(Counter(r for v in values for r in v["observations"]).items())),
        }
    selected = [[row[text_field]] + ([row[canonical_field]] if canonical_field else []) for row in rows]
    return {
        "scope": "READ_ONLY_TEXT_DIAGNOSTIC_NOT_PLATFORM_VALIDATION_OR_ADMISSION",
        "context_purpose": context_purpose,
        "sources": list(SOURCES),
        "input_text_sha256": hashlib.sha256(json.dumps(selected, ensure_ascii=False,
            separators=(",", ":")).encode("utf-8")).hexdigest(),
        "measurement_basis": "UNICODE_CODE_POINTS_AND_LOCAL_WHITESPACE_SPLIT_NOT_SERVER_TOKENIZER",
        "symbol_list_exhaustive": False,
        "reason_counts_overlap": True,
        "platform_validation_performed": False,
        "variant_clearance_claimed": False,
        "search_volume_verified": False,
        "admission_performed": False,
        "exclusion_approval_granted": False,
        "deployment_export_allowed": False,
        "totals": totals,
        "rows": profiles,
    }

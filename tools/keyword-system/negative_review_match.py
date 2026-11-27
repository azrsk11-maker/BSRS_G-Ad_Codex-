"""Optional local review of negative keyword literals with Unicode marks preserved."""

from argparse import ArgumentParser
from enum import Enum
import json
import sys
import unicodedata

from keyword_audit import MATCH_TYPES, normalize


class ReviewResult(Enum):
    LEXICAL_MATCH = "LEXICAL_MATCH"
    NO_LEXICAL_MATCH = "NO_LEXICAL_MATCH"
    HOLD_UNSEGMENTED_HAN = "HOLD_UNSEGMENTED_HAN"

    def __bool__(self):
        raise TypeError("Compare review results explicitly")


def _mark(char):
    return unicodedata.category(char).startswith("M")


def _words(text):
    word = []
    for char in normalize(text):
        if char.isalnum() or char == "_" or (word and _mark(char)):
            word.append(char)
        elif word:
            yield "".join(word)
            word.clear()
    if word:
        yield "".join(word)


def _contains(words, phrase):
    return any(words[start:start + len(phrase)] == phrase
               for start in range(len(words) - len(phrase) + 1))


def _han(char):
    name = unicodedata.name(char, "")
    return char == "〇" or name.startswith(("CJK UNIFIED IDEOGRAPH", "CJK COMPATIBILITY IDEOGRAPH"))


def _han_units(words):
    """Split Han bases for ambiguity detection and keep each base's marks."""
    for word in words:
        unit = []
        after_han = False
        for char in word:
            if _mark(char):
                unit.append(char)
                continue
            is_han = _han(char)
            if unit and (is_han or after_han):
                yield "".join(unit)
                unit.clear()
            unit.append(char)
            after_han = is_han
        yield "".join(unit)


def _han_ambiguity(negative, query, match_type):
    expanded_negative = tuple(_han_units(negative))
    expanded_query = tuple(_han_units(query))
    if expanded_negative == negative and expanded_query == query:
        return False
    if match_type == "EXACT":
        return expanded_negative == expanded_query
    if match_type == "PHRASE":
        return _contains(expanded_query, expanded_negative)
    # A broad-match word still needs its entire Han sequence in one contiguous span.
    return all(_contains(expanded_query, tuple(_han_units((word,)))) for word in negative)


def review_negative_match(text, match_type, query):
    """Return a local reviewer verdict for a pair whose scope is already established."""
    if match_type not in MATCH_TYPES:
        raise ValueError("Unsupported negative match type")
    negative = tuple(_words(text))
    actual = tuple(_words(query))
    if not negative or not actual:
        return ReviewResult.NO_LEXICAL_MATCH
    if match_type == "EXACT":
        matched = negative == actual
    elif match_type == "PHRASE":
        matched = _contains(actual, negative)
    else:
        matched = set(negative) <= set(actual)
    if matched:
        return ReviewResult.LEXICAL_MATCH
    if _han_ambiguity(negative, actual, match_type):
        return ReviewResult.HOLD_UNSEGMENTED_HAN
    return ReviewResult.NO_LEXICAL_MATCH


def main(argv=None, stdin=None):
    parser = ArgumentParser(description="Read a negative literal and query as two UTF-8 lines.")
    parser.add_argument("match_type", choices=sorted(MATCH_TYPES))
    options = parser.parse_args(argv)
    stream = sys.stdin.buffer if stdin is None else stdin
    raw = stream.read(8193)
    if len(raw) > 8192:
        parser.exit(2, "Review input exceeds its size limit.\n")
    try:
        negative, query = raw.decode("utf-8").splitlines()
        if not negative.strip() or not query.strip():
            raise ValueError("A review input is empty")
        result = review_negative_match(negative, options.match_type, query)
    except ValueError:
        parser.exit(2, "Supply two nonempty UTF-8 lines.\n")
    print(json.dumps({"review": result.value, "provider_verified": False, "deployment_authorized": False}))


if __name__ == "__main__":
    main()

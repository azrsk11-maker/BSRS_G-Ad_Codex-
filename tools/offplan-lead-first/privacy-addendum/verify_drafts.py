"""Verify the version and markup contract of the unpublished privacy drafts."""

from hashlib import sha256
import json
from pathlib import Path
import re
from xml.etree import ElementTree


HERE = Path(__file__).resolve().parent
LOCALES = ("en", "ar-AE", "de-DE", "fr-FR", "hi-IN", "zh-Hant-TW")
HEADING = "bsre-optional-measurement-notice"
GOOGLE = "https://business.safety.google/privacy/"
EMAIL = "marketing@blackswanrealestate.ae"


def require(condition, detail):
    if not condition:
        raise ValueError(detail)


def visible_text(element):
    return " ".join("".join(element.itertext()).split())


def check_fragment(raw, locale, expected_hash):
    require(sha256(raw).hexdigest() == expected_hash, "draft bytes differ from the review manifest")
    require(b"<!" not in raw and b"<?" not in raw, "expected a plain HTML fragment")
    root = ElementTree.fromstring(raw.decode("utf-8"))
    attributes = {"lang": locale, "aria-labelledby": HEADING}
    if locale == "ar-AE":
        attributes["dir"] = "rtl"
    require(root.tag == "section" and root.attrib == attributes, "section language or heading binding differs")
    require([node.tag for node in root] == ["h2"] + ["p"] * 5, "expected one heading and five paragraphs")
    heading, *paragraphs = root
    require(heading.attrib == {"id": HEADING} and not len(heading) and visible_text(heading), "invalid heading")
    references = {1: GOOGLE, 4: "mailto:" + EMAIL}
    for index, paragraph in enumerate(paragraphs):
        require(not paragraph.attrib and visible_text(paragraph), "paragraph is empty or has attributes")
        if index not in references:
            require(not len(paragraph), "unexpected element in plain-text paragraph")
            continue
        require(len(paragraph) == 1, "expected a single reference link")
        anchor = paragraph[0]
        attributes = {"href": references[index]}
        if locale == "ar-AE" and index == 4:
            attributes["dir"] = "ltr"
        require(anchor.tag == "a" and anchor.attrib == attributes and not len(anchor) and visible_text(anchor),
                "reference link or markup differs")
        if index == 4:
            require(visible_text(anchor) == EMAIL, "visible privacy contact differs")
    require(re.findall(r"[0-9]+", visible_text(paragraphs[2])) == ["180"]
            and re.findall(r"[0-9]+", visible_text(paragraphs[3])) == ["12", "12"],
            "source review periods differ")


def verify(folder):
    review = json.loads((folder / "REVIEW.json").read_text(encoding="utf-8"))
    require(review["status"] == "UNPUBLISHED_REVIEW_DRAFT" and review["code_or_policy_published"] is False,
            "draft status differs")
    translations = review["translations"]
    require(set(translations) == set(LOCALES[1:]), "regional draft inventory differs")
    hashes = {"en": review["sha256"]}
    for locale, draft in translations.items():
        require(draft["status"] == "PENDING_HUMAN_LANGUAGE_AND_PRIVACY_REVIEW", f"{locale} review status differs")
        hashes[locale] = draft["sha256"]
    for locale in LOCALES:
        try:
            raw = (folder / f"NOTICE_ADDENDUM.{locale}.html").read_bytes()
            check_fragment(raw, locale, hashes[locale])
        except (ValueError, ElementTree.ParseError) as error:
            raise ValueError(f"{locale}: {error}") from error
    return len(hashes)


if __name__ == "__main__":
    print(f"Verified {verify(HERE)} versioned privacy review drafts")

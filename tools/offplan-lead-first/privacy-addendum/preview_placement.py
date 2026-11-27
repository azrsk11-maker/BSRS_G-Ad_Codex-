"""Compose a local placement preview from a pinned public WordPress Pages response."""

from argparse import ArgumentParser
from hashlib import sha256
import json
from pathlib import Path
from xml.etree import ElementTree

from verify_drafts import EMAIL, GOOGLE, HEADING, HERE, check_fragment, require

PAGE_ID = 26761
SLUG = "property-enquiry-privacy-notice"
PUBLIC_URL = f"https://blackswanrealestate.ae/{SLUG}/"
ANCHOR = b"<h2>Your choices</h2>"


def preview(capture, expected_sha256, folder=HERE):
    require(sha256(capture).hexdigest() == expected_sha256, "public capture differs from its reviewed hash")
    page = json.loads(capture)
    require(
        (page.get("id"), page.get("slug"), page.get("link"), page.get("type"), page.get("status"))
        == (PAGE_ID, SLUG, PUBLIC_URL, "page", "publish"),
        "public notice page identity differs",
    )
    content = page["content"]
    require(set(content) == {"rendered", "protected"} and content["protected"] is False,
            "public rendered content is required")
    original = content["rendered"].encode("utf-8")
    require(b"<!" not in original and b"<?" not in original, "notice contains markup declarations")
    root = ElementTree.fromstring(original)
    require(root.tag == "article" and root.get("class") == "bsre-enquiry-privacy", "notice wrapper differs")
    require(sum(node.tag == "h2" and node.text == "Your choices" for node in root) == 1
            and original.count(ANCHOR) == 1, "choice heading is missing or ambiguous")
    require(not any(node.get("id") == HEADING or node.get("href") == GOOGLE for node in root.iter()),
            "measurement section or Google disclosure link already exists")
    for node in root.iter():
        require(node.tag in {"article", "h1", "h2", "p", "strong", "a"}
                and set(node.attrib) <= {"class", "aria-labelledby", "id", "style", "href"}
                and (node.get("href") is None or node.get("href") == f"mailto:{EMAIL}")
                and ("style" not in node.attrib or node is root
                     and node.attrib["style"] == "max-width:840px;margin:3rem auto;padding:0 1.25rem;line-height:1.7;"),
                "existing notice markup falls outside the captured static article")

    review = json.loads((folder / "REVIEW.json").read_text(encoding="utf-8"))
    require(review["status"] == "UNPUBLISHED_REVIEW_DRAFT" and review["code_or_policy_published"] is False,
            "draft status differs")
    section = (folder / "NOTICE_ADDENDUM.en.html").read_bytes()
    check_fragment(section, "en", review["sha256"])

    offset = original.index(ANCHOR)
    combined = original[:offset] + section + original[offset:]
    parsed = ElementTree.fromstring(combined)
    require(len(parsed) == len(root) + 1 and len(parsed.findall(f".//h2[@id='{HEADING}']")) == 1,
            "combined notice structure differs")
    return combined


def main():
    args = ArgumentParser(description=__doc__)
    args.add_argument("capture", type=Path)
    args.add_argument("--expected-sha256", required=True)
    args.add_argument("--output", type=Path, required=True)
    options = args.parse_args()
    combined = preview(options.capture.read_bytes(), options.expected_sha256)
    with options.output.open("xb") as output:
        output.write(combined)
    print(json.dumps({"scope": "LOCAL_PREVIEW_ONLY", "page_id": PAGE_ID, "published": False,
                      "preview_sha256": sha256(combined).hexdigest()}))


if __name__ == "__main__":
    main()

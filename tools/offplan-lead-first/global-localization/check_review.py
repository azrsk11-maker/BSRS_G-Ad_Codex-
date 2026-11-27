"""Independently check the rendered review folder without importing its compiler."""
from collections import Counter, defaultdict
import csv
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
all_files = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
assert set(manifest["file_hashes"]) | {"manifest.json"} == all_files
for name, digest in manifest["file_hashes"].items():
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest

pages = json.loads((root / "page-review.json").read_text(encoding="utf-8"))
campaigns = json.loads((root / "campaign-review.json").read_text(encoding="utf-8"))
assert len(pages) == 69
assert len({p["proposed_wordpress_path"] for p in pages}) == len(pages)
assert len(campaigns["campaigns"]) == 35 and campaigns["default_content_language"] == "en"
assert {x["country"] for x in campaigns["geo_exclusions"]} == {"BD", "PK"}
assert all(x["country"] not in {"BD", "PK"} and x["release_status"] == "HOLD"
           and not x["config_applied_by_this_package"] for x in campaigns["campaigns"])
pools = [x["recorded_paused_average_daily_aed"] for x in campaigns["campaigns"]
         if x["recorded_paused_average_daily_aed"] is not None]
assert len(pools) == 5 and sum(pools) == campaigns["average_daily_total_aed"] == 2500
assert Counter(p["country"] for p in pages if p["default"]) == dict.fromkeys(
    [c["country"] for c in campaigns["campaigns"]], 1)


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.tags = Counter()
        self.html_attributes = {}
        self.disabled_fieldset_depth = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.tags[tag] += 1
        assert not any(key.lower().startswith("on") for key in attrs)
        assert "src" not in attrs and "action" not in attrs and "formaction" not in attrs
        if tag == "fieldset" and "disabled" in attrs:
            self.disabled_fieldset_depth += 1
        if tag in {"input", "select", "textarea", "button"}:
            assert self.disabled_fieldset_depth or "disabled" in attrs
        if tag == "html":
            self.html_attributes = attrs
        if tag == "a":
            self.links.append(attrs["href"])

    def handle_endtag(self, tag):
        if tag == "fieldset" and self.disabled_fieldset_depth:
            self.disabled_fieldset_depth -= 1


known_links = {"https://blackswanrealestate.ae/enquire/off-plan/",
               "https://blackswanrealestate.ae/property-enquiry-privacy-notice/",
               "tel:+971506878663", "https://wa.me/971506878663"}
page_index = Page()
page_index.feed((root / "index.html").read_text(encoding="utf-8"))
assert set(page_index.links) == {p["preview"] for p in pages} and len(page_index.links) == len(pages)
for page in pages:
    path = root / page["preview"]
    parsed = Page()
    web = path.read_text(encoding="utf-8")
    parsed.feed(web)
    assert parsed.html_attributes == {"lang": page["locale"], "dir": "rtl" if page["language"] == "ar" else "ltr"}
    assert parsed.tags["h1"] == parsed.tags["fieldset"] == 1
    assert parsed.tags["form"] == parsed.tags["script"] == parsed.tags["iframe"] == 0
    assert known_links <= set(parsed.links)
    assert all(link in known_links or (path.parent / link).is_file() for link in parsed.links)
    assert "noindex,nofollow" in web and "form-action 'none'" in web and "5677" not in web
    assert page["cms_page_id"] is None and page["live_url"] is None

expected_intents = {f"keyword.{i:02}" for i in range(1, 17)} | {f"uae-existing.{i:02}" for i in range(1, 9)}
allowed_variants = {(p["country"], p["locale"]) for p in pages}
intents = defaultdict(Counter)
matches = defaultdict(set)
holds = Counter()
with (root / "review-keywords.csv").open(encoding="utf-8-sig", newline="") as source:
    for row in csv.DictReader(source):
        variant = (row["country"], row["locale"])
        assert variant in allowed_variants and row["review_status"] == "PROPOSED"
        assert "{" not in row["keyword"] and "}" not in row["keyword"]
        key = (*variant, row["keyword"].casefold())
        assert row["match_type"] not in matches[key]
        matches[key].add(row["match_type"])
        if row["match_type"] == "EXACT":
            intents[variant].update(row["source_intents"].split("|"))
        for hold in filter(None, row["technical_holds"].split("|")):
            holds[hold] += 1
        if row["locale"] not in {"sw-KE", "ne-NP", "si-LK"}:
            assert not row["technical_holds"], (row["locale"], row["keyword"], row["technical_holds"])
assert set(intents) == allowed_variants
assert all(counts == dict.fromkeys(expected_intents, 1) for counts in intents.values())
assert all(types == {"EXACT", "PHRASE"} for types in matches.values())
assert len(matches) * 2 == manifest["positive_review_placements"]
with (root / "negative-keyword-glossary.csv").open(encoding="utf-8-sig", newline="") as source:
    negative = Counter()
    for r in csv.DictReader(source):
        assert r["review_status"] == "GLOSSARY_ONLY"
        negative[(r["country"], r["locale"])] += 1
assert negative == dict.fromkeys(allowed_variants, 3)
assert len(json.loads((root / "previous-localized-keyword-drafts.json").read_text(encoding="utf-8"))["positive_candidates"]) == 62
print(json.dumps({"verified": True, "files": len(all_files), "previews": len(pages), "countries": len(campaigns["campaigns"]),
                  "unique_variant_phrases": len(matches), "keyword_placements": len(matches) * 2,
                  "glossary_rows": sum(negative.values()), "technical_holds_by_reason": holds}))

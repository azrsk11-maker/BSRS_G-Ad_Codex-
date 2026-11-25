"""Check rendered language coverage, field fidelity and release separation."""
from collections import Counter, defaultdict
import csv
from html.parser import HTMLParser
from pathlib import Path
import sys
from urllib.parse import urlsplit

from compile_review import BASE_PATH, ROLES, WIRE_ROLES, FormContract, base, field_mappings

OFFPLAN_INTENTS = {f"keyword.{i:02}" for i in range(1, 17)} | {f"uae-existing.{i:02}" for i in range(1, 9)}


class Preview(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.tags = Counter()
        self.ids = set()
        self.references = []
        self.links = []
        self.attributes = {}
        self.disabled_fieldsets = 0
        self.feed(text)
        self.close()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.tags[tag] += 1
        assert tag not in {"form", "script", "iframe", "object", "embed", "img"}
        assert not any(key.lower().startswith("on") for key in attrs)
        assert not {"src", "action", "formaction", "srcset"}.intersection(attrs)
        if tag == "html":
            self.attributes = attrs
        if tag == "fieldset" and "disabled" in attrs:
            self.disabled_fieldsets += 1
        if tag in {"input", "textarea", "select", "button"}:
            assert "disabled" in attrs or self.disabled_fieldsets
        if "id" in attrs:
            assert attrs["id"] not in self.ids
            self.ids.add(attrs["id"])
        for attr in ("aria-labelledby", "aria-describedby", "for"):
            if attr in attrs:
                self.references.extend(attrs[attr].split())
        if tag == "a":
            self.links.append(attrs["href"])

    def handle_endtag(self, tag):
        if tag == "fieldset" and self.disabled_fieldsets:
            self.disabled_fieldsets -= 1


def verify_links(root, path, preview):
    allowed = {base.LIVE_ENGLISH_FORM, base.CALL, base.WHATSAPP, base.LIVE_PRIVACY}
    for href in preview.links:
        if href not in allowed:
            parts = urlsplit(href)
            assert not parts.netloc and not parts.scheme and not parts.query
            if href.startswith("#"):
                assert parts.fragment in preview.ids
            else:
                target = (path.parent / href).resolve()
                assert target.is_relative_to(root) and target.is_file()


def verify_pages(root, pages, expected_langs, mapping):
    expected = {(country, locale, role) for country, locales in expected_langs.items()
                for locale in locales for role in ROLES}
    assert len(pages) == len(expected) == 414
    assert len({page["proposed_path"] for page in pages}) == len(pages)
    keys = Counter()
    seen = set()
    home = root / "index.html"
    root_page = Preview(home.read_text(encoding="utf-8"))
    verify_links(root, home, root_page)
    assert set(root_page.links) == {p["preview"] for p in pages if p["service"] == "hub"}
    for page in pages:
        country, locale, role = (page[key] for key in ("country", "locale", "service"))
        key = (country, locale, role)
        assert key not in seen and key in expected and page["live_url"] is None
        seen.add(key)
        assert page["default"] == (locale == f"en-{country}")
        keys[(country, role)] += int(page["default"])
        assert page["release_scope"] == ("OFFPLAN_RELEASE_CANDIDATE" if role == "off-plan" else "PREPARED_HOLD")
        path = root / page["preview"]
        text = path.read_text(encoding="utf-8")
        assert f"<style>{base.STYLE}</style>" in text
        assert "noindex,nofollow" in text and "form-action 'none'" in text and "5677" not in text
        page_parser = Preview(text)
        assert page_parser.attributes == {"lang": locale, "dir": "rtl" if locale.startswith("ar-") else "ltr"}
        assert page_parser.tags["h1"] == 1
        assert set(page_parser.references) <= page_parser.ids
        verify_links(root, path, page_parser)
        if role == "hub":
            assert page_parser.tags["fieldset"] == 0
        else:
            assert page_parser.tags["fieldset"] == 1
            assert FormContract(text, "fieldset").controls == mapping[role]["control_order"], (country, locale, role)
            assert {base.CALL, base.WHATSAPP, base.LIVE_PRIVACY} <= set(page_parser.links)
    assert set(keys.values()) == {1} and len(keys) == 210
    return seen


def verify_keywords(root, sections, expected_keys, manifest):
    expected_intents = {"off-plan": OFFPLAN_INTENTS, **{
        role: {f"{role}-existing.{i:02}" for i in range(1, len(terms) + 1)}
        for role, terms in sections["keyword_intents"].items()
    }}
    declared = defaultdict(Counter)
    by_keyword = defaultdict(set)
    holds = Counter()
    placements = Counter()
    with (root / "review-keywords.csv").open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            country, locale, role = (row[key] for key in ("country", "locale", "service"))
            keyword, match = row["keyword"], row["match_type"]
            key = (country, locale, role)
            assert key in expected_keys and match in {"EXACT", "PHRASE"}
            assert row["default_language"] == str(locale == f"en-{country}")
            assert row["release_scope"] == ("OFFPLAN_RELEASE_CANDIDATE" if role == "off-plan" else "PREPARED_HOLD")
            if locale not in {"sw-KE", "ne-NP", "si-LK"}:
                assert not row["technical_holds"] and not base.keyword_issues(keyword)
            elif row["technical_holds"]:
                holds[locale] += 1
                assert "GOOGLE_AD_LANGUAGE_UNLISTED" in row["technical_holds"]
            group = (*key, keyword.casefold())
            assert match not in by_keyword[group]
            by_keyword[group].add(match)
            declared[(*key, match)].update(row["source_intents"].split("|"))
            placements[role] += 1
    assert all(matches == {"EXACT", "PHRASE"} for matches in by_keyword.values())
    assert set(declared) == {(*key, match) for key in expected_keys for match in ("EXACT", "PHRASE")}
    assert all(counts == dict.fromkeys(expected_intents[role], 1) for (_, _, role, _), counts in declared.items())
    assert sum(placements.values()) == manifest["keyword_placements"]
    return placements, holds


def main():
    root = Path(sys.argv[1]).resolve()
    manifest = base.read_json(root / "manifest.json")
    actual = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
    assert actual == set(manifest["file_hashes"]) | {"manifest.json"}
    assert all(base.digest((root / path).read_bytes()) == value for path, value in manifest["file_hashes"].items())
    assert manifest["launch_scope"] == "off-plan" and manifest["excluded_geographies"] == ["BD", "PK"]
    expected_langs = {m["code"]: m["locales"] for m in base.read_json(BASE_PATH / "MARKETS.json")["markets"]}
    campaigns = base.read_json(root / "campaign-language-review.json")
    assert len(campaigns) == 210
    assert {(c["country"], c["service"]) for c in campaigns} == {(country, role) for country in expected_langs for role in ROLES}
    for row in campaigns:
        country, role = row["country"], row["service"]
        assert row["default_content_locale"] == f"en-{country}" and row["english_keywords_required"]
        assert row["regional_content_locales"] == expected_langs[country][1:]
        assert row["release_scope"] == ("OFFPLAN_RELEASE_CANDIDATE" if role == "off-plan" else "PREPARED_HOLD")
        assert not row["live_configuration_verified_for_this_proposal"]
    budget = base.read_json(root / "campaign-review.json")
    assert budget["average_daily_total_aed"] == 2500
    assert sum(row["recorded_paused_average_daily_aed"] or 0 for row in budget["campaigns"]) == 2500
    assert {row["country"] for row in budget["geo_exclusions"]} == {"BD", "PK"}
    mapping = base.read_json(root / "field-mapping.json")
    assert set(mapping) == set(WIRE_ROLES) and field_mappings() == mapping
    pages = base.read_json(root / "page-review.json")
    expected_keys = verify_pages(root, pages, expected_langs, mapping)
    sections = base.read_json(Path(__file__).resolve().parent / "SERVICE_TEXT.json")
    placements, holds = verify_keywords(root, sections, expected_keys, manifest)
    print({"status": "PASS", "pages": len(expected_keys), "form_contracts": len(mapping),
           "checked_forms": sum(page["service"] != "hub" for page in pages),
           "campaign_locale_defaults": len(campaigns), "keyword_placements": dict(placements),
           "language_holds": dict(holds)})


if __name__ == "__main__":
    main()

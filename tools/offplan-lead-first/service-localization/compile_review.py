"""Build the regional review package for the existing service funnels using one page design."""
from __future__ import annotations

import argparse
import csv
import html
from html.parser import HTMLParser
import importlib.util
import io
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
BASE_PATH = HERE.parent / "global-localization"
ROLES = ("off-plan", "resale", "rent", "sell", "let", "hub")
AUDIT_GROUPS = {
    "resale": ("24372566774", "204397706314", "Dubai Resale Buyers"),
    "rent": ("24378494092", "204397706354", "Dubai Immediate Rentals"),
    "sell": ("24367388382", "204397706394", "Dubai Sellers"),
    "let": ("24367388382", "204397706554", "Dubai Landlords"),
    "hub": ("24378494098", "204397706114", "Black Swan Brand"),
}
FIELDS = {
    "resale": ("html.area", "html.budget", "html.property_type", "html.timeline"),
    "rent": ("html.area", "extra.annual_budget", "html.property_type", "extra.rent_timing"),
    "sell": ("extra.property_area", "html.property_type", "extra.authority", "extra.sale_timing"),
    "let": ("extra.property_area", "html.property_type", "extra.authority", "extra.let_timing"),
}
WIRE_ROLES = {"off-plan": "off_plan", "resale": "resale", "rent": "tenant", "sell": "seller", "let": "landlord"}
CONTROL_TAGS = {"input", "select", "textarea", "button"}


def load_base():
    spec = importlib.util.spec_from_file_location("bsre_global_base", BASE_PATH / "compile_review.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = load_base()


class FormContract(HTMLParser):
    """Read the fixture's original control order, wire attributes and option values."""

    def __init__(self, fragment, wrapper):
        super().__init__()
        self.wrapper = wrapper
        self.inside = False
        self.attributes = {}
        self.controls = []
        self.active_select = None
        self.feed(fragment)
        self.close()

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == self.wrapper and (tag == "form" or "disabled" in attrs):
            self.inside = True
            self.attributes = attrs
        if not self.inside:
            return
        if tag in CONTROL_TAGS:
            control = {"tag": tag, "attributes": {key: value for key, value in attrs.items() if key != "placeholder"}}
            self.controls.append(control)
            if tag == "select":
                self.active_select = control["options"] = []
        if tag == "option":
            base.check(self.active_select is not None, "Option is outside a select control")
            self.active_select.append(attrs)

    def handle_endtag(self, tag):
        if tag == self.wrapper:
            self.inside = False
        if tag == "select":
            self.active_select = None


def field_mappings():
    mapping = {}
    for role, wire_role in WIRE_ROLES.items():
        fixture = base.FORM_FIXTURE.parent / f"{role}.html"
        source = FormContract(fixture.read_text(encoding="utf-8"), "form")
        base.check(source.attributes.get("data-role") == wire_role, f"Wire role changed: {role}")
        mapping[role] = {
            "wire_role": wire_role,
            "registered_intake_path": source.attributes["data-landing-path"],
            "fixture_sha256": base.digest(fixture.read_bytes()),
            "control_order": source.controls,
        }
    return mapping


def assert_same_keys(english, localized, label):
    base.check(isinstance(localized, dict) and set(english) == set(localized), f"Locale coverage mismatch: {label}")
    for key, source_value in english.items():
        value = localized[key]
        if isinstance(source_value, dict):
            assert_same_keys(source_value, value, f"{label}.{key}")
        elif isinstance(source_value, list):
            base.check(isinstance(value, list) and len(value) == len(source_value), f"Keyword intent coverage mismatch: {label}.{key}")
            for phrase in value:
                check_text(phrase, f"{label}.{key}")
        else:
            check_text(value, f"{label}.{key}")
            base.check(value.count("*") == source_value.count("*"), f"Required field marker changed: {label}.{key}")


def check_text(value, label):
    base.check(isinstance(value, str) and value.strip() and not re.search(r"[<>{}\x00-\x1f]", value),
               f"Invalid translation: {label}")


def check_observation(english, reference):
    audit = base.SOURCE_ROOT / reference["path"]
    base.check(base.digest(audit.read_bytes()) == reference["sha256"], "Keyword observation changed")
    rows = base.read_json(audit)["keywords"]
    for role, (campaign, ad_group, name) in AUDIT_GROUPS.items():
        group = [r for r in rows if r["Campaign ID"] == campaign and r["Ad group"] == name
                 and (ad_group is None or r["Ad group ID"] == ad_group)]
        observed = {(r["Keyword"][1:-1], r["Match type"]) for r in group if r["Keyword status"] == "Paused"}
        expected = {(phrase, match) for phrase in english["keyword_intents"][role] for match in ("Exact match", "Phrase match")}
        base.check(len(group) == len(expected) and observed == expected, f"Observed keyword scope mismatch: {role}")


def source_words(compiler):
    return {text: "html." + key for key, text in compiler.HTML_TEXT.items()}


def service_text_map(role, english, localized, words, compiler):
    strings = localized["base"]
    extra = localized["service"]["extra_form"]
    replacements = {text: strings[key] for text, key in words.items()}
    common_placeholders = {text: strings[f"placeholder.{key}"] for key, text in compiler.PLACEHOLDERS.items()}
    titles = {
        "resale": ("Dubai Resale Property Buyer Enquiry", "Share your resale buying brief",
                   "For buyers seeking a Dubai resale property. A team member reviews your requirements.", "Discuss my resale search",
                   "Other property requirements ", "Preferred bedrooms, move-in plans, financing or other requirements."),
        "rent": ("Find a Dubai Rental Property", "Tell us about your rental move",
                 "For tenants looking for a home in Dubai. Availability still needs to be confirmed.", "Discuss my rental requirements",
                 "Other rental requirements ", "Preferred bedrooms, occupants, furnishing or any other requirements."),
        "sell": ("Sell Your Dubai Property", "Tell us about the property",
                 "For property owners and authorized owner representatives. Authority must be confirmed by staff.", "Discuss selling my property",
                 "Property details *", "Building or community, bedrooms, approximate size, occupancy and your selling plans. Do not include identity documents or sensitive financial information."),
        "let": ("Let Your Dubai Property", "Share your landlord enquiry",
                "For owners and authorized representatives offering a Dubai property to let.", "Discuss letting my property",
                "Property and letting details *", "Building or community, bedrooms, approximate size, furnishing and occupancy. Do not include identity documents or sensitive financial information."),
    }
    kicker, title, intro, submit, other, placeholder = titles[role]
    service_title = localized["service"]["page_titles"][role]
    other_key = {"resale": "resale_other", "rent": "rent_other", "sell": "property_details", "let": "letting_details"}[role]
    for old, value in english["extra_form"].items():
        replacements[value + (" " if old in {"sale_timing", "let_timing", "resale_other", "rent_other"} else "")] = extra[old] + (
            " " if old in {"sale_timing", "let_timing", "resale_other", "rent_other"} else "")
    replacements.update({
        kicker: service_title, title: service_title, intro: localized["service"]["page_intros"][role],
        submit: service_title, other: extra[other_key] + (" " if other.endswith(" ") else ""),
        "Your total property budget. No minimum is assumed.": strings["html.budget_hint"],
        "State an annual amount, rather than a monthly rent. No minimum is assumed.": extra["annual_budget_help"],
    })
    common_placeholders[placeholder] = (extra["property_hint"] if role in {"sell", "let"} else extra[other_key])
    return replacements, common_placeholders


class FormText(HTMLParser):
    def __init__(self, fragment, replacements, placeholders, noscript):
        super().__init__(convert_charrefs=False)
        self.starts = [0] + [match.end() for match in re.finditer("\n", fragment)]
        self.replacements = replacements
        self.placeholders = placeholders
        self.noscript_text = noscript
        self.in_noscript = False
        self.spans = []
        self.feed(fragment)
        self.close()

    def source_offset(self):
        row, column = self.getpos()
        return self.starts[row - 1] + column

    def handle_starttag(self, tag, attrs):
        if tag == "noscript":
            self.in_noscript = True
        for match in re.finditer(r'\bplaceholder="([^"]*)"', self.get_starttag_text()):
            source = html.unescape(match[1])
            self.spans.append((self.source_offset() + match.start(1), len(match[1]), self.placeholders[source]))

    def handle_endtag(self, tag):
        if tag == "noscript":
            self.in_noscript = False

    def handle_data(self, data):
        if data.strip() and data != "→":
            replacement = self.noscript_text if self.in_noscript else self.replacements[data]
            self.spans.append((self.source_offset(), len(data), replacement))


def render_form(fixture, role, locale, english, localized, compiler):
    original = compiler.form_fragment(fixture)
    captions, hints = service_text_map(role, english, localized, source_words(compiler), compiler)
    parser = FormText(original, captions, hints, localized["base"]["html.noscript"])
    output = original
    for at, width, value in sorted(parser.spans, reverse=True):
        output = output[:at] + base.esc(value) + output[at + width:]
    legend = base.esc(localized["base"]["template.preview_legend"])
    output, count = re.subn(r"<form\b[^>]*>", '<div aria-labelledby="form-title"><fieldset disabled>'
                           f"<legend>{legend}</legend>", output)
    base.check(count == 1 and output.count("</form>") == 1, f"Unexpected fixture markup: {role}")
    output = output.replace("</form>", "</fieldset></div>")
    return output.replace('id="enquiry"', f'id="enquiry" lang="{locale}"', 1)


def href_for(role, locale, from_role):
    if role == from_role:
        return f"{locale}.html"
    if from_role == "off-plan":
        return f"{role}/{locale}.html"
    if role == "off-plan":
        return f"../{locale}.html"
    return f"../{role}/{locale}.html"


def review_search_terms(country, locale, role, terms, language_ref):
    values = {}
    for index, term in enumerate(terms, 1):
        value = base.normalize_keyword(term)
        _, intents = values.setdefault(value.casefold(), (value, []))
        intents.append(f"{role}-existing.{index:02}")
    for keyword, intents in values.values():
        issues = base.keyword_issues(keyword)
        if not language_ref["google_code"]:
            issues.append("GOOGLE_AD_LANGUAGE_UNLISTED")
        for match in ("EXACT", "PHRASE"):
            yield {"country": country, "locale": locale, "service": role,
                   "default_language": locale == f"en-{country}", "keyword": keyword, "match_type": match,
                   "source_intents": "|".join(intents), "technical_holds": "|".join(issues),
                   "release_scope": "PREPARED_HOLD"}


def render_service(role, locale, market, pack, english, fixture, compiler, offplan_title):
    titles, intros, extra = (pack["service"][key] for key in ("page_titles", "page_intros", "extra_form"))
    strings = pack["base"].copy()
    e = base.esc
    title = titles[role]
    if role == "hub":
        links = [(other, offplan_title if other == "off-plan" else titles[other]) for other in ROLES if other != "hub"]
        jump = "".join(f'<li><a href="{href_for(other,locale,role)}">{e(label)}</a></li>' for other, label in links)
        header = f'<header><strong>Black Swan Real Estate</strong><nav>{base.language_navigation(market, locale)}</nav></header>'
        return base.doc(title, locale, pack["direction"], f'{header}<main><h1>{e(title)}</h1><p>{e(intros[role])}</p><ul>{jump}</ul></main>')
    strings.update({
        "page.eyebrow": titles["hub"], "page.title": title, "page.intro": intros[role],
        "page.preview_notice": strings["template.preview"], "page.contact_cta": title, "page.form_notice": "",
    })
    if locale.startswith("en-"):
        strings["page.privacy_notice"] = "Read the live privacy notice for the enquiry form."
    bullets = "".join(
        f'<li>{e((extra[key[6:]] if key.startswith("extra.") else strings[key]).rstrip(" *"))}</li>'
        for key in FIELDS[role]
    )
    copy = {"cta_url": "#enquiry", "bullets": bullets, "form": render_form(fixture, role, locale, english, pack, compiler)}
    nav = f'<a href="{href_for("hub",locale,role)}">{e(titles["hub"])}</a>'
    return base.render_enquiry_shell(market, locale, pack["direction"], strings, copy, nav_extra=nav)


def build():
    global_outputs = base.build()
    plan = base.read_json(BASE_PATH / "MARKETS.json")
    references = base.read_json(BASE_PATH / "REFERENCES.json")
    compiler = base.load_form_compiler(base.read_json(BASE_PATH / "SOURCE_TEXT.json"))
    english = base.read_json(HERE / "SERVICE_TEXT.json")
    check_observation(english, references["existing_uae_keywords"])
    locale_packs = {}
    for language in base.LANGUAGE_NAMES:
        main_pack = base.read_json(BASE_PATH / "translations" / f"{language}.json")
        service = english if language == "en" else base.read_json(HERE / "translations" / f"{language}.json")
        assert_same_keys(english, service, language)
        locale_packs[language] = {"base": main_pack["strings"], "service": service, "direction": main_pack["direction"]}
    fixtures = {
        role: (base.FORM_FIXTURE.parent / f"{role}.html").read_text(encoding="utf-8")
        for role in ROLES if role not in {"hub", "off-plan"}
    }
    outputs = {}
    index_rows, page_map, all_keywords, campaign_language_map = [], [], [], []
    for row in csv.DictReader(io.StringIO(global_outputs["review-keywords.csv"].decode("utf-8-sig"))):
        all_keywords.append(
            {"country": row["country"], "locale": row["locale"], "service": "off-plan",
             "default_language": row["locale"] == f'en-{row["country"]}', "keyword": row["keyword"],
             "match_type": row["match_type"], "source_intents": row["source_intents"],
             "technical_holds": row["technical_holds"], "release_scope": "OFFPLAN_RELEASE_CANDIDATE"}
        )
    for market in plan["markets"]:
        code = market["code"]
        for role in ROLES:
            campaign_language_map.append({
                "country": code, "service": role, "default_content_locale": f"en-{code}",
                "english_keywords_required": True,
                "regional_content_locales": market["locales"][1:],
                "release_scope": "OFFPLAN_RELEASE_CANDIDATE" if role == "off-plan" else "PREPARED_HOLD",
                "live_configuration_verified_for_this_proposal": False,
            })
        market_links = []
        for locale in market["locales"]:
            language = base.language_of(locale)
            pack = locale_packs[language]
            offplan_title = pack["base"]["page.title"]
            for role in ROLES:
                folder = f"pages/{code.lower()}"
                if role == "off-plan":
                    preview = f"{folder}/{locale}.html"
                    # Keep the reviewed off-plan rendering. Link into the local service index for navigation.
                    hub = base.esc(pack["service"]["page_titles"]["hub"])
                    outputs[preview] = global_outputs[preview].replace(
                        b"</nav>", f'<a href="hub/{locale}.html">{hub}</a></nav>'.encode("utf-8"), 1
                    )
                else:
                    preview = f"{folder}/{role}/{locale}.html"
                    outputs[preview] = render_service(role, locale, market, pack, english, fixtures.get(role),
                                                      compiler, offplan_title)
                    all_keywords.extend(
                        review_search_terms(code, locale, role, pack["service"]["keyword_intents"][role],
                                            references["language_catalog"]["criteria"][language])
                    )
                page_map.append({
                    "country": code, "locale": locale, "service": role, "preview": preview,
                    "default": locale == f"en-{code}", "release_scope": "OFFPLAN_RELEASE_CANDIDATE" if role == "off-plan" else "PREPARED_HOLD",
                    "proposed_path": f"/off-plan-dubai-{locale.lower()}/" if role == "off-plan" else f"/property-{role}-dubai-{locale.lower()}/",
                    "ad_language_listed": bool(references["language_catalog"]["criteria"][language]["google_code"]),
                    "live_url": None,
                })
            market_links.append(
                f'<a href="pages/{code.lower()}/hub/{locale}.html" lang="{locale}">'
                f'{base.esc(base.LANGUAGE_NAMES[language])}{" (default)" if locale == f"en-{code}" else ""}</a>'
            )
        index_rows.append(f'<tr><th scope="row">{base.esc(market["name"])}</th><td>{" · ".join(market_links)}</td></tr>')
    outputs["index.html"] = base.doc(
        "Dubai property landing-page previews", "en", "ltr",
        '<main><h1>Dubai property landing-page previews</h1>'
        '<p>Choose a country and language to review off-plan, resale, rental, seller and landlord pages. English is the default in each market.</p>'
        '<p>Off-plan is the only launch scope. The other services are prepared for review.</p>'
        '<table><thead><tr><th scope="col">Market</th><th scope="col">Languages</th></tr></thead><tbody>'
        + "".join(index_rows) + '</tbody></table></main>',
    )
    outputs["page-review.json"] = base.json_bytes(page_map)
    outputs["field-mapping.json"] = base.json_bytes(field_mappings())
    outputs["campaign-language-review.json"] = base.json_bytes(campaign_language_map)
    outputs["review-keywords.csv"] = base.csv_bytes(all_keywords)
    outputs["campaign-review.json"] = global_outputs["campaign-review.json"]
    outputs["negative-keyword-glossary.csv"] = global_outputs["negative-keyword-glossary.csv"]
    outputs["previous-localized-keyword-drafts.json"] = global_outputs["previous-localized-keyword-drafts.json"]
    outputs["manifest.json"] = base.json_bytes({
        "scope": "REVIEW_ONLY", "countries": len(plan["markets"]), "role_variants": len(ROLES), "previews": len(page_map),
        "english_defaults": sum(page["default"] for page in page_map),
        "supported_language_keyword_placements": sum("GOOGLE_AD_LANGUAGE_UNLISTED" not in r["technical_holds"] for r in all_keywords),
        "keyword_placements": len(all_keywords), "keyword_placements_on_technical_hold": sum(bool(r["technical_holds"]) for r in all_keywords),
        "launch_scope": "off-plan", "excluded_geographies": sorted(base.EXCLUSIONS),
        "file_hashes": {path: base.digest(data) for path, data in outputs.items()},
    })
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    output = args.out.resolve()
    source = base.SOURCE_ROOT.resolve()
    base.check(not output.is_relative_to(source) and not source.is_relative_to(output), "Place review files outside the source checkout")
    outputs = build()
    if args.verify:
        actual = {path.relative_to(output).as_posix(): path for path in output.rglob("*") if path.is_file()}
        base.check(set(actual) == set(outputs) and all(not path.is_symlink() and path.read_bytes() == outputs[name]
                   for name, path in actual.items()), "Review files differ")
    else:
        output.mkdir(parents=True, exist_ok=False)
        for name, data in outputs.items():
            destination = output / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
    manifest = json.loads(outputs["manifest.json"])
    print(json.dumps({key: val for key, val in manifest.items() if key != "file_hashes"}))


if __name__ == "__main__":
    main()

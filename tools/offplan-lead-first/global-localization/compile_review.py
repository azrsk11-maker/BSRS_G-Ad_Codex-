"""Build offline editorial previews and keyword review files for the off-plan market list."""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import importlib.util
import io
import json
from pathlib import Path
import re
import unicodedata

HERE = Path(__file__).resolve().parent
SOURCE_ROOT = HERE.parents[2]
OFFPLAN = SOURCE_ROOT / "tools/offplan-lead-first"
FORM_FIXTURE = SOURCE_ROOT / "tools/staging-lab/fixtures/bsre-enquiries/templates/source/off-plan.html"
LIVE_ENGLISH_FORM = "https://blackswanrealestate.ae/enquire/off-plan/"
LIVE_PRIVACY = "https://blackswanrealestate.ae/property-enquiry-privacy-notice/"
CALL = "tel:+971506878663"
WHATSAPP = "https://wa.me/971506878663"
TARGETS = frozenset("AT BH BE CA CN EG FR DE HK IN ID IE JP KE KW MY NP NL NG OM PH QA SA SG ZA KR LK CH TW TH TR AE GB US VN".split())
EXCLUSIONS = frozenset(("BD", "PK"))
EXPECTED_LOCALES = {
    **{code: ("ar-" + code,) for code in "BH EG KW OM QA SA AE".split()},
    "AT": ("de-AT",), "BE": ("nl-BE", "fr-BE"), "CA": ("fr-CA",),
    "CN": ("zh-Hans-CN",), "FR": ("fr-FR",), "DE": ("de-DE",),
    "HK": ("zh-Hant-HK",), "IN": ("hi-IN",), "ID": ("id-ID",),
    "JP": ("ja-JP",), "KE": ("sw-KE",), "MY": ("ms-MY",), "NP": ("ne-NP",),
    "NL": ("nl-NL",), "PH": ("fil-PH",), "SG": ("zh-Hans-SG",), "KR": ("ko-KR",),
    "LK": ("si-LK", "ta-LK"), "CH": ("de-CH", "fr-CH", "it-CH"), "TW": ("zh-Hant-TW",),
    "TH": ("th-TH",), "TR": ("tr-TR",), "VN": ("vi-VN",),
}
LANGUAGE_NAMES = {
    "en": "English", "ar": "العربية", "de": "Deutsch", "fr": "Français",
    "nl": "Nederlands", "it": "Italiano", "tr": "Türkçe", "sw": "Kiswahili",
    "id": "Bahasa Indonesia", "zh-Hans": "简体中文", "zh-Hant-HK": "香港繁體中文",
    "zh-Hant-TW": "臺灣繁體中文", "hi": "हिन्दी", "ja": "日本語", "ko": "한국어",
    "ne": "नेपाली", "ms": "Bahasa Melayu", "fil": "Filipino", "si": "සිංහල",
    "ta": "தமிழ்", "th": "ไทย", "vi": "Tiếng Việt",
}
STYLE = """
:root{color-scheme:light;--ink:#182a24;--muted:#46594f;--paper:#fbf9f5;--line:#d8e0d7;--accent:#215d43}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:1rem/1.6 system-ui,sans-serif}
main,header{max-width:66rem;margin:auto;padding:1rem clamp(1rem,4vw,2.5rem)}
header{display:flex;justify-content:space-between;align-items:center;gap:1rem;flex-wrap:wrap;border-bottom:1px solid var(--line)}
nav{display:flex;gap:.75rem;flex-wrap:wrap}a{color:var(--accent)}a:focus-visible,summary:focus-visible{outline:3px solid #ad6000;outline-offset:3px}
[aria-current=page]{font-weight:700}h1{font-size:clamp(1.9rem,5vw,3.55rem);line-height:1.17;margin:.3em 0}
h2{font-size:1.35rem;margin-top:1.7rem}p,ul,ol{max-width:75ch}summary{cursor:pointer;font-weight:650}
.note{background:#f1ece0;border-inline-start:4px solid #995f18;padding:.75rem 1rem}
.actions{display:flex;gap:.75rem;flex-wrap:wrap;margin:1rem 0}.actions a{border:1px solid var(--accent);border-radius:.4rem;padding:.5rem .8rem}
.form-card,details.preferences{background:white;border:1px solid var(--line);padding:1rem;border-radius:.55rem;margin:1rem 0}
fieldset{margin:0;padding:.75rem;border:1px solid var(--line)}.field-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(13rem,1fr));gap:.75rem}
label{display:block}input:not([type=checkbox]),textarea,select{display:block;width:100%;margin:.2rem 0 .65rem;padding:.45rem;font:inherit}
input:disabled,textarea:disabled,select:disabled{color:#45564e;background:#f1f3ef}button{font:inherit}.field small{color:var(--muted)}
.honeypot{display:none}
table{width:100%;border-collapse:collapse}th,td{text-align:start;border-bottom:1px solid var(--line);padding:.55rem;vertical-align:top}
"""
PUNCTUATION = str.maketrans({"’": "'", "‘": "'", "‑": "-", "–": "-", "\u3000": " "})


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(data) -> bytes:
    return (json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_pairs)


def check(condition, problem):
    if not condition:
        raise ValueError(problem)


def language_of(locale):
    return locale if locale in {"zh-Hant-HK", "zh-Hant-TW"} else locale.rsplit("-", 1)[0]


def validate_market_plan(plan, references):
    check(plan["account_id"] == "573-038-4686" and plan["intent"] == "OFF_PLAN_BUYERS_ONLY", "Unexpected account or campaign intent")
    check(plan["default_language"] == "en" and plan["average_daily_budget_aed"] == 2500, "English default or budget changed")
    countries = plan["markets"]
    excluded = plan["excluded_geographies"]
    check(len(countries) == 35 and {x["code"] for x in countries} == TARGETS, "Incorrect geography allowlist")
    check(len(excluded) == 2 and {x["code"] for x in excluded} == EXCLUSIONS, "Incorrect geography exclusions")
    for market in countries:
        code = market["code"]
        check(market["locales"] == [f"en-{code}", *EXPECTED_LOCALES.get(code, ())], f"Unexpected locale mix for {code}")
    geo = references["geo_catalog"]["criteria"]
    check(set(geo) == TARGETS | EXCLUSIONS and len({x["id"] for x in geo.values()}) == 37, "Geo references incomplete or duplicated")
    check(all(g["status"] == "Active" for g in geo.values()), "Geo reference has inactive entries")
    check(len(references["existing_uae_keywords"]["records"]) == 8, "Existing keyword source is incomplete")


def load_form_compiler(source_text):
    tool_path = OFFPLAN / "form-localization/compile_form.py"
    check(digest(tool_path.read_bytes()) == source_text["source_form_compiler_sha256"], "Form compiler input changed")
    spec = importlib.util.spec_from_file_location("bsre_form_text", tool_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_uae_observation(existing):
    path = SOURCE_ROOT / existing["path"]
    check(digest(path.read_bytes()) == existing["sha256"], "Existing UAE keyword observation changed")
    rows = [
        row for row in read_json(path)["keywords"]
        if row["Campaign ID"] == "24372566774" and row["Ad group ID"] == "204397706154"
    ]
    observed = {
        (row["Keyword"][1:-1], {"Exact match": "EXACT", "Phrase match": "PHRASE"}[row["Match type"]])
        for row in rows if row["Keyword status"] == "Paused"
    }
    declared = {
        (record["english"], match)
        for record in existing["records"] for match in record["saved_match_types"]
    }
    check(len(rows) == len(observed) == 16 and observed == declared, "UAE keywords do not match the paused off-plan ad group")


def validate_translation(language, pack, canonical, source_hash, markets):
    strings = pack["strings"]
    check(pack["language_code"] == language and pack["source_text_sha256"] == source_hash, f"Source binding mismatch in {language}")
    check(pack["schema"] == "bsre-global-language-pack-v1", f"Invalid language pack {language}")
    check(pack["status"] == "DRAFT_REQUIRES_COMPETENT_REVIEW" and pack["direction"] == ("rtl" if language == "ar" else "ltr"), f"Invalid editorial status or direction in {language}")
    required = {key for key in canonical if not key.startswith("lead.")}
    check(required <= set(strings) <= set(canonical), f"Missing required translations or unexpected keys in {language}")
    for key, value in strings.items():
        check(isinstance(value, str) and value.strip() and not re.search(r"[<>\x00-\x1f]", value), f"Invalid plain text {language}:{key}")
        check(value.count("{origin}") == canonical[key].count("{origin}"), f"Incorrect origin placeholder {language}:{key}")
        check(not any(c in value.replace("{origin}", "") for c in "{}"), f"Unexpected placeholder {language}:{key}")
    check(set(pack["origins"]) == markets, f"Wrong origin modifiers for {language}")
    check(all(isinstance(origin, str) and origin.strip() and not re.search(r"[<>{}\x00-\x1f]", origin) for origin in pack["origins"].values()), f"Invalid origin in {language}")
    check(len(pack["existing_uae_keywords"]) == 8 and all(isinstance(s, str) and s.strip() for s in pack["existing_uae_keywords"]), f"Incomplete existing keyword equivalents in {language}")


def esc(value):
    return html.escape(value, quote=True)


def doc(title, locale, direction, body):
    return (
        f'<!doctype html>\n<html lang="{esc(locale)}" dir="{direction}">\n<head>\n'
        '<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">\n'
        '<meta name="robots" content="noindex,nofollow">\n'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; form-action \'none\'; base-uri \'none\'">\n'
        f'<title>{esc(title)}</title><style>{STYLE}</style>\n</head><body>{body}</body></html>\n'
    ).encode("utf-8")


def language_navigation(market, locale):
    links = []
    for variant in market["locales"]:
        label = LANGUAGE_NAMES[language_of(variant)]
        current = ' aria-current="page"' if variant == locale else ""
        links.append(f'<a href="{variant}.html" lang="{variant}" hreflang="{variant}"{current}>{esc(label)}</a>')
    return "".join(links)


def render_enquiry_shell(market, locale, direction, strings, copy, extras="", nav_extra=""):
    """Render the same language bar, hero, contact actions, form and consent region for every enquiry."""
    t = lambda key: esc(strings[key])
    form_notice = f'<p>{t("page.form_notice")}</p>' if strings["page.form_notice"] else ""
    preferences = (
        f'<details class="preferences"><summary>{t("consent.toggle")}</summary>'
        f'<p>{t("consent.intro")}</p>'
        + "".join(
            f'<label><input type="checkbox" disabled> {t(f"consent.{purpose}")} '
            f'<span>{t(f"consent.{purpose}_description")}</span></label>' for purpose in ("analytics", "ads")
        )
        + f'<p>{t("consent.separation")}</p>'
        f'<p>{t("consent.duration")}</p><p><a href="{LIVE_PRIVACY}">{t("consent.privacy")}</a></p>'
        f'<button disabled>{t("consent.reject")}</button> <button disabled>{t("consent.save")}</button></details>'
    )
    body = (
        f'<header><strong>Black Swan Real Estate</strong><nav>{language_navigation(market, locale)}{nav_extra}</nav></header>'
        f'<main><p class="note">{t("page.preview_notice")}</p><p>{t("page.eyebrow")}</p>'
        f'<h1>{t("page.title")}</h1><p>{t("page.intro")}</p><div class="actions">'
        f'<a href="{copy["cta_url"]}">{t("page.contact_cta")}</a>'
        f'<a href="{CALL}">{t("page.call_cta")}</a><a href="{WHATSAPP}">{t("page.whatsapp_cta")}</a></div>'
        f'{extras}<h2>{t("page.details_title")}</h2><ul>{copy["bullets"]}</ul>{copy.get("details", "")}'
        f'{form_notice}{copy["form"]}'
        f'<p>{t("page.privacy_notice")} <a href="{LIVE_PRIVACY}">{t("template.privacy_link")}</a></p>'
        f'{preferences}</main>'
    )
    return doc(strings["page.title"], locale, direction, body)


def render_page(market, locale, pack, fixture, form_compiler):
    strings = pack["strings"].copy()
    if pack["language_code"] == "en":
        strings["page.preview_notice"] = "Unpublished review preview. Enquiry submission and measurement are disabled."
        strings["page.form_notice"] = "The link above opens the live enquiry form. The form below is a disabled preview."
        strings["page.privacy_notice"] = "Read the live privacy notice for the enquiry form."
    t = lambda key: esc(strings[key])
    raw_form = form_compiler.localize_form(fixture, strings, locale)
    # Keep the actual labels and control constraints, but present the draft as static markup.
    review_form, count = re.subn(r'<form\b[^>]*>', '<div aria-labelledby="form-title">', raw_form)
    check(count == 1 and review_form.count("</form>") == 1, "Form fixture markup changed")
    review_form = review_form.replace("</form>", "</div>")
    bullets = "".join(f'<li>{t(f"page.detail_{i}")}</li>' for i in range(1, 5))
    steps = "".join(f'<li>{t(f"page.step_{i}")}</li>' for i in range(1, 4))
    faqs = "".join(
        f'<details><summary>{t(f"page.faq_{topic}_q")}</summary><p>{t(f"page.faq_{topic}_a")}</p></details>'
        for topic in ("project", "price", "qualification")
    )
    copy = {"cta_url": LIVE_ENGLISH_FORM, "bullets": bullets, "form": review_form,
            "details": f'<h2>{t("page.steps_title")}</h2><ol>{steps}</ol>{faqs}'}
    extras = f'<h2>{t("page.plans_title")}</h2><p>{t("page.plans_body")}</p>'
    return render_enquiry_shell(market, locale, pack["direction"], strings, copy, extras)


def normalize_keyword(value):
    return " ".join(unicodedata.normalize("NFC", value.translate(PUNCTUATION)).split())


def keyword_issues(value):
    issues = []
    if len(value) > 80 or len(value.encode("utf-8")) > 255 or len(value.split()) > 10:
        issues.append("REVIEW_LENGTH")
    if not value or not all(
        unicodedata.category(c)[0] in {"L", "M", "N"} or c in " _-'&+./·・" for c in value
    ):
        issues.append("REVIEW_CHARACTERS")
    return issues


def review_rows(market, locale, pack, recorded_keywords, google_language):
    strings, code = pack["strings"], market["code"]
    origin = pack["origins"][code]
    translated = [(f"keyword.{i:02d}", strings[f"keyword.{i:02d}"].replace("{origin}", origin)) for i in range(1, 17)]
    translated += [(record["intent_id"], text) for record, text in zip(recorded_keywords, pack["existing_uae_keywords"], strict=True)]
    grouped = {}
    for intent, keyword in translated:
        clean = normalize_keyword(keyword)
        key = clean.casefold()
        if key not in grouped:
            grouped[key] = (clean, [])
        grouped[key][1].append(intent)
    for keyword, intents in grouped.values():
        holds = keyword_issues(keyword)
        if not google_language["google_code"]:
            holds.append("GOOGLE_AD_LANGUAGE_UNLISTED")
        for match_type in ("EXACT", "PHRASE"):
            yield {
                "country": code, "locale": locale, "keyword": keyword, "match_type": match_type,
                "source_intents": "|".join(intents), "review_status": "PROPOSED", "technical_holds": "|".join(holds),
            }


def csv_bytes(rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        check(not any(isinstance(v, str) and v.startswith(("=", "+", "-", "@", "\t", "\r")) for v in row.values()), "Unsafe CSV cell")
        writer.writerow(row)
    return stream.getvalue().encode("utf-8-sig")


def build():
    source_text = read_json(HERE / "SOURCE_TEXT.json")
    canonical = source_text["strings"]
    plan = read_json(HERE / "MARKETS.json")
    references = read_json(HERE / "REFERENCES.json")
    validate_market_plan(plan, references)
    form_compiler = load_form_compiler(source_text)
    check(set(source_text["form_keys"]) == form_compiler.REQUIRED, "Unexpected form translation key set")
    prior_file = OFFPLAN / "keywords.json"
    check(digest(prior_file.read_bytes()) == source_text["source_keywords_sha256"], "Previous keyword catalogue changed")
    prior = read_json(prior_file)
    existing = references["existing_uae_keywords"]
    verify_uae_observation(existing)
    fixture = FORM_FIXTURE.read_text(encoding="utf-8")
    applied = read_json(OFFPLAN / "native-paused/APPLIED.json")
    pools = {row["country"]: row for row in applied["campaigns"]}
    check(set(pools) == {"AE", "DE", "FR", "IN", "TW"}, "Unexpected applied pools")
    check(sum(row["average_daily_budget_AED"] for row in pools.values()) == 2500 and
          all(row["status"] == "Paused" for row in pools.values()), "Recorded paused pools changed")
    countries_by_language = {language: set() for language in LANGUAGE_NAMES}
    for market in plan["markets"]:
        for locale in market["locales"]:
            countries_by_language[language_of(locale)].add(market["code"])
    languages = references["language_catalog"]["criteria"]
    check(set(languages) == set(LANGUAGE_NAMES), "Unexpected language reference coverage")
    check({path.stem for path in (HERE / "translations").glob("*.json")} == set(LANGUAGE_NAMES), "Missing or unexpected language packs")
    packs = {language: read_json(HERE / "translations" / f"{language}.json") for language in LANGUAGE_NAMES}
    source_hash = digest((HERE / "SOURCE_TEXT.json").read_bytes())
    for language, pack in packs.items():
        validate_translation(language, pack, canonical, source_hash, countries_by_language[language])

    outputs = {}
    keywords, negatives, page_rows, campaign_review, index_rows = [], [], [], [], []
    for market in plan["markets"]:
        code = market["code"]
        existing_pool = pools.get(code, {})
        variants = []
        for locale in market["locales"]:
            language = language_of(locale)
            pack = packs[language]
            preview = f"pages/{code.lower()}/{locale}.html"
            proposal_path = f"/off-plan-dubai-{locale.lower()}/"
            outputs[preview] = render_page(market, locale, pack, fixture, form_compiler)
            variant = {
                "locale": locale, "language": language, "default": locale == f"en-{code}",
                "preview": preview, "proposed_wordpress_path": proposal_path, "cms_page_id": None,
                "live_url": None, "status": "UNPUBLISHED_REVIEW_PREVIEW",
                "platform_language_listed": languages[language]["google_code"] is not None,
                "translated_receipt_message_count": sum(k.startswith("lead.") for k in pack["strings"]),
            }
            variants.append(variant)
            page_rows.append({"country": code, **variant})
            keywords.extend(review_rows(market, locale, pack, existing["records"], languages[language]))
            for i in range(1, 4):
                key = f"negative.{i:02d}"
                negatives.append({"country": code, "locale": locale, "intent": key,
                                  "translation": pack["strings"][key], "review_status": "GLOSSARY_ONLY"})
        target = references["geo_catalog"]["criteria"][code]
        campaign_review.append({
            "country": code, "market": market["name"], "geo_reference": target,
            "presence_targeting_requested": True, "default_content_locale": f"en-{code}",
            "proposed_content_locales": market["locales"], "recorded_campaign_id": existing_pool.get("id"),
            "recorded_paused_average_daily_aed": existing_pool.get("average_daily_budget_AED"),
            "release_status": "HOLD", "config_applied_by_this_package": False,
        })
        links = " · ".join(
            f'<a href="{v["preview"]}" lang="{v["locale"]}">{esc(LANGUAGE_NAMES[v["language"]])}'
            f'{" (default)" if v["default"] else ""}</a>'
            f'{" (website draft)" if not v["platform_language_listed"] else ""}'
            for v in variants
        )
        index_rows.append(f'<tr><th scope="row">{esc(market["name"])}</th><td>{links}</td></tr>')

    outputs["index.html"] = doc(
        "Off-plan landing page previews", "en", "ltr",
        "<main><h1>Off-plan landing page previews</h1>"
        "<p>English is the default content for each market. Choose a language to review the landing page and its disabled enquiry form.</p>"
        "<p>Geographic exclusions: Bangladesh and Pakistan.</p>"
        "<table><thead><tr><th>Market</th><th>Language previews</th></tr></thead><tbody>"
        + "".join(index_rows) + "</tbody></table></main>",
    )
    outputs["review-keywords.csv"] = csv_bytes(keywords)
    outputs["negative-keyword-glossary.csv"] = csv_bytes(negatives)
    outputs["previous-localized-keyword-drafts.json"] = json_bytes(prior)
    outputs["page-review.json"] = json_bytes(page_rows)
    outputs["campaign-review.json"] = json_bytes({
        "scope": "OFF_PLAN_BUYERS_ONLY", "account_id": plan["account_id"],
        "average_daily_total_aed": 2500, "default_content_language": "en",
        "status": "REVIEW_ONLY", "campaigns": campaign_review,
        "geo_exclusions": [{"country": item["code"], **references["geo_catalog"]["criteria"][item["code"]]}
                           for item in plan["excluded_geographies"]],
        "other_campaigns": "KEEP_PAUSED_OR_REMOVED", "providers_contacted": False,
    })
    outputs["manifest.json"] = json_bytes({
        "scope": "OFFLINE_CONTENT_REVIEW", "markets": len(campaign_review), "previews": len(page_rows),
        "english_defaults": sum(p["default"] for p in page_rows), "languages": len(packs),
        "positive_source_intents_per_variant": 24, "positive_review_placements": len(keywords),
        "positive_placements_with_technical_holds": sum(bool(k["technical_holds"]) for k in keywords),
        "prior_positive_drafts_preserved": len(prior["positive_candidates"]),
        "negative_glossary_rows": len(negatives), "geographic_exclusions": sorted(EXCLUSIONS),
        "file_hashes": {path: digest(data) for path, data in outputs.items()},
    })
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    out = args.out.resolve()
    check(not out.is_relative_to(SOURCE_ROOT.resolve()) and not SOURCE_ROOT.resolve().is_relative_to(out),
          "Place generated review files outside the source checkout")
    outputs = build()
    if args.verify:
        actual = {p.relative_to(out).as_posix(): p for p in out.rglob("*") if p.is_file()}
        check(set(actual) == set(outputs), "Output inventory mismatch")
        check(all(not p.is_symlink() and p.read_bytes() == outputs[name] for name, p in actual.items()),
              "Generated review files differ")
    else:
        out.mkdir(parents=True, exist_ok=False)
        for name, data in outputs.items():
            destination = out / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
    receipt = json.loads(outputs["manifest.json"])
    print(json.dumps({key: value for key, value in receipt.items() if key != "file_hashes"}))


if __name__ == "__main__":
    main()

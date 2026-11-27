"""Offline, text-only off-plan form localization; no deployment binding or I/O clients."""
from __future__ import annotations

import argparse
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
LOCALES = ("de-DE", "fr-FR", "zh-Hant-TW")
FIXTURE = "tools/staging-lab/fixtures/bsre-enquiries/"
HTML_TEXT = {
    "kicker": "Dubai Off-Plan Property Enquiry",
    "title": "Tell us about your next purchase",
    "intro": "For buyers planning a purchase. Your requirements are reviewed by the team.",
    "required_note": "Fields marked * are required. No minimum budget is imposed by this form.",
    "name": "Full name *", "phone": "Phone number *",
    "phone_hint": "Use a number where the team can contact you.",
    "country": "Country of residence *", "email": "Email address ",
    "optional": "(optional)", "area": "Preferred Dubai areas *",
    "budget": "Total purchase budget (AED) *",
    "budget_hint": "Your total property budget, not just a deposit. No minimum is assumed.",
    "property_type": "Property type *", "select": "Please select",
    "apartment": "Apartment", "townhouse": "Townhouse", "villa": "Villa",
    "other": "Other / to discuss", "timeline": "When do you plan to buy? *",
    "month_1": "Within 1 month", "month_1_3": "In 1–3 months",
    "month_3_6": "In 3–6 months", "month_6_plus": "More than 6 months / exploring",
    "details": "Add further preferences (optional)", "funding": "Funding position ",
    "cash": "Cash / own funds", "mortgage_arranged": "Mortgage arranged",
    "mortgage_needed": "Mortgage to be arranged", "discuss": "To discuss",
    "property_details": "Preferred handover / other requirements ",
    "honeypot": "Leave this field empty",
    "contact": "I request contact from Black Swan Real Estate about this enquiry by phone, WhatsApp or email. *",
    "marketing": "I would also like property news and offers from Black Swan Real Estate. ",
    "submit": "Discuss my off-plan purchase",
    "purpose": "Enquiry contact and optional marketing are separate choices. Do not include identity documents or sensitive financial information.",
}
PLACEHOLDERS = {
    "name": "Your name", "phone": "Include country code", "country": "Your current country",
    "email": "If you prefer email", "area": "Community or area", "budget": "Your indicative budget",
    "property_details": "Share preferred bedrooms, handover timing or other requirements.",
}
LEAD = {
    "unsent": "Unpublished preview — your enquiry has not been sent. This draft does not save or transmit your details. You can contact Black Swan Real Estate using the telephone or WhatsApp links.",
    "required": "Please check the required enquiry details and contact consent before submitting.",
    "unaccepted": "We could not accept this enquiry. Please use the telephone or WhatsApp contact option.",
    "secure": "This browser could not prepare a secure enquiry. Please use the telephone or WhatsApp contact option.",
    "changed_details": "Receipt of your earlier attempt is still unconfirmed. Some details have changed, so they have not been resent. Restore the original details to retry the same request, or contact us by phone or WhatsApp to check it. This prevents a duplicate enquiry.",
    "changed_analytics": "Receipt of your earlier attempt is still unconfirmed, and your analytics consent has changed. To respect your current choice, this request cannot be resent with its original attribution. Please contact us by phone or WhatsApp to check the earlier enquiry.",
    "changed_ads": "Receipt of your earlier attempt is still unconfirmed, and your advertising permission has changed. Please contact us by phone or WhatsApp to check that enquiry before sending another request.",
    "sending_button": "Sending enquiry…", "sending_status": "Sending your enquiry securely…",
    "validation": "The service rejected these details before accepting the enquiry. Please review your required fields and consent, then submit again. Your next corrected attempt will receive a new request reference.",
    "conflict": "The service could not reconcile this request reference. Your details have not been resent under a new reference. Please contact us by phone or WhatsApp to check the enquiry.",
    "received": "Enquiry received", "receipt_prefix": "Your enquiry has been received. Reference: ",
    "receipt_suffix": ". Black Swan Real Estate can now review your request. This receipt does not confirm property availability or qualification.",
    "uncertain": "We could not confirm receipt. Your enquiry may not have been accepted. Please retry; the same request reference will be reused to prevent a duplicate, or contact us by phone or WhatsApp.",
}
CONSENT = {
    "unavailable": "Optional measurement is off. Preferences could not be verified. You can still send an enquiry.",
    "saving": "Saving your preferences. Optional measurement stays off until confirmed.",
    "pending": "Optional measurement is off. This browser could not clear its pending change; save again.",
    "saved": "Your preferences are saved. You can change them here at any time.",
    "unconfirmed": "Optional measurement is off in this browser. The server has not confirmed this change. Keep this page open or return to preferences and save again.",
    "aria": "Optional measurement preferences", "toggle": "Measurement preferences",
    "heading": "Optional measurement",
    "intro": "Choose optional measurement for these property enquiry pages. Your enquiry works if you reject optional measurement.",
    "analytics": "Analytics", "analytics_description": "Measure visits and enquiry interactions to improve these pages.",
    "ads": "Ad measurement", "ads_description": "Measure ad clicks and accepted enquiries. This does not enable personalized advertising.",
    "separation": "Personalized advertising is off. These choices are separate from permission to contact you about your enquiry and optional marketing contact.",
    "duration": "Preferences last up to 180 days. This is separate from the retention period for enquiry records.",
    "privacy": "Read the property enquiry privacy notice",
    "reject": "Reject optional measurement", "save": "Save choices", "close": "Close preferences",
}
TEMPLATE_KEYS = ("privacy_before", "privacy_link", "privacy_after", "preview", "preview_legend", "live_note", "unavailable")
GROUPS = {"html": HTML_TEXT, "placeholder": PLACEHOLDERS, "lead": LEAD, "consent": CONSENT}
REQUIRED = {f"{group}.{key}" for group, items in GROUPS.items() for key in items}
REQUIRED |= {"html.noscript"} | {f"template.{key}" for key in TEMPLATE_KEYS}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key: " + key)
        result[key] = value
    return result


def load_catalog(path: Path = HERE / "translations.json") -> dict:
    catalog = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    if set(catalog) != {"schema", "locales", "strings"} or catalog["schema"] != "bsre-offplan-form-text-v1":
        raise ValueError("Invalid catalog schema or extra top-level keys")
    if catalog["locales"] != list(LOCALES):
        raise ValueError("Missing or extra locale")
    strings = catalog["strings"]
    if set(strings) != REQUIRED:
        raise ValueError(f"missing={sorted(REQUIRED - set(strings))}; extra={sorted(set(strings) - REQUIRED)}")
    normalized = {locale: {} for locale in LOCALES}
    for key, values in strings.items():
        if not isinstance(values, list) or len(values) != len(LOCALES):
            raise ValueError(f"{key}: missing or extra locale translation")
        for locale, value in zip(LOCALES, values):
            if not isinstance(value, str) or not value.strip() or any(ord(c) < 32 for c in value):
                raise ValueError(f"{locale}/{key}: empty, non-string or control character")
            if any(c in value for c in "<>"):
                raise ValueError(f"{locale}/{key}: markup is forbidden in plain text")
            normalized[locale][key] = value
    return {"schema": catalog["schema"], "locales": normalized}


def read_base(source_root: Path) -> tuple[dict, dict[str, bytes]]:
    manifest = json.loads((HERE / "BASE_MANIFEST.json").read_text(encoding="utf-8"))
    files = {}
    for name, expected in manifest["base_sha256"].items():
        data = (source_root / name).read_bytes()
        if sha(data) != expected:
            raise ValueError(f"Pinned base drift: {name}")
        files[name] = data
    return manifest, files


def form_fragment(source: str) -> str:
    start = source.index('<div class="form-card" id="enquiry">')
    stop = source.index("</form></div>", start) + len("</form></div>")
    return source[start:stop]


class TextSpans(HTMLParser):
    """Record exact source offsets; leave every tag/constraint/wire value untouched."""
    def __init__(self, source: str):
        super().__init__(convert_charrefs=False)
        self.source = source
        self.line_starts = [0] + [m.end() for m in re.finditer("\n", source)]
        self.records = []
        self.in_noscript = False
        self.feed(source)

    def source_offset(self) -> int:
        line, col = self.getpos()
        return self.line_starts[line - 1] + col

    def handle_starttag(self, tag, attrs):
        if tag == "noscript":
            self.in_noscript = True
        raw = self.get_starttag_text()
        for match in re.finditer(r'\bplaceholder="([^"]*)"', raw):
            value = html.unescape(match.group(1))
            keys = [key for key, old in PLACEHOLDERS.items() if old == value]
            if len(keys) != 1:
                raise ValueError("Unexpected placeholder")
            self.records.append((self.source_offset() + match.start(1), len(match.group(1)), "placeholder." + keys[0]))

    def handle_endtag(self, tag):
        if tag == "noscript":
            self.in_noscript = False

    def handle_data(self, data):
        if not data.strip() or data == "→":
            return
        keys = [key for key, old in HTML_TEXT.items() if old == data]
        key = "noscript" if self.in_noscript else keys[0] if len(keys) == 1 else None
        if key is None:
            raise ValueError("Unexpected form text: " + repr(data[:60]))
        self.records.append((self.source_offset(), len(data), "html." + key))


def localize_form(source: str, strings: dict, locale: str) -> str:
    fragment = form_fragment(source)
    spans = TextSpans(fragment).records
    found = {key for _, _, key in spans}
    expected = {"html." + key for key in HTML_TEXT} | {"placeholder." + key for key in PLACEHOLDERS} | {"html.noscript"}
    if found != expected:
        raise ValueError("Missing or extra form text span")
    for offset, size, key in sorted(spans, reverse=True):
        fragment = fragment[:offset] + html.escape(strings[key], quote=True) + fragment[offset + size:]
    fragment = fragment.replace('<div class="form-card" id="enquiry">', '<div class="form-card" id="enquiry" lang="' + locale + '">', 1)
    # Separate preview guard: existing lead.init enables the submit button, so a
    # disabled enclosing fieldset must remain effective even on such a host.
    fragment = re.sub(r'(<form\b[^>]*>)', lambda match: match.group(1) + '<fieldset disabled><legend>' + html.escape(strings['template.preview_legend'], quote=True) + '</legend>', fragment, count=1)
    fragment = fragment.replace('</form>', '</fieldset></form>', 1)
    return fragment + "\n"


def js_literal(value: str) -> str:
    return json.dumps(value, ensure_ascii=False).replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def localize_js(source: str, group: str, strings: dict) -> tuple[str, list]:
    # Simultaneous edits at exact quoted source tokens; never touch a translated result again.
    changes = []
    for key, old in GROUPS[group].items():
        needle = "'" + old.replace("\\", "\\\\").replace("'", "\\'") + "'"
        if source.count(needle) != 1:
            raise ValueError(f"{group}/{key}: expected exactly one pinned literal")
        changes.append((source.index(needle), needle, js_literal(strings[group + "." + key])))
    result = source
    for offset, old, new in sorted(changes, reverse=True):
        result = result[:offset] + new + result[offset + len(old):]
    return result, changes


def outputs(source_root: Path, catalog_path: Path = HERE / "translations.json") -> dict[str, bytes]:
    catalog = load_catalog(catalog_path)
    base, files = read_base(source_root)
    result = {}
    for locale in LOCALES:
        strings = catalog["locales"][locale]
        result[locale + "/form.html"] = localize_form(files[FIXTURE + "templates/source/off-plan.html"].decode("utf-8"), strings, locale).encode("utf-8")
        for group, asset in (("lead", "lead.js"), ("consent", "consent-bridge.js")):
            text, _ = localize_js(files[FIXTURE + "assets/" + asset].decode("utf-8"), group, strings)
            # Preserve the fixture's exact newline bytes and every nontranslated character.
            result[locale + "/" + asset] = text.encode("utf-8")
        result[locale + "/template-strings.json"] = json_bytes({key: strings["template." + key] for key in TEMPLATE_KEYS})
    result["MANIFEST.json"] = json_bytes({
        "schema": "bsre-offplan-form-candidate-v1", "status": "PRIVATE_PREPARATION_INTEGRATION_HELD",
        "source_head": base["source_head"], "source_tree": base["source_tree"],
        "base_sha256": base["base_sha256"], "catalog_sha256": sha(catalog_path.read_bytes()),
        "locales": list(LOCALES), "strings_per_locale": len(REQUIRED),
        "output_sha256": {name: sha(data) for name, data in result.items()},
        "installed": False, "live_verified": False, "production_write": False,
        "native_validation": "Browser-provided constraint messages remain browser controlled; client/server status strings are localized.",
        "preview_guard": "Added enclosing disabled fieldset and translated legend; existing control attributes and wire values unchanged.",
        "binding": {"CMS_page_id": None, "locale_route": None, "asset_registration": None, "privacy_translation": None, "contact_readback": None},
    })
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=HERE.parents[2])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root, target = args.source_root.resolve(), args.out.resolve()
    if root == target or root in target.parents:
        raise ValueError("Output must be outside Source; native fixture/runtime changes are prohibited")
    expected = outputs(root)
    if args.check:
        actual_names = {p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file()}
        if actual_names != set(expected):
            raise ValueError("Missing or extra generated file")
        for name, data in expected.items():
            if (target / name).read_bytes() != data:
                raise ValueError("Generated byte mismatch: " + name)
    else:
        # Refuse to overwrite a populated directory: inspect an ambiguous prior write first.
        if target.exists() and any(target.iterdir()):
            raise ValueError("Output directory is populated; use --check or a new explicit directory")
        for name, data in expected.items():
            path = target / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    print(json.dumps({"status": "PASS", "files": len(expected), "locales": len(LOCALES), "strings_per_locale": len(REQUIRED), "check": args.check}))


if __name__ == "__main__":
    main()

"""Focused offline contract checks; no browser, transport or production calls."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("offplan_form_compile", HERE / "compile_form.py")
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
SOURCE = Path(os.environ.get("BSRE_FORM_SOURCE_ROOT", str(HERE.parents[2]))).resolve()


class Markup(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, tuple(attrs)))

    def handle_endtag(self, tag):
        self.tags.append(("/" + tag, ()))


class FormLocalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog_raw = json.loads((HERE / "translations.json").read_text(encoding="utf-8"))
        cls.catalog = c.load_catalog()
        cls.base, cls.files = c.read_base(SOURCE)
        cls.rendered = c.outputs(SOURCE)
        cls.source_html = cls.files[c.FIXTURE + "templates/source/off-plan.html"].decode("utf-8")
        cls.fragment = c.form_fragment(cls.source_html)

    def modified_catalog(self, mutate):
        catalog = copy.deepcopy(self.catalog_raw)
        mutate(catalog)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.json"
            path.write_bytes(c.json_bytes(catalog))
            return c.load_catalog(path)

    def test_01_output_inventory_and_hashes(self):
        manifest = json.loads(self.rendered["MANIFEST.json"])
        self.assertEqual(13, len(self.rendered))
        self.assertEqual(85, manifest["strings_per_locale"])
        self.assertEqual(set(self.rendered) - {"MANIFEST.json"}, set(manifest["output_sha256"]))
        for name, expected in manifest["output_sha256"].items():
            self.assertEqual(expected, c.sha(self.rendered[name]))

    def test_02_deterministic_bytes(self):
        self.assertEqual(self.rendered, c.outputs(SOURCE))

    def test_03_all_markup_and_protocol_attributes_unchanged(self):
        baseline = Markup(self.fragment).tags
        def normalized(tags):
            return [(tag, tuple((key, value) for key, value in attrs if key not in {"lang", "placeholder"})) for tag, attrs in tags if tag not in {"fieldset", "/fieldset", "legend", "/legend"}]
        for locale in c.LOCALES:
            tags = Markup(self.rendered[locale + "/form.html"].decode("utf-8")).tags
            self.assertEqual(normalized(baseline), normalized(tags))
            langs = [dict(attrs)["lang"] for _, attrs in tags if "lang" in dict(attrs)]
            self.assertEqual([locale], langs)

    def test_04_field_names_wire_options_and_validation_constraints(self):
        def controls(text):
            return [(tag, dict(attrs)) for tag, attrs in Markup(text).tags if tag in {"form", "input", "select", "option", "textarea", "button"}]
        baseline = controls(self.fragment)
        for locale in c.LOCALES:
            translated = controls(self.rendered[locale + "/form.html"].decode("utf-8"))
            for (_, before), (_, after) in zip(baseline, translated):
                before.pop("placeholder", None)
                after.pop("placeholder", None)
            self.assertEqual(baseline, translated)
        values = [attrs.get("value") for tag, attrs in baseline if tag == "option"]
        self.assertEqual(["", "Apartment", "Townhouse", "Villa", "Other / to discuss", "", "Within 1 month", "In 1–3 months", "In 3–6 months", "More than 6 months / exploring", "", "Cash / own funds", "Mortgage arranged", "Mortgage to be arranged", "To discuss"], values)

    def test_05_contact_mandatory_marketing_optional_and_unchecked(self):
        for locale in c.LOCALES:
            fields = {dict(attrs).get("name"): dict(attrs) for tag, attrs in Markup(self.rendered[locale + "/form.html"].decode("utf-8")).tags if tag == "input"}
            self.assertIn("required", fields["contact_consent"])
            self.assertNotIn("required", fields["marketing_consent"])
            self.assertNotIn("checked", fields["contact_consent"])
            self.assertNotIn("checked", fields["marketing_consent"])

    def test_06_client_inverse_restores_all_protocol_and_event_bytes(self):
        for locale in c.LOCALES:
            strings = self.catalog["locales"][locale]
            for group, asset in (("lead", "lead.js"), ("consent", "consent-bridge.js")):
                original = self.files[c.FIXTURE + "assets/" + asset].decode("utf-8")
                localized, changes = c.localize_js(original, group, strings)
                self.assertEqual(localized.encode("utf-8"), self.rendered[locale + "/" + asset])
                restored = localized
                for _, old, new in changes:
                    self.assertEqual(1, restored.count(new))
                    restored = restored.replace(new, old, 1)
                self.assertEqual(original.encode("utf-8"), restored.encode("utf-8"))

    def test_07_form_has_no_script_link_endpoint_or_phone_number(self):
        for locale in c.LOCALES:
            text = self.rendered[locale + "/form.html"].decode("utf-8")
            self.assertNotRegex(text, r"(?i)<(?:script|iframe|a)\b|https?://|tel:|wa\.me/|\+971|BSRELeadConfig")
            form = next(dict(attrs) for tag, attrs in Markup(text).tags if tag == "form")
            self.assertEqual("#", form["action"])
            self.assertEqual("/enquire/off-plan/", form["data-landing-path"])
            self.assertEqual("off_plan", form["data-role"])

    def test_08_all_pinned_files_reject_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, data in self.files.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            for name, data in self.files.items():
                path = root / name
                path.write_bytes(data + b"\n")
                with self.assertRaisesRegex(ValueError, "Pinned base drift"):
                    c.read_base(root)
                path.write_bytes(data)

    def test_09_missing_translation_key_rejected(self):
        with self.assertRaisesRegex(ValueError, "missing="):
            self.modified_catalog(lambda doc: doc["strings"].pop("lead.validation"))

    def test_10_extra_translation_key_rejected(self):
        with self.assertRaisesRegex(ValueError, "extra="):
            self.modified_catalog(lambda doc: doc["strings"].update({"lead.extra": ["a", "b", "c"]}))

    def test_11_missing_or_extra_locale_translation_rejected(self):
        for size in (2, 4):
            with self.subTest(size=size), self.assertRaisesRegex(ValueError, "missing or extra locale translation"):
                self.modified_catalog(lambda doc: doc["strings"].update({"html.name": ["x"] * size}))
        with self.assertRaisesRegex(ValueError, "Missing or extra locale"):
            self.modified_catalog(lambda doc: doc["locales"].append("ru-RU"))

    def test_12_blank_markup_controls_nonstring_rejected(self):
        for value in ("", "   ", "<b>x</b>", "x\ny", 4):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.modified_catalog(lambda doc: doc["strings"]["html.name"].__setitem__(0, value))

    def test_13_unmapped_new_form_text_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "Unexpected form text"):
            c.localize_form(self.source_html.replace("Full name *", "New source label", 1), self.catalog["locales"]["de-DE"], "de-DE")

    def test_14_inert_binding_and_language_domains(self):
        manifest = json.loads(self.rendered["MANIFEST.json"])
        self.assertFalse(manifest["installed"])
        self.assertFalse(manifest["live_verified"])
        self.assertFalse(manifest["production_write"])
        self.assertTrue(all(value is None for value in manifest["binding"].values()))
        self.assertEqual(["de-DE", "fr-FR", "zh-Hant-TW"], manifest["locales"])

    def test_15_attribute_and_text_escaping(self):
        strings = dict(self.catalog["locales"]["de-DE"])
        strings["html.name"] = 'A & B "name"'
        strings["placeholder.name"] = 'A & B "placeholder"'
        text = c.localize_form(self.source_html, strings, "de-DE")
        self.assertIn("A &amp; B &quot;name&quot;", text)
        field = next(dict(attrs) for tag, attrs in Markup(text).tags if tag == "input" and dict(attrs).get("name") == "name")
        self.assertEqual(strings["placeholder.name"], field["placeholder"])

    def test_16_cli_rejects_source_output_without_mutation(self):
        result = subprocess.run([sys.executable, "-B", str(HERE / "compile_form.py"), "--source-root", str(SOURCE), "--out", str(SOURCE / "tools/offplan-lead-first/form-localization/test-output")], capture_output=True, text=True, encoding="utf-8")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("Output must be outside Source", result.stderr)
        self.assertFalse((SOURCE / "tools/offplan-lead-first/form-localization/test-output").exists())

    def test_17_all_template_strings_are_inert_and_present(self):
        for locale in c.LOCALES:
            strings = json.loads(self.rendered[locale + "/template-strings.json"])
            self.assertEqual(set(c.TEMPLATE_KEYS), set(strings))
            self.assertNotIn("href", strings)
            self.assertNotIn("privacyUrl", strings)

    def test_18_missing_duplicate_client_literal_rejected(self):
        original = self.files[c.FIXTURE + "assets/lead.js"].decode("utf-8")
        for mutated in (original.replace("'Sending enquiry…'", "'New source'"), original + "\n'Sending enquiry…';"):
            with self.assertRaisesRegex(ValueError, "expected exactly one pinned literal"):
                c.localize_js(mutated, "lead", self.catalog["locales"]["de-DE"])

    def test_19_every_explicit_client_status_literal_is_covered(self):
        consent = self.files[c.FIXTURE + "assets/consent-bridge.js"].decode("utf-8")
        calls = re.findall(r'\bsetMessage\(([^\n]*)\);', consent)
        visible = {value for call in calls for value in re.findall(r"'([^']*)'", call)}
        self.assertEqual(5, len(visible))
        self.assertTrue(visible.issubset(set(c.CONSENT.values())))
        lead = self.files[c.FIXTURE + "assets/lead.js"].decode("utf-8")
        status_calls = re.findall(r"showStatus\(status, '([^']*)'", lead)
        self.assertEqual(12, len(status_calls))
        self.assertTrue(set(status_calls).issubset(set(c.LEAD.values())))

    def test_20_added_disabled_fieldset_guards_every_control(self):
        for locale in c.LOCALES:
            tags = Markup(self.rendered[locale + "/form.html"].decode("utf-8")).tags
            self.assertEqual(1, sum(tag == "fieldset" for tag, _ in tags))
            inside = False
            for tag, attrs in tags:
                if tag == "fieldset":
                    self.assertEqual({"disabled": None}, dict(attrs))
                    inside = True
                elif tag == "/fieldset":
                    inside = False
                elif tag in {"input", "select", "textarea", "button"}:
                    self.assertTrue(inside)
            self.assertIn(self.catalog["locales"][locale]["template.preview_legend"], self.rendered[locale + "/form.html"].decode("utf-8"))

    def test_21_duplicate_json_key_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.json"
            raw = (HERE / "translations.json").read_text(encoding="utf-8")
            raw = raw.replace('"strings": {', '"strings": {}, "strings": {', 1)
            path.write_text(raw, encoding="utf-8", newline="\n")
            with self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
                c.load_catalog(path)


if __name__ == "__main__":
    unittest.main()

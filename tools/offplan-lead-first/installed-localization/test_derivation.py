"""Focused tests of the new installed-preimage/contact/selector boundaries."""
from html.parser import HTMLParser
import json
import os
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import derive_localization as d


class Controls(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.controls, self.fieldsets = [], []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        if tag in {"form", "input", "select", "option", "textarea", "button"}:
            self.controls.append((tag, tuple((key, value) for key, value in attrs if key != "placeholder")))
        if tag == "fieldset":
            self.fieldsets.append(dict(attrs))


class InstalledDerivationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path(os.environ.get("BSRE_FORM_SOURCE_ROOT", ".")).resolve()
        test_scope = os.environ.get("BSRE_LOCALIZATION_TEST_SCOPE")
        cls.temp = tempfile.TemporaryDirectory(prefix="locale-derivation-", dir=test_scope)
        cls.scope = Path(cls.temp.name).resolve()
        if test_scope:
            assert cls.scope.is_relative_to(Path(test_scope).resolve())
        cls.installed = cls.scope / "SYNTHETIC-preimages"
        fixture = cls.source / "tools/staging-lab/fixtures/bsre-enquiries"
        for name in d.PREIMAGES:
            # Explicit synthetic test input. This does not observe installed bytes.
            data = (fixture / name).read_bytes().replace(b"971568285677", b"971506878663").replace(b"+971 56 828 5677", b"+971 50 687 8663")
            d.checked_member(name, data)
            target = cls.installed / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        cls.audit_path = cls.scope / "SYNTHETIC-editor-audit.json"
        cls.extra_audit_path = cls.scope / "SYNTHETIC-extra-audit.json"
        size, digest = d.PREIMAGES["assets/lead.js"]
        audit = {
            "synthetic_test_fixture": True, "version_header": "0.2.12", "measurement_controls": "ALL_OFF", "code_saved": False,
            "method": "SYNTHETIC test data, not an authenticated observation", "representation_limit": "No live identity proof",
            "observed_at_utc": "2000-01-01T00:00:00Z", "lead_contact": {"approved8663_present": True, "old5677_absent": True},
            "files": [{"path": "assets/lead.js", "bytes": size, "sha256": digest}] + [{"path": "SYNTHETIC/member-" + str(i), "bytes": 0, "sha256": "0" * 64} for i in range(8)],
        }
        extra = {
            "synthetic_test_fixture": True, "raw_server_byte_identity_claimed": False, "observed_at_utc": "2000-01-01T00:00:00Z",
            "files": [{"path": name, "bytes": d.PREIMAGES[name][0], "sha256": d.PREIMAGES[name][1]} for name in ("assets/consent-bridge.js", "templates/source/off-plan.html")],
        }
        cls.audit_path.write_bytes(d.json_bytes(audit))
        cls.extra_audit_path.write_bytes(d.json_bytes(extra))
        cls.compiler, cls.catalog, cls.inputs, cls.audit, _ = d.load_inputs(cls.source, cls.installed, cls.audit_path, cls.extra_audit_path)
        cls.outputs = d.build_outputs(cls.source, cls.installed, cls.audit_path, cls.extra_audit_path)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_known_installed_lead_contact_preimage_is_accepted(self):
        original = self.inputs["assets/lead.js"]
        self.assertEqual(original, d.checked_member("assets/lead.js", original))
        self.assertIn(b"971506878663", original)
        self.assertNotIn(b"971568285677", original)

    def test_old_frozen_fixture_lead_is_rejected(self):
        original = (self.source / "tools/staging-lab/fixtures/bsre-enquiries/assets/lead.js").read_bytes()
        with self.assertRaisesRegex(d.GuardError, "PREIMAGE_MISMATCH"):
            d.checked_member("assets/lead.js", original)

    def test_single_byte_drift_and_unknown_member_rejected(self):
        for name, data in [("assets/lead.js", self.inputs["assets/lead.js"] + b"\n"), ("assets/unknown.js", b"")]:
            with self.subTest(name=name), self.assertRaisesRegex(d.GuardError, "PREIMAGE_MISMATCH"):
                d.checked_member(name, data)

    def test_forged_or_duplicate_editor_member_is_rejected(self):
        for mutation in ("hash", "duplicate", "contact", "measurement"):
            audit = json.loads(self.audit_path.read_text(encoding="utf-8"))
            if mutation == "hash":
                audit["files"][0]["sha256"] = "0" * 64
            elif mutation == "duplicate":
                audit["files"][1] = audit["files"][0]
            elif mutation == "contact":
                audit["lead_contact"]["old5677_absent"] = False
            else:
                audit["measurement_controls"] = "ON"
            original_reader = d.read_bounded
            def read(path, limit=50000):
                return d.json_bytes(audit) if Path(path) == self.audit_path else original_reader(path, limit)
            with self.subTest(mutation=mutation), patch.object(d, "read_bounded", side_effect=read), self.assertRaises(d.GuardError):
                d.load_inputs(self.source, self.installed, self.audit_path, self.extra_audit_path)

    def test_duplicate_json_keys_rejected(self):
        with self.assertRaisesRegex(d.GuardError, "DUPLICATE_JSON_KEY"):
            json.loads('{"files":[],"files":[]}', object_pairs_hook=d.unique_object)

    def test_compiler_or_catalog_drift_is_rejected(self):
        for filename in ("compile_form.py", "translations.json"):
            reader = d.read_bounded
            def read(path, limit=50000):
                data = reader(path, limit)
                return data + b"\n" if Path(path).name == filename else data
            with self.subTest(filename=filename), patch.object(d, "read_bounded", side_effect=read), self.assertRaisesRegex(d.GuardError, "COMPILER_DRIFT|CATALOG_DRIFT"):
                d.load_inputs(self.source, self.installed, self.audit_path, self.extra_audit_path)

    def test_client_derivations_reverse_to_exact_actual_preimages(self):
        inverses = json.loads(self.outputs["JS_TEXT_INVERSES.json"])
        self.assertEqual(6, len(inverses))
        for name, inverse in inverses.items():
            original = d.reverse_js(self.outputs[name].decode("utf-8"), inverse["edits"]).encode("utf-8")
            self.assertEqual(self.inputs["assets/" + name.split("/")[1]], original)
            self.assertEqual(inverse["preimage_sha256"], d.sha(original))

    def test_inverse_rejects_tampered_translated_span(self):
        inverse = json.loads(self.outputs["JS_TEXT_INVERSES.json"])["de-DE/lead.js"]
        output = self.outputs["de-DE/lead.js"].decode("utf-8")
        first = min(inverse["edits"], key=lambda item: item["offset"])
        output = output[:first["offset"]] + "!" + output[first["offset"] + 1:]
        with self.assertRaisesRegex(d.GuardError, "INVERSE_SPAN_MISMATCH"):
            d.reverse_js(output, inverse["edits"])

    def test_approved_contact_matcher_is_preserved_in_every_locale(self):
        for locale in d.LOCALES:
            output = self.outputs[locale + "/lead.js"]
            self.assertEqual(self.inputs["assets/lead.js"].count(b"971506878663"), output.count(b"971506878663"))
            self.assertNotIn(b"971568285677", output)

    def test_form_preserves_all_protocol_controls_and_stays_disabled(self):
        original = Controls(self.compiler.form_fragment(self.inputs["templates/source/off-plan.html"].decode("utf-8")))
        for locale in d.LOCALES:
            text = self.outputs[locale + "/form.html"].decode("utf-8")
            output = Controls(text)
            self.assertEqual(original.controls, output.controls)
            self.assertEqual([{"disabled": None}], output.fieldsets)
            self.assertIn('data-landing-path="/enquire/off-plan/"', text)
            self.assertIn('data-role="off_plan"', text)
            self.assertIn('lang="' + locale + '"', text)

    def test_deterministic_outputs_and_complete_manifest(self):
        self.assertEqual(self.outputs, d.build_outputs(self.source, self.installed, self.audit_path, self.extra_audit_path))
        manifest = json.loads(self.outputs["MANIFEST.json"])
        self.assertEqual(16, len(self.outputs))
        self.assertEqual(set(self.outputs) - {"MANIFEST.json"}, set(manifest["output_sha256"]))
        self.assertEqual(85, manifest["strings_per_locale"])
        for name, expected in manifest["output_sha256"].items():
            self.assertEqual(expected, d.sha(self.outputs[name]))

    def test_all_three_preimages_are_current_editor_bound_but_deployment_is_held(self):
        manifest = json.loads(self.outputs["MANIFEST.json"])
        self.assertTrue(all(member["current_editor_bound"] for member in manifest["preimages"].values()))
        self.assertFalse(manifest["installed"])
        self.assertFalse(manifest["live_PHP_integration_implemented"])
        self.assertFalse(json.loads(self.outputs["DEPLOYMENT_REJECTIONS.json"])["deployment_allowed"])

    def test_omitted_supplemental_preimages_stay_explicitly_held(self):
        outputs = d.build_outputs(self.source, self.installed, self.audit_path, None)
        manifest = json.loads(outputs["MANIFEST.json"])
        for name in ("assets/consent-bridge.js", "templates/source/off-plan.html"):
            self.assertFalse(manifest["preimages"][name]["current_editor_bound"])
            self.assertIn("CURRENT_PREIMAGE_NOT_VERIFIED:" + name, json.loads(outputs["DEPLOYMENT_REJECTIONS.json"])["reasons"])

    def test_supplemental_preimage_drift_is_rejected(self):
        extra = json.loads(self.extra_audit_path.read_text(encoding="utf-8"))
        extra["files"][1]["sha256"] = "0" * 64
        reader = d.read_bounded
        def read(path, limit=50000):
            return d.json_bytes(extra) if Path(path) == self.extra_audit_path else reader(path, limit)
        with patch.object(d, "read_bounded", side_effect=read), self.assertRaisesRegex(d.GuardError, "SUPPLEMENTAL_EDITOR_PREIMAGE_MISMATCH"):
            d.load_inputs(self.source, self.installed, self.audit_path, self.extra_audit_path)

    def test_only_authorized_descendant_outside_source_is_allowed(self):
        self.assertEqual(self.scope / "generated", d.safe_output_path(self.scope / "generated", self.scope, self.source))
        for target, scope in ((self.scope, self.scope), (self.scope.parent / "escape", self.scope), (self.source / "generated", self.source)):
            with self.subTest(target=target), self.assertRaisesRegex(d.GuardError, "OUTPUT_OUTSIDE_PRIVATE_OWNERSHIP|OUTPUT_INSIDE_SOURCE"):
                d.safe_output_path(target, scope, self.source)

    def test_existing_code_directory_cannot_be_overwritten(self):
        with patch.object(Path, "exists", return_value=True), patch.object(Path, "is_dir", return_value=True), patch.object(Path, "iterdir", return_value=iter([Path("keep")])), self.assertRaisesRegex(d.GuardError, "OUTPUT_ALREADY_POPULATED"):
            d.write_or_check(self.scope / "protected-output", self.outputs, False, self.scope, self.source)

    def test_written_inventory_reconciles_and_tampering_is_rejected(self):
        target = self.scope / "generated"
        d.write_or_check(target, self.outputs, False, self.scope, self.source)
        d.write_or_check(target, self.outputs, True, self.scope, self.source)
        (target / "de-DE/lead.js").write_bytes(b"tampered")
        with self.assertRaisesRegex(d.GuardError, "OUTPUT_INVENTORY_OR_BYTES_MISMATCH"):
            d.write_or_check(target, self.outputs, True, self.scope, self.source)

    def test_output_check_rejects_symlink_members(self):
        target = self.scope / "symlink-check"
        d.write_or_check(target, self.outputs, False, self.scope, self.source)
        with patch.object(Path, "is_symlink", return_value=True), self.assertRaisesRegex(d.GuardError, "OUTPUT_SYMLINK_MEMBER"):
            d.write_or_check(target, self.outputs, True, self.scope, self.source)


class LocaleSelectionTests(unittest.TestCase):
    def test_exact_locales_on_existing_route_only(self):
        for locale in d.LOCALES:
            for target in (d.INTAKE_PATH + "?bsre_locale=" + locale, d.INTAKE_PATH + "?utm_source=search&bsre_locale=" + locale + "&gclid=opaque"):
                self.assertEqual(locale, d.resolve_locale(target))

    def test_invalid_ambiguous_and_off_route_queries_use_english(self):
        targets = [
            d.INTAKE_PATH, "/off-plan-dubai-de/?bsre_locale=de-DE", "/enquire/resale/?bsre_locale=de-DE",
            "https://blackswanrealestate.ae/enquire/off-plan/?bsre_locale=de-DE",
            d.INTAKE_PATH + "?bsre_locale=de-DE&bsre_locale=fr-FR",
            d.INTAKE_PATH + "?bsre_locale[]=de-DE", d.INTAKE_PATH + "?bsre_locale=de-DE&bsre_locale[x]=fr-FR",
            d.INTAKE_PATH + "?%62sre_locale=de-DE", d.INTAKE_PATH + "?bsre.locale=de-DE",
            d.INTAKE_PATH + "?bsre_locale=de-de", d.INTAKE_PATH + "?bsre_locale=zh-TW", d.INTAKE_PATH + "?bsre_locale=en-IN",
            d.INTAKE_PATH + "?bsre_locale=%64e-DE", d.INTAKE_PATH + "?bsre_locale=de-DE%00", d.INTAKE_PATH + "?bsre_locale=de-DE#x",
            d.INTAKE_PATH + "?bsre_locale=de-DE;bsre_locale=fr-FR", d.INTAKE_PATH + "?bsre_locale=de-DE&x=%ZZ",
            d.INTAKE_PATH + "?bsre_locale", d.INTAKE_PATH + "?bsre_locale=", d.INTAKE_PATH + "?bsre_locale=de-DE&%FF=x",
            d.INTAKE_PATH + "?bsre_locale=de-DE&" + "&".join("x=1" for _ in range(32)),
            d.INTAKE_PATH + "?bsre_locale=de-DE&x=" + "a" * 4096, None,
            d.INTAKE_PATH + "?bsre_locale%00=fr-FR&bsre_locale=de-DE",
        ]
        for target in targets:
            with self.subTest(target=repr(target)[:100]):
                self.assertEqual("en", d.resolve_locale(target))

    def test_selector_is_presentation_only_and_emits_no_urls(self):
        with patch("builtins.open", side_effect=AssertionError("selector attempted file IO")):
            result = d.resolve_locale(d.INTAKE_PATH + "?bsre_locale=de-DE&gclid=opaque")
        self.assertEqual("de-DE", result)
        self.assertNotIn("?", result)
        self.assertNotIn("/", result)



if __name__ == "__main__":
    unittest.main()

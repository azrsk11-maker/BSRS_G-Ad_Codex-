"""Synthetic source and fixture checks for the paired-worker history handoff."""

from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import ModuleType
import unittest
from unittest.mock import patch

import keyword_history_reuse as reuse


def digest(value):
    return sha256(json.dumps(value, sort_keys=True).encode("ascii")).hexdigest()


class KeywordHistoryReuseTests(unittest.TestCase):
    def setUp(self):
        temporary = self.enterContext(TemporaryDirectory(prefix="keyword-history-reuse-"))
        self.folder = Path(temporary).resolve() / "keyword-system"
        self.folder.mkdir()
        modules = {}
        pins = {}
        for name in (*reuse.SOURCE_PINS, reuse.APPEND_ONLY, reuse.BANK_STAGE, reuse.FRONT_STAGE):
            path = self.folder / f"{name}.py"
            source = f"# Synthetic fixture {name}\n".encode("ascii")
            path.write_bytes(source)
            if name in reuse.SOURCE_PINS:
                pins[name] = sha256(source).hexdigest()
            modules[name] = ModuleType(name)
            modules[name].__file__ = str(path)
        self.modules = modules

        self.bank = self.fixture_class(reuse.BANK_MODULE, reuse.BANK_CLASS, reuse.BANK_STAGE)
        self.front = self.fixture_class(reuse.FRONT_MODULE, reuse.FRONT_CLASS, reuse.FRONT_STAGE)
        self.front_ids = [f"{reuse.FRONT_MODULE}.{reuse.FRONT_CLASS}.test_synthetic"]
        self.bank.when = date(2026, 11, 13)
        self.bank.base = {"records": [{"test": "prior"}]}
        self.bank.inputs = {"records": [{"test": "prior"}, {"test": "bank"}]}
        modules[reuse.APPEND_ONLY].digest = digest
        modules[reuse.BANK_STAGE].BASE_SHA256 = digest(self.bank.base)
        modules[reuse.FRONT_STAGE].BASE_SHA256 = digest(self.bank.inputs)

        self.enterContext(patch.dict(sys.modules, modules))
        self.enterContext(patch.multiple(reuse, CANONICAL_FOLDER=self.folder, SOURCE_PINS=pins,
            BANK_BASE_SHA256=digest(self.bank.base), FRONT_BASE_SHA256=digest(self.bank.inputs)))

    def fixture_class(self, name, class_name, stage):
        def test_synthetic(self):
            pass

        test_class = type(class_name, (unittest.TestCase,), {"__module__": name,
            "FRESH_BASE": None, "FRESH_INPUTS": None, "test_synthetic": test_synthetic})
        module = self.modules[name]
        setattr(module, class_name, test_class)
        module.e = self.modules[stage]
        module.stage = self.modules[reuse.APPEND_ONLY]
        module.current = self.modules[reuse.CURRENT]
        return test_class

    def assert_fallback(self, bank_verified=True, front_ids=None):
        with reuse.reuse_bank_history(self.folder, bank_verified,
                                     self.front_ids if front_ids is None else front_ids) as bound:
            self.assertFalse(bound)

    def test_detaches_nested_data_and_restores_override_when_front_raises(self):
        with self.assertRaisesRegex(RuntimeError, "synthetic front error"):
            with reuse.reuse_bank_history(self.folder, True, self.front_ids) as bound:
                self.assertTrue(bound)
                self.assertEqual(self.front.FRESH_BASE, self.bank.inputs)
                self.assertIsNone(self.front.FRESH_INPUTS)
                self.front.FRESH_BASE["records"][0]["test"] = "front"
                self.assertEqual(self.bank.inputs["records"][0]["test"], "prior")
                self.assert_fallback()
                self.assertEqual(self.front.FRESH_BASE["records"][0]["test"], "front")
                raise RuntimeError("synthetic front error")
        self.assertIsNone(self.front.FRESH_BASE)

    def test_requires_the_callers_bank_proof_and_exact_front_ids(self):
        self.assert_fallback(bank_verified=False)
        for ids in ([], self.front_ids * 2, [self.front_ids[0] + "_changed"]):
            with self.subTest(ids=ids):
                self.assert_fallback(front_ids=ids)
        self.assertIsNone(self.front.FRESH_BASE)

    def test_rejects_changed_source_missing_source_and_alternate_folder(self):
        self.assertTrue(reuse.pair_sources_match(self.folder))
        self.assertFalse(reuse.pair_sources_match(self.folder.parent))
        source = self.folder / f"{reuse.CURRENT}.py"
        source.write_bytes(source.read_bytes() + b"# Synthetic change\n")
        self.assertFalse(reuse.pair_sources_match(self.folder))
        self.assert_fallback()
        source.unlink()
        self.assertFalse(reuse.pair_sources_match(self.folder))

    def test_no_import_or_override_when_loaded_bank_source_does_not_match(self):
        with patch.dict(sys.modules, {reuse.BANK_MODULE: None}):
            self.assert_fallback()
        with patch.object(self.modules[reuse.BANK_MODULE], "__file__",
                          str(self.folder / f"{reuse.FRONT_MODULE}.py")):
            self.assert_fallback()
        self.assertIsNone(self.front.FRESH_BASE)

    def test_rejects_fixture_digest_and_definition_pin_drift(self):
        for field in ("base", "inputs"):
            with self.subTest(field=field), patch.object(self.bank, field, {"records": []}):
                self.assert_fallback()
        for name in (reuse.BANK_STAGE, reuse.FRONT_STAGE):
            with self.subTest(name=name), patch.object(self.modules[name], "BASE_SHA256", "changed"):
                self.assert_fallback()
        self.assertIsNone(self.front.FRESH_BASE)

    def test_preserves_existing_front_overrides_on_fallback(self):
        for field in ("FRESH_BASE", "FRESH_INPUTS"):
            marker = object()
            with self.subTest(field=field), patch.object(self.front, field, marker):
                self.assert_fallback()
                self.assertIs(getattr(self.front, field), marker)


if __name__ == "__main__":
    unittest.main()

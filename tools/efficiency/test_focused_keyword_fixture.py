"""Focused tool boundaries; these tests never reconstruct keyword history."""
import contextlib
import io
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import py_compile
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import focused_keyword_fixture as tool


class FocusedKeywordFixtureTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.run = self.root / 'run'; self.run.mkdir()

    def bind_toy_input(self):
        path = self.root / 'tools/keyword-system/fixture.py'
        path.parent.mkdir(parents=True); path.write_bytes(b'public-synthetic-input')
        profile = {'files': {'tools/keyword-system/fixture.py':
                            {'bytes': path.stat().st_size, 'sha256': tool.sha(path.read_bytes())}}}
        return path, profile

    def test_unsupported_profile_holds_before_keyword_import(self):
        with patch.object(tool, 'import_selected', side_effect=AssertionError('must not import')):
            with self.assertRaisesRegex(tool.Hold, 'UNSUPPORTED_FOCUSED_PROFILE'):
                tool.main(['--root', str(self.root), '--profile', 'arbitrary-module', '--inspect'])

    def test_profile_byte_mutation_is_not_an_array_certificate(self):
        with patch.object(tool, 'PROFILE_SHA256', '0' * 64):
            with self.assertRaisesRegex(tool.Hold, 'FOCUSED_PROFILE_CHANGED'):
                tool.load_profile()

    def test_input_byte_drift_holds_before_consumption(self):
        path, profile = self.bind_toy_input()
        with patch.multiple(tool, SOURCE=self.root, PROFILE=profile):
            snapshot = tool.source_snapshot()
            self.assertEqual(snapshot['file_count'], 1)
            path.write_bytes(b'X' * path.stat().st_size)
            with self.assertRaisesRegex(tool.Hold, 'FOCUSED_INPUT_CHANGED'):
                tool.source_snapshot()

    def test_oversized_input_declaration_holds_without_loading_it(self):
        path, profile = self.bind_toy_input()
        profile['files']['tools/keyword-system/fixture.py']['bytes'] = 65 * 1024 * 1024
        with patch.multiple(tool, SOURCE=self.root, PROFILE=profile), self.assertRaisesRegex(tool.Hold, 'FOCUSED_FILE_BOUND_EXCEEDED'):
            tool.source_snapshot()

    def test_bounded_reader_refuses_extra_bytes(self):
        path = self.root / 'large-fixture'; path.write_bytes(b'12345')
        with self.assertRaisesRegex(tool.Hold, 'FOCUSED_FILE_BOUND_EXCEEDED'):
            tool.read_bounded(path, 4)

    def test_retained_loaded_module_from_other_root_is_denied(self):
        path, profile = self.bind_toy_input()
        wrong = types.SimpleNamespace(__file__=str(self.root / 'other/fixture.py'))
        with patch.multiple(tool, SOURCE=self.root, PROFILE=profile), patch.dict(sys.modules, {'fixture': wrong}):
            with self.assertRaisesRegex(tool.Hold, 'LOADED_FOCUSED_SOURCE_CHANGED'):
                tool.validate_loaded_sources()

    def test_reusing_old_run_directory_is_denied(self):
        with self.assertRaisesRegex(tool.Hold, 'FRESH_RUN_DIRECTORY_REQUIRED'):
            tool.create_run(self.run)

    def test_child_failure_is_durable_before_hold(self):
        support = types.SimpleNamespace(run_owned=lambda *a, **k: subprocess.CompletedProcess(a, 1, 'partial-out', 'failure-code'))
        with patch.multiple(tool, SOURCE=self.root, OUT=self.run):
            with self.assertRaisesRegex(tool.Hold, 'FOCUSED_PHASE_HELD'):
                tool.invoke_phase('prepare', support)
        self.assertEqual((self.run / 'phase-prepare.log').read_text(), 'partial-outfailure-code')
        status = json.loads((self.run / 'phase-prepare-status.json').read_bytes())
        self.assertEqual(status['exit'], 1)
        self.assertEqual(status['stdout_bytes'], len('partial-out'))
        self.assertEqual(len((self.run / 'samples.jsonl').read_text().splitlines()), 1)

    def test_child_timeout_retains_partial_bytes_and_diagnostic_before_hold(self):
        def timed_out(*a, **k):
            raise subprocess.TimeoutExpired(a, 240, output=b'partial-events', stderr=b'bounded-diagnostic')
        support = types.SimpleNamespace(run_owned=timed_out)
        with patch.multiple(tool, SOURCE=self.root, OUT=self.run):
            with self.assertRaisesRegex(tool.Hold, 'FOCUSED_PHASE_HELD'):
                tool.invoke_phase('prepare', support)
        self.assertIn('partial-eventsbounded-diagnostic', (self.run / 'phase-prepare.log').read_text())
        status = json.loads((self.run / 'phase-prepare-status.json').read_bytes())
        self.assertTrue(status['timed_out']); self.assertIsNone(status['exit'])
        self.assertGreaterEqual(status['elapsed_seconds'], 0)

    def test_child_start_or_containment_error_is_persisted(self):
        def unavailable(*a, **k): raise OSError('synthetic unavailable')
        support = types.SimpleNamespace(run_owned=unavailable)
        with patch.multiple(tool, SOURCE=self.root, OUT=self.run):
            with self.assertRaises(tool.Hold): tool.invoke_phase('prepare', support)
        status = json.loads((self.run / 'phase-prepare-status.json').read_bytes())
        self.assertEqual(status['error_type'], 'OSError'); self.assertIsNone(status['exit'])

    def test_closed_owned_startup_gate_rejects_expired_or_wrong_token(self):
        for gate in ({'gate': 'other', 'deadline': 1e20}, {'gate': 'expected', 'deadline': 0},
                     {'gate': 'expected', 'deadline': True}):
            stdin = types.SimpleNamespace(buffer=io.BytesIO(json.dumps(gate).encode()))
            with patch.object(tool.sys, 'stdin', stdin), self.assertRaises(tool.Hold):
                tool.consume_gate('expected')

    def test_actual_child_never_imports_keyword_tests_without_owned_gate(self):
        result = subprocess.run([sys.executable, '-B', tool.__file__, '--root', str(self.root),
                                 '--_phase', 'prepare', '--_run-dir', str(self.run)],
                                input=b'', capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 1)
        output = json.loads(result.stdout)
        self.assertEqual(output['status'], 'HELD')
        self.assertFalse((self.run / 'fresh-fixture.json').exists())

    def poison_cache(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("VALUE='source'\n")
        poison = self.root / 'poison.py'; poison.write_text("VALUE='poison'\n")
        os.utime(path, (1700000000, 1700000000)); os.utime(poison, (1700000000, 1700000000))
        cache = Path(importlib.util.cache_from_source(str(path)))
        py_compile.compile(str(poison), cfile=str(cache), dfile=str(path), doraise=True)
        return cache

    def test_existing_valid_timestamp_pyc_is_ignored_by_explicit_source_loader(self):
        path = self.root / 'source_module.py'; cache = self.poison_cache(path)
        before = cache.read_bytes()
        normal = importlib.util.spec_from_file_location('normal_pyc_fixture', path)
        regular = importlib.util.module_from_spec(normal); normal.loader.exec_module(regular)
        self.assertEqual(regular.VALUE, 'poison', 'fixture must demonstrate a genuinely loadable mismatched cache')
        loaded = tool.source_module('focused_source_loader_fixture', path)
        self.addCleanup(sys.modules.pop, 'focused_source_loader_fixture', None)
        self.assertEqual(loaded.VALUE, 'source')
        self.assertEqual(cache.read_bytes(), before)

    def test_bound_keyword_finder_ignores_existing_pyc_without_deleting_or_allowing_it(self):
        path = self.root / 'tools/keyword-system/focused_pyc_fixture.py'; cache = self.poison_cache(path)
        before = cache.read_bytes()
        finder = tool.BoundSourceFinder(self.root, {'tools/keyword-system/focused_pyc_fixture.py'})
        with patch.object(sys, 'meta_path', [finder, *sys.meta_path]):
            loaded = __import__('focused_pyc_fixture')
        self.addCleanup(sys.modules.pop, 'focused_pyc_fixture', None)
        self.assertEqual(loaded.VALUE, 'source'); self.assertEqual(cache.read_bytes(), before)
        self.assertIsInstance(loaded.__loader__, tool.SourceOnlyLoader)


if __name__ == '__main__':
    unittest.main()

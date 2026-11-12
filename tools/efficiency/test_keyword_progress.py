"""Small real timeout/crash diagnostics and rejection/privacy contracts."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import keyword_modules as runner
import keyword_progress as progress
import owned_process as owned


class KeywordProgressTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='keyword-progress-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.writer = progress.Progress(self.root)
        self.rows = [{'module': 'test_synthetic', 'state': 'ACTIVE', 'expected': 1,
                      'started': 0, 'finished': 0, 'elapsed_seconds': .25}]

    def test_append_progress_survives_and_exposes_only_allowlisted_metadata(self):
        self.rows[0]['private_text'] = 'SYNTHETIC_MUST_NOT_ESCAPE'
        self.writer.write(self.rows)
        result = progress.read_diagnostic(self.root, self.writer.reference())
        self.assertFalse(result['acceptance'])
        self.assertTrue(result['diagnostic_only'])
        self.assertEqual(result['modules_total'], 1)
        self.assertNotIn('SYNTHETIC_MUST_NOT_ESCAPE', json.dumps(result))
        first = result['sha256']
        self.rows[0].update(state='COMPLETE', started=1, finished=1)
        self.writer.write(self.rows, 'FINISHED')
        result = progress.read_diagnostic(self.root, self.writer.reference())
        self.assertNotEqual(result['sha256'], first)
        self.assertFalse(result['acceptance'])
        self.assertFalse(self.writer.path.with_suffix('.new').exists())
        with self.writer.path.open('ab') as stream:
            stream.write(b'{"interrupted_append":')
        interrupted = progress.read_diagnostic(self.root, self.writer.reference())
        self.assertEqual(interrupted['status'], 'FINISHED')
        self.assertFalse(interrupted['acceptance'])

    def test_diagnostic_write_failure_disables_it_without_changing_test_execution(self):
        with patch.object(self.writer, 'write', side_effect=PermissionError('synthetic lock')) as write:
            runner.checkpoint(self.writer, {'test_synthetic': ['one']}, {}, {}, {}, force=True)
            runner.checkpoint(self.writer, {'test_synthetic': ['one']}, {}, {}, {}, force=True)
        write.assert_called_once()
        self.assertTrue(self.writer.disabled)

    def test_duplicate_escape_wrong_binding_and_malformed_receipts_are_withheld(self):
        self.writer.write(self.rows)
        reference = self.writer.reference()
        self.assertIsNone(progress.read_diagnostic(self.root, reference+'\n'+reference))
        self.assertIsNone(progress.read_diagnostic(self.root, progress.PREFIX+json.dumps({
            'file': '../outside.json', 'run_id': self.writer.run_id})))
        original = self.writer.path.read_bytes()
        for change in ({'run_id': '0'*32}, {'acceptance': True}, {'elapsed_seconds': float('nan')},
                       {'version': True}, {'modules': [{'module': 'private/path'}]}):
            value = json.loads(original)
            value.update(change)
            self.writer.path.write_text(json.dumps(value), encoding='utf-8')
            with self.subTest(change=list(change)):
                self.assertIsNone(progress.read_diagnostic(self.root, reference))
        self.writer.path.write_bytes(b'x'*(progress.LIMIT+1))
        self.assertIsNone(progress.read_diagnostic(self.root, reference))

    def test_real_outer_timeout_keeps_fixture_counts_without_claiming_a_pass(self):
        (self.root/'test_slow_setup.py').write_text('''import time,unittest
class Cases(unittest.TestCase):
    @classmethod
    def setUpClass(cls): time.sleep(5)
    def test_one(self): pass
''', encoding='utf-8')
        with self.assertRaises(subprocess.TimeoutExpired) as failure:
            owned.run_owned([sys.executable, '-B', str(Path(runner.__file__)), '--supervised',
                '--suite', str(self.root)], cwd=runner.ROOT, timeout=1)
        result = progress.read_diagnostic(runner.ROOT, failure.exception.stderr)
        self.assertIsNotNone(result)
        self.assertFalse(result['acceptance'])
        row = result['slowest_modules'][0]
        self.assertEqual((row['module'],row['expected'],row['started'],row['finished']),
                         ('test_slow_setup',1,0,0))
        # Either the outer owner kills first or the inner deadline records its
        # incomplete module. Both retain zero cases and cannot establish a pass.
        self.assertIn(row['state'], ('ACTIVE','INCOMPLETE'))
        self.assertIn(result['status'], ('RUNNING','TIMED_OUT'))

    def test_real_worker_crash_preserves_started_unfinished_case_and_duration(self):
        (self.root/'test_crash.py').write_text('''import os,unittest
class Cases(unittest.TestCase):
    def test_one(self): os._exit(7)
''', encoding='utf-8')
        result = owned.run_owned([sys.executable, '-B', str(Path(runner.__file__)), '--supervised',
            '--suite', str(self.root)], cwd=runner.ROOT, timeout=5)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(json.loads(result.stdout)['summary']['passed'])
        diagnostic = progress.read_diagnostic(runner.ROOT, result.stderr)
        row = diagnostic['slowest_modules'][0]
        self.assertEqual((row['state'],row['started'],row['finished']), ('INCOMPLETE',1,0))
        self.assertGreater(row['elapsed_seconds'], 0)

    def test_foundation_timeout_remains_failed_even_with_complete_diagnostic(self):
        self.rows[0].update(state='COMPLETE', started=1, finished=1)
        self.writer.write(self.rows, 'FINISHED')
        spec=importlib.util.spec_from_file_location('progress_foundation',runner.ROOT/'tools/check_repository.py')
        checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)
        stopped = subprocess.TimeoutExpired('synthetic',300,stderr=self.writer.reference().encode())
        supervisor = SimpleNamespace(run_owned=unittest.mock.Mock(side_effect=stopped))
        def module(name, path):
            return supervisor if name=='foundation_owned_process' else progress
        with patch.object(checker,'ROOT',self.root),patch.object(checker,'module',side_effect=module):
            result=checker.execute_check('keyword-system-behavior',['synthetic'],owned_tree=True)
        self.assertFalse(result['passed'])
        self.assertTrue(result['details']['timed_out'])
        self.assertIsNone(result['details']['exit'])
        self.assertFalse(result['details']['keyword_diagnostic']['acceptance'])
        self.assertEqual(supervisor.run_owned.call_args.kwargs['timeout'],300)

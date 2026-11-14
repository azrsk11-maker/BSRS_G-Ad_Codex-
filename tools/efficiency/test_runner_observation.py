"""Wrong repository/runtime metadata must fail before costly validation."""
import contextlib
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import runner_observation as observation


class RunnerObservationTests(unittest.TestCase):
    def setUp(self):
        self.repo={'full_name':observation.REPOSITORY,'private':False,'visibility':'public',
                   'private_body':'DO_NOT_PRINT_THIS_FIELD'}
        self.arguments={'system':'Linux','machine':'aarch64','version':(3,12,12),
                        'resources':{'cpu_count':4,'memory_available_bytes':16*1024**3}}

    def test_valid_observation_retains_controls_and_withholds_extra_event_fields(self):
        before=deepcopy(self.repo)
        result=observation.validate_observation(self.repo,**self.arguments)
        self.assertEqual(self.repo,before)
        self.assertEqual(result['startup_worker_selection']['selected_workers'],4)
        self.assertEqual(result['machine'],'aarch64')
        self.assertNotIn('DO_NOT_PRINT_THIS_FIELD',json.dumps(result))
        self.assertIs(result['release_authorized'],False)
        self.assertIs(result['source_body_hash_or_verdict_cache'],False)

    def test_private_missing_or_different_repository_is_rejected(self):
        for repo in (None,{},dict(self.repo,private=True),dict(self.repo,private=0),
                     dict(self.repo,visibility='private'),dict(self.repo,full_name='other/project')):
            with self.subTest(repo=repo),self.assertRaisesRegex(ValueError,'PUBLIC_REPOSITORY_REQUIRED'):
                observation.validate_observation(repo,**self.arguments)

    def test_mislabeled_or_nonlinux_runtime_is_rejected(self):
        for change in ({'system':'Windows'},{'machine':'x86_64'},{'machine':'armv7l'}):
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'LINUX_ARM_RUNTIME_REQUIRED'):
                observation.validate_observation(self.repo,**dict(self.arguments,**change))

    def test_python_version_guard_preserves_original_ast_runtime(self):
        for version in ((3,13,0),(3,11,10),(3,12),[3,12,12],(3,12,True)):
            with self.subTest(version=version),self.assertRaisesRegex(ValueError,'AST_VERSION_REQUIRED'):
                observation.validate_observation(self.repo,**dict(self.arguments,version=version))

    def test_resource_limits_remain_conservative(self):
        for resources,workers in (({'cpu_count':2,'memory_available_bytes':16*1024**3},2),
                                  ({'cpu_count':4,'memory_available_bytes':None},1),
                                  ({'cpu_count':64,'memory_available_bytes':16*1024**3},4)):
            result=observation.validate_observation(self.repo,**dict(self.arguments,resources=resources))
            self.assertEqual(result['startup_worker_selection']['selected_workers'],workers)
        with self.assertRaises(ValueError):
            observation.validate_observation(self.repo,**dict(self.arguments,
                resources={'cpu_count':True,'memory_available_bytes':16*1024**3}))

    def test_duplicate_or_nonobject_event_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'event.json'
            for body in (b'{"repository":{},"repository":{}}',b'[]',b'not-json'):
                path.write_bytes(body)
                with self.subTest(body=body),self.assertRaises(ValueError):observation.read_event(path)

    def test_oversized_event_is_rejected_before_parsing(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'event.json';path.write_bytes(b' '*(observation.MAX_EVENT_BYTES+1))
            with self.assertRaisesRegex(ValueError,'EVENT_BYTE_BOUND'):observation.read_event(path)

    def test_rejected_cli_does_not_print_event_or_private_path(self):
        output=io.StringIO()
        with patch.dict(observation.os.environ,{'GITHUB_EVENT_PATH':'DO_NOT_PRINT_THIS_PATH'}),\
             patch.object(observation,'read_event',side_effect=ValueError('DO_NOT_PRINT_THIS_EXCEPTION')),\
             contextlib.redirect_stdout(output):
            self.assertEqual(observation.main(),1)
        self.assertNotIn('DO_NOT_PRINT',output.getvalue())
        self.assertIn('REJECTED',output.getvalue())

    def test_cli_collects_actual_probe_values_instead_of_using_the_requested_label(self):
        output=io.StringIO()
        with patch.dict(observation.os.environ,{'GITHUB_EVENT_PATH':'fixture'}),\
             patch.object(observation,'read_event',return_value={'repository':self.repo}),\
             patch.object(observation.platform,'system',return_value='Linux'),\
             patch.object(observation.platform,'machine',return_value='x86_64'),\
             patch.object(observation.sys,'version_info',(3,12,12)),\
             patch.object(observation,'observe_resources',return_value=self.arguments['resources']),\
             contextlib.redirect_stdout(output):
            self.assertEqual(observation.main(),1)
        self.assertIn('REJECTED',output.getvalue())


if __name__=='__main__':
    unittest.main()

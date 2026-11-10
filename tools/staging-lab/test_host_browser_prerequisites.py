"""Synthetic-only fail-closed observations; no real process or network probes."""
import json
import subprocess
import unittest
from unittest.mock import patch
import host_browser_prerequisites as probe


class HostBrowserPrerequisiteTests(unittest.TestCase):
    def call(self, output=None, *, code=0, error=b'', exception=None):
        response = subprocess.CompletedProcess([], code,
            output if output is not None else json.dumps(dict.fromkeys(probe.CHECKS, True)).encode(), error)
        with patch.object(probe.sys, 'platform', 'linux'), \
             patch.object(probe.os, 'getuid', return_value=1001, create=True), \
             patch.object(probe.os, 'geteuid', return_value=1001, create=True), \
             patch.object(probe, '_binary', side_effect=lambda name: '/usr/bin/' + name), \
             patch.object(probe, '_baseline', return_value={'uid':1001,'euid':1001,'user':'u','net':'n','mnt':'m'}), \
             patch.object(probe.subprocess, 'run', side_effect=exception, return_value=response) as run:
            result = probe.observe()
            return result, run.call_args

    def assert_held(self, result):
        for key in ('browser_started','wordpress_started','browser_runtime_accepted',
                    'host_security_settings_changed','existing_container_controls_changed',
                    'software_installed','production_changes','release_authorized'):
            self.assertIs(result[key], False)
        self.assertEqual(result['outbound_connections_attempted'], 0)

    def test_non_linux_observation_never_attempts_a_process(self):
        with patch.object(probe.sys, 'platform', 'win32'), patch.object(probe.subprocess, 'run') as run:
            result=probe.observe()
        self.assertEqual(result['status'],'UNSUPPORTED_PLATFORM');run.assert_not_called();self.assert_held(result)

    def test_root_is_rejected_before_tools_or_processes(self):
        with patch.object(probe.sys,'platform','linux'), patch.object(probe.os,'getuid',return_value=0,create=True), \
             patch.object(probe,'_binary') as binary, patch.object(probe.subprocess,'run') as run:
            result=probe.observe()
        self.assertEqual(result['status'],'ROOT_EXECUTION_REJECTED');binary.assert_not_called();run.assert_not_called()

    def test_missing_utility_is_not_a_success_or_fallback(self):
        with patch.object(probe.sys,'platform','linux'), patch.object(probe.os,'getuid',return_value=1001,create=True), \
             patch.object(probe.os,'geteuid',return_value=1001,create=True), patch.object(probe,'_binary',return_value=None), \
             patch.object(probe.subprocess,'run') as run:
            result=probe.observe()
        self.assertEqual(result['status'],'COMMAND_UNAVAILABLE');run.assert_not_called();self.assert_held(result)

    def test_fixed_command_keeps_current_uid_nnp_timeout_and_clean_environment(self):
        result,args=self.call()
        command=args.args[0]
        self.assertEqual(command[:7],['/usr/bin/setpriv','--no-new-privs','/usr/bin/unshare','--user','--map-current-user','--net','--mount'])
        self.assertIn('-I',command);self.assertNotIn('--fork',command);self.assertNotIn('--map-root-user',command)
        self.assertEqual(args.kwargs['env'],{'PATH':'/usr/bin:/bin','LC_ALL':'C'})
        self.assertEqual(args.kwargs['timeout'],3);self.assertEqual(args.kwargs['stdin'],subprocess.DEVNULL)
        self.assertNotIn('shell',args.kwargs);self.assert_held(result)
        self.assertEqual(result['status'],'NAMESPACE_PREREQUISITES_OBSERVED')

    def test_denial_and_private_error_text_are_not_echoed_or_retried(self):
        result,_=self.call(code=1,error=b'Operation not permitted SYNTHETIC_PRIVATE_ERROR')
        self.assertEqual(result['status'],'DENIED_OR_FAILED');self.assertTrue(result['operation_not_permitted_reported'])
        self.assertNotIn('SYNTHETIC_PRIVATE_ERROR',json.dumps(result));self.assert_held(result)

    def test_timeout_start_error_and_large_output_stay_held(self):
        for exception,status in [(subprocess.TimeoutExpired('synthetic',3),'TIMED_OUT'),(OSError('synthetic'),'PROBE_START_OR_METADATA_FAILED')]:
            result,_=self.call(exception=exception)
            self.assertEqual(result['status'],status);self.assert_held(result)
        result,_=self.call(output=b'x'*8193);self.assertEqual(result['status'],'OVERSIZED_CHILD_OUTPUT')

    def test_partial_nonboolean_duplicate_and_secret_fields_are_rejected(self):
        samples=[b'{}',b'[]',b'null',b'not-json',b'\xff',b'{"uid_preserved":true,"uid_preserved":true}',
                 json.dumps(dict.fromkeys(probe.CHECKS,1)).encode(),
                 json.dumps(dict(dict.fromkeys(probe.CHECKS,True),secret='SYNTHETIC_PRIVATE')).encode()]
        for output in samples:
            with self.subTest(output=output):
                result,_=self.call(output=output)
                self.assertEqual(result['status'],'MALFORMED_CHILD_OUTPUT');self.assertEqual(result['checks'],{})
                self.assertNotIn('SYNTHETIC_PRIVATE',json.dumps(result));self.assert_held(result)

    def test_each_missing_isolation_invariant_prevents_prerequisite_success(self):
        for key in probe.CHECKS:
            with self.subTest(key=key):
                checks=dict.fromkeys(probe.CHECKS,True);checks[key]=False
                result,_=self.call(output=json.dumps(checks).encode())
                self.assertEqual(result['status'],'NAMESPACE_INVARIANT_NOT_VERIFIED');self.assert_held(result)


if __name__=='__main__':
    unittest.main()

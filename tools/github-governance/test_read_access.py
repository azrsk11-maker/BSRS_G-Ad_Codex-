import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
import urllib.error

spec = importlib.util.spec_from_file_location("read_access", Path(__file__).with_name("read_access.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
ACCOUNT = "BlackSwanBss3701"
SECRET = "synthetic-credential-for-test-only"


class FakeAPI:
    def __init__(self, *, write=False, login=ACCOUNT, repository=m.REPOSITORY, rows=None):
        self.calls = []
        self.routes = {
            "/user": (200, {"login": login, "email": "private@example.invalid"}),
            "/repos/" + m.REPOSITORY: (200, {"full_name": repository,
                "permissions": {"pull": True, "push": write, "triage": False, "maintain": False, "admin": False}}),
            "/user/repository_invitations?per_page=100": (200, rows if rows is not None else []),
        }

    def __call__(self, path):
        self.calls.append(path)
        return self.routes[path]


class AccessTests(unittest.TestCase):
    def test_read_and_write_are_distinct_without_mutation(self):
        for write in (False, True):
            api = FakeAPI(write=write)
            report = m.inspect_access(ACCOUNT, api)
            self.assertEqual(report["permissions"]["push"], write)
            self.assertEqual(report["api_calls"], 2)
            self.assertEqual(len(api.calls), 2)
            self.assertNotIn("email", json.dumps(report))
            self.assertNotIn("production", report)

    def test_wrong_authenticated_account_stops_before_repository_read(self):
        api = FakeAPI(login="different-user")
        with self.assertRaisesRegex(m.AccessError, "AUTHENTICATED_ACCOUNT_MISMATCH"):
            m.inspect_access(ACCOUNT, api)
        self.assertEqual(api.calls, ["/user"])

    def test_account_case_is_insensitive_but_input_is_bounded(self):
        self.assertEqual(m.inspect_access(ACCOUNT.lower(), FakeAPI())["authenticated_login"], ACCOUNT)
        for bad in ("marketing@example.invalid", "x\npassword=bad", "a" * 40, "", None):
            with self.assertRaisesRegex(m.AccessError, "INVALID_ACCOUNT"):
                m.inspect_access(bad, FakeAPI())

    def test_wrong_repository_never_establishes_write(self):
        with self.assertRaisesRegex(m.AccessError, "REPOSITORY_IDENTITY_MISMATCH"):
            m.inspect_access(ACCOUNT, FakeAPI(write=True, repository="other/repository"))

    def test_missing_or_coerced_permission_fields_hold(self):
        for value in ({"push": True}, {k: "true" for k in m.PERMISSIONS}, None):
            api = FakeAPI(write=True)
            api.routes["/repos/" + m.REPOSITORY][1]["permissions"] = value
            with self.assertRaisesRegex(m.AccessError, "PERMISSIONS_UNVERIFIED"):
                m.inspect_access(ACCOUNT, api)

    def test_invitation_output_does_not_expose_unrelated_repo_or_private_fields(self):
        rows = [{"id": 100, "repository": {"full_name": "private/other"}, "email": "private@example.invalid"},
                {"id": 101, "repository": {"full_name": m.REPOSITORY}, "secret": SECRET}]
        report = m.inspect_access(ACCOUNT, FakeAPI(rows=rows), invitations=True)
        self.assertEqual(report["matching_invitations_on_first_page"], 1)
        self.assertTrue(report["invitation_inventory_complete"])
        self.assertEqual(report["api_calls"], 3)
        for forbidden in (SECRET, "private/other", "private@example.invalid"):
            self.assertNotIn(forbidden, json.dumps(report))

    def test_full_invitation_page_cannot_claim_complete_absence(self):
        report = m.inspect_access(ACCOUNT, FakeAPI(rows=[{}] * 100), invitations=True)
        self.assertEqual(report["matching_invitations_on_first_page"], 0)
        self.assertFalse(report["invitation_inventory_complete"])

    def test_invitation_error_is_not_empty_success(self):
        api = FakeAPI()
        api.routes["/user/repository_invitations?per_page=100"] = (403, None)
        report = m.inspect_access(ACCOUNT, api, invitations=True)
        self.assertFalse(report["invitation_inventory_complete"])
        self.assertNotIn("matching_invitations_on_first_page", report)

    def test_cross_repository_and_credential_in_url_are_rejected(self):
        for origin in ("https://github.com/other/repo.git", "https://bad.example/" + m.REPOSITORY,
                       "https://name:password@github.com/" + m.REPOSITORY,
                       "https://github.com:bad/" + m.REPOSITORY):
            with patch.object(m, "git", return_value=subprocess.CompletedProcess([], 0, origin, "")) as git:
                with self.assertRaisesRegex(m.AccessError, "ORIGIN_OUTSIDE_APPROVED_REPOSITORY"):
                    m.read_credential(m.ROOT, ACCOUNT)
                self.assertEqual(git.call_count, 1)

    def test_cached_credential_errors_never_surface_helper_output(self):
        responses = [subprocess.CompletedProcess([], 0, "https://github.com/" + m.REPOSITORY + ".git", ""),
                     subprocess.CompletedProcess([], 1, SECRET, SECRET)]
        with patch.object(m, "git", side_effect=responses):
            with self.assertRaises(m.AccessError) as caught:
                m.read_credential(m.ROOT, ACCOUNT)
            self.assertEqual(str(caught.exception), "GIT_CREDENTIAL_UNAVAILABLE")

    def test_git_subprocess_cannot_prompt_or_trace_credentials(self):
        with patch.dict(os.environ, {"GIT_ASKPASS": "helper", "GCM_TRACE": "trace.log", "GIT_TRACE_CURL": "1"}), \
                patch.object(m.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "", "")) as run:
            m.git(m.ROOT, ["remote", "get-url", "origin"])
            kwargs = run.call_args.kwargs
            self.assertEqual(kwargs["env"]["GIT_TERMINAL_PROMPT"], "0")
            self.assertEqual(kwargs["env"]["GCM_INTERACTIVE"], "never")
            for key in ("GIT_ASKPASS", "GCM_TRACE", "GIT_TRACE_CURL"):
                self.assertNotIn(key, kwargs["env"])
            self.assertFalse(kwargs.get("shell", False))

    def test_transport_is_get_only_scope_pinned_and_redirects_denied(self):
        opener = unittest.mock.Mock()
        with patch.object(m.urllib.request, "build_opener", return_value=opener):
            get = m.transport(SECRET)
            with self.assertRaisesRegex(m.AccessError, "ENDPOINT_OUTSIDE_APPROVED_SCOPE"):
                get("/repos/other/repo")
            self.assertFalse(opener.open.called)
            opener.open.side_effect = urllib.error.HTTPError("https://api.github.com/user", 302, SECRET, {}, None)
            self.assertEqual(get("/user"), (302, None))
            request = opener.open.call_args.args[0]
            self.assertEqual(request.get_method(), "GET")
            self.assertEqual(request.full_url, "https://api.github.com/user")
            self.assertIsNone(m.NoRedirect().redirect_request(None, None, None, None, None, None))

    def test_cli_exit_codes_do_not_conflate_missing_access_with_runtime_error(self):
        for write, expected in ((True, 0), (False, 1)):
            out = io.StringIO()
            with patch.object(m, "read_credential", return_value=SECRET), patch.object(m, "transport", return_value=FakeAPI(write=write)), contextlib.redirect_stdout(out):
                code = m.main(["--account", ACCOUNT])
            self.assertEqual(code, expected)
            self.assertNotIn(SECRET, out.getvalue())
            self.assertEqual(json.loads(out.getvalue())["api_calls"], 2)
        out = io.StringIO()
        with patch.object(m, "read_credential", side_effect=m.AccessError("GIT_CREDENTIAL_UNAVAILABLE")), contextlib.redirect_stdout(out):
            self.assertEqual(m.main(["--account", ACCOUNT]), 2)
        self.assertEqual(json.loads(out.getvalue())["status"], "ACCESS_UNVERIFIED")


if __name__ == "__main__":
    unittest.main()

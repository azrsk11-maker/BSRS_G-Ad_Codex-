"""Safe observed test counters; fabricated outputs never certify live behavior."""
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location("foundation_summary", Path(__file__).resolve().parents[1] / "check_repository.py")
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


def tap(passed=5, failed=0, skipped=17, tests=22):
    return ("TAP version 13\n# PRIVATE_SYNTHETIC_OUTPUT\n1..22\n"
            f"# tests {tests}\n# suites 0\n# pass {passed}\n# fail {failed}\n"
            f"# cancelled 0\n# skipped {skipped}\n# todo 0\n# duration_ms 321.125\n")


class FoundationSummaryTests(unittest.TestCase):
    def test_complete_keyword_receipt_requires_valid_bounded_resource_selection(self):
        summary={key:1 for key in ('discovered_modules','completed_modules','discovered','started','finished')}
        summary.update(skipped=0,coverage_verified=True,passed=True,timed_out=False)
        policy={'mode':'auto','selected_workers':4,'maximum_workers':4,
            'memory_per_worker_bytes':2*1024**3,'cpu_count':4,'memory_available_bytes':8*1024**3}
        report={'summary':summary,'workers':4,'worker_resources':policy,'aggregate_timeout_seconds':300,
            'evidence_file':'test-output/keyword-modules-SYNTHETIC.json',
            'evidence_sha256':'0'*64,'expected_ids_sha256':'1'*64}
        resource_spec=importlib.util.spec_from_file_location('synthetic_resource_guard',
            CHECKER.ROOT/'tools/efficiency/keyword_resources.py')
        resources=importlib.util.module_from_spec(resource_spec);resource_spec.loader.exec_module(resources)
        for change,wanted in (({},True),({'maximum_workers':1000},False),
                              ({'memory_available_bytes':1},False),({'cpu_count':1},False)):
            candidate={**report,'worker_resources':{**policy,**change}}
            supervisor=SimpleNamespace(run_owned=lambda *a,**k: subprocess.CompletedProcess(a,0,json.dumps(candidate),''))
            def module(name,path):
                return supervisor if name=='foundation_owned_process' else resources
            with self.subTest(change=change),patch.object(CHECKER,'module',side_effect=module):
                result=CHECKER.execute_check('keyword-system-behavior',['synthetic'],owned_tree=True)
            self.assertEqual(result['passed'],wanted)

    def test_keyword_suite_time_budget_remains_bounded_and_failures_propagate(self):
        failed = subprocess.CompletedProcess(["synthetic-python"], 7, "", "SYNTHETIC_FAILURE")
        with patch.object(CHECKER.subprocess, "run", return_value=failed) as child:
            result = CHECKER.execute_check("keyword-system-behavior", ["synthetic-python"])
        self.assertEqual(child.call_args.kwargs["timeout"], 300)
        self.assertFalse(result["passed"])
        with patch.object(CHECKER.subprocess, "run", side_effect=subprocess.TimeoutExpired("synthetic-python", 300)) as child:
            timed_out = CHECKER.execute_check("keyword-system-behavior", ["synthetic-python"])
        self.assertFalse(timed_out["passed"])
        self.assertTrue(timed_out["details"]["timed_out"])
        self.assertIsNone(timed_out["details"]["exit"])
        self.assertEqual(child.call_args.kwargs["timeout"], 300)

    def execute(self, output, exit_code=0, stderr="", require=True):
        result = subprocess.CompletedProcess(["synthetic-node"], exit_code, output, stderr)
        with patch.object(CHECKER.subprocess, "run", return_value=result) as child:
            observed = CHECKER.execute_check(CHECKER.TAP_CHECK if require else "ordinary-synthetic-check", ["synthetic-node", "--test"])
        child.assert_called_once()
        self.assertEqual(child.call_args.kwargs["timeout"], 120)
        return observed

    def test_windows_skips_and_linux_execution_remain_distinct(self):
        windows = CHECKER.node_tap_summary(tap())
        linux = CHECKER.node_tap_summary(tap(passed=21, skipped=1))
        self.assertEqual((windows["pass"], windows["skipped"]), (5, 17))
        self.assertEqual((linux["pass"], linux["skipped"]), (21, 1))
        self.assertEqual(linux["tests"], 22)

    def test_crlf_and_nested_diagnostics_do_not_change_root_totals(self):
        output = tap().replace("1..22", "    # tests 999\n1..22").replace("\n", "\r\n")
        self.assertEqual(CHECKER.node_tap_summary(output)["tests"], 22)

    def test_missing_duplicate_truncated_and_trailing_fields_do_not_invent_counts(self):
        for output in ("", tap().replace("TAP version 13\n", ""), tap().replace("# fail 0\n", ""),
                       tap().replace("# pass 5\n", "# pass 5\n# pass 5\n"),
                       tap()[:-25], tap() + "PRIVATE_TRAILING_TEXT"):
            with self.subTest(output=output[:30]):
                self.assertIsNone(CHECKER.node_tap_summary(output))

    def test_impossible_totals_overflow_and_nonfinite_duration_are_rejected(self):
        for output in (tap(passed=6), tap().replace("# tests 22", "# tests 1000001"),
                       tap().replace("# pass 5", "# pass -5"), tap().replace("321.125", "NaN"),
                       tap().replace("321.125", "99999999"), tap().replace("# tests 22", "# tests \uff12\uff12")):
            self.assertIsNone(CHECKER.node_tap_summary(output))

    def test_missing_evidence_holds_even_after_zero_exit(self):
        check = self.execute("SYNTHETIC SUITE EXITED ZERO")
        self.assertFalse(check["passed"])
        self.assertEqual(check["details"]["tap_evidence_status"], "MISSING_OR_INVALID")

    def test_process_failures_and_all_skipped_cannot_become_success(self):
        self.assertFalse(self.execute(tap(), exit_code=7)["passed"])
        self.assertFalse(self.execute(tap(passed=4, failed=1))["passed"])
        self.assertFalse(self.execute(tap(passed=0, skipped=22))["passed"])

    def test_non_tap_commands_keep_existing_exit_semantics(self):
        self.assertTrue(self.execute("ordinary output", require=False)["passed"])
        self.assertFalse(self.execute("ordinary output", exit_code=1, require=False)["passed"])

    def test_public_summary_contains_only_observed_allowlisted_numeric_fields(self):
        check = self.execute(tap(), stderr="PRIVATE_SYNTHETIC_ERROR\n# tests 999999\n")
        summary = CHECKER.public_test_summary(check)
        self.assertEqual(summary["tests"], 22)
        self.assertEqual(summary["process_exit"], 0)
        self.assertEqual(summary["runner_platform"], CHECKER.sys.platform)
        self.assertFalse(summary["release_authorized"])
        public = json.dumps(summary)
        self.assertNotIn("PRIVATE", public)
        self.assertNotIn("output_tail", public)
        self.assertEqual(len(summary), 13)

    def test_decorated_or_replaced_summary_cannot_leak_extra_payloads(self):
        for change in ({"secret": "PRIVATE_SYNTHETIC_VALUE"}, {"pass": True}, {"duration_ms": float("inf")}):
            check = self.execute(tap())
            check["details"]["tap_summary"].update(change)
            summary = CHECKER.public_test_summary(check)
            self.assertEqual(summary["status"], "MISSING_OR_INVALID")
            self.assertNotIn("PRIVATE", json.dumps(summary))
        check = self.execute(tap())
        check["check"] = "PRIVATE_UNREVIEWED_CHECK"
        self.assertIsNone(CHECKER.public_test_summary(check))


if __name__ == "__main__":
    unittest.main()

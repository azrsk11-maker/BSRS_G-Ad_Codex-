import datetime as dt
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import audit_runner as runner


class AuditRunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.log = self.root / "private-session.jsonl"
        self.cache = self.root / "cache"
        self.since = runner.codex_metrics.instant("2026-11-01T00:00:00Z")
        self.until = runner.codex_metrics.instant("2026-11-02T00:00:00Z")
        self.call = {"timestamp": "2026-11-01T01:00:00Z", "type": "response_item", "payload": {
            "type": "function_call", "name": "exec_command", "call_id": "one",
            "arguments": json.dumps({"cmd": "echo PRIVATE_SECRET_ABC user@example.invalid"})}}
        self.output = {"timestamp": "2026-11-01T01:00:02Z", "type": "response_item", "payload": {
            "type": "function_call_output", "call_id": "one", "output": "PRIVATE_SECRET_ABC"}}
        self.log.write_text("\n".join(json.dumps(v) for v in (self.call, self.output)) + "\n")

    def tearDown(self):
        self.tmp.cleanup()

    def run_audit(self, **kwargs):
        return runner.run([self.log], self.since, self.until, self.cache, **kwargs)

    def test_hit_is_equal_and_reads_zero_log_bytes(self):
        cold = self.run_audit()
        with patch.object(runner.codex_metrics, "analyze", side_effect=AssertionError("read on hit")):
            hot = self.run_audit()
        self.assertFalse(cold["run"]["cache_hit"])
        self.assertTrue(hot["run"]["cache_hit"])
        self.assertEqual(hot["run"]["source_log_bytes_read_this_run"], 0)
        self.assertEqual(cold["report"], hot["report"])

    def test_cli_report_cannot_overwrite_source_log(self):
        before = self.log.read_bytes()
        with patch("sys.argv", ["audit", "--since", self.since.isoformat(), "--until", self.until.isoformat(),
                                "--cache-dir", str(self.cache), "--report", str(self.log), str(self.log)]), redirect_stdout(io.StringIO()):
            self.assertEqual(2, runner.main())
        self.assertEqual(before, self.log.read_bytes())
        self.assertFalse(self.cache.exists())

    def test_source_append_invalidates(self):
        self.run_audit()
        with self.log.open("a") as stream:
            stream.write(json.dumps({**self.output, "payload": {**self.output["payload"], "call_id": "two"}}) + "\n")
        self.assertFalse(self.run_audit()["run"]["cache_hit"])

    def test_window_change_invalidates(self):
        self.run_audit()
        self.until += dt.timedelta(seconds=1)
        self.assertFalse(self.run_audit()["run"]["cache_hit"])

    def test_explicit_refresh_reanalyzes(self):
        self.run_audit()
        self.assertFalse(self.run_audit(refresh=True)["run"]["cache_hit"])

    def test_corrupt_cache_is_replaced(self):
        self.run_audit()
        next(self.cache.glob("*.json")).write_text('{"schema":"wrong"}')
        self.assertFalse(self.run_audit()["run"]["cache_hit"])

    def test_tampered_report_digest_is_rejected(self):
        self.run_audit()
        file = next(self.cache.glob("*.json"))
        data = json.loads(file.read_text())
        data["report"]["tool_calls"] = 999
        file.write_text(json.dumps(data))
        self.assertEqual(self.run_audit()["report"]["tool_calls"], 1)

    def test_no_raw_input_in_report_or_cache(self):
        report = self.run_audit()
        content = json.dumps(report) + next(self.cache.glob("*.json")).read_text()
        for forbidden in ("PRIVATE_SECRET_ABC", "user@example.invalid", str(self.log), "echo "):
            self.assertNotIn(forbidden, content)

    def test_changing_source_never_caches(self):
        real = runner.codex_metrics.analyze
        def changed(*args):
            value = real(*args)
            with self.log.open("a") as stream:
                stream.write("\n")
            return value
        with patch.object(runner.codex_metrics, "analyze", side_effect=changed):
            value = self.run_audit()
        self.assertFalse(value["run"]["cache_written"])

    def test_rejects_duplicates_and_reversed_window(self):
        with self.assertRaises(ValueError):
            runner.run([self.log, self.log], self.since, self.until, self.cache)
        with self.assertRaises(ValueError):
            runner.run([self.log], self.until, self.since, self.cache)


if __name__ == "__main__":
    unittest.main()

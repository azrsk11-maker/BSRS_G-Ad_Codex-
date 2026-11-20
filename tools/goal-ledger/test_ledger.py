"""Focused synthetic tests; no provider, browser, Ads, or production access."""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

import ledger


def fixture():
    return ledger.seed({"groups": [{"goals": [
        {"id": i, "critical_dependencies": [], "first_launch_gate":
         ("conditional_on_selected_scope" if i == 98 else i < 90)}
        for i in range(1, 101)]}]})


def evidence(data, goal, kind, key="test-proof"):
    data["evidence"][key] = {"kind": kind, "goals": [goal],
                            "ref": "docs/audit/SYNTHETIC_TEST.json"}
    data["goals"][int(goal[1:]) - 1]["evidence_refs"].append(key)


class LedgerTests(unittest.TestCase):
    def test_initial_state_has_exactly_100_and_no_completion(self):
        data = fixture()
        self.assertEqual([], ledger.validate(data))
        result = ledger.summary(data)
        self.assertEqual({"pending": 100, "running": 0, "verified": 0, "blocked": 0}, result["counts"])
        self.assertFalse(result["launch"]["prerequisites_verified"])

    def test_missing_duplicate_and_unordered_ids_are_rejected(self):
        for mutate in (lambda d: d["goals"].pop(),
                       lambda d: d["goals"][1].update(id="G001"),
                       lambda d: d["goals"].reverse()):
            data = fixture()
            mutate(data)
            self.assertTrue(ledger.validate(data))

    def test_unknown_self_duplicate_and_cyclic_dependencies_are_rejected(self):
        for deps in (["G101"], ["G001"], ["G002", "G002"]):
            data = fixture()
            data["goals"][0]["depends_on"] = deps
            self.assertTrue(ledger.validate(data))
        data = fixture()
        data["goals"][0]["depends_on"] = ["G002"]
        data["goals"][1]["depends_on"] = ["G001"]
        self.assertIn("dependency graph contains a cycle", ledger.validate(data))

    def test_ready_requires_verified_dependencies_and_excludes_blocked(self):
        data = fixture()
        data["goals"][1]["depends_on"] = ["G001"]
        data["canonical_plan_sha256"] = ledger.plan_digest(data["goals"])
        data["goals"][4]["status"] = "blocked"
        evidence(data, "G005", "blocker", "identity-hold")
        self.assertNotIn("G002", ledger.summary(data)["ready"]["prelaunch"])
        self.assertNotIn("G005", ledger.summary(data)["ready"]["prelaunch"])
        data["goals"][0]["status"] = "verified"
        evidence(data, "G001", "goal_acceptance")
        self.assertIn("G002", ledger.summary(data)["ready"]["prelaunch"])

    def test_running_and_verified_cannot_bypass_dependencies(self):
        for status in ("running", "verified"):
            data = fixture()
            data["goals"][1].update(status=status, depends_on=["G001"])
            evidence(data, "G002", "native_ci")
            self.assertTrue(any("unverified dependencies" in x for x in ledger.validate(data)))

    def test_blocked_requires_blocker_evidence(self):
        data = fixture()
        data["goals"][4]["status"] = "blocked"
        self.assertTrue(ledger.validate(data))
        evidence(data, "G005", "blocker")
        self.assertEqual([], ledger.validate(data))

    def test_running_requires_bound_progress_evidence(self):
        data = fixture()
        data["goals"][0]["status"] = "running"
        self.assertTrue(ledger.validate(data))
        evidence(data, "G001", "local_test")
        self.assertEqual([], ledger.validate(data))

    def test_preparation_can_run_with_unfinished_completion_dependencies(self):
        data = fixture()
        data["goals"][1].update(status="running", preparation_only=True, depends_on=["G001"])
        data["canonical_plan_sha256"] = ledger.plan_digest(data["goals"])
        evidence(data, "G002", "observation")
        self.assertEqual([], ledger.validate(data))
        result = ledger.summary(data)
        self.assertEqual(["G002"], result["running_preparation"])
        self.assertEqual([], result["running_execution"])
        self.assertEqual(["G001"], result["waiting_on"]["G002"])
        self.assertNotIn("G002", result["ready_to_finish"]["prelaunch"])
        self.assertFalse(result["launch"]["prerequisites_verified"])

    def test_explicit_false_retains_running_dependency_checks(self):
        data = fixture()
        data["goals"][1].update(status="running", preparation_only=False, depends_on=["G001"])
        data["canonical_plan_sha256"] = ledger.plan_digest(data["goals"])
        evidence(data, "G002", "observation")
        self.assertTrue(any("unverified dependencies" in error for error in ledger.validate(data)))

    def test_preparation_flag_requires_actual_boolean(self):
        for value in (0, 1, None, "true", "false", [], {}):
            with self.subTest(value=value):
                data = fixture()
                data["goals"][0].update(status="running", preparation_only=value)
                evidence(data, "G001", "observation")
                self.assertTrue(any("preparation_only must be a boolean" in error
                                    for error in ledger.validate(data)))

    def test_preparation_true_cannot_describe_verified_pending_or_blocked(self):
        for status in ("verified", "pending", "blocked"):
            data = fixture()
            data["goals"][0].update(status=status, preparation_only=True)
            evidence(data, "G001", "blocker" if status == "blocked" else "goal_acceptance")
            self.assertTrue(any("preparation_only true requires running status" in error
                                for error in ledger.validate(data)))
        data = fixture()
        data["goals"][1].update(status="verified", preparation_only=True, depends_on=["G001"])
        data["canonical_plan_sha256"] = ledger.plan_digest(data["goals"])
        evidence(data, "G002", "native_ci")
        self.assertTrue(any("unverified dependencies" in error for error in ledger.validate(data)))

    def test_preparation_still_requires_bound_nonblocker_progress_evidence(self):
        for kind in (None, "blocker"):
            data = fixture()
            data["goals"][1].update(status="running", preparation_only=True, depends_on=["G001"])
            data["canonical_plan_sha256"] = ledger.plan_digest(data["goals"])
            if kind:
                evidence(data, "G002", kind)
            self.assertTrue(any("running requires a bound progress/evidence reference" in error
                                for error in ledger.validate(data)))

    def test_preparation_remains_separate_even_after_dependencies_verify(self):
        data = fixture()
        data["goals"][0]["status"] = "verified"
        evidence(data, "G001", "goal_acceptance", "prerequisite")
        data["goals"][1].update(status="running", preparation_only=True, depends_on=["G001"])
        data["canonical_plan_sha256"] = ledger.plan_digest(data["goals"])
        evidence(data, "G002", "observation", "preparation")
        prepared = ledger.summary(data)
        self.assertNotIn("G002", prepared["ready_to_finish"]["prelaunch"])
        self.assertNotIn("G002", prepared["waiting_on"])
        data["goals"][1]["preparation_only"] = False
        execution = ledger.summary(data)
        self.assertEqual([], execution["running_preparation"])
        self.assertEqual(["G002"], execution["running_execution"])
        self.assertIn("G002", execution["ready_to_finish"]["prelaunch"])
        self.assertEqual("planning_only_no_execution_permission", execution["authority"])

    def test_local_tests_cannot_verify_native_human_or_authority_gates(self):
        for goal in ("G002", "G003", "G025", "G029", "G070", "G082", "G084", "G088"):
            data = fixture()
            data["goals"][int(goal[1:]) - 1]["status"] = "verified"
            evidence(data, goal, "local_test")
            self.assertTrue(any("requires evidence kinds" in x for x in ledger.validate(data)))

    def test_tests_and_authorizations_do_not_prove_deployment_or_genuine_events(self):
        for goal in ("G048", "G083", "G085", "G089", "G090"):
            for kind in ("local_test", "native_ci", "scoped_authorization"):
                data = fixture()
                data["goals"][int(goal[1:]) - 1]["status"] = "verified"
                evidence(data, goal, kind)
                self.assertTrue(ledger.validate(data))

    def test_evidence_must_bind_the_exact_goal(self):
        data = fixture()
        evidence(data, "G001", "native_ci", "old-baseline")
        data["goals"][1].update(status="verified", evidence_refs=["old-baseline"])
        self.assertTrue(any("wrongly bound" in x for x in ledger.validate(data)))

    def test_conditional_and_later_tasks_do_not_enter_launch_gate_count(self):
        data = fixture()
        result = ledger.summary(data)
        self.assertEqual(89, result["launch"]["required_count"])
        self.assertNotIn("G098", result["launch"]["open_goals"])
        self.assertNotIn("G090", result["launch"]["open_goals"])
        self.assertEqual(["G098"], result["ready"]["conditional"])
        self.assertEqual("planning_only_no_execution_permission", result["authority"])

    def test_canonical_classification_and_dependencies_cannot_drift_silently(self):
        for field, value in (("launch_gate", "later"), ("depends_on", ["G002"])):
            data = fixture()
            data["goals"][0][field] = value
            self.assertTrue(any("canonical plan checksum" in x for x in ledger.validate(data)))

    def test_nonportable_refs_and_malformed_types_fail_closed(self):
        for ref in ("C:/private.json", "../private.json", "docs/../private.json",
                    "https://example.invalid/private-id", "docs/private?token=secret"):
            data = fixture()
            evidence(data, "G001", "local_test")
            data["evidence"]["test-proof"]["ref"] = ref
            self.assertTrue(ledger.validate(data))
        data = fixture()
        evidence(data, "G001", "local_test")
        data["evidence"]["test-proof"].update(kind={}, goals=None)
        self.assertTrue(ledger.validate(data))

    def test_seed_copies_only_canonical_graph_and_gate_fields(self):
        canonical = {"private_machine_path": "PRIVATE", "groups": [{"goals": [
            {"id": i, "goal": "PRIVATE", "critical_dependencies": [],
             "first_launch_gate": True} for i in range(1, 101)]}]}
        encoded = json.dumps(ledger.seed(canonical))
        self.assertNotIn("PRIVATE", encoded)
        canonical["groups"][0]["goals"][1]["critical_dependencies"] = [True]
        with self.assertRaises(ValueError):
            ledger.seed(canonical)

    def test_cli_summary_is_deterministic_and_never_mutates_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.json"
            ledger.write(path, fixture())
            original = path.read_bytes()
            results = []
            for _ in range(2):
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(0, ledger.main(["summary", str(path)]))
                results.append(output.getvalue())
            self.assertEqual(results[0], results[1])
            self.assertEqual(original, path.read_bytes())

    def test_seed_refuses_to_overwrite_existing_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "existing.json"
            ledger.write(path, fixture())
            original = path.read_bytes()
            with redirect_stderr(io.StringIO()):
                self.assertEqual(1, ledger.main(["seed", "unused", str(path)]))
            self.assertEqual(original, path.read_bytes())


if __name__ == "__main__":
    unittest.main()

"""Adversarial acceptance for the reviewed public fixture boundary; no network."""
import errno
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parent
RECEIPT_NAME = "INSTALLED_SOURCE_COMPARISON_2026-11-07.json"


class FixtureVerifierTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="bsre-fixture-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        lab = self.root / "tools" / "staging-lab"
        lab.mkdir(parents=True)
        self.verifier = lab / "verify_fixture.py"
        shutil.copyfile(SOURCE / "verify_fixture.py", self.verifier)
        self.fixture = lab / "fixtures" / "bsre-enquiries"
        shutil.copytree(SOURCE / "fixtures" / "bsre-enquiries", self.fixture)
        audit = self.root / "docs" / "audit"
        audit.mkdir(parents=True)
        self.receipt = audit / RECEIPT_NAME
        shutil.copyfile(SOURCE.parents[1] / "docs" / "audit" / RECEIPT_NAME,
                        self.receipt)

    def run_verifier(self):
        return subprocess.run(
            [sys.executable, "-B", str(self.verifier)],
            cwd=self.root, capture_output=True, text=True, timeout=10,
        )

    def assert_denied(self, result, reason):
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(reason, result.stderr)
        self.assertNotIn('"status": "PASS"', result.stdout)

    def test_reviewed_baseline_passes(self):
        result = self.run_verifier()
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["members"], 30)
        self.assertEqual(receipt["bytes"], 251836)

    def test_tampered_member_is_rejected(self):
        member = self.fixture / "assets" / "assets.css"
        member.write_bytes(member.read_bytes() + b"\n/* synthetic tamper */\n")
        self.assert_denied(self.run_verifier(), "Baseline hash mismatch")

    def test_coordinated_receipt_and_member_tamper_is_rejected(self):
        # An attacker can make the mutable receipt agree with changed source.
        # The separately pinned reviewed manifest must still reject that pair.
        member = self.fixture / "assets" / "assets.css"
        member.write_bytes(b"/* synthetic coordinated tamper */\n")
        receipt = json.loads(self.receipt.read_text(encoding="utf-8-sig"))
        row = next(row for row in receipt["results"]
                   if row["path"] == "assets/assets.css")
        row["target_sha256"] = hashlib.sha256(member.read_bytes()).hexdigest()
        row["target_bytes"] = member.stat().st_size
        self.receipt.write_text(json.dumps(receipt), encoding="utf-8")
        self.assert_denied(self.run_verifier(), "Reviewed member hash manifest changed")

    def test_unexpected_file_is_rejected(self):
        (self.fixture / "unexpected.txt").write_text("synthetic extra member\n")
        self.assert_denied(self.run_verifier(), "Fixture member set differs")

    def test_symlink_member_is_rejected_even_with_matching_bytes(self):
        member = self.fixture / "assets" / "assets.css"
        outside = self.root / "matching-outside-fixture.css"
        outside.write_bytes(member.read_bytes())
        member.unlink()
        try:
            member.symlink_to(outside)
        except NotImplementedError as error:
            self.skipTest("Filesystem/user cannot create symlinks: " + type(error).__name__)
        except OSError as error:
            if error.errno not in (errno.EACCES, errno.EPERM, errno.ENOTSUP) and getattr(error, "winerror", None) != 1314:
                raise
            self.skipTest("Filesystem/user cannot create symlinks: " + type(error).__name__)
        self.assert_denied(self.run_verifier(), "Symlink is not an accepted fixture")


if __name__ == "__main__":
    unittest.main()

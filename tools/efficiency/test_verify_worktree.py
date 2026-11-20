import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import verify_worktree as verifier


class WorktreeVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.git("init", "-q")
        self.git("config", "user.name", "Synthetic Test")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "core.autocrlf", "false")
        (self.root / "plain.txt").write_bytes(b"original\r\nbytes\n")
        (self.root / "space and unicode \u00e9.txt").write_bytes(b"\x00binary\xff\n")
        self.git("add", ".")
        self.git("commit", "-qm", "Synthetic baseline")

    def tearDown(self):
        self.temporary.cleanup()

    def git(self, *args, input_bytes=None):
        return subprocess.check_output(["git", *args], cwd=self.root, input=input_bytes, stderr=subprocess.DEVNULL)

    def test_exact_raw_bytes_and_single_batch(self):
        original = verifier.git
        calls = []
        def observed(root, *args, **kwargs):
            calls.append(args)
            return original(root, *args, **kwargs)
        with patch.object(verifier, "git", side_effect=observed):
            result = verifier.compare(self.root, "HEAD")
        self.assertEqual(result["byte_equal"], 2)
        self.assertEqual(result["different"], [])
        self.assertEqual(sum(call[:2] == ("cat-file", "--batch") for call in calls), 1)
        self.assertEqual(len(calls), 5)

    def test_line_endings_are_not_normalized(self):
        (self.root / "plain.txt").write_bytes(b"original\nbytes\n")
        self.assertEqual(verifier.compare(self.root, "HEAD")["different"], ["plain.txt"])

    def test_local_and_remote_only_paths_are_reported(self):
        (self.root / "new.txt").write_text("synthetic", encoding="utf-8")
        self.git("rm", "-q", "plain.txt")
        result = verifier.compare(self.root, "HEAD")
        self.assertEqual(result["missing_remote"], ["new.txt"])
        self.assertEqual(result["unexpected_remote"], ["plain.txt"])

    def test_ref_is_pinned_before_later_reads(self):
        old_commit = self.git("rev-parse", "HEAD").decode().strip()
        (self.root / "plain.txt").write_bytes(b"new version")
        self.git("commit", "-am", "Second synthetic version", "-q")
        self.git("branch", "moving", old_commit)
        original = verifier.git
        def move_after_pin(root, *args, **kwargs):
            result = original(root, *args, **kwargs)
            if args[:2] == ("rev-parse", "--verify"):
                self.git("branch", "-f", "moving", "HEAD")
            return result
        with patch.object(verifier, "git", side_effect=move_after_pin):
            result = verifier.compare(self.root, "moving")
        self.assertEqual(result["commit"], old_commit)
        self.assertEqual(result["different"], ["plain.txt"])

    @unittest.skipIf(os.name == "nt", "Windows disallows newline filenames")
    def test_newline_and_tab_names_are_not_split(self):
        name = "line\nwith\ttab.txt"
        (self.root / name).write_bytes(b"synthetic\n")
        self.git("add", ".")
        self.git("commit", "-qm", "Unusual synthetic filename")
        result = verifier.compare(self.root, "HEAD")
        self.assertEqual(result["byte_equal"], 3)
        self.assertEqual(result["different"], [])

    def test_local_symlink_is_rejected(self):
        target = self.root / "plain.txt"
        target.unlink()
        try:
            target.symlink_to(self.root / "space and unicode \u00e9.txt")
        except OSError:
            self.skipTest("Symlink creation unavailable")
        with self.assertRaisesRegex(verifier.VerificationError, "symlinks"):
            verifier.compare(self.root, "HEAD")

    def test_submodule_mode_is_rejected(self):
        commit = self.git("rev-parse", "HEAD").decode().strip()
        self.git("update-index", "--add", "--cacheinfo", "160000," + commit + ",module")
        self.git("commit", "-qm", "Synthetic gitlink")
        with self.assertRaisesRegex(verifier.VerificationError, "submodules"):
            verifier.compare(self.root, "HEAD")

    def test_local_junction_is_rejected_without_following_it(self):
        with patch.object(Path, "is_junction", return_value=True, create=True):
            with self.assertRaisesRegex(verifier.VerificationError, "junctions"):
                verifier.local_hash(self.root, b"plain.txt")

    def test_resolved_path_must_stay_inside_repository(self):
        outside = self.root.parent / "synthetic-outside"
        with patch.object(Path, "resolve", return_value=outside):
            with self.assertRaisesRegex(verifier.VerificationError, "outside"):
                verifier.local_hash(self.root, b"plain.txt")

    def test_empty_tree_needs_no_batch(self):
        self.git("rm", "-q", "plain.txt", "space and unicode \u00e9.txt")
        self.git("commit", "-qm", "Synthetic empty tree")
        self.assertEqual(verifier.compare(self.root, "HEAD")["byte_equal"], 0)

    def test_cli_mismatch_is_nonzero_and_does_not_write(self):
        (self.root / "plain.txt").write_bytes(b"changed")
        before = set(self.root.rglob("*"))
        output = io.StringIO()
        with redirect_stdout(output):
            code = verifier.main(["--root", str(self.root), "--ref", "HEAD"])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output.getvalue())["different"], ["plain.txt"])
        self.assertEqual(before, set(self.root.rglob("*")))

    def test_missing_tracked_file_cannot_claim_equality(self):
        (self.root / "plain.txt").unlink()
        with self.assertRaisesRegex(verifier.VerificationError, "unavailable"):
            verifier.compare(self.root, "HEAD")


class GitBatchFramingTests(unittest.TestCase):
    def setUp(self):
        self.object_id = b"a" * 40
        self.payload = b"\x00\nsynthetic\xff"
        self.objects = {self.object_id: len(self.payload)}
        self.data = self.object_id + b" blob " + str(len(self.payload)).encode() + b"\n" + self.payload + b"\n"

    def test_binary_body_uses_declared_size(self):
        self.assertEqual(verifier.batch_hashes(self.data, self.objects), {
            self.object_id: hashlib.sha256(self.payload).digest()})

    def test_missing_truncated_wrong_or_extra_data_is_rejected(self):
        variants = [b"", self.data[:-1], self.data[:-3], self.data + b"extra",
                    self.data.replace(b" blob ", b" tree ", 1),
                    self.data.replace(self.object_id, b"b" * 40, 1)]
        for data in variants:
            with self.subTest(data_length=len(data)), self.assertRaises(verifier.VerificationError):
                verifier.batch_hashes(data, self.objects)

    def test_nul_listing_must_be_complete(self):
        with self.assertRaises(verifier.VerificationError):
            verifier.nul_records(b"incomplete")

    def test_tree_symlink_is_rejected(self):
        with self.assertRaisesRegex(verifier.VerificationError, "Symlinks"):
            verifier.tree_records(b"120000 blob " + self.object_id + b" 6\tlink\0")


if __name__ == "__main__":
    unittest.main()

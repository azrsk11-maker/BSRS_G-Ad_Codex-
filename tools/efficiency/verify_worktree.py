"""Compare working files with one pinned Git commit without changing either.

One cat-file batch replaces a Git process per file. Contents are compared as raw
bytes, including line endings. Reports contain relative paths and counts only.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess


MAX_BLOB_BYTES = 64 * 1024 * 1024
MAX_BATCH_BYTES = 256 * 1024 * 1024
MAX_FILES = 100_000
GIT_TIMEOUT_SECONDS = 120
OBJECT_ID = re.compile(rb"[0-9a-f]{40}(?:[0-9a-f]{24})?\Z")


class VerificationError(ValueError):
    """Verification could not establish a complete byte comparison."""


def git(root, *args, input_bytes=None):
    try:
        result = subprocess.run(
            ["git", *args], cwd=root, input=input_bytes, capture_output=True,
            timeout=GIT_TIMEOUT_SECONDS, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise VerificationError("Git could not finish verification.") from error
    if result.returncode:
        raise VerificationError("Git rejected a verification command.")
    return result.stdout


def nul_records(data):
    if not data:
        return []
    if not data.endswith(b"\0"):
        raise VerificationError("Incomplete Git path listing.")
    records = data[:-1].split(b"\0")
    if len(records) > MAX_FILES or any(not record for record in records):
        raise VerificationError("Invalid or oversized Git path listing.")
    return records


def tree_records(data):
    records = {}
    for record in nul_records(data):
        try:
            metadata, name = record.split(b"\t", 1)
            mode, kind, object_id, size_text = metadata.split()
        except (ValueError, TypeError) as error:
            raise VerificationError("Invalid Git tree record.") from error
        if mode not in (b"100644", b"100755") or kind != b"blob":
            raise VerificationError("Symlinks and submodules need separate verification.")
        try:
            size = int(size_text)
        except ValueError as error:
            raise VerificationError("Invalid Git blob size.") from error
        if not OBJECT_ID.fullmatch(object_id) or size < 0 or size > MAX_BLOB_BYTES:
            raise VerificationError("Invalid or oversized Git blob.")
        if name in records:
            raise VerificationError("Duplicate Git tree path.")
        records[name] = (object_id, size)
    return records


def batch_hashes(data, objects):
    """Validate cat-file framing before hashing the exact payload bytes."""
    hashes = {}
    offset = 0
    view = memoryview(data)
    for expected_id, expected_size in objects.items():
        newline = data.find(b"\n", offset, offset + 128)
        if newline < 0:
            raise VerificationError("Incomplete Git batch header.")
        fields = data[offset:newline].split()
        if fields != [expected_id, b"blob", str(expected_size).encode("ascii")]:
            raise VerificationError("Unexpected Git batch object.")
        start = newline + 1
        end = start + expected_size
        if end >= len(data) or data[end:end + 1] != b"\n":
            raise VerificationError("Incomplete Git batch body.")
        hashes[expected_id] = hashlib.sha256(view[start:end]).digest()
        offset = end + 1
    if offset != len(data):
        raise VerificationError("Unexpected trailing Git batch data.")
    return hashes


def local_hash(root, name):
    path = root / os.fsdecode(name)
    relative = Path(os.fsdecode(name))
    if relative.is_absolute() or ".." in relative.parts:
        raise VerificationError("Unsafe Git path.")
    try:
        current = root
        for part in relative.parts:
            current = current / part
            if current.is_symlink() or getattr(current, "is_junction", lambda: False)():
                raise VerificationError("Local symlinks and junctions need separate verification.")
            if not current.resolve(strict=True).is_relative_to(root):
                raise VerificationError("Local path resolves outside the repository.")
        before = path.stat()
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_BLOB_BYTES:
            raise VerificationError("Local path is not a bounded regular file.")
        value = path.read_bytes()
        after = path.stat()
    except OSError as error:
        raise VerificationError("Local file became unavailable.") from error
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (
        after.st_size, after.st_mtime_ns, after.st_ino
    ) or len(value) != before.st_size:
        raise VerificationError("Local file changed during verification.")
    return hashlib.sha256(value).digest()


def compare(root, ref):
    root = Path(root).resolve(strict=True)
    actual_root = Path(os.fsdecode(git(root, "rev-parse", "--show-toplevel").rstrip(b"\r\n"))).resolve()
    if actual_root != root:
        raise VerificationError("Choose the repository root for verification.")
    commit_bytes = git(root, "rev-parse", "--verify", "--end-of-options", ref + "^{commit}").strip()
    if not OBJECT_ID.fullmatch(commit_bytes):
        raise VerificationError("Invalid pinned commit.")
    commit = commit_bytes.decode("ascii")
    local = set(nul_records(git(root, "ls-files", "--cached", "--others", "--exclude-standard", "--full-name", "-z")))
    remote = tree_records(git(root, "ls-tree", "-rzl", "--full-tree", commit))
    shared = sorted(local & remote.keys())
    objects = {}
    for name in shared:
        object_id, size = remote[name]
        objects[object_id] = size
    if sum(objects.values()) > MAX_BATCH_BYTES:
        raise VerificationError("Git batch exceeds the verification size limit.")
    hashes = {}
    if objects:
        requests = b"".join(object_id + b"\n" for object_id in objects)
        hashes = batch_hashes(git(root, "cat-file", "--batch", input_bytes=requests), objects)
    different = [name for name in shared if local_hash(root, name) != hashes[remote[name][0]]]
    return {
        "ref": ref, "commit": commit, "local_files": len(local), "remote_files": len(remote),
        "missing_remote": sorted(map(os.fsdecode, local - remote.keys())),
        "unexpected_remote": sorted(map(os.fsdecode, remote.keys() - local)),
        "different": sorted(map(os.fsdecode, different)),
        "byte_equal": len(shared) - len(different), "production_changes": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--ref", default="origin/codex/phase0-audit-foundation")
    args = parser.parse_args(argv)
    try:
        result = compare(args.root, args.ref)
    except (VerificationError, OSError) as error:
        print(json.dumps({"verified": False, "error": str(error), "production_changes": False}))
        return 2
    print(json.dumps(result))
    return int(bool(result["missing_remote"] or result["unexpected_remote"] or result["different"]))


if __name__ == "__main__":
    raise SystemExit(main())

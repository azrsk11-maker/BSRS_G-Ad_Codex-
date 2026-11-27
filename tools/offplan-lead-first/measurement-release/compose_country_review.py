"""Reproduce the tested country transport from its retained private review ZIP."""

from argparse import ArgumentParser
from io import BytesIO
import json
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from pack_plugin_review import HASH, PLUGIN, archive_bytes, digest, read_json, valid_member


HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[2]
REVIEW = HERE / "COUNTRY_TRANSPORT_REVIEW.json"
MAX_MEMBER_BYTES = 1024 * 1024


def apply_edits(previous, edits):
    """Offsets refer to original bytes, including line endings and Unicode."""
    result = bytearray()
    cursor = 0
    for edit in edits:
        start, removal = edit["offset"], edit["remove"]
        if type(start) is not int or type(removal) is not int or not cursor <= start <= len(previous):
            raise ValueError("Invalid or overlapping original offsets")
        if removal < 0 or start + removal > len(previous):
            raise ValueError("Edit extends beyond the original member")
        result.extend(previous[cursor:start])
        lines = edit["lines"]
        if not isinstance(lines, list) or any(not isinstance(line, str) for line in lines):
            raise ValueError("Replacement must be an ordered list of text lines")
        result.extend("".join(lines).encode("utf-8"))
        cursor = start + removal
    result.extend(previous[cursor:])
    if len(result) > MAX_MEMBER_BYTES:
        raise ValueError("Reproduced member is oversized")
    return bytes(result)


def compose(base, review):
    if review["scope"] != "OFFPLAN_COUNTRY_TRANSPORT_REVIEW_ONLY" or digest(base) != review["base_archive_sha256"]:
        raise ValueError("Input is not the pinned private forward review ZIP")
    approved = review["candidate_members"]
    if (len(approved) != review["candidate_member_count"] or len(approved) != 51
        or len({name.casefold() for name in approved}) != len(approved)
        or any(not valid_member(name) or not HASH.fullmatch(sha) for name, sha in approved.items())):
        raise ValueError("Invalid reviewed country inventory")

    files = {}
    prefix = PLUGIN + "/"
    with ZipFile(BytesIO(base)) as archive:
        if len(archive.infolist()) != review["base_member_count"] or len(archive.infolist()) != 49:
            raise ValueError("Wrong baseline member count")
        for member in archive.infolist():
            path = member.filename.removeprefix(prefix)
            if (not member.filename.startswith(prefix) or path not in approved or path in files
                or not valid_member(path) or member.file_size > MAX_MEMBER_BYTES):
                raise ValueError("Invalid baseline member")
            files[path] = archive.read(member)

    for path, change in review["changes"].items():
        previous = files.get(path)
        expected = digest(previous) if previous is not None else None
        if path not in approved or expected != change["before"]:
            raise ValueError("Change identity does not match its preimage")
        files[path] = apply_edits(previous or b"", change["edits"])
    if {path: digest(body) for path, body in files.items()} != approved:
        raise ValueError("Candidate does not match the tested byte inventory")
    return archive_bytes(dict(sorted(files.items())))


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("base_zip", type=Path)
    parser.add_argument("output_zip", type=Path)
    args = parser.parse_args()
    try:
        out = args.output_zip.resolve()
        if out.is_relative_to(SOURCE) or out.suffix.lower() != ".zip":
            raise ValueError("Use a new private ZIP path outside the Source worktree")
        with args.base_zip.open("rb") as stream:
            base = stream.read(MAX_MEMBER_BYTES + 1)
        if len(base) > MAX_MEMBER_BYTES:
            raise ValueError("Baseline ZIP outside review bounds")
        result = compose(base, read_json(REVIEW))
        with out.open("xb") as stream:
            stream.write(result)
    except (OSError, ValueError, KeyError, TypeError, BadZipFile) as error:
        print(json.dumps({"status": "HOLD", "reason": str(error)}))
        return 1
    print(json.dumps({"status": "MATCHED_TESTED_PRIVATE_REVIEW", "members": 51, "sha256": digest(result),
                      "ready_to_install": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Create or verify a complete WordPress plugin archive pair for private review."""

from argparse import ArgumentParser
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path, PurePosixPath
import re
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


PLUGIN = "bsre-enquiries"
ENTRYPOINT = "bsre-enquiries.php"
HASH = re.compile(r"[a-f0-9]{64}\Z")
MEMBER = re.compile(r"[A-Za-z0-9._/-]+\Z")


def digest(data):
    return sha256(data).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def valid_member(name):
    path = PurePosixPath(name)
    return (MEMBER.fullmatch(name) and not path.is_absolute() and path.as_posix() == name
            and not any(part.startswith(".") for part in path.parts)
            and path.suffix in {".php", ".js", ".css", ".html", ".json"})


def reviewed_rosters(review, original_receipt):
    old_rows = original_receipt["results"]
    baseline = {row["path"]: row["current_raw_sha256"] for row in old_rows}
    if len(baseline) != len(old_rows) or len(baseline) != review["original_member_count"] or len(baseline) != 30:
        raise ValueError("Retained file inventory disagrees with the review")
    candidate = baseline.copy()
    for path, delta in review["changes"].items():
        if baseline.get(path) != delta["before"]:
            raise ValueError("Forward delta has a different retained preimage")
        candidate[path] = delta["after"]
    if len(candidate) != review["candidate_member_count"] or len(candidate) != 49 or review["ready_to_install"] is not False:
        raise ValueError("Expected the exact review-only pair")
    for inventory in (baseline, candidate):
        if ENTRYPOINT not in inventory or any(not valid_member(name) or not isinstance(value, str) or not HASH.fullmatch(value)
                                            for name, value in inventory.items()):
            raise ValueError("Review contains an invalid member identity")
        if len({name.casefold() for name in inventory}) != len(inventory):
            raise ValueError("File inventory collides on a case-insensitive host")
    return {"forward": candidate, "rollback": baseline}


def verified_payloads(root, inventory):
    if root.resolve() != root.absolute() or not root.is_dir():
        raise ValueError("Review members require a regular directory")
    entries = {str(path.relative_to(root).as_posix()) for path in root.rglob("*") if path.is_file() or path.is_symlink()}
    if entries != inventory.keys():
        raise ValueError("Review directory contains extra or missing files")
    files = {}
    for name, expected in sorted(inventory.items()):
        path = root / name
        if path.resolve() != path.absolute() or not path.is_file() or path.stat().st_size > 1024 * 1024:
            raise ValueError("Review member is not a bounded regular file")
        data = path.read_bytes()
        if digest(data) != expected:
            raise ValueError("Review member no longer matches its SHA-256")
        files[name] = data
    return files


def archive_bytes(files):
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        for name, data in files.items():
            entry = ZipInfo(f"{PLUGIN}/{name}", date_time=(1980, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, data, compress_type=ZIP_DEFLATED, compresslevel=9)
    data = output.getvalue()
    with ZipFile(BytesIO(data)) as archive:
        expected = {f"{PLUGIN}/{name}": content for name, content in files.items()}
        if len(archive.infolist()) != len(expected) or any(
            archive.read(name) != body for name, body in expected.items()
        ):
            raise ValueError("ZIP round-trip did not preserve the reviewed files")
    return data


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--preimage-receipt", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    review = read_json(args.review / "REVIEW.json")
    rosters = reviewed_rosters(review, read_json(args.preimage_receipt))
    packages = {}
    receipt = {"status": "PRIVATE_REVIEW_ONLY", "ready_to_install": False, "archives": {}}
    for direction, inventory in rosters.items():
        files = verified_payloads(args.review / direction, inventory)
        version = re.search(rb"(?m)^ \* Version:\s*([0-9.]+)\s*\r?$", files[ENTRYPOINT])
        if not version:
            raise ValueError("Plugin header version could not be verified")
        version = version[1].decode("ascii")
        if (direction == "forward" and version != "0.2.15") or (direction == "rollback" and version != "0.2.12"):
            raise ValueError("Plugin header version disagrees with this review")
        archive = archive_bytes(files)
        name = f"{PLUGIN}-{version}-{direction}-PRIVATE-REVIEW.zip"
        packages[name] = archive
        receipt["archives"][direction] = {"file": name, "version": version, "members": len(files),
                                         "bytes": len(archive), "sha256": digest(archive)}
    packages["ARCHIVE_RECEIPT.json"] = (json.dumps(receipt, indent=2) + "\n").encode("utf-8")
    if args.check:
        if set(path.name for path in args.out.iterdir()) != packages.keys() or any(
            (args.out / name).is_symlink() or (args.out / name).read_bytes() != data for name, data in packages.items()
        ):
            raise ValueError("The reviewed archive output changed")
    else:
        args.out.mkdir(exist_ok=False)
        for name, data in packages.items():
            (args.out / name).write_bytes(data)
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()

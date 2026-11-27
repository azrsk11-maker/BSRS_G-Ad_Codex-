"""Compare a scoped live plugin ZIP with the retained review rollback offline."""

from argparse import ArgumentParser
from io import BytesIO
import json
from pathlib import Path, PurePosixPath
import stat
from zipfile import BadZipFile, ZIP_DEFLATED, ZIP_STORED, ZipFile

from pack_plugin_review import ENTRYPOINT, HASH, PLUGIN, digest, valid_member


ROLLBACK_SHA256 = "fe7c6d2fd8d6e23d78f77f6a3b08dd12b648fe7731931d42c323019e20b1ab79"
MEMBER_COUNT = 30
MAX_ARCHIVE_BYTES = 2 * 1024 * 1024
MAX_UNPACKED_BYTES = 1024 * 1024
MAX_ENTRIES = 100
WRAPPER = PLUGIN + "/"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_pinned_zip(path, expected_hash):
    require(isinstance(expected_hash, str) and HASH.fullmatch(expected_hash) is not None,
            "Expected a lowercase SHA-256")
    require(path.is_file() and not path.is_symlink(), "Expected a regular ZIP file")
    with path.open("rb") as stream:
        raw = stream.read(MAX_ARCHIVE_BYTES + 1)
    require(0 < len(raw) <= MAX_ARCHIVE_BYTES, "Archive exceeds the comparison size limit")
    require(digest(raw) == expected_hash, "Archive SHA-256 differs from its capture")
    return raw


def inventory(archive):
    entries = archive.infolist()
    require(len(entries) <= MAX_ENTRIES, "Too many archive entries")
    require(sum(info.file_size for info in entries) <= MAX_UNPACKED_BYTES,
            "Archive exceeds the expanded size limit")
    wrapped = any(info.filename.startswith(WRAPPER) for info in entries)
    members, dirs, seen = {}, set(), set()
    for info in entries:
        name = info.filename
        require(name == info.orig_filename and (not wrapped or name.startswith(WRAPPER)),
                "Archive contains entries outside the plugin folder")
        relative = name[len(WRAPPER):] if wrapped else name
        is_dir = info.is_dir()
        key = relative.removesuffix("/") if is_dir else relative
        require(key.casefold() not in seen, "Archive paths collide on a case-insensitive host")
        seen.add(key.casefold())

        mode = stat.S_IFMT(info.external_attr >> 16)
        require(mode in (0, stat.S_IFDIR if is_dir else stat.S_IFREG)
                and not info.flag_bits & 1 and info.compress_type in (ZIP_STORED, ZIP_DEFLATED),
                "Archive contains an unsupported entry type")
        if is_dir:
            require(info.file_size == 0, "Archive directory has a payload")
            dirs.add(key)
        else:
            require(valid_member(key), "Archive contains an invalid plugin member path")
            members[key] = info

    valid_dirs = {parent.as_posix() for key in members for parent in PurePosixPath(key).parents}
    valid_dirs.discard(".")
    if wrapped:
        valid_dirs.add("")
    require(dirs <= valid_dirs, "Archive contains an unrelated or invalid folder")
    require(len(members) == MEMBER_COUNT and ENTRYPOINT in members, "Unexpected installed plugin inventory")
    return members


def verify(export, rollback, export_sha256):
    require(not export.samefile(rollback), "Use distinct capture and rollback files")
    retained = read_pinned_zip(rollback, ROLLBACK_SHA256)
    observed = read_pinned_zip(export, export_sha256)
    with ZipFile(BytesIO(retained)) as original, ZipFile(BytesIO(observed)) as current:
        reference = inventory(original)
        installed = inventory(current)
        require(installed.keys() == reference.keys(), "Installed member names differ from the retained rollback")
        # Read only the exact scoped roster. Never extract or access unexpected members.
        for name in reference:
            require(current.read(installed[name]) == original.read(reference[name]),
                    "Installed member bytes differ from the retained rollback")
    return {
        "status": "MATCHED_RETAINED_ROLLBACK_MEMBERS",
        "export_sha256": export_sha256,
        "rollback_sha256": ROLLBACK_SHA256,
        "matched_members": MEMBER_COUNT,
        "authenticated_host_origin_verified_here": False,
        "production_change_authorized": False,
    }


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("export", type=Path)
    parser.add_argument("rollback", type=Path)
    parser.add_argument("--export-sha256", required=True)
    args = parser.parse_args()
    try:
        result = verify(args.export, args.rollback, args.export_sha256)
    except (BadZipFile, NotImplementedError):
        parser.exit(1, "Verification failed. Unsupported or corrupt archive.\n")
    except OSError:
        parser.exit(1, "Verification failed. A scoped input could not be read.\n")
    except ValueError as error:
        parser.exit(1, f"Verification failed. {error}.\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

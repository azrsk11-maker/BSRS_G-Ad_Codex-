from io import BytesIO
from pathlib import Path
import stat
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZipFile, ZipInfo

import check_hostinger_preimage as check
from pack_plugin_review import ENTRYPOINT, PLUGIN, archive_bytes, digest


FILES = {ENTRYPOINT: b"<?php // synthetic fixture\n"} | {
    f"assets/fixture-{index}.js": f"// clean synthetic file {index}\n".encode()
    for index in range(check.MEMBER_COUNT - 1)
}


def capture_bytes(files=FILES, *, wrapped=True, dirs=(), special_entries=()):
    prefix = PLUGIN + "/" if wrapped else ""
    stream = BytesIO()
    with ZipFile(stream, "w") as archive:
        for name in dirs:
            archive.writestr(prefix + name, b"")
        for name, body in files.items():
            archive.writestr(prefix + name, body)
        for member, body in special_entries:
            archive.writestr(member, body)
    return stream.getvalue()


class HostingerArchiveTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(TemporaryDirectory())
        self.export = Path(directory) / "capture.zip"
        self.rollback = Path(directory) / "rollback.zip"
        retained = archive_bytes(FILES)
        self.rollback.write_bytes(retained)
        self.enterContext(patch.object(check, "ROLLBACK_SHA256", digest(retained)))

    def verify_capture(self, raw, export_sha256=None):
        self.export.write_bytes(raw)
        return check.verify(self.export, self.rollback, export_sha256 or digest(raw))

    def test_folder_export_ignores_compression_and_explicit_directory_records(self):
        report = self.verify_capture(capture_bytes(dirs=("", "assets/")))
        self.assertEqual(report["matched_members"], 30)
        self.assertFalse(report["authenticated_host_origin_verified_here"])
        self.assertFalse(report["production_change_authorized"])
        self.assertNotEqual(report["export_sha256"], report["rollback_sha256"])

    def test_direct_plugin_contents_are_compared(self):
        report = self.verify_capture(capture_bytes(wrapped=False, dirs=("assets/",)))
        self.assertEqual(report["status"], "MATCHED_RETAINED_ROLLBACK_MEMBERS")

    def test_changed_body_with_same_names_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "bytes differ"):
            self.verify_capture(capture_bytes(FILES | {ENTRYPOINT: b"<?php // drift\n"}))

    def test_unexpected_name_fails_before_reading_member_data(self):
        files = {key: value for key, value in FILES.items() if key != "assets/fixture-0.js"}
        files["wp-config.php"] = b"synthetic unscopeable member"
        with patch.object(ZipFile, "read", side_effect=AssertionError("unexpected content read")):
            with self.assertRaisesRegex(ValueError, "names differ"):
                self.verify_capture(capture_bytes(files))

    def test_missing_member_is_rejected(self):
        files = {key: value for key, value in FILES.items() if key != "assets/fixture-0.js"}
        with self.assertRaisesRegex(ValueError, "Unexpected installed plugin inventory"):
            self.verify_capture(capture_bytes(files))

    def test_case_collision_and_traversal_are_rejected(self):
        for added, message in (("assets/FIXTURE-0.js", "collide"), ("../fixture.php", "invalid plugin member")):
            with self.subTest(added=added):
                with self.assertRaisesRegex(ValueError, message):
                    self.verify_capture(capture_bytes(FILES | {added: b"synthetic"}))

    def test_mixed_root_and_unrelated_empty_folder_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "outside the plugin folder"):
            self.verify_capture(capture_bytes(special_entries=(("outside.php", b""),)))
        with self.assertRaisesRegex(ValueError, "unrelated or invalid folder"):
            self.verify_capture(capture_bytes(dirs=("elsewhere/",)))

    def test_symbolic_link_and_oversized_payload_are_rejected(self):
        link = ZipInfo(PLUGIN + "/linked.php")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        with self.assertRaisesRegex(ValueError, "unsupported entry type"):
            self.verify_capture(capture_bytes(special_entries=((link, b"target"),)))
        oversize = b"0" * (check.MAX_UNPACKED_BYTES + 1)
        with self.assertRaisesRegex(ValueError, "expanded size limit"):
            self.verify_capture(capture_bytes(FILES | {ENTRYPOINT: oversize}))

    def test_changed_capture_pin_and_retained_pin_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "SHA-256 differs"):
            self.verify_capture(capture_bytes(), "a" * 64)
        self.rollback.write_bytes(b"drift")
        with self.assertRaisesRegex(ValueError, "SHA-256 differs"):
            self.verify_capture(capture_bytes())

    def test_single_file_cannot_pose_as_both_inputs(self):
        with self.assertRaisesRegex(ValueError, "distinct capture and rollback"):
            check.verify(self.rollback, self.rollback, check.ROLLBACK_SHA256)


if __name__ == "__main__":
    unittest.main()

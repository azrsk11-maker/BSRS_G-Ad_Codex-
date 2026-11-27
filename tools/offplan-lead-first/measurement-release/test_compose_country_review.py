from copy import deepcopy
from io import BytesIO
import unittest
from zipfile import ZipFile

from compose_country_review import apply_edits, compose
from pack_plugin_review import PLUGIN, archive_bytes, digest


class PrivateReviewComposerTest(unittest.TestCase):
    def setUp(self):
        originals = {f"fixture/part-{n:02d}.js": f"// {n}\r\n".encode() for n in range(49)}
        self.base = archive_bytes(originals)
        self.final = {**originals, "new.php": b"<?php exit;\n", "new.js": b"'use strict';\n"}
        self.review = {
            "scope": "OFFPLAN_COUNTRY_TRANSPORT_REVIEW_ONLY", "base_archive_sha256": digest(self.base),
            "base_member_count": 49, "candidate_member_count": 51,
            "candidate_members": {name: digest(body) for name, body in self.final.items()},
            "changes": {name: {"before": None, "edits": [{"offset": 0, "remove": 0, "lines": [self.final[name].decode()]}]}
                        for name in ("new.php", "new.js")},
        }

    def test_review_reproduces_exact_deterministic_archive(self):
        archive = compose(self.base, self.review)
        self.assertEqual(archive, compose(self.base, self.review))
        with ZipFile(BytesIO(archive)) as zip_file:
            self.assertEqual({name: zip_file.read(f"{PLUGIN}/{name}") for name in self.final}, self.final)

    def test_offsets_use_original_bytes(self):
        original = "日本\r\nrest\n".encode()
        review = [{"offset": len("日本\r\n".encode()), "remove": 4, "lines": ["été"]}]
        self.assertEqual(apply_edits(original, review), "日本\r\nété\n".encode())

    def test_overlapping_changes_reject(self):
        edits = [{"offset": 1, "remove": 2, "lines": []}, {"offset": 2, "remove": 0, "lines": ["x"]}]
        with self.assertRaisesRegex(ValueError, "overlapping"):
            apply_edits(b"abcdef", edits)

    def test_base_tamper_rejects_before_zip_parsing(self):
        with self.assertRaisesRegex(ValueError, "not the pinned"):
            compose(self.base + b"invalid", self.review)

    def test_wrong_preimage_rejected(self):
        tampered = deepcopy(self.review)
        tampered["changes"]["new.js"]["before"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "does not match its preimage"):
            compose(self.base, tampered)

    def test_changed_text_cannot_create_unreviewed_output(self):
        tampered = deepcopy(self.review)
        tampered["changes"]["new.js"]["edits"][0]["lines"].append("unreviewed content")
        with self.assertRaisesRegex(ValueError, "does not match the tested byte inventory"):
            compose(self.base, tampered)


if __name__ == "__main__":
    unittest.main()

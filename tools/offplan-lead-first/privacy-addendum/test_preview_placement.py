from hashlib import sha256
import json
import unittest

from preview_placement import ANCHOR, HERE, PAGE_ID, PUBLIC_URL, SLUG, preview
from verify_drafts import GOOGLE, HEADING


class NoticePlacementTests(unittest.TestCase):
    def setUp(self):
        self.original = ('<article class="bsre-enquiry-privacy"><h1>Notice</h1>\n'
                         '<p>Effective date</p>\n<h2>Your choices</h2>\n<p>Original choices</p>\n</article>')
        self.page = {"id": PAGE_ID, "link": PUBLIC_URL, "slug": SLUG, "status": "publish", "type": "page",
                     "content": {"rendered": self.original, "protected": False}}

    def compose(self):
        raw = json.dumps(self.page).encode()
        return preview(raw, sha256(raw).hexdigest())

    def test_exact_insertion_preserves_every_original_byte(self):
        fragment = (HERE / "NOTICE_ADDENDUM.en.html").read_bytes()
        output = self.compose()
        self.assertEqual(output.count(fragment), 1)
        self.assertEqual(output.replace(fragment, b"", 1), self.original.encode())
        self.assertEqual(output.split(fragment, 1)[1][:len(ANCHOR)], ANCHOR)

    def test_refuses_stale_capture(self):
        with self.assertRaisesRegex(ValueError, "capture differs"):
            preview(json.dumps(self.page).encode(), "0" * 64)

    def test_refuses_wrong_page_or_status(self):
        for field, value in (("id", PAGE_ID + 1), ("link", PUBLIC_URL + "other/"), ("status", "draft")):
            with self.subTest(field=field):
                original = self.page[field]
                self.page[field] = value
                with self.assertRaisesRegex(ValueError, "identity differs"):
                    self.compose()
                self.page[field] = original

    def test_refuses_edit_context_content(self):
        self.page["content"]["raw"] = self.original
        with self.assertRaisesRegex(ValueError, "rendered content"):
            self.compose()

    def test_refuses_absent_or_duplicate_anchor(self):
        for replacements in ("", ANCHOR.decode() * 2):
            with self.subTest(replacements=replacements):
                self.page["content"]["rendered"] = self.original.replace(ANCHOR.decode(), replacements)
                with self.assertRaisesRegex(ValueError, "heading is missing or ambiguous"):
                    self.compose()

    def test_refuses_disclosure_already_present(self):
        for node in (f'<p id="{HEADING}">Existing</p>', f'<a href="{GOOGLE}">Google</a>'):
            with self.subTest(node=node):
                self.page["content"]["rendered"] = self.original.replace("</article>", node + "</article>")
                with self.assertRaisesRegex(ValueError, "already exists"):
                    self.compose()

    def test_refuses_active_or_external_markup(self):
        for node in ('<script src="https://example.test/payload.js"></script>',
                     '<p onclick="alert(1)">Existing</p>',
                     '<a href="https://example.test/">External</a>'):
            with self.subTest(node=node):
                self.page["content"]["rendered"] = self.original.replace("</article>", node + "</article>")
                with self.assertRaisesRegex(ValueError, "captured static article"):
                    self.compose()


if __name__ == "__main__":
    unittest.main()

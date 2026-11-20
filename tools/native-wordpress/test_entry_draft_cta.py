"""Synthetic mutations of the existing private drafts; no website or Ads writes."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import compile_entry_cohort as c


class EntryDraftCtaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs, cls.pins = c.load_inputs()
        # This independent read also makes the pre-fix regression reproducible.
        cls.inputs['draft_fragments'] = {
            name: (c.ROOT / 'tools/native-wordpress/entry-drafts' / name).read_text(encoding='utf-8')
            for name in ('buyers.html', 'owners.html')
        }

    def reject_fragment(self, name, mutate, code='DRAFT_CTA_ROUTES_CHANGED'):
        inputs = deepcopy(self.inputs)
        inputs['draft_fragments'][name] = mutate(inputs['draft_fragments'][name])
        with self.assertRaisesRegex(ValueError, code):
            c.compile_proposal(inputs, self.pins)

    def test_existing_fragments_preserve_exact_saved_proposal(self):
        saved = json.loads((c.ROOT / c.OUTPUT).read_text(encoding='utf-8'))
        self.assertEqual(c.compile_proposal(self.inputs, self.pins), saved)

    def test_wrong_role_route_rejected_for_each_campaign(self):
        for name, route in (('buyers.html', '/enquire/off-plan/'), ('owners.html', '/enquire/sell/')):
            with self.subTest(name=name):
                self.reject_fragment(name, lambda body: body.replace(route, '/enquire/rent/'))

    def test_primary_and_secondary_cta_order_cannot_be_swapped(self):
        for name, first, second in (
                ('buyers.html', '/enquire/off-plan/', '/enquire/resale/'),
                ('owners.html', '/enquire/sell/', '/enquire/let/')):
            with self.subTest(name=name):
                self.reject_fragment(name, lambda body: body.replace(first, '/temporary/').replace(second, first).replace('/temporary/', second))

    def test_external_protocol_relative_or_tracking_url_rejected(self):
        for replacement in ('https://example.invalid/enquire/off-plan/', '//example.invalid/enquire/off-plan/',
                            '/enquire/off-plan/?utm_source=internal', '/enquire/off-plan/?gclid=synthetic',
                            '/enquire/off-plan/#form', 'javascript:void(0)'):
            with self.subTest(replacement=replacement):
                self.reject_fragment('buyers.html', lambda body: body.replace('/enquire/off-plan/', replacement))

    def test_extra_missing_or_duplicate_destination_rejected(self):
        self.reject_fragment('buyers.html', lambda body: body.replace('/enquire/resale/', '/enquire/off-plan/'))
        self.reject_fragment('buyers.html', lambda body: body[:body.index('<!-- wp:buttons -->')])
        self.reject_fragment('buyers.html', lambda body: body + '<a class="wp-block-button__link wp-element-button" href="/enquire/rent/">Synthetic extra</a>')

    def test_duplicate_href_and_override_attributes_rejected(self):
        for addition in (' href="/enquire/rent/"', ' onclick="return false"', ' target="_blank"',
                         ' style="display:none"', ' ping="https://example.invalid/"'):
            with self.subTest(addition=addition):
                self.reject_fragment('buyers.html', lambda body: body.replace('<a ', '<a' + addition + ' ', 1),
                                     'DRAFT_UNSUPPORTED_ATTRIBUTES')

    def test_dynamic_blocks_scripts_forms_and_resources_rejected(self):
        for addition in ('<script>void(0)</script>', '<form action="/enquire/rent/"></form>',
                         '<img src="https://example.invalid/synthetic.png">',
                         '<!-- wp:html --><!-- /wp:html -->', '<?synthetic processing?>'):
            with self.subTest(addition=addition):
                self.reject_fragment('buyers.html', lambda body: body + addition, 'DRAFT_UNSUPPORTED_MARKUP')

    def test_malformed_nesting_and_empty_cta_rejected(self):
        self.reject_fragment('buyers.html', lambda body: body.replace('</a>', '</div>', 1), 'DRAFT_INVALID_NESTING')
        self.reject_fragment('buyers.html', lambda body: body.replace('Discuss an off-plan purchase', ' '), 'DRAFT_CTA_LABEL_REQUIRED')

    def test_harmless_copy_change_can_be_recompiled_without_reauthorizing_release(self):
        inputs = deepcopy(self.inputs)
        inputs['draft_fragments']['buyers.html'] = inputs['draft_fragments']['buyers.html'].replace('your timing', 'your preferred timing')
        pins = dict(self.pins)
        pins['tools/native-wordpress/entry-drafts/buyers.html'] = hashlib.sha256(inputs['draft_fragments']['buyers.html'].encode('utf-8')).hexdigest()
        result = c.compile_proposal(inputs, pins)
        self.assertFalse(result['apply_supported'])
        self.assertFalse(result['website_publication_authorized'])
        self.assertFalse(result['ads_changes_authorized'])
        self.assertEqual(result['source_page_count'], 360)
        self.assertEqual(len(result['source_family_counts']), 15)

    def test_fragment_text_cannot_reuse_a_different_content_pin(self):
        self.reject_fragment('buyers.html', lambda body: body.replace('your timing', 'your preferred timing'),
                             'DRAFT_FRAGMENT_PIN_MISMATCH')

    def test_load_inputs_binds_actual_fragment_bytes_before_compile(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = list(c.INPUTS.values()) + ['tools/native-wordpress/entry-drafts/' + name for name in ('buyers.html', 'owners.html')]
            for relative in paths:
                destination = root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(c.ROOT / relative, destination)
            target = root / 'tools/native-wordpress/entry-drafts/buyers.html'
            target.write_bytes(target.read_bytes().replace(b'/enquire/off-plan/', b'/enquire/rent/'))
            with self.assertRaisesRegex(ValueError, 'DRAFT_CTA_ROUTES_CHANGED'):
                c.build_proposal(root)

    def test_missing_fragment_cannot_be_supplied_only_by_a_digest(self):
        inputs = deepcopy(self.inputs)
        inputs.pop('draft_fragments')
        with self.assertRaisesRegex(ValueError, 'EXACT_DRAFT_FRAGMENT_SET_REQUIRED'):
            c.compile_proposal(inputs, self.pins)


if __name__ == '__main__':
    unittest.main()

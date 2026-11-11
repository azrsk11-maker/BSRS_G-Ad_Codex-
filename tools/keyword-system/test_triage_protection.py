import hashlib
import unittest

from triage_protection import derive


def identity(text):
    return 'BSRE-N-'+hashlib.sha256(text.encode()).hexdigest()[:24]


def wb(*pairs):
    return {'queue': [{'normalized_text': text, 'disposition': disposition} for text, disposition in pairs]}


class TriageProtectionTests(unittest.TestCase):
    def test_other_review_hold_wins_protection_without_promoting_anything(self):
        source = [wb(('rent manager software', 'NEGATIVE_EXACT_REVIEW')),
                  wb(('rent manager software', 'HOLD'), ('warehouse for rent', 'POSITIVE_REVIEW'))]
        self.assertEqual(derive(source, [identity('rent manager software')], ['office for software company']),
                         ['office for software company', 'rent manager software', 'warehouse for rent'])

    def test_unadmitted_or_archived_negative_stays_protected(self):
        self.assertEqual(derive([wb(('job research', 'NEGATIVE_EXACT_REVIEW'),
            ('property agent recruitment', 'NEGATIVE_EXACT_REVIEW'))], [identity('job research')], []),
            ['property agent recruitment'])

    def test_unknown_or_duplicate_membership_and_unassessed_sources_fail_closed(self):
        source = [wb(('job research', 'NEGATIVE_EXACT_REVIEW'))]
        for ids in ([identity('missing')], [identity('job research')]*2, [True]):
            with self.assertRaises(ValueError): derive(source, ids, [])
        with self.assertRaises(ValueError):
            derive([wb(('job research', 'UNASSESSED'))], [identity('job research')], [])

    def test_invalid_normalization_and_in_source_duplicates_are_rejected(self):
        for source in ([wb(('Job research', 'HOLD'))],
                       [wb(('job research', 'HOLD'), ('job research', 'NEGATIVE_EXACT_REVIEW'))]):
            with self.assertRaises(ValueError): derive(source, [identity('job research')], [])

    def test_callers_do_not_share_mutable_results_or_case_variant_authored_input(self):
        source = [wb(('job research', 'NEGATIVE_EXACT_REVIEW'))]
        result = derive(source, [identity('job research')], ['Café property'])
        result.clear()
        self.assertEqual(derive(source, [identity('job research')], ['Café property']), ['café property'])
        with self.assertRaises(ValueError):
            derive(source, [identity('job research')], ['Café property', 'CAFÉ property'])


if __name__ == '__main__': unittest.main()

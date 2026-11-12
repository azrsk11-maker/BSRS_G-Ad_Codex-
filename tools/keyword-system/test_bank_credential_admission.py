"""Actual-source append-only research contracts; no advertising or live exports."""
from copy import deepcopy
from datetime import date, timedelta
import hashlib
import unittest
from unittest.mock import patch

import append_only_admission as stage
import bank_credential_admission as e
import current_negative_library as current


class BankCredentialAdmissionTests(unittest.TestCase):
    # A one-process integration runner may inject its own freshly reconstructed
    # base/results. These are never a serialized baseline or acceptance cache.
    FRESH_BASE = None
    FRESH_INPUTS = None

    @classmethod
    def setUpClass(cls):
        cls.when = date(2026, 11, 12)
        cls.base = cls.FRESH_BASE if cls.FRESH_BASE is not None else current.reconstruct_ofqual_veterinary_snapshot(
            e.first.ROOT, at=cls.when)
        cls.material = e.load_reviewed(e.first.ROOT, cls.when)
        cls.inputs = cls.FRESH_INPUTS if cls.FRESH_INPUTS is not None else e.extend(cls.base, e.first.ROOT, cls.when)

    def empty_base(self):
        return {key: [] for key in ('records', 'archived_records', 'protected_queries',
                                    'sources', 'campaigns', 'campaign_context')}

    def test_complete_history_bodies_order_extras_and_archives_are_preserved(self):
        self.assertEqual(stage.digest(self.base), e.BASE_SHA256)
        self.assertEqual(stage.recover_base(self.inputs, stage_key=e.STAGE_KEY), self.base)
        for field in ('records', 'protected_queries', 'sources'):
            self.assertEqual(self.inputs[field][:len(self.base[field])], self.base[field])
        for field in set(self.base) - {'records', 'protected_queries', 'sources'}:
            self.assertEqual(self.inputs[field], self.base[field])

    def test_original_full_cells_and_independent_review_provenance_are_bound(self):
        for record in self.inputs['records'][len(self.base['records']):]:
            key = record['normalized_text']
            row = self.material['groups'][key][0]
            saved = record['provenance_occurrences'][0]
            self.assertEqual({k: saved[k] for k in e.occurrence(row)}, e.occurrence(row))
            self.assertEqual(saved['original_text'], row['values']['Keyword'])
            self.assertEqual(saved['raw_source_sha256'], e.RAW_SHA256)
            self.assertEqual(record['original_text'], row['values']['Keyword'])
            self.assertEqual((record['match_type'], record['risk_level'], record['approval_state']),
                             ('EXACT', 'HIGH', 'PENDING'))
            self.assertEqual(record['eligible_campaigns'], ['BSRE-C0301'])
            self.assertEqual(record['deployed_resource_ids'], [])
            self.assertTrue(all(record[k] is None for k in ('volume', 'cpc', 'observed_query', 'observation_date')))
            self.assertIn(saved['independent_review_sha256'], e.SOURCE_PINS.values())

    def test_all_source_groups_and_preheld_cohort_receive_every_comparison(self):
        d = self.material['review']['fresh_variant_review']
        self.assertEqual(set(d['source_group_join_results']), set(self.material['source_groups']))
        self.assertEqual((d['external_key_comparisons'], d['within_source_key_comparisons']), (13924, 13924))
        self.assertEqual((d['cohort_external_key_comparisons'], d['cohort_within_source_key_comparisons']), (3212, 3212))
        for key in self.material['initial_holds']:
            self.assertEqual([r['method'] for r in d['source_group_join_results'][key]['joins']], list(e.METHODS))

    def test_semantic_compatibility_and_temporary_batch_holds_stay_protected(self):
        review = self.material['review']
        selected, held = set(review['selected_normalized_phrases']), set(review['held_groups'])
        self.assertEqual(selected | held, set(self.material['groups']))
        self.assertFalse(selected & held)
        self.assertTrue(set(self.material['initial_holds']) <= held)
        protected = {r['text'] for r in self.inputs['protected_queries']}
        self.assertTrue(held <= protected)
        self.assertEqual(len(self.material['strict_batch_holds']), 26)
        self.assertTrue(all('full NAVIGATION goal' in r['limit'] for r in self.material['strict_batch_holds'].values()))

    def test_noncohort_source_stays_unassessed_and_never_enters_new_master_rows(self):
        noncohort = set(self.material['source_groups']) - set(self.material['groups'])
        self.assertEqual(len(noncohort), 2678)
        new = {r['normalized_text'] for r in self.inputs['records'][len(self.base['records']):]}
        self.assertFalse(new & noncohort)
        d = self.material['review']['fresh_variant_review']['source_group_join_results']
        self.assertTrue(all(d[k]['semantic_state'] == 'UNASSESSED_NONCOHORT_NOT_ADMITTED' for k in noncohort))

    def test_preheld_external_token_bag_and_closed_aliases_are_not_omitted(self):
        key = next(iter(self.material['initial_holds']))
        base = self.empty_base()
        base['protected_queries'] = [{'query_id': 'SYNTHETIC-BAG', 'text': ' '.join(reversed(e.ka.tokens(key)))}]
        base['archived_records'] = [{'keyword_id': 'SYNTHETIC-CLOSED', 'original_text': e._closed(key)}]
        d = e.membership(base, self.material)
        joined = {row['method']: row['existing_identities'] for row in d['source_group_join_results'][key]['joins']}
        self.assertIn('protected_queries:SYNTHETIC-BAG', joined['equal_token_bag'])
        self.assertIn('archived_records:SYNTHETIC-CLOSED', joined['closed_alphanumeric'])
        base['records'] = [{'keyword_id': 'SYNTHETIC-CURRENT', 'original_text': key}]
        with self.assertRaisesRegex(ValueError, 'BANK_CREDENTIAL_NEW_HOLD_CONFLICTS_WITH_EXISTING_NEGATIVE'):
            e.membership(base, self.material)

    def test_source_peer_outside_selected_predicate_can_hold_a_candidate(self):
        key = next(k for k in self.material['review']['selected_normalized_phrases'] if ' ' in k)
        material = dict(self.material, source_groups=dict(self.material['source_groups']))
        outside = e._closed(key)
        self.assertNotIn(outside, material['source_groups'])
        material['source_groups'][outside] = [{'source_ordinal': 99999, 'values': {'Keyword': outside}}]
        d = e.membership(self.empty_base(), material)
        self.assertNotIn(key, d['selected_normalized_phrases'])
        self.assertTrue(any(99999 in r.get('outside_cohort_peer_ordinals', [])
                            for r in d['additional_variant_holds'][key]))

    def test_only_listed_provider_span_with_identical_remainder_causes_family_hold(self):
        texts = ['icici bank credit card password reset', 'icici credit card password reset',
                 'icici transaction password reset', 'icici login password reset',
                 'icici bank password reset without debit card', 'icici password reset using atm card']
        groups = {e.ka.normalize(t): [{'source_ordinal': i, 'values': {'Keyword': t}}]
                  for i, t in enumerate(texts, 1)}
        held, diagnostic = e.family_holds(groups)
        self.assertEqual(set(held), set(texts[:2]))
        self.assertTrue(all(r['broad_parent_membership_causes_hold'] is False for r in diagnostic))
        self.assertTrue(all('No proven identity' in r['limit'] for rs in held.values() for r in rs))

    def test_unlisted_identity_and_different_bank_name_are_not_repaired(self):
        texts = ['state bank of india password reset', 'bank of india password reset',
                 'my bank 2u password reset', 'maybank2u password reset']
        groups = {e.ka.normalize(t): [{'source_ordinal': i, 'values': {'Keyword': t}}]
                  for i, t in enumerate(texts, 1)}
        self.assertEqual(e.family_holds(groups)[0], {})

    def test_resealed_scope_dates_authority_and_selection_changes_fail(self):
        changes = [lambda r: r.update(campaign_key='SYNTHETIC-WRONG-SCOPE'),
                   lambda r: r.update(**{next(iter(e.LIMITS)): True}),
                   lambda r: r.update(valid_until=(self.when + timedelta(days=31)).isoformat()),
                   lambda r: r['selected_normalized_phrases'].append(next(iter(r['held_groups'])))]
        for change in changes:
            review = deepcopy(self.material['review']); change(review)
            review['subject_sha256'] = e.review_subject(review, self.material)
            with self.assertRaises(ValueError):
                e.validate_review(review, self.material, self.when)
        with self.assertRaises(ValueError):
            e.validate_review(self.material['review'], self.material, self.when + timedelta(days=31))

    def test_resealed_alias_unhold_fails_against_fresh_source_comparisons(self):
        review = deepcopy(self.material['review'])
        key = next(iter(review['fresh_variant_review']['additional_variant_holds']))
        review['selected_normalized_phrases'] = sorted(review['selected_normalized_phrases'] + [key])
        del review['held_groups'][key]
        review['fresh_variant_review']['selected_normalized_phrases'] = review['selected_normalized_phrases']
        review['fresh_variant_review']['all_held_normalized_phrases'].remove(key)
        review['subject_sha256'] = e.review_subject(review, self.material)
        material = dict(self.material, review=review)
        with patch.object(e, 'load_reviewed', return_value=material):
            with self.assertRaisesRegex(ValueError, 'BANK_CREDENTIAL_FRESH_VARIANT_REVIEW_CHANGED'):
                e.extend(self.base, e.first.ROOT, self.when)

    def test_changed_derived_body_and_unregistered_review_cannot_be_resealed(self):
        changed = deepcopy(self.inputs)
        changed['records'][-1]['volume'] = 0
        with self.assertRaisesRegex(ValueError, 'BANK_CREDENTIAL_DERIVED_BODIES_CHANGED'):
            e.check_saved(changed, e.first.ROOT, self.when)
        with patch.object(e, 'REVIEW_PIN', None):
            with self.assertRaisesRegex(ValueError, 'BANK_CREDENTIAL_REVIEW_UNREGISTERED'):
                e.load_reviewed(e.first.ROOT, self.when)

    def test_saved_generic_audit_does_not_promote_approvals_or_transfer_targets(self):
        report = e.check_saved(self.inputs, e.first.ROOT, self.when)
        self.assertTrue(report['passed'])
        self.assertFalse(report['deployment_export_allowed'])
        self.assertFalse(report['release_authorized'])
        self.assertEqual(report['prior_rows'], 11176)
        self.assertEqual(report['new_rows'], len(self.material['review']['selected_normalized_phrases']))

    def test_historical_and_latest_public_apis_keep_separate_fresh_chains(self):
        with patch.object(current, '_fresh_ofqual_veterinary_state', return_value=('old', 'old-report')) as old:
            self.assertEqual(current.reconstruct_ofqual_veterinary_snapshot(at=self.when), 'old')
            self.assertEqual(current.verify_ofqual_veterinary_snapshot(at=self.when), 'old-report')
            self.assertEqual(old.call_count, 2)
        with patch.object(current, '_fresh_bank_credential_state', return_value=('new', 'new-report')) as new:
            self.assertEqual(current.reconstruct(at=self.when), 'new')
            self.assertEqual(current.verify(at=self.when), 'new-report')
            self.assertEqual(new.call_count, 2)


if __name__ == '__main__':
    unittest.main()

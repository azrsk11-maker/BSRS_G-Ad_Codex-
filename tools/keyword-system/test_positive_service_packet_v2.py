"""Versioned held-intake checks; fixtures never grant business authority."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

import positive_service_packet_v2 as strict


def encoded(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf-8')


class PositiveServicePacketV2Tests(unittest.TestCase):
    def test_registered_packet_has_versioned_strict_but_no_business_authority(self):
        result = strict.verify_packet((strict.ROOT / strict.PACKET).read_bytes())
        self.assertEqual(result['schema'], 'bsre-positive-service-verification-v2')
        self.assertEqual(result['verification_version'], 2)
        self.assertEqual(result['status'], 'PASS_STRICT_V2_INTAKE_CONSISTENCY_ONLY')
        self.assertEqual((result['selected_canonical_seeds'], result['historical_occurrences']), (2, 4))
        self.assertEqual(result['reviewed_positive_contribution'], 0)
        for flag in ['business_evidence_accepted', 'master_admission_allowed',
                     'deployment_export_allowed', 'production_authorization']:
            self.assertIs(result[flag], False)

    def test_strict_entry_rejects_all_six_json_type_substitutions(self):
        base = strict.legacy.build_packet()
        mutations = [
            lambda v: v.update(production_authorization=0),
            lambda v: v.update(deployment_export_allowed=0),
            lambda v: v.update(evidence_intake_only=1),
            lambda v: v['counts'].update(reviewed_positive_contribution=False),
            lambda v: v['source'].update(canonical_candidates=41.0),
            lambda v: v['counts'].update(selected_canonical_seeds=2.0),
        ]
        for number, change in enumerate(mutations):
            with self.subTest(number=number):
                value = copy.deepcopy(base)
                change(value)
                with self.assertRaisesRegex(ValueError, 'differs'):
                    strict.verify_packet(encoded(value))

    def test_forged_binding_review_or_admission_is_rejected(self):
        base = strict.legacy.build_packet()
        mutations = [
            lambda v: v['rows'][0]['admission_reviews_required']['claims'].update(status='PASS'),
            lambda v: v['rows'][0]['binding_overlay_required'].update(primary_campaign_key='BSRE-C0001'),
            lambda v: v.update(deployment_export_allowed=True),
            lambda v: v['counts'].update(reviewed_positive_contribution=2),
        ]
        for change in mutations:
            value = copy.deepcopy(base); change(value)
            with self.assertRaisesRegex(ValueError, 'differs'):
                strict.verify_packet(encoded(value))

    def test_duplicate_json_keys_and_nonfinite_values_are_rejected(self):
        for raw in [b'{"schema":1,"schema":2}', b'{"value":NaN}']:
            with self.assertRaises(ValueError):
                strict.verify_packet(raw)

    def test_legacy_pin_drift_holds_before_template_builder(self):
        with mock.patch.object(strict, 'LEGACY_SHA256', '0' * 64), \
             mock.patch.object(strict.legacy, 'build_packet') as builder:
            with self.assertRaisesRegex(ValueError, 'LEGACY_DEPENDENCY_PIN_CHANGED'):
                strict.verify_packet(b'{}')
            builder.assert_not_called()

    def test_cli_reports_explicit_v2_and_false_authority(self):
        result = subprocess.run([sys.executable, '-B', str(Path(strict.__file__).resolve())],
                                capture_output=True, text=True, check=True)
        value = json.loads(result.stdout)
        self.assertEqual(value['verification_version'], 2)
        self.assertEqual(value['status'], 'PASS_STRICT_V2_INTAKE_CONSISTENCY_ONLY')
        self.assertIs(value['master_admission_allowed'], False)
        self.assertIs(value['production_authorization'], False)

    def test_legacy_receipt_is_historical_held_consistency_not_v2_proof(self):
        value = strict.legacy.build_packet()
        value['production_authorization'] = 0
        old = strict.legacy.verify_packet(encoded(value))
        self.assertEqual(old['status'], 'PASS_INTAKE_CONSISTENCY_ONLY')
        self.assertNotIn('verification_version', old)
        self.assertIs(old['master_admission_allowed'], False)
        with self.assertRaisesRegex(ValueError, 'differs'):
            strict.verify_packet(encoded(value))


if __name__ == '__main__':
    unittest.main()

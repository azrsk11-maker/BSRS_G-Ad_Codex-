"""Strict v2 held-workorder verification. No admission, writer or provider authority.

The byte-pinned historical reader stays unchanged for its historical dependants.
New default workorder intake must use this versioned verifier, not its legacy
Python-equality consistency receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

LEGACY_PATH = Path(__file__).with_name('positive_service_packet.py')
LEGACY_SHA256 = '5e69857f2e33e6a2686ad68ba430238bdac6bbe2d89bf6dd2340b9616cad36bd'


def verify_legacy_pin():
    if hashlib.sha256(LEGACY_PATH.read_bytes()).hexdigest() != LEGACY_SHA256:
        raise ValueError('STRICT_V2_LEGACY_DEPENDENCY_PIN_CHANGED')


verify_legacy_pin()  # Before importing the historical dependency.
import positive_service_packet as legacy

if Path(legacy.__file__).resolve() != LEGACY_PATH.resolve():
    raise ValueError('STRICT_V2_LEGACY_IMPORT_LOCATION_CHANGED')
ROOT = legacy.ROOT
PACKET = legacy.PACKET


def verify_packet(content, root=ROOT):
    verify_legacy_pin()
    expected = legacy.build_packet(root)
    actual = legacy.keyword_audit.parse_json_bytes(content)
    # Preserve JSON types while ignoring irrelevant object-key order/spacing.
    if legacy.canonical_sha256(actual) != legacy.canonical_sha256(expected):
        raise ValueError('Strict v2 workorder differs from freshly reconstructed held source')
    verify_legacy_pin()
    return {'schema': 'bsre-positive-service-verification-v2',
            'verification_version': 2, 'status': 'PASS_STRICT_V2_INTAKE_CONSISTENCY_ONLY',
            **expected['counts'], 'business_evidence_accepted': False,
            'master_admission_allowed': False, 'deployment_export_allowed': False,
            'production_authorization': False,
            'packet_canonical_sha256': legacy.canonical_sha256(actual),
            'legacy_reader_sha256': LEGACY_SHA256}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', type=Path, default=ROOT / PACKET)
    args = parser.parse_args()
    print(json.dumps(verify_packet(args.verify.read_bytes()), sort_keys=True))


if __name__ == '__main__':
    main()

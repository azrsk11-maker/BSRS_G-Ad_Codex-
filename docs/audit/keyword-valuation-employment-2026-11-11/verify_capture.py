"""Pinned genuine Planner projection; optional private raw equality, no admission."""
import argparse
import json
from pathlib import Path
import sys
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools/keyword-system"))
from supplemental_discovery import verify_capture
PINS = {'valuation-employment.json': '7be9d5d16a1413cf738b49e8bb92adcdb75e4c02b86bd7e61c940640d7f9371b', 'capture.json': '9408a2be59c1858152c770d82e833e18a87a6e89b25e927284ad93ef27ecfb76'}


def verify(source=None):
    sources = {"valuation-employment": source} if source is not None else None
    return verify_capture(HERE, PINS, sources)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, metavar="PRIVATE_PATH")
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.source), sort_keys=True))
    except Exception:
        print(json.dumps({"passed": False, "scope": "CAPTURE_VERIFICATION_FAILED", "deployment_authorized": False}))
        raise SystemExit(1)

"""Pinned official qualification intake; optional private raw equality, no admission."""
import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools/keyword-system"))
from ofqual_discovery import verify_capture

PINS = {
    "qualifications.json": "2869cab8a06a76fa113ef430b28d09c53a324b72555cd0b3b36d3bdf82de4ccc",
    "capture.json": "40563540ed29d76e03e2bea8be1a46aca960d888c138fcc2f9ac2f54dec2e9f7",
}


def verify(source=None):
    return verify_capture(HERE, PINS, source)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, metavar="PRIVATE_PATH")
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.source), sort_keys=True))
    except Exception:
        print(json.dumps({"passed": False, "scope": "CAPTURE_VERIFICATION_FAILED",
                          "deployment_authorized": False}))
        raise SystemExit(1)

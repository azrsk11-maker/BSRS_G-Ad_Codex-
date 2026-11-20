"""Pinned keywords-only clipboard intake; no admission or platform writer."""
import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from capture_tools import MAX_BYTES, validate_bundle

PINS = {'keywords.json': 'a3d8882f5edc61e40c482772723596caaf050a0d7a792e5fe4991be64b14e74f', 'capture.json': '929321ac43e8a7acf9511c5d974b124d6a1448099860873929099991556aeabc', 'review.json': 'dad9ca570b860ce3a0061eff2269d0a8d9c5cf026c20d83ff5eabff284bc5179', 'lexical.json': 'e12dc3149d9ba8d8543d8ce4505899aa0f19f4a7ef5a99382afd6fd7097de597'}


def read_bounded(path):
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("FILE_BOUNDS")
    return raw


def verify(source=None):
    blobs = {name: read_bounded(HERE / name) for name in PINS}
    raw = read_bounded(Path(source)) if source is not None else None
    return validate_bundle(blobs, PINS, raw)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, metavar="PRIVATE_PATH")
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.source), sort_keys=True))
    except Exception:
        print(json.dumps({"passed": False, "scope": "CLIPBOARD_CAPTURE_VERIFICATION_FAILED", "deployment_authorized": False}))
        raise SystemExit(1)

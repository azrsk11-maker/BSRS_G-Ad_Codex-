"""Read-only, byte-bounded JSON inspection; structure by default, values by choice.

Example: inspect_json.py capture.json --select source_projection.record_count
Dotted selectors support exact object keys and nonnegative array indexes. Keys
containing dots cannot be selected. No wildcard, recursive search or writer exists.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

DEFAULT_INPUT_BYTES = 4 * 1024 * 1024
MAX_INPUT_BYTES = 32 * 1024 * 1024
DEFAULT_OUTPUT_BYTES = 4000
MAX_OUTPUT_BYTES = 16000


class InspectionError(ValueError):
    """Public messages are fixed codes, never file content or paths."""


def _bound(value, maximum):
    if type(value) is not int or not 1 <= value <= maximum:
        raise InspectionError("INVALID_BOUND")
    return value


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InspectionError("INVALID_JSON")
        result[key] = value
    return result


def _constant(_value):
    raise InspectionError("INVALID_JSON")


def _float(value):
    number = float(value)
    if not math.isfinite(number):
        raise InspectionError("INVALID_JSON")
    return number


def read_json(path, max_input_bytes=DEFAULT_INPUT_BYTES):
    """Read at most limit+1 bytes, including when a file grows during the read."""
    limit = _bound(max_input_bytes, MAX_INPUT_BYTES)
    try:
        with Path(path).open("rb") as source:
            content = source.read(limit + 1)
        if len(content) > limit:
            raise InspectionError("INPUT_LIMIT_EXCEEDED")
        return json.loads(content.decode("utf-8-sig"), object_pairs_hook=_object,
                          parse_constant=_constant, parse_float=_float)
    except InspectionError:
        raise
    except OSError:
        raise InspectionError("INPUT_UNAVAILABLE") from None
    except (ValueError, UnicodeError, RecursionError):
        raise InspectionError("INVALID_JSON") from None


def _shape(value):
    if isinstance(value, dict):
        return {"type": "object", "items": len(value)}
    if isinstance(value, list):
        return {"type": "array", "items": len(value)}
    if isinstance(value, str):
        return {"type": "string", "characters": len(value)}
    return {"type": "null" if value is None else
            "boolean" if isinstance(value, bool) else "number"}


def _select(value, selector):
    if not isinstance(selector, str) or not 1 <= len(selector) <= 256:
        raise InspectionError("INVALID_SELECTOR")
    parts = selector.split(".")
    if any(not part for part in parts):
        raise InspectionError("INVALID_SELECTOR")
    for part in parts:
        if isinstance(value, dict) and part in value:
            value = value[part]
        elif (isinstance(value, list) and part.isascii() and part.isdecimal()
              and (part == "0" or not part.startswith("0")) and int(part) < len(value)):
            value = value[int(part)]
        else:
            raise InspectionError("SELECTOR_NOT_FOUND")
    return value


def inspect(value, selectors=(), max_output_bytes=DEFAULT_OUTPUT_BYTES):
    """Return a complete UTF-8 JSON line or fail; never truncate a value."""
    limit = _bound(max_output_bytes, MAX_OUTPUT_BYTES)
    if not isinstance(selectors, (tuple, list)) or len(selectors) > 32:
        raise InspectionError("INVALID_SELECTOR")
    if any(not isinstance(s, str) for s in selectors) or len(set(selectors)) != len(selectors):
        raise InspectionError("INVALID_SELECTOR")
    if selectors:
        result = {"mode": "selected", "fields": {s: _select(value, s) for s in selectors}}
    else:
        shape = _shape(value)
        if isinstance(value, dict):
            shape["fields"] = {key: _shape(child) for key, child in value.items()}
        result = {"mode": "structure", "root": shape}
    try:
        line = (json.dumps(result, ensure_ascii=False, allow_nan=False,
                           separators=(",", ":")) + "\n").encode("utf-8")
    except (ValueError, UnicodeError, RecursionError, TypeError):
        raise InspectionError("INVALID_JSON") from None
    if len(line) > limit:
        raise InspectionError("OUTPUT_LIMIT_EXCEEDED")
    return line


class SafeParser(argparse.ArgumentParser):
    def error(self, _message):
        raise InspectionError("INVALID_ARGUMENTS")


def main(argv=None, stdout=None, stderr=None):
    output, errors = stdout or sys.stdout.buffer, stderr or sys.stderr
    try:
        parser = SafeParser(description=__doc__)
        parser.add_argument("file", type=Path)
        parser.add_argument("--select", action="append", default=[], metavar="DOTTED.PATH",
                            help="Exact field/index; repeat up to 32 times. Default shows structure only.")
        parser.add_argument("--max-input-bytes", type=int, default=DEFAULT_INPUT_BYTES,
                            help=f"Read bound; default {DEFAULT_INPUT_BYTES}, maximum {MAX_INPUT_BYTES}.")
        parser.add_argument("--max-output-bytes", type=int, default=DEFAULT_OUTPUT_BYTES,
                            help=f"Whole UTF-8 JSON-line bound; default {DEFAULT_OUTPUT_BYTES}, maximum {MAX_OUTPUT_BYTES}.")
        args = parser.parse_args(argv)
        value = read_json(args.file, args.max_input_bytes)
        output.write(inspect(value, args.select, args.max_output_bytes))
        return 0
    except InspectionError as failure:
        errors.write(f"inspect_json: {failure}\n")
        return 2
    except (OSError, ValueError, UnicodeError, RecursionError):
        errors.write("inspect_json: INSPECTION_FAILED\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

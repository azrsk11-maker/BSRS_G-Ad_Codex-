"""Reuse a freshly verified bank fixture within a paired keyword worker."""

from contextlib import contextmanager
from copy import deepcopy
from datetime import date
from hashlib import sha256
from pathlib import Path
import sys
from types import ModuleType
import unittest


CANONICAL_FOLDER = Path(__file__).resolve().parents[1] / "keyword-system"
BANK_MODULE = "test_bank_channel_login_admission"
FRONT_MODULE = "test_front_office_document_admission"
BANK_CLASS = "BankChannelLoginAdmissionTests"
FRONT_CLASS = "FrontOfficeDocumentAdmissionTests"
BANK_SAVED_CASE_ID = f"{BANK_MODULE}.{BANK_CLASS}.test_saved_outputs_do_not_grant_approval_or_transfer_targets"
CURRENT = "current_negative_library"
APPEND_ONLY = "append_only_admission"
BANK_STAGE = "bank_channel_login_admission"
FRONT_STAGE = "front_office_document_admission"
BANK_BASE_SHA256 = "ea897a269a001239ab9d2ef1a75f9640909c1a55f66c6c8e5e40ec98623c3765"
FRONT_BASE_SHA256 = "a93d5aa368975f79d3fd5bd92223ccfe93d8b48d725ac8c301013aba8d3868cb"
# The measured setUpClass hooks, saved-output test, and replaced history caller.
SOURCE_PINS = {
    BANK_MODULE: "90093edaf151961dcd19cbcfe33abd457945ee3f8f243dda873b2ec2933b74f6",
    FRONT_MODULE: "7e8f5cc2cfaf3ece17ff785b3acf2e6a7f6c3f9847ac6b28bdda6ae2b6e8959c",
    CURRENT: "77122074aae8dbd050e4e00d4f659870aff107449461ade9e5edfa7fdfc94795",
}


def pair_sources_match(folder):
    """Check the measured source bytes in this checkout before pairing modules."""
    try:
        if Path(folder).resolve(strict=True) != CANONICAL_FOLDER:
            return False
        for name, expected in SOURCE_PINS.items():
            path = CANONICAL_FOLDER / f"{name}.py"
            if path.resolve(strict=True) != path or sha256(path.read_bytes()).hexdigest() != expected:
                return False
    except (OSError, RuntimeError):
        return False
    return True


def _detached_history(folder, front_expected):
    if not pair_sources_match(folder):
        return None

    loaded = {}
    for name in (*SOURCE_PINS, APPEND_ONLY, BANK_STAGE, FRONT_STAGE):
        module = sys.modules.get(name)
        if not isinstance(module, ModuleType):
            return None
        path = getattr(module, "__file__", None)
        if not path or Path(path).resolve(strict=True) != CANONICAL_FOLDER / f"{name}.py":
            return None
        loaded[name] = module

    bank_test, front_test = loaded[BANK_MODULE], loaded[FRONT_MODULE]
    stage = loaded[APPEND_ONLY]
    for test, definition in ((bank_test, BANK_STAGE), (front_test, FRONT_STAGE)):
        if (getattr(test, "e", None) is not loaded[definition]
                or getattr(test, "stage", None) is not stage
                or getattr(test, "current", None) is not loaded[CURRENT]):
            return None

    bank = getattr(bank_test, BANK_CLASS, None)
    front = getattr(front_test, FRONT_CLASS, None)
    for test_class, module_name, class_name in ((bank, BANK_MODULE, BANK_CLASS),
                                                (front, FRONT_MODULE, FRONT_CLASS)):
        if (not isinstance(test_class, type) or not issubclass(test_class, unittest.TestCase)
                or test_class.__module__ != module_name or test_class.__qualname__ != class_name
                or getattr(test_class, "FRESH_BASE", False) is not None
                or getattr(test_class, "FRESH_INPUTS", False) is not None):
            return None

    front_names = unittest.TestLoader().getTestCaseNames(front)
    front_ids = [f"{FRONT_MODULE}.{FRONT_CLASS}.{name}" for name in front_names]
    if front_ids != list(front_expected):
        return None

    base, inputs = vars(bank).get("base"), vars(bank).get("inputs")
    if (vars(bank).get("when") != date(2026, 11, 13)
            or type(base) is not dict or type(inputs) is not dict
            or getattr(loaded[BANK_STAGE], "BASE_SHA256", None) != BANK_BASE_SHA256
            or getattr(loaded[FRONT_STAGE], "BASE_SHA256", None) != FRONT_BASE_SHA256
            or stage.digest(base) != BANK_BASE_SHA256 or stage.digest(inputs) != FRONT_BASE_SHA256):
        return None
    return front, deepcopy(inputs)


@contextmanager
def reuse_bank_history(folder, bank_verified, front_expected):
    """Supply a detached base after the caller verified every bank outcome."""
    history = None
    if bank_verified is True:
        try:
            history = _detached_history(folder, front_expected)
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
            # The ordinary front setup remains available after missing or changed inputs.
            pass

    if history is None:
        yield False
        return

    front, base = history
    front.FRESH_BASE = base
    try:
        yield True
    finally:
        front.FRESH_BASE = None

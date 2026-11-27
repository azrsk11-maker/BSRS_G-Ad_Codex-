"""Guard the fresh composition's source, ordering and saved-document checks."""

from datetime import date
import hashlib
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, call, patch


with patch.object(sys, "path", [str(Path(__file__).resolve().parents[1] / "keyword-system"), *sys.path]):
    import current_negative_composition as composition


class NegativeCompositionTests(unittest.TestCase):
    when = date(2026, 11, 28)

    def test_binding_rejects_byte_drift_and_a_missing_source(self):
        body = b"check = True\n"
        signature = hashlib.sha256(b"phase\0" + hashlib.sha256(body).digest()).hexdigest()
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary).resolve()
            path = folder / "phase.py"
            path.write_bytes(body)
            with patch.object(composition, "SOURCE_MODULES", ("phase",)), \
                    patch.object(composition, "SOURCE_SHA256", signature):
                self.assertTrue(composition.reviewed_sources_match(folder))
                path.write_bytes(b"check = False\n")
                self.assertFalse(composition.reviewed_sources_match(folder))
                path.unlink()
                self.assertFalse(composition.reviewed_sources_match(folder))

    def test_source_mismatch_uses_the_reference_verifier(self):
        with patch.object(composition, "reviewed_sources_match", return_value=False), \
                patch.object(composition.reference, "verify", return_value={"reference": True}) as verify:
            self.assertEqual(composition.verify(at=self.when), {"reference": True})
            verify.assert_called_once_with(composition.first.ROOT, self.when)

    def test_each_stage_is_built_once_and_checked_before_handoff(self):
        order = Mock()
        original = object()
        middle = object()
        final = object()
        first_docs = {"index.json": {"version": 1}}
        final_docs = {"library-report.json": {"as_of": "2026-11-13", "rows": 14000}}
        one = SimpleNamespace(build_outputs=order.one, FOLDER="first", OUTPUT_PINS={"index.json": "one"})
        two = SimpleNamespace(build_outputs=order.two, FOLDER="second", OUTPUT_PINS={"library-report.json": "two"})
        order.one.return_value = middle, first_docs
        order.two.return_value = final, final_docs
        root = composition.first.ROOT
        with patch.object(composition, "STAGES", ("one", "two")), \
                patch.object(composition, "reviewed_sources_match", return_value=True), \
                patch.object(composition.reference, "reconstruct_valuation_snapshot", return_value=original) as base, \
                patch.object(composition.importlib, "import_module", side_effect=[one, two]), \
                patch.object(composition.append, "check_documents", order.check):
            self.assertEqual(composition.verify(at=self.when), {"as_of": "2026-11-28", "rows": 14000})
            base.assert_called_once_with(root, at=self.when)
        self.assertEqual(order.mock_calls, [
            call.one(original, root, self.when),
            call.check(root, one.FOLDER, one.OUTPUT_PINS, first_docs),
            call.two(middle, root, self.when),
            call.check(root, two.FOLDER, two.OUTPUT_PINS, final_docs),
        ])
        self.assertEqual(final_docs["library-report.json"]["as_of"], "2026-11-13")

    def test_a_failed_saved_document_check_stops_the_chain(self):
        stage = SimpleNamespace(build_outputs=Mock(return_value=({}, {})), FOLDER="held", OUTPUT_PINS={})
        with patch.object(composition, "STAGES", ("held", "later")), \
                patch.object(composition, "reviewed_sources_match", return_value=True), \
                patch.object(composition.reference, "reconstruct_valuation_snapshot", return_value={}), \
                patch.object(composition.importlib, "import_module", return_value=stage) as load, \
                patch.object(composition.append, "check_documents", side_effect=ValueError("APPEND_ONLY_SAVED_OUTPUT_CHANGED")):
            with self.assertRaisesRegex(ValueError, "APPEND_ONLY_SAVED_OUTPUT_CHANGED"):
                composition.verify(at=self.when)
            load.assert_called_once_with("held")

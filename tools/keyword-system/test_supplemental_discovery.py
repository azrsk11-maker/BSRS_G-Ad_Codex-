"""Synthetic supplemental capture provenance, privacy and overlap checks."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from planner_discovery import parse_discovery
from test_planner_discovery import PRIVATE_SENTINEL, fixture, fixture_row
import supplemental_discovery as sd


class SupplementalDiscoveryTests(unittest.TestCase):
    def test_proposal_assembly_roundtrip_preserves_private_projection_and_inputs(self):
        before = copy.deepcopy(self.batches)
        files = sd.assemble_capture(self.batches, capture_date_dubai="2026-11-11")
        pins = {name: hashlib.sha256(blob).hexdigest() for name, blob in files.items()}
        target = self.folder / "assembled"
        target.mkdir()
        for name, blob in files.items():
            self.assertIsInstance(blob, bytes)
            self.assertNotIn(PRIVATE_SENTINEL.encode(), blob)
            (target / name).write_bytes(blob)
        result = sd.verify_capture(target, pins, self.raw_sources)
        self.assertEqual(result["scope"], "PRIVATE_RAW_EQUIVALENCE")
        self.assertEqual((result["export_rows"], result["distinct_phrases"]), (4, 3))
        self.assertEqual(self.batches, before)
        self.assertEqual(json.loads(files["capture.json"])["master_contribution"], sd.MASTER)
        self.assertFalse(result["deployment_authorized"])

    def test_project_requires_independent_ui_count_account_and_exact_raw_hash(self):
        path = self.folder / "synthetic-count-discrepancy.csv"
        path.write_bytes(fixture([fixture_row("synthetic phrase " + str(i)) for i in range(166)]))
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        seeds = ["synthetic phrase 0"]
        context = dict(sd.CONTEXT, ui_idea_count=166)
        args = dict(topic="synthetic", batch_id="TEST_ONLY_COUNT", input_seeds=seeds,
                    ui_context=context, expected_source_sha256=digest)
        result = sd.project_discovery(path, **args)
        self.assertEqual(result["seed_reconciliation"]["exact_returned"], 1)
        for changed in ({"ui_context": dict(context, ui_idea_count=169)},
                        {"ui_context": dict(context, account_id="000-000-0000")},
                        {"expected_source_sha256": "0" * 64}):
            with self.subTest(changed=list(changed)), self.assertRaises(ValueError):
                sd.project_discovery(path, **dict(args, **changed))
        seeds.append("changed input")
        context["ui_idea_count"] = 169
        self.assertEqual(result["input_seeds"], ["synthetic phrase 0"])
        self.assertEqual(result["ui_context"]["ui_idea_count"], 166)
        self.assertNotIn(PRIVATE_SENTINEL, json.dumps(result))

    def test_assembly_rejects_collisions_authority_and_invalid_identity(self):
        for mutate in (lambda b: b[1].update(batch_id=b[0]["batch_id"]),
                       lambda b: b[1].update(topic=b[0]["topic"]),
                       lambda b: b[0].update(topic="../outside"),
                       lambda b: b[0]["controls"].update(approved=True)):
            batch = copy.deepcopy(self.batches)
            mutate(batch)
            with self.assertRaises(ValueError):
                sd.assemble_capture(batch, capture_date_dubai="2026-11-11")
        with self.assertRaises(ValueError):
            sd.assemble_capture(self.batches, capture_date_dubai="2026-02-30")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.raw_sources = {}
        self.batches = []
        for topic, words in (("sellers", ["synthetic shared", "synthetic seller"]),
                             ("landlords", ["SYNTHETIC shared", "synthetic landlord"])):
            self.batches.append(self.batch(topic, words))
        self.save()

    def batch(self, topic, words, rows=None):
        path = self.folder / (topic + ".csv")
        path.write_bytes(fixture([fixture_row(w) for w in words] if rows is None else rows))
        data = parse_discovery(path)
        # Real Planner filenames contain spaces; retain the original basename.
        data["source_basename"] = "Keyword Stats TEST_ONLY " + topic + ".csv"
        self.raw_sources[topic] = path
        seeds = ["synthetic shared"] + ["synthetic seed " + str(i) for i in range(9)]
        returned = {sd.normalize(r["values"]["Keyword"]) for r in data["records"]}
        missing = [{"seed": s, "grouped_under": None} for s in seeds if sd.normalize(s) not in returned]
        return {"version": 1, "scope": "AUTHENTIC_PLANNER_DISCOVERY_UNREVIEWED",
                "batch_id": "TEST_ONLY_" + topic, "topic": topic, "input_seeds": seeds,
                "ui_context": dict(sd.CONTEXT, ui_idea_count=len(data["records"])),
                "source_projection": data, "seed_reconciliation": {"exact_returned": 10 - len(missing),
                "without_separate_exact_row": missing}, "controls": dict(sd.CONTROLS)}

    def save(self):
        self.pins = {}
        items = []
        keys, batch_presence = sd.Counter(), sd.Counter()
        for batch in self.batches:
            filename = batch["topic"] + ".json"
            blob = (json.dumps(batch, ensure_ascii=False, indent=2) + "\n").encode()
            (self.folder / filename).write_bytes(blob)
            self.pins[filename] = hashlib.sha256(blob).hexdigest()
            data = batch["source_projection"]
            local = [sd.normalize(r["values"]["Keyword"]) for r in data["records"]]
            keys.update(local)
            batch_presence.update(set(local))
            items.append({"file": filename, "batch_id": batch["batch_id"],
                "sha256": self.pins[filename], "bytes": len(blob), "records": data["record_count"],
                "distinct_normalized": data["distinct_normalized_count"],
                "source_bytes": data["source_bytes"], "source_sha256": data["source_sha256"]})
        total = sum(keys.values())
        self.index = {"version": 1, "scope": "AUTHENTIC_UNREVIEWED_DISCOVERY_ONLY",
            "account_id": "573-038-4686", "capture_date_dubai": "2026-11-08",
            "source_files": items, "totals": {"export_rows": total, "distinct_normalized_phrases": len(keys),
            "repeated_occurrences": total - len(keys),
            "duplicate_phrase_groups": sum(v > 1 for v in keys.values()),
            "cross_batch_overlap_groups": sum(v > 1 for v in batch_presence.values())}, "master_contribution": dict(sd.MASTER)}
        self.save_index()

    def save_index(self):
        blob = (json.dumps(self.index, indent=2) + "\n").encode()
        (self.folder / "capture.json").write_bytes(blob)
        self.pins["capture.json"] = hashlib.sha256(blob).hexdigest()

    def test_public_partial_and_complete_raw_equivalence_are_distinct(self):
        original = {p.name: p.read_bytes() for p in self.folder.iterdir()}
        public = sd.verify_capture(self.folder, self.pins)
        self.assertEqual(public["scope"], "PUBLIC_CONSISTENCY_ONLY")
        self.assertEqual((public["export_rows"], public["distinct_phrases"]), (4, 3))
        partial = sd.verify_capture(self.folder, self.pins, {"sellers": self.raw_sources["sellers"]})
        self.assertEqual(partial["scope"], "PARTIAL_PRIVATE_RAW_EQUIVALENCE")
        self.assertEqual(partial["raw_batches_verified"], ["sellers"])
        complete = sd.verify_capture(self.folder, self.pins, self.raw_sources)
        self.assertEqual(complete["scope"], "PRIVATE_RAW_EQUIVALENCE")
        self.assertFalse(complete["deployment_authorized"])
        self.assertEqual({p.name: p.read_bytes() for p in self.folder.iterdir()}, original)
        self.assertNotIn(str(self.folder), json.dumps(complete))

    def test_short_real_batch_shapes_preserve_exact_seed_reconciliation(self):
        for count in (1, 3, 4, 7, 10):
            with self.subTest(count=count):
                batch = copy.deepcopy(self.batches[0])
                batch["input_seeds"] = batch["input_seeds"][:count]
                missing = [{"seed": s, "grouped_under": None}
                           for s in batch["input_seeds"] if s != "synthetic shared"]
                batch["seed_reconciliation"] = {"exact_returned": 1,
                                                "without_separate_exact_row": missing}
                self.assertEqual(sum(sd._batch(batch).values()), 2)
                batch["seed_reconciliation"]["exact_returned"] = True
                with self.assertRaisesRegex(ValueError, "SEED_RECONCILIATION"):
                    sd._batch(batch)

    def test_empty_oversized_and_normalized_duplicate_seed_lists_are_refused(self):
        for seeds in ([], ["synthetic seed " + str(i) for i in range(11)],
                      ["synthetic shared", "SYNTHETIC shared"], [" "]):
            with self.subTest(count=len(seeds)):
                batch = copy.deepcopy(self.batches[0])
                batch["input_seeds"] = seeds
                with self.assertRaises(ValueError):
                    sd._batch(batch)

    def test_tampered_pin_manifest_binding_or_extra_file_fails(self):
        path = self.folder / "sellers.json"
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "CAPTURE_BYTES_CHANGED"):
            sd.verify_capture(self.folder, self.pins)
        self.save()
        self.index["source_files"][0]["records"] += 1
        self.save_index()
        with self.assertRaisesRegex(ValueError, "INDEX_BINDING"):
            sd.verify_capture(self.folder, self.pins)
        self.save()
        self.pins["../outside.json"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "PINS"):
            sd.verify_capture(self.folder, self.pins)

    def test_privacy_context_authority_and_duplicate_identity_fail_when_repinned(self):
        original = copy.deepcopy(self.batches)
        mutations = [
            lambda: self.batches[0]["source_projection"]["records"][0]["values"].update({"In account?": "TEST_ONLY_PRIVATE"}),
            lambda: self.batches[0]["ui_context"].update({"account_id": "000-000-0000"}),
            lambda: self.batches[0]["ui_context"].update({"exclude_adult_ideas": 1}),
            lambda: self.batches[0]["controls"].update({"approved": 0}),
            lambda: self.batches[1].update({"batch_id": self.batches[0]["batch_id"]}),
            lambda: self.batches[0]["input_seeds"].__setitem__(1, self.batches[0]["input_seeds"][0]),
            lambda: self.batches[0]["seed_reconciliation"]["without_separate_exact_row"][0].update({"grouped_under": "invented"}),
        ]
        for change in mutations:
            self.batches = copy.deepcopy(original)
            change(); self.save()
            with self.subTest(change=change), self.assertRaises(ValueError):
                sd.verify_capture(self.folder, self.pins)

    def test_raw_mismatch_unknown_topic_and_duplicate_manifest_fail(self):
        self.raw_sources["sellers"].write_bytes(fixture([fixture_row("different synthetic query")]))
        with self.assertRaisesRegex(ValueError, "PRIVATE_RAW_PROJECTION_MISMATCH"):
            sd.verify_capture(self.folder, self.pins, self.raw_sources)
        with self.assertRaisesRegex(ValueError, "UNKNOWN_PRIVATE_TOPIC"):
            sd.verify_capture(self.folder, self.pins, {"unknown": self.raw_sources["sellers"]})
        self.index["source_files"].append(copy.deepcopy(self.index["source_files"][0]))
        self.save_index()
        with self.assertRaisesRegex(ValueError, "SOURCE_FILE_IDENTITY"):
            sd.verify_capture(self.folder, self.pins)

    def test_union_totals_and_complete_pin_membership_are_required(self):
        self.index["totals"]["distinct_normalized_phrases"] += 1
        self.save_index()
        with self.assertRaisesRegex(ValueError, "UNION_COUNTS"):
            sd.verify_capture(self.folder, self.pins)
        self.save()
        extra = b"{}"
        (self.folder / "extra.json").write_bytes(extra)
        self.pins["extra.json"] = hashlib.sha256(extra).hexdigest()
        with self.assertRaisesRegex(ValueError, "UNDECLARED_PINNED_FILE"):
            sd.verify_capture(self.folder, self.pins)

    def test_single_batch_duplicates_are_not_cross_batch_overlap(self):
        self.batches = [self.batch("sellers", ["synthetic shared", "SYNTHETIC shared"])]
        self.save()
        self.assertEqual(self.index["totals"], {"export_rows": 2,
            "distinct_normalized_phrases": 1, "repeated_occurrences": 1,
            "duplicate_phrase_groups": 1, "cross_batch_overlap_groups": 0})
        self.assertTrue(sd.verify_capture(self.folder, self.pins)["passed"])
        self.index["totals"]["cross_batch_overlap_groups"] = 1
        self.save_index()
        with self.assertRaisesRegex(ValueError, "UNION_COUNTS"):
            sd.verify_capture(self.folder, self.pins)

    def test_cross_batch_overlap_counts_distinct_batches_not_duplicate_rows(self):
        self.batches[0] = self.batch("sellers", ["synthetic shared", "SYNTHETIC shared"])
        self.save()
        self.assertEqual(self.index["totals"], {"export_rows": 4,
            "distinct_normalized_phrases": 2, "repeated_occurrences": 2,
            "duplicate_phrase_groups": 1, "cross_batch_overlap_groups": 1})
        self.assertTrue(sd.verify_capture(self.folder, self.pins)["passed"])
        self.index["totals"]["cross_batch_overlap_groups"] = 2
        self.save_index()
        with self.assertRaisesRegex(ValueError, "UNION_COUNTS"):
            sd.verify_capture(self.folder, self.pins)

    def test_duplicate_phrases_and_physical_line_gaps_match_parser(self):
        row = fixture_row("synthetic shared")
        row[2] = "synthetic\nmetric"
        self.batches[0] = self.batch("sellers", [], [row, fixture_row("SYNTHETIC shared")])
        self.save()
        data = self.batches[0]["source_projection"]
        self.assertEqual([r["source_line"] for r in data["records"]], [4, 6])
        self.assertEqual(sd.verify_capture(self.folder, self.pins, self.raw_sources)["distinct_phrases"], 2)
        report = sd.overlap_report([self.batches[0]], [self.batches[1]])
        shared = next(r for r in report["phrases"] if r["normalized_text"] == "synthetic shared")
        self.assertEqual([r["source_line"] for r in shared["original_refs"]], [4, 6])
        self.assertEqual(len(shared["supplemental_refs"]), 1)
        self.assertEqual(report["counts"]["combined_occurrences"], 4)
        data["duplicate_groups"][0]["source_lines"] = [4, 5]
        self.save()
        with self.assertRaisesRegex(ValueError, "COUNTS_OR_DUPLICATES"):
            sd.verify_capture(self.folder, self.pins)

    def test_overlap_retains_every_form_and_reference_without_mutation(self):
        original = [copy.deepcopy(self.batches[0])]
        supplemental = [copy.deepcopy(self.batches[1])]
        before = copy.deepcopy((original, supplemental))
        report = sd.overlap_report(original, supplemental)
        self.assertEqual(report["counts"], {"original_unique": 2, "supplemental_unique": 2,
            "overlap_unique": 1, "original_only_unique": 1, "supplemental_only_unique": 1,
            "combined_unique": 3, "original_occurrences": 2, "supplemental_occurrences": 2,
            "combined_occurrences": 4, "repeated_occurrences": 1})
        shared = next(r for r in report["phrases"] if r["normalized_text"] == "synthetic shared")
        self.assertEqual(shared["original_forms"], ["synthetic shared", "SYNTHETIC shared"])
        self.assertEqual(shared["original_refs"][0]["source_line"], 4)
        self.assertEqual(shared["supplemental_refs"][0]["batch_id"], "TEST_ONLY_landlords")
        self.assertFalse(report["classification_inherited"])
        self.assertNotIn("Avg. monthly searches", json.dumps(report))
        self.assertEqual((original, supplemental), before)
        with self.assertRaisesRegex(ValueError, "DUPLICATE_BATCH_ID"):
            sd.overlap_report(original, original)
        with self.assertRaises(ValueError):
            sd.overlap_report([], supplemental)
        broken = copy.deepcopy(supplemental)
        broken[0]["source_projection"]["records"][0]["source_line"] = True
        with self.assertRaisesRegex(ValueError, "SOURCE_LINE"):
            sd.overlap_report(original, broken)


if __name__ == "__main__":
    unittest.main()

"""Optional equal-work join benchmark; never admission or acceptance caching."""
from collections import defaultdict
import json
import statistics
import time

import buyer_source_reconciliation as buyer


def measure(samples=3):
    if type(samples) is not int or not 1 <= samples <= 3:
        raise ValueError("One to three samples only")
    report = buyer.build_report()
    external = [(r["reference"], buyer.attention_keys(r["original_literal"]))
                for r in report["external_literal_references"]]
    source = [(r["source_ordinal"], buyer.attention_keys(r["original_literal"]))
              for r in report["source_occurrences"]]
    expected = [[(j["external_references"], j["source_peer_ordinals"]) for j in r["joins"]]
                for r in report["source_occurrences"]]

    def cartesian():
        return [[(sorted(ref for ref, values in external if values[index] == key),
                  [peer for peer, values in source if peer != ordinal and values[index] == key])
                 for index, key in enumerate(keys)] for ordinal, keys in source]

    def indexed():
        outer = [defaultdict(list) for _ in buyer.METHODS]
        peers = [defaultdict(list) for _ in buyer.METHODS]
        for ref, keys in external:
            for index, key in enumerate(keys):
                outer[index][key].append(ref)
        for ordinal, keys in source:
            for index, key in enumerate(keys):
                peers[index][key].append(ordinal)
        return [[(sorted(outer[index].get(key, ())), [peer for peer in peers[index][key] if peer != ordinal])
                 for index, key in enumerate(keys)] for ordinal, keys in source]

    timings = {"cartesian": [], "indexed": []}
    for trial in range(samples):
        # Alternate order to avoid giving one strategy every warm-first position.
        order = (("cartesian", cartesian), ("indexed", indexed))
        for label, function in order if trial % 2 == 0 else reversed(order):
            started = time.perf_counter()
            actual = function()
            timings[label].append(round(time.perf_counter() - started, 6))
            if actual != expected:
                raise ValueError("Equal-work benchmark join mismatch")
    baseline = statistics.median(timings["cartesian"])
    optimized = statistics.median(timings["indexed"])
    return {"passed": True, "scope": "LOCAL_EQUAL_WORK_JOIN_PHASE_ONLY",
            "source_occurrences": len(source), "external_literal_forms": len(external),
            "methods": len(buyer.METHODS), "samples_per_strategy": samples,
            "all_join_results_equal": True, "measured_seconds": timings,
            "median_baseline_seconds": baseline, "median_indexed_seconds": optimized,
            "median_elapsed_reduction_percent": round(100 * (1 - optimized / baseline), 3),
            "includes_index_construction": True,
            "excludes_shared_normalization_and_source_verification": True,
            "whole_workflow_speedup_claimed": False, "billed_tokens_and_cost": None,
            "deployment_authorized": False}


if __name__ == "__main__":
    print(json.dumps(measure(), sort_keys=True))

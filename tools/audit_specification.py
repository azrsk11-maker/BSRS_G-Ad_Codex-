"""Read-only, standard-library audit of the supplied planning pack.

Inspected upstream validate_planning_package.py before use. Import validate(), never
its CLI (which overwrites source planning_validation.json). This tool writes only
to --output-dir, refuses an output directory within the source pack, and verifies
source hashes after execution. Its PASS is structure/integrity, never live readiness.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import time

sys.dont_write_bytecode = True


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def visit(value, counts):
    counts[type(value).__name__] += 1
    if isinstance(value, dict):
        for child in value.values():
            visit(child, counts)
    elif isinstance(value, list):
        for child in value:
            visit(child, counts)


def audit(source: Path, output: Path):
    started = time.perf_counter()
    source, output = source.resolve(), output.resolve()
    if output == source or source in output.parents:
        raise ValueError("Output must not be within the immutable source pack")
    files = sorted(p for p in source.rglob("*") if p.is_file())
    raw = {str(p.relative_to(source)).replace("\\", "/"): p.read_bytes() for p in files}
    before = {name: digest(data) for name, data in raw.items()}
    parsed, inventory = {}, []
    for name, data in raw.items():
        text = data.decode("utf-8-sig")
        entry = {"path": name, "bytes": len(data), "sha256": before[name],
                 "lines": len(text.splitlines()), "read_mode": "full_utf8_decode"}
        if name.endswith(".json"):
            value = json.loads(text, object_pairs_hook=unique_object,
                               parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
            counts = Counter()
            visit(value, counts)
            parsed[name] = value
            entry.update(read_mode="full_parse_and_recursive_visit", node_counts=dict(counts),
                         root_type=type(value).__name__, root_records=len(value))
        inventory.append(entry)

    checks = []

    def check(name, ok, observed):
        checks.append({"check": name, "passed": bool(ok), "observed": observed})

    declared = parsed["artifact_manifest.json"]["artifacts"]
    check("manifest paths are unique", len({x["path"] for x in declared}) == len(declared), len(declared))
    check("manifest covers every other supplied file", set(x["path"] for x in declared) == set(raw) - {"artifact_manifest.json"}, len(raw))
    mismatch = [x["path"] for x in declared if x["path"] not in raw or
                x["sha256"] != before.get(x["path"]) or x["bytes"] != len(raw.get(x["path"], b""))]
    check("all declared source bytes and SHA256 match", not mismatch, mismatch)

    # Upstream source was manually reviewed: validate() reads only; CLI main() writes.
    spec = importlib.util.spec_from_file_location("bsre_planning_validator", source / "validate_planning_package.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    upstream = module.validate(source)
    check("upstream planning validation rerun equals saved result", upstream == parsed["planning_validation.json"],
          {"status": upstream["status"], "checks": len(upstream["checks"])})

    registry = parsed["planned_campaign_page_registry.json"]
    families = parsed["page_family_allocation.json"]["families"]
    family_by_code = {f["code"]: f for f in families}
    check("family definitions have unique codes", len(family_by_code) == len(families), len(families))
    null_fields = ["actual_url", "google_campaign_id", "campaign_name", "property_destination",
                   "audience_origin", "language", "inventory_source", "permission_evidence",
                   "cms_content_or_native_route_id", "hostinger_site_id", "page_version", "tracking_evidence_ref"]
    constants = {"visibility": "UNLISTED_NOINDEX_PUBLIC_URL", "budget_approved": False,
                 "release_approved": False, "status": "PLANNED_SOURCE_REQUIRED",
                 "website_scope": "EXISTING_MAIN_SITE_NATIVE_PAGE",
                 "shared_tracking_configuration": "website_tracking_contract.json",
                 "tracking_status": "NOT_IMPLEMENTED_NOT_TESTED"}
    row_errors, next_slot = [], Counter()
    keys = set(null_fields) | set(constants) | {"campaign_key", "landing_page_id", "family_code", "family_name",
                                              "family_slot", "proposed_path", "primary_decision"}
    for number, row in enumerate(registry, 1):
        code = row.get("family_code")
        next_slot[code] += 1
        expected = {**constants, **dict.fromkeys(null_fields),
                    "campaign_key": f"BSRE-C{number:04}", "landing_page_id": f"BSRE-LP{number:04}",
                    "proposed_path": f"/lp/bsre-c{number:04}/", "family_slot": next_slot[code]}
        if code in family_by_code:
            expected.update(family_name=family_by_code[code]["family"], primary_decision=family_by_code[code]["decision"])
        else:
            row_errors.append({"row": number, "error": "unknown family"})
        if set(row) != keys:
            row_errors.append({"row": number, "error": "unexpected/missing keys"})
        for key, value in expected.items():
            if row.get(key) != value or (type(value) is bool and type(row.get(key)) is not bool):
                row_errors.append({"row": number, "field": key, "error": "unexpected planning value"})
    check("every field in all 360 rows checked against planning constraints", not row_errors, {"rows": len(registry), "fields_per_row": len(keys), "errors": row_errors})
    check("family slot sequences and quotas exact", dict(next_slot) == {f["code"]: f["pages"] for f in families}, dict(next_slot))

    signals = parsed["positive_intent_taxonomy.json"]
    check("signal sequence exact and all examples explicitly illustrative", all(
        row["signal_id"] == f"SIG-{i:03}" and row["example_status"] == "ILLUSTRATIVE_NOT_VOLUME_VERIFIED"
        and row["fixed_per_signal_quota"] is False and row["example_candidate"].strip()
        for i, row in enumerate(signals, 1)), len(signals))
    tests = parsed["website_tracking_acceptance_tests.json"]["tests"]
    check("all 32 tests unexecuted without fabricated evidence/reviewer", all(
        row["test_id"] == f"WT-{i:03}" and row["status"] == "NOT_EXECUTED"
        and row["evidence_ref"] is None and row["reviewer"] is None
        for i, row in enumerate(tests, 1)), len(tests))
    events = parsed["website_tracking_contract.json"]["events"]
    check("all event definitions undeployed and untested", all(
        row["implementation_status"] == "NOT_IMPLEMENTED" and row["test_status"] == "NOT_EXECUTED"
        for row in events), len(events))
    sources = parsed["sources.json"]
    check("source identifiers unique", len({s["id"] for s in sources}) == len(sources), len(sources))
    master = raw["BlackSwan_Real_Estate_Algorithmic_Master_Plan_v3.md"].decode("utf-8-sig")
    addendum = raw["Website_Tracking_Addendum_v3.md"].decode("utf-8-sig")
    amendment = addendum[addendum.index("## 24."):].strip()
    check("standalone amendment is verbatim in Master", amendment in master, "complete section 24 excluding separate reference appendix")
    numbered = re.findall(r"^## (\d+)\.", master, re.M)
    check("master sections numbered 1 through 24 in order", numbered == [str(i) for i in range(1, 25)], numbered)
    after_files = sorted(p for p in source.rglob("*") if p.is_file())
    after = {str(p.relative_to(source)).replace("\\", "/"): digest(p.read_bytes()) for p in after_files}
    check("source pack unchanged including file inventory", before == after, len(after))

    result = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source_directory": str(source), "scope": "PLANNING_INTEGRITY_ONLY_NOT_LIVE_ACCEPTANCE",
        "status": "PASS" if upstream["status"] == "PASS" and all(x["passed"] for x in checks) else "FAIL",
        "upstream_check_count": len(upstream["checks"]), "additional_check_count": len(checks),
        "files_read": len(files), "bytes_read": sum(map(len, raw.values())),
        "json_files_fully_parsed": len(parsed), "registry_rows_fully_checked": len(registry),
        "keyword_research_rows_completed_in_pack": {"positive": 0, "negative": 0},
        "keyword_deficits_in_pack": {"positive": 14000, "negative": 14000},
        "sources_revalidated_online_in_this_script": 0,
        "runtime_acceptance_tests_executed_by_this_script": 0,
        "checks": checks, "elapsed_seconds": round(time.perf_counter() - started, 6),
    }
    output.mkdir(parents=True, exist_ok=True)
    for name, value in [("source_inventory.json", {"files": inventory}),
                        ("planning_validation_rerun.json", upstream), ("specification_audit.json", result)]:
        (output / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.source, args.output_dir)
    print(json.dumps({k: v for k, v in report.items() if k != "checks"}, indent=2))
    raise SystemExit(0 if report["status"] == "PASS" else 1)

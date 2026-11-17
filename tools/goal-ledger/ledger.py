"""Offline coordinator for the existing 100 goals. No provider calls or writes."""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

IDS = tuple(f"G{i:03}" for i in range(1, 101))
STATUSES = ("pending", "running", "verified", "blocked")
GATES = ("prelaunch", "conditional", "later")
KINDS = {
    "observation", "local_test", "native_ci", "goal_acceptance", "blocker",
    "independent_human_review", "protected_merge", "identity_verification",
    "library_approval", "scoped_authorization", "configuration_readback",
    "deployment_readback", "activation_readback", "genuine_event",
}
SPECIAL_REQUIREMENTS = {
    "G002": {"native_ci"}, "G003": {"independent_human_review"},
    "G004": {"protected_merge"}, "G005": {"identity_verification"},
    "G025": {"library_approval"}, "G029": {"library_approval"},
    "G044": {"genuine_event"}, "G045": {"genuine_event"},
    "G048": {"genuine_event", "scoped_authorization"},
    "G049": {"genuine_event"},
    "G070": {"scoped_authorization", "configuration_readback"},
    "G081": {"independent_human_review"},
    "G082": {"scoped_authorization"},
    "G083": {"deployment_readback"},
    "G084": {"scoped_authorization"},
    "G085": {"deployment_readback"},
    "G088": {"scoped_authorization"},
    "G089": {"activation_readback"},
    **{f"G{i:03}": {"genuine_event"} for i in range(90, 94)},
}
DEFINITION = "docs/EXECUTION_BACKLOG_100.md"


def required_kinds(goal_id):
    return SPECIAL_REQUIREMENTS.get(goal_id, {"goal_acceptance"})


def plan_digest(rows):
    """Pin canonical IDs/dependencies/classifications independently of live status."""
    plan = [{key: row.get(key) for key in ("id", "depends_on", "launch_gate")} for row in rows]
    return hashlib.sha256(json.dumps(plan, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def portable_ref(value):
    """Public-source artifact references only; no local paths or private URLs."""
    return (isinstance(value, str) and len(value) <= 240
            and bool(re.fullmatch(r"(?:docs|tools)/[A-Za-z0-9_./#-]+", value))
            and ".." not in value.split("/"))


def validate(data):
    """Return bounded errors. References are assertions, not verified file content."""
    errors = []
    if not isinstance(data, dict):
        return ["ledger must be an object"]
    if type(data.get("schema_version")) is not int or data.get("schema_version") != 1 or data.get("definition_ref") != DEFINITION:
        errors.append("unsupported schema or canonical definition reference")
    rows = data.get("goals")
    if not isinstance(rows, list) or len(rows) != 100:
        return errors + ["exactly 100 goal rows required"]
    if any(not isinstance(row, dict) for row in rows):
        return errors + ["every goal must be an object"]
    keys = [row.get("id") for row in rows]
    if keys != list(IDS):
        return errors + ["goal IDs must be exactly G001..G100, once, in order"]
    if data.get("canonical_plan_sha256") != plan_digest(rows):
        errors.append("canonical plan checksum mismatch; dependencies/classifications changed")
    evidence = data.get("evidence")
    if not isinstance(evidence, dict):
        return errors + ["evidence must be an object"]
    for key, item in evidence.items():
        if not isinstance(key, str) or not re.fullmatch(r"[a-z0-9-]{1,64}", key):
            errors.append("invalid evidence key")
        if not isinstance(item, dict):
            errors.append(f"evidence {key}: must be an object")
            continue
        if not isinstance(item.get("kind"), str) or item.get("kind") not in KINDS or not portable_ref(item.get("ref")):
            errors.append(f"evidence {key}: invalid kind or nonportable reference")
        bound = item.get("goals")
        if (not isinstance(bound, list) or any(x not in IDS for x in bound)
                or len(set(bound)) != len(bound)):
            errors.append(f"evidence {key}: invalid goal bindings")
    by_id = {row["id"]: row for row in rows}
    graph = {}
    for row in rows:
        goal_id = row["id"]
        deps = row.get("depends_on")
        if (not isinstance(deps, list) or any(x not in IDS for x in deps)
                or len(set(deps)) != len(deps) or goal_id in deps):
            errors.append(f"{goal_id}: invalid dependencies")
            deps = []
        graph[goal_id] = deps
        if row.get("launch_gate") not in GATES:
            errors.append(f"{goal_id}: invalid launch classification")
        if row.get("status") not in STATUSES:
            errors.append(f"{goal_id}: invalid status")
        preparation = row.get("preparation_only", False)
        if type(preparation) is not bool:
            errors.append(f"{goal_id}: preparation_only must be a boolean")
        if preparation is True and row.get("status") != "running":
            errors.append(f"{goal_id}: preparation_only true requires running status")
        refs = row.get("evidence_refs")
        if (not isinstance(refs, list) or any(not isinstance(x, str) for x in refs)
                or len(set(refs)) != len(refs)):
            errors.append(f"{goal_id}: invalid evidence references")
            refs = []
        bound_items = []
        for ref in refs:
            item = evidence.get(ref)
            if (not isinstance(item, dict) or not isinstance(item.get("goals"), list)
                    or goal_id not in item["goals"]):
                errors.append(f"{goal_id}: missing or wrongly bound evidence {ref}")
            else:
                if isinstance(item.get("kind"), str) and item["kind"] in KINDS:
                    bound_items.append(item)
        kinds = {item.get("kind") for item in bound_items}
        if row.get("status") == "blocked" and "blocker" not in kinds:
            errors.append(f"{goal_id}: blocked requires a bound blocker reference")
        if row.get("status") == "running" and not kinds - {"blocker"}:
            errors.append(f"{goal_id}: running requires a bound progress/evidence reference")
        if row.get("status") == "verified":
            missing = sorted(required_kinds(goal_id) - kinds)
            if missing:
                errors.append(f"{goal_id}: verified requires evidence kinds {','.join(missing)}")
        if (row.get("status") == "verified"
                or row.get("status") == "running" and preparation is not True):
            unmet = [dep for dep in deps if by_id[dep].get("status") != "verified"]
            if unmet:
                errors.append(f"{goal_id}: unverified dependencies {','.join(unmet)}")
    visiting, visited = set(), set()

    def visit(goal_id):
        if goal_id in visiting:
            return False
        if goal_id in visited:
            return True
        visiting.add(goal_id)
        for dep in graph[goal_id]:
            if not visit(dep):
                return False
        visiting.remove(goal_id)
        visited.add(goal_id)
        return True

    if not all(visit(goal_id) for goal_id in IDS):
        errors.append("dependency graph contains a cycle")
    return errors


def summary(data):
    errors = validate(data)
    if errors:
        raise ValueError("; ".join(errors))
    rows = data["goals"]
    by_id = {row["id"]: row for row in rows}
    ready = {gate: [] for gate in GATES}
    ready_to_finish = {gate: [] for gate in GATES}
    waiting = {}
    for row in rows:
        unmet = [dep for dep in row["depends_on"] if by_id[dep]["status"] != "verified"]
        if row["status"] == "pending" and not unmet:
            ready[row["launch_gate"]].append(row["id"])
        if (row["status"] in ("pending", "running") and not unmet
                and row.get("preparation_only", False) is not True):
            ready_to_finish[row["launch_gate"]].append(row["id"])
        if row["status"] != "verified" and unmet:
            waiting[row["id"]] = unmet
    launch = [row["id"] for row in rows if row["launch_gate"] == "prelaunch"]
    open_launch = [goal_id for goal_id in launch if by_id[goal_id]["status"] != "verified"]
    return {
        "schema_version": 1, "goal_count": 100,
        "counts": {status: sum(row["status"] == status for row in rows) for status in STATUSES},
        "ready": ready,
        "ready_to_finish": ready_to_finish,
        "running": [row["id"] for row in rows if row["status"] == "running"],
        "running_preparation": [row["id"] for row in rows if row["status"] == "running"
                                and row.get("preparation_only", False) is True],
        "running_execution": [row["id"] for row in rows if row["status"] == "running"
                              and row.get("preparation_only", False) is False],
        "blocked": [row["id"] for row in rows if row["status"] == "blocked"],
        "waiting_on": waiting,
        "launch": {"required_count": len(launch), "open_goals": open_launch,
                   "prerequisites_verified": not open_launch},
        "authority": "planning_only_no_execution_permission",
    }


def seed(canonical):
    """Import identifiers, dependency graph and gate types; never import private prose."""
    goals = [row for group in canonical["groups"] for row in group["goals"]]
    if (any(type(row["id"]) is not int for row in goals)
            or [row["id"] for row in goals] != list(range(1, 101))):
        raise ValueError("canonical input must contain exactly ordered IDs 1..100")
    gate_map = {True: "prelaunch", False: "later", "conditional_on_selected_scope": "conditional"}
    rows = []
    for goal in goals:
        gate = goal["first_launch_gate"]
        if type(gate) not in (bool, str) or gate not in gate_map:
            raise ValueError("unsupported canonical launch classification")
        deps = goal["critical_dependencies"]
        if any(type(dep) is not int or dep not in range(1, 101) for dep in deps):
            raise ValueError("canonical dependency is not a valid integer goal ID")
        rows.append({"id": f"G{goal['id']:03}",
                     "depends_on": [f"G{dep:03}" for dep in deps],
                     "launch_gate": gate_map[gate], "status": "pending", "evidence_refs": []})
    result = {"schema_version": 1, "definition_ref": DEFINITION,
              "canonical_plan_sha256": plan_digest(rows), "evidence": {}, "goals": rows}
    errors = validate(result)
    if errors:
        raise ValueError("; ".join(errors))
    return result


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n",
                          encoding="utf-8", newline="\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "summary"):
        sub.add_parser(name).add_argument("ledger")
    create = sub.add_parser("seed", help="explicitly create a new pending ledger from canonical JSON")
    create.add_argument("canonical")
    create.add_argument("output")
    args = parser.parse_args(argv)
    try:
        if args.command == "seed":
            if Path(args.output).exists():
                raise ValueError("refusing to overwrite an existing ledger")
            data = seed(load(args.canonical))
            write(args.output, data)
            print('{"created":true,"goal_count":100}')
            return 0
        data = load(args.ledger)
        errors = validate(data)
        if errors:
            print(json.dumps({"valid": False, "errors": errors}, sort_keys=True))
            return 1
        print(json.dumps({"valid": True, "goal_count": 100} if args.command == "validate"
                         else summary(data), sort_keys=True, separators=(",", ":")))
        return 0
    except (ValueError, KeyError, TypeError, OSError) as exc:
        # Do not echo paths/private input values from parser or filesystem errors.
        print(json.dumps({"valid": False, "error": type(exc).__name__}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

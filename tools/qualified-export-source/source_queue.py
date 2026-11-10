"""Private durable owner-review staging. No provider source, upload, or network API.

The preserved qualification preview remains UPLOAD_PROHIBITED. This module does
not convert it into Google columns. It reserves first-person candidates passing
the existing local checks and reconciles fresh supplied evidence before use.
"""
from __future__ import annotations

import argparse
from calendar import monthrange
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import sys

HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[1]
HISTORY = HERE.parent / "qualification-history"
if str(HISTORY) not in sys.path:
    sys.path.insert(0, str(HISTORY))
from audit_history import (KNOWN_EXCLUSIONS, MAX_ROWS, AuditInputError,
                           audit_history, read_bounded, validate_envelope)
from qualification_core import _inspect, strict_json_bytes, when

SCHEMA = "bsre-private-qualified-queue-v1"
ARTIFACT = "PRIVATE_QUALIFIED_OWNER_REVIEW_QUEUE_NOT_GOOGLE_SOURCE"
BINDING_FIELDS = {"customer_id", "conversion_owner_customer_id", "conversion_action_id",
                  "conversion_name", "mapping_verified", "stage_key", "identifier_route"}
REVIEW_FIELDS = {"schema", "fixture_only", "ledger_sha256", "purpose_sha256", "binding_sha256",
                 "retention_sha256", "whole_history_reviewed", "permission_mapping_reviewed",
                 "reviewer_reference", "evidence_reference", "reviewed_at_utc"}
RETENTION_FIELDS = {"outcome_id", "closed_at_utc", "retention_due_at_utc",
                    "review_verified", "evidence_reference"}
INPUT_NAMES = ("ledger", "purpose", "binding", "retention", "review")


class SourceError(ValueError):
    """Bounded public diagnostic; never contains a supplied value or path."""


def require(condition, code):
    if not condition:
        raise SourceError(code)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def opaque(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9:_-]{0,149}", value) is not None


def utc(value):
    require(isinstance(value, str) and value.endswith("Z"), "UTC_Z_TIMESTAMP_REQUIRED")
    parsed = when(value)
    require(parsed.utcoffset().total_seconds() == 0, "UTC_Z_TIMESTAMP_REQUIRED")
    return parsed.astimezone(timezone.utc)


def clock(value):
    require(isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None,
            "TIMEZONE_REQUIRED")
    return value.astimezone(timezone.utc)


def next_year(value):
    year = value.year + 1
    return value.replace(year=year, day=min(value.day, monthrange(year, value.month)[1]))


def private_path(value, *, existing=False):
    """Never write the private queue/projection into the source checkout."""
    supplied = Path(value).absolute()
    if supplied.exists() or supplied.is_symlink():
        require(stat.S_ISREG(supplied.lstat().st_mode), "PRIVATE_FILE_TYPE_INVALID")
    require(not supplied.is_symlink(), "PRIVATE_FILE_TYPE_INVALID")
    resolved = supplied.resolve()
    require(not resolved.is_relative_to(REPOSITORY), "PRIVATE_OUTPUT_OUTSIDE_REPOSITORY_REQUIRED")
    require(resolved.parent.is_dir(), "PRIVATE_PARENT_REQUIRED")
    require(not existing or resolved.is_file(), "PRIVATE_FILE_REQUIRED")
    return resolved


class Snapshot:
    """Exact, bounded bytes of whitelisted evidence extracts; no raw intake."""

    def __init__(self, raw):
        require(set(raw) == set(INPUT_NAMES), "INPUT_SET_INVALID")
        require(all(isinstance(value, bytes) and len(value) <= 10 * 1024 * 1024 for value in raw.values()),
                "INPUT_SIZE_OR_TYPE_INVALID")
        try:
            self.values = {key: strict_json_bytes(value) for key, value in raw.items()}
        except (ValueError, UnicodeError, TypeError, RecursionError) as error:
            raise SourceError("INPUT_JSON_INVALID") from error
        self.hashes = {key: digest(value) for key, value in raw.items()}
        self.sha256 = digest(canonical(self.hashes).encode("utf-8"))

    @classmethod
    def from_paths(cls, paths):
        return cls({key: read_bounded(Path(value)) for key, value in paths.items()})

    def evaluate(self, now):
        try:
            return self._evaluate(clock(now))
        except (ValueError, TypeError, KeyError, OverflowError, RecursionError) as error:
            if isinstance(error, SourceError):
                raise
            raise SourceError("INPUT_OR_VALIDATION_ERROR") from error

    def _evaluate(self, now):
        data, purposes, binding, retention, review = (self.values[key] for key in INPUT_NAMES)
        validate_envelope(data, None)
        require(isinstance(purposes, list) and len(purposes) <= MAX_ROWS, "PURPOSE_ROWS_INVALID")
        require(isinstance(binding, dict) and set(binding) == BINDING_FIELDS, "BINDING_FIELDS_INVALID")
        require(isinstance(review, dict) and set(review) == REVIEW_FIELDS, "REVIEW_FIELDS_INVALID")
        require(review["schema"] == "bsre-qualified-preparation-review-v1" and
                type(review["fixture_only"]) is bool and review["fixture_only"] == data["fixture_only"],
                "REVIEW_CLASSIFICATION_INVALID")
        for key in INPUT_NAMES[:-1]:
            require(review[key + "_sha256"] == self.hashes[key], "REVIEW_EXACT_INPUT_HASH_MISMATCH")
        require(opaque(review["reviewer_reference"]) and opaque(review["evidence_reference"]),
                "REVIEW_REFERENCE_INVALID")
        require(review["whole_history_reviewed"] is True and review["permission_mapping_reviewed"] is True,
                "COMPLETE_HISTORY_AND_PERMISSION_REVIEW_REQUIRED")
        reviewed = utc(review["reviewed_at_utc"])
        require(reviewed <= now, "REVIEW_TIME_INVALID")
        # The review must cover these actual observations, not predate them.
        require(all(utc(row["recorded_at_utc"]) <= reviewed for row in data["records"]),
                "REVIEW_PRECEDES_RECORDED_HISTORY")
        require(all(when(row["observed_at_utc"]) <= reviewed for row in purposes),
                "REVIEW_PRECEDES_PURPOSE_OBSERVATION")
        for row in data["records"]:
            require(opaque(row.get("person_key")) and opaque(row.get("lead_id")) and
                    opaque(row.get("canonical_lead_id")), "OPAQUE_PRIVATE_JOIN_REQUIRED")
        require(isinstance(retention, dict) and set(retention) ==
                {"schema", "fixture_only", "ledger_sha256", "records", "history_incomplete",
                 "history_marker_verified", "history_marker_evidence_reference", "history_marker_read_at_utc"},
                "RETENTION_ENVELOPE_INVALID")
        require(retention["schema"] == "bsre-qualified-retention-review-v1" and
                type(retention["fixture_only"]) is bool and retention["fixture_only"] == data["fixture_only"] and
                retention["ledger_sha256"] == self.hashes["ledger"], "RETENTION_BINDING_INVALID")
        require(type(retention["history_incomplete"]) is bool or retention["history_incomplete"] is None,
                "RETENTION_HISTORY_MARKER_INVALID")
        require(type(retention["history_marker_verified"]) is bool and
                opaque(retention["history_marker_evidence_reference"]) and
                utc(retention["history_marker_read_at_utc"]) <= reviewed,
                "RETENTION_HISTORY_EVIDENCE_INVALID")
        require(isinstance(retention["records"], list) and len(retention["records"]) <= MAX_ROWS,
                "RETENTION_ROWS_INVALID")
        retained = {}
        for row in retention["records"]:
            require(isinstance(row, dict) and set(row) == RETENTION_FIELDS, "RETENTION_FIELDS_INVALID")
            require(isinstance(row["outcome_id"], str) and row["outcome_id"] not in retained,
                    "RETENTION_OUTCOME_NOT_UNIQUE")
            require(row["review_verified"] is True and opaque(row["evidence_reference"]),
                    "RETENTION_REVIEW_REQUIRED")
            due = utc(row["retention_due_at_utc"]) if row["retention_due_at_utc"] is not None else None
            if row["closed_at_utc"] is not None:
                closed = utc(row["closed_at_utc"])
                require(closed <= reviewed and due is not None and closed < due <= next_year(closed),
                        "TWELVE_MONTH_CLOSURE_RETENTION_REQUIRED")
            retained[row["outcome_id"]] = due

        audit = audit_history(data, now)
        report, preview, selection = _inspect(data, binding, purposes, now)
        require(preview.get("UPLOAD_PROHIBITED") is True and preview.get("artifact_type") ==
                "GCLID_INTERNAL_REVIEW_PREVIEW_NOT_UPLOAD_FORMAT", "PRESERVED_PREVIEW_CONTRACT_CHANGED")
        global_holds = []
        if retention["history_incomplete"] is not False or retention["history_marker_verified"] is not True:
            global_holds.append("AUTHORITATIVE_RETENTION_HISTORY_NOT_COMPLETE")
        if not audit["history"]["complete_attested"]:
            global_holds.append("WHOLE_HISTORY_NOT_ATTESTED")
        if audit["counts"]["held_person_mappings"] or set(audit["outcome_hold_counts"]) - KNOWN_EXCLUSIONS:
            global_holds.append("WHOLE_HISTORY_HAS_UNRESOLVED_BUSINESS_HOLDS")
        original = {row["outcome_id"]: row for row in data["records"]}
        person_leads = {}
        for row in data["records"]:
            person_leads.setdefault(row["person_key"], set()).update((row["lead_id"], row["canonical_lead_id"]))
        withdrawn_leads = {p["lead_id"] for p in purposes if p["withdrawn_at_utc"] is not None}
        withdrawn_people = {person for person, leads in person_leads.items() if leads & withdrawn_leads}
        previews = {row["outcome_id"]: row for row in preview["rows"]}
        withheld = {row["outcome_id"]: row["codes"] for row in report["export_held"]}
        candidates = {}
        for chosen in selection:
            oid = chosen["outcome_id"]
            row = original[oid]
            holds = list(global_holds) + withheld.get(oid, [])
            private_preview = previews.get(oid)
            if private_preview is None and not withheld.get(oid):
                holds.append("QUALIFICATION_PREVIEW_NOT_ELIGIBLE")
            permission = [p for p in purposes if p["lead_id"] == row["lead_id"]]
            latest = max(permission, key=lambda p: when(p["observed_at_utc"]), default=None)
            original_permission = bool(latest and any(
                p["evidence_id"] == row.get("privacy_evidence_reference") and
                p["click_id_type"] == "GCLID" and p["click_id"] == row.get("click_id") and
                all(p[key] is True for key in ("acknowledged", "measurement_eligible", "ad_measurement",
                                               "record_integrity_verified")) and
                p["ad_user_data"] == "GRANTED" and p["ad_personalization"] == "DENIED" and
                p["withdrawn_at_utc"] is None and
                all(isinstance(p[key], str) and p[key].strip() and p[key] != "none"
                    for key in ("evidence_id", "decision_version", "notice_version")) and
                when(p["observed_at_utc"]) <= when(p["attribution_captured_at_utc"]) <= when(row["occurred_at_utc"]) and
                when(p["expires_at_utc"]) > when(p["attribution_captured_at_utc"]) and
                when(p["attribution_captured_at_utc"]) == when(latest["attribution_captured_at_utc"])
                for p in permission))
            if not original_permission:
                holds.append("ORIGINAL_PERMISSION_AT_CAPTURE_NOT_ESTABLISHED")
            # Any recorded withdrawal for this original lead latches locally;
            # a replacement evidence ID or later grant cannot revive it.
            withdrawn = row["person_key"] in withdrawn_people
            if withdrawn:
                holds.append("WITHDRAWAL_REVIEW_HOLD")
            expiry = min((when(p["expires_at_utc"]) for p in permission), default=now)
            due = retained.get(oid)
            if oid not in retained:
                holds.append("RETENTION_REVIEW_MISSING")
            retire_at = min(expiry, due) if due is not None else expiry
            if retire_at <= now:
                holds.append("RETENTION_OR_PERMISSION_EXPIRED")
            payload = None
            if private_preview is not None and not withdrawn and original_permission:
                # This deliberately uses original Outcome40 time, including
                # fractional seconds. The legacy preview formats whole seconds.
                payload = {"outcome_id": oid, "lead_id": row["lead_id"],
                           "original_gclid": private_preview["google_click_id"],
                           "actual_qualified_at_utc": row["occurred_at_utc"],
                           "conversion_action_id": row["conversion_action_id"],
                           "conversion_name": row["conversion_name"],
                           "original_order_id": row["order_id"]}
            candidates[row["person_key"]] = {"outcome_id": oid, "payload": payload,
                "retire_at": retire_at.astimezone(timezone.utc).isoformat(),
                "withdrawn": withdrawn, "holds": sorted(set(holds))}
        return {"fixture_only": data["fixture_only"], "candidates": candidates,
                "provided_people": {row["person_key"] for row in data["records"]},
                "withdrawn_people": withdrawn_people,
                "retention_history_gap": retention["history_incomplete"] is True,
                "global_holds": global_holds, "audit": audit}


class PrivateQueue:
    def __init__(self, path):
        self.path = private_path(path)
        created = not self.path.exists()
        if created:
            descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(descriptor)
        self.db = sqlite3.connect(self.path, isolation_level=None, timeout=5)
        self.db.row_factory = sqlite3.Row
        try:
            if not created:
                require(self.db.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='metadata'")
                        .fetchone()[0] == 1 and self._meta("schema") == SCHEMA, "QUEUE_SCHEMA_MISMATCH")
            self.db.execute("PRAGMA journal_mode=DELETE")
            self.db.execute("PRAGMA secure_delete=ON")
            self.db.executescript("""
          CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS queue (
            person_key TEXT PRIMARY KEY, outcome_id TEXT NOT NULL UNIQUE,
            payload TEXT, payload_sha256 TEXT, state TEXT NOT NULL,
            holds TEXT NOT NULL, snapshot_sha256 TEXT NOT NULL,
            reviewed_snapshot_sha256 TEXT, reviewer_reference TEXT,
            updated_at TEXT NOT NULL, retire_at TEXT NOT NULL,
            withdrawal_latched INTEGER NOT NULL DEFAULT 0,
            identity_conflict_latched INTEGER NOT NULL DEFAULT 0);
            """)
            self.db.execute("INSERT OR IGNORE INTO metadata VALUES ('schema', ?)", (SCHEMA,))
        except Exception:
            self.db.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.db.close()

    def _meta(self, key):
        row = self.db.execute("SELECT value FROM metadata WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def _set_meta(self, key, value):
        self.db.execute("INSERT OR REPLACE INTO metadata VALUES (?,?)", (key, value))

    def _begin(self, now):
        now = clock(now)
        self.db.execute("BEGIN IMMEDIATE")
        previous = self._meta("last_evaluated_at")
        if previous is not None and now < when(previous):
            self.db.rollback()
            raise SourceError("QUEUE_TIME_CANNOT_MOVE_BACKWARDS")
        self._set_meta("last_evaluated_at", now.isoformat())
        return now

    def stage(self, snapshot, now):
        now = clock(now)
        evaluated = snapshot.evaluate(now)  # Validate every extract before any write.
        self._begin(now)
        try:
            fixture = "true" if evaluated["fixture_only"] else "false"
            require(self._meta("fixture_only") in (None, fixture), "QUEUE_FIXTURE_CLASSIFICATION_MISMATCH")
            self._set_meta("fixture_only", fixture)
            existing = {row["person_key"]: row for row in self.db.execute("SELECT * FROM queue")}
            expired = {person for person, row in existing.items() if when(row["retire_at"]) <= now}
            for person in expired:
                self.db.execute("DELETE FROM queue WHERE person_key=?", (person,))
                existing.pop(person)
            if expired:
                self._set_meta("history_gap", "true")
            # A deleted historical person is a completeness gap, not permission
            # to forget their qualification and count a new first outcome.
            if set(existing) - evaluated["provided_people"] or evaluated["retention_history_gap"]:
                self._set_meta("history_gap", "true")
            gap = self._meta("history_gap") == "true"
            all_people = set(existing) | set(evaluated["candidates"])
            existing_outcomes = {row["outcome_id"]: row["person_key"] for row in existing.values()}
            changed_owners = {existing_outcomes[item["outcome_id"]]
                              for person, item in evaluated["candidates"].items()
                              if item["outcome_id"] in existing_outcomes and
                              existing_outcomes[item["outcome_id"]] != person}
            for person in sorted(all_people):
                before = existing.get(person)
                candidate = evaluated["candidates"].get(person)
                if candidate is None:
                    holds = ["SOURCE_NO_LONGER_ELIGIBLE"]
                    if gap:
                        holds.append("DURABLE_HISTORY_GAP")
                    withdrawn = bool(before["withdrawal_latched"] or person in evaluated["withdrawn_people"])
                    if withdrawn:
                        holds.append("WITHDRAWAL_LATCHED")
                    conflict = bool(before["identity_conflict_latched"] or person in changed_owners)
                    if conflict:
                        holds.append("RESERVED_IDENTITY_CHANGED_REVIEW_REQUIRED")
                    self.db.execute("UPDATE queue SET state='HELD', holds=?, snapshot_sha256=?, "
                                    "reviewed_snapshot_sha256=NULL, reviewer_reference=NULL, updated_at=?, "
                                    "payload=CASE WHEN ? THEN NULL ELSE payload END, "
                                    "payload_sha256=CASE WHEN ? THEN NULL ELSE payload_sha256 END, "
                                    "withdrawal_latched=?, identity_conflict_latched=? WHERE person_key=?",
                                    (canonical(holds), snapshot.sha256, now.isoformat(), withdrawn, withdrawn,
                                     withdrawn, conflict, person))
                    continue
                holds = list(candidate["holds"])
                if gap:
                    holds.append("DURABLE_HISTORY_GAP")
                if gap and before is None:
                    # No person tombstones are retained. Once history is lost,
                    # do not recreate deleted/new private qualification mappings.
                    continue
                if when(candidate["retire_at"]) <= now and before is None:
                    # Expired requests cannot recreate a purged private row.
                    continue
                owner = existing_outcomes.get(candidate["outcome_id"])
                if owner is not None and owner != person:
                    continue
                payload = canonical(candidate["payload"]) if candidate["payload"] is not None else None
                payload_hash = digest(payload.encode("utf-8")) if payload else None
                withdrawn = bool(candidate["withdrawn"] or before and before["withdrawal_latched"])
                conflict = bool(person in changed_owners or before and (before["identity_conflict_latched"] or
                    before["outcome_id"] != candidate["outcome_id"] or
                    before["payload_sha256"] and payload_hash and before["payload_sha256"] != payload_hash))
                if withdrawn:
                    holds.append("WITHDRAWAL_LATCHED")
                    payload = payload_hash = None
                if conflict:
                    holds.append("RESERVED_IDENTITY_CHANGED_REVIEW_REQUIRED")
                if before:
                    retire_at = min(when(before["retire_at"]), when(candidate["retire_at"])).isoformat()
                    # Conflicts preserve original identity/time; no auto-replacement.
                    if conflict and not withdrawn:
                        payload, payload_hash = before["payload"], before["payload_sha256"]
                    elif payload is None and not withdrawn:
                        payload, payload_hash = before["payload"], before["payload_sha256"]
                    oid = before["outcome_id"]
                else:
                    retire_at, oid = candidate["retire_at"], candidate["outcome_id"]
                if when(retire_at) <= now:
                    holds.append("RETENTION_OR_PERMISSION_EXPIRED")
                holds = sorted(set(holds))
                reviewed = before and before["reviewed_snapshot_sha256"] == snapshot.sha256 and not holds
                state = "HELD" if holds else "OWNER_REVIEWED" if reviewed else "OWNER_REVIEW"
                self.db.execute("""INSERT OR REPLACE INTO queue VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (person, oid, payload, payload_hash, state, canonical(holds), snapshot.sha256,
                     snapshot.sha256 if reviewed else None, before["reviewer_reference"] if reviewed else None,
                     now.isoformat(), retire_at, int(withdrawn), int(conflict)))
            self._set_meta("snapshot_sha256", snapshot.sha256)
            evaluation_holds = Counter(code for item in evaluated["candidates"].values() for code in item["holds"])
            if gap:
                evaluation_holds["DURABLE_HISTORY_GAP"] += len(evaluated["candidates"])
            self._set_meta("evaluation_hold_counts", canonical(dict(evaluation_holds)))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.summary()

    def mark_reviewed(self, outcome_id, expected_snapshot_sha256, reviewer_reference, now):
        require(opaque(reviewer_reference), "REVIEWER_REFERENCE_INVALID")
        now = self._begin(now)
        try:
            row = self.db.execute("SELECT * FROM queue WHERE outcome_id=?", (outcome_id,)).fetchone()
            require(row is not None and row["snapshot_sha256"] == expected_snapshot_sha256 and
                    self._meta("snapshot_sha256") == expected_snapshot_sha256, "REVIEW_SNAPSHOT_MISMATCH")
            require(self._meta("history_gap") != "true" and row["holds"] == "[]" and
                    row["payload"] is not None and when(row["retire_at"]) > now, "REVIEW_HELD_OR_EXPIRED")
            self.db.execute("UPDATE queue SET state='OWNER_REVIEWED', reviewed_snapshot_sha256=?, "
                            "reviewer_reference=?, updated_at=? WHERE outcome_id=?",
                            (expected_snapshot_sha256, reviewer_reference, now.isoformat(), outcome_id))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.summary()

    def projection(self, snapshot, now):
        # A fresh reconciliation is mandatory, including after owner review.
        summary = self.stage(snapshot, now)
        self.db.execute("BEGIN")
        try:
            require(self._meta("snapshot_sha256") == snapshot.sha256, "PROJECTION_SNAPSHOT_CHANGED")
            rows = [{**json.loads(row["payload"]), "private_review_valid_until_utc": row["retire_at"]}
                    for row in self.db.execute("SELECT payload, retire_at FROM queue WHERE state='OWNER_REVIEWED' "
                        "AND holds='[]' AND snapshot_sha256=? AND reviewed_snapshot_sha256=? ORDER BY outcome_id",
                        (snapshot.sha256, snapshot.sha256))] if self._meta("history_gap") != "true" else []
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {"artifact_type": ARTIFACT, "UPLOAD_PROHIBITED": True,
                "google_source_format_verified": False, "provider_route_eligibility_verified": False,
                "account_restricted_access_verified": False, "source_evidence_truth_independently_verified": False,
                "private_storage_access_independently_verified": False, "requires_fresh_reconciliation": True,
                "fixture_only": self._meta("fixture_only") == "true", "evaluated_at_utc": clock(now).isoformat(),
                "snapshot_sha256": snapshot.sha256, "rows": rows, "summary": summary}

    def purge(self, now):
        now = self._begin(now)
        try:
            expired = [row[0] for row in self.db.execute("SELECT person_key, retire_at FROM queue")
                       if when(row[1]) <= now]
            for person in expired:
                self.db.execute("DELETE FROM queue WHERE person_key=?", (person,))
            if expired:
                # No person hash/tombstone survives. Completeness remains held.
                self._set_meta("history_gap", "true")
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {**self.summary(), "private_rows_purged": len(expired)}

    def summary(self):
        states = Counter()
        holds = Counter()
        for row in self.db.execute("SELECT state, holds FROM queue"):
            states[row["state"]] += 1
            holds.update(json.loads(row["holds"]))
        return {"schema": SCHEMA, "scope": "PRIVATE_OWNER_REVIEW_ONLY", "UPLOAD_PROHIBITED": True,
                "network_calls": 0, "fixture_only": self._meta("fixture_only") == "true",
                "private_storage_access_independently_verified": False,
                "snapshot_sha256": self._meta("snapshot_sha256"),
                "durable_history_gap": self._meta("history_gap") == "true",
                "states": dict(sorted(states.items())), "hold_counts": dict(sorted(holds.items())),
                "evaluation_hold_counts": json.loads(self._meta("evaluation_hold_counts") or "{}"),
                "contains_record_identifiers_or_click_data": False}


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise SourceError("ARGUMENTS_INVALID")


def main(argv=None):
    parser = Parser(description=__doc__)
    parser.add_argument("operation", choices=("stage", "review", "project", "purge"))
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--now", required=True)
    for name in INPUT_NAMES:
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--outcome-id")
    parser.add_argument("--snapshot-sha256")
    parser.add_argument("--reviewer-reference")
    parser.add_argument("--output", type=Path)
    try:
        args = parser.parse_args(argv)
        now = when(args.now)
        snapshot = None
        if args.operation in ("stage", "project"):
            paths = {name: getattr(args, name) for name in INPUT_NAMES}
            require(all(paths.values()), "ALL_EVIDENCE_INPUTS_REQUIRED")
            snapshot = Snapshot.from_paths(paths)
            snapshot.evaluate(now)
        output = private_path(args.output) if args.operation == "project" and args.output else None
        require(args.operation != "project" or output is not None, "PRIVATE_OUTPUT_REQUIRED")
        with PrivateQueue(args.db) as queue:
            if args.operation == "stage":
                result = queue.stage(snapshot, now)
            elif args.operation == "review":
                result = queue.mark_reviewed(args.outcome_id, args.snapshot_sha256, args.reviewer_reference, now)
            elif args.operation == "purge":
                result = queue.purge(now)
            else:
                projection = queue.projection(snapshot, now)
                # A projection is a dated private review artifact. Never overwrite
                # an existing file or expose identifier-bearing content to stdout.
                descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as target:
                    target.write(canonical(projection) + "\n")
                result = {**projection["summary"], "private_projection_rows": len(projection["rows"])}
    except (SourceError, AuditInputError, ValueError, TypeError, KeyError, OverflowError,
            RecursionError, OSError, sqlite3.Error) as error:
        code = str(error) if isinstance(error, SourceError) else "LOCAL_INPUT_OR_STORAGE_REJECTED"
        print(json.dumps({"status": "REJECTED", "code": code, "UPLOAD_PROHIBITED": True}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

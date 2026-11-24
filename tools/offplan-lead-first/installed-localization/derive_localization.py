"""Private offline localization derivation. No WordPress hooks or deployment client."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from types import ModuleType
from urllib.parse import unquote_to_bytes

LOCALES = ("de-DE", "fr-FR", "zh-Hant-TW")
INTAKE_PATH = "/enquire/off-plan/"
LOCALE_KEY = "bsre_locale"
COMPILER_SHA256 = "a96849ef61ab02b201297fa0c7722df4c794c7f0acc26c1c6f748ac27b51e086"
CATALOG_SHA256 = "37077c6777f64505c6b6512fab99fec8a4177885572016f7ac63a79348d47b17"
PREIMAGES = {
    "assets/lead.js": (26591, "c42a6a68cdab20a700f9fe06a306a32903080fa1ac58b87fc8e8f26ce3f25f16"),
    "assets/consent-bridge.js": (18242, "490b50be1fa1113f8a152bd0fcb8899efc9d7a1f9e5a149798a851e342f1f993"),
    "templates/source/off-plan.html": (11168, "78e2349a7e1b1e2acee94e65d592d72a9d1902d6881040ec89bf7c38c5d8e05f"),
}


class GuardError(ValueError):
    pass


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise GuardError("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def read_bounded(path: Path, limit: int = 50000) -> bytes:
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise GuardError("INPUT_SIZE_LIMIT")
    return data


def checked_member(name: str, data: bytes) -> bytes:
    expected = PREIMAGES.get(name)
    if expected is None or (len(data), sha(data)) != expected:
        raise GuardError("PREIMAGE_MISMATCH:" + name)
    if name == "assets/lead.js" and (b"971506878663" not in data or b"971568285677" in data):
        raise GuardError("CONTACT_PREIMAGE_MISMATCH")
    return data


def load_inputs(source: Path, installed: Path, audit_path: Path, extra_audit_path: Path | None = None):
    tooling = source.resolve() / "tools/offplan-lead-first/form-localization"
    compiler_path = tooling / "compile_form.py"
    catalog_path = tooling / "translations.json"
    compiler_raw = read_bounded(compiler_path)
    if sha(compiler_raw) != COMPILER_SHA256:
        raise GuardError("COMPILER_DRIFT")
    if sha(read_bounded(catalog_path)) != CATALOG_SHA256:
        raise GuardError("CATALOG_DRIFT")
    # Execute only the hash-pinned tooling without import-loader pycache writes.
    module = ModuleType("pinned_form_text_compiler")
    module.__file__ = str(compiler_path)
    exec(compile(compiler_raw, str(compiler_path), "exec"), module.__dict__)
    catalog = module.load_catalog(catalog_path)
    audit_raw = read_bounded(audit_path)
    audit = json.loads(audit_raw, object_pairs_hook=unique_object)
    members = audit.get("files")
    if not isinstance(members, list) or len(members) != 9:
        raise GuardError("EDITOR_AUDIT_MEMBER_SET")
    indexed = {}
    for member in members:
        if not isinstance(member, dict) or not isinstance(member.get("path"), str) or member["path"] in indexed:
            raise GuardError("EDITOR_AUDIT_MEMBER_SET")
        indexed[member["path"]] = member
    lead = indexed.get("assets/lead.js", {})
    if (lead.get("bytes"), lead.get("sha256")) != PREIMAGES["assets/lead.js"]:
        raise GuardError("CURRENT_EDITOR_LEAD_MISMATCH")
    if audit.get("version_header") != "0.2.12" or audit.get("measurement_controls") != "ALL_OFF" or audit.get("code_saved") is not False:
        raise GuardError("EDITOR_AUDIT_SCOPE_MISMATCH")
    contact = audit.get("lead_contact", {})
    if contact.get("approved8663_present") is not True or contact.get("old5677_absent") is not True:
        raise GuardError("CURRENT_EDITOR_CONTACT_MISMATCH")
    verified = {"assets/lead.js"}
    audit["supplemental_editor_audit_sha256"] = None
    audit["supplemental_editor_observed_at_utc"] = None
    if extra_audit_path is not None:
        extra_raw = read_bounded(extra_audit_path)
        extra = json.loads(extra_raw, object_pairs_hook=unique_object)
        extra_members = extra.get("files")
        if not isinstance(extra_members, list) or extra.get("raw_server_byte_identity_claimed") is not False:
            raise GuardError("SUPPLEMENTAL_EDITOR_SCOPE_MISMATCH")
        extra_paths = []
        for member in extra_members:
            if not isinstance(member, dict) or not isinstance(member.get("path"), str) or member["path"] in extra_paths:
                raise GuardError("SUPPLEMENTAL_EDITOR_MEMBER_SET")
            extra_paths.append(member["path"])
            name = member["path"]
            if name in PREIMAGES:
                if (member.get("bytes"), member.get("sha256")) != PREIMAGES[name]:
                    raise GuardError("SUPPLEMENTAL_EDITOR_PREIMAGE_MISMATCH:" + name)
                verified.add(name)
        if not {"assets/consent-bridge.js", "templates/source/off-plan.html"}.issubset(verified):
            raise GuardError("SUPPLEMENTAL_EDITOR_REQUIRED_MEMBER_MISSING")
        audit["supplemental_editor_audit_sha256"] = sha(extra_raw)
        audit["supplemental_editor_observed_at_utc"] = extra["observed_at_utc"]
    audit["verified_preimage_paths"] = sorted(verified)
    base = installed.resolve()
    files = {}
    for name in PREIMAGES:
        path = (base / name).resolve()
        if not path.is_relative_to(base):
            raise GuardError("INPUT_PATH_ESCAPE")
        files[name] = checked_member(name, read_bounded(path))
    return module, catalog, files, audit, sha(audit_raw)


def resolve_locale(request_target: str) -> str:
    """Pure offline selector; query is never persisted or copied into any URL/config."""
    if not isinstance(request_target, str) or len(request_target) > 4096 or re.search(r"[\x00-\x20\x7f#\\]", request_target):
        return "en"
    path, separator, query = request_target.partition("?")
    if path != INTAKE_PATH or not separator or ";" in query or re.search(r"%(?![0-9A-Fa-f]{2})", query):
        return "en"
    pairs = query.split("&")
    if len(pairs) > 32:
        return "en"
    selected = []
    for pair in pairs:
        key, equal, value = pair.partition("=")
        try:
            decoded = unquote_to_bytes(key.replace("+", " ")).decode("utf-8", errors="strict")
        except UnicodeError:
            return "en"
        if re.search(r"[\x00-\x20\x7f]", decoded):
            return "en"
        if decoded == LOCALE_KEY:
            if key != LOCALE_KEY or not equal:
                return "en"
            selected.append(value)
        elif decoded.startswith(LOCALE_KEY + "[") or decoded.replace(".", "_").replace(" ", "_") == LOCALE_KEY:
            return "en"
    return selected[0] if len(selected) == 1 and selected[0] in LOCALES else "en"


def reverse_js(output: str, edits: list[dict]) -> str:
    positions, delta = [], 0
    for edit in sorted(edits, key=lambda item: item["offset"]):
        positions.append((edit["offset"] + delta, edit["before"], edit["after"]))
        delta += len(edit["after"]) - len(edit["before"])
    result = output
    for offset, before, after in reversed(positions):
        if result[offset:offset + len(after)] != after:
            raise GuardError("INVERSE_SPAN_MISMATCH")
        result = result[:offset] + before + result[offset + len(after):]
    return result


def deployment_rejections(audit: dict) -> list[str]:
    observed = set(audit.get("verified_preimage_paths", []))
    missing = ["CURRENT_PREIMAGE_NOT_VERIFIED:" + name for name in PREIMAGES if name not in observed]
    return missing + [
        "FRESH_SERVED_ASSET_AND_EXECUTED_NATIVE_BYTE_IDENTITY_NOT_PROVEN",
        "MAIN_ENTRYPOINT_AND_NATIVE_INTEGRATION_NOT_BOUND_BY_THIS_DERIVATION",
        "NATIVE_PHP_ROUTE_AND_ASSET_BINDING_NOT_IMPLEMENTED",
        "ACTUAL_LOCALE_PRIVACY_DOCUMENTS_NOT_BOUND",
        "WHOLE_DOCUMENT_AND_CONSENT_PANEL_LANGUAGE_NOT_BOUND",
        "COMPETENT_COPY_STAFF_LANGUAGE_AND_HUMAN_REVIEW_PENDING",
        "CURRENT_NATIVE_AND_GENUINE_INTAKE_ACCEPTANCE_PENDING",
        "TAIWAN_COUNTRY_APPLICABILITY_REMAINS_HELD",
    ]


def build_outputs(source: Path, installed: Path, audit_path: Path, extra_audit_path: Path | None = None) -> dict[str, bytes]:
    module, catalog, files, audit, audit_sha = load_inputs(source, installed, audit_path, extra_audit_path)
    result, inverses = {}, {}
    for locale in LOCALES:
        strings = catalog["locales"][locale]
        if len(strings) != 85:
            raise GuardError("CATALOG_STRING_COUNT")
        result[locale + "/form.html"] = module.localize_form(files["templates/source/off-plan.html"].decode("utf-8"), strings, locale).encode("utf-8")
        for group, name in (("lead", "lead.js"), ("consent", "consent-bridge.js")):
            original = files["assets/" + name]
            output, changes = module.localize_js(original.decode("utf-8"), group, strings)
            edits = [{"offset": offset, "before": before, "after": after} for offset, before, after in changes]
            if reverse_js(output, edits).encode("utf-8") != original:
                raise GuardError("INVERSE_PREIMAGE_MISMATCH")
            if name == "lead.js" and ("971568285677" in output or output.count("971506878663") != original.decode("utf-8").count("971506878663")):
                raise GuardError("CONTACT_DERIVATION_MISMATCH")
            key = locale + "/" + name
            result[key] = output.encode("utf-8")
            inverses[key] = {"preimage_sha256": sha(original), "output_sha256": sha(result[key]), "edits": edits}
        result[locale + "/template-strings.json"] = json_bytes({key: strings["template." + key] for key in module.TEMPLATE_KEYS})
    result["JS_TEXT_INVERSES.json"] = json_bytes(inverses)
    result["LOCALE_SELECTION.json"] = json_bytes({
        "implementation": "derive_localization.py::resolve_locale - offline pure function, not an installed WordPress hook",
        "existing_intake_path": INTAKE_PATH, "query_key": LOCALE_KEY, "allowlisted_locales": list(LOCALES),
        "default_and_invalid_locale": "en", "query_persistence": False,
        "data_landing_path": INTAKE_PATH, "canonical_intake_path_changed": False,
        "privacy_or_endpoint_query_binding": False, "dynamic_URL_or_remote_asset_generation": False,
    })
    result["DEPLOYMENT_REJECTIONS.json"] = json_bytes({"deployment_allowed": False, "reasons": deployment_rejections(audit)})
    result["MANIFEST.json"] = json_bytes({
        "schema": "bsre-installed-preimage-localization-candidate-v1", "status": "PRIVATE_INERT_CANDIDATE_NOT_INSTALLABLE",
        "derivation_script_sha256": sha(Path(__file__).read_bytes()),
        "compiler_sha256": COMPILER_SHA256, "catalog_sha256": CATALOG_SHA256, "editor_audit_sha256": audit_sha,
        "supplemental_editor_audit_sha256": audit["supplemental_editor_audit_sha256"],
        "supplemental_editor_observed_at_utc": audit["supplemental_editor_observed_at_utc"],
        "editor_representation": audit["method"], "editor_representation_limit": audit["representation_limit"],
        "editor_observed_at_utc": audit["observed_at_utc"],
        "preimages": {name: {"bytes": len(data), "sha256": sha(data), "current_editor_bound": name in audit["verified_preimage_paths"]} for name, data in files.items()},
        "locales": list(LOCALES), "strings_per_locale": 85, "all_client_text_edits_reversible_to_exact_preimage": True,
        "approved_contact_digits": "971506878663", "old_contact_digits_absent_from_derived_lead_clients": True,
        "preview_form_disabled_fieldset_retained": True, "live_PHP_integration_implemented": False,
        "installed": False, "live_verified": False, "production_write": False, "measurement_controls_changed": False,
        "output_sha256": {name: sha(data) for name, data in result.items()},
    })
    return result


def safe_output_path(path: Path, ownership_root: Path, source_root: Path) -> Path:
    target = path.resolve()
    scope = ownership_root.resolve()
    if target == scope or not target.is_relative_to(scope):
        raise GuardError("OUTPUT_OUTSIDE_PRIVATE_OWNERSHIP")
    if target.is_relative_to(source_root.resolve()):
        raise GuardError("OUTPUT_INSIDE_SOURCE")
    return target


def write_or_check(target: Path, outputs: dict[str, bytes], check: bool, ownership_root: Path, source_root: Path) -> None:
    target = safe_output_path(target, ownership_root, source_root)
    if check:
        if any(path.is_symlink() for path in target.rglob("*")):
            raise GuardError("OUTPUT_SYMLINK_MEMBER")
        actual = {str(path.relative_to(target)).replace("\\", "/") for path in target.rglob("*") if path.is_file()}
        if actual != set(outputs) or any((target / name).read_bytes() != data for name, data in outputs.items()):
            raise GuardError("OUTPUT_INVENTORY_OR_BYTES_MISMATCH")
        return
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise GuardError("OUTPUT_ALREADY_POPULATED_CHECK_BEFORE_RETRY")
    target.mkdir(parents=True, exist_ok=True)
    for name, data in outputs.items():
        destination = (target / name).resolve()
        if not destination.is_relative_to(target):
            raise GuardError("OUTPUT_MEMBER_ESCAPE")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as stream:
            stream.write(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--installed-root", type=Path)
    parser.add_argument("--editor-audit", type=Path)
    parser.add_argument("--extra-editor-audit", type=Path)
    parser.add_argument("--output-scope", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--resolve-target")
    args = parser.parse_args()
    if args.resolve_target is not None:
        if args.out is not None or args.check:
            parser.error("selector cannot be combined with artifact output")
        print(json.dumps({"locale": resolve_locale(args.resolve_target), "scope": "OFFLINE_SELECTOR_NOT_WP_HOOK"}))
        return
    if any(value is None for value in (args.out, args.source_root, args.installed_root, args.editor_audit, args.output_scope)):
        parser.error("derivation requires --source-root, --installed-root, --editor-audit, --output-scope and --out")
    safe_output_path(args.out, args.output_scope, args.source_root)
    outputs = build_outputs(args.source_root, args.installed_root, args.editor_audit, args.extra_editor_audit)
    write_or_check(args.out, outputs, args.check, args.output_scope, args.source_root)
    print(json.dumps({"status": "PASS_OFFLINE_ONLY", "files": len(outputs), "locales": len(LOCALES), "strings_per_locale": 85, "check": args.check, "deployment_allowed": False}))


if __name__ == "__main__":
    try:
        main()
    except GuardError as error:
        raise SystemExit(str(error)) from None

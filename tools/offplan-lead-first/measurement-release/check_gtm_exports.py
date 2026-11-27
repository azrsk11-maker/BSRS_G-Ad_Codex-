"""Verify the owned-funnel GTM export pair offline against a pinned capture."""

from argparse import ArgumentParser
from datetime import datetime
from hashlib import file_digest, sha256
import json
from pathlib import Path
import re


PUBLIC_ID = "GTM-NW8WXKRF"
CONTAINER_NAME = "BSRE Owned Funnels | blackswanrealestate.ae"
LIVE_VERSION_ID = "1"
DRAFT_WORKSPACE_ID = "2"
# The UI's workspace export uses the synthetic version ID 0. The pinned
# capture provides the workspace selection which that export does not encode.
DRAFT_EXPORT_VERSION_ID = "0"
TAG_ID = "4"
TRIGGER_ID = "3"
CANDIDATE_SHA256 = "4e62a282828eef4748394b33f211277a59e901135c7c4800e42f7ec02a7edfd3"
CAPTURE_SCOPE = "OFFPLAN_GTM_NATIVE_EXPORT_CAPTURE"
CAPTURE_FIELDS = {
    "scope", "account_id", "container_id", "public_id", "live_version_id", "draft_workspace_id",
    "live_export_sha256", "draft_export_sha256", "candidate_zip_sha256",
}
BOOTSTRAP = (
    "<script>\n"
    "if (window.BSREGoogleRuntime && typeof window.BSREGoogleRuntime.activate === 'function') {\n"
    "  window.BSREGoogleRuntime.activate();\n"
    "}\n"
    "</script>\n"
)
BUILT_INS = {
    "PAGE_URL": "Page URL",
    "PAGE_HOSTNAME": "Page Hostname",
    "PAGE_PATH": "Page Path",
    "REFERRER": "Referrer",
    "EVENT": "Event",
}
EMPTY_COLLECTIONS = {"variable", "folder", "zone", "customTemplate", "client", "gtagConfig", "transformation"}
FEATURES = {
    "supportUserPermissions": True,
    "supportEnvironments": True,
    "supportWorkspaces": True,
    "supportGtagConfigs": False,
    "supportBuiltInVariables": True,
    "supportClients": False,
    "supportFolders": True,
    "supportTags": True,
    "supportTemplates": True,
    "supportTriggers": True,
    "supportVariables": True,
    "supportVersions": True,
    "supportZones": True,
    "supportTransformations": False,
}
MAX_JSON_BYTES = 256 * 1024


class VerificationError(ValueError):
    """A fixed, sanitized verification failure."""


def require(condition, message):
    if not condition:
        raise VerificationError(message)


def object_with_unique_keys(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON object key")
        result[key] = value
    return result


def reject_json_constant(_):
    raise VerificationError("non-standard JSON constant")


def read_json(path):
    with path.open("rb") as stream:
        raw = stream.read(MAX_JSON_BYTES + 1)
    require(len(raw) <= MAX_JSON_BYTES, "JSON exceeds the export size limit")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=object_with_unique_keys,
                           parse_constant=reject_json_constant)
    except VerificationError:
        raise
    except (ValueError, RecursionError):
        raise VerificationError("invalid UTF-8 JSON") from None
    require(isinstance(value, dict), "expected a JSON object")
    return value, sha256(raw).hexdigest()


def check_fields(value, required, optional=()):
    require(isinstance(value, dict) and required <= value.keys()
            and value.keys() <= required.union(optional), "unexpected GTM fields")


def numeric_id(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9]+", value) is not None


def check_identity(value, capture):
    require(value["accountId"] == capture["account_id"] and value["containerId"] == capture["container_id"],
            "GTM account or container mismatch")


def check_fingerprint(value):
    require(numeric_id(value["fingerprint"]), "invalid GTM fingerprint")


def check_container(container, capture, path, url):
    check_fields(container, {
        "accountId", "containerId", "path", "name", "publicId", "usageContext",
        "fingerprint", "tagManagerUrl", "tagIds", "features",
    })
    check_identity(container, capture)
    check_fingerprint(container)
    require(container["path"] == path and container["tagManagerUrl"] == url
            and container["name"] == CONTAINER_NAME and container["usageContext"] == ["WEB"]
            and container["publicId"] == PUBLIC_ID and container["tagIds"] == [PUBLIC_ID],
            "unexpected owned web container metadata")
    features = container["features"]
    require(isinstance(features, dict) and features == FEATURES
            and all(type(value) is bool for value in features.values()), "unexpected container features")


def check_built_ins(variables, capture):
    require(isinstance(variables, list) and len(variables) == len(BUILT_INS),
            "unexpected built-in variable count")
    types = set()
    for variable in variables:
        check_fields(variable, {"accountId", "containerId", "name", "type"})
        check_identity(variable, capture)
        variable_type = variable["type"]
        require(isinstance(variable_type, str) and variable_type not in types
                and variable_type in BUILT_INS and variable["name"] == BUILT_INS[variable_type],
                "unexpected built-in variable")
        types.add(variable_type)


def check_draft_entities(tags, triggers, capture):
    require(isinstance(tags, list) and len(tags) == 1 and isinstance(triggers, list)
            and len(triggers) == 1, "expected exactly one draft tag and trigger")
    tag, trigger = tags[0], triggers[0]
    check_fields(trigger, {"accountId", "containerId", "triggerId", "name", "type", "fingerprint"})
    check_identity(trigger, capture)
    check_fingerprint(trigger)
    require(trigger["triggerId"] == TRIGGER_ID and trigger["name"] == "BSRE | Runtime pageview"
            and trigger["type"] == "PAGEVIEW", "unexpected draft page-view trigger")

    check_fields(tag, {
        "accountId", "containerId", "tagId", "name", "type", "parameter", "fingerprint",
        "firingTriggerId", "tagFiringOption", "consentSettings",
    })
    check_identity(tag, capture)
    check_fingerprint(tag)
    require(tag["tagId"] == TAG_ID and tag["name"] == "BSRE | Reviewed local runtime bootstrap"
            and tag["type"] == "html" and tag["firingTriggerId"] == [trigger["triggerId"]]
            and tag["tagFiringOption"] == "ONCE_PER_LOAD"
            and tag["consentSettings"] == {"consentStatus": "NOT_NEEDED"},
            "unexpected draft bootstrap or firing options")
    params = tag["parameter"]
    require(isinstance(params, list) and len(params) == 2, "unexpected custom HTML parameters")
    for param in params:
        check_fields(param, {"type", "key", "value"})
        require(isinstance(param["key"], str), "invalid custom HTML parameter key")
    require({param["key"]: (param["type"], param["value"]) for param in params}
            == {"html": ("TEMPLATE", BOOTSTRAP), "supportDocumentWrite": ("BOOLEAN", "false")},
            "custom HTML differs from the guarded reviewed bootstrap")


def check_export(export, capture, *, draft, published_version_id=None):
    check_fields(export, {"exportFormatVersion", "exportTime", "containerVersion"})
    require(type(export["exportFormatVersion"]) is int and export["exportFormatVersion"] == 2,
            "unsupported GTM export format")
    try:
        datetime.strptime(export["exportTime"], "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        raise VerificationError("invalid GTM export time") from None

    version = export["containerVersion"]
    check_fields(version, {
        "accountId", "containerId", "containerVersionId", "path", "container",
        "builtInVariable", "fingerprint", "tagManagerUrl",
    }, EMPTY_COLLECTIONS | {"name", "description", "deleted", "tag", "trigger"})
    check_identity(version, capture)
    check_fingerprint(version)
    if published_version_id is not None:
        require(not draft and isinstance(published_version_id, str)
                and re.fullmatch(r"(?:[2-9]|[1-9][0-9]+)", published_version_id),
                "published bootstrap must have a real version after the empty rollback version")
    version_id = published_version_id or (DRAFT_EXPORT_VERSION_ID if draft else LIVE_VERSION_ID)
    account_id = capture["account_id"]
    container_id = capture["container_id"]
    path = f"accounts/{account_id}/containers/{container_id}"
    version_path = f"{path}/versions/{version_id}"
    ui = "https://tagmanager.google.com/#"
    require(version["containerVersionId"] == version_id and version["path"] == version_path
            and version["tagManagerUrl"] == f"{ui}/versions/{version_path}?apiLink=version",
            "unexpected GTM export version identity")
    valid_name = (isinstance(version.get("name", ""), str) if published_version_id is not None
                  else version.get("name") == (None if draft else "Empty Container"))
    require(valid_name
            and version.get("deleted", False) is False
            and isinstance(version.get("description", ""), str),
            "unexpected GTM export version metadata")
    check_container(version["container"], capture, path, f"{ui}/container/{path}/workspaces?apiLink=container")
    check_built_ins(version["builtInVariable"], capture)
    require(all(version.get(key, []) == [] for key in EMPTY_COLLECTIONS), "unexpected GTM objects")
    tags = version.get("tag", [])
    triggers = version.get("trigger", [])
    if draft or published_version_id is not None:
        check_draft_entities(tags, triggers, capture)
    else:
        require(tags == [] and triggers == [], "rollback contains tags or triggers")
    return {"tags": len(tags), "triggers": len(triggers), "built_in_variables": len(BUILT_INS)}


def read_capture(checkpoint, checkpoint_sha256):
    capture, capture_sha256 = read_json(checkpoint)
    require(capture_sha256 == checkpoint_sha256.lower(), "capture checkpoint SHA-256 mismatch")
    require(capture.keys() == CAPTURE_FIELDS and capture["scope"] == CAPTURE_SCOPE
            and capture["public_id"] == PUBLIC_ID and numeric_id(capture["account_id"])
            and numeric_id(capture["container_id"]) and capture["live_version_id"] == LIVE_VERSION_ID
            and capture["draft_workspace_id"] == DRAFT_WORKSPACE_ID, "unexpected capture checkpoint")
    return capture, capture_sha256


def verify_exports(live_path, draft_path, candidate_zip, checkpoint, checkpoint_sha256):
    capture, capture_sha256 = read_capture(checkpoint, checkpoint_sha256)
    with candidate_zip.open("rb") as stream:
        candidate_sha256 = file_digest(stream, "sha256").hexdigest()
    require(candidate_sha256 == capture["candidate_zip_sha256"] == CANDIDATE_SHA256,
            "reviewed candidate ZIP SHA-256 mismatch")
    live, live_sha256 = read_json(live_path)
    draft, draft_sha256 = read_json(draft_path)
    require(live_sha256 == capture["live_export_sha256"] and draft_sha256 == capture["draft_export_sha256"],
            "native export SHA-256 mismatch")
    return {
        "status": "OFFLINE_EXPORT_CONTENT_VERIFIED",
        "public_id": PUBLIC_ID,
        "candidate_zip_sha256": candidate_sha256,
        "checkpoint_sha256": capture_sha256,
        "rollback": {"sha256": live_sha256, **check_export(live, capture, draft=False)},
        "draft": {"sha256": draft_sha256, **check_export(draft, capture, draft=True)},
        "provider_state_checked_here": False,
        "publication_authorized": False,
    }


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("rollback_export", type=Path)
    parser.add_argument("draft_export", type=Path)
    parser.add_argument("--candidate-zip", required=True, type=Path)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--checkpoint-sha256", required=True, help="trusted capture checkpoint SHA-256")
    args = parser.parse_args()
    try:
        result = verify_exports(args.rollback_export, args.draft_export, args.candidate_zip,
                                args.checkpoint, args.checkpoint_sha256)
    except VerificationError as error:
        parser.exit(1, f"Verification failed. {error}.\n")
    except OSError:
        parser.exit(1, "Verification failed. An input could not be read.\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

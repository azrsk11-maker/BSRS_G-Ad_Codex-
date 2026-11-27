"""Build and verify the same current negative research from fresh inputs."""

import hashlib
import importlib
import json
from pathlib import Path

import append_only_admission as append
import current_negative_library as reference
import negative_admission as first


STAGES = (
    "ofqual_admission", "entertainment_admission", "apprenticeship_admission",
    "ofqual_occupational_admission", "ofqual_veterinary_admission", "bank_credential_admission",
    "bank_support_admission", "ofqual_animal_care_admission", "bank_channel_login_admission",
    "front_office_document_admission", "septic_grease_admission", "trade_services_admission",
    "pest_commercial_services_admission", "pool_sprinkler_admission",
)
SOURCE_MODULES = (
    "current_negative_library", "append_only_admission", "negative_admission",
    "negative_library", "keyword_audit", *STAGES,
)
SOURCE_SHA256 = "a0ceed4bcdfee3ca20db7f358e065af72d3c481d807cc44606381f01ef99de44"


def reviewed_sources_match(folder):
    signature = hashlib.sha256()
    try:
        for name in SOURCE_MODULES:
            path = folder / f"{name}.py"
            if path.resolve(strict=True) != path:
                return False
            signature.update(name.encode("ascii") + b"\0")
            signature.update(hashlib.sha256(path.read_bytes()).digest())
    except (OSError, RuntimeError):
        return False
    return signature.hexdigest() == SOURCE_SHA256


def verify(root=first.ROOT, at=None):
    """Verify every saved stage before passing freshly generated inputs onward."""
    root = Path(root).resolve()
    if root != first.ROOT or not reviewed_sources_match(root / "tools/keyword-system"):
        return reference.verify(root, at)
    when = first.dubai_date() if at is None else at
    inputs = reference.reconstruct_valuation_snapshot(root, at=when)
    # Each builder performs the full prefix, source, review and research audit.
    # Its pinned index binds the complete generated inputs for this stage.
    for name in STAGES:
        stage = importlib.import_module(name)
        inputs, documents = stage.build_outputs(inputs, root, when)
        append.check_documents(root, stage.FOLDER, stage.OUTPUT_PINS, documents)
    return dict(documents["library-report.json"], as_of=when.isoformat())


if __name__ == "__main__":
    try:
        print(json.dumps(verify()))
    except Exception:
        print(json.dumps({"passed": False, "scope": "CURRENT_RESEARCH_LIBRARY_HELD",
                          "deployment_export_allowed": False, "production_writes_available": False}))
        raise SystemExit(1)

"""Compare a pinned GTM Versions live readback with its native version export."""

from argparse import ArgumentParser
from datetime import datetime
import json
from pathlib import Path

from check_gtm_exports import PUBLIC_ID, VerificationError, check_export, read_capture, read_json, require


OBSERVATION_SCOPE = "BSRE_OFFPLAN_GTM_VERSIONS_LIVE_READBACK"
OBSERVATION_FIELDS = {
    "scope", "account_id", "container_id", "public_id", "observed_at_utc",
    "live_version_id", "live_export_sha256",
}


def verify_publication(live_export, observation, observation_sha256, original_capture, original_sha256):
    capture, _ = read_capture(original_capture, original_sha256)
    live, observed_sha256 = read_json(observation)
    require(observed_sha256 == observation_sha256.lower(), "live observation SHA-256 mismatch")
    require(live.keys() == OBSERVATION_FIELDS and live["scope"] == OBSERVATION_SCOPE
            and all(live[key] == capture[key] for key in ("account_id", "container_id", "public_id")),
            "live observation scope or container identity differs")
    try:
        datetime.strptime(live["observed_at_utc"], "%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        raise VerificationError("invalid live observation UTC time") from None

    export, export_sha256 = read_json(live_export)
    require(export_sha256 == live["live_export_sha256"], "live export SHA-256 mismatch")
    require(isinstance(live["live_version_id"], str), "invalid observed live version ID")
    counts = check_export(export, capture, draft=False, published_version_id=live["live_version_id"])
    return {
        "status": "MATCHED_PUBLISHED_BOOTSTRAP_EXPORT",
        "public_id": PUBLIC_ID,
        "live_version_id": live["live_version_id"],
        "observed_at_utc": live["observed_at_utc"],
        "live_export_sha256": export_sha256,
        **counts,
        "provider_live_status_independently_checked": False,
        "provider_conversion_verified": False,
        "activation_authorized": False,
    }


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("live_export", type=Path)
    parser.add_argument("live_observation", type=Path)
    parser.add_argument("observation_sha256")
    parser.add_argument("original_capture", type=Path)
    parser.add_argument("original_sha256")
    args = parser.parse_args()
    try:
        result = verify_publication(args.live_export, args.live_observation, args.observation_sha256,
                                    args.original_capture, args.original_sha256)
    except (OSError, TypeError, ValueError, KeyError) as error:
        reason = str(error) if isinstance(error, VerificationError) else "invalid readback inputs"
        print(json.dumps({"status": "HOLD", "activation_authorized": False, "reason": reason}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

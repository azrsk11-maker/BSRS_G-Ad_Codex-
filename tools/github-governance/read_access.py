"""Read this project's Git-client access without exposing credentials or changing access."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

REPOSITORY = "azrsk11-maker/BSRS_G-Ad_Codex-"
ROOT = Path(__file__).resolve().parents[2]
ACCOUNT = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})\Z")
PERMISSIONS = ("pull", "push", "triage", "maintain", "admin")


class AccessError(Exception):
    """Only constant, credential-free diagnostic codes cross the CLI boundary."""


def git(root, arguments, *, credential_input=None):
    env = os.environ.copy()
    env.update(GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never")
    # A cache miss must not launch another prompt or execute an askpass helper.
    env.pop("GIT_ASKPASS", None)
    env.pop("SSH_ASKPASS", None)
    for key in list(env):
        if key.startswith(("GIT_TRACE", "GCM_TRACE")) or key == "GIT_CURL_VERBOSE":
            env.pop(key, None)
    try:
        return subprocess.run(
            ["git", "-c", "credential.interactive=never", "-c", "core.askPass=", *arguments],
            cwd=root, input=credential_input, capture_output=True, text=True,
            env=env, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        raise AccessError("GIT_READ_UNAVAILABLE") from None


def read_credential(root, account):
    if not isinstance(account, str) or not ACCOUNT.fullmatch(account):
        raise AccessError("INVALID_ACCOUNT")
    origin = git(root, ["remote", "get-url", "origin"])
    if origin.returncode:
        raise AccessError("ORIGIN_UNAVAILABLE")
    try:
        url = urllib.parse.urlsplit(origin.stdout.strip())
        port = url.port
    except ValueError:
        raise AccessError("ORIGIN_OUTSIDE_APPROVED_REPOSITORY") from None
    path = url.path.removesuffix(".git").strip("/")
    if (url.scheme != "https" or url.hostname != "github.com" or port is not None
            or url.username is not None or url.password is not None
            or url.query or url.fragment or path.casefold() != REPOSITORY.casefold()):
        raise AccessError("ORIGIN_OUTSIDE_APPROVED_REPOSITORY")
    result = git(root, ["credential", "fill"], credential_input=(
        "protocol=https\nhost=github.com\nusername=" + account + "\n\n"))
    if result.returncode:
        raise AccessError("GIT_CREDENTIAL_UNAVAILABLE")
    fields = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    secret = fields.get("password")
    if not secret:
        raise AccessError("GIT_CREDENTIAL_UNAVAILABLE")
    return secret


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def transport(secret):
    opener = urllib.request.build_opener(NoRedirect())
    allowed = {"/user", "/repos/" + REPOSITORY, "/user/repository_invitations?per_page=100"}

    def get(path):
        if path not in allowed:
            raise AccessError("ENDPOINT_OUTSIDE_APPROVED_SCOPE")
        request = urllib.request.Request("https://api.github.com" + path, headers={
            "Authorization": "Bearer " + secret, "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28", "Cache-Control": "no-cache",
            "User-Agent": "BSRE-Read-Only-Access-Check",
        })
        try:
            with opener.open(request, timeout=20) as response:
                raw = response.read(1_048_577)
                if len(raw) > 1_048_576:
                    raise AccessError("API_RESPONSE_TOO_LARGE")
                return response.status, json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as error:
            # Never emit response bodies, URLs or credential-helper output.
            return error.code, None
        except (OSError, ValueError):
            raise AccessError("API_READ_UNAVAILABLE") from None
    return get


def inspect_access(account, api, *, invitations=False):
    if not isinstance(account, str) or not ACCOUNT.fullmatch(account):
        raise AccessError("INVALID_ACCOUNT")
    calls = 1
    status, profile = api("/user")
    if status != 200 or not isinstance(profile, dict):
        raise AccessError("AUTHENTICATED_PROFILE_UNAVAILABLE")
    login = profile.get("login")
    if not isinstance(login, str) or login.casefold() != account.casefold():
        raise AccessError("AUTHENTICATED_ACCOUNT_MISMATCH")
    calls += 1
    status, repo = api("/repos/" + REPOSITORY)
    if status != 200 or not isinstance(repo, dict):
        raise AccessError("REPOSITORY_READ_UNAVAILABLE")
    if str(repo.get("full_name", "")).casefold() != REPOSITORY.casefold():
        raise AccessError("REPOSITORY_IDENTITY_MISMATCH")
    permissions = repo.get("permissions")
    if not isinstance(permissions, dict) or any(type(permissions.get(k)) is not bool for k in PERMISSIONS):
        raise AccessError("REPOSITORY_PERMISSIONS_UNVERIFIED")
    report = {"repository": REPOSITORY, "authenticated_login": login,
              "status": "WRITE_ACCESS_VERIFIED" if permissions["push"] else "WRITE_ACCESS_MISSING",
              "permissions": {k: permissions[k] for k in PERMISSIONS}, "api_calls": calls}
    if invitations:
        calls += 1
        status, rows = api("/user/repository_invitations?per_page=100")
        report["invitation_read_status"] = status
        if status == 200 and isinstance(rows, list):
            matching = [r for r in rows if isinstance(r, dict) and isinstance(r.get("repository"), dict)
                        and str(r["repository"].get("full_name", "")).casefold() == REPOSITORY.casefold()]
            report["matching_invitations_on_first_page"] = len(matching)
            # A full page cannot prove absence on subsequent pages.
            report["invitation_inventory_complete"] = len(rows) < 100
        else:
            report["invitation_inventory_complete"] = False
        report["api_calls"] = calls
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", required=True, help="Expected GitHub username, not email")
    parser.add_argument("--invitations", action="store_true", help="Read first invitation page; expose only target counts")
    args = parser.parse_args(argv)
    started = time.perf_counter()
    try:
        report = inspect_access(args.account, transport(read_credential(ROOT, args.account)), invitations=args.invitations)
        result = 0 if report["permissions"]["push"] else 1
    except AccessError as error:
        report = {"repository": REPOSITORY, "status": "ACCESS_UNVERIFIED", "error": str(error)}
        result = 2
    report["elapsed_seconds"] = round(time.perf_counter() - started, 6)
    print(json.dumps(report, sort_keys=True))
    return result


if __name__ == "__main__":
    raise SystemExit(main())

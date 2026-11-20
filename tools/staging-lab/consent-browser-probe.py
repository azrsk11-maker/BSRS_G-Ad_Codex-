"""Local synthetic Chrome check. No production origins, credentials or writes."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import ssl
import subprocess
from tempfile import TemporaryDirectory
import time
import threading
from trusted_loopback_tls import server_context, verify_loopback_tls


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--chrome", type=Path, required=True, help="Path to an installed Chrome executable")
parser.add_argument("--tls-cert", type=Path, required=True, help="Supplied certificate chain normally trusted by Chrome and the OS")
parser.add_argument("--tls-key", type=Path, required=True, help="Private key for the supplied test certificate; never commit")
parser.add_argument("--withdrawal-outage", action="store_true")
parser.add_argument("--narrow", action="store_true")
args = parser.parse_args()
if not args.chrome.is_file():
    parser.error("--chrome must point to an existing executable")
tls = server_context(args.tls_cert, args.tls_key)
root = Path(__file__).resolve().parent
bridge = (root / "fixtures/bsre-enquiries/assets/consent-bridge.js").read_bytes()
stylesheet = (root / "fixtures/bsre-enquiries/assets/consent.css").read_bytes()
scenario = (root / "consent-browser-probe.js").read_bytes()
fail_withdrawal = args.withdrawal_outage
html = b'<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/consent.css"><body><script defer src="/config.js"></script><script defer src="/bridge.js"></script><script defer src="/test.js"></script>'
config = b'window.BSRETrackingConfig={cmpProviderId:"bsre_first_party_v1",consentContextEndpoint:location.origin+"/context",consentUpdateEndpoint:location.origin+"/update"};'
if fail_withdrawal:
    config += b"window.BSREProbeWithdrawalOutage=true;"
if args.narrow:
    config += b"window.BSREProbeNarrow=true;"
result = {}
withdrawal_failure_sent = False


class Fixture(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, data, kind, cookie=None):
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; base-uri 'none'")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        assets = {"/browser": (html, "text/html"), "/browser-return": (html, "text/html"), "/browser-pending": (html, "text/html"),
                  "/browser-peer": (html, "text/html"),
                  "/config.js": (config, "text/javascript"), "/bridge.js": (bridge, "text/javascript"),
                  "/consent.css": (stylesheet, "text/css"),
                  "/test.js": (scenario, "text/javascript")}
        if self.path in assets:
            self.send(*assets[self.path])
        else:
            self.send_error(404)

    def do_POST(self):
        global withdrawal_failure_sent
        if self.headers.get("Origin") != origin:
            self.send_error(403)
            return
        data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path == "/browser-result":
            result.update(data)
            self.send(b"{}", "application/json")
            return
        cookie = self.headers.get("Cookie", "")
        choice = "ad" if "__Host-bsre_consent=ad" in cookie else "denied" if "__Host-bsre_consent=denied" in cookie else None
        new_cookie = None
        if self.path == "/update":
            if fail_withdrawal and choice == "ad" and not data["ad_measurement"] and not withdrawal_failure_sent:
                withdrawal_failure_sent = True
                self.send_error(503)
                return
            choice = "ad" if data["ad_measurement"] else "denied"
            new_cookie = f"__Host-bsre_consent={choice}; Secure; HttpOnly; SameSite=Strict; Path=/"
        now = int(time.time())
        snapshot = dict(known=bool(choice), acknowledged=bool(choice), measurement_eligible=True,
                        preferences=dict(analytics=False, ad_measurement=choice == "ad", personalization=False),
                        decision_version=choice or "none", notice_version="TEST_ONLY",
                        preference_expires_at=now + 3600 if choice else 0, preference_days=180,
                        csrf_token=f"cc1|{now}|" + "a" * 64, expires_in=7200)
        self.send(json.dumps(snapshot).encode(), "application/json", new_cookie)


with TemporaryDirectory(prefix="bsre-browser-fixture-") as temp:
    directory = Path(temp)
    with ThreadingHTTPServer(("127.0.0.1", 0), Fixture) as server:
        origin = f"https://127.0.0.1:{server.server_port}"
        server.socket = tls.wrap_socket(server.socket, server_side=True)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            verify_loopback_tls(server.server_port)
        except Exception:
            server.shutdown()
            worker.join(timeout=3)
            raise
        command = [str(args.chrome.resolve()), "--headless", "--disable-popup-blocking",
                f"--user-data-dir={directory / 'profile'}", "--disable-background-networking",
                "--disable-quic", "--proxy-server=http://127.0.0.1:1", "--no-first-run"]
        if args.narrow:
            command.extend(["--window-size=500,700", "--force-device-scale-factor=1.5"])
        command.append(origin + "/browser")
        try:
            with subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) as browser:
                try:
                    deadline = time.monotonic() + 20
                    while not result and browser.poll() is None and time.monotonic() < deadline:
                        time.sleep(0.05)
                finally:
                    if browser.poll() is None:
                        browser.terminate()
                    browser.wait(timeout=5)
        finally:
            server.shutdown()
            worker.join(timeout=3)
    print(json.dumps(result or {"status": "NO_RESULT"}))
    if result.get("status") != "PASS" or (fail_withdrawal and not withdrawal_failure_sent):
        raise SystemExit(1)

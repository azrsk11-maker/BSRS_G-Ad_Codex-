"""Exercise the reviewed off-plan frame transport in Chrome on loopback HTTPS."""

from argparse import ArgumentParser
from base64 import b64encode
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from html import unescape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ipaddress import ip_address
import json
from pathlib import Path
import re
import ssl
from subprocess import CREATE_NO_WINDOW, run
from tempfile import TemporaryDirectory
from threading import Thread
from time import perf_counter
from urllib.parse import parse_qs, urlsplit

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa


CASES = {
    "canonical": ("/enquire/off-plan/", True, False, False),
    "german_query": ("/enquire/off-plan/", True, False, False),
    "india_bound": ("/off-plan-dubai-en-in/", True, True, False),
    "india_unbound": ("/off-plan-dubai-en-in/", True, False, False),
    "resale": ("/enquire/resale/", True, False, False),
    "refusal": ("/enquire/off-plan/", False, False, False),
    "no_frame_referrer": ("/enquire/off-plan/", True, False, True),
}
RUNTIME = "/wp-json/bsre/v1/measurement/runtime"


def loopback_tls(directory):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(timezone.utc)
    name = x509.Name([x509.NameAttribute(x509.NameOID.COMMON_NAME, "127.0.0.1")])
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(hours=1))
            .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ip_address("127.0.0.1"))]), False)
            .sign(key, hashes.SHA256()))
    cert_path, key_path = directory / "loopback.crt", directory / "loopback.key"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert_path, key_path)
    public = key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return ctx, b64encode(sha256(public).digest()).decode("ascii")


class Fixture(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def respond(self, body, content_type="text/html; charset=utf-8", policy=None, referrer=None, status=200):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if policy:
            self.send_header("Content-Security-Policy", policy)
        if referrer:
            self.send_header("Referrer-Policy", referrer)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlsplit(self.path)
        self.server.paths.append(url.path)
        origin = f"https://127.0.0.1:{self.server.server_port}"
        if url.path == "/":
            frames = "".join(f'<iframe src="{entry[0]}?fixture={name}{"&bsre_locale=de-DE" if name == "german_query" else ""}"></iframe>'
                             for name, entry in CASES.items())
            return self.respond(("<!doctype html><body><pre id='result'></pre>"
                "<script>const results={};addEventListener('message',e=>{if(e.origin!==location.origin||!e.data.fixture)return;"
                "results[e.data.fixture]=e.data.result;document.querySelector('#result').textContent=JSON.stringify(results);});</script>"
                + frames).encode())
        if url.path == "/candidate.js":
            return self.respond(self.server.candidate, "text/javascript")
        if url.path == "/no-frame-referrer.js":
            source = self.server.candidate.replace(b"frame.referrerPolicy = 'origin';", b"frame.referrerPolicy = 'no-referrer';", 1)
            return self.respond(source, "text/javascript")
        if url.path == RUNTIME:
            params = parse_qs(url.query)
            check = {
                "origin_only_referer": self.headers.get("Referer") == origin + "/",
                "same_origin": self.headers.get("Sec-Fetch-Site") == "same-origin",
                "iframe": self.headers.get("Sec-Fetch-Dest") == "iframe",
                "fixed_scope_and_purpose": params == {"scope": ["off-plan"], "purpose": ["advertising"]},
            }
            self.server.observations.append(check)
            if not all(check.values()):
                return self.respond(b"denied", status=403)
            frame = """<!doctype html><script nonce="test-fixture">
            addEventListener('message', e => {
              if (e.origin !== location.origin || e.source !== parent || e.data?.type !== 'bsre-runtime-init') return;
              parent.postMessage({type:'bsre-runtime-active',version:'1.0.0',purpose:'advertising',nonce:e.data.nonce},location.origin);
            });
            parent.postMessage({type:'bsre-runtime-ready',version:'1.0.0',purpose:'advertising'},location.origin);
            </script>"""
            return self.respond(frame.encode(), policy="default-src 'none'; frame-ancestors 'self'; script-src 'nonce-test-fixture'", referrer="origin")

        name = parse_qs(url.query).get("fixture", [""])[0]
        if name not in CASES or CASES[name][0] != url.path:
            return self.respond(b"not found", status=404)
        _, allowed, india, negative = CASES[name]
        config = {"enabled": True, "advertising_enabled": True, "runtime_endpoint": origin + RUNTIME,
                  "offplan_india_bound": india, "config_version": "gm1-" + "a" * 32}
        script = "/no-frame-referrer.js" if negative else "/candidate.js"
        document = f"""<!doctype html><body><script nonce="test-fixture">
          window.BSREGoogleConfig={json.dumps(config)};
          window.BSREMeasurement={{ canLoad: purpose => {str(allowed).lower()} && purpose === 'advertising', connect: () => {{}} }};
          window.BSREConsentBridge={{}};
          window.BSRELead={{advertisingContext:()=>({{}})}};
          addEventListener('load', () => setTimeout(() => parent.postMessage({{
            fixture:{json.dumps(name)},result:{{frame:Boolean(document.querySelector('iframe')),active:Boolean(window.BSREGoogle?.active('advertising'))}}
          }},location.origin),200));
        </script><script nonce="test-fixture" src="{script}"></script></body>"""
        policy = "default-src 'none'; frame-ancestors 'self'; script-src 'nonce-test-fixture'; " + "frame-src " + origin + RUNTIME
        self.respond(document.encode(), policy=policy, referrer="no-referrer")


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--chrome", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit("Choose a new output path to preserve the earlier check")
    manifest = json.loads((args.candidate / "REVIEW.json").read_text(encoding="utf-8"))
    script = (args.candidate / "forward/assets/google-measurement.js").read_bytes()
    fingerprint = sha256(script).hexdigest()
    if fingerprint != manifest["changes"]["assets/google-measurement.js"]["after"] or script.count(b"frame.referrerPolicy = 'origin';") != 1:
        raise SystemExit("The exact reviewed frame candidate failed its identity check")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    start = perf_counter()
    scratch = args.out.parent.resolve()
    with TemporaryDirectory(prefix="bsre-loopback-", dir=scratch, ignore_cleanup_errors=True) as tmp:
        folder = Path(tmp).resolve()
        if folder.parent != scratch:
            raise SystemExit("Unexpected fixture directory")
        context, public_pin = loopback_tls(folder)
        with ThreadingHTTPServer(("127.0.0.1", 0), Fixture) as server:
            server.socket = context.wrap_socket(server.socket, server_side=True)
            server.candidate, server.observations, server.paths = script, [], []
            service = Thread(target=server.serve_forever, daemon=True)
            service.start()
            try:
                chrome = run([str(args.chrome), "--headless", "--dump-dom", "--virtual-time-budget=4000",
                              "--no-first-run", "--no-default-browser-check", "--disable-extensions",
                              "--disable-background-networking", "--disable-component-update", "--disable-sync", "--disable-quic",
                              "--proxy-server=http://127.0.0.1:9", "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",
                              f"--user-data-dir={folder / 'profile'}", f"--ignore-certificate-errors-spki-list={public_pin}",
                              f"https://127.0.0.1:{server.server_port}/"], capture_output=True, timeout=22, creationflags=CREATE_NO_WINDOW)
            finally:
                server.shutdown()
                service.join(timeout=2)
            dom = chrome.stdout.decode("utf-8", errors="replace")
            result = re.search(r'<pre id="result">([^<]*)</pre>', dom)
            cases = json.loads(unescape(result[1])) if result and result[1] else {}
            requests = server.observations
            paths = server.paths
    receipt = {"schema": "bsre.offplan.loopback-frame.v1", "elapsed_seconds": round(perf_counter() - start, 3), "chrome_exit": chrome.returncode,
               "parent_asset_sha256": fingerprint, "cases": cases, "runtime_header_checks": requests,
               "scope": "Loopback browser fixture using the reviewed parent JS, local header observer and synthetic child. No vendor SDK or production submission."}
    expected = {name: {"frame": name in {"canonical", "german_query", "india_bound", "no_frame_referrer"},
                      "active": name in {"canonical", "german_query", "india_bound"}} for name in CASES}
    receipt["passed"] = chrome.returncode == 0 and cases == expected and len(requests) == 4 and sum(all(x.values()) for x in requests) == 3
    if not receipt["passed"]:
        receipt["diagnostics"] = {"stdout_bytes": len(chrome.stdout), "stderr_bytes": len(chrome.stderr), "loopback_paths": paths,
                                  "browser_error_codes": sorted(set(re.findall(r"(?:ERR_[A-Z_]+|net_error -?\d+)", dom + chrome.stderr.decode(errors="replace"))))}
    with args.out.open("x", encoding="utf-8", newline="\n") as output:
        output.write(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"passed": receipt["passed"], "cases": len(cases), "requests": len(requests), "seconds": receipt["elapsed_seconds"]}))
    if not receipt["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

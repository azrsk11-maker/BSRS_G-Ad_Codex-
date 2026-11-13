"""Real synthetic TLS handshakes. No browser, production or global trust changes."""
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import hashlib
import json
import os
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
import ipaddress

BASE = Path(__file__).resolve().parents[2]
PYDIR = BASE/'tools/staging-lab'
NODEDIR = BASE/'tools/website-tracking/tracking-system'
sys.path.insert(0, str(PYDIR))
import trusted_loopback_tls as helper


class Silent(BaseHTTPRequestHandler):
    def log_message(self, *args): pass


class TLSTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='bsre-private-tls-')
        cls.root = Path(cls.temp.name)
        cls.key = ec.generate_private_key(ec.SECP256R1())
        cls.ca_key = ec.generate_private_key(ec.SECP256R1())
        now = datetime.now(timezone.utc)
        ca_name = x509.Name([x509.NameAttribute(x509.NameOID.COMMON_NAME, 'SYNTHETIC TEST ONLY CA')])
        ca = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name)
              .public_key(cls.ca_key.public_key()).serial_number(x509.random_serial_number())
              .not_valid_before(now-timedelta(days=1)).not_valid_after(now+timedelta(days=1))
              .add_extension(x509.BasicConstraints(ca=True, path_length=0), True).sign(cls.ca_key, hashes.SHA256()))
        cls.ca = cls.root/'ca.pem'
        cls.ca.write_bytes(ca.public_bytes(serialization.Encoding.PEM))
        cls.keyfile = cls.root/'key.pem'
        cls.keyfile.write_bytes(cls.key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        cls.certs = {}
        for kind in ['valid', 'expired', 'wrong-host']:
            san = x509.DNSName('wrong.invalid') if kind == 'wrong-host' else x509.IPAddress(ipaddress.ip_address('127.0.0.1'))
            leaf_name = x509.Name([x509.NameAttribute(x509.NameOID.COMMON_NAME, 'SYNTHETIC LOOPBACK LEAF')])
            cert = (x509.CertificateBuilder().subject_name(leaf_name).issuer_name(ca_name)
                    .public_key(cls.key.public_key()).serial_number(x509.random_serial_number())
                    .not_valid_before(now-timedelta(days=2))
                    .not_valid_after(now-timedelta(days=1) if kind=='expired' else now+timedelta(hours=1))
                    .add_extension(x509.BasicConstraints(ca=False,path_length=None),True)
                    .add_extension(x509.SubjectAlternativeName([san]),False).sign(cls.ca_key, hashes.SHA256()))
            path = cls.root/(kind+'.pem'); path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
            cls.certs[kind] = path

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def env(self, trusted):
        env = os.environ.copy()
        # These synthetic per-process roots test validation only; never used for browser acceptance.
        for name in ['SSL_CERT_FILE','SSL_CERT_DIR','NODE_EXTRA_CA_CERTS','NODE_TLS_REJECT_UNAUTHORIZED']:
            env.pop(name,None)
        if trusted:
            env['SSL_CERT_FILE'] = str(self.ca)
            env['NODE_EXTRA_CA_CERTS'] = str(self.ca)
        return env

    def run_child(self, args, trusted=False):
        return subprocess.run(args, env=self.env(trusted), capture_output=True, text=True, timeout=12)

    def handshake(self, runtime, kind, trusted):
        server = ThreadingHTTPServer(('127.0.0.1',0), Silent)
        server.socket = helper.server_context(self.certs[kind],self.keyfile).wrap_socket(server.socket,server_side=True)
        worker = threading.Thread(target=server.serve_forever,daemon=True); worker.start()
        port = server.server_port
        try:
            if runtime=='python':
                args=[sys.executable,'-B','-c',f"import sys; sys.path.insert(0,{str(PYDIR)!r}); from trusted_loopback_tls import verify_loopback_tls; verify_loopback_tls({port})"]
            else:
                code=f"import {{verifyLoopbackTLS}} from {json.dumps((NODEDIR/'trusted-loopback-tls.mjs').as_uri())}; await verifyLoopbackTLS({port});"
                args=['node','--input-type=module','-e',code]
            return self.run_child(args,trusted)
        finally:
            server.shutdown(); worker.join(3); server.server_close()

    def test_real_handshakes_both_runtimes(self):
        for runtime in ['python','node']:
            for kind,trusted,ok in [('valid',True,True),('valid',False,False),('expired',True,False),('wrong-host',True,False)]:
                with self.subTest(runtime=runtime,kind=kind,trusted=trusted):
                    result=self.handshake(runtime,kind,trusted)
                    self.assertEqual(result.returncode==0,ok,result.stderr[-800:])

    def test_entrypoints_reject_missing_material(self):
        p=self.run_child([sys.executable,'-B',str(PYDIR/'consent-browser-probe.py'),'--chrome',sys.executable])
        self.assertNotEqual(p.returncode,0); self.assertIn('--tls-cert',p.stderr)
        env=self.env(False); env['BSRE_BROWSER_PATH']='SYNTHETIC_BROWSER_MUST_NOT_START'
        p=subprocess.run(['node',str(NODEDIR/'browser-cta-acceptance.mjs')],env=env,capture_output=True,text=True,timeout=12)
        self.assertNotEqual(p.returncode,0); self.assertIn('Explicit BSRE_TLS_CERT',p.stderr)

    def test_invalid_tls_prevents_both_entrypoint_browser_launches(self):
        for kind in ['valid','expired','wrong-host']:
            # valid-but-untrusted and the two invalid trusted scenarios must all fail before spawn.
            trusted=kind!='valid'
            with self.subTest(runtime='python',kind=kind):
                code=f"import runpy,sys; from unittest.mock import patch; sys.path.insert(0,{str(PYDIR)!r}); sys.argv=['probe','--chrome',sys.executable,'--tls-cert',{str(self.certs[kind])!r},'--tls-key',{str(self.keyfile)!r}];\nwith patch('subprocess.Popen',side_effect=AssertionError('BROWSER_STARTED')): runpy.run_path({str(PYDIR/'consent-browser-probe.py')!r},run_name='__main__')"
                p=self.run_child([sys.executable,'-B','-c',code],trusted)
                self.assertNotEqual(p.returncode,0); self.assertIn('CERTIFICATE_VERIFY_FAILED',p.stderr)
                self.assertNotIn('BROWSER_STARTED',p.stderr)
            with self.subTest(runtime='node',kind=kind):
                env=self.env(trusted)
                env.update(BSRE_BROWSER_PATH='SYNTHETIC_BROWSER_MUST_NOT_START',BSRE_TLS_CERT=str(self.certs[kind]),BSRE_TLS_KEY=str(self.keyfile))
                p=subprocess.run(['node',str(NODEDIR/'browser-cta-acceptance.mjs')],env=env,capture_output=True,text=True,timeout=12)
                self.assertNotEqual(p.returncode,0)
                self.assertRegex(p.stderr,'CERT_|certificate|cert chain')
                self.assertNotIn('spawn SYNTHETIC_BROWSER',p.stderr)

    def test_malformed_and_mismatched_material(self):
        bad=self.root/'bad.pem';bad.write_text('SYNTHETIC INVALID',encoding='utf-8')
        other=self.root/'other-key.pem'
        other.write_bytes(ec.generate_private_key(ec.SECP256R1()).private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
        for cert,key in [(bad,self.keyfile),(self.certs['valid'],other)]:
            with self.subTest(runtime='python',cert=cert.name,key=key.name):
                with self.assertRaises(ssl.SSLError): helper.server_context(cert,key)
            with self.subTest(runtime='node',cert=cert.name,key=key.name):
                code=f"import {{loadTestTLS}} from {json.dumps((NODEDIR/'trusted-loopback-tls.mjs').as_uri())}; await loadTestTLS({json.dumps(str(cert))},{json.dumps(str(key))});"
                p=self.run_child(['node','--input-type=module','-e',code]);self.assertNotEqual(p.returncode,0)

    def test_security_flags_absent_and_sources_unchanged(self):
        for p in [PYDIR/'consent-browser-probe.py', NODEDIR/'browser-cta-acceptance.mjs']:
            text=p.read_text(encoding='utf-8')
            for forbidden in ['ignore-certificate-errors','--no-sandbox','Security.setIgnoreCertificateErrors','rejectUnauthorized:false']:
                self.assertNotIn(forbidden,text)



if __name__=='__main__':
    unittest.main()

import fs from 'node:fs/promises';
import tls from 'node:tls';

export async function loadTestTLS(cert, key) {
  if (!cert || !key) throw new Error('Explicit BSRE_TLS_CERT and BSRE_TLS_KEY required');
  const material = {cert: await fs.readFile(cert), key: await fs.readFile(key)};
  tls.createSecureContext(material); // Reject malformed material and mismatched keys before serving.
  return material;
}

export function verifyLoopbackTLS(port) {
  return new Promise((resolve, reject) => {
    const socket = tls.connect({host:'127.0.0.1', port, rejectUnauthorized:true,
      checkServerIdentity:(_, cert) => tls.checkServerIdentity('127.0.0.1', cert)});
    socket.setTimeout(3000, () => socket.destroy(new Error('TLS preflight timed out')));
    socket.once('error', reject);
    socket.once('secureConnect', () => {socket.end(); resolve();});
  });
}

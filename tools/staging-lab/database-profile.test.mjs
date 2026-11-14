import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {gzipSync} from 'node:zlib';
import {install, validateLock, verifyIndex} from './install-db-profile.mjs';
import {assertServerVersion, checkServer} from './database-profile.mjs';

const original = JSON.parse(readFileSync(new URL('./database-11.8.9.lock.json', import.meta.url), 'utf8'));
const sha = value => createHash('sha256').update(value).digest('hex');
function fixture(failure) {
  const lock = structuredClone(original), artifacts = new Map(), files = new Map(), calls = [];
  for (const p of lock.packages) {
    const bytes = Buffer.from(`synthetic-deb-${p.Package}`);
    p.SHA256 = sha(bytes); p.Size = String(bytes.length);
    artifacts.set(lock.repository + p.Filename, bytes);
  }
  const index = gzipSync(lock.packages.map(p => Object.entries(p).map(([k,v]) => `${k}: ${v}`).join('\n')).join('\n\n'));
  const release = Buffer.from(`Origin: MariaDB\nSHA256:\n ${sha(index)} ${index.length} main/binary-amd64/Packages.gz\n`);
  const bytes = {key: Buffer.from('synthetic-key'), release, signature: Buffer.from('synthetic-signature'), index};
  for (const [name, item] of Object.entries(lock.metadata)) {
    item.sha256 = sha(bytes[name]); artifacts.set(item.url, bytes[name]);
  }
  const io = {
    run(file, args, capture) {
      calls.push([file, args, capture]);
      if (file === 'curl') {
        assert.ok(args.includes('--fail') && args.includes('--tlsv1.2'));
        assert.equal(args[args.indexOf('--proto') + 1], '=https');
        assert.equal(args[args.indexOf('--proto-redir') + 1], '=https');
        const url = args[args.indexOf('--output') - 1], name = args.at(-1);
        if (failure === 'download') throw new Error('Download failed');
        files.set(name, failure === 'checksum' ? Buffer.from('tampered') : artifacts.get(url));
      }
      if (file === 'dpkg') return failure === 'architecture' ? 'arm64\n' : 'amd64\n';
      if (file === 'gpg' && args.includes('--show-keys')) {
        return 'pub:::::::::\nfpr:::::::::' + (failure === 'fingerprint' ? '0'.repeat(40) : lock.fingerprint) + ':\n';
      }
      if (file === 'gpgv' && failure === 'signature') throw new Error('Bad signature');
      if (file === 'apt-get' && args.some(a => a.endsWith('.deb')) && failure === 'apt') throw new Error('APT failed');
      if (file === 'dpkg-query') return failure === 'installed-version' ? '1:10.11.19' : lock.packages.find(p => p.Package === args.at(-1)).Version;
      return '';
    },
    read(path, encoding) {
      if (path === '/etc/os-release') return failure === 'os' ? 'ID=ubuntu\nVERSION_ID="24.04"\n' : 'ID=debian\nVERSION_ID="12"\n';
      const value = files.get(path); assert.ok(value, `Unknown fake file ${path}`);
      return encoding ? value.toString(encoding) : value;
    },
    write(path, value) { files.set(path, Buffer.from(value)); },
    temp: () => '/synthetic-build', remove: path => calls.push(['cleanup', path]),
  };
  return {lock, io, calls, files, index, release};
}

test('allowlist rejects unknown profiles before any command/write; baseline stays Debian-native', () => {
  const f = fixture();
  for (const profile of ['', undefined, '__proto__', '11.8', 'mariadb-11.8.10']) assert.throws(() => install(profile, f.lock, f.io));
  assert.equal(f.calls.length, 0); assert.equal(f.files.size, 0);
  install('debian-bookworm', null, f.io);
  assert.deepEqual(f.calls, [['apt-get', ['install', '-y', '--no-install-recommends', 'mariadb-server'], undefined]]);
  assert.equal(f.files.get('/opt/lab-build/database-profile').toString(), 'debian-bookworm\n');
});

test('real lock fixes official Debian12 URLs, package names, architecture and builds', () => {
  validateLock(original);
  for (const mutate of [l => l.repository += 'other/', l => l.fingerprint = '0'.repeat(40),
    l => l.packages.pop(), l => l.packages[1].Version = 'latest',
    l => l.packages[0].Filename = '../evil.deb', l => l.metadata.key.url = 'http://example.invalid/key']) {
    const changed = structuredClone(original); mutate(changed); assert.throws(() => validateLock(changed));
  }
});

test('signature-bound SHA256 index must contain every exact package', () => {
  const f = fixture(); verifyIndex(f.release.toString(), f.index, f.lock.packages);
  assert.throws(() => verifyIndex(f.release.toString().replace('SHA256:', 'MD5Sum:'), f.index, f.lock.packages));
  assert.throws(() => verifyIndex(f.release.toString(), Buffer.from('bad index'), f.lock.packages));
  const changed = structuredClone(f.lock.packages); changed[0].SHA256 = '0'.repeat(64);
  assert.throws(() => verifyIndex(f.release.toString(), f.index, changed));
});

test('acquisition verifies before vendor install and emits baked profile only after exact installed versions', () => {
  const f = fixture(); install('mariadb-11.8.9', f.lock, f.io);
  const signature = f.calls.findIndex(c => c[0] === 'gpgv');
  const vendorInstall = f.calls.findIndex(c => c[0] === 'apt-get' && c[1].some(a => a.endsWith('.deb')));
  assert.ok(signature > 0 && vendorInstall > signature);
  assert.equal(f.calls[vendorInstall][1].filter(a => a.endsWith('.deb')).length, 7);
  assert.equal(f.calls.filter(c => c[0] === 'dpkg-query').length, 7);
  assert.equal(f.files.get('/opt/lab-build/database-profile').toString(), 'mariadb-11.8.9\n');
  assert.equal(f.calls.at(-1)[0], 'cleanup');
});

for (const failure of ['os', 'architecture', 'download', 'checksum', 'fingerprint', 'signature', 'apt', 'installed-version']) {
  test(`fail closed on ${failure}`, () => {
    const f = fixture(failure); assert.throws(() => install('mariadb-11.8.9', f.lock, f.io));
    assert.equal(f.files.has('/opt/lab-build/database-profile'), false);
    if (!['apt', 'installed-version'].includes(failure)) {
      assert.equal(f.calls.some(c => c[0] === 'apt-get' && c[1].some(a => a.endsWith('.deb'))), false);
    }
  });
}

test('actual server branch/patch required; client, malformed, multiline and other profiles rejected', () => {
  assert.equal(assertServerVersion('debian-bookworm', '10.11.19-MariaDB-0+deb12u1').status, 'PASS');
  assert.equal(assertServerVersion('mariadb-11.8.9', '11.8.9-MariaDB-deb12').database, '11.8.9-MariaDB-deb12');
  for (const version of ['10.11.19-MariaDB', '11.8.8-MariaDB', '11.8.90-MariaDB', '11.8.9',
    'mysqlnd 8.2.35', 'mariadb Ver 15.1 Distrib 11.8.9-MariaDB', '11.8.9-MariaDB\n', '11.8.9-MariaDB\r',
    '11.8.9-MariaDB\n11.8.9-MariaDB', '', null]) {
    assert.throws(() => assertServerVersion('mariadb-11.8.9', version));
  }
  assert.throws(() => assertServerVersion('__proto__', '11.8.9-MariaDB'));
});

test('server check uses bounded socket SQL and propagates failed SQL/read instead of passing', () => {
  const read = path => { assert.equal(path, '/opt/lab-build/database-profile'); return 'mariadb-11.8.9\n'; };
  const run = (file, args, options) => {
    assert.equal(file, 'mariadb'); assert.ok(args.includes('--no-defaults'));
    assert.ok(args.includes('--socket=/tmp/bsre.sock')); assert.ok(args.includes('--execute=SELECT VERSION()'));
    assert.equal(options.timeout, 5000); assert.equal(options.maxBuffer, 4096);
    return '11.8.9-MariaDB-deb12\n';
  };
  assert.equal(checkServer(read, run).production_acceptance, false);
  assert.throws(() => checkServer(read, () => { throw new Error('SQL failure'); }));
  assert.throws(() => checkServer(() => { throw new Error('Profile missing'); }, run));
});

test('both profiles retain the complete lab and identical required isolation controls', () => {
  const local = name => readFileSync(new URL(name, import.meta.url), 'utf8');
  const workflow = local('../../.github/workflows/isolated-wordpress-lab.yml');
  const entry = local('entrypoint.sh'), docker = local('Dockerfile');
  assert.ok(docker.startsWith('FROM php:8.2-cli-bookworm@sha256:ce09ca1d4b532edf9b0347b44a1968a80d9175addb581c450ba0c9a43fa0c5ea\n'));
  assert.ok(docker.includes('881e53a4681ff2cd911651b11cccdede5ae477ddf0765af5d6a1a8b219a1d835'));
  assert.ok(docker.includes('ARG BSRE_DB_PROFILE=debian-bookworm') && docker.includes('USER mysql'));
  const create = workflow.split('\n').filter(l => l.trim().startsWith('docker create '));
  assert.equal(create.length, 2);
  const controls = '--network none --read-only --cap-drop ALL --security-opt no-new-privileges --memory 1g --cpus 2 --pids-limit 128 --tmpfs /tmp:rw,noexec,nosuid,size=512m,mode=1777';
  for (const line of create) assert.ok(line.includes(controls));
  assert.match(workflow, /isolated-native-wordpress:\n/); assert.match(workflow, /timeout-minutes: 15/);
  assert.ok(workflow.includes('--build-arg BSRE_DB_PROFILE=mariadb-11.8.9'));
  assert.ok(entry.indexOf('/opt/lab/isolation.php') < entry.indexOf('mkdir /tmp/database'));
  assert.ok(entry.includes('--skip-networking'));
  assert.ok(entry.indexOf('node /opt/lab/database-profile.mjs') > entry.indexOf('until mariadb-admin'));
  assert.ok(entry.indexOf('node /opt/lab/database-profile.mjs') < entry.indexOf('CREATE DATABASE'));
  assert.ok(entry.indexOf('CREATE DATABASE') < entry.indexOf('/opt/lab/native.php'));
});

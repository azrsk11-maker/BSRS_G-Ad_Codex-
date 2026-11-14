// Build-only dependency acquisition. Never imports or executes WordPress/PHP.
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {readFileSync, writeFileSync, mkdtempSync, rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {gunzipSync} from 'node:zlib';

export const PROFILES = ['debian-bookworm', 'mariadb-11.8.9'];
const BASE = 'https://archive.mariadb.org/mariadb-11.8.9/repo/debian/';
const FINGERPRINT = '177F4010FE56CA3336300305F1656F24C74CD1D8';
const NAMES = ['galera-4', 'libmariadb3', 'mariadb-client', 'mariadb-client-core',
  'mariadb-common', 'mariadb-server', 'mariadb-server-core'];
const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');
const requireTrue = (condition, message) => { if (!condition) throw new Error(message); };

export function validateLock(lock) {
  requireTrue(lock?.schema === 1 && lock.repository === BASE &&
    lock.fingerprint === FINGERPRINT && lock.packages?.length === NAMES.length,
  'Unrecognized database acquisition lock');
  requireTrue(JSON.stringify(lock.packages.map(p => p.Package)) === JSON.stringify(NAMES),
    'Unexpected vendor package set/order');
  for (const p of lock.packages) {
    const version = p.Package === 'galera-4' ? '26.4.27-deb12' : '1:11.8.9+maria~deb12';
    const arch = p.Package === 'mariadb-common' ? 'all' : 'amd64';
    const filename = p.Package === 'galera-4'
      ? 'pool/main/g/galera-4/galera-4_26.4.27-deb12_amd64.deb'
      : `pool/main/m/mariadb/${p.Package}_11.8.9+maria~deb12_${arch}.deb`;
    requireTrue(p.Version === version && p.Architecture === arch && p.Filename === filename &&
      /^[a-f0-9]{64}$/.test(p.SHA256) && /^[1-9][0-9]*$/.test(p.Size), 'Invalid package lock');
  }
  const expected = {
    key: 'https://mariadb.org/mariadb_release_signing_key.pgp',
    release: BASE + 'dists/bookworm/Release',
    signature: BASE + 'dists/bookworm/Release.gpg',
    index: BASE + 'dists/bookworm/main/binary-amd64/Packages.gz',
  };
  requireTrue(Object.keys(lock.metadata ?? {}).sort().join() === Object.keys(expected).sort().join(),
    'Unexpected metadata set');
  for (const [name, url] of Object.entries(expected)) {
    requireTrue(lock.metadata[name]?.url === url && /^[a-f0-9]{64}$/.test(lock.metadata[name]?.sha256),
      'Invalid metadata lock');
  }
}

export function verifyIndex(release, compressed, packages) {
  const digest = sha256(compressed);
  const section = release.split('\nSHA256:\n')[1]?.split(/\n[A-Za-z0-9-]+:/)[0];
  requireTrue(section?.split('\n').some(line =>
    line.trim() === `${digest} ${compressed.length} main/binary-amd64/Packages.gz` ||
    line.trim().split(/\s+/).join(' ') === `${digest} ${compressed.length} main/binary-amd64/Packages.gz`),
  'Package index is not SHA256-bound by signed Release');
  const records = gunzipSync(compressed, {maxOutputLength: 4 * 1024 * 1024}).toString('utf8')
    .trim().split('\n\n').map(record => Object.fromEntries(record.split('\n')
      .filter(line => /^[A-Za-z0-9-]+: /.test(line)).map(line => {
        const separator = line.indexOf(': '); return [line.slice(0, separator), line.slice(separator + 2)];
      })));
  for (const p of packages) {
    const matches = records.filter(r => r.Package === p.Package && r.Version === p.Version && r.Architecture === p.Architecture);
    requireTrue(matches.length === 1 && ['Filename', 'SHA256', 'Size'].every(k => matches[0][k] === p[k]),
      'Locked package differs from signed package index');
  }
}

const defaultIO = {
  run: (file, args, capture = false) => execFileSync(file, args, {
    encoding: 'utf8', timeout: 120000, maxBuffer: 4 * 1024 * 1024,
    stdio: capture ? ['ignore', 'pipe', 'pipe'] : 'inherit',
  }),
  read: readFileSync, write: writeFileSync,
  temp: () => mkdtempSync(join(tmpdir(), 'bsre-db-')),
  remove: path => rmSync(path, {recursive: true, force: true}),
};

export function install(profile, lock, io = defaultIO) {
  requireTrue(PROFILES.includes(profile), 'Unknown database profile');
  if (profile === 'debian-bookworm') {
    io.run('apt-get', ['install', '-y', '--no-install-recommends', 'mariadb-server']);
  } else {
    validateLock(lock);
    requireTrue(io.read('/etc/os-release', 'utf8').split('\n').includes('ID=debian') &&
      io.read('/etc/os-release', 'utf8').split('\n').includes('VERSION_ID="12"') &&
      io.run('dpkg', ['--print-architecture'], true).trim() === 'amd64',
    'MariaDB profile requires Debian 12 amd64');
    io.run('apt-get', ['install', '-y', '--no-install-recommends', 'gnupg']);
    const dir = io.temp();
    try {
      function fetch(url, digest, name, size) {
        const destination = join(dir, name);
        io.run('curl', ['--fail', '--location', '--proto', '=https', '--proto-redir', '=https',
          '--tlsv1.2', '--connect-timeout', '15', '--max-time', '60',
          '--max-filesize', String(size ?? 4 * 1024 * 1024), url, '--output', destination]);
        const bytes = io.read(destination);
        requireTrue(sha256(bytes) === digest && (size === undefined || bytes.length === Number(size)),
          'Acquired dependency checksum/size mismatch');
        return destination;
      }
      const files = Object.fromEntries(Object.entries(lock.metadata).map(([name, item]) =>
        [name, fetch(item.url, item.sha256, name)]));
      const keyInfo = io.run('gpg', ['--batch', '--no-options', '--homedir', dir, '--with-colons',
        '--show-keys', files.key], true);
      requireTrue(keyInfo.split('\n').filter(l => l.startsWith('pub:')).length === 1 &&
        keyInfo.split('\n').find(l => l.startsWith('fpr:'))?.split(':')[9] === FINGERPRINT,
      'Vendor primary signing-key fingerprint mismatch');
      const keyring = join(dir, 'vendor.gpg');
      io.run('gpg', ['--batch', '--no-options', '--homedir', dir, '--dearmor', '--output', keyring, files.key]);
      io.run('gpgv', ['--homedir', dir, '--keyring', keyring, files.signature, files.release]);
      verifyIndex(io.read(files.release, 'utf8'), io.read(files.index), lock.packages);
      const debs = lock.packages.map(p => fetch(BASE + p.Filename, p.SHA256, p.Package + '.deb', p.Size));
      // Debian's signed repositories resolve Debian-native shared-library dependencies.
      // Vendor packages are local, exact, signed-index-bound artifacts, never a floating repo.
      io.run('apt-get', ['install', '-y', '--no-install-recommends', ...debs]);
      for (const p of lock.packages) {
        requireTrue(io.run('dpkg-query', ['--show', '--showformat=${Version}', p.Package], true) === p.Version,
          'Installed vendor package version differs from lock');
      }
    } finally {
      io.remove(dir);
    }
  }
  io.write('/opt/lab-build/database-profile', profile + '\n', {encoding: 'utf8', mode: 0o444});
  return {phase: 'build_database_dependencies', profile,
    packages: profile === 'mariadb-11.8.9' ? lock.packages.map(p => ({
      package: p.Package, version: p.Version, architecture: p.Architecture, sha256: p.SHA256,
    })) : [], server_executed: false};
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const lock = JSON.parse(readFileSync(new URL('./database-11.8.9.lock.json', import.meta.url), 'utf8'));
  console.log(JSON.stringify(install(process.argv[2], lock)));
}

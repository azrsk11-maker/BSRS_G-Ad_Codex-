// Runs after socket readiness and before CREATE DATABASE or WordPress bootstrap.
import {execFileSync} from 'node:child_process';
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

export function assertServerVersion(profile, version) {
  const patterns = {
    'debian-bookworm': /^10\.11\.[0-9]+-MariaDB(?:[-+][A-Za-z0-9.~+_-]+)?$/,
    'mariadb-11.8.9': /^11\.8\.9-MariaDB(?:[-+][A-Za-z0-9.~+_-]+)?$/,
  };
  if (!Object.hasOwn(patterns, profile) || typeof version !== 'string' ||
      version.includes('\n') || version.includes('\r') || !patterns[profile].test(version)) {
    throw new Error('Actual database server version does not match the baked lab profile');
  }
  return {phase: 'pre_wordpress_database', status: 'PASS', profile, database: version,
    synthetic_database_only: true, production_acceptance: false};
}

export function checkServer(read = readFileSync, run = execFileSync) {
  const profile = read('/opt/lab-build/database-profile', 'utf8').trim();
  const version = run('mariadb', ['--no-defaults', '--user=root', '--socket=/tmp/bsre.sock',
    '--batch', '--skip-column-names', '--execute=SELECT VERSION()'], {
    encoding: 'utf8', timeout: 5000, maxBuffer: 4096, stdio: ['ignore', 'pipe', 'pipe'],
  }).replace(/\n$/, '');
  return assertServerVersion(profile, version);
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  console.log(JSON.stringify(checkServer()));
}

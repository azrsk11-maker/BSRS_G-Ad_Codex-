import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { buildPreferenceAddon } from './build-native-addon.mjs';
import { buildManifest, names, folder, sha } from './build-runtime.mjs';

const here = dirname(fileURLToPath(import.meta.url));
test('pure add-on maps only eight exact current G37 files without rebuilding G36', () => {
  const files = buildPreferenceAddon();
  const expected = [...names.map(n => 'g37-pref/runtime/' + n),
    'g37-pref/runtime/preference-source.json', 'g37-pref/FixturePorts.php', 'g37-pref/native.php'];
  assert.deepEqual([...files.keys()].sort(), expected.sort());
  assert.equal(files.size, 8);
  for (const name of names) assert.equal(sha(files.get('g37-pref/runtime/' + name)), sha(readFileSync(join(folder, name))));
  assert.deepEqual(files.get('g37-pref/runtime/preference-source.json'), buildManifest().bytes);
  for (const name of ['FixturePorts.php', 'native.php']) assert.deepEqual(files.get('g37-pref/' + name), readFileSync(join(here, 'native', name)));
  const code = readFileSync(join(here, 'build-native-addon.mjs'), 'utf8');
  assert.ok(!code.includes('buildG36LabPacket') && !code.includes('g36-source') && !code.includes('writeFile'));
});

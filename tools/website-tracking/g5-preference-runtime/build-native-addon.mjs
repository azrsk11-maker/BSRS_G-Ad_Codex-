/** Pure eight-file G37 add-on. Existing accepted /opt/lab/g36 is a required CI input. */
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { buildManifest, names, folder } from './build-runtime.mjs';

const here = dirname(fileURLToPath(import.meta.url));
export function buildPreferenceAddon() {
  const manifest = buildManifest();
  const files = new Map(names.map(name => [
    'g37-pref/runtime/' + name, readFileSync(join(folder, name)),
  ]));
  files.set('g37-pref/runtime/preference-source.json', manifest.bytes);
  files.set('g37-pref/FixturePorts.php', readFileSync(join(here, 'native/FixturePorts.php')));
  files.set('g37-pref/native.php', readFileSync(join(here, 'native/native.php')));
  return files;
}

import {existsSync, mkdirSync, readFileSync, writeFileSync} from 'node:fs';
import {dirname, resolve} from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {buildG5RuntimeCandidate, readG5NativeFixture} from '../website-tracking/g5-runtime-ports/build-candidate.mjs';

/** Fixed image-build path only. The existing isolated entrypoint owns runtime isolation. */
export function buildG5RuntimeLab() {
  if (process.platform !== 'linux' || fileURLToPath(import.meta.url) !== '/opt/lab/staging-lab/build-g5-runtime-lab.mjs') throw new Error('G5_FIXED_LAB_BUILD_PATH_REQUIRED');
  const candidate = buildG5RuntimeCandidate();
  const native = readG5NativeFixture();
  const files = Object.entries(candidate.outputs).map(([name,bytes]) => ['/opt/lab/g5/ready/' + name, bytes]);
  files.push(['/opt/lab/g5/tests/native.php', native]);
  files.push(['/opt/lab/g5/manifest.json', Buffer.from(JSON.stringify(candidate.manifest,null,2)+'\n')]);
  // All reads/hash checks complete before the first write. Existing exact bytes are reusable.
  for (const [path,bytes] of files) if (existsSync(path) && !readFileSync(path).equals(bytes)) throw new Error('G5_LAB_DESTINATION_CONFLICT');
  for (const [path,bytes] of files) { mkdirSync(dirname(path),{recursive:true}); if (!existsSync(path)) writeFileSync(path,bytes,{flag:'wx'}); }
  return candidate.manifest;
}
if (process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url) {
  const manifest = buildG5RuntimeLab();
  process.stdout.write(JSON.stringify({phase:'g5_runtime_candidate_build',output_count:manifest.output_count,status:manifest.status,native_accepted:false})+'\n');
}

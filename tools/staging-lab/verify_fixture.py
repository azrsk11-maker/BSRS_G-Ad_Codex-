"""Verify the exact reviewed baseline before any image build. No network/writes."""
import hashlib
import json
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
fixture = ROOT / 'tools/staging-lab/fixtures/bsre-enquiries'
receipt = json.loads((ROOT / 'docs/audit/INSTALLED_SOURCE_COMPARISON_2026-11-07.json').read_text())
expected = {r['path']: r['target_sha256'] for r in receipt['results']}
manifest_digest = hashlib.sha256(json.dumps(expected, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
if manifest_digest != '91e1be72d725b359a5c665022c5cc700aba9782bba7964115b19ab9ba34201d9':
    raise SystemExit('Reviewed member hash manifest changed')
if len(expected) != 30 or receipt['target_zip_sha256'] != 'f64910af55a72d5551d24ceb2cc7d2ffa666b7bd8579126d719463897bdf2443':
    raise SystemExit('Unexpected baseline provenance')
actual = {p.relative_to(fixture).as_posix() for p in fixture.rglob('*') if p.is_file()}
if actual != set(expected):
    raise SystemExit('Fixture member set differs from reviewed baseline')
for name, digest in expected.items():
    if PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts:
        raise SystemExit('Unsafe fixture path')
    path = fixture / name
    if path.is_symlink() or any(p.is_symlink() for p in path.parents if p != fixture.parent):
        raise SystemExit('Symlink is not an accepted fixture')
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise SystemExit('Baseline hash mismatch: ' + name)
print(json.dumps({'scope': 'PRIMARY_PLUGIN_SOURCE_ONLY_NOT_PRIVATE_CONFIG', 'status': 'PASS', 'members': 30, 'bytes': sum((fixture / n).stat().st_size for n in expected)}))

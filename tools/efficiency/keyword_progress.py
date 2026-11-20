"""Bounded, non-authoritative keyword timing diagnostics; never acceptance."""
import hashlib
import json
import math
from pathlib import Path
import re
import time
import uuid

LIMIT = 1048576
PREFIX = 'KEYWORD_PROGRESS '
NAME = re.compile(r'test-output/keyword-progress-([0-9a-f]{32})\.jsonl\Z')


def directory(root):
    root = Path(root).resolve(strict=True)
    target = root / 'test-output'
    target.mkdir(exist_ok=True)
    if (target.is_symlink() or (hasattr(target, 'is_junction') and target.is_junction())
            or target.resolve().parent != root):
        raise ValueError('Unsafe diagnostic directory')
    return target


class Progress:
    def __init__(self, root):
        self.run_id = uuid.uuid4().hex
        self.relative = 'test-output/keyword-progress-' + self.run_id + '.jsonl'
        self.path = directory(root) / Path(self.relative).name
        self.started = time.perf_counter()
        self.last_write = float('-inf')
        self.disabled = False
        with self.path.open('xb'):
            pass

    def reference(self):
        return PREFIX + json.dumps({'run_id': self.run_id, 'file': self.relative}, separators=(',', ':'))

    def due(self):
        return not self.disabled and time.perf_counter() - self.last_write >= 5

    def write(self, rows, status='RUNNING'):
        value = {'version': 1, 'run_id': self.run_id, 'diagnostic_only': True,
                 'acceptance': False, 'status': status,
                 'elapsed_seconds': round(time.perf_counter() - self.started, 6), 'modules': rows}
        body = (json.dumps(value, separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')
        if (len(body) > LIMIT or self.path.is_symlink()
                or self.path.stat().st_size + len(body) > LIMIT):
            raise ValueError('Unsafe or oversized diagnostic')
        # Append one complete snapshot. A killed append leaves the preceding
        # newline-terminated snapshot intact; no Windows/OneDrive rename needed.
        with self.path.open('ab') as stream:
            stream.write(body)
        self.last_write = time.perf_counter()


def read_diagnostic(root, stderr):
    """Return checked metadata only; mutable/stale progress proves no verdict."""
    if isinstance(stderr, bytes):
        stderr = stderr.decode('utf-8', errors='replace')
    if not isinstance(stderr, str) or len(stderr) > LIMIT:
        return None
    refs = [line[len(PREFIX):] for line in stderr.splitlines() if line.startswith(PREFIX)]
    if len(refs) != 1:
        return None
    try:
        ref = json.loads(refs[0])
        match = NAME.fullmatch(ref['file'])
        if not match or match.group(1) != ref['run_id']:
            return None
        path = directory(root) / Path(ref['file']).name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > LIMIT:
            return None
        body = path.read_bytes()
        if len(body) > LIMIT:
            return None
        if b'\n' not in body:
            return None
        value = json.loads(body.rsplit(b'\n', 2)[-2])
        if (type(value['version']) is not int or value['version'] != 1 or value['run_id'] != ref['run_id']
                or value['diagnostic_only'] is not True or value['acceptance'] is not False
                or value['status'] not in ('RUNNING', 'FINISHED', 'TIMED_OUT')
                or type(value['elapsed_seconds']) not in (int, float)
                or not math.isfinite(value['elapsed_seconds']) or value['elapsed_seconds'] < 0
                or not isinstance(value['modules'], list) or len(value['modules']) > 256):
            return None
        rows = []
        names = set()
        for row in value['modules']:
            name = row['module']
            if (not isinstance(name, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,127}', name)
                    or name in names or row['state'] not in ('PENDING', 'ACTIVE', 'COMPLETE', 'INCOMPLETE')
                    or any(type(row[k]) is not int or not 0 <= row[k] <= 100000 for k in ('expected', 'started', 'finished'))
                    or not row['finished'] <= row['started'] <= row['expected']
                    or type(row['elapsed_seconds']) not in (int, float)
                    or not math.isfinite(row['elapsed_seconds']) or row['elapsed_seconds'] < 0):
                return None
            names.add(name)
            rows.append({k: row[k] for k in ('module', 'state', 'expected', 'started', 'finished', 'elapsed_seconds')})
        return {'diagnostic_only': True, 'acceptance': False, 'status': value['status'],
                'file': ref['file'], 'sha256': hashlib.sha256(body).hexdigest(),
                'elapsed_seconds': value['elapsed_seconds'],
                'modules_total': len(rows), 'slowest_modules': sorted(rows, key=lambda x: x['elapsed_seconds'], reverse=True)[:12]}
    except (OSError, ValueError, KeyError, TypeError):
        return None

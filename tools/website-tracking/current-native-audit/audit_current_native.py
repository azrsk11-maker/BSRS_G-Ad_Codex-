"""Explicit current-head extension; frozen historical code, logs and assertions stay unchanged."""
import argparse
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

OWN = Path(__file__).resolve().parent
SCOPE_SHA256 = 'a47cafd7e8808432f2908fa1d38d2f89a21bf70f0253acdfb374f22d3382d7fe'
PHASE = 'current_g36_physical_identity'
BUDGET_DIR = 'g39-native-log-audit-budget30-20261117'


def need(ok, code):
    if not ok:
        raise ValueError(code)


def read(path, limit=2 * 1024 * 1024):
    with Path(path).open('rb') as stream:
        raw = stream.read(limit + 1)
    need(len(raw) <= limit, 'CURRENT_BYTE_BOUND')
    return raw


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def pairs(values):
    result = {}
    for key, value in values:
        need(key not in result, 'CURRENT_DUPLICATE_JSON_KEY')
        result[key] = value
    return result


def load(raw):
    def invalid(_):
        raise ValueError('CURRENT_NON_JSON_CONSTANT')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def same(a, b):
    return json.dumps(a, sort_keys=True, separators=(',', ':'), allow_nan=False) == json.dumps(b, sort_keys=True, separators=(',', ':'), allow_nan=False)


def path_under(root, relative):
    need(isinstance(relative, str) and re.fullmatch('[A-Za-z0-9_./-]+', relative)
         and not relative.startswith('/') and all(part not in ('', '.', '..') for part in relative.split('/')), 'CURRENT_SAFE_PATH')
    root = Path(root).resolve()
    target = root / relative
    need(root in target.resolve().parents and not target.is_symlink(), 'CURRENT_PATH_ESCAPE')
    at = root
    for part in relative.split('/'):
        at /= part
        need(not at.is_symlink(), 'CURRENT_SOURCE_SYMLINK')
    return target


def scope():
    raw = read(OWN / 'CURRENT_SCOPE.json')
    need(pin(raw)['sha256'] == SCOPE_SHA256, 'CURRENT_SCOPE_CHANGED')
    value = load(raw)
    need(value['schema'] == 'bsre-current-native-scope-v1' and value['old_document_count'] == 458
         and value['new_physical_identity_receipts'] == 2 and value['historical_predecessor_documents'] == 454,
         'CURRENT_CLOSED_DOCUMENT_SCOPE')
    need(value['composer']['path'] == 'tools/website-tracking/coupled-package-v3/compose-v3.mjs', 'CURRENT_EXACT_COMPOSER')
    return value


def historical(history, reviewed):
    path = path_under(history, BUDGET_DIR + '/audit_g39.py')
    need(pin(read(path)) == reviewed['historical_auditor'], 'CURRENT_HISTORICAL_AUDITOR_CHANGED')
    need(pin(read(path.parent / 'FREEZE.json')) == reviewed['historical_freeze'], 'CURRENT_HISTORICAL_FREEZE_CHANGED')
    spec = importlib.util.spec_from_file_location('current_preserved_budget30', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    frozen = module.freeze()  # Authenticates the complete accepted module/config/review closure.
    old = module.predecessor(frozen)
    expected, _ = old.configuration()
    need(len(expected['source_pins']) == 186, 'CURRENT_EXACT186_HISTORICAL_SOURCE_ASSERTIONS')
    return module, old, frozen, expected


def restore_delta(raw, delta):
    need(pin(raw) == delta['after'], 'CURRENT_DELTA_PIN:' + delta['path'])
    for edit in delta['inverse_edits']:
        before, after = edit['before'].encode('utf-8'), edit['after'].encode('utf-8')
        need(before and raw.count(before) == 1, 'CURRENT_DELTA_EXACT_ONCE:' + delta['path'])
        raw = raw.replace(before, after, 1)
    need(pin(raw) == delta['before'], 'CURRENT_DELTA_INVERSE:' + delta['path'])
    return raw


def source_deltas(source, reviewed):
    rows = reviewed['source_deltas']
    need(len(rows) == len({row['path'] for row in rows}), 'CURRENT_DUPLICATE_SOURCE_DELTA')
    need(reviewed['composer'] in rows, 'CURRENT_COMPOSER_DELTA_REQUIRED')
    result = {row['path']: restore_delta(read(path_under(source, row['path'])), row) for row in rows}
    for row in reviewed['new_source_files']:
        need(pin(read(path_under(source, row['path']))) == row['pin'], 'CURRENT_NEW_SOURCE_PIN:' + row['path'])
    return result


def derive(source, reviewed, node='node'):
    need(pin(read(OWN / 'derive-current.mjs')) == reviewed['derivation_helper'], 'CURRENT_DERIVATION_HELPER_CHANGED')
    need(pin(read(path_under(source, reviewed['composer']['path']))) == reviewed['composer']['after'], 'CURRENT_COMPOSER_REQUIRED')
    result = subprocess.run([node, str(OWN / 'derive-current.mjs'), str(Path(source).resolve()), str(OWN / 'CURRENT_SCOPE.json')],
                            capture_output=True, check=True, timeout=60)
    need(len(result.stdout) <= 256 * 1024 and not result.stderr, 'CURRENT_DERIVATION_OUTPUT_BOUND')
    value = load(result.stdout)
    need(value['scope'] == 'DERIVED_HASHES_ONLY_NOT_NATIVE_ACCEPTANCE'
         and same(value['expected_receipt'], reviewed['expected_receipt'])
         and same(value['guard'], reviewed['guard']) and value['receiver'] == reviewed['receiver'], 'CURRENT_REDERIVATION_CHANGED')
    return value


def validate_identity_records(lines, records, expected):
    rows = [row for row in records if row['data'].get('phase') == PHASE
            or row['data'].get('schema') == 'bsre-current-g36-physical-identity-v1']
    markers = [row for row in records if row['data'].get('phase') == 'pre_wordpress_database']
    need(len(rows) == len(markers) == 2, 'CURRENT_EXACT_TWO_PHYSICAL_IDENTITY_RECEIPTS')
    for number, (row, marker) in enumerate(zip(rows, markers)):
        need(not row['pretty'] and row['line'] == row['end_line'] and list(row['data']) == list(expected)
             and same(row['data'], expected), 'CURRENT_EXACT_PHYSICAL_IDENTITY')
        lower = markers[number - 1]['end_line'] if number else 0
        prior = [item for item in records if lower < item['line'] < marker['line']
                 and item['data'].get('phase') == 'pre_wordpress_isolation']
        need(len(prior) == 1 and prior[0]['end_line'] < row['line'] < marker['line'], 'CURRENT_IDENTITY_AFTER_ISOLATION_BEFORE_DATABASE')
        # No old runtime block or G35->G36 adjacency is interrupted.
        if number:
            end = [item for item in records if lower < item['line'] < row['line']
                   and item['data'].get('phase') == 'g39_local_history']
            need(len(end) == 1, 'CURRENT_SECOND_IDENTITY_AFTER_COMPLETE_FIRST_PROFILE')
    removed = {row['line'] for row in rows}
    retained = [row for row in records if row['line'] not in removed]
    need(len(records) == 460 and len(retained) == 458, 'CURRENT_EXACT460_AND_RETAINED458_DOCUMENTS')
    return rows, retained


def verify_log_metadata(raw, metadata, binding):
    need(metadata['head'] == binding['head'] and metadata['conclusion'] == 'success'
         and metadata['check'] == 'isolated-native-wordpress' and type(metadata['bytes']) is int
         and metadata['bytes'] == len(raw) and metadata['sha256'] == pin(raw)['sha256'], 'CURRENT_RAW_LOG_METADATA_BINDING')


def verify_frozen_candidate_pins(current, restored, expected):
    for path, before in expected.items():
        observed = pin(restored[path]) if path in restored else current[path]
        need(observed == before, 'CURRENT_FROZEN_G39_CANDIDATE_CHANGED:' + path)


@contextmanager
def base_source_view(source, paths, restored):
    # Only an explicit source projection is created; raw logs are never copied or rewritten.
    with tempfile.TemporaryDirectory(prefix='bsre-current-source-') as directory:
        view = Path(directory).resolve()
        for path in sorted(paths):
            target = path_under(view, path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(restored.get(path, read(path_under(source, path))))
        yield view


def prepare(source, head, feature_tree, history, node='node'):
    reviewed = scope()
    need(re.fullmatch('[a-f0-9]{40}', head or '') and re.fullmatch('[a-f0-9]{40}', feature_tree or ''), 'CURRENT_EXACT_HEAD_TREE_REQUIRED')
    budget, old, frozen, baseline = historical(history, reviewed)
    need(budget.git(source, 'rev-parse', 'HEAD').decode().strip() == head
         and budget.git(source, 'rev-parse', head + '^{tree}').decode().strip() == feature_tree, 'CURRENT_SOURCE_HEAD_TREE')
    restored = source_deltas(source, reviewed)
    changed = budget.git(source, 'diff', '--name-status', '--no-renames', reviewed['baseline_head'], head).decode().splitlines()
    changed_paths = []
    for row in changed:
        status, path = row.split('\t')
        need(status in ('A', 'M'), 'CURRENT_UNREVIEWED_DELETION_OR_TYPE_CHANGE')
        changed_paths.append(path)
    inputs = load(read(Path(source) / 'tools/website-tracking/g5-local-history-runtime/SOURCE_PINS.json'))['files']
    needed = set(baseline['source_pins']) | set(inputs) | set(frozen['candidate_pins']) | set(changed_paths)
    needed |= {row['path'] for row in reviewed['new_source_files']} | set(restored)
    current = budget.committed_pins(source, head, needed)
    verify_frozen_candidate_pins(current, restored, frozen['candidate_pins'])
    for path, expected in baseline['source_pins'].items():
        if path not in budget.CI_PATHS:
            need(pin(restored[path]) == expected if path in restored else current[path] == expected,
                 'CURRENT_UNDECLARED_HISTORICAL_SOURCE_CHANGE:' + path)
    with base_source_view(source, needed, restored) as view:
        inverses, _ = budget.inverse_files(view, frozen, baseline)
        inverses.update(restored)
        # CI paths additionally undo the original reviewed budget30/G39 deltas.
        old_ci, _ = budget.inverse_files(view, frozen, baseline)
        inverses.update(old_ci)
        with budget.retained_source_view(source, baseline, inverses) as retained:
            old.source_binding(retained, baseline)
    derived = derive(source, reviewed, node)
    return {'schema': 'bsre-current-exact-native-binding-v1', 'head': head, 'feature_tree': feature_tree,
            'scope_sha256': SCOPE_SHA256, 'source_pins': current, 'changed_paths': sorted(changed_paths),
            'explicit_source_inverse_paths': sorted(restored), 'historical_source_assertions': 186,
            'historical_candidate_source_assertions': len(frozen['candidate_pins']),
            'expected_receipt': derived['expected_receipt'], 'native_executed': False,
            'acceptance': 'PREPARED_ONLY_ACTUAL_CURRENT_NATIVE_LOG_REQUIRED'}


def audit(log, metadata, merge_tree, source, binding, history, node='node'):
    reviewed = scope()
    raw = read(log, 16 * 1024 * 1024)
    verify_log_metadata(raw, load(read(metadata)), binding)
    current = prepare(source, binding['head'], binding['feature_tree'], history, node)
    need(same(current, binding), 'CURRENT_REVISION_BINDING_CHANGED')
    budget, old, frozen, baseline = historical(history, reviewed)
    need(read(log, old.g38.fc6.MAX_LOG) == raw, 'CURRENT_RAW_LOG_CHANGED_BEFORE_SCAN')
    lines, records = old.scan(raw)
    identities, retained_records = validate_identity_records(lines, records, current['expected_receipt'])
    restored = source_deltas(source, reviewed)
    with base_source_view(source, set(current['source_pins']), restored) as view:
        historical_inverses, _ = budget.inverse_files(view, frozen, baseline)
        historical_inverses.update({path: raw for path, raw in restored.items() if path not in budget.CI_PATHS})
        original_prepare, original_predecessor, original_inverse = budget.prepare, budget.predecessor, budget.inverse_files
        original_scan = old.scan
        try:
            # Every replacement is explicit: current committed binding, exact source
            # inverses, and ONLY the two independently validated identity documents.
            budget.prepare = lambda current_source, head, tree: prepare(current_source, head, tree, history, node)
            budget.predecessor = lambda frozen_value: old
            budget.inverse_files = lambda current_source, frozen_value, expected: (historical_inverses, inputs_for(old, view))
            old.scan = lambda value: (lines, retained_records) if value == raw else original_scan(value)
            preserved = budget.audit(log, metadata, merge_tree, source, current)
        finally:
            budget.prepare, budget.predecessor, budget.inverse_files = original_prepare, original_predecessor, original_inverse
            old.scan = original_scan
    need(read(log, old.g38.fc6.MAX_LOG) == raw, 'CURRENT_RAW_LOG_CHANGED')
    need(same(prepare(source, binding['head'], binding['feature_tree'], history, node), binding), 'CURRENT_SOURCE_CHANGED')
    return {'schema': 'bsre-current-native-log-audit-v1', 'status': 'PASS_CURRENT_NATIVE_ENGINEERING_ONLY',
            'head': binding['head'], 'feature_tree': binding['feature_tree'], 'raw_log': pin(raw),
            'complete_json_documents': 460, 'new_physical_identity_receipts': len(identities),
            'retained_budget30_documents': 458, 'retained_predecessor_documents': 454,
            'current_committed_source_bindings': len(binding['source_pins']), 'historical_source_assertions': 186,
            'explicit_source_inverse_paths': sorted(restored), 'current_physical_identity': current['expected_receipt'],
            'frozen_budget30_assertions': preserved, 'raw_log_rewritten': False,
            'historical_acceptance_relabelled_as_current': False, 'all_prior_behavior_assertions_retained': True,
            'native_executed_by_auditor': False, 'provider_human_production_accepted': False}


def inputs_for(old, view):
    return load(read(view / 'tools/website-tracking/g5-local-history-runtime/SOURCE_PINS.json'))['files']


def comparison_path(value):
    path = Path(value).resolve()
    if os.name == 'nt':
        text = str(path)
        if text.startswith('\\\\?\\UNC\\'):
            path = Path('\\\\' + text[8:])
        elif text.startswith('\\\\?\\'):
            path = Path(text[4:])
    return path


def output_target(output, source, history, inputs=()):
    if os.name == 'nt':
        # Check BEFORE absolute()/resolve(): Windows can normalize trailing
        # dots/spaces, and Python 3.12 has no os.path.isreserved().
        raw_name = os.fspath(output).replace('/', '\\')
        need(not raw_name.startswith(('\\\\?\\', '\\\\.\\', '\\??\\')), 'CURRENT_OUTPUT_RESERVED_NAMESPACE')
        tail = os.path.splitdrive(raw_name)[1]
        for part in re.split(r'[\\/]', tail):
            if part in ('', '.', '..'):
                continue
            device = part.split('.', 1)[0].rstrip(' ').upper()
            need(not re.search(r'[:*?"<>|\x00-\x1f]', part) and not part.endswith(('.', ' '))
                 and not re.fullmatch(r'CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|(?:COM|LPT)[1-9¹²³]', device),
                 'CURRENT_OUTPUT_RESERVED_NAME')
    target = Path(output).absolute()
    resolved = comparison_path(target)
    for root in (comparison_path(source), comparison_path(history)):
        need(resolved != root and root not in resolved.parents, 'CURRENT_OUTPUT_PROTECTED_ROOT')
    need(all(resolved != comparison_path(path) for path in inputs if path), 'CURRENT_OUTPUT_INPUT_ALIAS')
    for path in (target, *target.parents):
        need(not path.is_symlink() and not getattr(path, 'is_junction', lambda: False)(), 'CURRENT_OUTPUT_LINK')
    need(not os.path.lexists(target), 'CURRENT_OUTPUT_EXISTS')
    need(target.parent.is_dir(), 'CURRENT_OUTPUT_PARENT_REQUIRED')
    return resolved


@contextmanager
def anchored_output_parent(target):
    """Keep intermediate links from redirecting creation after pathname checks."""
    handles = []
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        create = kernel.CreateFileW
        create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        create.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        class TagInfo(ctypes.Structure):
            _fields_ = [('attributes', wintypes.DWORD), ('tag', wintypes.DWORD)]
        info = kernel.GetFileInformationByHandleEx
        info.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
        info.restype = wintypes.BOOL
        try:
            for path in (*reversed(target.parent.parents), target.parent):
                # FILE_LIST_DIRECTORY registers read sharing. Attributes-only
                # access would not prevent a concurrent directory deletion.
                # Sharing read only prevents write/reparse-point/rename/delete
                # changes to every ancestor until the output handle is closed.
                handle = create(str(path), 0x81, 1, None, 3, 0x02200000, None)
                if handle == ctypes.c_void_p(-1).value:
                    raise ctypes.WinError(ctypes.get_last_error())
                handles.append(handle)
                tag = TagInfo()
                if not info(handle, 9, ctypes.byref(tag), ctypes.sizeof(tag)):
                    raise ctypes.WinError(ctypes.get_last_error())
                need(tag.attributes & 0x10 and not tag.tag & 0x20000000, 'CURRENT_OUTPUT_ANCESTOR_LINK')
            yield None
        finally:
            for handle in reversed(handles):
                kernel.CloseHandle(handle)
    else:
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        try:
            handles.append(os.open(target.anchor, flags))
            for part in target.parent.parts[1:]:
                handles.append(os.open(part, flags, dir_fd=handles[-1]))
            yield handles[-1]
        finally:
            for handle in reversed(handles):
                os.close(handle)


def exclusive_private_fd(target, parent_fd=None):
    if os.name != 'nt':
        name = target.name if parent_fd is not None else target
        return os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent_fd)
    # Windows os.open(mode=0600) does not create an owner-only NTFS DACL.
    # Apply a protected Owner Rights ACL atomically with CREATE_NEW instead.
    import ctypes
    from ctypes import wintypes
    import msvcrt
    class SecurityAttributes(ctypes.Structure):
        _fields_ = [('length', wintypes.DWORD), ('descriptor', wintypes.LPVOID), ('inherit', wintypes.BOOL)]
    advapi = ctypes.WinDLL('advapi32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    convert = advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW
    convert.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(wintypes.LPVOID), wintypes.LPVOID]
    convert.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [wintypes.LPVOID]
    create = kernel.CreateFileW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(SecurityAttributes), wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    descriptor = wintypes.LPVOID()
    if not convert('D:P(A;;FA;;;OW)', 1, ctypes.byref(descriptor), None):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        attributes = SecurityAttributes(ctypes.sizeof(SecurityAttributes), descriptor, False)
        handle = create(str(target), 0x40000000, 0, ctypes.byref(attributes), 1, 0x00200080, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            return msvcrt.open_osfhandle(handle, os.O_WRONLY | os.O_BINARY)
        except BaseException:
            kernel.CloseHandle(handle)
            raise
    finally:
        kernel.LocalFree(descriptor)


def write_output(output, result, source, history, inputs=()):
    # Recheck after expensive work, then let exclusive creation arbitrate any
    # newly occupied name. A partial failed output remains evidence, not a retry.
    target = output_target(output, source, history, inputs)
    raw = (json.dumps(result, indent=2, sort_keys=True) + '\n').encode('utf-8')
    with anchored_output_parent(target) as parent_fd:
        output_target(target, source, history, inputs)
        with os.fdopen(exclusive_private_fd(target, parent_fd), 'wb') as stream:
            stream.write(raw)
            if parent_fd is not None:
                pinned, current = os.fstat(parent_fd), target.parent.stat(follow_symlinks=False)
                need((pinned.st_dev, pinned.st_ino) == (current.st_dev, current.st_ino), 'CURRENT_OUTPUT_PARENT_CHANGED')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['prepare', 'audit'])
    for name in ['source', 'history', 'head', 'tree', 'output']:
        parser.add_argument('--' + name, required=True)
    for name in ['log', 'metadata', 'merge-tree', 'binding']:
        parser.add_argument('--' + name)
    parser.add_argument('--node', default='node')
    args = parser.parse_args()
    input_files = [args.log, args.metadata, args.merge_tree, args.binding,
                   __file__, OWN / 'CURRENT_SCOPE.json', OWN / 'derive-current.mjs']
    target = output_target(args.output, args.source, args.history, input_files)
    if args.operation == 'prepare':
        result = prepare(args.source, args.head, args.tree, args.history, args.node)
    else:
        need(all(getattr(args, name) for name in ['log', 'metadata', 'merge_tree', 'binding']), 'CURRENT_AUDIT_ARGUMENTS')
        binding = load(read(args.binding))
        need(binding['head'] == args.head and binding['feature_tree'] == args.tree, 'CURRENT_CLI_BINDING')
        result = audit(args.log, args.metadata, args.merge_tree, args.source, binding, args.history, args.node)
    write_output(target, result, args.source, args.history, input_files)
    print(json.dumps({key: result[key] for key in ['schema', 'head', 'feature_tree']}))


if __name__ == '__main__':
    main()

"""Explicit two-profile test tool. Foundation selection and scheduler are unchanged."""
from __future__ import annotations
import argparse
from copy import deepcopy
from datetime import date, datetime, timezone
import hashlib
import importlib.util
from importlib.machinery import SourceFileLoader
import inspect
import io
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import types
import unittest
import uuid

class SourceOnlyLoader(SourceFileLoader):
    """Compile bound source directly; neither read nor write cached bytecode."""
    def get_code(self, fullname):
        filename = self.get_filename(fullname)
        with open(filename, 'rb') as stream: raw = stream.read(1048577)
        if len(raw) > 1048576: raise ImportError('FOCUSED_SOURCE_CODE_BOUND_EXCEEDED')
        return self.source_to_code(raw, filename)


def source_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path, loader=SourceOnlyLoader(name, str(path)))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


CODEC = source_module('fresh_history_codec', Path(__file__).resolve().with_name('fresh_history_codec.py'))

TOOL_DIR = Path(__file__).resolve().parent
ROOT = TOOL_DIR.parents[1]
SOURCE = ROOT
OUT = None
PROFILE = None
WHEN = date(2026, 11, 13)
MODULES = {'test_pest_commercial_services_admission': ('PestCommercialServicesAdmissionTests', 19),
           'test_pool_sprinkler_admission': ('PoolSprinklerAdmissionTests', 20)}
SCHEMA = 'bsre-focused-keyword-fixture-v1'
ATTEMPT = 1
PROFILE_SHA256 = 'd30077c011a1d16f9f5c448ad5b1f081b64ddf339adbc911a0d708fd7a4fb118'


class Hold(ValueError):
    pass

def need(ok, code):
    if not ok:
        raise Hold(code)

def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def put(name, value):
    target = OUT / name
    target.write_bytes(encoded(value) + b'\n')

def sample(phase, started, **fields):
    row = {'phase': phase, 'attempt': ATTEMPT, 'elapsed_seconds': round(time.perf_counter() - started, 6), 'retrieved_at_utc': datetime.now(timezone.utc).isoformat(), **fields}
    with (OUT / 'samples.jsonl').open('ab') as handle:
        handle.write(encoded(row) + b'\n')
        handle.flush()
        os.fsync(handle.fileno())
    return row

def import_selected():
    install_source_finder()
    sys.path.insert(0, str(SOURCE / 'tools/keyword-system'))
    modules = {name: __import__(name) for name in MODULES}
    import current_negative_library as current
    import append_only_admission as stage
    import pest_commercial_services_admission as pest
    import pool_sprinkler_admission as pool
    import ofqual_admission as ofqual
    path = SOURCE / 'tools/efficiency/keyword_resources.py'
    spec = importlib.util.spec_from_file_location('private_keyword_resources', path, loader=SourceOnlyLoader('private_keyword_resources', str(path)))
    resources = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(resources)
    return (modules, current, stage, pest, pool, ofqual, resources)

def runtime_identity(expected_files=None):
    files = set(expected_files or [])
    if expected_files is None:
        files.update((str(Path(sys.executable).resolve()), str(Path(sys._base_executable).resolve())))
        base = Path(sys.base_prefix)
        files.update((str(p.resolve()) for p in base.glob('python3*.dll')))
        for name, module in list(sys.modules.items()):
            filename = getattr(module, '__file__', None)
            if filename:
                p = Path(filename)
                if p.is_file() and p.resolve().is_relative_to(base.resolve()):
                    files.add(str(p.resolve()))
    file_hashes = {name: file_sha(Path(name)) for name in sorted(files)}
    return {'version': sys.version, 'implementation': platform.python_implementation(), 'platform': sys.platform, 'machine': platform.machine(), 'files': file_hashes, 'runtime_sha256': sha(encoded(file_hashes))}

def ids(suite):
    if isinstance(suite, unittest.TestSuite):
        return [name for child in suite for name in ids(child)]
    return [suite.id()]

def constant_view(value):
    if isinstance(value, types.CodeType):
        return code_view(value)
    if isinstance(value, bytes):
        return {'bytes': value.hex()}
    if value is Ellipsis:
        return {'ellipsis': True}
    if isinstance(value, Path):
        return {'path': str(value)}
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    if isinstance(value, (tuple, list)):
        return [constant_view(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return {'set': sorted((constant_view(v) for v in value), key=lambda v: encoded(v))}
    if isinstance(value, dict):
        return {str(k): constant_view(v) for k, v in value.items()}
    raise TypeError(type(value).__name__)

def code_view(code):
    return {name: constant_view(getattr(code, name)) for name in ('co_argcount', 'co_posonlyargcount', 'co_kwonlyargcount', 'co_nlocals', 'co_stacksize', 'co_flags', 'co_code', 'co_consts', 'co_names', 'co_varnames', 'co_filename', 'co_name', 'co_qualname', 'co_firstlineno', 'co_linetable', 'co_exceptiontable', 'co_freevars', 'co_cellvars')}

def function_view(function):
    return {'module': function.__module__, 'qualname': function.__qualname__, 'code': code_view(function.__code__), 'defaults': constant_view(function.__defaults__), 'kwdefaults': constant_view(function.__kwdefaults__), 'closure': [constant_view(cell.cell_contents) for cell in function.__closure__ or ()]}

class FunctionGuard:
    """Semantic producer guard only at fresh-fixture boundaries, never per case."""

    def __init__(self):
        self.functions = []
        self.constants = []
        self.aliases = []
        for module in list(sys.modules.values()):
            filename = getattr(module, '__file__', None)
            if not filename or not Path(filename).resolve().is_relative_to(SOURCE / 'tools/keyword-system') or module.__name__.startswith('test_') or (module.__name__ in {'pest_commercial_services_admission', 'pool_sprinkler_admission'}):
                continue
            for name, value in list(vars(module).items()):
                if inspect.isfunction(value) and value.__module__ == module.__name__:
                    self.functions.append((module, name, sha(encoded(function_view(value)))))
                elif isinstance(value, types.ModuleType):
                    self.aliases.append((module, name, value.__name__, getattr(value, '__file__', None)))
                if name.isupper() and (not name.startswith('_')):
                    try:
                        self.constants.append((module, name, sha(encoded(constant_view(value)))))
                    except (TypeError, ValueError):
                        pass

    def check(self):
        for owner, name, digest in self.functions:
            current = vars(owner).get(name)
            need(inspect.isfunction(current) and current.__globals__ is vars(owner) and (sha(encoded(function_view(current))) == digest), 'FUNCTION_MONKEYPATCH_OR_CODE_DRIFT:' + getattr(owner, '__name__', type(owner).__name__) + '.' + name)
        for owner, name, module_name, filename in self.aliases:
            current = vars(owner).get(name)
            need(isinstance(current, types.ModuleType) and current.__name__ == module_name and (getattr(current, '__file__', None) == filename), 'MODULE_ALIAS_DRIFT')
        for owner, name, digest in self.constants:
            need(sha(encoded(constant_view(vars(owner)[name]))) == digest, 'DEPENDENCY_CONSTANT_DRIFT')

    def manifest(self):
        return {'functions': {owner.__name__ + ':' + name: digest for owner, name, digest in self.functions}, 'constants': {owner.__name__ + ':' + name: digest for owner, name, digest in self.constants}, 'module_aliases': {owner.__name__ + ':' + name: [module_name, filename] for owner, name, module_name, filename in self.aliases}}

def assert_apis(modules, ofqual):
    need(sys.version_info[:2] == (3, 12), 'REVIEWED_AST_REQUIRES_PYTHON312')
    reviewed = ofqual.first.pinned(SOURCE, ofqual.FOLDER + '/review.json', ofqual.REVIEW_PIN)
    need(ofqual.implementation_binding(SOURCE) == reviewed['implementation'], 'ORIGINAL_AST_BINDING_CHANGED')
    found = {}
    for name, (class_name, count) in MODULES.items():
        cls = getattr(modules[name], class_name)
        need(vars(cls)['FRESH_BASE'] is None and vars(cls)['FRESH_INPUTS'] is None, 'FRESH_API_PRESET')
        source = inspect.getsource(cls.setUpClass.__func__)
        need('cls.FRESH_BASE if cls.FRESH_BASE is not None' in source and 'cls.FRESH_INPUTS if cls.FRESH_INPUTS is not None' in source and ('e.load_reviewed' in source) and ('e.extend' in source), 'FRESH_API_CHANGED')
        found[name] = ids(unittest.defaultTestLoader.loadTestsFromModule(modules[name]))
        need(len(found[name]) == count and len(set(found[name])) == count, 'CASE_IDENTITY_CHANGED')
    return found

def prepare():
    started = time.perf_counter()
    binding = json.loads(read_bounded(OUT / 'binding.json', 4 * 1024 * 1024))
    modules, current, stage, pest, pool, ofqual, resources = import_selected()
    assert_apis(modules, ofqual)
    binding_check(binding)
    guard = FunctionGuard()
    pest_state, _report = current._fresh_pest_commercial_services_state(SOURCE, WHEN)
    trade = stage.recover_base(pest_state, stage_key=pest.STAGE_KEY)
    need(stage.digest(trade) == pest.BASE_SHA256 and stage.digest(pest_state) == pool.BASE_SHA256, 'FRESH_BASE_DIGEST_CHANGED')
    raw = CODEC.dumps({'schema': SCHEMA, 'run_id': binding['run_id'], 'when': binding['when'], 'source_manifest_sha256': binding['source']['manifest_sha256'], 'runtime_sha256': binding['runtime']['runtime_sha256'], 'pest_state': pest_state})
    (OUT / 'fresh-fixture.json').write_bytes(raw)
    restored = CODEC.loads(raw)['pest_state']
    roundtrip = {'pest': stage.digest(restored), 'trade': stage.digest(stage.recover_base(restored, stage_key=pest.STAGE_KEY))}
    put('fixture-binding.json', {'schema': SCHEMA, 'run_id': binding['run_id'], 'fixture_sha256': sha(raw), 'bytes': len(raw), 'roundtrip_digests': roundtrip, 'release_authorized': False, 'contains_current_test_results': False})
    row = sample('fixture_creation', started, status='OBSERVED', fixture_bytes=len(raw), fixture_sha256=sha(raw), roundtrip_digests=roundtrip, resources=resources.observe())
    need(roundtrip == {'pest': pool.BASE_SHA256, 'trade': pest.BASE_SHA256}, 'SERIALIZATION_CHANGED_BASE')
    guard.check()
    binding_check(binding)
    put('fixture_creation.json', row)

class Observed(unittest.TextTestResult):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.terminal = []
        self.started_ids = []
        self.stopped_ids = []
        self.case_ticks = {}

    def startTest(self, test):
        cls = type(test)
        test.base, test.inputs, test.material = deepcopy((cls.base, cls.inputs, cls.material))
        need(test.base is not cls.base and test.inputs is not cls.inputs and (test.material is not cls.material), 'CASE_MUTATION_ISOLATION_FAILED')
        self.case_ticks[test.id()] = time.perf_counter()
        self.started_ids.append(test.id())
        super().startTest(test)

    def stopTest(self, test):
        elapsed = time.perf_counter() - self.case_ticks[test.id()]
        with (OUT / ('case-events-' + ARGS.arm + '-' + ARGS.module + '.jsonl')).open('ab') as handle:
            handle.write(encoded({'id': test.id(), 'elapsed_seconds': round(elapsed, 6)}) + b'\n')
            handle.flush()
        self.stopped_ids.append(test.id())
        super().stopTest(test)

    def addSuccess(self, test):
        self.terminal.append([test.id(), 'success'])
        super().addSuccess(test)

    def addFailure(self, test, err):
        self.terminal.append([test.id(), 'failure'])
        super().addFailure(test, err)

    def addError(self, test, err):
        self.terminal.append([test.id(), 'error'])
        super().addError(test, err)

    def addSkip(self, test, reason):
        self.terminal.append([test.id(), 'skip'])
        super().addSkip(test, reason)

def worker(arm, name):
    started = time.perf_counter()
    binding = json.loads(read_bounded(OUT / 'binding.json', 4 * 1024 * 1024))
    modules, current, stage, pest, pool, ofqual, resources = import_selected()
    assert_apis(modules, ofqual)
    binding_check(binding)
    cls = getattr(modules[name], MODULES[name][0])
    fixture_info = None
    if arm == 'optimized':
        raw = read_bounded(OUT / 'fresh-fixture.json', 128 * 1024 * 1024)
        fixture_info = json.loads(read_bounded(OUT / 'fixture-binding.json', 65536))
        need(fixture_info['run_id'] == binding['run_id'] and sha(raw) == fixture_info['fixture_sha256'], 'FIXTURE_BYTES_OR_RUN_CHANGED')
        fixture = CODEC.loads(raw)
        need(fixture['run_id'] == binding['run_id'] and fixture['when'] == binding['when'] and (fixture['source_manifest_sha256'] == binding['source']['manifest_sha256']) and (fixture['runtime_sha256'] == binding['runtime']['runtime_sha256']), 'FIXTURE_BINDING_CHANGED')
        pest_state = fixture['pest_state']
        need(stage.digest(pest_state) == pool.BASE_SHA256, 'PEST_FIXTURE_BODY_CHANGED')
        trade = stage.recover_base(pest_state, stage_key=pest.STAGE_KEY)
        need(stage.digest(trade) == pest.BASE_SHA256, 'TRADE_FIXTURE_BODY_CHANGED')
        cls.FRESH_BASE = deepcopy(trade if name == 'test_pest_commercial_services_admission' else pest_state)
        need(cls.FRESH_INPUTS is None, 'OWN_STAGE_BYPASSED')
        del fixture, pest_state, trade, raw
    guard = FunctionGuard()
    guard.check()
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromModule(modules[name])
    need(ids(suite) == binding['cases'][name], 'CASE_SET_CHANGED')
    tick = time.perf_counter()
    result = unittest.TextTestRunner(stream=stream, verbosity=1, resultclass=Observed).run(suite)
    run_seconds = time.perf_counter() - tick
    row = sample(arm + ':' + name, started, status='OBSERVED', unittest_seconds=round(run_seconds, 6), tests=result.testsRun, terminal=result.terminal, started_ids=result.started_ids, stopped_ids=result.stopped_ids, failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped), original_stage_extend_executed_via_unmodified_setup=True, fresh_inputs_none=cls.FRESH_INPUTS is None, resources=resources.observe(), successful=result.wasSuccessful())
    (OUT / (arm + '-' + name + '.log')).write_text(stream.getvalue(), encoding='utf-8')
    put(arm + '-' + name + '.json', row)
    guard.check()
    binding_check(binding)
    expected = binding['cases'][name]
    need(result.testsRun == len(expected) and result.started_ids == expected and (result.stopped_ids == expected) and (result.terminal == [[case, 'success'] for case in expected]) and result.wasSuccessful() and (not result.skipped), 'INCOMPLETE_OR_FAILED_ORIGINAL_CASES')

def load_profile(name='pest-pool-v1'):
    need(name == 'pest-pool-v1', 'UNSUPPORTED_FOCUSED_PROFILE')
    raw = read_bounded(TOOL_DIR / 'focused-keyword-profiles-v1.json', 1048576)
    need(sha(raw) == PROFILE_SHA256, 'FOCUSED_PROFILE_CHANGED')
    profile = json.loads(raw)
    need(profile['schema'] == 'bsre-focused-keyword-profiles-v1' and profile['date'] == WHEN.isoformat()
         and set(profile['cases']) == set(MODULES), 'FOCUSED_PROFILE_INVALID')
    return profile


def read_bounded(path, limit):
    with Path(path).open('rb') as stream: raw = stream.read(limit + 1)
    need(len(raw) <= limit, 'FOCUSED_FILE_BOUND_EXCEEDED')
    return raw


def file_sha(path, limit=128 * 1024 * 1024):
    digest = hashlib.sha256(); total = 0
    with Path(path).open('rb') as stream:
        while True:
            block = stream.read(min(65536, limit - total + 1))
            if not block: break
            total += len(block); need(total <= limit, 'FOCUSED_FILE_BOUND_EXCEEDED'); digest.update(block)
    return digest.hexdigest()


def source_snapshot():
    need(PROFILE is not None, 'FOCUSED_PROFILE_REQUIRED')
    entries = {}
    need(sum(row['bytes'] for row in PROFILE['files'].values()) <= 256 * 1024 * 1024, 'FOCUSED_CORPUS_BOUND_EXCEEDED')
    for name, expected in sorted(PROFILE['files'].items()):
        relative = Path(name)
        need(not relative.is_absolute() and '..' not in relative.parts, 'FOCUSED_PATH_INVALID')
        path = SOURCE / relative
        cursor = path
        while cursor != SOURCE:
            need(not cursor.is_symlink() and not cursor.is_junction(), 'FOCUSED_PATH_LINKED')
            cursor = cursor.parent
        need(type(expected['bytes']) is int and 0 <= expected['bytes'] <= 64 * 1024 * 1024, 'FOCUSED_FILE_BOUND_EXCEEDED')
        raw = read_bounded(path, expected['bytes']); digest = sha(raw)
        need(len(raw) == expected['bytes'] and digest == expected['sha256'], 'FOCUSED_INPUT_CHANGED')
        entries[name] = [len(raw), digest]
    return {'files': entries, 'manifest_sha256': sha(encoded(entries)),
            'file_count': len(entries), 'bytes': sum(row[0] for row in entries.values())}


def tool_files():
    names = ('focused_keyword_fixture.py', 'fresh_history_codec.py', 'focused-keyword-profiles-v1.json', 'owned_process.py')
    return {name: file_sha(TOOL_DIR / name, 1048576) for name in names}


def binding_check(binding):
    need(binding['schema'] == SCHEMA and binding['when'] == WHEN.isoformat(), 'BINDING_DATE_OR_SCHEMA')
    need(binding['source_root'] == str(SOURCE) and binding['run_dir'] == str(OUT), 'RUN_PATH_CHANGED')
    need(binding['tool_files'] == tool_files(), 'FOCUSED_TOOL_CODE_CHANGED')
    validate_loaded_sources()
    need(source_snapshot() == binding['source'], 'SOURCE_OR_INPUT_DRIFT')
    need(runtime_identity(binding['runtime']['files']) == binding['runtime'], 'RUNTIME_DRIFT')
    guard = FunctionGuard(); guard.check(); actual = guard.manifest()
    for group, entries in binding['producer_semantics'].items():
        need(all(actual[group].get(key) == value for key, value in entries.items()), 'BOUND_PRODUCER_SEMANTICS_CHANGED')


def inspect_current():
    snapshot = source_snapshot()
    modules, current, stage, pest, pool, ofqual, resources = import_selected()
    validate_loaded_sources()
    need(assert_apis(modules, ofqual) == PROFILE['cases'], 'ORIGINAL_CASE_SET_CHANGED')
    guard = FunctionGuard(); guard.check()
    return snapshot, runtime_identity(), guard.manifest(), resources.observe()


def validate_loaded_sources():
    for name in PROFILE['files']:
        part = Path(name)
        if name.startswith('tools/keyword-system/') and part.suffix == '.py':
            loaded = sys.modules.get(part.stem)
            if loaded is not None:
                need(Path(str(getattr(loaded, '__file__', ''))).resolve() == (SOURCE / part).resolve(), 'LOADED_FOCUSED_SOURCE_CHANGED')


class BoundSourceFinder:
    def __init__(self, root, files):
        self.root, self.files = root, frozenset(files)

    def find_spec(self, fullname, path=None, target=None):
        if '.' in fullname: return None
        relative = 'tools/keyword-system/' + fullname + '.py'
        if relative not in self.files: return None
        filename = self.root / relative
        return importlib.util.spec_from_file_location(fullname, filename, loader=SourceOnlyLoader(fullname, str(filename)))


def install_source_finder():
    for name in PROFILE['files']:
        part = Path(name)
        if name.startswith('tools/keyword-system/') and part.suffix == '.py':
            loaded = sys.modules.get(part.stem)
            if loaded is not None:
                need(isinstance(getattr(loaded, '__loader__', None), SourceOnlyLoader), 'PRELOADED_FOCUSED_BYTECODE_UNVERIFIED')
    if not any(isinstance(finder, BoundSourceFinder) and finder.root == SOURCE for finder in sys.meta_path):
        sys.meta_path.insert(0, BoundSourceFinder(SOURCE, PROFILE['files']))


def create_run(directory):
    target = Path(directory).resolve()
    need(not target.exists(), 'FRESH_RUN_DIRECTORY_REQUIRED')
    target.mkdir(parents=True)
    return target


READ_PATHS = set()
DENIED_READS = []


def install_boundary():
    allowed_tools = {str((TOOL_DIR / name).resolve()) for name in
        ('focused_keyword_fixture.py', 'fresh_history_codec.py', 'focused-keyword-profiles-v1.json', 'owned_process.py')}
    runtime_roots = (Path(sys.base_prefix).resolve(), Path(sys.prefix).resolve())
    metadata = {'/proc/meminfo', '/sys/fs/cgroup/memory.max', '/sys/fs/cgroup/memory.current', '/sys/fs/cgroup/cpu.max'}
    def boundary(event, arguments):
        if event != 'open' or not arguments or not isinstance(arguments[0], (str, bytes, os.PathLike)):
            return
        path = Path(os.fsdecode(arguments[0])).resolve()
        if OUT is not None and path.is_relative_to(OUT):
            return
        mode = arguments[1] if len(arguments) > 1 else ''
        flags = arguments[2] if len(arguments) > 2 else 0
        writes = (isinstance(mode, str) and any(letter in mode for letter in 'wax+')) or (
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR))
        if writes:
            DENIED_READS.append('OUTSIDE_RUN_WRITE'); raise Hold('OUTSIDE_FOCUSED_RUN_WRITE_DENIED')
        if str(path) in allowed_tools or any(path.is_relative_to(root) for root in runtime_roots) or str(path) in metadata:
            return
        if path.is_relative_to(SOURCE):
            name = path.relative_to(SOURCE).as_posix()
            if name in PROFILE['files']:
                READ_PATHS.add(name); return
        if not path.exists():
            return  # Normal failed import-cache probes convey no bytes.
        if os.path.normcase(str(path)) == os.path.normcase(os.devnull):
            return
        DENIED_READS.append('UNBOUND_INPUT'); raise Hold('UNBOUND_FOCUSED_INPUT_DENIED')
    sys.addaudithook(boundary)


def support_module():
    path = TOOL_DIR / 'owned_process.py'
    need(file_sha(path, 1048576) == PROFILE['support_pins']['owned_process.py'], 'OWNED_PROCESS_IMPLEMENTATION_CHANGED')
    spec = importlib.util.spec_from_file_location('focused_owned_process', path, loader=SourceOnlyLoader('focused_owned_process', str(path)))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def consume_gate(gate_name):
    gate = json.loads(sys.stdin.buffer.readline(512))
    deadline = gate.get('deadline')
    need(gate.get('gate') == gate_name and type(deadline) in (int, float)
         and math.isfinite(deadline) and deadline > time.monotonic(), 'OWNED_STARTUP_GATE_REQUIRED')
    return deadline


def invoke_phase(phase, support):
    started = time.perf_counter()
    args = [sys.executable, '-B', str(Path(__file__).resolve()), '--root', str(SOURCE), '--_run-dir', str(OUT), '--_phase', phase]
    text_output = text_error = ''
    try:
        result = support.run_owned(args, cwd=SOURCE, timeout=240)
        text_output, text_error = result.stdout, result.stderr
        outcome = {'exit': result.returncode}
    except subprocess.TimeoutExpired as error:
        text_output, text_error = error.stdout or '', error.stderr or ''
        outcome = {'exit': None, 'timed_out': True}
    except OSError as error:
        outcome = {'exit': None, 'error_type': type(error).__name__}
    if isinstance(text_output, bytes): text_output = text_output.decode('utf-8', errors='replace')
    if isinstance(text_error, bytes): text_error = text_error.decode('utf-8', errors='replace')
    log = 'phase-' + phase + '.log'
    (OUT / log).write_text(text_output + text_error, encoding='utf-8')
    row = sample('phase:' + phase, started, timeout_seconds=240, log=log,
                 stdout_bytes=len(text_output.encode()), stderr_bytes=len(text_error.encode()), **outcome)
    put('phase-' + phase + '-status.json', row)
    need(outcome.get('exit') == 0, 'FOCUSED_PHASE_HELD:' + phase)
    return row


def main(argv=None):
    global SOURCE, ROOT, OUT, PROFILE, ARGS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=TOOL_DIR.parents[1])
    parser.add_argument('--profile', default='pest-pool-v1')
    parser.add_argument('--inspect', action='store_true')
    parser.add_argument('--output-base', type=Path)
    parser.add_argument('--_run-dir', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--_phase', choices=['prepare', *MODULES], help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    sys.dont_write_bytecode = True
    SOURCE = args.root.resolve(); ROOT = SOURCE
    PROFILE = load_profile(args.profile)
    support = support_module()
    if args._phase:
        deadline = consume_gate(support.GATE)
        need(args._run_dir is not None, 'FRESH_RUN_REQUIRED')
        OUT = args._run_dir.resolve()
        ARGS = types.SimpleNamespace(arm='optimized', module=None if args._phase == 'prepare' else args._phase)
        install_boundary()
        binding = json.loads((OUT / 'binding.json').read_bytes())
        try:
            if args._phase == 'prepare': prepare()
            else: worker('optimized', args._phase)
            need(time.monotonic() < deadline, 'FOCUSED_PHASE_DEADLINE_EXCEEDED')
        finally:
            put('reads-' + args._phase + '.json', {'paths': sorted(READ_PATHS), 'denied': DENIED_READS})
        return 0
    if args.inspect:
        install_boundary()
        snapshot, runtime, semantics, resources = inspect_current()
        print(json.dumps({'scope': 'FOCUSED_TEST_INSPECTION_NOT_ACCEPTANCE', 'status': 'READY',
            'profiles': 2, 'cases': 39, 'source_files': snapshot['file_count'], 'source_manifest_sha256': snapshot['manifest_sha256'],
            'python': platform.python_version(), 'resources': resources, 'release_authorized': False}))
        return 0
    base = (args.output_base or (SOURCE / 'test-output')).resolve()
    OUT = create_run(base / ('focused-keywords-' + uuid.uuid4().hex))
    install_boundary()
    snapshot, runtime, semantics, resources = inspect_current()
    binding = {'schema': SCHEMA, 'run_id': OUT.name, 'when': WHEN.isoformat(), 'source_root': str(SOURCE),
        'run_dir': str(OUT), 'source': snapshot, 'runtime': runtime, 'producer_semantics': semantics,
        'prototype_sha256': sha(Path(__file__).read_bytes()), 'tool_files': tool_files(),
        'cases': PROFILE['cases'], 'resources': resources, 'release_authorized': False}
    put('binding.json', binding)
    phases = [invoke_phase('prepare', support)]
    phases += [invoke_phase(name, support) for name in MODULES]
    complete = [json.loads((OUT / ('optimized-' + name + '.json')).read_bytes()) for name in MODULES]
    need(all(row['successful'] and row['failures'] == row['errors'] == row['skipped'] == 0 for row in complete), 'ORIGINAL_CASES_HELD')
    result = {'scope': 'FOCUSED_TESTS_NOT_FOUNDATION_OR_RELEASE_ACCEPTANCE', 'status': 'PASS', 'modules': 2, 'cases': 39,
        'fresh_fixture_included': True, 'sequential_child_seconds': round(sum(row['elapsed_seconds'] for row in phases), 6),
        'phases': phases, 'release_authorized': False}
    put('focused-result.json', result)
    print(json.dumps({key: value for key, value in result.items() if key != 'phases'}))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (Hold, OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({'scope': 'FOCUSED_TESTS_NOT_ACCEPTANCE', 'status': 'HELD', 'error_type': type(error).__name__,
                          'error_code': str(error) if isinstance(error, Hold) else 'INPUT_RUNTIME_OR_PROTOCOL_FAILURE', 'release_authorized': False}))
        raise SystemExit(1)

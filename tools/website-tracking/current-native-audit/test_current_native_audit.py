"""Falsification/shape tests only. No mock log is accepted as actual native evidence."""
from copy import deepcopy
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
import io
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
import unittest
from unittest.mock import patch

OWN=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('current_audit_under_test',OWN/'audit_current_native.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)


class CurrentAuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scope=audit.scope()
        cls.history=Path(os.environ['BSRE_CURRENT_HISTORY'])
        cls.source=Path(os.environ['BSRE_CURRENT_SOURCE'])
        cls.raw=audit.read(os.environ['BSRE_OLD_LOG'],16*1024*1024)
        cls.metadata=audit.load(audit.read(os.environ['BSRE_OLD_METADATA']))
        cls.budget,cls.old,cls.frozen,cls.baseline=audit.historical(cls.history,cls.scope)
        cls.lines,cls.records=cls.old.scan(cls.raw)

    def test_actual_old_log_is_exact_and_rejected_as_current(self):
        self.assertEqual(audit.pin(self.raw),{'bytes':974155,'sha256':'b535ab5ddf24b40091de75db716b79805bdc526ebe367d4d1333f55dcc6b83c3'})
        self.assertEqual(len(self.records),458)
        with self.assertRaisesRegex(ValueError,'EXACT_TWO_PHYSICAL'):
            audit.validate_identity_records(self.lines,self.records,self.scope['expected_receipt'])

    def fixture(self):
        # Insert new lines into a PRIVATE DIAGNOSTIC fixture. Original raw bytes
        # and metadata remain untouched and cannot authenticate this fixture.
        payload=json.dumps(self.scope['expected_receipt'],separators=(',',':'))
        original=self.raw.decode('utf-8-sig').splitlines(keepends=True)
        markers={row['line'] for row in self.records if row['data'].get('phase')=='pre_wordpress_database'}
        parts=[]
        for number,line in enumerate(original,1):
            if number in markers:parts.append('2026-11-18T00:00:00.0000000Z '+payload+'\n')
            parts.append(line)
        raw=''.join(parts).encode('utf-8')
        return raw,self.old.scan(raw)

    def test_diagnostic_projection_preserves_every_old_document_and_raw_line_order(self):
        raw,(lines,records)=self.fixture()
        identities,retained=audit.validate_identity_records(lines,records,self.scope['expected_receipt'])
        self.assertEqual(len(identities),2);self.assertEqual(len(records),460);self.assertEqual(len(retained),458)
        self.assertEqual([row['data'] for row in retained],[row['data'] for row in self.records])
        self.assertEqual([row['json_sha256'] for row in retained],[row['json_sha256'] for row in self.records])
        with self.assertRaisesRegex(ValueError,'RAW_LOG_METADATA_BINDING'):
            audit.verify_log_metadata(raw,self.metadata,{'head':self.metadata['head']})

    def test_changed_identity_and_boolean_integer_substitution_reject(self):
        _,(lines,records)=self.fixture()
        for mutate in [lambda row:row['bindings'].__setitem__('M','0'*64),
                       lambda row:row.__setitem__('all_site_files_readback_verified',1),
                       lambda row:row.__setitem__('source_members',True),
                       lambda row:row.__setitem__('retention_context',None),
                       lambda row:row['files'][next(iter(row['files']))].__setitem__('sha256','f'*64)]:
            bad=deepcopy(records);target=next(row for row in bad if row['data'].get('phase')==audit.PHASE);mutate(target['data'])
            with self.assertRaisesRegex(ValueError,'EXACT_PHYSICAL_IDENTITY'):
                audit.validate_identity_records(lines,bad,self.scope['expected_receipt'])

    def test_duplicate_missing_or_misplaced_identity_rejects(self):
        _,(lines,records)=self.fixture();identities=[row for row in records if row['data'].get('phase')==audit.PHASE]
        for bad in [records+[deepcopy(identities[0])],[row for row in records if row is not identities[0]]]:
            with self.assertRaisesRegex(ValueError,'EXACT_TWO_PHYSICAL'):
                audit.validate_identity_records(lines,bad,self.scope['expected_receipt'])
        bad=deepcopy(records);target=next(row for row in bad if row['data'].get('phase')==audit.PHASE);target['line']=target['end_line']=1
        with self.assertRaisesRegex(ValueError,'AFTER_ISOLATION_BEFORE_DATABASE'):
            audit.validate_identity_records(lines,bad,self.scope['expected_receipt'])

    def test_tampered_raw_or_wrong_head_cannot_use_old_metadata(self):
        binding={'head':self.metadata['head']}
        audit.verify_log_metadata(self.raw,self.metadata,binding)
        for raw,meta,bound in [(self.raw+b'\n',self.metadata,binding),(self.raw,self.metadata,{'head':'0'*40})]:
            with self.assertRaisesRegex(ValueError,'RAW_LOG_METADATA_BINDING'):
                audit.verify_log_metadata(raw,meta,bound)

    def test_all_declared_current_source_inverses_are_exact(self):
        restored=audit.source_deltas(self.source,self.scope)
        self.assertEqual(len(restored),11)
        self.assertIn("tools/staging-lab/g38/native/g2-retirement-races.php",restored)
        for row in self.scope['source_deltas']:
            self.assertEqual(audit.pin(restored[row['path']]),row['before'])
        composer=self.scope['composer'];raw=audit.read(self.source/composer['path'])
        with self.assertRaisesRegex(ValueError,'DELTA_PIN'):
            audit.restore_delta(raw+b'\n',composer)

    def test_current_context_then_original_four_ci_inverses_preserve_all186_source_assertions(self):
        restored=audit.source_deltas(self.source,self.scope)
        inputs=audit.load(audit.read(self.source/'tools/website-tracking/g5-local-history-runtime/SOURCE_PINS.json'))['files']
        needed=set(self.baseline['source_pins'])|set(inputs)|set(self.frozen['candidate_pins'])|set(restored)
        with audit.base_source_view(self.source,needed,restored) as view:
            inverses,_=self.budget.inverse_files(view,self.frozen,self.baseline)
            inverses.update({path:raw for path,raw in restored.items() if path not in self.budget.CI_PATHS})
            with self.budget.retained_source_view(self.source,self.baseline,inverses) as retained:
                self.old.source_binding(retained,self.baseline)
                self.assertEqual(len(self.baseline['source_pins']),186)

    def test_current_compilation_matches_sealed_receipt_and_exact_four_changes(self):
        derived=audit.derive(self.source,self.scope)
        self.assertEqual(derived['expected_receipt'],self.scope['expected_receipt'])
        self.assertEqual(len(derived['expected_receipt']['files']),4)
        self.assertNotEqual(derived['expected_receipt']['bindings']['M'],'5d8107cb2abc02c493b68290816368d57efae0d30d5d65693660c3c8b504db71')

    def test_all17_frozen_candidate_source_assertions_keep_exact_declared_inverses(self):
        restored=audit.source_deltas(self.source,self.scope)
        current={path:audit.pin(audit.read(self.source/path)) for path in self.frozen['candidate_pins']}
        self.assertEqual(len(current),17)
        self.assertEqual(len(set(current)&set(restored)),4)
        audit.verify_frozen_candidate_pins(current,restored,self.frozen['candidate_pins'])
        bad=deepcopy(current);path=next(path for path in bad if path not in restored);bad[path]['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'FROZEN_G39_CANDIDATE_CHANGED'):
            audit.verify_frozen_candidate_pins(bad,restored,self.frozen['candidate_pins'])

    def test_frozen_auditor_pin_is_checked_before_import(self):
        original=audit.read
        def tamper(path,*args):
            raw=original(path,*args)
            return raw+b'\n' if Path(path).name=='audit_g39.py' else raw
        with patch.object(audit,'read',side_effect=tamper):
            with self.assertRaisesRegex(ValueError,'HISTORICAL_AUDITOR_CHANGED'):
                audit.historical(self.history,self.scope)

    def test_duplicate_json_keys_nonfinite_numbers_and_unsafe_paths_reject(self):
        for raw in [b'{"x":1,"x":2}',b'{"x":NaN}']:
            with self.assertRaises(ValueError):audit.load(raw)
        for path in ['../outside','/absolute','a/../b','a//b']:
            with self.assertRaises(ValueError):audit.path_under(OWN,path)

    @contextmanager
    def committed_git_fixture(self,*,worktree_drift=False,committed_undeclared_drift=False):
        # Only the Git process boundary is synthetic. The accepted committed_pins
        # parser, complete blob framing/worktree equality, source inverses and all
        # historical binding assertions run unchanged. No repository is written.
        inputs=audit.load(audit.read(self.source/'tools/website-tracking/g5-local-history-runtime/SOURCE_PINS.json'))['files']
        changed={row['path']:'M' for row in self.scope['source_deltas']}
        changed.update({row['path']:'A' for row in self.scope['new_source_files']})
        paths=set(self.baseline['source_pins'])|set(inputs)|set(self.frozen['candidate_pins'])|set(changed)
        raw={path:audit.read(self.source/path) for path in paths}
        victim='tools/website-tracking/tracking-system/build-native-frame-candidate.mjs'
        self.assertIn(victim,paths);self.assertNotIn(victim,changed)
        original_read=self.budget.read
        if committed_undeclared_drift:raw[victim]+=b'\n';changed[victim]='M'
        objects={hashlib.sha1(b'blob '+str(len(value)).encode()+b'\0'+value).hexdigest():(path,value) for path,value in raw.items()}
        def git(_source,*args,input_bytes=None):
            if args==('rev-parse','HEAD'):return ('c'*40+'\n').encode()
            if args==('rev-parse','c'*40+'^{tree}'):return ('d'*40+'\n').encode()
            if args[:3]==('diff','--name-status','--no-renames'):
                return ''.join(status+'\t'+path+'\n' for path,status in sorted(changed.items())).encode()
            if args==('ls-tree','-r','-z','c'*40):
                return b''.join(('100644 blob '+oid+'\t'+path).encode()+b'\0' for oid,(path,_) in objects.items())
            if args==('cat-file','--batch'):
                return b''.join((oid+' blob '+str(len(objects[oid][1]))+'\n').encode()+objects[oid][1]+b'\n' for oid in input_bytes.decode().splitlines())
            raise AssertionError(args)
        def read(path,*args):
            value=original_read(path,*args)
            if Path(path)==self.source/victim and (worktree_drift or committed_undeclared_drift):return value+b'\n'
            return value
        with patch.object(audit,'historical',return_value=(self.budget,self.old,self.frozen,self.baseline)),patch.object(self.budget,'git',side_effect=git),patch.object(self.budget,'read',side_effect=read):
            yield

    def test_prepare_runs_real_committed_blob_parser_and_all_explicit_inverses(self):
        with self.committed_git_fixture():
            result=audit.prepare(self.source,'c'*40,'d'*40,self.history)
        self.assertEqual(result['acceptance'],'PREPARED_ONLY_ACTUAL_CURRENT_NATIVE_LOG_REQUIRED')
        self.assertIs(result['native_executed'],False)
        self.assertEqual(result['historical_source_assertions'],186)
        self.assertEqual(result['historical_candidate_source_assertions'],17)

    def test_prepare_rejects_uncommitted_worktree_drift(self):
        with self.committed_git_fixture(worktree_drift=True):
            with self.assertRaisesRegex(ValueError,'WORKTREE_DIFFERS_FROM_COMMITTED_HEAD'):
                audit.prepare(self.source,'c'*40,'d'*40,self.history)

    def test_prepare_rejects_committed_but_undeclared_historical_source_drift(self):
        with self.committed_git_fixture(committed_undeclared_drift=True):
            with self.assertRaisesRegex(ValueError,'UNDECLARED_HISTORICAL_SOURCE_CHANGE'):
                audit.prepare(self.source,'c'*40,'d'*40,self.history)


class OutputGuardTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='bsre-audit-output-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.source=self.root/'source';self.source.mkdir()
        self.history=self.root/'history';self.history.mkdir()
        self.private=self.root/'private';self.private.mkdir()

    def target(self,path,inputs=()):
        return audit.output_target(path,self.source,self.history,inputs)

    def directory_alias(self,target,alias):
        if os.name=='nt':
            import _winapi
            _winapi.CreateJunction(str(target),str(alias))
        else:os.symlink(target,alias,target_is_directory=True)

    def argv(self,output,operation='prepare'):
        return ['audit_current_native.py',operation,'--source',str(self.source),'--history',str(self.history),
                '--head','c'*40,'--tree','d'*40,'--output',str(output)]

    def test_source_history_and_normalized_descendants_are_refused_before_work(self):
        for path in [self.source,self.source/'new.json',self.source/'..'/'source'/'new.json',self.history/'new.json']:
            with self.assertRaisesRegex(ValueError,'OUTPUT_PROTECTED_ROOT'):self.target(path)
        for operation in ['prepare','audit']:
            with patch.object(sys,'argv',self.argv(self.source/'new.json',operation)),patch.object(audit,'prepare') as prepare,patch.object(audit,'audit') as run:
                with self.assertRaisesRegex(ValueError,'OUTPUT_PROTECTED_ROOT'):audit.main()
                prepare.assert_not_called();run.assert_not_called()
        if os.name=='nt':
            with self.assertRaisesRegex(ValueError,'OUTPUT_PROTECTED_ROOT'):
                audit.output_target(self.source/'fresh.json','\\\\?\\'+str(self.source),self.history)
            for name in ['\\\\?\\'+str(self.source/'fresh.json'),'\\\\.\\NUL','\\\\?\\GLOBALROOT\\Device\\HarddiskVolume1\\fresh.json']:
                with self.assertRaisesRegex(ValueError,'OUTPUT_RESERVED_NAMESPACE'):self.target(name)

    def test_every_input_name_and_normalized_alias_is_preserved(self):
        files=[]
        for name in ['raw.log','metadata.json','merge-tree.json','binding.json']:
            path=self.private/name;path.write_bytes(b'SYNTHETIC PROTECTED INPUT');files.append(path)
        for path in files:
            for alias in [path,path.parent/'.'/path.name]:
                with self.assertRaisesRegex(ValueError,'OUTPUT_INPUT_ALIAS'):self.target(alias,files)
            self.assertEqual(path.read_bytes(),b'SYNTHETIC PROTECTED INPUT')
        reserved=self.private/'not-created-input.json'
        with self.assertRaisesRegex(ValueError,'OUTPUT_INPUT_ALIAS'):self.target(reserved,[reserved])
        if os.name=='nt':
            for name in ['raw.log:alternate','NUL','CON','fresh.json.','fresh.json ']:
                with self.assertRaisesRegex(ValueError,'OUTPUT_RESERVED_NAME'):self.target(self.private/name,files)

    def test_existing_file_directory_and_hardlinked_input_never_overwrite(self):
        existing=self.private/'existing.json';existing.write_bytes(b'KEEP EXISTING')
        directory=self.private/'directory';directory.mkdir()
        alias=self.private/'hardlinked.json';os.link(existing,alias)
        for path in [existing,directory,alias]:
            with self.assertRaisesRegex(ValueError,'OUTPUT_EXISTS'):self.target(path,[existing]) if path!=existing else self.target(path)
        self.assertEqual(existing.read_bytes(),b'KEEP EXISTING');self.assertEqual(alias.read_bytes(),b'KEEP EXISTING')

    def test_actual_directory_aliases_to_protected_and_private_roots_are_refused(self):
        for name,target in [('source-alias',self.source),('private-alias',self.private)]:
            alias=self.root/name;self.directory_alias(target,alias)
            with self.assertRaisesRegex(ValueError,'OUTPUT_PROTECTED_ROOT|OUTPUT_LINK'):self.target(alias/'new.json')
            self.assertFalse((target/'new.json').exists())

    def test_symbolic_output_name_fails_closed(self):
        alias=self.private/'symbolic.json'
        if os.name=='nt':
            # Windows test hosts need no symlink privilege: real junctions are
            # covered above; this tests the final-file symlink stat boundary.
            with patch.object(Path,'is_symlink',autospec=True,side_effect=lambda path: path==alias):
                with self.assertRaisesRegex(ValueError,'OUTPUT_LINK'):self.target(alias)
        else:
            os.symlink(self.private/'missing.json',alias)
            with self.assertRaisesRegex(ValueError,'OUTPUT_LINK'):self.target(alias)

    def test_missing_parent_and_parent_replaced_after_preflight_are_refused(self):
        with self.assertRaisesRegex(ValueError,'OUTPUT_PARENT_REQUIRED'):self.target(self.private/'missing'/'new.json')
        parent=self.root/'later';parent.mkdir();output=parent/'new.json'
        self.target(output);self.assertEqual(parent.parent,self.root);parent.rmdir()
        self.directory_alias(self.source,parent)
        with self.assertRaisesRegex(ValueError,'OUTPUT_PROTECTED_ROOT'):
            audit.write_output(output,{'synthetic_only':True},self.source,self.history)
        self.assertFalse((self.source/'new.json').exists())

    def test_exclusive_creation_preserves_a_name_occupied_after_recheck(self):
        output=self.private/'raced.json';original=audit.exclusive_private_fd
        def race(path,parent_fd=None):
            Path(path).write_bytes(b'OTHER WRITER');return original(path,parent_fd)
        with patch.object(audit,'exclusive_private_fd',side_effect=race):
            with self.assertRaises(OSError):audit.write_output(output,{'synthetic_only':True},self.source,self.history)
        self.assertEqual(output.read_bytes(),b'OTHER WRITER')

    def test_parent_alias_swap_at_the_create_boundary_cannot_write_source(self):
        parent=self.root/'last-window';parent.mkdir();output=parent/'new.json';original=audit.exclusive_private_fd
        def race(path,parent_fd=None):
            parent.rmdir();self.directory_alias(self.source,parent)
            return original(path,parent_fd)
        with patch.object(audit,'exclusive_private_fd',side_effect=race):
            with self.assertRaises(OSError):audit.write_output(output,{'synthetic_only':True},self.source,self.history)
        self.assertFalse((self.source/'new.json').exists())

    def test_private_fresh_cli_success_and_owner_only_permissions(self):
        output=self.private/'fresh.json'
        result={'schema':'SYNTHETIC_OUTPUT_TEST','head':'c'*40,'feature_tree':'d'*40,'synthetic_only':True}
        with patch.object(sys,'argv',self.argv(output)),patch.object(audit,'prepare',return_value=result) as prepare,redirect_stdout(io.StringIO()):
            audit.main();prepare.assert_called_once()
        self.assertEqual(json.loads(output.read_text(encoding='utf-8')),result)
        if os.name!='nt':self.assertEqual(output.stat().st_mode&0o077,0)
        else:
            import ctypes
            from ctypes import wintypes
            advapi=ctypes.WinDLL('advapi32',use_last_error=True);kernel=ctypes.WinDLL('kernel32',use_last_error=True)
            get=advapi.GetFileSecurityW;get.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.LPVOID,wintypes.DWORD,ctypes.POINTER(wintypes.DWORD)];get.restype=wintypes.BOOL
            size=wintypes.DWORD();get(str(output),4,None,0,ctypes.byref(size));self.assertGreater(size.value,0)
            descriptor=ctypes.create_string_buffer(size.value);self.assertTrue(get(str(output),4,descriptor,size,ctypes.byref(size)))
            convert=advapi.ConvertSecurityDescriptorToStringSecurityDescriptorW;convert.argtypes=[wintypes.LPVOID,wintypes.DWORD,wintypes.DWORD,ctypes.POINTER(wintypes.LPWSTR),wintypes.LPVOID];convert.restype=wintypes.BOOL
            value=wintypes.LPWSTR();self.assertTrue(convert(descriptor,1,4,ctypes.byref(value),None))
            try:
                self.assertTrue(value.value.startswith('D:P'));self.assertEqual(value.value.count('('),1);self.assertIn(';;;OW)',value.value)
            finally:kernel.LocalFree.argtypes=[wintypes.LPVOID];kernel.LocalFree(value)
        with self.assertRaisesRegex(ValueError,'OUTPUT_EXISTS'):audit.write_output(output,result,self.source,self.history)


if __name__=='__main__':unittest.main()

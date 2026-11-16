import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {modes,waitFields,expectedWaitQuery,validateReceipt,validateProfileLog} from './check-receipt.mjs';
const php=readFileSync(new URL('./native/g2-retirement-races.php',import.meta.url),'utf8');
const sha=b=>createHash('sha256').update(b).digest('hex');
const baseChecks=['capture_matcher_rejects_identity_and_permission_corruption','exact_two_retirement_targets','observed_real_wait','exact_retirement_outcome','exact_child_outcome','retirement_audit_anchor_atomic','authenticated_ledger_exact_old_receipt','healthy_unknown_exact_original_input_preserved','unknown_retry_keeps_original_decision','canonical_lease_and_transaction_released','no_http_or_mail','bounded_duration'];
function fixture(mode){
 const extra=mode.startsWith('choose_')?['new_choice_exact_revision_and_permissions','old_history_retained_only_after_rollback']:['known_stage_matches_retirement_winner',...(mode==='stage_rollback'?['staged_exact_original_input_preserved','known_retry_keeps_original_decision']:[])];
 return {phase:'g38_g2_retirement_race',status:'PASS',mode,checks:Object.fromEntries([...baseChecks,...extra].map(k=>[k,true])),
  wait:{mechanism:'INNODB_LOCK_WAITS',real_wait:true,child_live:true,distinct_processes:true,distinct_connections:true,waiter:42,blocker:41,named_lock_owner:41,state_primary_wait:true,waiting_statement:mode.startsWith('choose_')?'INSERT_IGNORE_STATE':'SELECT_STATE_FOR_UPDATE',polls:2,elapsed_ms:12,
   parent_pid:501,child_pid:502,parent_connection:41,child_connection:42,requesting_trx_id:'1002',blocking_trx_id:'1001',
   waiting_table:'`bsre_synthetic`.`g37_pref_'+sha('g38|'+mode).slice(0,12)+'_synthetic_bsre_consent_state`',waiting_index:'PRIMARY',waiting_query:expectedWaitQuery(mode),
   selected_database:'bsre_synthetic',database_prefix:'g37_pref_'+sha('g38|'+mode).slice(0,12)+'_synthetic_',canonical_class:'BSRE\\ClosedRetention\\LeaseBoundWpdb',canonical_bootstrapped:true,canonical_g2_same_object:true,custody_active:true,custody_connection:'41',session_in_transaction:'1',session_tx_isolation:'REPEATABLE-READ'},
  runtime_isolation:Object.fromEntries(['cli','non_root','loopback_only','no_routes','no_capabilities','no_new_privileges','readonly_application','database_already_started','no_docker_socket'].map(k=>[k,true])),
  synthetic_only:true,actual_provider_accepted:false,production_authorized:false,full_operational_retention_accepted:false};
}
test('all four fixed prefixes fit the unchanged RuntimePolicy and remain distinct',()=>{
 const prefixes=modes.map(m=>'g37_pref_'+sha('g38|'+m).slice(0,12)+'_synthetic_');
 assert.equal(new Set(prefixes).size,4);for(const p of prefixes)assert.match(p,/^[A-Za-z0-9_]{1,40}_$/);
 assert.equal(php.match(/const G38_MODES = \[([^;]+)\];/)[1],modes.map(m=>"'"+m+"'").join(','));
});
test('real wait observation cannot be replaced by sleeping or matching unrelated waits',()=>{
 for(const token of ['INNODB_LOCK_WAITS','INNODB_TRX','INNODB_LOCKS','w.requested_lock_id','IS_USED_LOCK','custodyConnectionId','INSERT IGNORE INTO ',' FOR UPDATE','waiting_index'])assert.ok(php.includes(token),token);
 assert.ok(php.includes('r.trx_mysql_thread_id=%d AND b.trx_mysql_thread_id=%d'));
 assert.ok(!php.includes('extends wpdb')&&!php.includes("add_filter('query'")&&!php.includes('new wpdb'));
});
test('barrier uses the real signed fixture callback; rollback is existing post-delete key failure',()=>{
 assert.ok(php.includes('$services->onCoverage=function()'));
 assert.ok(php.includes('$services->rollbackKey=$rollback'));
 assert.ok(php.includes("$error==='G37_INJECTED_KEY_FAILURE'"));
 assert.ok(php.includes('V\\Algebra::validate($crypto->open('));
});
test('complete synthetic receipt set passes the offline acceptance checker',()=>{
 const out=validateProfileLog(modes.map(m=>JSON.stringify(fixture(m))).join('\n'));
 assert.equal(out.real_sql_waits,4);assert.equal(out.checks,56);
});
test('missing checks, false checks and promoted production/provider claims are rejected',()=>{
 for(const mutate of [v=>delete v.checks.healthy_unknown_exact_original_input_preserved,v=>v.checks.exact_child_outcome=false,v=>v.actual_provider_accepted=true,v=>v.production_authorized=true,v=>v.runtime_isolation.no_routes=false]){
  const v=fixture('choose_commit');mutate(v);assert.throws(()=>validateReceipt(v));
 }
});
test('identity, personalization and immutable retry assertions are mandatory',()=>{
 const matcher=php.slice(php.indexOf('function g38matchesCapture('),php.indexOf('function g38admit('));
 for(const token of ["'personalization'=>0","hash('sha256',$originalRaw)","$expected=$original+",'$actualKeys!==$expectedKeys','$row[$field]!==$value',"$altered[$field]=is_int($value)?$value+1:$value.'CORRUPT'",'unset($missing[$field])'])assert.ok(matcher.includes(token),token);
 assert.ok(php.includes("$capture=$init['capture'];"));
 assert.ok(!php.includes("$captures[0]===$childResult['row']"));
 for(const name of ['capture_matcher_rejects_identity_and_permission_corruption','healthy_unknown_exact_original_input_preserved','unknown_retry_keeps_original_decision','staged_exact_original_input_preserved','known_retry_keeps_original_decision']){
  const v=fixture('stage_rollback');delete v.checks[name];assert.throws(()=>validateReceipt(v));
 }
});
test('every raw wait field is required and observed identities must correlate',()=>{
 const good=fixture('choose_commit');assert.deepEqual(Object.keys(good.wait),waitFields);assert.equal(waitFields.length,30);
 for(const field of waitFields){const v=structuredClone(good);delete v.wait[field];assert.throws(()=>validateReceipt(v),field);}
 for(const mutate of [v=>v.wait.parent_pid=v.wait.child_pid,v=>v.wait.parent_connection=99,v=>v.wait.child_connection=99,v=>v.wait.requesting_trx_id=v.wait.blocking_trx_id,v=>v.wait.requesting_trx_id='01002',v=>v.wait.blocking_trx_id=1001,v=>v.wait.waiting_table='`bsre_synthetic`.`foreign_state`',v=>v.wait.waiting_index='foreign_index',v=>v.wait.waiting_query=v.wait.waiting_query.replace("'aa","'bb"),v=>v.wait.waiting_query='x'.repeat(2049),v=>v.wait.custody_connection='99',v=>v.wait.custody_active=false,v=>v.wait.session_in_transaction='0',v=>v.wait.session_tx_isolation='READ-COMMITTED',v=>v.wait.canonical_g2_same_object=false]){
  const v=structuredClone(good);mutate(v);assert.throws(()=>validateReceipt(v));
 }
});
test('raw metadata is selected and emitted from observations without expected-string substitution',()=>{
 const start=php.indexOf("return ['mechanism'");const emitted=php.slice(start,php.indexOf('];',start)+2);
 assert.deepEqual([...emitted.matchAll(/'([a-z0-9_]+)'\s*=>/g)].map(v=>v[1]),waitFields);
 for(const token of ['w.requesting_trx_id AS requesting_trx_id','w.blocking_trx_id AS blocking_trx_id',"'waiting_table'=>$row['waiting_table']","'waiting_index'=>$row['waiting_index']","'waiting_query'=>$query","'parent_pid'=>$parentPid","'child_pid'=>$process['pid']","'session_tx_isolation'=>$facts['session_tx_isolation']"])assert.ok(php.includes(token),token);
 assert.ok(php.includes('strlen($query)>2048'));assert.ok(!php.includes('substr($query'));
});
test('sleep-only evidence, wrong owner, same connection and wrong SQL mechanism are rejected',()=>{
 for(const mutate of [v=>delete v.wait,v=>v.wait.mechanism='sleep',v=>v.wait.named_lock_owner=99,v=>v.wait.waiter=v.wait.blocker,v=>v.wait.child_live=false,v=>v.wait.waiting_statement='SELECT_STATE_FOR_UPDATE']){
  const v=fixture('choose_commit');mutate(v);assert.throws(()=>validateReceipt(v));
 }
});
test('diagnostics, duplicate modes and incomplete profile logs never count as native acceptance',()=>{
 const good=modes.map(m=>JSON.stringify(fixture(m))).join('\n');
 assert.throws(()=>validateProfileLog(good+'\n'+JSON.stringify({phase:'g38_g2_race_diagnostic',status:'FAIL'})));
 assert.throws(()=>validateProfileLog(modes.map(()=>JSON.stringify(fixture('choose_commit'))).join('\n')));
 assert.throws(()=>validateProfileLog(JSON.stringify(fixture('choose_commit'))));
 assert.throws(()=>validateProfileLog(good+'\n{"phase":"g38_g2_'));
});

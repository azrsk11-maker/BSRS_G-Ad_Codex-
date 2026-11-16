import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {buildG2SharedRepositorySources as build} from './build-g2-shared-repository-candidate.mjs';
import {buildG2ProfileCandidate} from './build-g2-profile-candidate.mjs';
const fixture=new URL('../../staging-lab/fixtures/bsre-enquiries/',import.meta.url);
const inputs=[readFileSync(new URL('bsre-enquiries.php',fixture)),readFileSync(new URL('includes/consent.php',fixture)),
  readFileSync(new URL('./purpose-attribution.php',import.meta.url)),readFileSync(new URL('./receipt-recovery-wordpress.php',import.meta.url))];
const nl=s=>s.replaceAll('\r\n','\n');
test('fixed source pins reject every unrelated input mutation and nonbuffer',()=>{
  for(let i=0;i<inputs.length;i++){
    const bad=inputs.map(x=>Buffer.from(x));bad[i][0]^=1;assert.throws(()=>build(...bad),/SOURCE_CHANGED/);
    const nonbuffer=[...inputs];nonbuffer[i]=inputs[i].toString();assert.throws(()=>build(...nonbuffer),/SOURCE_CHANGED/);
  }
});
test('disabled original consent path is byte-equivalent after removing exact insertion',()=>{
  const out=build(...inputs); const before=inputs[1].toString();
  const start=out.consent.indexOf("    if (defined('BSRE_G2_SHARED_REPOSITORY_ENABLED')");
  const end=out.consent.indexOf('    if ($store) return $store;',start);
  assert.ok(start>0&&end>start);
  assert.equal(out.consent.slice(0,start)+out.consent.slice(end),before);
  assert.ok(out.consent.indexOf('SharedRepository\\repository($store)')<out.consent.indexOf('if ($store) return $store;'));
});
test('original plugin acquires only bootstrap include after all original dependencies',()=>{
  const out=build(...inputs), s=nl(out.plugin);
  assert.equal(s.replace("require_once __DIR__ . '/includes/g2-profile/bootstrap.php';\n",''),nl(inputs[0].toString()));
  assert.ok(s.indexOf('/includes/presentation.php')<s.indexOf('/includes/g2-profile/bootstrap.php'));
});
test('purpose selector and legacy lookup use same canonical repository when enabled',()=>{
  const s=build(...inputs).purpose;
  assert.ok(s.includes('return \\BSRE\\SharedRepository\\repository(Runtime::$store);'));
  assert.ok(s.includes('? repository()->database() : (Runtime::$store ? Runtime::$store->database() : $wpdb)'));
  assert.ok(s.includes('return Runtime::$store ?? new WpConsentRepository($wpdb);'));
});
test('status default database check follows guards and never moves before proof minting',()=>{
  const s=build(...inputs).recovery;
  assert.ok(s.indexOf("if ($operation === 'proof')")<s.indexOf('\\BSRE\\SharedRepository\\repository();'));
  assert.ok(s.indexOf('RATE')===-1 || s.indexOf('\\BSRE\\SharedRepository\\repository();')>s.indexOf('receipt-recovery-session:'));
  assert.ok(s.includes('Intake\\consent_repository()->link('));
});
test('profile bootstrap is inert unless explicitly enabled and registers no routes',()=>{
  const s=readFileSync(new URL('./g2-shared-bootstrap.php',import.meta.url),'utf8');
  assert.ok(s.indexOf("!==true) return;")<s.indexOf('require_once'));
  assert.ok(s.indexOf("'/purpose-store.php'")<s.indexOf("'/purpose-attribution.php'"));
  assert.ok(s.includes('G2_NAMESPACE_OCCUPIED')&&!s.includes('register_rest_route('));
  assert.ok(s.includes("add_action('admin_init',__NAMESPACE__.'\\\\migrate',20)"));
});
test('migration code is additive-only, capability gated, with independent schema marker',()=>{
  const s=readFileSync(new URL('./g2-shared-repository.php',import.meta.url),'utf8');
  const m=s.slice(s.indexOf('function migrate(): bool'));
  assert.ok(m.indexOf("current_user_can('manage_options')")<m.indexOf('ALTER TABLE'));
  assert.ok(m.includes("'ADD COLUMN `'"));
  assert.ok(!m.includes('DROP ')&&!m.includes('TRUNCATE ')&&!m.includes('DELETE ')&&!m.includes("update_option('bsre_consent_schema_version'"));
  assert.ok(s.includes("'G2_DATABASE_CHANGED'")&&s.includes("'G2_STORE_CONFLICT'")&&s.includes('G2_IDENTITY_INDEX_REQUIRED'));
  assert.ok(s.includes("const SCHEMA_OPTION = 'bsre_g2_shared_repository_schema'"));
});
test('builder neither mutates its inputs nor removes immutable guards or wire content',()=>{
  const old=inputs.map(x=>Buffer.from(x)),r=build(...inputs);
  for(let i=0;i<inputs.length;i++)assert.deepEqual(inputs[i],old[i]);
  assert.equal(r.deployment_prohibited,true);
  assert.ok(r.plugin.includes('function receive(')&&r.consent.includes('get_option(\'bsre_consent_schema_version\')'));
});
test('separate G2 tree retains original interface, common G1 store and exact requires',()=>{
  const audit=readFileSync(new URL('../../../docs/audit/INSTALLED_SOURCE_COMPARISON_2026-11-07.json',import.meta.url));
  const r=buildG2ProfileCandidate(audit),files=new Map(r.files.map(x=>[x.path,Buffer.from(x.content_base64,'base64')]));
  assert.equal(files.size,39);assert.equal(r.deployment_prohibited,true);assert.equal(r.g3_routes_or_transport_selected,false);
  assert.deepEqual(files.get('includes/consent-store.php'),readFileSync(new URL('includes/consent-store.php',fixture)));
  const store=files.get('includes/g2-profile/purpose-store.php').toString();
  assert.ok(store.includes("if ((int) $capture['known'] === 1)"));
  assert.ok(store.includes('interface ConsentRepository extends \\BSRE\\Enquiries\\ConsentRepository'));
  const boot=files.get('includes/g2-profile/bootstrap.php').toString();
  for(const [,name] of boot.matchAll(/require_once __DIR__\.'\/([^']+)'/g))assert.ok(files.has('includes/g2-profile/'+name));
  assert.throws(()=>buildG2ProfileCandidate(Buffer.concat([audit,Buffer.from('\n')])),/MAP_CHANGED/);
});
test('actual selected database is read before cached reuse or any migration option/write',()=>{
  const s=readFileSync(new URL('./g2-shared-repository.php',import.meta.url),'utf8');
  const identity=s.slice(s.indexOf('function selected_database('),s.indexOf('function query_rows('));
  assert.ok(identity.includes("get_var('SELECT DATABASE()')")&&identity.includes('$actual!==DB_NAME'));
  assert.ok(identity.includes('suppress_errors(true)')&&identity.includes('finally')&&!identity.includes('->dbname'));
  const repo=s.slice(s.indexOf('function repository('),s.indexOf('function migrate('));
  assert.ok(repo.indexOf('selected_database($wpdb)')<repo.indexOf('get_option('));
  assert.ok(repo.indexOf('selected_database($wpdb)')<repo.indexOf('Runtime::$schemaChecked'));
  const migrate=s.slice(s.indexOf('function migrate('));
  assert.ok(migrate.indexOf('selected_database($wpdb)')<migrate.indexOf('current_user_can('));
  assert.ok(migrate.indexOf('selected_database($wpdb)')<migrate.indexOf('get_option('));
  assert.ok(repo.includes('Runtime::$database!==$database')&&migrate.includes('Runtime::$database!==$database'));
});
test('late native lane uses runtime-safe controls and actual same-object DB switch probe',()=>{
  const s=readFileSync(new URL('../../staging-lab/g2-shared-repository-native.php',import.meta.url),'utf8');
  assert.ok(!s.includes("require '/opt/lab/isolation.php'"));
  assert.ok(s.includes("is_dir('/tmp/database')")&&s.includes("file_exists('/tmp/bsre.sock')"));
  assert.ok(s.indexOf('foreach ($runtimeIsolation')<s.indexOf("require '/opt/wordpress/wp-load.php'"));
  assert.ok(s.includes('$wpdb->select($foreign)')&&s.includes('same_object_same_prefix_database_switch'));
  assert.ok(s.includes("add_filter('query',$observeQuery")&&s.includes("count($observedQueries)===3"));
  assert.ok(s.includes('foreign_default_selection_rejected')&&s.includes('foreign_purpose_selection_rejected')&&s.includes('foreign_migration_rejected'));
});

test('native disabled lane loads fixed candidate and retains the original factory contract',()=>{
  const s=readFileSync(new URL('../../staging-lab/g2-shared-repository-native.php',import.meta.url),'utf8');
  assert.equal((s.match(/require_once WP_PLUGIN_DIR\.'\/bsre-enquiries\/bsre-enquiries.php';/g)||[]).length,2);
  assert.ok(s.includes("if ($mode==='enabled') delete_option(G\\SCHEMA_OPTION);"));
  assert.ok(s.includes("get_class($handle['repository'])===E\\WpConsentRepository::class"));
  assert.ok(!s.includes("$handle['repository']===$default"));
  assert.ok(s.includes('disabled_default_still_links_receipts')&&s.includes('disabled_additive_columns_absent'));
  const fixture=readFileSync(new URL('../../staging-lab/g2-namespace-collision-fixture.php',import.meta.url),'utf8');
  assert.ok(fixture.includes("PHP_SAPI!=='cli'")&&fixture.includes('BSRE_G2_NAMESPACE_COLLISION_LAB'));
  assert.ok(s.includes("$error->getMessage()!=='G2_NAMESPACE_OCCUPIED'"));
});

test('native migration probes reject conflicting metadata before any write and resume a partial schema',()=>{
  const s=readFileSync(new URL('../../staging-lab/g2-shared-repository-native.php',import.meta.url),'utf8');
  assert.ok(s.includes('conflicting_additive_schema_rejected_without_writes')&&s.includes('$writes===[]'));
  assert.ok(s.includes('conflicting_schema_preserves_original_row')&&s.includes('partial_schema_not_ready'));
  assert.ok(s.indexOf('partial_schema_not_ready')<s.indexOf("g2check('actual_additive_migration_succeeds'"));
  assert.ok(s.includes("update_option(G\\SCHEMA_OPTION,'1',false);")&&s.includes("'G2_ADDITIVE_SCHEMA_INCOMPLETE'"));
});

test('held repository handles retain identity guards without changing the pinned G1 implementation',()=>{
  const s=readFileSync(new URL('./g2-shared-repository.php',import.meta.url),'utf8');
  const bound=s.slice(s.indexOf('final class BoundRepository'),s.indexOf('function query_rows('));
  assert.ok(bound.includes('implements P\\ConsentRepository')&&bound.includes('selected_database($this->db)'));
  assert.ok(bound.includes('$wpdb!==$this->db')&&bound.includes('$this->db->prefix!==$this->prefix'));
  for(const name of ['database','admissionContract','current','choose','stage','link','uncertain','revoked','exportRows']) {
    const method=bound.slice(bound.indexOf('public function '+name+'('));
    assert.ok(method.slice(0,method.indexOf('\n')).includes('$this->guard();'),name);
  }
  assert.ok(s.includes('new BoundRepository(new P\\WpConsentRepository($wpdb),$wpdb,$database)'));
  const native=readFileSync(new URL('../../staging-lab/g2-shared-repository-native.php',import.meta.url),'utf8');
  assert.ok(native.includes('foreign_held_operations_only_read_connection_identity')&&native.includes('count($observedQueries)===count($heldOperations)'));
});

import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {modes} from './build-native-packet.mjs';
const hash=value=>createHash('sha256').update(value).digest('hex');
test('every native mode fits the unchanged canonical RuntimePolicy prefix contract',()=>{
 const guard=readFileSync(new URL('../g5-runtime-ports/candidate/plugin/includes/candidate/runtime/G5Contracts.php',import.meta.url));
 assert.equal(hash(guard),'bef6f67cc995d4ad5a273d54de7c1c7e6953a88fb33a962bfb6d29e4c574af26');
 const driver=readFileSync(new URL('./native/native.php',import.meta.url),'utf8');
 const expression="$wpdb->prefix='g37_pref_'.substr(hash('sha256',$mode),0,12).'_synthetic_';";
 assert.equal(driver.split(expression).length,2);
 const prefixes=modes.map(mode=>'g37_pref_'+hash(mode).slice(0,12)+'_synthetic_');
 assert.equal(prefixes.length,28);assert.equal(new Set(prefixes).size,modes.length);
 for(const prefix of prefixes)assert.match(prefix,/^[A-Za-z0-9_]{1,40}_$/);
 assert.ok(modes.includes('expired_backup_reference')&&modes.includes('external_deadlines'));
});

import {readFileSync,writeFileSync,mkdirSync,existsSync} from 'node:fs';
import {dirname} from 'node:path';
import {buildCanonicalLeaseCandidate} from '../website-tracking/canonical-lease/build-candidate.mjs';
import {buildCanonicalRouteNative} from '../website-tracking/canonical-lease/build-route-native.mjs';
if(process.argv.length!==2)throw new Error('G35_FIXED_LAB_BUILD_ONLY');
const candidate=buildCanonicalLeaseCandidate(readFileSync('/opt/lab/g2/original-member-audit.json'));
for(const row of candidate.files){
 if(!row.path.startsWith('wp-content/')||row.path.split('/').some(part=>!part||part==='.'||part==='..'))throw new Error('G35_OUTPUT_PATH_INVALID');
 const file='/opt/lab/g35/'+row.path,bytes=Buffer.from(row.content_base64,'base64');
 mkdirSync(dirname(file),{recursive:true});
 if(existsSync(file)&&!readFileSync(file).equals(bytes))throw new Error('G35_LAB_OUTPUT_EXISTS');
 writeFileSync(file,bytes);
}
const route=buildCanonicalRouteNative();
writeFileSync('/opt/lab/g35/route-native.php',route.php);
writeFileSync('/opt/lab/g35/BUILD.json',JSON.stringify({profile:candidate.profile,
 files:candidate.files.map(({path,sha256})=>({path,sha256}))},null,2)+'\n');
writeFileSync('/opt/lab/g35/ROUTE_BUILD.json',JSON.stringify({status:'HELD',deployment_prohibited:true,
 original_route_sha256:route.original_route_sha256,original_G5_sha256:route.original_G5_sha256,
 ordered_edits:route.ordered_edits,original_route_recovered:route.original_route_recovered},null,2)+'\n');

import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {dirname} from 'node:path';
import {buildG34ProfileCandidate} from '../website-tracking/tracking-system/build-g34-profile-candidate.mjs';
if(process.argv.length!==2)throw new Error('G34_FIXED_LAB_BUILD_ONLY');
for(const row of buildG34ProfileCandidate(readFileSync('/opt/lab/g2/original-member-audit.json')).files){
  const target='/opt/lab/g34/plugins/bsre-enquiries/'+row.path;
  mkdirSync(dirname(target),{recursive:true});writeFileSync(target,Buffer.from(row.content_base64,'base64'));
}

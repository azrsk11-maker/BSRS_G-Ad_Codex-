import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {dirname} from 'node:path';
import {buildG3ProfileCandidate} from '../website-tracking/tracking-system/build-g3-profile-candidate.mjs';
if(process.argv.length!==2)throw new Error('G3_FIXED_LAB_BUILD_ONLY');
for(const row of buildG3ProfileCandidate(readFileSync('/opt/lab/g2/original-member-audit.json')).files){
  const target='/opt/lab/g3/plugins/bsre-enquiries/'+row.path;
  mkdirSync(dirname(target),{recursive:true});writeFileSync(target,Buffer.from(row.content_base64,'base64'));
}

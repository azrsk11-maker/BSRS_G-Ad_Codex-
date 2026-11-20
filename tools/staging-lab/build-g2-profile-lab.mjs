// Fixed isolated image paths; no user-selected plugin root, URL, settings or arguments.
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {dirname} from 'node:path';
import {buildG2ProfileCandidate} from '../website-tracking/tracking-system/build-g2-profile-candidate.mjs';
if(process.argv.length!==2)throw new Error('G2_FIXED_LAB_BUILD_ONLY');
const result=buildG2ProfileCandidate(readFileSync('/opt/lab/g2/original-member-audit.json'));
for(const row of result.files){
  const path='/opt/lab/g2/plugins/bsre-enquiries/'+row.path;
  mkdirSync(dirname(path),{recursive:true});writeFileSync(path,Buffer.from(row.content_base64,'base64'));
}

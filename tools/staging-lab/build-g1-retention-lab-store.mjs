// Fixed lab build paths only; never executes WordPress/PHP or accepts injected paths.
import {readFileSync,writeFileSync} from 'node:fs';
import {buildG1RetentionStoreCandidate} from '../website-tracking/tracking-system/build-g1-retention-store-candidate.mjs';
if(process.argv.length!==2) throw new Error('G1_FIXED_LAB_BUILD_ONLY');
const r=buildG1RetentionStoreCandidate(readFileSync('/opt/wordpress/wp-content/plugins/bsre-enquiries/includes/consent-store.php'));
writeFileSync('/opt/lab/g1-retention/store.php',r.candidate);

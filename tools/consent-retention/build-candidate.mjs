// Derive an isolated namespace candidate; immutable baseline stays untouched.
import {readFileSync,writeFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
const [input,output]=process.argv.slice(2);
const raw=readFileSync(input);
if(createHash('sha256').update(raw).digest('hex')!=='7ccb7fdf0d88a3d2b1d54832f61c71bfcc025554bebf3927d7f5ce0c72f12262')throw Error('Unreviewed consent store');
let source=raw.toString().replace('namespace BSRE\\Enquiries;', 'namespace BSRE\\RetentionCandidate;\nuse const BSRE\\Enquiries\\CONSENT_PREFERENCE_SECONDS;');
source=source.replace('interface ConsentRepository {','interface ConsentRepository extends \\BSRE\\Enquiries\\ConsentRepository {');
const anchor='return $this->transaction(function () use ($capture) {';
if(source.split(anchor).length!==2)throw Error('Stage anchor changed');
source=source.replace(anchor,anchor+`
            // Share the retention/choice state lock before staging evidence.
            // A snapshot read before retirement must never recreate a known grant.
            if ($capture['subject_key'] !== '') {
                $current = $this->row($this->db->prepare("SELECT * FROM {$this->state} WHERE subject_key=%s FOR UPDATE", $capture['subject_key']));
                if (!$current) throw new \\RuntimeException('Consent evidence retired.');
                if ((int) $capture['known'] === 1) {
                    $original = $this->row($this->db->prepare("SELECT receipt FROM {$this->history} WHERE subject_key=%s AND revision=%d FOR UPDATE", $capture['subject_key'], $capture['original_revision']));
                    if (!$original || !hash_equals($original['receipt'], $capture['decision_version'])) throw new \\RuntimeException('Consent evidence retired.');
                }
            }`);
writeFileSync(output,source);

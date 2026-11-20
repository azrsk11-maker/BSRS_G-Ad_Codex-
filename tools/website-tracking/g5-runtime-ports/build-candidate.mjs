import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';

const sourceOutputs = {
  "tools/closed-enquiry-retention/Workflow.php": "plugin/includes/candidate/closed-enquiry-retention/Workflow.php",
  "tools/closed-enquiry-retention/NoMailCopy.php": "plugin/includes/candidate/closed-enquiry-retention/NoMailCopy.php",
  "tools/closed-enquiry-retention/RetirementIntent.php": "plugin/includes/candidate/closed-enquiry-retention/RetirementIntent.php",
  "tools/closed-enquiry-retention/ClosureCollection.php": "plugin/includes/candidate/closed-enquiry-retention/ClosureCollection.php",
  "tools/closed-enquiry-retention/RetirementJournal.php": "plugin/includes/candidate/closed-enquiry-retention/RetirementJournal.php",
  "tools/closed-enquiry-retention/ClosureCollectionJournal.php": "plugin/includes/candidate/closed-enquiry-retention/ClosureCollectionJournal.php",
  "tools/closed-enquiry-retention/LeaseBoundWpdb.php": "plugin/includes/candidate/closed-enquiry-retention/LeaseBoundWpdb.php",
  "tools/consent-retention/RetentionInventory.php": "plugin/includes/candidate/consent-retention/RetentionInventory.php"
};
const candidatePaths = {
  "plugin/includes/candidate/closed-enquiry-retention/ActualCaptureResource.php": "tools/website-tracking/g5-runtime-ports/candidate/plugin/includes/candidate/closed-enquiry-retention/ActualCaptureResource.php",
  "plugin/includes/candidate/closed-enquiry-retention/ActualJournal.php": "tools/website-tracking/g5-runtime-ports/candidate/plugin/includes/candidate/closed-enquiry-retention/ActualJournal.php",
  "plugin/includes/candidate/closed-enquiry-retention/CaptureRules.php": "tools/website-tracking/g5-runtime-ports/candidate/plugin/includes/candidate/closed-enquiry-retention/CaptureRules.php",
  "plugin/includes/candidate/recovery/ActualRecoveryCustody.php": "tools/website-tracking/g5-runtime-ports/candidate/plugin/includes/candidate/recovery/ActualRecoveryCustody.php",
  "plugin/includes/candidate/runtime/G5Contracts.php": "tools/website-tracking/g5-runtime-ports/candidate/plugin/includes/candidate/runtime/G5Contracts.php"
};
export const SOURCE_SHA256 = Object.freeze({
  "tools/closed-enquiry-retention/Workflow.php": "5e9c7d4b0816f83b6349d08051a8dac552faa5af44a877966d2e042a635cb8f7",
  "tools/closed-enquiry-retention/NoMailCopy.php": "25864e2a07fba073fcc68922a68050571aca7e3d4a2160be72a0f2ce56a49e82",
  "tools/closed-enquiry-retention/RetirementIntent.php": "8d3c5d0b6bf1f3f4be316dbdffdcadb653e0e691e823ba7746961d5f68e1f349",
  "tools/closed-enquiry-retention/ClosureCollection.php": "793ac11a2de66e26e4caee0ea357c2bd43200b3c7695fea534c819b9a8fdf6d7",
  "tools/closed-enquiry-retention/RetirementJournal.php": "d8b26bbeabb9875f5205cf2d2d025954d78917c8e7c3367d9f59eb4f50d34bb3",
  "tools/closed-enquiry-retention/ClosureCollectionJournal.php": "6801f8868ea09fa108f0eba6591c4014f3cf2bc69e2010018476163fc5054fce",
  "tools/closed-enquiry-retention/LeaseBoundWpdb.php": "a358c8f28a6186ce5bc452aa699c93ddd96fb71b58528f1e21acc9e42b854b58",
  "tools/consent-retention/RetentionInventory.php": "5d7a68b6f40ccf3c87071382b2a392c91243b8d7378d668732ae3a6e759f89cb",
  "tools/closed-enquiry-retention/WpCaptureResource.php": "50008a488db9c52393355d47665ff4af30d7a2af7ecdfa65a73574eab1347992"
});
export const CANDIDATE_SHA256 = Object.freeze({
  "tools/website-tracking/g5-runtime-ports/candidate/plugin/includes/candidate/closed-enquiry-retention/ActualCaptureResource.php": "30685843d5b56551e15984150d7ec2ba83d9c4152b4a154ca40efe71bedbf177",
  "tools/website-tracking/g5-runtime-ports/candidate/plugin/includes/candidate/closed-enquiry-retention/ActualJournal.php": "33dc908fbe4f5e5794540b67091e847a08473649a15f4bd69ae01b126c998cd3",
  "tools/website-tracking/g5-runtime-ports/candidate/plugin/includes/candidate/closed-enquiry-retention/CaptureRules.php": "87c2012acf8d27a93063bd7ace11ae33dec548837de3e29c2569274c0b1e7671",
  "tools/website-tracking/g5-runtime-ports/candidate/plugin/includes/candidate/recovery/ActualRecoveryCustody.php": "32b232c7f476c8c8ab9477b8b775836cd7d26bdacb65a2fec30a330436fea2ec",
  "tools/website-tracking/g5-runtime-ports/candidate/plugin/includes/candidate/runtime/G5Contracts.php": "bef6f67cc995d4ad5a273d54de7c1c7e6953a88fb33a962bfb6d29e4c574af26"
});
export const OUTPUT_SHA256 = Object.freeze({
  "plugin/includes/candidate/closed-enquiry-retention/ActualCaptureResource.php": "30685843d5b56551e15984150d7ec2ba83d9c4152b4a154ca40efe71bedbf177",
  "plugin/includes/candidate/closed-enquiry-retention/ActualJournal.php": "33dc908fbe4f5e5794540b67091e847a08473649a15f4bd69ae01b126c998cd3",
  "plugin/includes/candidate/closed-enquiry-retention/CaptureRules.php": "87c2012acf8d27a93063bd7ace11ae33dec548837de3e29c2569274c0b1e7671",
  "plugin/includes/candidate/closed-enquiry-retention/ClosureCollection.php": "793ac11a2de66e26e4caee0ea357c2bd43200b3c7695fea534c819b9a8fdf6d7",
  "plugin/includes/candidate/closed-enquiry-retention/ClosureCollectionJournal.php": "6801f8868ea09fa108f0eba6591c4014f3cf2bc69e2010018476163fc5054fce",
  "plugin/includes/candidate/closed-enquiry-retention/LeaseBoundWpdb.php": "a358c8f28a6186ce5bc452aa699c93ddd96fb71b58528f1e21acc9e42b854b58",
  "plugin/includes/candidate/closed-enquiry-retention/NoMailCopy.php": "25864e2a07fba073fcc68922a68050571aca7e3d4a2160be72a0f2ce56a49e82",
  "plugin/includes/candidate/closed-enquiry-retention/RetirementIntent.php": "8d3c5d0b6bf1f3f4be316dbdffdcadb653e0e691e823ba7746961d5f68e1f349",
  "plugin/includes/candidate/closed-enquiry-retention/RetirementJournal.php": "d8b26bbeabb9875f5205cf2d2d025954d78917c8e7c3367d9f59eb4f50d34bb3",
  "plugin/includes/candidate/closed-enquiry-retention/Workflow.php": "5e9c7d4b0816f83b6349d08051a8dac552faa5af44a877966d2e042a635cb8f7",
  "plugin/includes/candidate/consent-retention/RetentionInventory.php": "5d7a68b6f40ccf3c87071382b2a392c91243b8d7378d668732ae3a6e759f89cb",
  "plugin/includes/candidate/recovery/ActualRecoveryCustody.php": "32b232c7f476c8c8ab9477b8b775836cd7d26bdacb65a2fec30a330436fea2ec",
  "plugin/includes/candidate/runtime/G5Contracts.php": "bef6f67cc995d4ad5a273d54de7c1c7e6953a88fb33a962bfb6d29e4c574af26"
});
export const RULE_SPANS = Object.freeze([
  {
    "start": "    private const SCHEMA = [",
    "end_exclusive": "    private string $table;",
    "sha256": "c4c85a63b33e7710d7d069d8dee27ab546364cf897e0d2e13d6280fa032dd3fc"
  },
  {
    "start": "    private function schema(): void",
    "end_exclusive": "    /** No nested transaction",
    "sha256": "85f5bb97b34b354d8583f52ca083708264c84f4a037ece91d62150351cd7c96d"
  },
  {
    "start": "    private static function uuid(string $value): void",
    "end_exclusive": "    private function current(",
    "sha256": "ca2a1bf56309d11ae0e8fc6c2d36d15a2ed0658b173dda02eb31fcc3be5601a9"
  },
  {
    "start": "    private static function binding(array $row): array",
    "end_exclusive": "    public function inventory(",
    "sha256": "5e87874025065b02accdcb85bd1c47110eca64e6545b3fe072adf1240229adc5"
  }
]);
export const NATIVE_SHA256 = '266076af2e47feb2e72db3de5143c9490fc310dc431dbf2e5d78ee3bd4e20bd2';
export const REQUIRED_OUTPUTS = Object.freeze(Object.keys(OUTPUT_SHA256).sort());
export const sha256 = value => createHash('sha256').update(value).digest('hex');
const defaultRead = relative => readFileSync(new URL('../../' + relative.replace(/^tools\//, ''), import.meta.url));
function input(read, relative) {
  let value;
  try { value = read(relative); } catch { throw new Error('G5_INPUT_UNAVAILABLE:' + relative); }
  if (!(value instanceof Uint8Array)) throw new Error('G5_INPUT_BYTES_REQUIRED:' + relative);
  return Buffer.from(value);
}
function pinned(read, relative, pin) {
  const value = input(read, relative);
  if (sha256(value) !== pin) throw new Error('G5_PREIMAGE_CHANGED:' + relative);
  return value;
}

/** Build-time byte derivation only. No filesystem write, network, hook, runtime key or activation. */
export function buildG5RuntimeCandidate({read = defaultRead} = {}) {
  const originals = {};
  for (const [relative, pin] of Object.entries(SOURCE_SHA256)) originals[relative] = pinned(read, relative, pin);
  const outputs = {};
  for (const [relative, output] of Object.entries(sourceOutputs)) outputs[output] = Buffer.from(originals[relative]);
  for (const [output, relative] of Object.entries(candidatePaths)) outputs[output] = pinned(read, relative, CANDIDATE_SHA256[relative]);
  const original = originals['tools/closed-enquiry-retention/WpCaptureResource.php'].toString('utf8');
  const spans = RULE_SPANS.map(({start, end_exclusive, sha256:pin}) => {
    if (original.split(start).length !== 2 || original.split(end_exclusive).length !== 2) throw new Error('G5_CAPTURE_RULE_ANCHOR_CHANGED');
    const value = original.slice(original.indexOf(start), original.indexOf(end_exclusive));
    if (sha256(Buffer.from(value)) !== pin) throw new Error('G5_CAPTURE_RULE_PREIMAGE_CHANGED');
    return value;
  });
  const rules = Buffer.from('<?php\ndeclare(strict_types=1);\nnamespace BSRE\\ActualRetention;\nuse BSRE\\ClosedRetention\\Failure;\nuse BSRE\\ClosedRetention\\Workflow;\n/** Pure rules extracted exactly; no old class guard, authority or fixture is installed here. */\ntrait CaptureRules\n{\n' + spans.join('') + '}\n');
  if (!rules.equals(outputs['plugin/includes/candidate/closed-enquiry-retention/CaptureRules.php'])) throw new Error('G5_CAPTURE_RULE_DERIVATION_CHANGED');
  const names = Object.keys(outputs).sort();
  if (JSON.stringify(names) !== JSON.stringify(REQUIRED_OUTPUTS) || names.length !== 13) throw new Error('G5_OUTPUT_SET_INCOMPLETE');
  for (const name of names) if (sha256(outputs[name]) !== OUTPUT_SHA256[name]) throw new Error('G5_OUTPUT_HASH_CHANGED:' + name);
  return {
    outputs,
    manifest: {
      schema_version:1, profile:'G5_DURABLE_PORTS_PARTIAL', status:'HELD', full_profile_complete:false,
      production_authorized:false, native_accepted:false, actual_provider_accepted:false,
      output_count:13, outputs:{...OUTPUT_SHA256}, source_preimages:{...SOURCE_SHA256}, candidate_preimages:{...CANDIDATE_SHA256},
      remaining:['canonical_common_connection_lease','actual_composed_capture_producer','independent_anchor_and_key_custody','actual_receiver_mail_source_evidence','ActualPreferenceRetention.php','ActualRetirementPort.php','encrypted_recovery_snapshot_preservation','coupled_native_provider_acceptance']
    }
  };
}

/** Test fixture only; never an emitted runtime/provider authority. */
export function readG5NativeFixture({read = defaultRead} = {}) {
  return pinned(read, 'tools/website-tracking/g5-runtime-ports/tests/native.php', NATIVE_SHA256);
}

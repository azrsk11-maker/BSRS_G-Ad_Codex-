/** Validate aggregate staff evidence without accepting it as real workload proof. */
export function validateStaffGate(timing, capacity, reviewed = false) {
  const errors = [];
  if (!timing || typeof timing !== 'object') errors.push('timing summary is required');
  if (!capacity || typeof capacity !== 'object') errors.push('capacity summary is required');
  const t = timing || {}, c = capacity || {};
  for (const key of ['peak_first_contact_sample_count','peak_first_contact_max_seconds','missing_first_attempt_count','late_first_attempt_count']) {
    if (!(key in t)) errors.push(`timing.${key} is required`);
  }
  for (const key of ['staffed_days_supplied','total_completed','min_daily_completions_observed','sample_representativeness_verified']) {
    if (!(key in c)) errors.push(`capacity.${key} is required`);
  }
  if (Number(t.missing_first_attempt_count) !== 0) errors.push('missing first attempts must be zero');
  if (Number(t.late_first_attempt_count) !== 0) errors.push('late first attempts must be zero');
  if (t.peak_first_contact_max_seconds !== null && Number(t.peak_first_contact_max_seconds) > 1800) errors.push('first-contact maximum exceeds 1800 seconds');
  if (Number(t.peak_first_contact_sample_count) <= 0) errors.push('representative timing sample must be nonempty');
  if (Number(c.staffed_days_supplied) <= 0 || Number(c.min_daily_completions_observed) < 0) errors.push('capacity sample must contain staffed days');
  if (c.sample_representativeness_verified !== true) errors.push('owner-reviewed representativeness is required');
  if (reviewed !== true) errors.push('owner review is required');
  return {schema_version:1, valid:errors.length===0, errors, release_authorized:false};
}

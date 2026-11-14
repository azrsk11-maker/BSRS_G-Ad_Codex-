# Staff rehearsal and capacity evidence

Use this worksheet with [staff readiness issue #4](https://github.com/azrsk11-maker/BSRS_G-Ad_Codex-/issues/4). The owner confirms the next 14:00–15:00 Dubai session with Amit before scheduling. Use the restricted entry workflow on desktop and phone, plus synthetic cases excluded from production measurement.

## Record during the rehearsal

| Time (Dubai) | Exercise | Record |
|---|---|---|
| 14:00–14:10 | Sign in as Amit, then test a denied account and an expired session. | Account role, assignment boundary and whether the private source workbook remained inaccessible. |
| 14:10–14:25 | Review one enquiry for each of the five roles. Record first contact, qualification evidence and the proposal for owner review. | First-contact delay, hands-on minutes, completed proposals, owner review delay and any backlog. |
| 14:25–14:35 | Repeat the same person across roles. Exercise uncertain history, lost acknowledgments and withdrawal. | Number of unique accepted results, unresolved decisions and items held from imports. |
| 14:35–14:45 | Repeat assigned-entry and enquiry steps on a phone. | Save, error recovery, keyboard or touch issues, and whether test traffic stayed excluded. |
| 14:45–14:55 | Simulate a failed import, privacy request and uncovered absence. | Who acts, when the backlog becomes unmanageable, how a pause would be requested and when coverage resumes. |
| 14:55–15:00 | Record results and unresolved failures. | Owner review reference and explicit pass or hold for the rehearsal. |

For each synthetic case, keep a private row with the case key, accepted time, assignment time, first documented outreach attempt, successful contact time if any, staff completion, hands-on minutes, outcome and any rework. Use Dubai local time. Measure the 30-minute response target from acceptance to the first documented call or message attempt, counting only staffed minutes. Record successful contact separately. An unanswered attempt cannot establish contactability or qualification. Report any late or missing attempt separately and publish only aggregates and review references, without contact details or production record IDs.

## Verify operating capacity separately

1. Record the owner-reviewed workload for the full AED 2,000 aggregate average daily allocation, including peak arrivals and existing work. Keep the forecast separate from measured throughput.
2. Measure completed enquiries and first-contact delays across a representative staffed workload, including non-enquiry work, pauses, retries and owner review. Record opening and ending backlog. Do not multiply a short rehearsal result into a measured daily capacity.
3. Compare the observed daily capacity with the reviewed launch load and check the 30-minute first-contact target under peak arrivals. The full 10:00–19:00 shift is 540 minutes. At the stated estimate of 300 enquiries, even a shift with no breaks or other duties would allow only 1.8 staff minutes per enquiry. This arithmetic is an upper bound on available time per enquiry, with no assumption that the workload can be met.
4. Record the completed rehearsal and measured capacity evidence references, the reviewed daily load, coverage hours and pause contingency. For the peak workload, record the number of observed first-contact cases and the longest delay in whole seconds. Count any case still awaiting first contact after 30 minutes as a miss and keep the gate open. Activation evidence needs a nonempty representative sample with a maximum of 1,800 seconds. Leave the release gate open until the owner reviews the evidence. An unconfirmed session or an uncovered shift cannot support release.

Run `python -B tools/release-control/staff_timing.py <private-timing.json>` from the repository root. Supply only an `as_of_utc` timestamp and a `cases` array with a unique opaque `case_key`, `accepted_at_utc`, and `first_attempt_at_utc` (null if pending). Use whole UTC seconds ending in `Z`. The calculator emits only aggregate counts and the longest observed delay. Include missing and late attempt counts in the activation packet. Both must be zero in the reviewed sample. Keep the input file private and verify the sample's workload and coverage separately.

For workload arithmetic, run `python -B tools/release-control/staff_timing.py --capacity <private-daily-totals.json>`. Supply a `days` array with one row per reviewed Dubai date. Each row has `dubai_date`, `opening_backlog`, `arrivals`, `completed`, and `closing_backlog`. Use Dubai calendar-day boundaries, including arrivals outside the staffed shift. Use consistent case definitions and count each completion once. Reconcile transfers or other adjustments separately before using this simple daily balance. The tool checks each day's balance and continuity on adjacent dates. It reports gaps, observed completions and backlog growth as aggregates. Verify full-shift coverage and representative workload separately. The minimum observed completions do not establish launch capacity by themselves.

Attach the calculator's aggregate JSON output from the owner-reviewed, representative full-load sample as the staff gate's `workload_summary` file reference (`path` and `sha256`). The claimed daily capacity cannot exceed the lowest observed daily completion count in that sample. Keep the aggregate receipt in the private packet workspace. Keep raw dates, counts by day and case records out of the packet. The owner still verifies staffing coverage, representativeness and any backlog concerns.

## 4 November rehearsal status

The owner confirmed in Codex that Amit completed the 14:00–15:00 Dubai rehearsal on 4 November and that private evidence is available. The evidence location is pending. The rehearsal is owner-reported complete, with exercise results still to be verified. Representative workload, backlog and first-contact timing evidence are separate from rehearsal completion. The 300 enquiries/day estimate remains unverified and the staff activation gate remains open. [Issue #4](https://github.com/azrsk11-maker/BSRS_G-Ad_Codex-/issues/4)

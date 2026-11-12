# Consent retention implementation correction (2026-11-11)

The cleanup worker introduced in local commit `cb6c2ce` was withdrawn in `07f6f86`. It changed the byte-pinned primary WordPress fixture and failed the existing provenance and source-derived integration checks. The original fixture, candidate source pin and backend receipt were restored; the withdrawn worker is not a retained executable candidate.

- The primary fixture preserves the reviewed 30-member package and continues to report retention deletion as unimplemented.
- Continue through the existing [per-choice planner](../../tools/consent-retention/per-choice/README.md), [selective SQL application](../../tools/consent-retention/per-choice/SELECTIVE_APPLICATION.md), and [purpose-history integration](../../tools/consent-retention/per-choice/PURPOSE_INTEGRATION.md). These candidates cover individual Dubai calendar-month deadlines and necessary submitted/withdrawal history, with separate lab guards, source bindings and concurrency checks.
- The [closed-enquiry workflow](../../tools/closed-enquiry-retention/README.md) separately models the adopted twelve-month-after-closure policy and owner-controlled marketing-mailbox action. Production collectors, provider acceptance and authorization remain required.

The withdrawn worker was not policy-equivalent: it used a fixed 365-day duration, required preference expiry to predate the annual cutoff, and excluded only recent captures. Those conditions could delay never-submitted choice retirement and remove history still required by older submitted enquiries. Reuse the existing candidates rather than treating the discarded worker or its former source-pattern tests as retention acceptance.

This is a correction and continuation pointer. The withdrawn change was never deployed to WordPress or production. No retention deployment, deletion, Ads, tracking, workbook, permission or financial change is authorized by this note.

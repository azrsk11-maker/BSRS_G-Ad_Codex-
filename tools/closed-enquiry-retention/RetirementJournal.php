<?php
declare(strict_types=1);
namespace BSRE\ClosedRetention;

/** Internal Journal capability; the nominated owner controller supplies exact authorization. */
trait RetirementJournal
{
    public function assertRetirementOpen(): void
    {
        if ($this->unresolvedRetirementCount() !== 0) throw new Failure('RETIREMENT_CUSTODY_RECONCILIATION_REQUIRED');
    }

    public function stageRetirement(array &$record, int $now): void
    {
        RetirementIntent::validateRecord($record, $now);
        $plan = $record['plan']; $id = $plan['closure_id'];
        $this->assertClosureLease($id);
        $this->assertRetirementOpen();
        if ($record['revision'] !== 0 || $record['phase'] !== 'INTENT_RECORDED' || $now >= $plan['expires_at']
            || $this->journal($plan['digest']) !== null || $this->closure($id) !== $plan['before']) throw new Failure('RETIREMENT_STAGE_CONFLICT');
        $this->assertNoClosureJobs($id);
        $this->pinAdmissionFloor($plan['admission_hash']);
        if ($this->admissionFloor() !== $plan['admission_hash']) throw new Failure('RETIREMENT_ADMISSION_FLOOR_CONFLICT');
        $this->save($record);
        if ($this->journal($plan['digest']) !== $record) throw new Failure('RETIREMENT_DURABLE_INTENT_REQUIRED');
    }

    public function assertRetirementSource(array $record, int $now): void
    {
        RetirementIntent::validateRecord($record, $now);
        $plan = $record['plan']; $id = $plan['closure_id'];
        $this->assertClosureLease($id);
        $this->assertRetirementOpen();
        if ($record['revision'] < 1 || $this->journal($plan['digest']) !== $record
            || $this->admissionFloor() !== $plan['admission_hash']) throw new Failure('RETIREMENT_DURABLE_INTENT_REQUIRED');
        $this->assertNoClosureJobs($id, $plan['digest']);
        $current = $this->closure($id);
        if ($current !== $plan['before'] && $current !== $plan['after']) throw new Failure('CLOSURE_BASELINE_CHANGED');
    }

    public function commitRetirement(array $record, array $proof, int $now): void
    {
        RetirementIntent::validateRecord($record, $now);
        $plan = $record['plan']; $id = $plan['closure_id'];
        $this->assertRetirementSource($record, $now);
        if ($record['phase'] === 'INTENT_RECORDED') throw new Failure('RETIREMENT_DURABLE_INTENT_REQUIRED');
        RetirementIntent::verifiedFence($record, $proof, $now);
        $current = $this->closure($id);
        if ($current === $plan['after']) return; // Exact acknowledgement recovery; no second revision.
        if ($current !== $plan['before']) throw new Failure('CLOSURE_BASELINE_CHANGED');
        $this->writeClosure($plan['before'], $plan['after']);
    }

    /** Privacy cleanup only. Never deletes a closure, sender fence, provider row or purge job. */
    public function scrubRetirement(array $record, int $now): bool
    {
        RetirementIntent::validateRecord($record, $now);
        $plan = $record['plan']; $id = $plan['closure_id'];
        $this->assertClosureLease($id);
        $current = $this->journal($plan['digest']);
        if ($current === null) return false;
        if ($current !== $record) throw new Failure('RETIREMENT_DURABLE_INTENT_REQUIRED');
        if ($now < $record['recovery_until']) throw new Failure('RETIREMENT_RECOVERY_WINDOW_OPEN');
        $closure = $this->closure($id);
        $unresolved = $this->unresolvedRetirementCount();
        $this->forget($id, $plan['digest'], true);
        if ($this->journal($plan['digest']) !== null || $this->closure($id) !== $closure
            || $this->unresolvedRetirementCount() <= $unresolved) throw new Failure('RETIREMENT_SCRUB_UNCONFIRMED');
        return true;
    }
}

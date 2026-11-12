<?php
declare(strict_types=1);
namespace BSRE\ClosedRetention;

/** Shared candidate rules; production source/identity-index/migration custody remains a deployment gate. */
trait ClosureCollectionJournal
{
    public function assertCollectionTarget(array $target, bool $allowExact = false): void
    {
        Workflow::validateClosureRecord($target, time());
        $id = $target['closure_id'];
        if ($id !== $target['request_id'] || $target['revision'] !== 1
            || !in_array($target['email_status'], ['SENT', 'QUEUED', 'RETRY_WAIT', 'NEEDS_REVIEW'], true)
            || (($target['email_status'] === 'SENT') !== ($target['mail_message_ids'] !== []))) throw new Failure('COLLECTION_TARGET_INVALID');
        $this->assertClosureLease($id);
        $this->assertRetirementOpen();
        $this->assertNoClosureJobs($id);
        foreach ($this->collectionRows() as $key => $row) {
            if (!is_array($row) || ($row['closure_id'] ?? null) !== $key) throw new Failure('COLLECTION_REGISTRY_UNVERIFIED');
            try { Workflow::validateClosureRecord($row, time()); }
            catch (\Throwable $error) { throw new Failure('COLLECTION_REGISTRY_UNVERIFIED'); }
            if ($key === $id && $allowExact && $row === $target) continue;
            if ($key === $id || $row['request_id'] === $target['request_id'] || $row['lead_id'] === $target['lead_id']
                || $row['event_id'] === $target['event_id']
                || array_intersect($row['outcome_ids'], $target['outcome_ids']) !== []
                || array_intersect($row['mail_message_ids'], $target['mail_message_ids']) !== []) throw new Failure('COLLECTION_IDENTITY_ALREADY_BOUND');
        }
    }

    public function insertClosure(array $target): void
    {
        $this->assertCollectionTarget($target);
        $this->createCollectedClosure($target);
        if ($this->closure($target['closure_id']) !== $target) throw new Failure('COLLECTION_WRITE_UNCONFIRMED');
    }
}

<?php
declare(strict_types=1);
namespace BSRE\PurposeRetention;

/** Extend the existing bounded policy without discarding new private evidence. */
final class RetentionInventory {
    public const KIND = \BSRE\RetentionReview\RetentionInventory::KIND;
    public const MAX_ROWS = \BSRE\RetentionReview\RetentionInventory::MAX_ROWS;
    private const EXTRA = ['purpose_version','purpose_hash','purpose_record_hash','purpose_json'];
    public static function plan(array $snapshot, int $now, bool $enabled = false): array {
        $projected = $snapshot;
        if (isset($projected['captures']) && is_array($projected['captures'])) {
            foreach ($projected['captures'] as &$capture) {
                if (!is_array($capture)) throw new \RuntimeException('PURPOSE_RETENTION_SCHEMA_INVALID');
                self::validate($capture);
                foreach (self::EXTRA as $key) unset($capture[$key]);
            }
            unset($capture);
        }
        return \BSRE\RetentionReview\RetentionInventory::plan($projected, $now, $enabled);
    }
    private static function validate(array $capture): void {
        $present = array_intersect(self::EXTRA, array_keys($capture));
        if (!$present) return; // Old backup remains legacy/unknown; never inferred.
        if (count($present) !== count(self::EXTRA) || !in_array($capture['purpose_version'], [0,1,'0','1'], true)) throw new \RuntimeException('PURPOSE_RETENTION_SCHEMA_INVALID');
        if ((int) $capture['purpose_version'] === 0) {
            if ($capture['purpose_hash'] !== '' || $capture['purpose_record_hash'] !== '' || !in_array($capture['purpose_json'], ['',null], true)) throw new \RuntimeException('PURPOSE_RETENTION_SCHEMA_INVALID');
        } else \BSRE\PurposeAttribution\assert_record($capture);
    }
    public static function assertRestoreReferences(array $snapshot, array $retired): void {
        foreach ($snapshot['captures'] as $capture) {
            self::validate($capture);
            if ((int) ($capture['purpose_version'] ?? 0) !== 1) continue;
            $record = json_decode($capture['purpose_json'], true, 12, JSON_THROW_ON_ERROR);
            foreach (['analytics','advertising'] as $purpose) foreach (['first','last'] as $slot) {
                $touch = $record[$purpose][$slot] ?? null;
                if ($touch !== null && isset($retired[$touch['decision_version']])) throw new \RuntimeException('RESTORED_CAPTURE_REQUIRES_RECONCILIATION');
            }
        }
    }
}

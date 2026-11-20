<?php
declare(strict_types=1);
namespace BSRE\RetentionReview\PerChoice;

require_once dirname(__DIR__) . '/RetentionInventory.php';
use BSRE\RetentionReview\RetentionInventory;

/** Pure synthetic planning only. It has no database, deletion, scheduler or provider API. */
final class PerChoicePlanner
{
    public const SCHEMA = 'SYNTHETIC_PER_CHOICE_PLAN_V1';
    public const COVERAGE = 'SYNTHETIC_PER_CHOICE_COVERAGE_V1';
    private const MAX_CLOCK = 4102444800;
    private const PREFERENCE_SECONDS = 15552000;
    private const NUMBERS = ['revision','original_revision','changed_at','expires_at','preference_expires_at',
        'created_at','gclid_first_captured_ms','gclid_last_captured_ms','analytics','ad_measurement',
        'personalization','uncertain','eligible','known','delivery_pending'];

    /** Bounded scalar-only copy also isolates caller-owned PHP references from the old normalizer. */
    private static function copy(array $value): array
    {
        $nodes = 0; $textBytes = 0;
        $sort = static function ($item, int $depth = 0) use (&$sort, &$nodes, &$textBytes) {
            if (++$nodes > 40000 || $depth > 8) self::invalid();
            if (!is_array($item)) {
                if (!is_null($item) && !is_string($item) && !is_int($item) && !is_bool($item) && !is_float($item)) self::invalid();
                if (is_string($item)) $textBytes += strlen($item);
                if ($textBytes > 8000000) self::invalid();
                return $item;
            }
            $keys = array_keys($item);
            if (!array_is_list($item)) sort($keys, SORT_STRING);
            $result = [];
            foreach ($keys as $key) {
                if (is_string($key)) { if (strlen($key) > 128) self::invalid(); $textBytes += strlen($key); }
                $result[$key] = $sort($item[$key], $depth + 1);
            }
            return $result;
        };
        return $sort($value);
    }

    /** Canonical digest preserves original scalar types and list order. Not a source certificate. */
    public static function digest(array $value): string
    {
        try {
            $bytes = json_encode(self::copy($value), JSON_THROW_ON_ERROR);
            if (strlen($bytes) > 8000000) self::invalid();
            return hash('sha256', $bytes);
        }
        catch (\Throwable $error) { self::invalid(); }
    }

    /** Private result contains exact synthetic row references; do not publish or log real inputs. */
    public static function plan(array $snapshot, array $coverage, int $now, bool $enabled = false): array
    {
        $result = ['schema'=>self::SCHEMA, 'mode'=>'DISABLED', 'execution'=>'NONE',
            'apply_supported'=>false, 'source_authenticated'=>false, 'production_eligibility'=>'UNASSESSED',
            'production_authorized'=>false, 'rows'=>[], 'global_reasons'=>[]];
        if (!$enabled) return $result;
        if ($now <= 0 || $now > self::MAX_CLOCK) self::invalid();
        $snapshot = self::copy($snapshot);
        // Reuse exact baseline schema/size/calendar validation without changing its policy or pin.
        try { RetentionInventory::plan($snapshot, $now, true); }
        catch (\Throwable $error) { self::invalid(); }
        self::keys($coverage, ['kind','snapshot_sha256','status','observed_at','valid_until','history_pruned']);
        if ($coverage['kind'] !== self::COVERAGE ||
            !is_string($coverage['snapshot_sha256']) || !preg_match('/^[a-f0-9]{64}$/D', $coverage['snapshot_sha256']) ||
            !in_array($coverage['status'], ['COMPLETE_SYNTHETIC','UNKNOWN'], true) ||
            !is_int($coverage['observed_at']) || !is_int($coverage['valid_until']) ||
            !is_bool($coverage['history_pruned'])) self::invalid();
        $snapshotDigest = self::digest($snapshot);
        $global = [];
        if (!hash_equals($snapshotDigest, $coverage['snapshot_sha256'])) $global[] = 'COVERAGE_SNAPSHOT_MISMATCH';
        if ($coverage['status'] !== 'COMPLETE_SYNTHETIC') $global[] = 'COVERAGE_UNKNOWN';
        if ($coverage['observed_at'] <= 0 || $coverage['observed_at'] > $now ||
            $coverage['valid_until'] <= $coverage['observed_at'] || $now >= $coverage['valid_until'] ||
            $coverage['valid_until'] > self::MAX_CLOCK) $global[] = 'COVERAGE_CLOCK_UNRESOLVED';
        if ($coverage['history_pruned']) $global[] = 'PRUNED_HISTORY_REQUIRES_RECONCILIATION';

        $tables = [];
        foreach (RetentionInventory::COLUMNS as $table => $_) {
            $tables[$table] = $snapshot[$table];
            foreach ($tables[$table] as &$row) {
                foreach (self::NUMBERS as $key) if (array_key_exists($key, $row)) $row[$key] = (int)$row[$key];
            }
            unset($row);
        }
        foreach ($tables as $table => $rows) foreach ($rows as $row) {
            $time = $row[$table === 'captures' ? 'created_at' : 'changed_at'];
            if ($time > $coverage['observed_at']) $global[] = 'COVERAGE_PREDATES_SNAPSHOT_ROW';
        }
        $states = []; $histories = []; $subjects = []; $holds = []; $receiptOwners = [];
        foreach ($tables['state'] as $row) {
            $s = $row['subject_key']; $subjects[$s] = true;
            if (isset($states[$s])) $holds[$s][] = 'DUPLICATE_CURRENT_STATE';
            $states[$s] = $row;
        }
        foreach ($tables['history'] as $row) {
            $s = $row['subject_key']; $subjects[$s] = true; $r = $row['revision'];
            if (isset($histories[$s][$r])) $holds[$s][] = 'DUPLICATE_HISTORY_REVISION';
            if (isset($receiptOwners[$row['receipt']])) $global[] = 'DUPLICATE_HISTORY_RECEIPT';
            $receiptOwners[$row['receipt']] = $s;
            $histories[$s][$r] = $row;
        }
        foreach ($subjects as $s => $_) {
            $state = $states[$s] ?? null; $history = $histories[$s] ?? [];
            if (!$state || !$history) $holds[$s][] = 'CURRENT_HISTORY_LINEAGE_MISSING';
            ksort($history, SORT_NUMERIC); $expected = 1; $previous = 0;
            foreach ($history as $revision => $row) {
                if ($revision !== $expected++) $holds[$s][] = 'HISTORY_GAP';
                if ($row['changed_at'] < $previous) $holds[$s][] = 'HISTORY_TIME_REGRESSION';
                $previous = $row['changed_at'];
            }
            if ($state && $history) {
                $last = end($history);
                foreach (RetentionInventory::COLUMNS['history'] as $field) {
                    if ($state[$field] !== $last[$field]) { $holds[$s][] = 'CURRENT_HISTORY_MISMATCH'; break; }
                }
                if ($state['revision'] < 1 || $state['receipt'] === '' ||
                    $state['changed_at'] > PHP_INT_MAX - self::PREFERENCE_SECONDS ||
                    $state['expires_at'] !== $state['changed_at'] + self::PREFERENCE_SECONDS) {
                    $holds[$s][] = 'CURRENT_PREFERENCE_WINDOW_UNRESOLVED';
                }
            }
            foreach (array_merge($state ? [$state] : [], array_values($history)) as $row) {
                if ($row['changed_at'] <= 0 || $row['changed_at'] > $now) $holds[$s][] = 'CHOICE_CLOCK_UNRESOLVED';
                if ($row['uncertain'] !== 0 || $row['personalization'] !== 0 || $row['receipt'] === '' || $row['notice_version'] === '') {
                    $holds[$s][] = 'CHOICE_PERMISSION_UNRESOLVED';
                }
            }
        }

        $requests = []; $protectFrom = []; $captureReasons = [];
        foreach ($tables['captures'] as $index => $capture) {
            $s = $capture['subject_key']; $reasons = ['CAPTURE_OUTSIDE_NEVER_SUBMITTED_SCOPE'];
            $request = $capture['request_id']; $captureDigest = self::digest($capture);
            if (isset($requests[$request])) {
                $global[] = hash_equals($requests[$request], $captureDigest) ? 'DUPLICATE_CAPTURE_REQUEST' : 'CONFLICTING_CAPTURE_RETRY';
            }
            $requests[$request] = $captureDigest;
            if ($s === '') $global[] = 'UNLINKED_CAPTURE_PREVENTS_SUBJECT_EXCLUSION';
            if (isset($receiptOwners[$capture['decision_version']]) && $receiptOwners[$capture['decision_version']] !== $s) {
                $global[] = 'CAPTURE_SUBJECT_RECEIPT_CONFLICT';
            }
            $original = $histories[$s][$capture['original_revision']] ?? null;
            $accepted = $capture['state'] === 'ACCEPTED' && $capture['lead_id'] !== '' && $capture['event_id'] !== '';
            $staged = $capture['state'] === 'STAGED' && $capture['lead_id'] === '' && $capture['event_id'] === '';
            $linked = $s !== '' && isset($states[$s]) && $original !== null &&
                $capture['known'] === 1 && $capture['uncertain'] === 0 && $capture['personalization'] === 0 &&
                $capture['created_at'] > 0 && $capture['created_at'] <= $now && ($accepted || $staged);
            if ($linked) {
                foreach (['analytics','ad_measurement','personalization','notice_version'] as $key) {
                    if ($original[$key] !== $capture[$key]) $linked = false;
                }
                if ($original['receipt'] !== $capture['decision_version'] || $original['changed_at'] > $capture['created_at'] ||
                    $capture['preference_expires_at'] !== $original['changed_at'] + self::PREFERENCE_SECONDS ||
                    $capture['created_at'] >= $capture['preference_expires_at']) $linked = false;
                // Seconds cannot establish ordering at a later choice's exact boundary.
                // A retry must retain its ORIGINAL capture time, not the processing time.
                $next = $capture['original_revision'] < PHP_INT_MAX ?
                    ($histories[$s][$capture['original_revision'] + 1] ?? null) : null;
                if ($next !== null && $capture['created_at'] >= $next['changed_at']) $linked = false;
            }
            if ($linked) {
                $protectFrom[$s] = min($protectFrom[$s] ?? PHP_INT_MAX, $capture['original_revision']);
                $reasons[] = $accepted ? 'SUBMITTED_EVIDENCE_PROTECTED' : 'IN_FLIGHT_EVIDENCE_PROTECTED';
            } else {
                $reasons[] = 'CAPTURE_LINEAGE_UNRESOLVED';
                if ($s !== '') $holds[$s][] = 'CAPTURE_LINEAGE_UNRESOLVED';
            }
            $captureReasons[$index] = $reasons;
        }
        $global = self::reasons($global);
        $result['mode'] = 'SYNTHETIC_REVIEW_ONLY';
        $result['snapshot_sha256'] = $snapshotDigest;
        $result['coverage_sha256'] = self::digest($coverage);
        $result['evaluated_at'] = $now;
        $result['global_reasons'] = $global;
        $counts = ['due_unreferenced_choice_rows'=>0, 'held_choice_rows'=>0, 'protected_capture_rows'=>0];
        foreach ($tables as $table => $rows) {
            foreach ($rows as $index => $row) {
                $s = $row['subject_key']; $reasons = array_merge($global, $holds[$s] ?? []); $deadline = null;
                if ($table === 'captures') {
                    $classification = 'PROTECTED_CAPTURE_OUTSIDE_SCOPE'; ++$counts['protected_capture_rows'];
                    $reasons = array_merge($reasons, $captureReasons[$index]);
                } else {
                    if ($row['changed_at'] > 0 && $row['changed_at'] <= $now) {
                        $due = RetentionInventory::anniversary($row['changed_at']);
                        $deadline = (new \DateTimeImmutable('@'.$due))->setTimezone(new \DateTimeZone('Asia/Dubai'))->format('Y-m-d\TH:i:sP');
                        if ($now < $due) $reasons[] = 'TWELVE_MONTH_CHOICE_RETENTION_NOT_DUE';
                    } else $reasons[] = 'CHOICE_CLOCK_UNRESOLVED';
                    if (isset($protectFrom[$s])) {
                        if ($table === 'state') $reasons[] = 'CURRENT_CAPTURE_AUTHORITY_REQUIRED';
                        elseif ($row['revision'] >= $protectFrom[$s]) $reasons[] = 'CAPTURE_AND_WITHDRAWAL_HISTORY_REQUIRED';
                    }
                    if (isset($states[$s]) && $row['receipt'] === $states[$s]['receipt'] && $states[$s]['expires_at'] > $now) {
                        $reasons[] = 'CURRENT_PREFERENCE_ACTIVE';
                    }
                    $classification = $reasons ? 'HOLD' : 'DUE_UNREFERENCED_SYNTHETIC_REVIEW';
                    ++$counts[$classification === 'HOLD' ? 'held_choice_rows' : 'due_unreferenced_choice_rows'];
                }
                $pk = ['state'=>'subject_key','history'=>'receipt','captures'=>'request_id'][$table];
                $result['rows'][] = ['row_ref'=>'bsre_consent_'.$table.':'.$row[$pk], 'classification'=>$classification,
                    'deadline_dubai'=>$deadline, 'reasons'=>self::reasons($reasons)];
            }
        }
        usort($result['rows'], static fn($a,$b) => strcmp($a['row_ref'], $b['row_ref']));
        $result['counts'] = $counts;
        $result['plan_sha256'] = self::digest($result);
        return $result;
    }

    private static function reasons(array $reasons): array
    {
        $reasons = array_values(array_unique($reasons)); sort($reasons, SORT_STRING); return $reasons;
    }
    private static function keys(array $value, array $expected): void
    {
        $actual = array_keys($value); sort($actual); sort($expected); if ($actual !== $expected) self::invalid();
    }
    private static function invalid(): never
    {
        throw new \InvalidArgumentException('INVALID_OR_UNBOUNDED_SYNTHETIC_PER_CHOICE_INPUT');
    }
}

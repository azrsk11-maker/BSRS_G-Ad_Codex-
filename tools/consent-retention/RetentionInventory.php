<?php
declare(strict_types=1);

namespace BSRE\RetentionReview;

/** Pure, disabled-by-default policy review; deliberately has no WordPress adapter. */
final class RetentionInventory
{
    public const KIND = 'SYNTHETIC_INCOMPLETE';
    public const MAX_ROWS = 1000;
    public const COLUMNS = [
        'state' => ['subject_key','revision','receipt','analytics','ad_measurement','personalization','notice_version','changed_at','expires_at','uncertain'],
        'history' => ['receipt','subject_key','revision','analytics','ad_measurement','personalization','notice_version','changed_at','uncertain'],
        'captures' => ['request_id','fingerprint','subject_key','original_revision','decision_version','notice_version','analytics','ad_measurement','personalization','preference_expires_at','eligible','known','created_at','state','uncertain','delivery_pending','click_capture_state','gclid_first','gclid_last','gclid_first_captured_ms','gclid_last_captured_ms','lead_id','event_id'],
    ];
    private const UINTS = ['revision','original_revision','changed_at','expires_at','preference_expires_at','created_at','gclid_first_captured_ms','gclid_last_captured_ms'];
    private const BITS = ['analytics','ad_measurement','personalization','uncertain','eligible','known','delivery_pending'];
    private const LENGTHS = ['subject_key'=>64,'receipt'=>32,'request_id'=>36,'fingerprint'=>64,'decision_version'=>32,'notice_version'=>64,'state'=>16,'click_capture_state'=>16,'gclid_first'=>256,'gclid_last'=>256,'lead_id'=>64,'event_id'=>64];

    /** Arrays contain exact consent-store.php columns, never decorated exportRows output. */
    public static function plan(array $snapshot, int $now, bool $enabled = false): array
    {
        $result = ['kind'=>self::KIND, 'mode'=>'DISABLED', 'execution'=>'NONE',
            'production_eligibility'=>'UNASSESSED', 'rows'=>[]];
        if (!$enabled) return $result;
        self::keys($snapshot, ['kind','state','history','captures']);
        if ($snapshot['kind'] !== self::KIND || $now <= 0) self::invalid();
        // A caller-provided "complete" or "reviewed" flag cannot establish provenance.
        $tables = []; $count = 0;
        foreach (self::COLUMNS as $table => $columns) {
            if (!is_array($snapshot[$table]) || !array_is_list($snapshot[$table])) self::invalid();
            $count += count($snapshot[$table]);
            if ($count > self::MAX_ROWS) self::invalid();
            $tables[$table] = array_map(fn($row) => self::normalize($table, $row), $snapshot[$table]);
        }
        $result['mode'] = 'REVIEW_ONLY';
        $states = []; $histories = []; $subjects = []; $holds = []; $global = [];
        $historyReceipts = []; $requests = [];
        foreach ($tables['state'] as $row) {
            $s = $row['subject_key']; $subjects[$s] = true;
            if (isset($states[$s])) $holds[$s][] = 'DUPLICATE_CURRENT_STATE';
            $states[$s] = $row;
        }
        foreach ($tables['history'] as $row) {
            $s = $row['subject_key']; $subjects[$s] = true; $r = $row['revision'];
            if (isset($histories[$s][$r])) $holds[$s][] = 'DUPLICATE_HISTORY_REVISION';
            if (isset($historyReceipts[$row['receipt']])) {
                $holds[$s][] = 'DUPLICATE_HISTORY_RECEIPT';
                $holds[$historyReceipts[$row['receipt']]][] = 'DUPLICATE_HISTORY_RECEIPT';
            }
            $historyReceipts[$row['receipt']] = $s;
            $histories[$s][$r] = $row;
        }
        foreach ($subjects as $s => $_) {
            $current = $states[$s] ?? null; $history = $histories[$s] ?? [];
            if (!$current) $holds[$s][] = 'CURRENT_STATE_MISSING';
            if (!$history) $holds[$s][] = 'HISTORY_MISSING';
            if ($current && ($current['revision'] < 1 || $current['receipt'] === '' || $current['notice_version'] === '')) $holds[$s][] = 'CHOICE_UNRESOLVED';
            ksort($history, SORT_NUMERIC); $expected = 1; $previousTime = 0;
            foreach ($history as $r => $row) {
                if ($r !== $expected++) $holds[$s][] = 'HISTORY_GAP';
                if ($row['changed_at'] < $previousTime) $holds[$s][] = 'HISTORY_TIME_REGRESSION';
                $previousTime = $row['changed_at'];
            }
            if ($current && $history) {
                $last = end($history);
                foreach (self::COLUMNS['history'] as $field) {
                    if ($current[$field] !== $last[$field]) { $holds[$s][] = 'CURRENT_HISTORY_MISMATCH'; break; }
                }
            }
            foreach (array_merge($current ? [$current] : [], array_values($history)) as $row) {
                if ($row['changed_at'] <= 0 || $row['changed_at'] > $now) $holds[$s][] = 'CHOICE_TIME_UNRESOLVED';
                if ($row['uncertain'] !== 0) $holds[$s][] = 'CHOICE_UNCERTAIN';
                if ($row['personalization'] !== 0) $holds[$s][] = 'PERSONALIZATION_UNSUPPORTED';
                if ($row['notice_version'] === '' || $row['receipt'] === '') $holds[$s][] = 'CHOICE_UNRESOLVED';
            }
            if ($current) {
                if ($current['expires_at'] < $current['changed_at']) $holds[$s][] = 'PREFERENCE_EXPIRY_INVALID';
                if ($current['expires_at'] > $now) $holds[$s][] = 'CURRENT_PREFERENCE_ACTIVE';
                if ($current['changed_at'] > 0 && self::anniversary($current['changed_at']) > $now) $holds[$s][] = 'CURRENT_SUBJECT_RETENTION_NOT_DUE';
            }
        }
        $captureReasons = [];
        foreach ($tables['captures'] as $i => $row) {
            $s = $row['subject_key']; $reasons = ['CAPTURE_REQUIRES_RETENTION_RESOLUTION'];
            if ($s === '') {
                $global[] = 'UNLINKED_CAPTURE_PREVENTS_SUBJECT_EXCLUSION';
                $reasons[] = 'CAPTURE_SUBJECT_UNKNOWN';
            }
            if (isset($requests[$row['request_id']])) {
                // Duplicate requests can cross subjects; no partial classification is trusted.
                $global[] = 'DUPLICATE_CAPTURE_REQUEST';
            }
            $requests[$row['request_id']] = true;
            if ($row['state'] === 'ACCEPTED' || $row['lead_id'] !== '' || $row['event_id'] !== '') {
                $reasons[] = 'SUBMITTED_CLOSURE_INTERFACE_MISSING';
                if ($row['state'] !== 'ACCEPTED' || $row['lead_id'] === '' || $row['event_id'] === '') $reasons[] = 'CAPTURE_LINK_INCONSISTENT';
            } elseif ($row['state'] === 'STAGED') $reasons[] = 'IN_FLIGHT_CAPTURE';
            else $reasons[] = 'CAPTURE_OUTCOME_UNKNOWN';
            if ($row['delivery_pending'] !== 0) $reasons[] = 'CAPTURE_DELIVERY_PENDING';
            if ($row['uncertain'] !== 0 || $row['known'] !== 1) $reasons[] = 'CAPTURE_PERMISSION_UNRESOLVED';
            if ($row['created_at'] <= 0 || $row['created_at'] > $now) $reasons[] = 'CAPTURE_TIME_UNRESOLVED';
            if ($row['personalization'] !== 0) $reasons[] = 'PERSONALIZATION_UNSUPPORTED';
            $original = $histories[$s][$row['original_revision']] ?? null;
            if (!$original || !isset($states[$s])) $reasons[] = 'CAPTURE_ORIGINAL_EVIDENCE_MISSING';
            elseif ($row['known'] === 1) {
                foreach (['analytics','ad_measurement','personalization','notice_version'] as $field) {
                    if ($original[$field] !== $row[$field]) { $reasons[] = 'CAPTURE_ORIGINAL_DECISION_MISMATCH'; break; }
                }
                if ($original['receipt'] !== $row['decision_version'] || $original['changed_at'] > $row['created_at']) $reasons[] = 'CAPTURE_ORIGINAL_DECISION_MISMATCH';
            }
            $captureReasons[$i] = $reasons;
            if ($s !== '') $holds[$s] = array_merge($holds[$s] ?? [], $reasons);
        }
        foreach ($tables as $table => $rows) {
            foreach ($rows as $i => $row) {
                $s = $row['subject_key']; $reasons = array_merge($global, $holds[$s] ?? []);
                $deadline = null;
                if ($table === 'captures') $reasons = array_merge($reasons, $captureReasons[$i]);
                elseif ($row['changed_at'] > 0 && $row['changed_at'] <= $now) {
                    $due = self::anniversary($row['changed_at']);
                    $deadline = self::format($due);
                    if ($due > $now) $reasons[] = 'TWELVE_MONTH_CHOICE_RETENTION_NOT_DUE';
                }
                $classification = $reasons ? 'HOLD' : 'AGE_ELIGIBLE_FOR_REVIEW';
                $reasons[] = 'SYNTHETIC_SNAPSHOT_LIVE_LINK_COVERAGE_UNVERIFIED';
                if ($classification === 'AGE_ELIGIBLE_FOR_REVIEW') $reasons[] = 'TWELVE_CALENDAR_MONTHS_REACHED_IN_SUPPLIED_SNAPSHOT';
                $reasons = array_values(array_unique($reasons)); sort($reasons, SORT_STRING);
                $pk = ['state'=>'subject_key','history'=>'receipt','captures'=>'request_id'][$table];
                $result['rows'][] = ['row_ref'=>'bsre_consent_'.$table.':'.$row[$pk],
                    'classification'=>$classification, 'deadline_dubai'=>$deadline, 'reasons'=>$reasons];
            }
        }
        usort($result['rows'], fn($a,$b) => strcmp($a['row_ref'], $b['row_ref']));
        return $result;
    }

    /** Twelve Dubai calendar months, clamping 29 February to 28 February. */
    public static function anniversary(int $timestamp): int
    {
        if ($timestamp <= 0) self::invalid();
        $date = (new \DateTimeImmutable('@'.$timestamp))->setTimezone(new \DateTimeZone('Asia/Dubai'));
        $year = (int)$date->format('Y') + 1;
        if ($year > 9999) self::invalid();
        $month = (int)$date->format('n');
        $first = $date->setDate($year, $month, 1);
        return $first->setDate($year, $month, min((int)$date->format('j'), (int)$first->format('t')))->getTimestamp();
    }

    private static function normalize(string $table, $row): array
    {
        if (!is_array($row)) self::invalid();
        self::keys($row, self::COLUMNS[$table]);
        foreach ($row as $field => &$value) {
            if (in_array($field, array_merge(self::UINTS, self::BITS), true)) {
                if (is_string($value) && preg_match('/^(0|[1-9][0-9]*)$/D', $value) && strlen($value) <= strlen((string)PHP_INT_MAX)
                    && (strlen($value) < strlen((string)PHP_INT_MAX) || strcmp($value, (string)PHP_INT_MAX) <= 0)) $value = (int)$value;
                if (!is_int($value) || $value < 0 || (in_array($field, self::BITS, true) && $value > 1)) self::invalid();
            } elseif (!is_string($value) || strlen($value) > self::LENGTHS[$field]) self::invalid();
        }
        unset($value);
        foreach (['subject_key'=>64,'receipt'=>32,'fingerprint'=>64,'decision_version'=>32] as $field => $length) {
            if (!array_key_exists($field, $row)) continue;
            $emptyAllowed = ($field === 'subject_key' && $table === 'captures') || ($field === 'receipt' && $table === 'state');
            if (($row[$field] === '' && !$emptyAllowed) || ($row[$field] !== '' && !preg_match('/^[a-f0-9]{'.$length.'}$/D', $row[$field]))) self::invalid();
        }
        if ($table === 'captures' && !preg_match('/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/Di', $row['request_id'])) self::invalid();
        return $row;
    }
    private static function keys(array $value, array $expected): void
    {
        $actual = array_keys($value); sort($actual); sort($expected);
        if ($actual !== $expected) self::invalid();
    }
    private static function format(int $timestamp): string
    {
        return (new \DateTimeImmutable('@'.$timestamp))->setTimezone(new \DateTimeZone('Asia/Dubai'))->format('Y-m-d\TH:i:sP');
    }
    private static function invalid(): never
    {
        throw new \InvalidArgumentException('INVALID_OR_UNBOUNDED_SYNTHETIC_SNAPSHOT: no partial manifest produced.');
    }
}

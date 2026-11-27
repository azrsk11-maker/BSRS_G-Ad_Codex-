<?php
namespace BSRE\Enquiries;

/** Resolve presentation text only after the existing WordPress binding has passed. */
function offplan_presentation_locale(array $binding, string $request_target): string {
    if (($binding['id'] ?? null) !== 26751
        || !in_array($binding['mode'] ?? null, ['live', 'preview'], true)
        || ($binding['scope']['kind'] ?? null) !== 'service'
        || ($binding['scope']['slug'] ?? null) !== 'off-plan'
        || ($binding['scope']['path'] ?? null) !== '/enquire/off-plan/') {
        return 'en';
    }
    if (strlen($request_target) > 4096 || preg_match('~[\x00-\x20\x5c\x7f#]~', $request_target) !== 0) {
        return 'en';
    }
    [$path, $query] = array_pad(explode('?', $request_target, 2), 2, null);
    if ($path !== '/enquire/off-plan/' || $query === null || str_contains($query, ';')
        || preg_match('/%(?![0-9A-Fa-f]{2})/', $query) !== 0) {
        return 'en';
    }
    $pairs = explode('&', $query, 33);
    if (count($pairs) > 32) {
        return 'en';
    }
    $selected = null;
    foreach ($pairs as $pair) {
        [$key, $value] = array_pad(explode('=', $pair, 2), 2, null);
        $decoded = rawurldecode(str_replace('+', ' ', $key));
        if (preg_match('//u', $decoded) !== 1 || preg_match('~[\x00-\x20\x7f]~', $decoded) !== 0) {
            return 'en';
        }
        if ($decoded === 'bsre_locale') {
            if ($selected !== null || $key !== 'bsre_locale' || $value === null) {
                return 'en';
            }
            $selected = $value;
        } elseif (str_starts_with($decoded, 'bsre_locale[') || str_replace('.', '_', $decoded) === 'bsre_locale') {
            return 'en';
        }
    }
    return in_array($selected, ['de-DE', 'fr-FR', 'zh-Hant-TW'], true) ? $selected : 'en';
}

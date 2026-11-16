<?php
/** Private candidate. Read-only native ownership/metadata port; no activation or route registration. */
namespace BSRE\NativeTracking;
if (!defined('ABSPATH')) exit;

final class NativePageContext {
    private const PAGE_FIELDS = ['campaign_key','landing_page_id','page_version','page_family','property_destination','property_segment','transaction_intent','language','property_id','project_id'];
    private const CTA_FIELDS = ['cta_id','cta_type','cta_position','destination_key'];
    private const TYPES = ['ordinary','phone','whatsapp','email','brochure','floorplan','calculator','comparison','property','viewing','main_site'];
    private array $registry;

    /** Server-owned, reviewed configuration only. Never pass REST/query/form data here.
     * Catalog members are explicit reviewed non-sensitive business codes, not a PII detector.
     * Empty configuration still resolves existing owned service pages without invented campaign IDs.
     */
    public function __construct(array $registry = []) {
        if ($registry !== []) {
            if (!self::keys($registry, ['schema','revision','catalog','pages']) || $registry['schema'] !== 1
                || !self::code($registry['revision']) || !is_array($registry['catalog']) || !is_array($registry['pages'])
                || !array_is_list($registry['pages']) || count($registry['pages']) > 1000) throw new \InvalidArgumentException('NATIVE_REGISTRY_INVALID');
            foreach ($registry['catalog'] as $field => $values) {
                if (!in_array($field, self::PAGE_FIELDS, true) || !is_array($values) || !array_is_list($values)
                    || count($values) > 1000 || count($values) !== count(array_unique($values, SORT_REGULAR))) throw new \InvalidArgumentException('NATIVE_CATALOG_INVALID');
                foreach ($values as $value) if (!self::field($field, $value)) throw new \InvalidArgumentException('NATIVE_CATALOG_INVALID');
            }
            $ids = []; $paths = [];
            foreach ($registry['pages'] as $row) {
                if (!$this->valid_row($row, $registry['catalog']) || isset($ids[$row['native_page_id']]) || isset($paths[$row['page_path']])) throw new \InvalidArgumentException('NATIVE_PAGE_INVALID');
                $ids[$row['native_page_id']] = true; $paths[$row['page_path']] = true;
            }
        }
        $this->registry = $registry;
    }

    /** No option/URL fallback. The owning bootstrap supplies the exact reviewed constant, if any. */
    public static function wordpress(): self {
        $value = defined('BSRE_NATIVE_TRACKING_REGISTRY') ? constant('BSRE_NATIVE_TRACKING_REGISTRY') : [];
        if (!is_array($value)) throw new \InvalidArgumentException('NATIVE_REGISTRY_INVALID');
        return new self($value);
    }

    private static function keys(array $value, array $keys): bool {
        $actual = array_keys($value); sort($actual); sort($keys); return $actual === $keys;
    }
    private static function code($value): bool { return is_string($value) && preg_match('/^[A-Za-z][A-Za-z0-9_-]{0,79}$/D', $value) === 1; }
    private static function field(string $field, $value): bool {
        if ($field === 'campaign_key') return is_string($value) && preg_match('/^BSRE-C[0-9]{4}$/D', $value) === 1;
        if ($field === 'landing_page_id') return is_string($value) && preg_match('/^BSRE-LP[0-9]{4}$/D', $value) === 1;
        if ($field === 'language') return is_string($value) && preg_match('/^[a-z]{2}(?:-[A-Z]{2})?$/D', $value) === 1;
        if ($field === 'page_version' && is_string($value) && preg_match('/^[0-9]{1,4}(?:\.[0-9]{1,4}){1,3}$/D', $value) === 1) return true;
        return self::code($value);
    }
    private static function path($value): bool {
        // No query, fragment, encoding, free text, contact syntax, traversal or numeric identifiers.
        return is_string($value) && strlen($value) <= 240 && ($value === '/' || preg_match('~^/(?:[a-z][a-z0-9-]{0,60}/)+$~D', $value) === 1);
    }
    private function valid_row($row, array $catalog): bool {
        if (!is_array($row) || !self::keys($row, ['native_page_id','page_path','page_context','forms','ctas'])
            || !is_int($row['native_page_id']) || $row['native_page_id'] <= 0 || !self::path($row['page_path'])
            || !is_array($row['page_context']) || !is_array($row['forms']) || !array_is_list($row['forms'])
            || !is_array($row['ctas']) || !array_is_list($row['ctas']) || count($row['forms']) > 100 || count($row['ctas']) > 100) return false;
        foreach ($row['page_context'] as $key => $value) if (!in_array($key, self::PAGE_FIELDS, true)
            || !self::field($key, $value) || !in_array($value, $catalog[$key] ?? [], true)) return false;
        // A campaign/page pair is admitted together; never synthesize one from the other.
        if (isset($row['page_context']['campaign_key']) !== isset($row['page_context']['landing_page_id'])) return false;
        $forms = []; $ctas = [];
        foreach ($row['forms'] as $form) {
            if (!is_string($form) || !preg_match('/^BSRE-[A-Z][A-Z0-9_-]{0,110}$/D', $form) || isset($forms[$form])) return false;
            $forms[$form] = true;
        }
        foreach ($row['ctas'] as $cta) {
            if (!is_array($cta) || !self::keys($cta, self::CTA_FIELDS) || !is_string($cta['cta_id'])
                || !preg_match('/^BSRE-[A-Z][A-Z0-9_-]{0,110}$/D', $cta['cta_id']) || isset($ctas[$cta['cta_id']])
                || !in_array($cta['cta_type'], self::TYPES, true) || !in_array($cta['cta_position'], ['header','hero','form','footer','sticky','other'], true)
                || !self::code($cta['destination_key'])) return false;
            $ctas[$cta['cta_id']] = true;
        }
        return true;
    }

    /** Query identity and real published permalink must agree. Caller cannot choose a URL. */
    public function current(): ?array {
        if (!\is_page() || !\is_ssl() || \is_preview()) return null;
        $id = \BSRE\Enquiries\managed_native_page_id(\get_queried_object_id());
        if (!$id || \get_post_type($id) !== 'page' || \get_post_status($id) !== 'publish'
            || \get_post_field('post_password', $id, 'raw') !== '' || !\BSRE\Enquiries\real_estate_home(\home_url('/'))) return null;
        $url = \get_permalink($id);
        if (!is_string($url) || \BSRE\Enquiries\origin($url) !== \BSRE\Enquiries\origin(\home_url('/'))) return null;
        $parts = parse_url($url);
        if (!is_array($parts) || isset($parts['query']) || isset($parts['fragment']) || !self::path($parts['path'] ?? null)) return null;
        $path = $parts['path']; $role = 'unknown'; $owned = false;
        foreach (\BSRE\Enquiries\SERVICES as $slug => $service) {
            if ($path !== '/enquire/' . $slug . '/') continue;
            $scope = ['kind' => 'service', 'slug' => $slug, 'path' => $path];
            $binding = \BSRE\Enquiries\owned_parent_binding($scope);
            if (($binding['mode'] ?? '') !== 'live' || ($binding['id'] ?? 0) !== $id
                || \BSRE\Enquiries\registered_service_page_id($slug) !== $id) return null;
            $owned = true; $role = $service['role']; break;
        }
        if ($path === '/enquire/') {
            $binding = \BSRE\Enquiries\owned_parent_binding(['kind' => 'hub', 'slug' => '', 'path' => $path]);
            if (($binding['mode'] ?? '') !== 'live' || ($binding['id'] ?? 0) !== $id) return null;
            $owned = true;
        }
        // A reviewed metadata row can never bypass the original enquiry rendering/ownership boundary.
        if (str_starts_with($path, '/enquire/') && !$owned) return null;
        $row = null;
        foreach ($this->registry['pages'] ?? [] as $candidate) if ($candidate['native_page_id'] === $id && $candidate['page_path'] === $path) { $row = $candidate; break; }
        // Existing main-site pages need explicit reviewed identity; no wildcard /lp or arbitrary permalink admission.
        if (!$owned && $row === null) return null;
        return [
            'schema' => 1, 'registry_revision' => $this->registry['revision'] ?? 'service-baseline',
            'company' => 'BlackSwan Real Estate', 'page_path' => $path, 'role' => $role,
            'page_context' => (object) ($row['page_context'] ?? []),
            'forms' => $row['forms'] ?? [], 'ctas' => $row['ctas'] ?? [],
        ];
    }

    /** Server-side join re-resolves current native identity; client metadata/URLs are never copied. */
    public function component(string $kind, string $id): ?array {
        $page = $this->current();
        if ($page === null) return null;
        if ($kind === 'form' && in_array($id, $page['forms'], true)) return ['form_id' => $id];
        if ($kind === 'cta') foreach ($page['ctas'] as $cta) if ($cta['cta_id'] === $id) return $cta;
        return null;
    }
}

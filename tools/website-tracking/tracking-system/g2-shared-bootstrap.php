<?php
declare(strict_types=1);
namespace BSRE\SharedRepository;
if (!defined('ABSPATH')) exit;
// This file is emitted in includes/g2-profile only; no routes/transport/G3 flags enabled.
if (!defined('BSRE_G2_SHARED_REPOSITORY_ENABLED') || BSRE_G2_SHARED_REPOSITORY_ENABLED!==true) return;
foreach (['BSRE\\PurposeAttribution\\ConsentRepository','BSRE\\PurposeAttribution\\WpConsentRepository',
    'BSRE\\PurposeAttribution\\Runtime','BSRE\\RetentionAdmission\\Runtime','BSRE\\SharedRepository\\Runtime',
    'BSRE\\SharedRepository\\BoundRepository'] as $name) {
    if (class_exists($name,false) || interface_exists($name,false)) throw new \RuntimeException('G2_NAMESPACE_OCCUPIED');
}
require_once __DIR__.'/purpose-store.php';
require_once __DIR__.'/purpose-attribution.php';
require_once __DIR__.'/purpose-intake.php';
require_once __DIR__.'/retention-admission.php';
require_once __DIR__.'/receipt-recovery.php';
require_once __DIR__.'/receipt-status.php';
require_once __DIR__.'/receipt-recovery-wordpress.php';
require_once __DIR__.'/shared-repository.php';
// Original schema2 admin hook runs first. This hook adds only four purpose columns.
add_action('admin_init',__NAMESPACE__.'\\migrate',20);

<?php
declare(strict_types=1);
function wp_get_environment_type(): string { return 'production'; }
function home_url(): string { return 'https://example.invalid'; }
require __DIR__ . '/OwnerMailReview.php';
try { \BSRE\OwnerMailReview\Guard::lab(); throw new RuntimeException('Disabled guard failed'); }
catch (\BSRE\OwnerMailReview\ReviewFailure $error) {
    if ($error->getMessage() !== 'ISOLATED_LAB_ONLY') throw $error;
}
define('BSRE_OWNER_MAIL_REVIEW_LAB', true);
define('BSRE_CLOSED_RETENTION_LAB', true);
try { \BSRE\OwnerMailReview\Guard::lab(); throw new RuntimeException('Production guard failed'); }
catch (\BSRE\OwnerMailReview\ReviewFailure $error) {
    if ($error->getMessage() !== 'ISOLATED_LAB_ONLY') throw $error;
}
echo "Owner mail review: default-disabled and production-host guards passed (2 checks).\n";

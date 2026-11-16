<?php
declare(strict_types=1);
namespace BSRE\ProfileTransport;
if (!defined('ABSPATH')) exit;
if (!defined('BSRE_G3_ROUTE_CONTEXT_ENABLED') || BSRE_G3_ROUTE_CONTEXT_ENABLED!==true) return;
if (function_exists(__NAMESPACE__.'\\boot')) throw new \RuntimeException('G3_NAMESPACE_OCCUPIED');
require_once __DIR__.'/route-context.php';
boot();

<?php
require __DIR__ . '/offplan-locale.php';

use function BSRE\Enquiries\offplan_presentation_locale;

$canonical = '/enquire/off-plan/';
$binding = [
    'id' => 26751,
    'mode' => 'live',
    'scope' => ['kind' => 'service', 'slug' => 'off-plan', 'path' => $canonical],
];
$checked = 0;
$expect = static function ($expected, $actual) use (&$checked): void {
    $checked++;
    if ($expected !== $actual) {
        throw new RuntimeException('Case ' . $checked . ' expected ' . $expected . ', got ' . $actual);
    }
};

foreach (['de-DE', 'fr-FR', 'zh-Hant-TW'] as $locale) {
    $expect($locale, offplan_presentation_locale($binding, $canonical . '?bsre_locale=' . $locale));
    $expect($locale, offplan_presentation_locale($binding, $canonical . '?gclid=opaque&bsre_locale=' . $locale . '&utm_source=search'));
}

foreach ([
    $canonical, '/enquire/resale/?bsre_locale=de-DE', '/off-plan-dubai-en-in/?bsre_locale=de-DE',
    'https://blackswanrealestate.ae' . $canonical . '?bsre_locale=de-DE',
    $canonical . '?bsre_locale[]=de-DE', $canonical . '?bsre_locale%5Bx%5D=de-DE',
    $canonical . '?bsre_locale=de-DE&bsre_locale=fr-FR', $canonical . '?bsre_locale=&bsre_locale=fr-FR',
    $canonical . '?bsre_locale=de-DE&bsre.locale=de-DE', $canonical . '?bsre+locale=de-DE',
    $canonical . '?bsre%5Flocale=de-DE', $canonical . '?bsre_locale=%64e-DE',
    $canonical . '?bsre_locale=DE-de', $canonical . '?bsre_locale=en-IN',
    $canonical . '?bsre_locale=de-DE#x', $canonical . '?bsre_locale=de-DE&x=%ZZ',
    $canonical . '?bsre_locale=de-DE;%20x=1', $canonical . '?bsre_locale=de-DE&%FF=x',
    $canonical . '?bsre_locale=de-DE&%00x=1', $canonical . '?bsre_locale=de-DE&x=\\',
    $canonical . '?bsre_locale=de-DE&x=' . str_repeat('x', 4100),
    $canonical . '?bsre_locale=de-DE' . str_repeat('&x=1', 32),
] as $target) {
    $expect('en', offplan_presentation_locale($binding, $target));
}

$target = $canonical . '?bsre_locale=de-DE';
$expect('en', offplan_presentation_locale([], $target));
$expect('en', offplan_presentation_locale(array_replace($binding, ['id' => 26752]), $target));
$expect('en', offplan_presentation_locale(array_replace($binding, ['mode' => 'held']), $target));
$expect('en', offplan_presentation_locale(array_replace($binding, ['scope' => ['kind' => 'service', 'slug' => 'resale', 'path' => '/enquire/resale/']]), $target));
$expect('de-DE', offplan_presentation_locale(array_replace($binding, ['mode' => 'preview']), $target));
fwrite(STDOUT, $checked . " PHP locale cases passed\n");

# Unpublished privacy addendum review copy

`NOTICE_ADDENDUM.en.html` is the primary English review copy for the existing enquiry notice. Five regional drafts follow it for the current off-plan markets. The [review manifest](REVIEW.json) pins all six fragments and records pending language and privacy review.

| Market | Regional review draft |
| --- | --- |
| UAE | [Arabic](NOTICE_ADDENDUM.ar-AE.html) |
| Germany | [German](NOTICE_ADDENDUM.de-DE.html) |
| France | [French](NOTICE_ADDENDUM.fr-FR.html) |
| India | [Hindi](NOTICE_ADDENDUM.hi-IN.html) |
| Taiwan | [Traditional Chinese](NOTICE_ADDENDUM.zh-Hant-TW.html) |

From the repository root, run `python3 -B tools/offplan-lead-first/privacy-addendum/verify_drafts.py`. The check verifies draft hashes, language and heading markup, the Arabic reading direction, both link targets and the numeric retention periods. Reviewers should use the exact pinned bytes, check the user-facing control label and verify the translated meaning and local disclosure placement.

Publication requires verified consent, withdrawal and retention behavior, operational monthly review of enquiries and matching Marketing email copies, and approval of the exact wording and placement. Use one reviewed fragment per localized notice page so its heading ID is unique. The Google data-use link belongs in the consent disclosure or the first layer of the linked policy. [Google disclosure guidance](https://www.google.com/about/company/user-consent-policy-help/) · [Google Business Data Responsibility](https://business.safety.google/privacy/)

## Review English placement

Use a saved public [WordPress Pages response](https://developer.wordpress.org/rest-api/reference/pages/) for the existing enquiry notice, page `26761`, and its separately checked capture SHA-256. The offline composer inserts the pinned English fragment immediately before the observed “Your choices” heading and preserves the surrounding rendered content byte for byte. Review this first-layer placement in the generated HTML:

```sh
python3 -B tools/offplan-lead-first/privacy-addendum/preview_placement.py "$capture" \
  --expected-sha256 "$capture_sha256" --output "$review_html"
```

This preview uses public rendered content. An authorized WordPress editor must read back the current editable page, preserve its rollback revision and verify the exact approved placement before saving. Each translated fragment still needs its own verified native notice binding and language review.

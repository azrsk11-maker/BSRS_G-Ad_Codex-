# Strict v2 held owner-service workorder verification

Use the explicit v2 entry for **new default workorder intake**:

```text
python -B tools/keyword-system/positive_service_packet_v2.py --verify PATH_TO_WORKORDER
python -B -m unittest discover -s tools/keyword-system -p test_positive_service_packet_v2.py
```

Use the project's verified Python runtime on Windows. The CLI prints only a
versioned aggregate held-consistency receipt. It does not write a master, admit
keywords, accept business facts, approve a page, export criteria or call a provider.
All six boolean/integer/float substitution regressions are rejected.

`positive_service_packet.py` is a **historical held-consistency reader**, retained
byte-exact at SHA256
`5e69857f2e33e6a2686ad68ba430238bdac6bbe2d89bf6dd2340b9616cad36bd`.
Seven historical review modules depend directly or transitively on this pinned
source. Its old Python-equality verifier is not type-strict: false/0 and
integer/float substitutions can compare equal. It remains deprecated for new
default intake verification; its unversioned PASS is not a strict-v2 receipt and
never establishes admission or business/release authority. Do not widen its pins,
rewrite historical reports, or call the legacy behavior fixed.

The v2 entry checks that exact legacy file before import and before/after using
its unchanged held-template builder. It requires an exact canonical JSON-type
comparison and returns schema `bsre-positive-service-verification-v2`, integer
`verification_version:2`, status `PASS_STRICT_V2_INTAKE_CONSISTENCY_ONLY`, and false
admission/business/export/production flags. New integrations requiring strict
consistency must require that explicit version; there is no fallback to legacy.
The separately selected-owner verifier is already type-strict and is unchanged.

The registered historical workorder, provenance, source reports, five unfinished
subject-bound reviews and all false authority/count flags are unchanged. Genuine
business evidence, exact page/context binding, independent full-library review
and separate production authorization remain required. No phrase, metric,
approval, source scope or keyword admission is manufactured by this compatibility
correction.

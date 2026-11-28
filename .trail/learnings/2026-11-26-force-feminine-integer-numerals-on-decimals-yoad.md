---
title: Force feminine integer numerals on נקודה decimals and separate engine bugs in Critic verdicts
author: Yoad
date: 2026-11-26
branch: master
id: l-047e15c1
scope: repo
status: active
src: agent
touches:
  - normalizer/hebrew_spoken_form.py
  - numeric_pairs/README.md
  - numeric_pairs/coverage.py
  - numeric_pairs/review.py
  - numeric_pairs/web/app.py
  - numeric_pairs/web/index.html
  - tests/test_normalize_tts_words.py
---

## Decided
- Force feminine (`'f'`) integer numerals whenever a decimal is read with `נקודה` (`4.6 ק"מ` -> `ארבע נקודה שש קילומטר`), even when followed by a masculine noun or unit.
- For `.5` read as `וחצי`, keep masculine/feminine agreement (`ארבעה וחצי קילומטר`) but strip construct state (`'mn'`/`'fn'` -> `'m'`/`'f'`) so `2.5 קילומטרים` renders as `שניים וחצי קילומטרים`, never `*שני וחצי`.
- Classify Critic verdicts into `approved`, `spec_repairable`, `engine_bug`, and `template_defect` so good templates get repaired in place and renderer bugs surface explicitly in the UI instead of silently filtering out numeric patterns.

## Tried and ruled out
- Letting `decimal_number` accept a free `"gender"` parameter from the LLM or letting `_convert_number` pass unit `gender` into `נקודה` decimals: produced ungrammatical `*ארבעה נקודה חמש קילומטר`, `*חמישה נקודה שתיים קילוגרם`, and `*שני וחצי קילומטרים`.
- Binary `approved: false` Critic drops: silently discarded valid sentence templates when the deterministic renderer had a bug.

## In the code:
- `normalizer/hebrew_spoken_form.py`: `_convert_number` decimal `int_gender` resolution.
- `numeric_pairs/micro_templates.py`: `_decimal_fragment` (`half_style="point"|"natural"`, unconditional `'f'` on `נקודה`).
- `numeric_pairs/pipeline.py` and `numeric_pairs/web/index.html`: 4-way `verdict_kind` handling, in-place `spec_repairable` repair instructions, and `engine_bugs` UI alert/counter.
- `tests/test_normalize_tts_words.py` and `tests/test_numeric_pairs_pipeline.py`: regression coverage.

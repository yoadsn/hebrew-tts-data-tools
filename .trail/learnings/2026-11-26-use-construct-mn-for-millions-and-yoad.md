---
title: "Use construct 'mn' for millions and billions in _convert_integer and join final single-component groups with ו׳ החיבור"
author: Yoad
date: 2026-11-26
branch: master
id: l-efddba63
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
- Pass construct masculine `'mn'` to `_convert_integer(billions, 'mn')` and `_convert_integer(millions, 'mn')` in `normalizer/hebrew_spoken_form.py` so `2,xxx,xxx` and `2,xxx,xxx,xxx` render `שני מיליון` and `שני מיליארד` (while compound `22` / `102` keep `ושניים` after `ו׳ החיבור`).
- When a number `>= 1,000,000` ends on a single-component `millions`, `thousands`, or `hundreds` group without an internal `' ו'` (`2,500,000`, `1,002,000`, `2,000,500`, `2,002,000,000`), prepend `ו׳ החיבור` (`שני מיליון וחמש מאות אלף`, `מיליון ואלפיים`, `שני מיליון וחמש מאות`, `שני מיליארד ושני מיליון`), while leaving 4-digit `< 1,000,000` hundreds (`1900 -> אלף תשע מאות`) unchanged.
- Extract `failed_idx` in `PipelineStore.submit_verdicts` and support `POST /api/pipeline/batches/{batch_id}/recheck-engine-bugs` so resolved engine bugs show before/after `cardinal` and clear active `total_engine_bugs`.

## Tried and ruled out
- Passing `'m'` to `_convert_integer(millions, 'm')` and `_convert_integer(billions, 'm')`: produced ungrammatical `*שניים מיליון` and `*שניים מיליארד` whenever `millions == 2` or `billions == 2` (surfaced by Critic on batch `b_182bb4b91ea7`).

## In the code:
- `normalizer/hebrew_spoken_form.py`: `_convert_integer`
- `numeric_pairs/pipeline.py`, `numeric_pairs/web/app.py`, `numeric_pairs/web/index.html`: `failed_idx` capture and `recheck_engine_bugs`
- `tests/test_normalize_tts_words.py` and `tests/test_numeric_pairs_pipeline.py`: regression tests

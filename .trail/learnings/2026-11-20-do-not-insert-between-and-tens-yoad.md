---
title: Do not insert ו׳ החיבור between מאה and tens when units follow
author: Yoad
date: 2026-11-20
branch: experiment/numeric-pairs
id: l-ee5f2aa6
scope: repo
status: active
src: agent
touches:
  - numeric_pairs/__main__.py
  - numeric_pairs/core.py
  - tests/test_numeric_pairs.py
  - normalizer/hebrew_spoken_form.py
---

## Decided
- Removed `add_and = (hundreds == 1)` in `_convert_integer` in `normalizer/hebrew_spoken_form.py` (with `numeric_pairs/core.py` bumped to `RENDERER_VERSION = "19"`).
- In Hebrew compound numbers, `ו׳ החיבור` appears only before the final component: `101..119` (`value < 20`) and round `120..190` (`value % 10 == 0`) get `ו` (`מאה וחמישה עשר`, `מאה ועשרים`), while `121..199` with nonzero units read `מאה ארבעים ושלושה` instead of `מאה וארבעים ושלושה`.
## Tried and ruled out
- Special-casing `hundreds == 1` to always prepend `ו` before remainders `< 100`: it duplicated `ו` across `121..199` (and recursively in `131,775`, `1,141,698`, etc.).
## In the code:
- `normalizer/hebrew_spoken_form.py`: `_convert_integer`
- `numeric_pairs/core.py` and `numeric_pairs/__main__.py`: large-batch deduplicated generation up to `100,000` samples and `--out-dir` export bundle.

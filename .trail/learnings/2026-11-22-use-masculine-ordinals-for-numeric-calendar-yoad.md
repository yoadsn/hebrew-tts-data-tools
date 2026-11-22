---
title: Use masculine ordinals for numeric calendar days 1 through 10
author: Yoad
date: 2026-11-22
branch: master
id: l-6ce8de9e
scope: repo
status: active
replaces: l-58abce85
src: agent
touches:
  - numeric_pairs/core.py
  - tests/test_numeric_pairs_revisions.py
---

## Decided
- In `numeric_pairs/core.py`, render `numeric_calendar` natural days 1..10 with `ordinal_masculine(day)` (`ראשון..עשירי`) for both `"ordinal"` (`בשני לשמיני`, `בעשירי לרביעי`) and `"named"` (`בשני לאוגוסט`, `בחמישי לאוקטובר`) month styles, while keeping `cardinal(day, "f")` for days > 10 (`בעשרים ושלוש לשמיני`).
## Tried and ruled out
- Special-casing only `day == 1` (`"ראשון" if day == 1 else cardinal(day, "f")`): produced unnatural feminine cardinals for days 2..10 (`בשתיים לשמיני`, `בחמש לאוגוסט`).
## Watch out
- Add explicit regression tests in `tests/test_numeric_pairs_revisions.py` for days 2..10 across both `spoken_style` variants, since span validation checks offsets rather than Hebrew date naturalness.

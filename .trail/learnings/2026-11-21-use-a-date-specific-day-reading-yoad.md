---
title: Use a date-specific day reading for the second of the month
author: Yoad
date: 2026-11-21
branch: master
id: l-58abce85
scope: repo
status: active
src: agent
touches:
  - numeric_pairs/core.py
  - tests/test_numeric_pairs_revisions.py
---

## Decided
- In `numeric_pairs/core.py`, the natural `numeric_calendar` day policy uses feminine cardinal readings for every day except 1, so day 2 becomes שתיים instead of the natural date form שני. Both numeric and named month styles inherit it.
## Watch out
- In `tests/test_numeric_pairs_revisions.py`, existing numeric calendar examples cover day 1 and 23 but not day 2; alignment validation checks spans, not Hebrew naturalness. Any correction needs a regression test and regenerated datasets while preserving old runs.

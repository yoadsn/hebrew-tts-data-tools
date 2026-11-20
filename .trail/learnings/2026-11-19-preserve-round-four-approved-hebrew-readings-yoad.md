---
title: Preserve round-four approved Hebrew readings and construct forms
author: Yoad
date: 2026-11-19
branch: master
id: l-429dcd47
scope: repo
status: active
src: agent
touches:
  - README.md
  - configs/prepare_pocket_tts_hebrew.yaml
  - requirements-dev.txt
  - ui/audit_app.py
---

## Decided
- Keep user-rated natural combinations from Round 4 eligible and unchanged: `בשעה רבע לשמונה` at `:45` in `departure`, `100% ... אך לא כל הנשאלים ענו לשאלה הזאת` in `survey`, and `סביבת הבדיקות עודכנה ... עבור כלל המשתמשים` in `version`.
- Use construct `שלושת רבעי` before `כוס` in `fraction`, construct `מינוס שתי` before `מעלות` in `negative_temp` (sampling `2..20`), masculine `אחד` after `כביש`/`קו` in `road_route` (while `2+` remain unmarked feminine), and `ו`-joined sub-100 remainders (`ושתי` for `2`, avoiding `001` sampling) in `million_exact`.
## Tried and ruled out
- Rewriting `:45` departures away from `בשעה רבע ל...` or blocking `100%` surveys from partial-response continuations: the user explicitly rated both generated forms natural.
## Watch out
- Freeze `numeric_pairs/naturalness_round4_pairs.json` at `starter-16` / `renderer 15` so historical ratings stay bound to the exact pairs reviewed. Keep `(0, 0)` contexts on default `CONTINUATIONS[archetype]` for length-mix span tests.
## In the code:
- `numeric_pairs/core.py` and `numeric_pairs/catalog.py`: bumped to `starter-17` and renderer `16`.
- `numeric_pairs/contexts.py` and `numeric_pairs/inspection.py`: semantic compatibility groups for Rounds 4 and 5.
- `numeric_pairs/naturalness_round4_pairs.json` and `tests/test_numeric_pairs_round4.py`: frozen Round 4 snapshots and regression checks.

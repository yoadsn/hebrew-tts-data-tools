---
title: Sample native spoken readings while keeping formal variants dormant
author: Yoad
date: 2026-11-14
branch: master
id: l-c65aceda
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
- In `numeric_pairs/variants.py`, default formal weights are zero for section numbers, decimal temperatures, versions, half-hour durations, full dates, and prices with half a shekel. These follow the user's native-speaker feedback, even where the formal alternative is grammatically standard; `numeric_pairs/core.py` retains both reading policies and records the chosen variant and exact spans. A future run may increase a per-archetype formal weight, but old runs snapshot the weights and retain their review records in `numeric_pairs/review.py`.
- For `full_date` after `האירוע נקבע`, use written `ל-20.1.2026` to match spoken `לעשרים בינואר, אלפיים עשרים ושש`, not the previous `ב-` wording. For `.5` temperature readings use `וחצי`, for `.25` use `ורבע`, for `.75` use `ושלושת רבעי`.
## Tried and ruled out
- Keeping formal-only output because it is technically correct: the user's review specifically says native speakers prefer `סעיף שמונה עשרה, חמש`, `גרסה שלוש אחת תשע`, `שישים וארבע וחצי שקל`, and `שלוש וחצי שעות`. A proposed 10% formal sample for versions is postponed because the later instruction sets natural speech to 100% for now.
## Watch out
- Do not silently apply these colloquial rules to unrelated numeric contexts or rewrite historical runs. Future changes to the default weights should preserve run identity and test fixtures in `tests/test_numeric_pairs.py`.

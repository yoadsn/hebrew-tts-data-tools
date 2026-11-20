---
title: Do not write singular purchases as a digit before the noun
author: Yoad
date: 2026-11-14
branch: master
id: l-de10f1a1
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
- `numeric_pairs/core.py` samples purchase quantities from 2 upward. In Hebrew the natural singular purchase is `קניתי עגבנייה אחת`, not `קניתי 1 עגבנייה`; a digits/spoken pair for this template would require an unnatural written sentence. The user's review rejected that generated example.
## Tried and ruled out
- Rendering `1 עגבנייה` against `עגבנייה אחת` and aligning the whole phrase is technically possible, but exact offsets do not make the written wording natural.
## Watch out
- Do not ban numeric 1 globally. A separately vetted archetype may admit it in another context, but `purchase` and `approximate` should not generate this pattern. See `numeric_pairs/catalog.py` and `tests/test_numeric_pairs.py`.

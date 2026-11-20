---
title: "Read stopwatch decimals as decimals, not hundredths"
author: Yoad
date: 2026-11-14
branch: master
id: l-2acf7751
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
- For `numeric_pairs/core.py` stopwatch values written like `28.10 שניות`, speak `עשרים ושמונה נקודה אחת שניות`, trimming a trailing fractional zero for the spoken number; `28.12` speaks `נקודה שתים עשרה`. User corrected sample in run `1170d817118467803bc0`. Add exact-span fixtures in `tests/test_numeric_pairs.py`.
## Tried and ruled out
- Treating `28.10 שניות` as `עשרים ושמונה שניות ועשר מאיות`: the reviewer says native speakers would not say `מאיות` with this decimal notation. Explicit hundredths would need a different written archetype, like `28 שניות ו-10 מאיות`.
## Watch out
- Preserve the old reviewed sample and feedback as-is. Do not generalize this decimal-second policy to decimal temperatures or prices; they have independent reading rules.

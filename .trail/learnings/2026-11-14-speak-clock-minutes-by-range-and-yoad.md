---
title: Speak clock minutes by range and mobile numbers in groups
author: Yoad
date: 2026-11-14
branch: master
id: l-009c3d7b
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
- In `numeric_pairs/adapter.py`, hour readings remain 12-hour without a daypart; for one minute say `ודקה`, for 2–19 say `ו... דקות` (with feminine construct for 2), and from 20 on use the short minute reading. Quarter/half/quarter-to use dedicated readings. The user's review explicitly corrected `15:16` and `05:14`, including the one-minute and 15-minute cases.
- In `numeric_pairs/core.py`, phone identifiers retain all digits including leading zeros, but the spoken sequence has comma pauses after groups of three and three, leaving the final four digits together (`050-3159268` -> `אפס חמש אפס, שלוש אחת חמש, תשע שתיים שש שמונה`).
## Tried and ruled out
- Using the existing generic clock normalizer unchanged returned `שלוש שש עשרה` without `ו` or `דקות`; reading all phone digits as one uninterrupted sequence ignored the user's grouping.
## Watch out
- Keep these reading policies isolated in the generator adapter, not as a blanket change to the shared normalizer. Bump the catalog and renderer versions when changing the spoken output so old review records remain attached to their original pair IDs. Test exact alignment spans after changing punctuation.

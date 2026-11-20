---
title: Keep human-approved Hebrew examples when restricting sentence combinations
author: Yoad
date: 2026-11-19
branch: master
id: l-86daa55a
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
- Gemini naturalness findings are proposals; user-rated natural combinations must stay eligible even when neighboring examples need constraints. Round two accepted the future date with attendees, 180 participants at a table, a bus-route speaker shift, and the feminine half-shekel reading.
- Freeze reviewed pairs and alignments before changing rendering. Ratings refer to what the user saw, not what today's renderer would output.
- Generate with compatible opening, ending, and continuation groups, and noun-dependent personal purchase limits.
## Tried and ruled out
- Free Cartesian mixing of starts and ends in numeric_pairs/contexts.py created contradictions. Blanket bans on future venues or large table capacities would reject user-approved examples.
## Watch out
- In numeric_pairs/core.py, amounts ending in 1 take שקלים; do not change the half-shekel reading when fixing price/shipping contradictions.
## In the code:
- numeric_pairs/contexts.py: compatible frames and clauses.
- numeric_pairs/catalog.py: purchase buckets.
- numeric_pairs/naturalness.py and numeric_pairs/naturalness_round2_pairs.json: historical rating snapshots.

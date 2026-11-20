---
title: Show the numeric scenario map alongside executable archetypes
author: Yoad
date: 2026-11-14
branch: master
id: l-ee0f7499
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
- In `numeric_pairs/catalog.py`, keep the ten areas from the user-provided Hebrew TN/ITN guide visible as `SCENARIO_AREAS`, with explicit pending subcases. Expose this in `numeric_pairs/web/index.html` so a completed implementation milestone cannot be mistaken for comprehensive numeric coverage. The user asked to broaden the archetypes before reviewing another generated run.
## Tried and ruled out
- Treating the initial eight reviewed archetypes as the complete catalog: the guide covers years, dates, durations, monetary amounts, measurements, scores, hierarchical numbers, ranges and multiple identifier readings not represented there.
## Watch out
- Only put a domain in the generative catalog after adding a specific spoken policy and exact-span fixtures in `tests/test_numeric_pairs.py`. Leave ambiguous or high-risk identifier cases marked pending rather than relying on the generic normalizer. When adding archetypes, set the default generation count to cover each archetype at least once and bump catalog/renderer versions without disturbing old review runs.

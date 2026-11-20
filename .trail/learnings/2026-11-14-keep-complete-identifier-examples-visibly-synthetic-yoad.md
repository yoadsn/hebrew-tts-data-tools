---
title: Keep complete identifier examples visibly synthetic
author: Yoad
date: 2026-11-14
branch: master
id: l-31a36435
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
- `numeric_pairs/catalog.py` and `numeric_pairs/core.py` now include full-length card, international phone, civil ID, passport, bank-account and plate archetypes, but the generators use explicitly fake contexts and constrained example namespaces. Card numbers start with non-issuable `0000`, international phones use the reserved US `+1 202-555-01xx` range, civil IDs fail the checksum, bank accounts use `000`, plates use `00-`, and passports use fictional `XX`. The user requested full identifier coverage, not real personal records. Validate the constraints and exact reading spans in `tests/test_numeric_pairs.py`.
## Tried and ruled out
- Generating plausible arbitrary card or identity numbers to increase diversity: accidental real identifiers can leak into a corpus. Restricting to redacted suffixes alone does not cover the user's full-length training cases.
## Watch out
- Preserve old run files and feedback. Changes to reading variants for long identifiers need native-speaker review; grouping, prefix and letter names should not be generalized to every national numbering plan. The category map remains explicit about pending variants.

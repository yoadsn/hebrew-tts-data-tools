---
title: Treat unreviewed generated samples as valid
author: Yoad
date: 2026-11-14
branch: master
id: l-a27149f7
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
- In `numeric_pairs/coverage.py`, treat an absent review verdict as valid. Only an explicit reject or correction removes a sample from the valid count; an explicit accept restores a rejected/corrected sample. In `numeric_pairs/web/index.html`, show this default so reviewers need not approve every ordinary example.
## Tried and ruled out
- Requiring an explicit accept for every sample in the review UI: it adds unnecessary work and makes missing submissions look like quality failures.
## Watch out
- Keep the default consistent in future export filtering. Correction notes do not automatically modify raw pairs in `numeric_pairs/review.py`.

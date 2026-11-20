---
title: Load the spoken form without importing the normalizer package
author: Yoad
date: 2026-11-14
branch: master
id: l-ccd0377b
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
- For the standalone numeric pair generator, load the existing spoken-form file through a narrow adapter instead of importing `normalizer.hebrew_spoken_form` as a package. This avoids executing `normalizer/__init__.py`, which imports the sentence normalizer that assumes `hebrew_spoken_form` is a top-level module.
## Tried and ruled out
- A regular package import failed with `ModuleNotFoundError: hebrew_spoken_form` when invoked as `python3 -m numeric_pairs`. Modifying the existing normalizer's package imports would affect unrelated consumers and was outside this module's boundary.
## Watch out
- When extracting this package to a new repository, replace the adapter with the copied spoken-form implementation or a dedicated package import.
In the code: `numeric_pairs/adapter.py`; `normalizer/__init__.py`; `normalizer/hebrew_tts_normalizer.py`.

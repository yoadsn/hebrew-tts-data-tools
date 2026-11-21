---
title: Expose the repo root to pytest in the uv non-package project
author: Yoad
date: 2026-11-21
branch: master
id: l-2d60a9f8
scope: repo
status: active
src: agent
touches:
  - README.md
  - pyproject.toml
  - uv.lock
---

## Decided
- Set `pythonpath = ["."]` under `[tool.pytest.ini_options]` in `pyproject.toml` so the documented `uv run pytest tests -q` command discovers the top-level `numeric_pairs` package.
## Tried and ruled out
- Running the pytest console script with `package = false` and no pytest pythonpath failed collection with `ModuleNotFoundError: numeric_pairs`; the project itself is not installed into the environment.
## In the code
- `pyproject.toml`: `[tool.uv]` and `[tool.pytest.ini_options]`.

---
title: Prompt Neon corpus-first for numeric usages (multi-usage covered_usages) instead of 1-to-1 archetype checklists
author: Yoad
date: 2026-11-27
branch: master
id: l-eddbe893
scope: repo
status: active
src: agent
---

Decided: In build_neon_prompt and PipelineStore, present uncovered Tier-1 items strictly as a palette of numeric reading usages (_USAGE_PHENOMENON_HINTS) to weave naturally into corpus-first spoken Hebrew, track multi-usage covered_usages per template in tier1_coverage(), forbid domain widgets on flexible counted-noun usages (_FLEXIBLE_USAGE_IDS) that inject canned Tier-1 stationery nouns (קלסרים, חוברות, עפרונות, מדפים), cap targeted mining in mine_spoken_contexts to ~50% so general multi-number REGEX_BUCKETS always run, and support reuse_snippets_from so new batches can deeply mine already-sampled snippets without re-sampling.

Ruled out: Prompting Neon with a 1-to-1 Tier-1 archetype checklist plus domain previews for every archetype.

Why: Inspecting batches b_2f600c5a9fd5, b_e93f709e3a0c, and b_a6f3a03dfc4e showed that checklist + domain prompting caused Neon to ignore rich real podcast/Knesset snippets in mined_snippets and regress into wooden 2-clause textbook wrapper sentences around canned Tier-1 nouns.

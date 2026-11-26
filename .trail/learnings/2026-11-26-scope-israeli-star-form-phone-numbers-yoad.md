---
title: Scope Israeli star-form phone numbers to national and business service lines
author: Yoad
date: 2026-11-26
branch: master
id: l-ce4c39ac
scope: repo
status: active
src: agent
touches:
  - numeric_pairs/catalog.py
  - numeric_pairs/inspection.py
  - numeric_pairs/phone_formats.py
  - tests/test_numeric_pairs_phones.py
---

## Decided
- Add Israeli star-form short dial numbers (`*XXXX` 70%, `*XXXXX` 20%, `*XXX` 10%, spoken as `כוכבית` + feminine digits) only to `business_line` (50% share) and `national_line` (40% share), where every starter is a national call-center or hotline frame.
- Do not require a `000` subscriber block inside 3–5 digit star numbers (start with `1`–`9` so digit variety is preserved for TTS).
## Tried and ruled out
- Adding star numbers to `mobile`, `landline`, `local_landline`, or `israeli_international`: those frames explicitly reference mobile/SMS (`בנייד`), geographic/local landlines (`בטלפון הקווי`, `באזור החיוג המקומי`), or international `+972` dialing where `*` shortcodes are invalid.
## In the code:
- `numeric_pairs/phone_formats.py`: `STAR_PHONE_KINDS`, `STAR_LENGTH_WEIGHTS`, `sample_star_phone`, `is_star_phone`, `spoken_phone` (`digits-star-{3,4,5}`).
- `tests/test_numeric_pairs_phones.py`: star rendering, 70/20/10 length distribution, and rejection on non-star phone kinds.

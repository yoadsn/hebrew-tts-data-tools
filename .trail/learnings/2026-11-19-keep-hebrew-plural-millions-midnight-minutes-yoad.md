---
title: "Keep Hebrew plural millions, midnight minutes, and general fractions in natural syntactic frames"
author: Yoad
date: 2026-11-19
branch: master
id: l-82982c79
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
- Use construct masculine `שני מיליון` (`cardinal(m, "m", construct=True) + " מיליון"`) for plural millions (`plural_millions`), joining single thousands without internal `ו` via `ו` (`שני מיליון וחמש מאות אלף`) and multi-part thousands via `, ` (`שלושה מיליון, שבע מאות וחמישים אלף`).
- Restrict `midnight_time` (`חצות` readings) to minutes `0..20` and `30` (`בחצות`, `בחצות ודקה`, `בחצות ושתי דקות`, `בחצות ורבע`, `בחצות ועשרים`, `בחצות וחצי`), leaving arbitrary `00:21..00:59` minutes to `departure`'s `שתים עשרה ...` reading.
- Frame `general_fraction` (`שליש`, `שני שלישים`, `שתי חמישיות`, `שלוש שמיניות`, etc.) as indefinite partitive direct objects (`הצוות השלים 2/3 מהמשימות`) so singular (`1/3`) and plural (`2/3`, `3/5`) fractions share transitive verbs without verb-number disagreement.
- Enforce at least 20 starts and 20 ends per archetype bank and at least 10 compatible starts and 10 compatible ends in every `FrameGroup` and sampled value configuration.
## Tried and ruled out
- Delegating plural millions to `normalizer/hebrew_spoken_form.py`: `_convert_integer(2, 'm') + ' מיליון'` produces ungrammatical `שניים מיליון`.
- Allowing `חצות` with arbitrary minutes like `00:38`: native speakers say `שתים עשרה שלושים ושמונה`, not `חצות שלושים ושמונה`.
## In the code:
- `numeric_pairs/catalog.py` and `numeric_pairs/core.py`: `starter-18` / renderer `17` with 69 archetypes (`plural_millions`, `child_half_age`, `month_end_date`, `midnight_time`, `general_fraction`, `multi_digit_decimal`, `airline_flight`).
- `numeric_pairs/lexicon.py` and `numeric_pairs/contexts.py`: expanded phone and archetype banks, dedicated `MOBILE_ENDINGS` and `AGE_RANGE_ENDINGS`, and `>=10` compatibility pools.
- `tests/test_numeric_pairs_round4.py`: `test_pending_subcases_minimum_ten_pools_and_spot_sample_fixes`.

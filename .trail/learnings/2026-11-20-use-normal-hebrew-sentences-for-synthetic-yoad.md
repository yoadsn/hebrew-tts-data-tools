---
title: Use normal Hebrew sentences for synthetic identifiers and never use דמה
author: Yoad
date: 2026-11-20
branch: master
id: l-cf256503
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
- Keep identifier values synthetic at the sampling layer (`0000` card prefix, `XX` passport prefix, invalid-checksum `000` civil ID, `000` bank account and phone subscriber blocks, `00-` plates, `+1 202-555-01xx`), but frame all generated sentences (`TEMPLATES`, `RECORD`, `MOBILE_ENDINGS`, `STARTS`, and `CLAUSE_GROUPS`) as completely normal, everyday Hebrew sentences.
- Never use `דמה` (`הדמה`), `פיקטיבי`, `סימולציית`, `הדגמה`, or meta-disclaimers about fake/non-real personal data in output sentences (`starter-19` / renderer `18`).
## Tried and ruled out
- Labelling synthetic phones, cards, IDs, passports, bank accounts, and plates in the spoken sentence text with `דמה` / `פיקטיבי` / `לצורך בדיקת המערכת`: the user rejected `דמה` as unnatural, rare, and hard to pronounce, and noted sentences need not announce that numbers are fake.
## In the code:
- `numeric_pairs/lexicon.py`, `numeric_pairs/contexts.py`, `numeric_pairs/core.py`: everyday frames for `RECORD`, `card_suffix`, `card_full`, `civil_id`, `passport_id`, `bank_account`, `license_plate`, and all phone archetypes.
- `tests/test_numeric_pairs_round4.py`: `test_no_dema_or_fake_disclaimer_words_in_any_output_sentences`.

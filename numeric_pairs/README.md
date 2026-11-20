# Hebrew numeric sentence pairs

Standalone top-level package for generating paired written/spoken Hebrew sentences. The
core requires only Python and `normalizer/hebrew_spoken_form.py`, accessed through
`numeric_pairs/adapter.py`; the web interface additionally needs `numeric_pairs/requirements.txt`.

```sh
python3 -m pip install -r numeric_pairs/requirements.txt
python3 -m numeric_pairs.web              # http://127.0.0.1:8766
python3 -m numeric_pairs --seed 42 --count 56 > /path/to/pairs.jsonl
python3 -m pytest tests/test_numeric_pairs.py -q
```

For these tests, install `pytest` and `httpx` in the environment as development
dependencies; the web runtime only needs `numeric_pairs/requirements.txt`.

The app has tabs for archetypes, generation, review, coverage, corpus candidates,
and export. Generation is deterministic by seed, selected
archetypes, row index, sampling controls, and catalog/renderer version. Runs and append-only reviews are
stored in `~/.local/share/hebrew-numeric-pairs/` (override with
`NUMERIC_PAIRS_DATA_DIR`). There is currently no authentication: bind the server to
localhost, not a public network.

The **Archetypes** tab opens first. Search for an archetype and expand it to
inspect the actual base template (including optional slots), compatible opening
and ending banks, shared continuation clauses and their 30/40/30 length weights,
numeric pools/ranges/generator constraints, and three written/spoken examples
with aligned readings. The read-only `/api/archetypes/{id}/design` endpoint
derives this information from the generator and does **not** create a run,
write feedback, or read the corpus. The scenario map remains available as a
collapsed section above the searchable list.

The lexical banks in `lexicon.py` provide 20–50 openings and endings for
non-phone archetypes, plus 39 sampled countable nouns (stone was excluded from
ordinary purchases after review) and 40 street names. Catalog `starter-16` /
renderer `15` distinguish the revised samples from earlier saved runs.
Ordinary purchases use noun-specific limits (2–6/12/20/30 items in four
quantity buckets); bulk orders use their own institutional
frames. Default house numbers have 1–3 digits, with 4–5 digits still
available when explicitly selected as stress cases.

Israeli phone examples include mobile `05X`, geographic `02/03/04/08/09`,
local seven-digit numbers, national `07X`, international `+972`, and
`1599/1700/1800` service formats. Generated complete numbers deliberately use
a conspicuous `000` subscriber group. This is **not** a formally reserved
Israeli fictional-number range: do not dial or use the examples as contact
details. Format classes are based on the [Israeli telephone prefix overview](https://he.wikipedia.org/wiki/קידומת_טלפון_בישראל).

The **Naturalness** tab lists proposed Hebrew-language concerns separately
from saved run feedback. Rate each flagged sentence natural, unnatural, or
unsure and optionally explain why. Ratings are appended to
`naturalness-ratings.jsonl` under the data directory; they never reject a
sample, change an archetype, or affect exports automatically.
The first 24, second 20, and third 25 rated candidates are frozen with exact alignments
in `naturalness_round1_pairs.json`, `naturalness_round2_pairs.json`, and
`naturalness_round3_pairs.json`. Notes remain in the local rating history; flags
never automatically change generation or export. Sentence openings, endings and
continuations are sampled from semantically compatible frame groups (including
value-gated groups for dates, clock hours, scores, age ranges, and distances, as
well as liquid/solid and sweet/savory recipe splits and dedicated software-version
and residential slash-address banks), visible in archetype inspection.

`digits_span` and `cardinal_span` are half-open **Unicode code-point** ranges into
the final strings. Each alignment includes the complete numeric expression, including
attached prefixes and counted nouns when order changes. The browser uses `Array.from`
to convert to JavaScript's UTF-16 representation for highlighting. `sampled` records
semantic values; `id` is stable for a given value and configuration. The web UI records
accept/reject/correction notes without editing the underlying examples. **Unreviewed
samples are valid by default**; an explicit rejection or correction overrides that
default. An explicitly accepted sample is also valid. Old runs remain reviewable,
but cannot be rerun under a changed catalog/renderer version.

The initial expanded catalog adds feminine floor ordinals 1–10, 24-hour written
clock times with 12-hour spoken readings (no daypart inference), integer percentages
1–100, and mobile identifiers read digit by digit with their leading zeros.
Reviewed time readings now use `ודקה` for one minute, `ו... דקות` for 2–19,
short readings from 20 onward, and dedicated quarter/half/quarter-to readings
for 15/30/45. Mobile numbers are spoken as digit groups of 3, 3, and 4,
separated by commas. These rules apply only to this package's adapter; the
shared normalizer is unchanged. The catalog/renderer versions change on every
rendering policy update so historical runs and feedback stay intact.
The Generate tab controls address number digit lengths and the probability of
boundary-style versus random values. Coverage reports category, archetype, numeric
kind, digit-length, reading, noun-gender, review-status, and internal QA counts.
Purchases deliberately start at 2: `קניתי 1 עגבנייה` is not a natural Hebrew
written pattern even though the spoken singular `קניתי עגבנייה אחת` is grammatical.

The current `starter-16` catalog contains **62 executable archetypes** across
the ten broad areas in the supplied TN/ITN scenario guide. New fixtures cover
ranking, implicit ages, years, day/month and full dates, durations with a half,
curated fractions, decimal and negative temperatures, shekels with or without
agorot, kilogram and kilometer measurements, four-digit card endings,
five- or seven-digit postal strings, road/route pairs, software versions, scores,
sections, age ranges, and half percentages. The `starter-7` expansion adds
infant age 1.5, decades, seconds plus hundredths, square meters, map scale,
and upper attendance limits; this revision adds pill-quantity ranges, opening-hour
ranges and integer-dollar prices. Stopwatch decimals are read as decimals rather
than as explicit hundredths (e.g. `28.10 שניות` → `עשרים ושמונה נקודה אחת שניות`).
The newest batch adds exact million-plus quantities (nonzero units), meeting
times to a non-round minute, full 16-digit card numbers, reserved international
phone examples, synthetic civil IDs and passports, multi-minute stopwatch times,
euro prices, data units, bank accounts, vehicle plates, flight codes, numeric
day/month, slash addresses, minimum ages, six-digit shekel amounts, explicit
written hundredths, and slash-form full dates. All twelve named months are
available for named-month dates. The **identifier data is synthetic**: card
numbers start with the non-issuable `0000`, US phones use the reserved
`+1 202-555-01xx` example range, civil IDs fail their checksum, accounts and
vehicle plates use `000` / `00-` prefixes, and passports use a fictional `XX`
prefix. Never paste real personal data into this generator or candidate import.
The Archetypes tab continues to mark finer subcases pending, including alternate
readings and additional identifier formats; a guide example is not evidence that
every regional/grammatical variant is implemented. The default
run count equals the catalog size, giving each archetype one first-pass example;
choose a larger count for within-archetype variation. Catalog and renderer
versions change when new policies appear, leaving old runs reviewable.

Every archetype has at least one reusable, original sentence frame in
`contexts.py`. Seeded generation samples a compatible beginning, ending,
optional medium/long continuation, and typed numeric values, yielding at
least ten distinct sentence combinations per archetype. Shared lexical banks
group compatible suffixes; continuations add a domain-appropriate cause,
qualification, instruction or consequence rather than an unrelated phrase.
The length mix includes short statements and fuller sentences: across 2,240
samples (40 seeds), written-text median was **12 words**, the 90th percentile
**19 words**, versus 6 and 8 words before continuations. Only outer sentence
context varies: numeric fragments, readings, optional groups and internal
separators remain in their typed archetypes. Chosen context and continuation
indices are included in each generated pair's identity, preserving exact
alignments and reproducible runs. Direct `render()` calls without a context
keep the original fixed wording for backwards-compatible fixtures.
The frames were inspired by a local batch of 557 deduplicated, redacted
numeric snippets from explore.ivrit.ai, **not copied** from its transcripts.
Those search hits are short transcript *segments* (median 7 words, 95th
percentile 11), not full-sentence boundaries; matching their lengths would
underrepresent complete, multi-clause sentences.
That inspiration file lives under
`~/.local/share/hebrew-numeric-pairs/corpus-inspiration/`, outside the repo;
it contains no authentication cookie or audio and is not used at runtime.

On the Generate tab, **Select never-ran archetypes** selects only archetypes
that have not appeared in any saved run, including older runs absent from the
30-run archive view. It sets the count to one per selected archetype. A selected
archetype that was never sampled because a run was shorter than its selected
list still counts as never run. No run is created until Generate is clicked.

The reviewer-approved default reading policy is **100% natural speech** for
sections, decimal temperatures, software versions, half-shekel prices, full
dates, and half-hour durations. For example: `18.5` → `סעיף שמונה עשרה, חמש`,
`15.5 מעלות` → `חמש עשרה וחצי מעלות`, `3.1.9` → `שלוש אחת תשע`, and
`64.50 ₪` → `שישים וארבע וחצי שקל`. For dates after `נקבע`, both views now
use the `ל-` / `ל` preposition. Quarter and three-quarter decimals use their
dedicated readings as well. The formal readings remain available but dormant:
`numeric_pairs/variants.py` defines zero formal weights by default, while the
Generate tab can assign 0–100% per affected archetype for a future run. The
run snapshots these weights and the chosen reading variant on each pair, so
changing the configuration never rewrites old runs or feedback. Forms that
were not flagged as unnatural remain as before; no blanket grammatical
changes are made to the shared normalizer.

The Candidates tab accepts up to 100 lines of licensed, manually checked
non-sensitive sentences per paste, with source, license, restrictions and an
explicit permission checkbox. It proposes structural contexts by masking the
numeric expression, keeps up to three redacted examples, and clusters identical
contexts. Phone numbers, long identifiers and emails are redacted before storage;
this is **not a complete privacy filter**, so only paste text cleared for this
use. Choose evaluation instead of derivation to store held-out structural
patterns separately; they never enter candidate proposals. A human can reject
a candidate or approve it only after supplying grammar, semantic slots, safe
substitution ranges, and written/spoken policies. Approval records a proposal,
not executable code: curated archetypes must still be implemented and tested
in `catalog.py` and `core.py` before they can generate sentences.

An export includes only implicitly valid and explicitly accepted raw pairs;
rejected or correction-requested samples are excluded. Each pair is validated
again before writing. The split holds out *entire category families* for dev
and test, so a run needs at least three valid categories. The manifest records
schema/catalog/renderer versions, seed and sampling settings, review counts,
split sizes, family assignment, value overlaps, and quality gates. Files are
stored under `NUMERIC_PAIRS_DATA_DIR/exports/<run>-<review fingerprint>/` and
downloadable from the Export tab. Changing review verdicts creates a different
export ID; existing exports and old run feedback stay intact. Corrections are
not silently applied to exported text.

When extracting this package, copy/replace `adapter.py` and the spoken-form dependency;
none of the core's domain types depend on the existing audio or UI pipelines. The
starter catalog is intentionally small and curated; it is not a complete TN/ITN system.

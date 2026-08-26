# Hebrew TTS Data Tools

Reusable Hebrew text normalization, aligned-audio segmentation, quality filtering, and
dataset auditing tools. The Pocket TTS profiles are designed for CrowdRecital recordings
containing `audio.wav`, `transcript.aligned.json`, and `metadata.json` per recording.

The repository contains code and configuration only. Raw audio, prepared datasets, cached
parts, and model artifacts are intentionally ignored and must be transferred separately.

## Requirements

- Python 3.11 or 3.12
- ffmpeg available on `PATH`
- enough disk for the prepared audio (the 38.9-hour CrowdRecital build measured about 6.7 GB)

Linux/server setup:

```bash
git clone https://github.com/asaelbarilan/hebrew-tts-data-tools.git
cd hebrew-tts-data-tools
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
ffmpeg -version
```

Windows setup:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
ffmpeg -version
```

For development and tests, install `requirements-dev.txt` instead.

## Pocket TTS preparation

Two checked-in profiles are provided:

- `configs/prepare_pocket_tts_hebrew.yaml`: proven student profile, 4-16 seconds with an
  approximately 8-second target.
- `configs/prepare_pocket_tts_hebrew_teacher.yaml`: experimental teacher profile,
  4-40 seconds with an approximately 23-second measured mean. Training must use
  `--head-samples 500` for full coverage of its longest clips.

Set portable paths and run a representative pilot before the full build:

```bash
export CROWD_RECITAL_ROOT=/data/crowd-recital
export POCKET_TTS_PREPARED_DIR=/data/prepared/CrowdRecital_pockettts_8s

python data_prep/prepare_ivritai.py \
  --config configs/prepare_pocket_tts_hebrew.yaml \
  --max_source_entries 50 \
  --source_selection spread
```

Inspect the pilot, then remove `--max_source_entries` for the full build:

```bash
python data_prep/prepare_ivritai.py \
  --config configs/prepare_pocket_tts_hebrew.yaml
```

The preparation job saves each completed chunk beside the output in a `_parts` directory.
Rerunning the identical command reuses completed chunks after an interruption. Do not reuse
the parts directory after changing the source corpus or segmentation profile; choose a new
output path instead.

For the teacher profile:

```bash
export POCKET_TTS_PREPARED_DIR=/data/prepared/CrowdRecital_pockettts_teacher_23s
python data_prep/prepare_ivritai.py \
  --config configs/prepare_pocket_tts_hebrew_teacher.yaml \
  --max_source_entries 50 \
  --source_selection spread
```

## What the Pocket TTS profiles enforce

- aligned slicing on transcript segment boundaries;
- minimum session/sample and segment quality of 0.6;
- Hebrew number/text normalization after segmentation;
- removal of wiki `==` markers while retaining spoken heading words;
- removal of normalized rows above a 0.15 Latin-letter ratio;
- propagation of `user_id` as the speaker identity and `biological_sex` for auditing;
- no internal random validation split. The Pocket TTS repository creates a deterministic,
  speaker-disjoint split and different-clip/same-speaker prompt pairs afterward.

`source_id` is constant (`recital`) in this corpus. Never use it as the train/validation
grouping key; use `user_id`.

## Validate and audit output

Run regression tests:

```bash
python -m pytest tests -q
```

Listen to prepared samples and compare normalized/raw text:

```bash
python ui/output_samples_app.py --data_path "$POCKET_TTS_PREPARED_DIR"
```

The UI prints its localhost URL. On a remote server, forward that port over SSH or audit a
local copy of the dataset.

Quick normalizer check:

```bash
python scripts/smoke_test_normalizer.py
```

## Word-level forced alignment

Pocket TTS needs to know *when* each word was said, not only what was said. From its
`training/README.md`:

> it's not enough to have pairs of `(speech audio, transcript)`, we also need to know when
> exactly each word was said. This is because for training, the audio is cut into smaller
> parts, and we need to know exactly what text corresponds to what part of the audio.

The trainer does run without word timings -- it falls back to a random window for the voice
prompt -- but it then loses the trailing-silence trim, which Kyutai identify as the reason a
model "emits silence instead of EOS, so generations never terminate".

CrowdRecital ships timings in `transcript.aligned.json`. Most other corpora do not, so align
them yourself:

```bash
# Confirm a candidate model is a Hebrew char-level CTC head before spending GPU time
PYTHONPATH=/path/to/pocket-tts python -m data_prep.align_hebrew in.jsonl out.jsonl --check-model

# Align (input/output are Pocket TTS manifests)
PYTHONPATH=/path/to/pocket-tts python -m data_prep.align_hebrew     manifest.jsonl manifest_aligned.jsonl     --model imvladikon/wav2vec2-xls-r-300m-hebrew --device cuda --batch-size 8
```

`--resume` appends and skips utterances already aligned, so preemptible jobs continue where
they stopped.

### Accuracy

Wav2Vec2 is multilingual (XLS-R); only the CTC head and its 27-character vocabulary are
Hebrew-specific. Measured against CrowdRecital's own timings, 40 utterances / 316 words:

| boundary | median | p90 |
|---|---|---|
| word end | 19 ms | 71 ms |
| word start | 74 ms | 158 ms |

One frame at Pocket TTS's 12.5 Hz is 80 ms, so word ends land within a quarter of a frame.
Ends are the accurate side, which is fortunate: `last_word_end` is what drives the silence
trim. 5.7% of words returned no timing.

Caveat: CrowdRecital's timings are themselves automatic, so this measures agreement between
two aligners, not accuracy against hand labels.

## Handoff to Pocket TTS

This tool produces the segmented Hugging Face dataset. Continue with the training repository:

```bash
git clone https://github.com/asaelbarilan/pocket-tts.git
```

Follow `HEBREW_SERVER_RUNBOOK.md` there to create speaker-disjoint manifests, train the Hebrew
SentencePiece model, precompute model-specific Mimi latents, and launch either the 6-layer
student adaptation or an experimental 24-layer teacher adaptation.

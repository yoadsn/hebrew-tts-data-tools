"""Regression tests for the crowd-recital slicing path in prepare_ivritai.

These lock in the behaviour that was investigated when a 25-source pilot produced
zero examples. The root cause was source selection (the manifest is sorted by
duration, so `max_source_entries` took the shortest recordings, all below
`min_duration`), not the slicing code. The fixture below is the known-good source
`00Kkty6u7kGDjQMoRPs9L`, which must always produce exactly one example.

Run with:  python -m pytest hebrew-tts-data-tools/tests -q
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data_prep.prepare_ivritai import (  # noqa: E402
    DurationController,
    Segment,
    TARGET_SAMPLE_RATE,
    _load_cli_config,
    calculate_segments_quality_score,
    generate_examples_from_slices,
    generate_slices,
    get_segment_word_scores,
    latin_letter_ratio,
    merge_slice_segments,
    strip_wiki_markup,
)

MIN_DURATION = 4.0
TARGET_DURATION = 8.0
MAX_DURATION = 16.0
SEGMENT_QUALITY_THRESHOLD = 0.6


def _words(spec):
    """spec: list of (word, start, end, probability)."""
    return [{"word": w, "start": s, "end": e, "probability": p, "tokens": [0]} for w, s, e, p in spec]


# Schema-faithful copy of crowd-recital/00Kkty6u7kGDjQMoRPs9L/transcript.aligned.json
KNOWN_GOOD_SEGMENTS = [
    {
        "start": 0.78,
        "end": 4.78,
        "text": ' בשנת תשכ"ב הונחה אבן הפינה בשכונת גבעת מרדכי.',
        "seek": None,
        "tokens": [34561, 5997, 5548],
        "temperature": None,
        "avg_logprob": None,
        "compression_ratio": None,
        "no_speech_prob": None,
        "words": _words(
            [
                (" בשנת", 0.78, 1.00, 0.71044921875),
                (' תשכ"ב', 1.12, 2.16, 0.7375164031982422),
                (" הונחה", 2.60, 2.88, 0.9791259765625),
                (" אבן", 2.88, 3.16, 0.9793294270833334),
                (" הפינה", 3.16, 3.44, 0.9296875),
                (" בשכונת", 3.44, 3.94, 0.99853515625),
                (" גבעת", 3.94, 4.28, 0.9973958333333334),
                (" מרדכי.", 4.28, 4.78, 0.99287109375),
            ]
        ),
    }
]
KNOWN_GOOD_AUDIO_DURATION = 4.8
KNOWN_GOOD_METADATA = {
    "source_id": "recital",
    "source_entry_id": "00Kkty6u7kGDjQMoRPs9L",
    "session_duration": 4.778666666666667,
    "quality_score": 0.9792,
}


def _silence(duration_sec):
    return np.zeros(int(duration_sec * TARGET_SAMPLE_RATE), dtype=np.float32)


def _parse(raw_segments):
    return [Segment(**s) for s in raw_segments]


def _run(raw_segments, audio_duration, min_duration=MIN_DURATION, **example_kwargs):
    segments = _parse(raw_segments)
    controller = DurationController(min_duration, MAX_DURATION, TARGET_DURATION)
    slices = generate_slices(
        segments,
        audio_duration,
        MAX_DURATION,
        SEGMENT_QUALITY_THRESHOLD,
        duration_controller=controller,
    )
    slices = merge_slice_segments(slices)
    examples = list(
        generate_examples_from_slices(
            slices,
            _silence(audio_duration),
            KNOWN_GOOD_METADATA,
            min_duration=min_duration,
            **example_kwargs,
        )
    )
    return slices, examples


def test_aligned_json_schema_parses_into_segment_objects():
    segments = _parse(KNOWN_GOOD_SEGMENTS)
    assert len(segments) == 1
    assert segments[0].has_words()
    assert len(get_segment_word_scores(segments[0])) == 8


def test_known_good_source_yields_exactly_one_example():
    slices, examples = _run(KNOWN_GOOD_SEGMENTS, KNOWN_GOOD_AUDIO_DURATION)

    assert len(slices) == 1
    assert slices[0]["seek"] == 0
    assert examples, "known-good source must not be silently dropped"
    assert len(examples) == 1

    example = examples[0]
    assert example["metadata"]["duration"] == pytest.approx(4.78, abs=0.05)
    assert example["metadata"]["quality_score"] == pytest.approx(0.9792, abs=1e-3)
    assert example["metadata"]["entry_id"] == "00Kkty6u7kGDjQMoRPs9L"
    assert "בשנת" in example["raw_text"]
    assert example["text"].strip(), "normalized text must be non-empty"
    assert example["audio"]["bytes"]


@pytest.mark.parametrize("audio_duration", [1.9, 3.5])
def test_sources_shorter_than_min_duration_yield_nothing(audio_duration):
    """This is why the shortest-25 pilot produced zero examples -- expected, not a bug."""
    segments = [
        dict(
            KNOWN_GOOD_SEGMENTS[0],
            start=0.2,
            end=audio_duration - 0.1,
            words=_words([(" מילה", 0.2, audio_duration - 0.1, 0.95)]),
        )
    ]
    _, examples = _run(segments, audio_duration)
    assert examples == []


def test_merged_segments_keep_all_word_scores():
    """A merged segment must contribute its word scores to the example quality score."""
    segments = [
        dict(
            KNOWN_GOOD_SEGMENTS[0],
            start=0.0,
            end=1.0,
            text=" ראשון",
            words=_words([(" ראשון", 0.0, 1.0, 0.40)]),
        ),
        dict(
            KNOWN_GOOD_SEGMENTS[0],
            start=1.1,  # gap 0.1 < 0.3 merge threshold
            end=6.0,
            text=" שני שלישי רביעי",
            words=_words(
                [
                    (" שני", 1.1, 3.0, 0.95),
                    (" שלישי", 3.0, 4.5, 0.96),
                    (" רביעי", 4.5, 6.0, 0.97),
                ]
            ),
        ),
    ]
    slices, examples = _run(segments, 6.2, min_duration=1.0)

    merged = [s for s in slices if s["segments"]][0]["segments"]
    assert len(merged) == 1, "adjacent segments should merge"
    assert len(merged[0]["word_scores"]) == 4, "all four word scores must survive merge"

    assert examples
    expected = calculate_segments_quality_score(_parse(segments))
    assert examples[0]["metadata"]["quality_score"] == pytest.approx(expected)
    assert examples[0]["metadata"]["quality_score"] > 0.4


def test_strip_wiki_markup_removes_markers_but_keeps_spoken_words():
    text = "באתר המרכז למורשת המודיעין == הערות שוליים =="
    stripped = strip_wiki_markup(text)
    assert "=" not in stripped
    assert "הערות שוליים" in stripped, "the words were spoken and must be kept"
    assert "  " not in stripped
    assert strip_wiki_markup("טקסט רגיל") == "טקסט רגיל"


@pytest.mark.parametrize(
    "text, expected",
    [
        ("טקסט עברי בלבד", 0.0),
        ("Java, JavaScript, Lua, Perl, PHP, Python, Rust", 1.0),
        ("", 0.0),
        ("1234 ,.!?", 0.0),
    ],
)
def test_latin_letter_ratio(text, expected):
    assert latin_letter_ratio(text) == pytest.approx(expected)


def test_latin_ratio_is_measured_over_letters_not_all_characters():
    # Punctuation and digits must not dilute the signal.
    assert latin_letter_ratio("Redis, 2015!") == pytest.approx(1.0)
    assert latin_letter_ratio("מודל BERT הוא מודל שפה") > 0


def _one_segment(text, words):
    return [dict(KNOWN_GOOD_SEGMENTS[0], start=0.1, end=5.9, text=text, words=_words(words))]


def test_latin_dominant_slice_is_dropped():
    latin = " Java, JavaScript, Lua, Perl, PHP, Python, Rust, Scala"
    segments = _one_segment(latin, [(latin, 0.1, 5.9, 0.95)])

    _, kept = _run(segments, 6.0, max_latin_letter_ratio=1.0)
    assert len(kept) == 1, "disabled filter must keep everything"

    _, dropped = _run(segments, 6.0, max_latin_letter_ratio=0.15)
    assert dropped == [], "Latin-dominant slice must be dropped"


def test_hebrew_slice_with_incidental_latin_is_kept():
    text = " מודל שפה שהוצג באוקטובר על ידי חוקרים בחברת Google בארצות הברית"
    segments = _one_segment(text, [(text, 0.1, 5.9, 0.95)])
    _, examples = _run(segments, 6.0, max_latin_letter_ratio=0.15)
    assert len(examples) == 1
    assert "Google" in examples[0]["text"]


def test_dropped_slice_does_not_leak_into_prev_text():
    """A dropped slice must break the prev_text chain, not be silently skipped over."""
    hebrew = " זהו משפט עברי ראשון שנאמר כאן"
    latin = " Java, JavaScript, Lua, Perl, PHP, Python, Rust, Scala"
    segments = [
        dict(KNOWN_GOOD_SEGMENTS[0], start=0.1, end=5.0, text=hebrew, words=_words([(hebrew, 0.1, 5.0, 0.95)])),
        dict(KNOWN_GOOD_SEGMENTS[0], start=6.0, end=11.0, text=latin, words=_words([(latin, 6.0, 11.0, 0.95)])),
        dict(KNOWN_GOOD_SEGMENTS[0], start=12.0, end=17.0, text=hebrew, words=_words([(hebrew, 12.0, 17.0, 0.95)])),
    ]
    _, examples = _run(segments, 17.5, max_latin_letter_ratio=0.15)
    assert len(examples) == 2, "only the two Hebrew slices survive"
    assert examples[1]["has_prev"] is False
    assert examples[1]["prev_text"] == ""


def test_duration_controller_rejection_does_not_underflow():
    controller = DurationController(MIN_DURATION, MAX_DURATION, TARGET_DURATION)
    controller.record_rejected_slice()  # nothing recorded yet
    assert controller.completed_durations == []
    controller.record_completed_slice(8.0)
    controller.record_rejected_slice()
    assert controller.completed_durations == []


def test_config_expands_environment_paths(monkeypatch, tmp_path):
    source = tmp_path / "source"
    output = tmp_path / "output"
    monkeypatch.setenv("TEST_RECITAL_ROOT", str(source))
    monkeypatch.setenv("TEST_PREPARED_DIR", str(output))
    config = tmp_path / "profile.yaml"
    config.write_text(
        'prepare_ivritai:\n  input_folder: "${TEST_RECITAL_ROOT}"\n  output_dataset_name: "${TEST_PREPARED_DIR}"\n',
        encoding="utf-8",
    )

    loaded = _load_cli_config(str(config))

    assert loaded["input_folder"] == str(source)
    assert loaded["output_dataset_name"] == str(output)


def test_config_rejects_unset_environment_path(monkeypatch, tmp_path):
    monkeypatch.delenv("MISSING_RECITAL_ROOT", raising=False)
    config = tmp_path / "profile.yaml"
    config.write_text('input_folder: "${MISSING_RECITAL_ROOT}"\n', encoding="utf-8")

    with pytest.raises(ValueError, match="unset environment variable"):
        _load_cli_config(str(config))

"""Validation tests for second-round naturalness review flags and report."""

import json
from pathlib import Path

from numeric_pairs.core import render, validate_pair
from numeric_pairs.naturalness import (
    FLAGS_FILE,
    NEXT_FLAGS_FILE,
    ROUND_ONE_SNAPSHOTS,
    ROUND_TWO_SNAPSHOTS,
    NaturalnessStore,
)


def test_round2_flags_schema_reproducibility_and_isolation(tmp_path):
    assert NEXT_FLAGS_FILE.exists(), "numeric_pairs/naturalness_flags_round2.json must exist"
    round1_raw = json.loads(FLAGS_FILE.read_text(encoding="utf-8"))
    round2_raw = json.loads(NEXT_FLAGS_FILE.read_text(encoding="utf-8"))
    frozen_r1 = json.loads(ROUND_ONE_SNAPSHOTS.read_text(encoding="utf-8"))
    frozen_r2 = json.loads(ROUND_TWO_SNAPSHOTS.read_text(encoding="utf-8"))

    assert isinstance(round2_raw, list)
    assert 12 <= len(round2_raw) <= 25
    assert len(round1_raw) == 24
    assert len(frozen_r1) == 24
    assert len(frozen_r2) == len(round2_raw)

    # Approved natural round-1 items (#7, #9, #10, #11, #16 -> 0-based indices 6, 8, 9, 10, 15)
    approved_natural_r1 = [round1_raw[idx] for idx in (6, 8, 9, 10, 15)]

    store = NaturalnessStore(tmp_path)
    all_flags = store.flags()
    assert len(all_flags) >= len(round1_raw) + len(round2_raw)

    r1_items = all_flags[: len(round1_raw)]
    r2_items = all_flags[len(round1_raw) : len(round1_raw) + len(round2_raw)]

    # Round 1 frozen pairs must remain untouched
    assert all(item["round"] == 1 and item["pair"] == frozen_r1[item["id"]] for item in r1_items)
    assert all(item["round"] == 2 for item in r2_items)

    # All IDs across Round 1 and Round 2 must be distinct
    all_ids = [item["id"] for item in all_flags]
    assert len(set(all_ids)) == len(all_ids)

    seen_signatures = set()
    for entry, item in zip(round2_raw, r2_items):
        assert set(entry) == {
            "archetype_id",
            "sampled",
            "context",
            "continuation",
            "reason_he",
            "suggestion_he",
            "severity",
        }
        assert entry["severity"] in {"low", "medium", "high"}
        assert isinstance(entry["context"], list) and len(entry["context"]) == 2
        assert all(type(x) is int for x in entry["context"])
        assert type(entry["continuation"]) is int and entry["continuation"] in (0, 1, 2)
        assert entry["reason_he"].strip() and entry["suggestion_he"].strip()

        # Must not duplicate any approved natural round-1 item
        for approved in approved_natural_r1:
            assert not (
                entry["archetype_id"] == approved["archetype_id"]
                and entry["sampled"] == approved["sampled"]
                and entry["context"] == approved["context"]
            )

        signature = (
            entry["archetype_id"],
            json.dumps(entry["sampled"], sort_keys=True, ensure_ascii=False),
            tuple(entry["context"]),
            entry["continuation"],
        )
        assert signature not in seen_signatures, f"Duplicate candidate in round 2: {signature}"
        seen_signatures.add(signature)

        # Reviewed round-two text cannot change after a renderer revision.
        validate_pair(item["pair"])
        assert item["pair"] == frozen_r2[item["id"]]


def test_round2_markdown_report_documents_all_candidates():
    report_path = Path(__file__).resolve().parent.parent / "numeric_pairs" / "naturalness_review_round2.md"
    assert report_path.exists(), "numeric_pairs/naturalness_review_round2.md must exist"
    report_text = report_path.read_text(encoding="utf-8")
    round2_raw = json.loads(NEXT_FLAGS_FILE.read_text(encoding="utf-8"))

    frozen = json.loads(ROUND_TWO_SNAPSHOTS.read_text(encoding="utf-8"))
    items = NaturalnessStore(Path(__file__).resolve().parent).flags()[24:]
    for idx, (entry, item) in enumerate(zip(round2_raw, items), 1):
        rendered = frozen[item["id"]]
        assert f"### דוגמה #{idx} " in report_text
        assert rendered["digits"] in report_text
        assert rendered["cardinal"] in report_text

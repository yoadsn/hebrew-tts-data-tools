import json

import pytest

from numeric_pairs.naturalness import NaturalnessStore


def test_flagged_examples_are_read_only_until_human_rates(tmp_path):
    flags = tmp_path / "flags.json"
    flags.write_text(json.dumps([{
        "archetype_id": "address", "sampled": {"street": "הרצל", "house": 12},
        "context": [0, 0], "continuation": 0,
        "reason_he": "הקשר נשמע מאולץ", "suggestion_he": "אפשר לקצר",
        "severity": "medium",
    }], ensure_ascii=False), encoding="utf-8")
    store = NaturalnessStore(tmp_path, flags)
    first = store.flags()
    assert len(first) == 1
    assert first[0]["rating"] is None
    assert first[0]["pair"]["alignments"]
    assert sorted(path.name for path in tmp_path.iterdir()) == ["flags.json"]
    with pytest.raises(ValueError):
        store.rate("other-id", "natural", "")
    with pytest.raises(ValueError):
        store.rate(first[0]["id"], "accept", "")
    rating = store.rate(first[0]["id"], "unnatural", "המשפט מלאכותי")
    assert store.flags()[0]["rating"] == rating
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "flags.json", "naturalness-ratings.jsonl"]
    assert not (tmp_path / "feedback.jsonl").exists()
    store.rate(first[0]["id"], "natural", "לאחר בדיקה זה סביר")
    assert store.flags()[0]["rating"]["verdict"] == "natural"
    assert len((tmp_path / "naturalness-ratings.jsonl").read_text().splitlines()) == 2


def test_naturalness_api_does_not_write_run_feedback(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from numeric_pairs.web import app as web_app

    flags = tmp_path / "flags.json"
    flags.write_text(json.dumps([{
        "archetype_id": "address", "sampled": {"street": "הרצל", "house": 12},
        "context": [0, 0], "continuation": 0,
        "reason_he": "לבדוק את המשפט", "suggestion_he": "לנסח אחרת",
    }], ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(web_app, "naturalness_store", NaturalnessStore(tmp_path, flags))
    client = TestClient(web_app.app)
    item = client.get("/api/naturalness").json()[0]
    assert item["rating"] is None
    assert client.post(f"/api/naturalness/{item['id']}/rating", json={
        "verdict": "unsure", "note": "לבדוק שוב"}).status_code == 200
    assert client.get("/api/naturalness").json()[0]["rating"]["note"] == "לבדוק שוב"
    assert client.post("/api/naturalness/bad/rating", json={
        "verdict": "natural"}).status_code == 422
    assert not list(tmp_path.glob("run-*"))
    assert not (tmp_path / "feedback.jsonl").exists()


def test_round_one_snapshots_keep_rated_sentences_and_spans(tmp_path):
    from numeric_pairs.core import validate_pair
    from numeric_pairs.naturalness import ROUND_ONE_SNAPSHOTS

    frozen = json.loads(ROUND_ONE_SNAPSHOTS.read_text(encoding="utf-8"))
    items = NaturalnessStore(tmp_path).flags()
    assert len(frozen) == 24
    assert all(item["pair"] == frozen[item["id"]] and item["round"] == 1
               for item in items[:24])
    for pair in frozen.values():
        validate_pair(pair)

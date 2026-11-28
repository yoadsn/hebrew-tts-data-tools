"""Tests for the spoken micro-template compiler, CLI-driven Neon pipeline, and session cost ledger."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
import pytest

from numeric_pairs.core import validate_pair
from numeric_pairs.micro_templates import (
    generate_from_templates,
    validate_and_stress_template,
)
from numeric_pairs.pipeline import PipelineStore
from numeric_pairs.review import ReviewStore
from numeric_pairs.candidates import CandidateStore


SAMPLE_TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "spoken_exit_hours_01",
        "archetype_id": "duration_half",
        "track": "corpus_inspired",
        "inspiration_summary": "יציאה בצהריים אחרי שהייה ארוכה ללא שינה או אוכל",
        "slots": {
            "subject_open": {"kind": "micro_bank", "values": ["הוא יוצא משם", "אחי יצא משם", "הבחור יצא משם"]},
            "exit_hour": {"kind": "int_range", "lower": 12, "upper": 15},
            "hours_stayed": {"kind": "derived_int", "base_slot": "exit_hour", "offset_min": 14, "offset_max": 20},
            "deprivation": {"kind": "micro_bank", "values": ["לא אכל כלום", "לא ישן דקה", "היה בלי קליטה בכלל"]},
        },
        "nodes": [
            {"slot": "subject_open"},
            {"lit": " יום אחר כך "},
            {"num": "colloquial_daypart_hour", "slot": "exit_hour", "prefix": "ב"},
            {"lit": ", כלומר הוא היה שם "},
            {
                "num": "counted_noun",
                "slot": "hours_stayed",
                "approx": "איזה ",
                "noun": {"singular": "שעה", "plural": "שעות", "gender": "f"},
            },
            {"lit": " שבהן הוא "},
            {"slot": "deprivation"},
            {"lit": "."},
        ],
    },
    {
        "id": "spoken_cases_contrast_02",
        "archetype_id": "multi_digit_decimal",
        "track": "corpus_inspired",
        "inspiration_summary": "השוואת נתונים יומיים ועליית מדד עשרוני",
        "slots": {
            "place_open": {"kind": "micro_bank", "values": ["במדינות השכנות עצרו הכול", "באירופה הקפיאו את הפעילות"]},
            "n1": {"kind": "int_range", "lower": 2000, "upper": 5000, "step": 1000},
            "n2": {"kind": "derived_int", "base_slot": "n1", "offset_min": 1000, "offset_max": 2500, "step": 500},
            "rate": {"kind": "decimal_range", "lower": 0.7, "upper": 1.6, "decimals": 1},
        },
        "nodes": [
            {"slot": "place_open"},
            {"lit": " בגלל "},
            {
                "num": "counted_noun",
                "slot": "n1",
                "comma_thousands": True,
                "noun": {"singular": "פנייה", "plural": "פניות", "gender": "f"},
            },
            {"lit": " ביום, ואצלנו ראינו השבוע "},
            {
                "num": "counted_noun",
                "slot": "n2",
                "approx": "יותר מ-",
                "comma_thousands": True,
                "noun": {"singular": "פנייה", "plural": "פניות", "gender": "f"},
            },
            {"lit": " כשהמדד עלה כבר "},
            {"num": "decimal_number", "slot": "rate", "prefix": "ל"},
            {"lit": "."},
        ],
    },
    {
        "id": "spoken_siblings_age_03",
        "archetype_id": "age",
        "track": "corpus_inspired",
        "inspiration_summary": "פער גילאים בין אח בכור לאח צעיר בדיבור טבעי",
        "slots": {
            "older_intro": {"kind": "micro_bank", "values": ["האח הגדול במשפחה", "בן הדוד הבכור שלנו"]},
            "older_age": {"kind": "int_range", "lower": 32, "upper": 42},
            "younger_age": {"kind": "derived_int", "base_slot": "older_age", "offset_min": -8, "offset_max": -4},
        },
        "nodes": [
            {"slot": "older_intro"},
            {"lit": " הוא "},
            {"num": "adjacent_approx", "slot": "older_age", "step": 1, "gender": "f", "lead": "באזור ה-"},
            {"lit": ", והאח הקטן לעומתו רק בן "},
            {"num": "cardinal_number", "slot": "younger_age", "gender": "f"},
            {"lit": "."},
        ],
    },
    {
        "id": "spoken_voicemail_mobile_04",
        "archetype_id": "mobile",
        "track": "transactional_spoken",
        "inspiration_summary": "הודעת קול טבעית להשארת מספר נייד לחזרה",
        "slots": {
            "opener": {"kind": "micro_bank", "values": ["תקשיבי, תרשמי רגע את הנייד הישיר שלו,", "אחי, פשוט תשלח הודעה למספר"]},
            "mob": {"kind": "archetype_sampler", "archetype_id": "mobile"},
            "closer": {"kind": "micro_bank", "values": ["ותגיד שדיברנו הבוקר", "והוא יחזור אליך תוך כמה דקות"]},
        },
        "nodes": [
            {"slot": "opener"},
            {"lit": " "},
            {"num": "domain", "kind": "mobile", "slot": "mob"},
            {"lit": ", "},
            {"slot": "closer"},
            {"lit": "."},
        ],
    },
]


def test_micro_templates_stress_and_relational_constraints():
    for tpl in SAMPLE_TEMPLATES:
        samples = validate_and_stress_template(tpl, stress_count=8, seed=17)
        assert len(samples) == 8
        for pair in samples:
            validate_pair(pair)
            assert not any(c.isdigit() for c in pair["cardinal"])

    # Verify relational bound n2 > n1 holds across generated batch
    batch = generate_from_templates([SAMPLE_TEMPLATES[1]], count=15, seed=99)
    for pair in batch:
        assert pair["sampled"]["n2"] > pair["sampled"]["n1"]
        validate_pair(pair)


def test_micro_templates_reject_raw_digits_and_dema():
    bad_digits = {
        **SAMPLE_TEMPLATES[0],
        "id": "bad_raw_digit",
        "nodes": [{"lit": "בשנת 2020 "}, *SAMPLE_TEMPLATES[0]["nodes"]],
    }
    with pytest.raises(ValueError, match="raw ASCII digits"):
        validate_and_stress_template(bad_digits)

    bad_dema = {
        **SAMPLE_TEMPLATES[3],
        "id": "bad_dema_word",
        "nodes": [*SAMPLE_TEMPLATES[3]["nodes"][:-1], {"lit": " לצורך בדיקה במספר דמה."}],
    }
    with pytest.raises(ValueError, match="forbidden"):
        validate_and_stress_template(bad_dema)


def test_decimal_number_always_feminine_on_nekuda_and_supports_natural_half():
    from numeric_pairs.micro_templates import render_micro_template

    tpl_point = {
        "id": "spoken_distance_time_04",
        "archetype_id": "distance",
        "slots": {"km_dist": {"kind": "decimal_range", "lower": 4.5, "upper": 6.5, "decimals": 1}},
        "nodes": [
            {"lit": "יצאתי מהבית, נסיעה של "},
            {"num": "decimal_number", "slot": "km_dist", "gender": "m"},
            {"lit": " קילומטר."},
        ],
    }
    p45 = render_micro_template(tpl_point, {"km_dist": "4.5"})
    assert p45["cardinal"] == "יצאתי מהבית, נסיעה של ארבע נקודה חמש קילומטר."
    p126 = render_micro_template(tpl_point, {"km_dist": "12.6"})
    assert p126["cardinal"] == "יצאתי מהבית, נסיעה של שתים עשרה נקודה שש קילומטר."

    tpl_half = {
        **tpl_point,
        "nodes": [
            {"lit": "יצאתי מהבית, נסיעה של "},
            {"num": "decimal_number", "slot": "km_dist", "half_style": "natural", "noun_gender": "m"},
            {"lit": " קילומטר."},
        ],
    }
    assert render_micro_template(tpl_half, {"km_dist": "4.5"})["cardinal"] == "יצאתי מהבית, נסיעה של ארבעה וחצי קילומטר."
    assert render_micro_template(tpl_half, {"km_dist": "4.6"})["cardinal"] == "יצאתי מהבית, נסיעה של ארבע נקודה שש קילומטר."


def test_counted_noun_plural_millions_construct_shnei_million():
    from numeric_pairs.micro_templates import render_micro_template

    tpl = {
        "id": "spoken_million_users_pct_02",
        "archetype_id": "survey",
        "slots": {
            "exact_users": {"kind": "int_range", "lower": 1_142_363, "upper": 6_897_648, "step": 5},
            "retention_pct": {"kind": "int_range", "lower": 68, "upper": 96, "step": 1},
        },
        "nodes": [
            {"lit": "מסתבר שיש במערכת כבר "},
            {"num": "counted_noun", "slot": "exact_users", "comma_thousands": True, "noun": {"singular": "משתמש", "plural": "משתמשים", "gender": "m"}},
            {"lit": " פעילים, וכמעט "},
            {"num": "percentage", "slot": "retention_pct"},
            {"lit": " מהם חוזרים."},
        ],
    }
    pair = render_micro_template(tpl, {"exact_users": 2_513_603, "retention_pct": 72})
    assert "שני מיליון חמש מאות ושלושה עשר אלף שש מאות ושלושה משתמשים" in pair["cardinal"]
    assert "שניים מיליון" not in pair["cardinal"]


class FakeOpenChamberClient:
    def __init__(self):
        self.created: list[dict[str, Any]] = []
        self.interrupted: list[str] = []
        self.sent_prompts: list[dict[str, Any]] = []
        self.status = "busy"
        self.target_status = "idle"
        self.cost = 0.0425

    def connection_info(self) -> dict[str, Any]:
        return {"configured": True, "base_url": "http://127.0.0.1:57123", "has_password": True, "_password": "pw"}

    def get_session_status(self, session_id: str, directory: str) -> str:
        return self.target_status

    def send_prompt(self, session_id: str, prompt: str, *, directory: str, timeout: float = 900.0) -> Any:
        self.sent_prompts.append({"session_id": session_id, "prompt": prompt, "directory": directory})
        return {"ok": True}

    def create_and_start_session(self, **kwargs: Any) -> dict[str, Any]:
        self.created.append(kwargs)
        return {
            "session_id": "ses_fake_neon_001",
            "model": kwargs.get("model_spec", "google/gemini-4-neon"),
            "variant": kwargs.get("variant") or "default",
            "title": kwargs["title"],
        }

    def fetch_session_telemetry(self, session_id: str, directory: str) -> dict[str, Any]:
        return {
            "session_id": session_id,
            "model": "google/gemini-4-neon",
            "status": self.status,
            "outcome": "succeeded" if self.status == "idle" else None,
            "cost_usd": self.cost,
            "cost_source": "openchamber_session",
            "tokens": {"input": 8200, "output": 1180, "reasoning": 410, "cache_read": 14000, "cache_write": 0},
            "assistant_turns": 4,
            "last_activity": "כלי shell: pipeline_cli submit-verdicts",
            "updated_at_ms": 1795715000000,
        }

    def interrupt_session(self, session_id: str, directory: str) -> None:
        self.interrupted.append(session_id)
        self.status = "idle"


def test_end_to_end_pipeline_api_verdict_gating_export_and_cost(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from numeric_pairs.web import app as web

    fake_oc = FakeOpenChamberClient()
    rev_store = ReviewStore(tmp_path)
    monkeypatch.setattr(web, "store", rev_store)
    monkeypatch.setattr(web, "candidate_store", CandidateStore(tmp_path))
    monkeypatch.setattr(web, "pipeline_store", PipelineStore(lambda: web.store, oc_client=fake_oc))

    client = TestClient(web.app)

    # Read-only status leaves tmp_path empty
    st = client.get("/api/pipeline/status")
    assert st.status_code == 200
    assert st.json()["openchamber"]["configured"] is True
    assert list(tmp_path.iterdir()) == []

    # 1. Dispatch batch from UI
    created = client.post("/api/pipeline/batches", json={"target_count": 18, "seed": 7, "notes": "בדיקת צינור מלאה"})
    assert created.status_code == 200
    batch = created.json()
    batch_id = batch["id"]
    assert batch["sessions"][0]["session_id"] == "ses_fake_neon_001"
    assert len(fake_oc.created) == 1
    assert batch_id in fake_oc.created[0]["prompt"]

    # 2. Step: mine
    mined = client.post(f"/api/pipeline/batches/{batch_id}/mine")
    assert mined.status_code == 200
    assert len(mined.json()["snippets"]) >= 4

    # 3. Step: submit templates (4 valid templates)
    sub_tpl = client.post(f"/api/pipeline/batches/{batch_id}/templates", json={"templates": SAMPLE_TEMPLATES})
    assert sub_tpl.status_code == 200
    assert sub_tpl.json()["total_compiled_templates"] == 4
    assert sub_tpl.json()["errors"] == []

    # 4. Step: stress pack
    pack = client.get(f"/api/pipeline/batches/{batch_id}/stress-pack")
    assert pack.status_code == 200
    assert len(pack.json()["templates_to_audit"]) == 4
    assert all(len(t["stress_realizations"]) == 8 for t in pack.json()["templates_to_audit"])

    # 5. Step: critic verdicts — flag 1 engine_bug, 1 spec_repairable, and approve 2; then repair the spec_repairable in place!
    verdicts_round1 = [
        {"template_id": "spoken_exit_hours_01", "passed_count": 8, "verdict_kind": "approved", "approved": True, "reason": "8/8 טבעי לחלוטין"},
        {"template_id": "spoken_cases_contrast_02", "passed_count": 8, "verdict_kind": "approved", "approved": True, "reason": "8/8 מעולה"},
        {"template_id": "spoken_siblings_age_03", "passed_count": 0, "verdict_kind": "engine_bug", "approved": False, "reason": "באג הדגמה במנוע"},
        {"template_id": "spoken_voicemail_mobile_04", "passed_count": 6, "verdict_kind": "spec_repairable", "approved": False, "reason": "ניסוח פתיח אחד לתיקון"},
    ]
    ver_res = client.post(f"/api/pipeline/batches/{batch_id}/verdicts", json={"verdicts": verdicts_round1})
    assert ver_res.status_code == 200
    assert ver_res.json()["approved_templates"] == 2
    assert ver_res.json()["engine_bugs_flagged"] == 1
    assert ver_res.json()["spec_repairable_templates"] == ["spoken_voicemail_mobile_04"]

    # Repair spoken_voicemail_mobile_04 in place via submit-templates and approve it
    repaired_res = client.post(f"/api/pipeline/batches/{batch_id}/templates", json={"templates": [SAMPLE_TEMPLATES[3]]})
    assert repaired_res.status_code == 200
    ver_res2 = client.post(
        f"/api/pipeline/batches/{batch_id}/verdicts",
        json={"verdicts": [{"template_id": "spoken_voicemail_mobile_04", "passed_count": 8, "verdict_kind": "approved", "approved": True, "reason": "8/8 תוקן ואושר"}]},
    )
    assert ver_res2.json()["approved_templates"] == 3
    assert ver_res2.json()["engine_bugs_flagged"] == 1

    # 6. Step: finalize
    fake_oc.status = "idle"
    fin = client.post(f"/api/pipeline/batches/{batch_id}/finalize")
    assert fin.status_code == 200
    fin_data = fin.json()
    assert fin_data["status"] == "succeeded"
    assert fin_data["generated_count"] == 18
    assert fin_data["total_cost_usd"] == pytest.approx(0.0425)
    run_id = fin_data["run_id"]

    # Poll endpoint reflects live cost, pairs, and steps
    polled = client.get(f"/api/pipeline/batches/{batch_id}").json()
    assert all(s["status"] == "done" for s in polled["steps"])
    assert len(polled["pairs"]) == 18
    assert all(p["micro_template_id"] != "spoken_siblings_age_03" for p in polled["pairs"])

    # Ledger reflects cumulative session cost
    ledger = client.get("/api/pipeline/batches").json()["ledger"]
    assert ledger["total_cost_usd"] == pytest.approx(0.0425)
    assert ledger["total_pairs_generated"] == 18

    # Registered run works seamlessly in Review, Coverage, AND Export!
    cov = client.get(f"/api/runs/{run_id}/coverage")
    assert cov.status_code == 200
    assert cov.json()["total"] == 18
    assert cov.json()["qa_failures"] == []

    exp = client.post(f"/api/runs/{run_id}/export")
    assert exp.status_code == 200
    assert exp.json()["manifest"]["exported"] == 18

    # Simulate an engine bug fix on spoken_siblings_age_03 (perturb stored old sample so recheck sees engine output changed)
    batch_file = tmp_path / "pipeline" / "batches" / f"{batch_id}.json"
    import json

    raw_batch = json.loads(batch_file.read_text(encoding="utf-8"))
    for t in raw_batch["templates"]:
        if t["id"] == "spoken_siblings_age_03":
            t["stress_samples"][0]["cardinal"] = "פלט ישן עם באג מנוע"
    batch_file.write_text(json.dumps(raw_batch, ensure_ascii=False), encoding="utf-8")

    rechecked = client.post(f"/api/pipeline/batches/{batch_id}/recheck-engine-bugs")
    assert rechecked.status_code == 200
    rechecked_data = rechecked.json()
    t03 = next(t for t in rechecked_data["templates"] if t["id"] == "spoken_siblings_age_03")
    assert t03["verdict"]["approved"] is True
    assert t03["verdict"]["rescued_from_engine_bug"] is True
    assert rechecked_data["engine_bugs"][0]["resolved"] is True
    assert rechecked_data["engine_bugs"][0]["approved_after_fix"] is True
    assert len(rechecked_data["pairs"]) > 18
    assert any(p["micro_template_id"] == "spoken_siblings_age_03" for p in rechecked_data["pairs"])
    assert client.get("/api/pipeline/batches").json()["ledger"]["total_engine_bugs"] == 0


def test_default_batch_targets_uncovered_tier1_archetypes_and_custom_notes_overrides(tmp_path, monkeypatch):
    from numeric_pairs.catalog import ARCHETYPES
    from numeric_pairs.corpus_miner import ARCHETYPE_MINING_QUERIES
    from numeric_pairs.web import app as web_app

    # Every Tier-1 catalog archetype must have a tailored corpus-mining query
    assert {a.id for a in ARCHETYPES}.issubset(set(ARCHETYPE_MINING_QUERIES.keys()))

    fake_oc = FakeOpenChamberClient()
    test_review_store = ReviewStore(tmp_path)
    test_pipeline_store = PipelineStore(lambda: test_review_store, oc_client=fake_oc)

    monkeypatch.setattr(web_app, "store", test_review_store)
    monkeypatch.setattr(web_app, "pipeline_store", test_pipeline_store)
    monkeypatch.delenv("IVRIT_AI_COOKIE", raising=False)

    client = TestClient(web_app.app)

    # Initial lazy coverage check must not touch disk and reports 0 / 69 covered
    status_before = client.get("/api/pipeline/status").json()
    assert status_before["tier1_coverage"]["total_archetypes"] == len(ARCHETYPES)
    assert status_before["tier1_coverage"]["covered_count"] == 0
    assert list(tmp_path.iterdir()) == []

    # 1. Default batch (empty notes) selects uncovered Tier-1 archetypes and injects them into Neon's prompt
    b1 = client.post("/api/pipeline/batches", json={"target_count": 12, "seed": 10, "corpus_ratio": 0.75, "notes": ""}).json()
    assert b1["selection_mode"] == "tier1_uncovered_default"
    assert len(b1["target_archetypes"]) == b1["sizing"]["candidate_templates_target"]
    assert all(t["already_covered"] is False for t in b1["target_archetypes"])
    assert all(t["example_digits"] and t["example_cardinal"] for t in b1["target_archetypes"])

    prompt1 = fake_oc.created[0]["prompt"]
    assert "Numeric Usage Palette" in prompt1
    assert "CORPUS-FIRST RULE" in prompt1
    for t in b1["target_archetypes"]:
        assert f"`{t['id']}`" in prompt1

    # Mine step returns target_archetypes alongside snippets
    mined1 = client.post(f"/api/pipeline/batches/{b1['id']}/mine").json()
    assert mined1["selection_mode"] == "tier1_uncovered_default"
    assert [t["id"] for t in mined1["target_archetypes"]] == [t["id"] for t in b1["target_archetypes"]]

    # Approve SAMPLE_TEMPLATES (duration_half, survey, age, mobile) on batch 1
    client.post(f"/api/pipeline/batches/{b1['id']}/templates", json={"templates": SAMPLE_TEMPLATES})
    client.post(
        f"/api/pipeline/batches/{b1['id']}/verdicts",
        json={
            "verdicts": [
                {"template_id": t["id"], "passed_count": 8, "verdict_kind": "approved", "approved": True, "reason": "8/8"}
                for t in SAMPLE_TEMPLATES
            ]
        },
    )
    expected_covered = {t["archetype_id"] for t in SAMPLE_TEMPLATES}
    cov_after = client.get("/api/pipeline/batches").json()["tier1_coverage"]
    assert cov_after["covered_count"] == len(expected_covered)
    assert set(cov_after["covered_ids"]) == expected_covered

    # 2. Next default batch must NOT pick already-covered archetypes
    b2 = client.post("/api/pipeline/batches", json={"target_count": 24, "seed": 10, "corpus_ratio": 0.75}).json()
    assert b2["selection_mode"] == "tier1_uncovered_default"
    b2_ids = {t["id"] for t in b2["target_archetypes"]}
    assert b2_ids.isdisjoint(expected_covered)

    # 3. Custom notes batch overrides default Tier-1 targeting
    b3 = client.post(
        "/api/pipeline/batches",
        json={"target_count": 12, "seed": 11, "notes": "דגש מיוחד על טמפרטורות שליליות בלבד"},
    ).json()
    assert b3["selection_mode"] == "custom_notes"
    assert b3["target_archetypes"] == []
    prompt3 = fake_oc.created[-1]["prompt"]
    assert "דגש מיוחד על טמפרטורות שליליות בלבד" in prompt3
    assert "Numeric Usage Palette" not in prompt3


def test_text_file_corpus_sources_local_ssh_cli_api_and_prompt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys):
    import subprocess
    from numeric_pairs.corpus_sources import (
        CorpusSourceError,
        load_corpus_sources,
        save_corpus_source,
        search_configured_source,
        validate_source_spec,
    )
    from numeric_pairs.pipeline_cli import main as cli_main
    from numeric_pairs.web import app as web_app

    # 1. Lazy read must not touch tmp_path
    assert load_corpus_sources(tmp_path) == []
    assert list(tmp_path.iterdir()) == []

    # 2. Validation rejects unsafe SSH hosts / bad ids / missing ssh_host
    with pytest.raises(ValueError):
        validate_source_spec({"id": "bad id!", "name": "x", "location": "local", "path": "/tmp/a.txt"})
    with pytest.raises(ValueError):
        validate_source_spec({"id": "ssh1", "name": "x", "location": "ssh", "ssh_host": "-oProxyCommand=bad", "path": "/a.txt"})
    with pytest.raises(ValueError):
        validate_source_spec({"id": "ssh2", "name": "x", "location": "ssh", "ssh_host": "host; rm -rf /", "path": "/a.txt"})
    with pytest.raises(ValueError):
        validate_source_spec({"id": "ssh3", "name": "x", "location": "ssh", "path": "/a.txt"})

    # 3. Local text_file source: regex, fixed, context_lines, start_line, sensitive redaction
    sample_file = tmp_path / "sample_protocols.txt"
    sample_file.write_text(
        "\n".join(
            [
                "פתיחת הישיבה בנושא תכנון ובנייה.",
                'יש בעיה עם תכנית תמ"א 38 בחיזוק מבנים ותיקים.',
                "אנחנו דנים בסעיף 135 בחוק התכנון.",
                "שורה נוספת על סעיף 16 ועל 5.5 מיליארד שקלים.",
                "טלפון במשרד הוא 052-1234567 לבירורים.",
                'עוד אזכור של תמ"א 38 בסוף הישיבה.',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    data_root = tmp_path / "data"
    cli_main(
        [
            "add-source",
            "--data-root",
            str(data_root),
            "--id",
            "local_protocols",
            "--name",
            "פרוטוקולים מקומיים",
            "--location",
            "local",
            "--path",
            str(sample_file),
            "--description",
            "בדיקת קובץ טקסט מקומי",
        ]
    )
    added_out = json.loads(capsys.readouterr().out)
    assert added_out["source"]["id"] == "local_protocols"

    cli_main(
        [
            "search-source",
            "--data-root",
            str(data_root),
            "--source",
            "local_protocols",
            "--query",
            r"סעיף\s+\d+",
            "--mode",
            "regex",
            "--context",
            "1",
            "--limit",
            "10",
        ]
    )
    local_res = json.loads(capsys.readouterr().out)
    assert local_res["match_count"] == 2
    assert local_res["truncated"] is False
    assert local_res["matches"][0]["line_number"] == 3
    assert 'תמ"א 38' in local_res["matches"][0]["context_before"][0]
    assert local_res["matches"][1]["line_number"] == 4
    assert "[מזהה מוסתר]" in local_res["matches"][1]["context_after"][0]

    # Fixed mode + start_line skips first occurrence
    fixed_res = search_configured_source(
        data_root,
        "local_protocols",
        query='תמ"א 38',
        mode="fixed",
        start_line=3,
        limit=1,
    )
    assert fixed_res["match_count"] == 1
    assert fixed_res["matches"][0]["line_number"] == 6

    # 4. Remote SSH text_file source (mocked subprocess.run)
    save_corpus_source(
        data_root,
        {
            "id": "remote_knesset",
            "name": "פרוטוקולי ועדות הכנסת",
            "type": "text_file",
            "location": "ssh",
            "ssh_host": "compute-example-01",
            "path": "/data/committee/train_text_dump.txt",
            "description": "פרוטוקולים מרוחקים שורה למשפט",
            "enabled": True,
        },
    )

    ssh_calls: list[list[str]] = []

    def _fake_subprocess_run(cmd, **kwargs):
        ssh_calls.append(list(cmd))
        remote_cmd = cmd[-1]
        # Simulate BSD remote without -P on first call when testing fallback
        if "FALLBACK_TRIGGER" in remote_cmd and " -P " in remote_cmd:
            return subprocess.CompletedProcess(cmd, 2, "", "grep: invalid option -- P\n")
        if "NO_MATCH_PATTERN" in remote_cmd:
            return subprocess.CompletedProcess(cmd, 1, "", "")
        if "SSH_CONN_FAIL" in remote_cmd:
            return subprocess.CompletedProcess(cmd, 255, "", "ssh: Could not resolve hostname")
        # Return realistic grep -n -C 1 output with both overlapping lines and -- separator
        stdout = (
            "1-שורה לפני.\n"
            "2:הסכום הגיע ל-5.5 מיליארד שקלים בסעיף 135.\n"
            "3:וגם סעיף 136 עלה לדיון.\n"
            "4-שורה אחרי.\n"
            "--\n"
            "10:דיון נוסף בסעיף 140.\n"
        )
        return subprocess.CompletedProcess(cmd, 0, stdout, "")

    monkeypatch.setattr("numeric_pairs.corpus_sources.subprocess.run", _fake_subprocess_run)

    ssh_res = search_configured_source(
        data_root,
        "remote_knesset",
        query=r"-?\d+",
        mode="regex",
        limit=2,
        context_lines=1,
        start_line=101,
    )
    assert ssh_res["match_count"] == 2
    assert ssh_res["truncated"] is True
    # Line numbers adjusted by start_line - 1 (100)
    assert ssh_res["matches"][0]["line_number"] == 102
    assert ssh_res["matches"][0]["context_before"] == ["שורה לפני."]
    assert ssh_res["matches"][0]["context_after"] == ["וגם סעיף 136 עלה לדיון."]
    assert ssh_res["matches"][1]["line_number"] == 103
    # Verify safe ssh invocation and quoted `-e` + `tail -n +101`
    assert ssh_calls[0][:6] == ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "--"]
    assert ssh_calls[0][6] == "compute-example-01"
    assert "tail -n +101" in ssh_calls[0][7]
    assert "-e '-?\\d+'" in ssh_calls[0][7]

    # Automatic -P -> -E fallback translates \d -> [0-9]
    fb_res = search_configured_source(data_root, "remote_knesset", query=r"FALLBACK_TRIGGER\s+\d+", mode="regex", limit=2)
    assert fb_res["mode"] == "ere_fallback"
    assert "[0-9]+" in ssh_calls[-1][7]
    assert "[[:space:]]+" in ssh_calls[-1][7]

    # Exit code 1 -> empty list (no error)
    empty_res = search_configured_source(data_root, "remote_knesset", query="NO_MATCH_PATTERN", mode="fixed")
    assert empty_res["match_count"] == 0
    assert empty_res["matches"] == []

    # SSH connection failure -> CorpusSourceError
    with pytest.raises(CorpusSourceError):
        search_configured_source(data_root, "remote_knesset", query="SSH_CONN_FAIL", mode="fixed")

    # 5. FastAPI endpoints + Neon prompt awareness + mine_spoken_contexts integration
    fake_oc = FakeOpenChamberClient()
    test_review_store = ReviewStore(data_root)
    test_pipeline_store = PipelineStore(lambda: test_review_store, oc_client=fake_oc)
    monkeypatch.setattr(web_app, "store", test_review_store)
    monkeypatch.setattr(web_app, "pipeline_store", test_pipeline_store)
    monkeypatch.delenv("IVRIT_AI_COOKIE", raising=False)

    client = TestClient(web_app.app)
    sources_resp = client.get("/api/pipeline/sources").json()
    assert {s["id"] for s in sources_resp["sources"]} == {"local_protocols", "remote_knesset"}

    # Creating a batch advertises configured text_file sources and `search-source` CLI in Neon's prompt
    batch = client.post("/api/pipeline/batches", json={"target_count": 12, "seed": 5, "notes": "חוקים וועדות"}).json()
    prompt = fake_oc.created[-1]["prompt"]
    assert "remote_knesset" in prompt
    assert "search-source" in prompt

    # Searching with batch_id attaches snippets to the batch
    s_resp = client.post(
        "/api/pipeline/sources/local_protocols/search",
        json={"query": r"סעיף\s+\d+", "mode": "regex", "limit": 5, "context_lines": 1, "batch_id": batch["id"]},
    )
    assert s_resp.status_code == 200
    assert s_resp.json()["match_count"] == 2
    polled = client.get(f"/api/pipeline/batches/{batch['id']}").json()
    assert any(sn.get("source_id") == "local_protocols" for sn in polled["mined_snippets"])

    # SSH error surfaces cleanly as HTTP 502
    err_resp = client.post(
        "/api/pipeline/sources/remote_knesset/search",
        json={"query": "SSH_CONN_FAIL", "mode": "fixed"},
    )
    assert err_resp.status_code == 502

    # Mine step without ivrit.ai cookie still pulls live snippets from configured text_file sources!
    mined = client.post(f"/api/pipeline/batches/{batch['id']}/mine").json()
    assert mined["mode"] == "live_text_sources"
    assert any(sn.get("source_type") == "text_file" for sn in mined["snippets"])
    assert len(mined["available_sources"]) == 2

    # Delete source via API
    del_resp = client.delete("/api/pipeline/sources/remote_knesset")
    assert del_resp.status_code == 200
    assert [s["id"] for s in del_resp.json()["sources"]] == ["local_protocols"]


def test_optional_empty_opener_micro_bank_and_opening_diversity_warnings():
    from numeric_pairs.pipeline import _opening_diversity_warnings, build_neon_prompt

    # 1. Optional "" inside micro_bank allows mixing direct openings with multi-word conversational openers
    tpl_ok = {
        "id": "optional_opener_budget_01",
        "archetype_id": "money",
        "slots": {
            "opener": {
                "kind": "micro_bank",
                "values": ["", "אם אני זוכר נכון, ", "תחשוב על זה, ", "שים לב, "],
            },
            "amount": {"kind": "int_range", "lower": 120, "upper": 480, "step": 20},
        },
        "nodes": [
            {"slot": "opener"},
            {"lit": "התיקון הזה עלה לנו "},
            {"num": "counted_noun", "slot": "amount", "noun": {"singular": "שקל", "plural": "שקלים", "gender": "m"}},
            {"lit": "."},
        ],
    }
    samples = validate_and_stress_template(tpl_ok, stress_count=8, seed=42)
    assert any(s["digits"].startswith("התיקון הזה") for s in samples)
    assert any(s["digits"].startswith("אם אני זוכר נכון, התיקון הזה") for s in samples)
    assert all(s["digits"] == s["digits"].strip() and "  " not in s["digits"] for s in samples)

    # Leading space caused by bad spacing with optional "" is caught at compile time
    tpl_bad_space = {
        **tpl_ok,
        "id": "optional_opener_bad_space_02",
        "nodes": [
            {"slot": "opener"},
            {"lit": " התיקון הזה עלה לנו "},
            {"num": "counted_noun", "slot": "amount", "noun": {"singular": "שקל", "plural": "שקלים", "gender": "m"}},
            {"lit": "."},
        ],
    }
    with pytest.raises(ValueError, match="whitespace"):
        validate_and_stress_template(tpl_bad_space, stress_count=8, seed=42)

    # 2. Opening diversity warnings flag repeated tired 1-word starters and stay empty for varied/direct batches
    repetitive = [
        {"id": "t1", "stress_samples": [{"digits": "שמע, זה עלה 40 שקל."}]},
        {"id": "t2", "stress_samples": [{"digits": "שמע, הגענו ב-5 בערב."}]},
        {"id": "t3", "stress_samples": [{"digits": "בקיצור, נשארו 3 שעות."}]},
        {"id": "t4", "stress_samples": [{"digits": "בסוף, שילמנו 90 שקל."}]},
    ]
    warns = _opening_diversity_warnings(repetitive)
    assert any("שמע" in w for w in warns)
    assert any("4/4" in w for w in warns)

    diverse = [
        {"id": "d1", "stress_samples": [{"digits": "בשבוע שעבר שילמנו 40 שקל."}]},
        {"id": "d2", "stress_samples": [{"digits": "אם אני זוכר נכון, הגענו ב-5 בערב."}]},
        {"id": "d3", "stress_samples": [{"digits": "אתה לא מאמין, נשארו רק 3 שעות."}]},
        {"id": "d4", "stress_samples": [{"digits": "הוועדה אישרה תקציב של 90 מיליון."}]},
    ]
    assert _opening_diversity_warnings(diverse) == []

    # 3. Prompt surfaces the opening-diversity guidance and examples
    prompt = build_neon_prompt(
        batch_id="b_test",
        server_url="http://127.0.0.1:8766",
        target_count=24,
        candidate_templates_target=8,
        min_approved_templates=4,
        corpus_ratio=0.75,
        user_notes="",
        temp_dir="/tmp",
    )
    assert "אם אני זוכר נכון," in prompt
    assert "תחשוב על זה," in prompt
    assert "אתה קולט?" in prompt
    assert "אתה לא מאמין," in prompt
    assert "שים לב," in prompt
    assert "Omit discourse-starter prefixes" in prompt
    assert "CORPUS-FIRST RULE" in prompt


def test_multi_usage_coverage_canned_noun_warning_and_snippet_reuse(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from numeric_pairs.pipeline import _opening_diversity_warnings
    from numeric_pairs.web import app as web_app

    # 1. Canned Tier-1 stationery nouns and single-number batches trigger style warnings
    canned_warns = _opening_diversity_warnings(
        [{"id": "c1", "stress_samples": [{"digits": "במשלוח של הבוקר הועברו כ-10 חוברות."}], "spec": {"nodes": [{"num": "domain"}]}}]
    )
    assert any("חוברות" in w or "stationery" in w for w in canned_warns)

    # 2. Multi-usage `covered_usages` credits all represented numeric usages, and `reuse_snippets_from` reuses prior snippets
    fake_oc = FakeOpenChamberClient()
    test_review_store = ReviewStore(tmp_path)
    test_pipeline_store = PipelineStore(lambda: test_review_store, oc_client=fake_oc)
    monkeypatch.setattr(web_app, "store", test_review_store)
    monkeypatch.setattr(web_app, "pipeline_store", test_pipeline_store)
    monkeypatch.delenv("IVRIT_AI_COOKIE", raising=False)

    client = TestClient(web_app.app)

    # Create seed batch with real (non-exemplar) mined snippets on disk
    b1 = client.post("/api/pipeline/batches", json={"target_count": 12, "seed": 21, "notes": "seed"}).json()
    b1_path = tmp_path / "pipeline" / "batches" / f"{b1['id']}.json"
    raw = json.loads(b1_path.read_text(encoding="utf-8"))
    raw["mine_mode"] = "live_mixed"
    raw["mined_snippets"] = [
        {
            "id": "ivrit_100_1",
            "bucket": "tier1:section",
            "target_archetype": "section",
            "source": "גיקונומי",
            "episode_title": "פרק בדיקה",
            "hit_text": "דיברו על 3.5 מיליון שקל",
            "context_window": "רגע, איך יכול להיות שתקציב של 3.5 מיליון שקל תקוע כבר מ-2021 בגלל סעיף אחד?",
        },
        {
            "id": "src_knesset_42",
            "bucket": "spoken_units",
            "source": "פרוטוקולי ועדות הכנסת",
            "episode_title": "שורה 42",
            "hit_text": "60% מהתקציב",
            "context_window": "אנחנו מדברים על זה שכמעט 60% מהתקציב בכלל לא הגיע לפריפריה.",
        },
    ]
    b1_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

    # Submit a multi-usage template covering 3 numeric usages at once!
    multi_tpl = {
        **SAMPLE_TEMPLATES[0],
        "id": "multi_usage_spoken_01",
        "archetype_id": "duration_half",
        "covered_usages": ["duration_half", "departure", "money"],
        "source_snippet_id": "ivrit_100_1",
    }
    sub = client.post(f"/api/pipeline/batches/{b1['id']}/templates", json={"templates": [multi_tpl]})
    assert sub.status_code == 200
    client.post(
        f"/api/pipeline/batches/{b1['id']}/verdicts",
        json={"verdicts": [{"template_id": "multi_usage_spoken_01", "passed_count": 8, "verdict_kind": "approved", "approved": True, "reason": "8/8"}]},
    )
    cov = client.get("/api/pipeline/batches").json()["tier1_coverage"]
    assert {"duration_half", "departure", "money"}.issubset(set(cov["covered_ids"]))

    # Status reports the 2 unique reusable snippets
    st = client.get("/api/pipeline/status").json()
    assert st["reusable_snippets"]["total_unique_snippets"] == 2

    # Launch batch 2 reusing existing snippets (without network/SSH calls!)
    b2 = client.post(
        "/api/pipeline/batches",
        json={"target_count": 12, "seed": 22, "reuse_snippets_from": ["all"]},
    ).json()
    assert "ALREADY sampled in previous batches" in fake_oc.created[-1]["prompt"]
    mined2 = client.post(f"/api/pipeline/batches/{b2['id']}/mine").json()
    assert mined2["mode"] == "reused_from_batches"
    assert len(mined2["snippets"]) == 2
    assert all(s.get("reused_from_batch") == b1["id"] for s in mined2["snippets"])
    # Stale target_archetype tag is stripped so Neon treats the snippet freshly
    assert all("target_archetype" not in s for s in mined2["snippets"])


def test_counted_noun_hebrew_dual_forms_for_value_two():
    from numeric_pairs.micro_templates import render_micro_template

    cases = [
        ({"singular": "יום", "plural": "ימים", "gender": "m"}, "", "2 ימים", "יומיים"),
        ({"singular": "חודש", "plural": "חודשים", "gender": "m"}, "איזה ", "איזה 2 חודשים", "איזה חודשיים"),
        ({"singular": "שבוע", "plural": "שבועות", "gender": "m"}, "כ-", "כ-2 שבועות", "כשבועיים"),
        ({"singular": "שנה", "plural": "שנים", "gender": "f"}, "יותר מ-", "יותר מ-2 שנים", "יותר משנתיים"),
        ({"singular": "שעה", "plural": "שעות", "gender": "f"}, "בערך ", "בערך 2 שעות", "בערך שעתיים"),
        ({"singular": "פעם", "plural": "פעמים", "gender": "f"}, "לפחות ", "לפחות 2 פעמים", "לפחות פעמיים"),
        # Non-dual nouns still use שני/שתי
        ({"singular": "דקה", "plural": "דקות", "gender": "f"}, "", "2 דקות", "שתי דקות"),
        ({"singular": "שקל", "plural": "שקלים", "gender": "m"}, "", "2 שקלים", "שני שקלים"),
    ]
    for idx, (noun, approx, expected_digits, expected_cardinal) in enumerate(cases):
        tpl = {
            "id": f"dual_test_{idx}",
            "archetype_id": "purchase",
            "slots": {"n": {"kind": "int_range", "lower": 2, "upper": 5}},
            "nodes": [
                {"lit": "זה לקח "},
                {"num": "counted_noun", "slot": "n", "approx": approx, "noun": noun},
                {"lit": "."},
            ],
        }
        p2 = render_micro_template(tpl, {"n": 2})
        assert p2["digits"] == f"זה לקח {expected_digits}."
        assert p2["cardinal"] == f"זה לקח {expected_cardinal}."

    # Value 3 still uses normal construct plural
    p3 = render_micro_template(
        {
            "id": "dual_test_three",
            "archetype_id": "purchase",
            "slots": {"n": {"kind": "int_range", "lower": 2, "upper": 5}},
            "nodes": [
                {"lit": "זה לקח "},
                {"num": "counted_noun", "slot": "n", "noun": {"singular": "יום", "plural": "ימים", "gender": "m"}},
                {"lit": "."},
            ],
        },
        {"n": 3},
    )
    assert p3["cardinal"] == "זה לקח שלושה ימים."


def test_template_library_mixed_80_20_generation_export_and_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import subprocess
    import sys

    from numeric_pairs.export import build_export
    from numeric_pairs.template_library import library_summary
    from numeric_pairs.web import app as web_app

    fake_oc = FakeOpenChamberClient()
    test_review_store = ReviewStore(tmp_path)
    test_pipeline_store = PipelineStore(lambda: test_review_store, oc_client=fake_oc)
    monkeypatch.setattr(web_app, "store", test_review_store)
    monkeypatch.setattr(web_app, "pipeline_store", test_pipeline_store)
    monkeypatch.delenv("IVRIT_AI_COOKIE", raising=False)
    monkeypatch.delenv("NUMERIC_PAIRS_TEMPLATE_LIBRARY", raising=False)

    client = TestClient(web_app.app)

    # 1. Read-only GET /api/library is strictly lazy (creates no files)
    lib0 = client.get("/api/library").json()
    assert lib0["total_templates"] == 0
    assert lib0["exists"] is False
    assert list(tmp_path.iterdir()) == []

    # 2. Decoupled template_count vs target_count + auto-promotion on finalize
    batch = client.post(
        "/api/pipeline/batches",
        json={"template_count": 12, "target_count": 20, "seed": 31, "notes": "lib test"},
    ).json()
    assert batch["sizing"]["candidate_templates_target"] == 12
    assert batch["target_count"] == 20

    client.post(f"/api/pipeline/batches/{batch['id']}/templates", json={"templates": SAMPLE_TEMPLATES})
    verdicts = [
        {"template_id": t["id"], "passed_count": 8, "verdict_kind": "approved", "approved": True, "reason": "8/8"}
        for t in SAMPLE_TEMPLATES
    ]
    client.post(f"/api/pipeline/batches/{batch['id']}/verdicts", json={"verdicts": verdicts})
    fin = client.post(f"/api/pipeline/batches/{batch['id']}/finalize")
    assert fin.status_code == 200

    lib1 = client.get("/api/library").json()
    assert lib1["exists"] is True
    assert lib1["total_templates"] == len(SAMPLE_TEMPLATES)
    assert lib1["enabled_templates"] == len(SAMPLE_TEMPLATES)
    assert lib1["batches"][0]["batch_id"] == batch["id"]

    # Download curated JSON works
    dl = client.get("/api/library/download")
    assert dl.status_code == 200
    assert json.loads(dl.text)["schema"] == "micro-template-library-v1"

    # 3. Default run via POST /api/runs uses 80% MicroTemplate / 20% Tier-1 mix!
    run_80 = client.post("/api/runs", json={"seed": 42, "count": 50}).json()
    assert run_80["micro_template_ratio"] == 0.8
    assert run_80["mix"]["micro_template_count"] == 40
    assert run_80["mix"]["tier1_count"] == 10
    assert sum(1 for p in run_80["pairs"] if p.get("source_tier") == "micro_template") == 40
    assert sum(1 for p in run_80["pairs"] if p.get("source_tier") == "tier1") == 10

    # Same seed + ratio is 100% deterministic
    run_80_again = client.post("/api/runs", json={"seed": 42, "count": 50}).json()
    assert run_80_again["id"] == run_80["id"]
    assert run_80_again["pairs"] == run_80["pairs"]

    # Configurable ratios: 100% micro, 50/50, and 0% (pure Tier-1)
    run_100 = client.post("/api/runs", json={"seed": 42, "count": 20, "micro_template_ratio": 1.0}).json()
    assert run_100["mix"]["micro_template_count"] == 20
    assert run_100["mix"]["tier1_count"] == 0

    run_50 = client.post("/api/runs", json={"seed": 42, "count": 20, "micro_template_ratio": 0.5}).json()
    assert run_50["mix"]["micro_template_count"] == 10
    assert run_50["mix"]["tier1_count"] == 10

    run_0 = client.post("/api/runs", json={"seed": 42, "count": 20, "micro_template_ratio": 0.0}).json()
    assert run_0["mix"]["micro_template_count"] == 0
    assert run_0["mix"]["tier1_count"] == 20
    assert all("micro_template_id" not in p for p in run_0["pairs"])

    # 4. Export verifies source_tiers and zero_template_leakage across train/dev/test
    manifest, splits = build_export(run_80, {})
    assert manifest["source_tiers"] == {"micro_template": 40, "tier1": 10}
    assert manifest["unique_micro_templates"] == len(SAMPLE_TEMPLATES)
    assert manifest["quality_gates"]["zero_template_leakage"] is True
    split_tpls = [
        {row["micro_template_id"] for row in rows if row.get("micro_template_id")}
        for rows in splits.values()
    ]
    assert not any(a & b for i, a in enumerate(split_tpls) for b in split_tpls[i + 1 :])

    # 5. Per-template and per-batch toggle/delete controls
    first_tid = SAMPLE_TEMPLATES[0]["id"]
    r_tog = client.patch(f"/api/library/templates/{first_tid}", json={"enabled": False})
    assert r_tog.status_code == 200
    assert r_tog.json()["summary"]["enabled_templates"] == len(SAMPLE_TEMPLATES) - 1

    r_btog = client.post(f"/api/library/batches/{batch['id']}/toggle", json={"enabled": False})
    assert r_btog.status_code == 200
    assert r_btog.json()["summary"]["enabled_templates"] == 0

    # When all library templates are disabled, create_run falls back cleanly to Tier-1
    run_fb = client.post("/api/runs", json={"seed": 7, "count": 10}).json()
    assert run_fb["mix"]["fallback_to_tier1"] is True
    assert run_fb["mix"]["tier1_count"] == 10

    # Re-enable batch and test CLI (`python -m numeric_pairs`) with --library and --micro-ratio
    client.post(f"/api/library/batches/{batch['id']}/toggle", json={"enabled": True})
    lib_path = tmp_path / "micro_template_library.json"
    out_dir = tmp_path / "cli_export"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "numeric_pairs",
            "--seed",
            "99",
            "--count",
            "50",
            "--library",
            str(lib_path),
            "--out-dir",
            str(out_dir),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert proc.returncode == 0
    cli_manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert cli_manifest["mix"]["micro_template_count"] == 40
    assert cli_manifest["mix"]["tier1_count"] == 10
    assert cli_manifest["source_tiers"] == {"micro_template": 40, "tier1": 10}
    assert cli_manifest["quality_gates"]["zero_template_leakage"] is True
    assert len((out_dir / "pairs.jsonl").read_text(encoding="utf-8").splitlines()) == 50

    # CLI --no-library forces 100% Tier-1
    out_t1 = tmp_path / "cli_t1"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "numeric_pairs",
            "--seed",
            "99",
            "--count",
            "20",
            "--no-library",
            "--out-dir",
            str(out_t1),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    t1_manifest = json.loads((out_t1 / "manifest.json").read_text(encoding="utf-8"))
    assert t1_manifest["mix"]["micro_template_count"] == 0
    assert t1_manifest["mix"]["tier1_count"] == 20

    # Delete a template works cleanly
    r_del = client.delete(f"/api/library/templates/{first_tid}")
    assert r_del.status_code == 200
    assert library_summary(tmp_path, include_official=False, include_templates=False)["total_templates"] == len(SAMPLE_TEMPLATES) - 1


def test_official_repo_library_overlay_and_selective_publish(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from numeric_pairs.template_library import load_library_entries, promote_specs_to_library
    from numeric_pairs.web import app as web_app

    local_root = tmp_path / "local_data"
    official_file = tmp_path / "repo" / "micro_template_library.json"

    test_review_store = ReviewStore(local_root, official_library=official_file)
    test_pipeline_store = PipelineStore(lambda: test_review_store, oc_client=FakeOpenChamberClient())
    monkeypatch.setattr(web_app, "store", test_review_store)
    monkeypatch.setattr(web_app, "pipeline_store", test_pipeline_store)
    monkeypatch.delenv("NUMERIC_PAIRS_TEMPLATE_LIBRARY", raising=False)
    monkeypatch.delenv("NUMERIC_PAIRS_OFFICIAL_LIBRARY", raising=False)

    client = TestClient(web_app.app)

    # 1. Seed local workspace with 3 templates (none published yet)
    promote_specs_to_library(local_root, SAMPLE_TEMPLATES, source_batch_id="b_local_01", enabled=True)
    lib0 = client.get("/api/library").json()
    assert lib0["official_templates"] == 0
    assert lib0["unpublished_templates"] == len(SAMPLE_TEMPLATES)
    assert all(t["publish_status"] == "unpublished" for t in lib0["templates"])

    # 2. Selectively publish 2 of the 3 templates to the official repo file
    chosen_ids = [SAMPLE_TEMPLATES[0]["id"], SAMPLE_TEMPLATES[1]["id"]]
    pub1 = client.post("/api/library/publish", json={"template_ids": chosen_ids}).json()
    assert pub1["published_count"] == 2
    assert pub1["total_official_templates"] == 2
    assert official_file.is_file()

    lib1 = client.get("/api/library").json()
    by_id = {t["id"]: t for t in lib1["templates"]}
    assert by_id[chosen_ids[0]]["publish_status"] == "published"
    assert by_id[chosen_ids[1]]["publish_status"] == "published"
    assert by_id[SAMPLE_TEMPLATES[2]["id"]]["publish_status"] == "unpublished"
    assert lib1["official_templates"] == 2
    assert lib1["unpublished_templates"] == len(SAMPLE_TEMPLATES) - 2

    # 3. Publish remaining unpublished templates ("select all" / default template_ids=None)
    pub2 = client.post("/api/library/publish", json={}).json()
    assert pub2["published_count"] == len(SAMPLE_TEMPLATES) - 2
    assert pub2["total_official_templates"] == len(SAMPLE_TEMPLATES)
    lib2 = client.get("/api/library").json()
    assert lib2["unpublished_templates"] == 0
    assert lib2["published_templates"] == len(SAMPLE_TEMPLATES)

    # 4. Simulate a fresh git clone (brand-new empty local dir) reading ONLY the official repo file
    fresh_local = tmp_path / "fresh_clone_local"
    fresh_entries = load_library_entries(fresh_local, official_path=official_file, include_official=True, enabled_only=True)
    assert len(fresh_entries) == len(SAMPLE_TEMPLATES)
    assert all(e["source_scope"] == "official" and e["published"] is True for e in fresh_entries)

    fresh_store = ReviewStore(fresh_local, official_library=official_file)
    fresh_run = fresh_store.create_run(42, 20)  # Default 80/20 mix works out-of-the-box!
    assert fresh_run["mix"]["micro_template_count"] == 16
    assert fresh_run["mix"]["tier1_count"] == 4

    # 5. Unpublishing removes from official file without deleting local copy
    rm = client.delete(f"/api/library/official/{chosen_ids[0]}")
    assert rm.status_code == 200
    lib3 = client.get("/api/library").json()
    assert lib3["official_templates"] == len(SAMPLE_TEMPLATES) - 1
    assert lib3["unpublished_templates"] == 1


def test_batch_completion_session_wakeup_notification(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import time
    from numeric_pairs.web import app as web_app

    fake_oc = FakeOpenChamberClient()
    test_review_store = ReviewStore(tmp_path)
    test_pipeline_store = PipelineStore(lambda: test_review_store, oc_client=fake_oc)
    test_pipeline_store._monitor_interval_s = 0.05
    monkeypatch.setattr(web_app, "store", test_review_store)
    monkeypatch.setattr(web_app, "pipeline_store", test_pipeline_store)
    monkeypatch.delenv("IVRIT_AI_COOKIE", raising=False)

    client = TestClient(web_app.app)

    # 1. Finalize sends wake-up message to notify_session_id exactly once with notify_context
    b1 = client.post(
        "/api/pipeline/batches",
        json={
            "target_count": 12,
            "seed": 101,
            "notes": "wakeup test",
            "notify_session_id": "ses_parent_wakeup_01",
            "notify_context": "Series 1/10 · kick off 2/10 if succeeded",
        },
    ).json()
    assert b1["notify_session_id"] == "ses_parent_wakeup_01"

    client.post(f"/api/pipeline/batches/{b1['id']}/templates", json={"templates": SAMPLE_TEMPLATES})
    verdicts = [
        {"template_id": t["id"], "passed_count": 8, "verdict_kind": "approved", "approved": True, "reason": "8/8"}
        for t in SAMPLE_TEMPLATES
    ]
    client.post(f"/api/pipeline/batches/{b1['id']}/verdicts", json={"verdicts": verdicts})
    fin = client.post(f"/api/pipeline/batches/{b1['id']}/finalize")
    assert fin.status_code == 200

    deadline = time.time() + 3.0
    while len(fake_oc.sent_prompts) < 1 and time.time() < deadline:
        time.sleep(0.02)

    assert len(fake_oc.sent_prompts) == 1
    msg = fake_oc.sent_prompts[0]
    assert msg["session_id"] == "ses_parent_wakeup_01"
    assert b1["id"] in msg["prompt"]
    assert "status: succeeded" in msg["prompt"]
    assert "Series 1/10" in msg["prompt"]

    # Calling sync / finalize again must NOT double-notify
    test_pipeline_store._dispatch_completion_notification(b1["id"])
    time.sleep(0.1)
    assert len(fake_oc.sent_prompts) == 1

    # 2. Failed batch also wakes up notify_session_id with error details
    b2 = client.post(
        "/api/pipeline/batches",
        json={
            "target_count": 12,
            "seed": 102,
            "notes": "fail test",
            "dispatch_session": False,
            "notify_session_id": "ses_parent_wakeup_02",
            "notify_context": "Series 2/10",
        },
    ).json()
    client.post(f"/api/pipeline/batches/{b2['id']}/fail", json={"reason": "simulated error"})

    deadline = time.time() + 3.0
    while len(fake_oc.sent_prompts) < 2 and time.time() < deadline:
        time.sleep(0.02)

    assert len(fake_oc.sent_prompts) == 2
    msg2 = fake_oc.sent_prompts[1]
    assert msg2["session_id"] == "ses_parent_wakeup_02"
    assert "status: failed" in msg2["prompt"]
    assert "simulated error" in msg2["prompt"]

    # 3. Transient session status "retry" must NOT be mistaken for idle/failed
    b3 = client.post(
        "/api/pipeline/batches",
        json={
            "target_count": 12,
            "seed": 103,
            "notes": "retry test",
            "notify_session_id": "ses_parent_wakeup_03",
        },
    ).json()
    # Backdate dispatch timestamp so the >10s idle-detection window is active
    b3_path = test_pipeline_store.batches_dir / f"{b3['id']}.json"
    b3_data = json.loads(b3_path.read_text(encoding="utf-8"))
    b3_data["sessions"][0]["dispatched_at_ts"] = time.time() - 60.0
    b3_path.write_text(json.dumps(b3_data, ensure_ascii=False), encoding="utf-8")

    fake_oc.status = "retry"
    synced_retry = test_pipeline_store.sync_batch_telemetry(b3["id"], force=True)
    assert synced_retry is not None
    assert synced_retry["status"] == "running"
    assert len(fake_oc.sent_prompts) == 2

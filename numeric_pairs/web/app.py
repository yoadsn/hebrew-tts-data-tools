"""Same-origin JSON API for the staged, no-build review UI."""

from pathlib import Path
import re

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from numeric_pairs.catalog import ARCHETYPES, BY_ID, CATALOG_VERSION, SCENARIO_AREAS
from numeric_pairs.core import RENDERER_VERSION
from numeric_pairs.inspection import describe
from numeric_pairs.naturalness import NaturalnessStore
from numeric_pairs.review import ReviewStore
from numeric_pairs.candidates import CandidateStore
from numeric_pairs.export import save_export
from numeric_pairs.variants import DEFAULT_FORMAL_WEIGHTS

app = FastAPI(title="Hebrew numeric pairs")
store = ReviewStore()
candidate_store = CandidateStore(store.root)
naturalness_store = NaturalnessStore(store.root)


class GenerateRequest(BaseModel):
    seed: int = 42
    count: int = Field(default=len(ARCHETYPES), ge=1, le=200)
    archetypes: list[str] | None = None
    address_lengths: list[int] = Field(default_factory=lambda: [1, 2, 3])
    boundary_weight: float = Field(default=0.25, ge=0, le=1)
    variant_weights: dict[str, float] | None = None


class FeedbackRequest(BaseModel):
    pair_id: str
    verdict: str
    note: str = ""


class NaturalnessRatingRequest(BaseModel):
    verdict: str
    note: str = ""


class CorpusRequest(BaseModel):
    sentences: str = Field(max_length=20000)
    source: str = Field(max_length=300)
    license: str = Field(max_length=300)
    restrictions: str = Field(default="", max_length=300)
    approved_for_derivation: bool = False
    purpose: str = "derivation"


class CandidateReviewRequest(BaseModel):
    status: str
    grammar: str = ""
    slots: str = ""
    safe_ranges: str = ""
    written_policy: str = ""
    spoken_policy: str = ""
    note: str = ""


@app.get("/")
def index():
    return FileResponse(Path(__file__).with_name("index.html"))


@app.get("/api/catalog")
def catalog():
    return {"catalog_version": CATALOG_VERSION, "renderer_version": RENDERER_VERSION,
            "archetypes": [item.__dict__ for item in ARCHETYPES],
            "default_formal_weights": DEFAULT_FORMAL_WEIGHTS,
            "scenario_areas": [{"title": title, "implemented": list(ids), "pending": pending}
                               for title, ids, pending in SCENARIO_AREAS]}


@app.get("/api/runs")
def runs():
    return store.list_runs()


@app.get("/api/archetypes/never-ran")
def never_ran_archetypes():
    return {"archetypes": store.never_ran_archetypes()}


@app.get("/api/archetypes/{archetype_id}/design")
def archetype_design(archetype_id: str):
    if archetype_id not in BY_ID:
        raise HTTPException(404, "Archetype not found")
    return describe(archetype_id)


@app.get("/api/naturalness")
def naturalness_flags():
    return naturalness_store.flags()


@app.post("/api/naturalness/{flag_id}/rating")
def rate_naturalness(flag_id: str, request: NaturalnessRatingRequest):
    try:
        return naturalness_store.rate(flag_id, request.verdict, request.note)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/runs")
def create_run(request: GenerateRequest):
    try:
        return store.create_run(request.seed, request.count, request.archetypes,
                                address_lengths=tuple(request.address_lengths),
                                boundary_weight=request.boundary_weight,
                                variant_weights=request.variant_weights)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(404, "Run not found")
    return {**run, "feedback": store.feedback(run_id)}


@app.get("/api/runs/{run_id}/coverage")
def coverage(run_id: str):
    summary = store.coverage(run_id)
    if summary is None:
        raise HTTPException(404, "Run not found")
    return summary


@app.post("/api/runs/{run_id}/feedback")
def save_feedback(run_id: str, request: FeedbackRequest):
    try:
        return store.save_feedback(run_id, request.pair_id, request.verdict, request.note)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/candidates")
def candidates():
    return candidate_store.list()


@app.post("/api/candidates/import")
def import_candidates(request: CorpusRequest):
    try:
        return candidate_store.ingest(**request.model_dump())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/candidates/{candidate_id}/review")
def review_candidate(candidate_id: str, request: CandidateReviewRequest):
    try:
        return candidate_store.review(candidate_id, **request.model_dump())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/runs/{run_id}/export")
def export_run(run_id: str):
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(404, "Run not found")
    try:
        return save_export(store.root, run, store.feedback(run_id))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/exports/{export_id}/{filename}")
def download_export(export_id: str, filename: str):
    if not re.fullmatch(r"[a-f0-9]{20}-[a-f0-9]{16}", export_id) or filename not in {
            "manifest.json", "train.jsonl", "dev.jsonl", "test.jsonl"}:
        raise HTTPException(404, "Export not found")
    path = store.root / "exports" / export_id / filename
    if not path.is_file():
        raise HTTPException(404, "Export not found")
    return FileResponse(path, filename=filename)

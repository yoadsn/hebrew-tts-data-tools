"""Same-origin JSON API for the staged, no-build review UI."""

from pathlib import Path
import re
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from numeric_pairs.catalog import ARCHETYPES, BY_ID, CATALOG_VERSION, SCENARIO_AREAS
from numeric_pairs.core import RENDERER_VERSION
from numeric_pairs.corpus_sources import CorpusSourceError
from numeric_pairs.inspection import describe
from numeric_pairs.naturalness import NaturalnessStore
from numeric_pairs.pipeline import PipelineStore
from numeric_pairs.review import ReviewStore
from numeric_pairs.candidates import CandidateStore
from numeric_pairs.export import save_export
from numeric_pairs.template_library import (
    DEFAULT_MICRO_TEMPLATE_RATIO,
    delete_template as delete_library_template,
    library_file,
    library_summary,
    official_library_file,
    publish_templates_to_repo,
    set_batch_enabled as set_library_batch_enabled,
    set_template_enabled as set_library_template_enabled,
    sync_library_from_batches,
    unpublish_template_from_repo,
)
from numeric_pairs.variants import DEFAULT_FORMAL_WEIGHTS

app = FastAPI(title="Hebrew numeric pairs")
store = ReviewStore()
candidate_store = CandidateStore(store.root)
naturalness_store = NaturalnessStore(store.root)
pipeline_store = PipelineStore(lambda: store)


class GenerateRequest(BaseModel):
    seed: int = 42
    count: int = Field(default=len(ARCHETYPES), ge=1, le=50000)
    archetypes: list[str] | None = None
    address_lengths: list[int] = Field(default_factory=lambda: [1, 2, 3])
    boundary_weight: float = Field(default=0.25, ge=0, le=1)
    variant_weights: dict[str, float] | None = None
    micro_template_ratio: float = Field(default=DEFAULT_MICRO_TEMPLATE_RATIO, ge=0.0, le=1.0)


class LibrarySyncRequest(BaseModel):
    batch_ids: list[str] | None = None
    only_multi_number: bool = False
    disable_single_number_batches: bool = False


class LibraryToggleRequest(BaseModel):
    enabled: bool


class LibraryPublishRequest(BaseModel):
    template_ids: list[str] | None = None
    batch_ids: list[str] | None = None
    include_disabled: bool = False


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


class PipelineSettingsRequest(BaseModel):
    ivrit_cookie: str | None = Field(default=None, max_length=16000)


class PipelineCreateBatchRequest(BaseModel):
    target_count: int = Field(default=24, ge=1, le=5000)
    template_count: int | None = Field(default=None, ge=3, le=55)
    seed: int = 42
    corpus_ratio: float = Field(default=0.75, ge=0.0, le=1.0)
    notes: str = Field(default="", max_length=2000)
    reuse_snippets_from: list[str] | None = None
    model: str = Field(default="google/gemini-4-neon", max_length=120)
    variant: str = Field(default="default", max_length=40)
    dispatch_session: bool = True
    notify_session_id: str | None = Field(default=None, max_length=120)
    notify_context: str = Field(default="", max_length=2000)


class PipelineTemplatesRequest(BaseModel):
    templates: list[dict[str, Any]]


class PipelineVerdictsRequest(BaseModel):
    verdicts: list[dict[str, Any]]


class PipelineFailRequest(BaseModel):
    reason: str = Field(max_length=2000)


class PipelineCorpusSourceRequest(BaseModel):
    id: str = Field(min_length=1, max_length=48)
    name: str = Field(min_length=1, max_length=120)
    type: str = Field(default="text_file", max_length=32)
    location: str = Field(default="local", max_length=16)
    path: str = Field(min_length=1, max_length=500)
    ssh_host: str | None = Field(default=None, max_length=128)
    ssh_port: int | None = Field(default=None, ge=1, le=65535)
    description: str = Field(default="", max_length=300)
    enabled: bool = True


class PipelineSourceSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    mode: str = Field(default="regex", max_length=16)
    limit: int = Field(default=20, ge=1, le=100)
    context_lines: int = Field(default=0, ge=0, le=5)
    ignore_case: bool = False
    start_line: int = Field(default=1, ge=1)
    batch_id: str | None = Field(default=None, max_length=40)


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
                                variant_weights=request.variant_weights,
                                micro_template_ratio=request.micro_template_ratio)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/library")
def get_library(include_templates: bool = True):
    return library_summary(
        store.root,
        official_path=store.official_library_path,
        include_official=store.include_official_library,
        include_templates=include_templates,
    )


@app.post("/api/library/sync")
def sync_library(request: LibrarySyncRequest):
    return sync_library_from_batches(
        store.root,
        batch_ids=request.batch_ids,
        only_multi_number=request.only_multi_number,
        disable_single_number_batches=request.disable_single_number_batches,
        official_path=store.official_library_path,
        include_official=store.include_official_library,
    )


@app.post("/api/library/publish")
def publish_library(request: LibraryPublishRequest):
    off_path = store.official_library_path or official_library_file()
    return publish_templates_to_repo(
        store.root,
        template_ids=request.template_ids,
        batch_ids=request.batch_ids,
        include_disabled=request.include_disabled,
        official_path=off_path,
    )


@app.delete("/api/library/official/{template_id}")
def unpublish_library_template(template_id: str):
    off_path = store.official_library_path or official_library_file()
    if not unpublish_template_from_repo(store.root, template_id, official_path=off_path):
        raise HTTPException(404, f"Template {template_id!r} not found in official repo library")
    return {
        "unpublished": template_id,
        "summary": library_summary(
            store.root,
            official_path=store.official_library_path,
            include_official=store.include_official_library,
            include_templates=False,
        ),
    }


@app.patch("/api/library/templates/{template_id}")
def toggle_library_template(template_id: str, request: LibraryToggleRequest):
    updated = set_library_template_enabled(
        store.root,
        template_id,
        request.enabled,
        official_path=store.official_library_path,
        include_official=store.include_official_library,
    )
    if updated is None:
        raise HTTPException(404, f"Template {template_id!r} not found in library")
    return {
        "template": updated,
        "summary": library_summary(
            store.root,
            official_path=store.official_library_path,
            include_official=store.include_official_library,
            include_templates=False,
        ),
    }


@app.delete("/api/library/templates/{template_id}")
def remove_library_template(template_id: str):
    if not delete_library_template(store.root, template_id):
        raise HTTPException(404, f"Template {template_id!r} not found in local library")
    return {
        "deleted": template_id,
        "summary": library_summary(
            store.root,
            official_path=store.official_library_path,
            include_official=store.include_official_library,
            include_templates=False,
        ),
    }


@app.post("/api/library/batches/{batch_id}/toggle")
def toggle_library_batch(batch_id: str, request: LibraryToggleRequest):
    changed = set_library_batch_enabled(
        store.root,
        batch_id,
        request.enabled,
        official_path=store.official_library_path,
        include_official=store.include_official_library,
    )
    if changed == 0:
        raise HTTPException(404, f"No library templates found for batch {batch_id!r}")
    return {
        "batch_id": batch_id,
        "enabled": request.enabled,
        "changed": changed,
        "summary": library_summary(
            store.root,
            official_path=store.official_library_path,
            include_official=store.include_official_library,
            include_templates=False,
        ),
    }


@app.get("/api/library/download")
def download_library(scope: str = "official"):
    if scope == "official":
        off = store.official_library_path or official_library_file()
        if off.is_file():
            return FileResponse(off, filename="micro_template_library.json")
    path = library_file(store.root)
    if not path.is_file():
        raise HTTPException(404, "Library file has not been created yet")
    return FileResponse(path, filename="micro_template_library.json")


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


@app.get("/api/pipeline/status")
def pipeline_status():
    return pipeline_store.environment_status()


@app.put("/api/pipeline/settings")
def update_pipeline_settings(request: PipelineSettingsRequest):
    return pipeline_store.update_settings(ivrit_cookie=request.ivrit_cookie)


@app.get("/api/pipeline/sources")
def list_pipeline_sources():
    return {"sources": pipeline_store.list_corpus_sources()}


@app.post("/api/pipeline/sources")
def save_pipeline_source(request: PipelineCorpusSourceRequest):
    try:
        saved = pipeline_store.save_corpus_source(request.model_dump())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"source": saved, "sources": pipeline_store.list_corpus_sources()}


@app.delete("/api/pipeline/sources/{source_id}")
def delete_pipeline_source(source_id: str):
    if not pipeline_store.delete_corpus_source(source_id):
        raise HTTPException(404, f"Corpus source {source_id!r} not found")
    return {"deleted": source_id, "sources": pipeline_store.list_corpus_sources()}


@app.post("/api/pipeline/sources/{source_id}/search")
def search_pipeline_source(source_id: str, request: PipelineSourceSearchRequest):
    try:
        return pipeline_store.search_corpus_source(
            source_id,
            query=request.query,
            mode=request.mode,
            limit=request.limit,
            context_lines=request.context_lines,
            ignore_case=request.ignore_case,
            start_line=request.start_line,
            batch_id=request.batch_id,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except CorpusSourceError as exc:
        raise HTTPException(502, str(exc)) from exc


@app.get("/api/pipeline/batches")
def list_pipeline_batches():
    return {
        "batches": pipeline_store.list_batches(),
        "ledger": pipeline_store.cost_summary(),
        "tier1_coverage": pipeline_store.tier1_coverage(),
    }


@app.post("/api/pipeline/batches")
def create_pipeline_batch(request: PipelineCreateBatchRequest, http_request: Request):
    server_url = str(http_request.base_url).rstrip("/")
    try:
        return pipeline_store.create_batch(
            target_count=request.target_count,
            template_count=request.template_count,
            seed=request.seed,
            corpus_ratio=request.corpus_ratio,
            notes=request.notes,
            reuse_snippets_from=request.reuse_snippets_from,
            model=request.model,
            variant=request.variant,
            server_url=server_url,
            dispatch_session=request.dispatch_session,
            notify_session_id=request.notify_session_id,
            notify_context=request.notify_context,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/pipeline/batches/{batch_id}")
def get_pipeline_batch(batch_id: str):
    batch = pipeline_store.sync_batch_telemetry(batch_id)
    if batch is None:
        raise HTTPException(404, "Batch not found")
    return batch


@app.post("/api/pipeline/batches/{batch_id}/mine")
def mine_pipeline_batch(batch_id: str):
    try:
        return pipeline_store.run_mine_step(batch_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/pipeline/batches/{batch_id}/templates")
def submit_pipeline_templates(batch_id: str, request: PipelineTemplatesRequest):
    try:
        return pipeline_store.submit_templates(batch_id, request.templates)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/pipeline/batches/{batch_id}/stress-pack")
def get_pipeline_stress_pack(batch_id: str):
    try:
        return pipeline_store.get_stress_pack(batch_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/api/pipeline/batches/{batch_id}/verdicts")
def submit_pipeline_verdicts(batch_id: str, request: PipelineVerdictsRequest):
    try:
        return pipeline_store.submit_verdicts(batch_id, request.verdicts)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/pipeline/batches/{batch_id}/recheck-engine-bugs")
def recheck_pipeline_engine_bugs(batch_id: str):
    try:
        return pipeline_store.recheck_engine_bugs(batch_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/api/pipeline/batches/{batch_id}/finalize")
def finalize_pipeline_batch(batch_id: str):
    try:
        return pipeline_store.finalize_batch(batch_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/pipeline/batches/{batch_id}/fail")
def fail_pipeline_batch(batch_id: str, request: PipelineFailRequest):
    try:
        return pipeline_store.fail_batch(batch_id, request.reason)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/pipeline/batches/{batch_id}/cancel")
def cancel_pipeline_batch(batch_id: str):
    try:
        return pipeline_store.cancel_batch(batch_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

"""FastAPI application: REST + Server-Sent Events API, and the built frontend."""

import asyncio
import json
import logging
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import documents
from .chunker import BlockKind
from .config import get_settings
from .jobs import JobStore, TooManyJobs
from .llm import LLMError, make_llm
from .metrics import TextMetrics, analyze
from .prompts import Intensity
from .rewriter import Rewriter
from .textutils import word_count

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("refiner")

settings = get_settings()
rewriter = Rewriter(make_llm(settings), settings)
store = JobStore(rewriter, settings)


@asynccontextmanager
async def lifespan(_: FastAPI):
    sweeper = asyncio.create_task(store.sweep_forever())
    log.info("Academic Style Refiner ready (model=%s, mock=%s)", settings.model, settings.mock_llm)
    yield
    sweeper.cancel()


app = FastAPI(title="Academic Style Refiner", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def no_store(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        # User text passes through these responses; keep it out of browser and proxy caches.
        response.headers["Cache-Control"] = "no-store"
    return response


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TextIn(BaseModel):
    text: str = Field(min_length=1)


class JobIn(TextIn):
    intensity: Intensity = "moderate"


class BlockOut(BaseModel):
    id: int
    kind: BlockKind
    text: str


class JobOut(BaseModel):
    job_id: str
    blocks: list[BlockOut]


class JobSnapshot(BaseModel):
    job_id: str
    status: str
    intensity: Intensity
    completed: int
    total: int
    blocks: list[BlockOut]
    outputs: dict[int, str]
    warnings: dict[int, list[str]]
    errors: dict[int, str]


class ParagraphIn(BaseModel):
    text: str = Field(min_length=1, max_length=20_000)
    intensity: Intensity = "moderate"
    context_before: str | None = Field(default=None, max_length=20_000)
    context_after: str | None = Field(default=None, max_length=20_000)
    previous: str | None = Field(default=None, max_length=20_000)


class ParagraphOut(BaseModel):
    text: str
    warnings: list[str]


class ExportBlockIn(BaseModel):
    kind: BlockKind
    text: str


class ExportIn(BaseModel):
    format: Literal["txt", "docx", "pdf"]
    title: str = Field(default="", max_length=200)
    blocks: list[ExportBlockIn]


class ExtractOut(BaseModel):
    filename: str
    text: str
    words: int


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


def _check_length(text: str) -> None:
    n = word_count(text)
    if n > settings.max_words:
        raise HTTPException(413, f"The document has {n:,} words; the limit is {settings.max_words:,}.")


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "model": settings.model, "mock": settings.mock_llm, "max_words": settings.max_words}


@app.post("/api/analyze", response_model=TextMetrics)
async def analyze_text(body: TextIn) -> TextMetrics:
    _check_length(body.text)
    return analyze(body.text)


@app.post("/api/extract", response_model=ExtractOut)
async def extract(file: UploadFile = File(...)) -> ExtractOut:
    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(413, f"Files must be under {settings.max_upload_bytes // (1024 * 1024)} MB.")
    try:
        text = documents.extract_text(file.filename or "upload.txt", data)
    except documents.UnsupportedFile as e:
        raise HTTPException(415, str(e)) from e
    _check_length(text)
    return ExtractOut(filename=file.filename or "upload", text=text, words=word_count(text))


@app.post("/api/jobs", response_model=JobOut, status_code=201)
async def create_job(body: JobIn) -> JobOut:
    _check_length(body.text)
    try:
        job = store.create(body.text, body.intensity)
    except TooManyJobs as e:
        raise HTTPException(429, "The server is busy with other documents. Please try again in a minute.") from e
    return JobOut(job_id=job.id, blocks=[BlockOut(id=b.id, kind=b.kind, text=b.text) for b in job.blocks])


@app.get("/api/jobs/{job_id}", response_model=JobSnapshot)
async def get_job(job_id: str) -> JobSnapshot:
    job = store.get(job_id)
    if job is None:
        raise HTTPException(404, "Job not found or expired.")
    return JobSnapshot(
        job_id=job.id,
        status=job.status,
        intensity=job.intensity,
        completed=job.completed,
        total=job.total,
        blocks=[BlockOut(id=b.id, kind=b.kind, text=b.text) for b in job.blocks],
        outputs=job.outputs,
        warnings=job.warnings,
        errors=job.errors,
    )


@app.get("/api/jobs/{job_id}/events")
async def job_events(job_id: str, request: Request) -> StreamingResponse:
    job = store.get(job_id)
    if job is None:
        raise HTTPException(404, "Job not found or expired.")

    async def stream():
        sent = 0
        while True:
            async with job.changed:
                if sent >= len(job.events) and job.status == "running":
                    try:
                        await asyncio.wait_for(job.changed.wait(), timeout=15)
                    except TimeoutError:
                        pass
                pending = job.events[sent:]
            if await request.is_disconnected():
                return
            if not pending:
                if job.status != "running":
                    return
                yield ": keep-alive\n\n"
                continue
            for event in pending:
                yield f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"
            sent += len(pending)
            if pending[-1]["event"] == "done":
                return

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@app.delete("/api/jobs/{job_id}", status_code=204)
async def delete_job(job_id: str) -> Response:
    await store.delete(job_id)
    return Response(status_code=204)


@app.post("/api/refine/paragraph", response_model=ParagraphOut)
async def refine_paragraph(body: ParagraphIn) -> ParagraphOut:
    try:
        result = await rewriter.refine(
            body.text, body.intensity, body.context_before, body.context_after, previous=body.previous
        )
    except LLMError as e:
        raise HTTPException(502, str(e)) from e
    return ParagraphOut(text=result.text, warnings=result.warnings)


_MEDIA_TYPES = {
    "txt": "text/plain; charset=utf-8",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
}


@app.post("/api/export")
async def export(body: ExportIn) -> Response:
    blocks = [(b.kind, b.text) for b in body.blocks]
    _check_length("\n\n".join(t for _, t in blocks))
    if body.format == "txt":
        data = documents.to_txt(blocks)
    elif body.format == "docx":
        data = await asyncio.to_thread(documents.to_docx, body.title, blocks)
    else:
        data = await asyncio.to_thread(documents.to_pdf, body.title, blocks)
    stem = re.sub(r"[^A-Za-z0-9_-]+", "-", body.title).strip("-")[:60] or "refined-document"
    return Response(
        content=data,
        media_type=_MEDIA_TYPES[body.format],
        headers={"Content-Disposition": f'attachment; filename="{stem}.{body.format}"'},
    )


# ---------------------------------------------------------------------------
# Frontend (production build), if present
# ---------------------------------------------------------------------------

_static = Path(settings.static_dir)
if _static.is_dir() and (_static / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=_static / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str) -> FileResponse:
        candidate = (_static / path).resolve()
        if path and candidate.is_file() and _static.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(_static / "index.html")

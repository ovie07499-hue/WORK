"""In-memory job store. Nothing is written to disk; jobs are purged after a TTL."""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from .chunker import Block, split_document
from .config import Settings
from .llm import LLMError
from .metrics import analyze
from .prompts import Intensity
from .rewriter import Rewriter

log = logging.getLogger(__name__)

JobStatus = Literal["running", "done", "failed", "cancelled"]


class TooManyJobs(Exception):
    pass


@dataclass
class Job:
    id: str
    intensity: Intensity
    blocks: list[Block]
    status: JobStatus = "running"
    outputs: dict[int, str] = field(default_factory=dict)
    warnings: dict[int, list[str]] = field(default_factory=dict)
    errors: dict[int, str] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.monotonic)
    finished_at: float | None = None
    task: asyncio.Task | None = None
    changed: asyncio.Condition = field(default_factory=asyncio.Condition)

    @property
    def total(self) -> int:
        return sum(b.rewritable for b in self.blocks)

    @property
    def completed(self) -> int:
        return len(self.outputs) + len(self.errors)

    def output_text(self) -> str:
        return "\n\n".join(self.outputs.get(b.id, b.text) for b in self.blocks)

    def source_text(self) -> str:
        return "\n\n".join(b.text for b in self.blocks)

    async def emit(self, event: str, **data: Any) -> None:
        async with self.changed:
            self.events.append({"event": event, "data": data})
            self.changed.notify_all()


class JobStore:
    def __init__(self, rewriter: Rewriter, settings: Settings):
        self._rewriter = rewriter
        self._settings = settings
        self._jobs: dict[str, Job] = {}

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def create(self, text: str, intensity: Intensity) -> Job:
        running = sum(j.status == "running" for j in self._jobs.values())
        if running >= self._settings.max_active_jobs:
            raise TooManyJobs()
        job = Job(id=uuid.uuid4().hex, intensity=intensity, blocks=split_document(text))
        self._jobs[job.id] = job
        job.task = asyncio.create_task(self._run(job))
        return job

    async def delete(self, job_id: str) -> bool:
        job = self._jobs.pop(job_id, None)
        if job is None:
            return False
        if job.task and not job.task.done():
            job.task.cancel()
        return True

    def purge_expired(self) -> None:
        now = time.monotonic()
        ttl = self._settings.job_ttl_seconds
        for job_id, job in list(self._jobs.items()):
            # Running jobs get a generous hard cap; finished jobs expire after the TTL.
            reference = job.finished_at if job.finished_at is not None else job.created_at + ttl
            if now - reference > ttl:
                if job.task and not job.task.done():
                    job.task.cancel()
                del self._jobs[job_id]

    async def sweep_forever(self) -> None:
        while True:
            await asyncio.sleep(60)
            self.purge_expired()

    async def _run(self, job: Job) -> None:
        semaphore = asyncio.Semaphore(self._settings.chunk_concurrency)
        blocks = job.blocks
        await job.emit("progress", completed=0, total=job.total)

        async def process(index: int) -> None:
            block = blocks[index]
            before = blocks[index - 1].text if index > 0 else None
            after = blocks[index + 1].text if index + 1 < len(blocks) else None

            async def on_stage(stage: str) -> None:
                await job.emit("stage", block_id=block.id, stage=stage)

            async with semaphore:
                try:
                    result = await self._rewriter.refine(block.text, job.intensity, before, after, on_stage=on_stage)
                except Exception as e:
                    if isinstance(e, LLMError):
                        message = str(e)
                    else:
                        log.exception("Block %s of job %s failed", block.id, job.id)
                        message = "Internal error while rewriting this paragraph."
                    job.errors[block.id] = message
                    await job.emit("block_error", block_id=block.id, message=message)
                else:
                    job.outputs[block.id] = result.text
                    job.warnings[block.id] = result.warnings
                    await job.emit("block", block_id=block.id, text=result.text, warnings=result.warnings)
            await job.emit("progress", completed=job.completed, total=job.total)

        try:
            await asyncio.gather(*(process(i) for i, b in enumerate(blocks) if b.rewritable))
            job.status = "done" if len(job.errors) < max(1, job.total) else "failed"
            await job.emit(
                "done",
                status=job.status,
                metrics_before=analyze(job.source_text()).model_dump(),
                metrics_after=analyze(job.output_text()).model_dump(),
            )
        except asyncio.CancelledError:
            job.status = "cancelled"
            raise
        except Exception:
            log.exception("Job %s crashed", job.id)
            job.status = "failed"
            await job.emit("done", status="failed", message="Internal error while processing the document.")
        finally:
            job.finished_at = time.monotonic()

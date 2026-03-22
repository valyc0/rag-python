from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from contextlib import suppress
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from app.config import Settings, load_settings
from app.logging_config import configure_logging, get_logger
from app.models import HealthResponse, IngestResponse, IngestStatusResponse, QueryDebugResponse, QueryRequest, QueryResponse
from app.service import RagService
from app.watcher import DocumentWatcher

settings = load_settings()
configure_logging(settings.app.log_level)
logger = get_logger(__name__)
service = RagService(settings)
watcher: DocumentWatcher | None = None
startup_rescan_task: asyncio.Task[None] | None = None


async def _run_startup_rescan() -> None:
    try:
        response = await service.rescan_documents()
        logger.info(
            "Initial document rescan completed: scanned=%s indexed=%s removed=%s skipped=%s chunks=%s",
            response.scanned_files,
            response.indexed_files,
            response.removed_files,
            response.skipped_files,
            response.chunks_written,
        )
    except Exception:
        logger.exception("Initial document rescan failed")


@asynccontextmanager
async def lifespan(_: FastAPI):
    global startup_rescan_task, watcher
    startup_rescan_task = asyncio.create_task(_run_startup_rescan())
    if settings.watch.enabled:
        watcher = DocumentWatcher(service, settings.documents.path, settings.watch.debounce_seconds)
        watcher.start(asyncio.get_running_loop())
    try:
        yield
    finally:
        if startup_rescan_task and not startup_rescan_task.done():
            startup_rescan_task.cancel()
            with suppress(asyncio.CancelledError):
                await startup_rescan_task
        if watcher:
            watcher.stop()


app = FastAPI(title="RAG Python Engine", version="0.1.0", lifespan=lifespan)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="starting" if startup_rescan_task and not startup_rescan_task.done() else "ok",
        llm_model=settings.ollama.llm_model,
        embedding_model=settings.ollama.embedding_model,
        documents_path=settings.documents.path,
    )


@app.get("/documents")
async def documents() -> list[dict[str, Any]]:
    return service.list_documents()


@app.post("/ingest/rescan", response_model=IngestResponse)
async def rescan() -> IngestResponse:
    return await service.rescan_documents()


@app.get("/ingest/status", response_model=IngestStatusResponse)
async def ingest_status() -> IngestStatusResponse:
    startup_indexing = bool(startup_rescan_task and not startup_rescan_task.done())
    return service.get_ingest_status(startup_indexing=startup_indexing)


@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest) -> QueryResponse:
    try:
        return await service.answer_question(
            request.question,
            top_k=request.top_k,
            metadata_filter=request.metadata_filter,
            use_cache=request.use_cache,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/query/debug", response_model=QueryDebugResponse)
async def query_debug(request: QueryRequest) -> QueryDebugResponse:
    try:
        return await service.debug_question(
            request.question,
            top_k=request.top_k,
            metadata_filter=request.metadata_filter,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/query/stream")
async def query_stream(request: QueryRequest) -> StreamingResponse:
    _, stream = await service.stream_answer(request.question, request.metadata_filter)

    async def generator():
        async for line in stream:
            yield f"event: token\ndata: {line}\n\n"

    return StreamingResponse(generator(), media_type="text/event-stream")


def get_settings() -> Settings:
    return settings

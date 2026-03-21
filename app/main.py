from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from app.config import Settings, load_settings
from app.logging_config import configure_logging
from app.models import HealthResponse, IngestResponse, QueryDebugResponse, QueryRequest, QueryResponse
from app.service import RagService
from app.watcher import DocumentWatcher

settings = load_settings()
configure_logging(settings.app.log_level)
service = RagService(settings)
watcher: DocumentWatcher | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global watcher
    await service.rescan_documents()
    if settings.watch.enabled:
        watcher = DocumentWatcher(service, settings.documents.path, settings.watch.debounce_seconds)
        watcher.start(asyncio.get_running_loop())
    try:
        yield
    finally:
        if watcher:
            watcher.stop()


app = FastAPI(title="RAG Python Engine", version="0.1.0", lifespan=lifespan)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
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

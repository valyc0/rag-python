from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field


@dataclass(slots=True)
class DocumentChunk:
    chunk_id: str
    text: str
    source_path: str
    file_name: str
    page_number: int
    chunk_index: int
    content_hash: str


@dataclass(slots=True)
class SearchHit:
    chunk_id: str
    text: str
    metadata: dict[str, Any]
    score: float
    dense_rank: int | None = None
    sparse_rank: int | None = None


class QueryRequest(BaseModel):
    question: str = Field(min_length=3)
    top_k: int | None = None
    metadata_filter: dict[str, Any] | None = None
    use_cache: bool = True


class SourceChunk(BaseModel):
    chunk_id: str
    source_path: str
    file_name: str
    page_number: int
    score: float
    excerpt: str


class QueryResponse(BaseModel):
    answer: str
    cached: bool
    context_chars: int
    prompt_chars: int
    sources: list[SourceChunk]


class QueryDebugResponse(QueryResponse):
    prompt: str
    context: str
    selected_chunks: list[str]
    selected_chunk_count: int


class IngestResponse(BaseModel):
    scanned_files: int
    indexed_files: int
    removed_files: int
    skipped_files: int
    chunks_written: int


class IngestStatusResponse(BaseModel):
    status: str
    startup_indexing: bool
    ingest_in_progress: bool
    current_file: str | None
    pending_files: list[str]
    pending_count: int
    last_completed_at: str | None
    last_result: IngestResponse | None
    last_error: str | None


class HealthResponse(BaseModel):
    status: str
    llm_model: str
    embedding_model: str
    documents_path: str

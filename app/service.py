from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from diskcache import Cache

from app.chunking import Chunker
from app.config import Settings
from app.logging_config import get_logger
from app.models import IngestResponse, IngestStatusResponse, QueryDebugResponse, QueryResponse, SearchHit, SourceChunk
from app.ollama_client import OllamaClient
from app.parsers import parse_file
from app.prompting import build_prompt
from app.repository import MetadataRepository
from app.retrieval import HybridRetriever
from app.utils import safe_excerpt, sha256_file, sha256_text
from app.vector_store import VectorStore

logger = get_logger(__name__)
FALLBACK_ANSWER = "Non lo so in base ai documenti forniti."


class RagService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = MetadataRepository(
            sqlite_path=settings.storage.sqlite_path,
            metadata_backend=settings.storage.metadata_backend,
            postgres_dsn=settings.storage.postgres_dsn,
        )
        self.vector_store = VectorStore(
            persist_path=settings.storage.chroma_path,
            collection_name=settings.storage.qdrant_collection_name,
            vector_backend=settings.storage.vector_backend,
            qdrant_url=settings.storage.qdrant_url,
            qdrant_api_key=settings.storage.qdrant_api_key,
            qdrant_timeout_seconds=settings.storage.qdrant_timeout_seconds,
        )
        self.chunker = Chunker(
            settings.chunking.chunk_size_tokens,
            settings.chunking.overlap_tokens,
            settings.chunking.min_chunk_tokens,
        )
        self.client = OllamaClient(settings.ollama.base_url, settings.ollama.timeout_seconds)
        self.retriever = HybridRetriever(
            self.repository,
            self.vector_store,
            settings.retrieval.hybrid_alpha,
            settings.retrieval.rerank,
        )
        self.cache = Cache(settings.storage.cache_path)
        self._ingest_lock = asyncio.Lock()
        self._ingest_in_progress = False
        self._ingest_current_file: str | None = None
        self._ingest_pending_files: list[str] = []
        self._last_ingest_completed_at: str | None = None
        self._last_ingest_result: IngestResponse | None = None
        self._last_ingest_error: str | None = None

    async def rescan_documents(self) -> IngestResponse:
        async with self._ingest_lock:
            self._ingest_in_progress = True
            self._ingest_current_file = None
            self._ingest_pending_files = []
            self._last_ingest_error = None
            try:
                documents_dir = Path(self.settings.documents.path)
                supported = set(self.settings.documents.supported_extensions)
                indexed_files = 0
                removed_files = 0
                skipped_files = 0
                chunks_written = 0

                discovered_files = sorted(
                    path for path in documents_dir.rglob("*") if path.is_file() and path.suffix.lower() in supported
                )
                discovered_paths = {str(path) for path in discovered_files}
                existing_records = {item["source_path"]: item for item in self.repository.list_files()}
                existing_paths = set(existing_records)

                planned_files: list[tuple[Path, str]] = []
                for path in discovered_files:
                    file_hash = sha256_file(path)
                    record = existing_records.get(str(path))
                    if record and record["file_hash"] == file_hash:
                        skipped_files += 1
                        continue
                    planned_files.append((path, file_hash))

                self._ingest_pending_files = [str(path) for path, _ in planned_files]

                for removed_path in sorted(existing_paths - discovered_paths):
                    logger.info("Removing deleted file from index: %s", removed_path)
                    self.vector_store.delete_by_source(removed_path)
                    self.repository.delete_file(removed_path)
                    removed_files += 1

                for index, (path, file_hash) in enumerate(planned_files):
                    self._ingest_current_file = str(path)
                    self._ingest_pending_files = [str(item[0]) for item in planned_files[index + 1 :]]
                    logger.info("Indexing file: %s", path)
                    pages = parse_file(path)
                    chunks = self.chunker.chunk_pages(path, pages)
                    if not chunks:
                        skipped_files += 1
                        continue

                    texts = [chunk.text for chunk in chunks]
                    embeddings = await self._embed_in_batches(texts, batch_size=16)
                    self.vector_store.delete_by_source(str(path))
                    self.vector_store.upsert_chunks(chunks, embeddings)
                    self.repository.replace_chunks_for_file(str(path), chunks)
                    self.repository.upsert_file(
                        str(path),
                        file_hash,
                        path.stat().st_mtime,
                        datetime.now(UTC).isoformat(),
                    )
                    indexed_files += 1
                    chunks_written += len(chunks)

                response = IngestResponse(
                    scanned_files=len(discovered_files),
                    indexed_files=indexed_files,
                    removed_files=removed_files,
                    skipped_files=skipped_files,
                    chunks_written=chunks_written,
                )
                self._last_ingest_result = response
                self._last_ingest_completed_at = datetime.now(UTC).isoformat()
                return response
            except Exception as exc:
                self._last_ingest_error = str(exc)
                raise
            finally:
                self._ingest_in_progress = False
                self._ingest_current_file = None
                self._ingest_pending_files = []

    async def answer_question(
        self,
        question: str,
        *,
        top_k: int | None = None,
        metadata_filter: dict[str, Any] | None = None,
        use_cache: bool = True,
    ) -> QueryResponse:
        cache_key = sha256_text(f"{question}|{top_k}|{metadata_filter}")
        if use_cache and cache_key in self.cache:
            cached_response = self.cache[cache_key]
            return QueryResponse.model_validate({**cached_response, "cached": True})

        payload = await self._run_query(question, top_k=top_k, metadata_filter=metadata_filter)
        response = QueryResponse(
            answer=payload["answer"],
            cached=False,
            context_chars=payload["context_chars"],
            prompt_chars=payload["prompt_chars"],
            sources=payload["sources"],
        )
        self.cache.set(cache_key, response.model_dump(), expire=3600)
        return response

    async def debug_question(
        self,
        question: str,
        *,
        top_k: int | None = None,
        metadata_filter: dict[str, Any] | None = None,
    ) -> QueryDebugResponse:
        payload = await self._run_query(question, top_k=top_k, metadata_filter=metadata_filter)
        return QueryDebugResponse(
            answer=payload["answer"],
            cached=False,
            context_chars=payload["context_chars"],
            prompt_chars=payload["prompt_chars"],
            sources=payload["sources"],
            prompt=payload["prompt"],
            context=payload["context"],
            selected_chunks=payload["selected_chunks"],
            selected_chunk_count=payload["selected_chunk_count"],
        )

    async def _run_query(
        self,
        question: str,
        *,
        top_k: int | None = None,
        metadata_filter: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        query_embedding = (await self.client.embed(self.settings.ollama.embedding_model, [question]))[0]
        hits = self.retriever.search(
            question,
            query_embedding,
            top_k or self.settings.retrieval.top_k,
            self.settings.retrieval.dense_k,
            self.settings.retrieval.bm25_k,
            metadata_filter,
        )
        selected_hits = self._compress_hits(hits, self.settings.context.max_chars)
        context, prompt = build_prompt(question, selected_hits)
        answer = await self.client.generate(
            model=self.settings.ollama.llm_model,
            prompt=prompt,
            temperature=self.settings.ollama.temperature,
            top_p=self.settings.ollama.top_p,
            num_predict=self.settings.ollama.num_predict,
        )
        if self._should_retry_extractive(answer, selected_hits, question):
            focused_hits = selected_hits[:2]
            context, prompt = build_prompt(question, focused_hits, extractive=True)
            retry_answer = await self.client.generate(
                model=self.settings.ollama.llm_model,
                prompt=prompt,
                temperature=0.0,
                top_p=self.settings.ollama.top_p,
                num_predict=min(160, self.settings.ollama.num_predict),
            )
            if retry_answer.strip():
                answer = retry_answer.strip()
                selected_hits = focused_hits

        extractive_fallback = self._build_extractive_fallback(question, selected_hits, answer)
        if extractive_fallback:
            answer = extractive_fallback

        return {
            "answer": answer,
            "context": context,
            "prompt": prompt,
            "context_chars": len(context),
            "prompt_chars": len(prompt),
            "sources": self._build_sources(selected_hits),
            "selected_chunks": [hit.text for hit in selected_hits],
            "selected_chunk_count": len(selected_hits),
        }

    async def stream_answer(self, question: str, metadata_filter: dict[str, Any] | None = None) -> tuple[str, Any]:
        query_embedding = (await self.client.embed(self.settings.ollama.embedding_model, [question]))[0]
        hits = self.retriever.search(
            question,
            query_embedding,
            self.settings.retrieval.top_k,
            self.settings.retrieval.dense_k,
            self.settings.retrieval.bm25_k,
            metadata_filter,
        )
        selected_hits = self._compress_hits(hits, self.settings.context.max_chars)
        _, prompt = build_prompt(question, selected_hits)
        stream = self.client.stream_generate(
            model=self.settings.ollama.llm_model,
            prompt=prompt,
            temperature=self.settings.ollama.temperature,
            top_p=self.settings.ollama.top_p,
            num_predict=self.settings.ollama.num_predict,
        )
        return prompt, stream

    def _build_sources(self, hits: list[SearchHit]) -> list[SourceChunk]:
        return [
            SourceChunk(
                chunk_id=hit.chunk_id,
                source_path=hit.metadata["source_path"],
                file_name=hit.metadata["file_name"],
                page_number=int(hit.metadata["page_number"]),
                score=round(hit.score, 4),
                excerpt=safe_excerpt(hit.text),
            )
            for hit in hits
        ]

    def _should_retry_extractive(self, answer: str, hits: list[SearchHit], question: str) -> bool:
        normalized_answer = answer.strip()
        if not hits:
            return False
        if normalized_answer != FALLBACK_ANSWER and not normalized_answer.lower().startswith("non so"):
            return False
        question_terms = {token for token in re.findall(r"\w+", question.lower()) if len(token) > 2}
        candidate_text = " ".join(hit.text.lower() for hit in hits[:2])
        has_numeric_signal = bool(re.search(r"\d+\s*(?:°c|c|km|kg|v|bar|%)", candidate_text))
        has_term_overlap = any(term in candidate_text for term in question_terms)
        return has_numeric_signal or has_term_overlap

    def _build_extractive_fallback(self, question: str, hits: list[SearchHit], answer: str) -> str | None:
        if not hits:
            return None
        if not answer.strip().lower().startswith("non so"):
            return None

        question_terms = {token for token in re.findall(r"\w+", question.lower()) if len(token) > 2}
        best_sentence: str | None = None
        best_hit: SearchHit | None = None
        best_score = 0

        for hit in hits[:2]:
            sentences = [segment.strip() for segment in re.split(r"(?<=[.!?])\s+", hit.text) if segment.strip()]
            for sentence in sentences:
                sentence_lower = sentence.lower()
                overlap = sum(1 for term in question_terms if term in sentence_lower)
                numeric_bonus = 2 if re.search(r"\d+\s*(?:°c|c|km|kg|v|bar|%)", sentence_lower) else 0
                score = overlap + numeric_bonus
                if score > best_score:
                    best_score = score
                    best_sentence = sentence
                    best_hit = hit

        if best_sentence is None or best_hit is None or best_score < 2:
            return None

        return (
            f"{best_sentence.strip()} "
            f"Fonte: {best_hit.metadata['file_name']}, pagina {best_hit.metadata['page_number']}."
        )

    async def _embed_in_batches(self, texts: list[str], batch_size: int) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            embeddings.extend(await self.client.embed(self.settings.ollama.embedding_model, batch))
        return embeddings

    def _compress_hits(self, hits: list[SearchHit], max_chars: int) -> list[SearchHit]:
        selected: list[SearchHit] = []
        total_chars = 0
        seen_hashes: set[str] = set()
        for hit in hits:
            content_hash = str(hit.metadata.get("content_hash", hit.chunk_id))
            if content_hash in seen_hashes:
                continue
            projected = total_chars + len(hit.text)
            if selected and projected > max_chars:
                break
            selected.append(hit)
            seen_hashes.add(content_hash)
            total_chars = projected
        return selected or hits[:1]

    def list_documents(self) -> list[dict[str, Any]]:
        return self.repository.list_files()

    def get_ingest_status(self, *, startup_indexing: bool) -> IngestStatusResponse:
        return IngestStatusResponse(
            status="indexing" if self._ingest_in_progress or startup_indexing else "idle",
            startup_indexing=startup_indexing,
            ingest_in_progress=self._ingest_in_progress,
            current_file=self._ingest_current_file,
            pending_files=list(self._ingest_pending_files),
            pending_count=len(self._ingest_pending_files),
            last_completed_at=self._last_ingest_completed_at,
            last_result=self._last_ingest_result,
            last_error=self._last_ingest_error,
        )

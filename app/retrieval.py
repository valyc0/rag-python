from __future__ import annotations

from collections import defaultdict
from typing import Any

from rank_bm25 import BM25Okapi

from app.models import SearchHit
from app.repository import MetadataRepository
from app.vector_store import VectorStore


class HybridRetriever:
    def __init__(self, repository: MetadataRepository, vector_store: VectorStore, alpha: float, rerank: bool) -> None:
        self.repository = repository
        self.vector_store = vector_store
        self.alpha = alpha
        self.rerank = rerank

    def _tokenize(self, text: str) -> list[str]:
        return [token for token in text.lower().split() if token]

    def _bm25_search(self, query: str, top_k: int, metadata_filter: dict[str, Any] | None = None) -> list[SearchHit]:
        chunks = self.repository.list_chunks(metadata_filter)
        if not chunks:
            return []
        corpus = [self._tokenize(chunk["text"]) for chunk in chunks]
        model = BM25Okapi(corpus)
        scores = model.get_scores(self._tokenize(query))
        ranked_indices = sorted(range(len(scores)), key=lambda index: scores[index], reverse=True)[:top_k]
        max_score = max(scores) if len(scores) else 0.0
        results: list[SearchHit] = []
        for rank, index in enumerate(ranked_indices, start=1):
            chunk = chunks[index]
            score = float(scores[index]) / max_score if max_score else 0.0
            results.append(
                SearchHit(
                    chunk_id=chunk["chunk_id"],
                    text=chunk["text"],
                    metadata={
                        "source_path": chunk["source_path"],
                        "file_name": chunk["file_name"],
                        "page_number": chunk["page_number"],
                        "chunk_index": chunk["chunk_index"],
                        "content_hash": chunk["content_hash"],
                    },
                    score=score,
                    sparse_rank=rank,
                )
            )
        return results

    def search(
        self,
        query: str,
        query_embedding: list[float],
        top_k: int,
        dense_k: int,
        bm25_k: int,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[SearchHit]:
        dense_hits = self.vector_store.search(query_embedding, dense_k, metadata_filter)
        sparse_hits = self._bm25_search(query, bm25_k, metadata_filter)

        fused: dict[str, SearchHit] = {}
        score_map: defaultdict[str, float] = defaultdict(float)

        for hit in dense_hits:
            fused[hit.chunk_id] = hit
            score_map[hit.chunk_id] += self.alpha * hit.score + (1.0 / (60 + (hit.dense_rank or 1)))
        for hit in sparse_hits:
            existing = fused.get(hit.chunk_id)
            if existing is None:
                fused[hit.chunk_id] = hit
            else:
                existing.sparse_rank = hit.sparse_rank
                existing.score = max(existing.score, hit.score)
            score_map[hit.chunk_id] += (1.0 - self.alpha) * hit.score + (1.0 / (60 + (hit.sparse_rank or 1)))

        ranked = sorted(
            fused.values(),
            key=lambda item: score_map[item.chunk_id] + (self._rerank_bonus(query, item.text) if self.rerank else 0.0),
            reverse=True,
        )
        for item in ranked:
            item.score = score_map[item.chunk_id]
        return ranked[:top_k]

    def _rerank_bonus(self, query: str, text: str) -> float:
        query_terms = set(self._tokenize(query))
        text_terms = set(self._tokenize(text))
        if not query_terms:
            return 0.0
        overlap = len(query_terms.intersection(text_terms))
        return overlap / len(query_terms)

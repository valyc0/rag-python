from __future__ import annotations

from typing import Any

import chromadb

from app.models import DocumentChunk, SearchHit


class VectorStore:
    def __init__(self, persist_path: str, collection_name: str = "rag_chunks") -> None:
        self.client = chromadb.PersistentClient(path=persist_path)
        self.collection = self.client.get_or_create_collection(name=collection_name)

    def upsert_chunks(self, chunks: list[DocumentChunk], embeddings: list[list[float]]) -> None:
        if not chunks:
            return
        self.collection.upsert(
            ids=[chunk.chunk_id for chunk in chunks],
            embeddings=embeddings,
            documents=[chunk.text for chunk in chunks],
            metadatas=[
                {
                    "source_path": chunk.source_path,
                    "file_name": chunk.file_name,
                    "page_number": chunk.page_number,
                    "chunk_index": chunk.chunk_index,
                    "content_hash": chunk.content_hash,
                }
                for chunk in chunks
            ],
        )

    def delete_by_source(self, source_path: str) -> None:
        self.collection.delete(where={"source_path": source_path})

    def search(
        self,
        query_embedding: list[float],
        top_k: int,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[SearchHit]:
        payload = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=metadata_filter or None,
            include=["documents", "metadatas", "distances"],
        )
        ids = payload.get("ids", [[]])[0]
        documents = payload.get("documents", [[]])[0]
        metadatas = payload.get("metadatas", [[]])[0]
        distances = payload.get("distances", [[]])[0]
        results: list[SearchHit] = []
        for rank, chunk_id in enumerate(ids, start=1):
            distance = float(distances[rank - 1]) if rank - 1 < len(distances) else 1.0
            score = 1.0 / (1.0 + distance)
            results.append(
                SearchHit(
                    chunk_id=chunk_id,
                    text=documents[rank - 1],
                    metadata=metadatas[rank - 1],
                    score=score,
                    dense_rank=rank,
                )
            )
        return results

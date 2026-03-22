from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from uuid import NAMESPACE_URL, uuid5

import chromadb
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, FieldCondition, Filter, MatchValue, PointStruct, VectorParams

from app.models import DocumentChunk, SearchHit


class BaseVectorStore(ABC):
    @abstractmethod
    def upsert_chunks(self, chunks: list[DocumentChunk], embeddings: list[list[float]]) -> None:
        raise NotImplementedError

    @abstractmethod
    def delete_by_source(self, source_path: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def search(
        self,
        query_embedding: list[float],
        top_k: int,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[SearchHit]:
        raise NotImplementedError


class ChromaVectorStore(BaseVectorStore):
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


class QdrantVectorStore(BaseVectorStore):
    def __init__(
        self,
        url: str,
        collection_name: str = "rag_chunks",
        api_key: str | None = None,
        timeout_seconds: int = 30,
    ) -> None:
        self.collection_name = collection_name
        self.client = QdrantClient(
            url=url,
            api_key=api_key or None,
            timeout=timeout_seconds,
            check_compatibility=False,
        )

    def upsert_chunks(self, chunks: list[DocumentChunk], embeddings: list[list[float]]) -> None:
        if not chunks:
            return
        self._ensure_collection(len(embeddings[0]))
        points = [
            PointStruct(
                id=self._point_id(chunk.chunk_id),
                vector=embedding,
                payload={
                    "chunk_id": chunk.chunk_id,
                    "text": chunk.text,
                    "source_path": chunk.source_path,
                    "file_name": chunk.file_name,
                    "page_number": chunk.page_number,
                    "chunk_index": chunk.chunk_index,
                    "content_hash": chunk.content_hash,
                },
            )
            for chunk, embedding in zip(chunks, embeddings, strict=True)
        ]
        self.client.upsert(collection_name=self.collection_name, points=points, wait=True)

    def delete_by_source(self, source_path: str) -> None:
        if not self._collection_exists():
            return
        selector = Filter(must=[FieldCondition(key="source_path", match=MatchValue(value=source_path))])
        self.client.delete(collection_name=self.collection_name, points_selector=selector, wait=True)

    def search(
        self,
        query_embedding: list[float],
        top_k: int,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[SearchHit]:
        if not self._collection_exists():
            return []
        query_filter = self._build_filter(metadata_filter)
        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_embedding,
            limit=top_k,
            query_filter=query_filter,
            with_payload=True,
            with_vectors=False,
        )
        matches = response.points
        results: list[SearchHit] = []
        for rank, point in enumerate(matches, start=1):
            payload = dict(point.payload or {})
            chunk_id = str(payload.pop("chunk_id", point.id))
            text = str(payload.pop("text", ""))
            results.append(
                SearchHit(
                    chunk_id=chunk_id,
                    text=text,
                    metadata=payload,
                    score=float(point.score),
                    dense_rank=rank,
                )
            )
        return results

    def _ensure_collection(self, vector_size: int) -> None:
        if self._collection_exists():
            return
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )

    def _collection_exists(self) -> bool:
        try:
            self.client.get_collection(self.collection_name)
            return True
        except Exception:
            return False

    def _build_filter(self, metadata_filter: dict[str, Any] | None) -> Filter | None:
        if not metadata_filter:
            return None
        must: list[FieldCondition] = []
        for key, value in metadata_filter.items():
            must.append(FieldCondition(key=key, match=MatchValue(value=value)))
        return Filter(must=must)

    def _point_id(self, chunk_id: str) -> str:
        return str(uuid5(NAMESPACE_URL, chunk_id))


class VectorStore:
    def __init__(
        self,
        persist_path: str,
        collection_name: str = "rag_chunks",
        vector_backend: str = "chroma",
        qdrant_url: str = "http://qdrant:6333",
        qdrant_api_key: str = "",
        qdrant_timeout_seconds: int = 30,
    ) -> None:
        backend = vector_backend.lower()
        if backend == "qdrant":
            self._store: BaseVectorStore = QdrantVectorStore(
                url=qdrant_url,
                collection_name=collection_name,
                api_key=qdrant_api_key,
                timeout_seconds=qdrant_timeout_seconds,
            )
        else:
            self._store = ChromaVectorStore(persist_path=persist_path, collection_name=collection_name)

    def __getattr__(self, item: str) -> Any:
        return getattr(self._store, item)

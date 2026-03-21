from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from app.models import DocumentChunk


class MetadataRepository:
    def __init__(self, sqlite_path: str) -> None:
        self.path = Path(sqlite_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self._initialize()

    def _initialize(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS files (
                source_path TEXT PRIMARY KEY,
                file_hash TEXT NOT NULL,
                modified_at REAL NOT NULL,
                indexed_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id TEXT PRIMARY KEY,
                source_path TEXT NOT NULL,
                file_name TEXT NOT NULL,
                page_number INTEGER NOT NULL,
                chunk_index INTEGER NOT NULL,
                content_hash TEXT NOT NULL,
                text TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_chunks_source_path ON chunks(source_path);
            """
        )
        self.connection.commit()

    def get_file(self, source_path: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT source_path, file_hash, modified_at, indexed_at FROM files WHERE source_path = ?",
            (source_path,),
        ).fetchone()
        return dict(row) if row else None

    def upsert_file(self, source_path: str, file_hash: str, modified_at: float, indexed_at: str) -> None:
        self.connection.execute(
            """
            INSERT INTO files(source_path, file_hash, modified_at, indexed_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(source_path)
            DO UPDATE SET file_hash = excluded.file_hash,
                          modified_at = excluded.modified_at,
                          indexed_at = excluded.indexed_at
            """,
            (source_path, file_hash, modified_at, indexed_at),
        )
        self.connection.commit()

    def replace_chunks_for_file(self, source_path: str, chunks: list[DocumentChunk]) -> None:
        self.connection.execute("DELETE FROM chunks WHERE source_path = ?", (source_path,))
        self.connection.executemany(
            """
            INSERT INTO chunks(chunk_id, source_path, file_name, page_number, chunk_index, content_hash, text)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    chunk.chunk_id,
                    chunk.source_path,
                    chunk.file_name,
                    chunk.page_number,
                    chunk.chunk_index,
                    chunk.content_hash,
                    chunk.text,
                )
                for chunk in chunks
            ],
        )
        self.connection.commit()

    def delete_file(self, source_path: str) -> None:
        self.connection.execute("DELETE FROM files WHERE source_path = ?", (source_path,))
        self.connection.execute("DELETE FROM chunks WHERE source_path = ?", (source_path,))
        self.connection.commit()

    def list_files(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT source_path, file_hash, modified_at, indexed_at FROM files ORDER BY source_path"
        ).fetchall()
        return [dict(row) for row in rows]

    def list_chunks(self, metadata_filter: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        query = "SELECT chunk_id, source_path, file_name, page_number, chunk_index, content_hash, text FROM chunks"
        params: list[Any] = []
        where_clauses: list[str] = []
        if metadata_filter:
            if "source_path" in metadata_filter:
                where_clauses.append("source_path = ?")
                params.append(metadata_filter["source_path"])
            if "file_name" in metadata_filter:
                where_clauses.append("file_name = ?")
                params.append(metadata_filter["file_name"])
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        query += " ORDER BY source_path, page_number, chunk_index"
        rows = self.connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def close(self) -> None:
        self.connection.close()

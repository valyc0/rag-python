from __future__ import annotations

from abc import ABC, abstractmethod
import sqlite3
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from app.models import DocumentChunk


class BaseMetadataRepository(ABC):
    @abstractmethod
    def get_file(self, source_path: str) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    def upsert_file(self, source_path: str, file_hash: str, modified_at: float, indexed_at: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def replace_chunks_for_file(self, source_path: str, chunks: list[DocumentChunk]) -> None:
        raise NotImplementedError

    @abstractmethod
    def delete_file(self, source_path: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_files(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def list_chunks(self, metadata_filter: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError


class SqliteMetadataRepository(BaseMetadataRepository):
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


class PostgresMetadataRepository(BaseMetadataRepository):
    def __init__(self, postgres_dsn: str) -> None:
        self.connection = psycopg.connect(postgres_dsn, row_factory=dict_row)
        self._initialize()

    def _initialize(self) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS files (
                    source_path TEXT PRIMARY KEY,
                    file_hash TEXT NOT NULL,
                    modified_at DOUBLE PRECISION NOT NULL,
                    indexed_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS chunks (
                    chunk_id TEXT PRIMARY KEY,
                    source_path TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    page_number INTEGER NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    content_hash TEXT NOT NULL,
                    text TEXT NOT NULL
                )
                """
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_source_path ON chunks(source_path)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_file_name ON chunks(file_name)")
        self.connection.commit()

    def get_file(self, source_path: str) -> dict[str, Any] | None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT source_path, file_hash, modified_at, indexed_at FROM files WHERE source_path = %s",
                (source_path,),
            )
            return cursor.fetchone()

    def upsert_file(self, source_path: str, file_hash: str, modified_at: float, indexed_at: str) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO files(source_path, file_hash, modified_at, indexed_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT(source_path)
                DO UPDATE SET file_hash = EXCLUDED.file_hash,
                              modified_at = EXCLUDED.modified_at,
                              indexed_at = EXCLUDED.indexed_at
                """,
                (source_path, file_hash, modified_at, indexed_at),
            )
        self.connection.commit()

    def replace_chunks_for_file(self, source_path: str, chunks: list[DocumentChunk]) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute("DELETE FROM chunks WHERE source_path = %s", (source_path,))
            cursor.executemany(
                """
                INSERT INTO chunks(chunk_id, source_path, file_name, page_number, chunk_index, content_hash, text)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
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
        with self.connection.cursor() as cursor:
            cursor.execute("DELETE FROM files WHERE source_path = %s", (source_path,))
            cursor.execute("DELETE FROM chunks WHERE source_path = %s", (source_path,))
        self.connection.commit()

    def list_files(self) -> list[dict[str, Any]]:
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT source_path, file_hash, modified_at, indexed_at FROM files ORDER BY source_path")
            return list(cursor.fetchall())

    def list_chunks(self, metadata_filter: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        query = "SELECT chunk_id, source_path, file_name, page_number, chunk_index, content_hash, text FROM chunks"
        params: list[Any] = []
        where_clauses: list[str] = []
        if metadata_filter:
            if "source_path" in metadata_filter:
                where_clauses.append("source_path = %s")
                params.append(metadata_filter["source_path"])
            if "file_name" in metadata_filter:
                where_clauses.append("file_name = %s")
                params.append(metadata_filter["file_name"])
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        query += " ORDER BY source_path, page_number, chunk_index"
        with self.connection.cursor() as cursor:
            cursor.execute(query, params)
            return list(cursor.fetchall())

    def close(self) -> None:
        self.connection.close()


class MetadataRepository:
    def __init__(
        self,
        sqlite_path: str,
        metadata_backend: str = "sqlite",
        postgres_dsn: str = "",
    ) -> None:
        backend = metadata_backend.lower()
        if backend == "postgres":
            self._repository: BaseMetadataRepository = PostgresMetadataRepository(postgres_dsn)
        else:
            self._repository = SqliteMetadataRepository(sqlite_path)

    def __getattr__(self, item: str) -> Any:
        return getattr(self._repository, item)

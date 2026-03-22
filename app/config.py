from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class AppSettings(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"


class DocumentSettings(BaseModel):
    path: str = "./documents"
    supported_extensions: list[str] = Field(default_factory=lambda: [".pdf", ".txt", ".docx", ".md"])


class ChunkingSettings(BaseModel):
    chunk_size_tokens: int = 700
    overlap_tokens: int = 120
    min_chunk_tokens: int = 80


class RetrievalSettings(BaseModel):
    top_k: int = 5
    dense_k: int = 8
    bm25_k: int = 8
    hybrid_alpha: float = 0.65
    rerank: bool = True
    stopwords: list[str] = Field(
        default_factory=lambda: [
            "che",
            "con",
            "come",
            "cosa",
            "dove",
            "quando",
            "quale",
            "quali",
            "della",
            "delle",
            "degli",
            "dello",
            "dell",
            "sullo",
            "sulla",
            "sulle",
            "negli",
            "nelle",
            "dallo",
            "dalla",
            "dalle",
        ]
    )


class ContextSettings(BaseModel):
    max_chars: int = 6000


class OllamaSettings(BaseModel):
    base_url: str = "http://localhost:11434"
    llm_model: str = "llama3.2"
    embedding_model: str = "nomic-embed-text"
    temperature: float = 0.1
    top_p: float = 0.9
    num_predict: int = 512
    timeout_seconds: int = 120


class StorageSettings(BaseModel):
    metadata_backend: str = "sqlite"
    vector_backend: str = "chroma"
    chroma_path: str = "./data/chroma"
    sqlite_path: str = "./data/state/index.db"
    postgres_dsn: str = "postgresql://rag:rag@postgres:5432/rag"
    cache_path: str = "./data/cache"
    qdrant_url: str = "http://qdrant:6333"
    qdrant_api_key: str = ""
    qdrant_collection_name: str = "rag_chunks"
    qdrant_timeout_seconds: int = 30


class IngestSettings(BaseModel):
    concurrent_files: int = Field(default=2, ge=1)


class WatchSettings(BaseModel):
    enabled: bool = True
    debounce_seconds: float = 2.0


class Settings(BaseModel):
    app: AppSettings = Field(default_factory=AppSettings)
    documents: DocumentSettings = Field(default_factory=DocumentSettings)
    chunking: ChunkingSettings = Field(default_factory=ChunkingSettings)
    retrieval: RetrievalSettings = Field(default_factory=RetrievalSettings)
    context: ContextSettings = Field(default_factory=ContextSettings)
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    ingest: IngestSettings = Field(default_factory=IngestSettings)
    watch: WatchSettings = Field(default_factory=WatchSettings)


def _deep_update(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_update(base[key], value)
        else:
            base[key] = value
    return base


def _apply_env_overrides(config: dict[str, Any]) -> dict[str, Any]:
    env_map = {
        "RAG_HOST": ("app", "host"),
        "RAG_PORT": ("app", "port"),
        "RAG_LOG_LEVEL": ("app", "log_level"),
        "RAG_DOCUMENTS_PATH": ("documents", "path"),
        "OLLAMA_BASE_URL": ("ollama", "base_url"),
        "OLLAMA_LLM_MODEL": ("ollama", "llm_model"),
        "OLLAMA_EMBEDDING_MODEL": ("ollama", "embedding_model"),
        "RAG_CHROMA_PATH": ("storage", "chroma_path"),
        "RAG_SQLITE_PATH": ("storage", "sqlite_path"),
        "RAG_METADATA_BACKEND": ("storage", "metadata_backend"),
        "RAG_VECTOR_BACKEND": ("storage", "vector_backend"),
        "RAG_POSTGRES_DSN": ("storage", "postgres_dsn"),
        "RAG_CACHE_PATH": ("storage", "cache_path"),
        "QDRANT_URL": ("storage", "qdrant_url"),
        "QDRANT_API_KEY": ("storage", "qdrant_api_key"),
        "QDRANT_COLLECTION_NAME": ("storage", "qdrant_collection_name"),
        "QDRANT_TIMEOUT_SECONDS": ("storage", "qdrant_timeout_seconds"),
        "RAG_INGEST_CONCURRENT_FILES": ("ingest", "concurrent_files"),
        "RAG_QUERY_STOPWORDS": ("retrieval", "stopwords"),
        "RAG_WATCH_ENABLED": ("watch", "enabled"),
    }
    for env_name, path in env_map.items():
        if env_name not in os.environ:
            continue
        current = config
        for key in path[:-1]:
            current = current.setdefault(key, {})
        raw_value = os.environ[env_name]
        if env_name == "RAG_QUERY_STOPWORDS":
            current[path[-1]] = [item.strip() for item in raw_value.split(",") if item.strip()]
            continue
        if raw_value.lower() in {"true", "false"}:
            current[path[-1]] = raw_value.lower() == "true"
        elif raw_value.isdigit():
            current[path[-1]] = int(raw_value)
        else:
            current[path[-1]] = raw_value
    return config


def load_settings(config_path: str | None = None) -> Settings:
    base_path = Path(config_path or os.environ.get("RAG_CONFIG_PATH", "config/config.yaml"))
    with base_path.open("r", encoding="utf-8") as handle:
        raw_config = yaml.safe_load(handle) or {}
    config = _apply_env_overrides(raw_config)
    settings = Settings.model_validate(config)

    for directory in [
        Path(settings.documents.path),
        Path(settings.storage.chroma_path),
        Path(settings.storage.sqlite_path).parent,
        Path(settings.storage.cache_path),
    ]:
        directory.mkdir(parents=True, exist_ok=True)

    return settings

#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${ROOT_DIR}/docker-compose.prod.yml"
OLLAMA_HOST_PORT="${OLLAMA_HOST_PORT:-11435}"
RAG_API_HOST_PORT="${RAG_API_HOST_PORT:-8010}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-postgres}"
QDRANT_HOST_PORT="${QDRANT_HOST_PORT:-6333}"

cd "$ROOT_DIR"

mkdir -p documents

docker compose -f "$COMPOSE_FILE" up -d postgres qdrant ollama

echo "Waiting for Qdrant in production stack..."
for _ in $(seq 1 60); do
  if curl -fsS "http://localhost:${QDRANT_HOST_PORT}/collections" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

curl -fsS "http://localhost:${QDRANT_HOST_PORT}/collections" >/dev/null

echo "Waiting for Ollama in production stack..."
for _ in $(seq 1 90); do
  if curl -fsS "http://localhost:${OLLAMA_HOST_PORT}/api/tags" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

curl -fsS "http://localhost:${OLLAMA_HOST_PORT}/api/tags" >/dev/null

docker exec rag-ollama ollama pull llama3.2
docker exec rag-ollama ollama pull nomic-embed-text

docker compose -f "$COMPOSE_FILE" up -d --build rag-api

echo "Production API available on http://localhost:${RAG_API_HOST_PORT}"
echo "Production Ollama available on http://localhost:${OLLAMA_HOST_PORT}"
echo "Qdrant available on http://localhost:${QDRANT_HOST_PORT}"

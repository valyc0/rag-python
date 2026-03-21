#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OLLAMA_HOST_PORT="${OLLAMA_HOST_PORT:-11435}"
RAG_API_HOST_PORT="${RAG_API_HOST_PORT:-8010}"

cd "$ROOT_DIR"

mkdir -p documents data/chroma data/state data/cache

docker compose up -d ollama

echo "Waiting for Ollama..."
for _ in $(seq 1 60); do
  if curl -fsS "http://localhost:${OLLAMA_HOST_PORT}/api/tags" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

curl -fsS "http://localhost:${OLLAMA_HOST_PORT}/api/tags" >/dev/null

docker exec rag-ollama ollama pull llama3.2
docker exec rag-ollama ollama pull nomic-embed-text

docker compose up -d rag-api

echo "RAG API available on http://localhost:${RAG_API_HOST_PORT}"
echo "Ollama available on http://localhost:${OLLAMA_HOST_PORT}"

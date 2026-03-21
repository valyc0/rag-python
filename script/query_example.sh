#!/usr/bin/env bash

set -euo pipefail

RAG_API_HOST_PORT="${RAG_API_HOST_PORT:-8010}"
USE_CACHE="${USE_CACHE:-true}"

QUESTION="${1:-Riassumi il contenuto dei documenti indicizzati}"

curl -fsS -X POST "http://localhost:${RAG_API_HOST_PORT}/query" \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"${QUESTION}\",\"use_cache\":${USE_CACHE}}" | python3 -m json.tool

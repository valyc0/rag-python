#!/usr/bin/env bash

set -euo pipefail

RAG_API_HOST_PORT="${RAG_API_HOST_PORT:-8010}"

QUESTION="${1:-Riassumi il contenuto dei documenti indicizzati}"

curl -fsS -X POST "http://localhost:${RAG_API_HOST_PORT}/query/debug" \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"${QUESTION}\"}" | python3 -m json.tool
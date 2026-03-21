#!/usr/bin/env bash

set -euo pipefail

RAG_API_HOST_PORT="${RAG_API_HOST_PORT:-8010}"
USE_CACHE="${USE_CACHE:-true}"

FILE_NAME="${1:-1Samuele.pdf}"
QUESTION="${2:-Riassumi il contenuto del documento}"

curl -fsS -X POST "http://localhost:${RAG_API_HOST_PORT}/query" \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"${QUESTION}\",\"use_cache\":${USE_CACHE},\"metadata_filter\":{\"file_name\":\"${FILE_NAME}\"}}" | python3 -m json.tool

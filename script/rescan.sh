#!/usr/bin/env bash

set -euo pipefail

RAG_API_HOST_PORT="${RAG_API_HOST_PORT:-8010}"

curl -fsS -X POST "http://localhost:${RAG_API_HOST_PORT}/ingest/rescan" | python3 -m json.tool

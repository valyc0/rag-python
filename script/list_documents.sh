#!/usr/bin/env bash

set -euo pipefail

RAG_API_HOST_PORT="${RAG_API_HOST_PORT:-8010}"

curl -fsS "http://localhost:${RAG_API_HOST_PORT}/documents" | python3 -m json.tool

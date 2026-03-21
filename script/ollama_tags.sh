#!/usr/bin/env bash

set -euo pipefail

OLLAMA_HOST_PORT="${OLLAMA_HOST_PORT:-11435}"

curl -fsS "http://localhost:${OLLAMA_HOST_PORT}/api/tags"
echo

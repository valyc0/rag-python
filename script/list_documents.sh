#!/usr/bin/env bash

set -euo pipefail

RAG_API_HOST_PORT="${RAG_API_HOST_PORT:-8010}"
LIST_DOCUMENTS_TIMEOUT_SECONDS="${LIST_DOCUMENTS_TIMEOUT_SECONDS:-300}"
ENDPOINT="http://localhost:${RAG_API_HOST_PORT}/documents"

start_time=$(date +%s)

while true; do
	if response="$(curl -fsS "$ENDPOINT" 2>/dev/null)"; then
		printf '%s\n' "$response" | python3 -m json.tool
		exit 0
	fi

	now=$(date +%s)
	if (( now - start_time >= LIST_DOCUMENTS_TIMEOUT_SECONDS )); then
		echo "RAG API not ready on $ENDPOINT after ${LIST_DOCUMENTS_TIMEOUT_SECONDS}s." >&2
		echo "The production stack may still be indexing documents during startup." >&2
		exit 1
	fi

	sleep 2
done

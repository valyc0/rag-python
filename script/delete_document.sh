#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOCUMENTS_DIR="${RAG_DOCUMENTS_HOST_PATH:-${ROOT_DIR}/documents}"
RAG_API_HOST_PORT="${RAG_API_HOST_PORT:-8010}"

usage() {
  echo "Usage: ./script/delete_document.sh <relative-path-in-documents>"
  echo
  echo "Deletes a document from the host documents directory and triggers a rescan."
}

if [[ $# -ne 1 ]]; then
  usage >&2
  exit 1
fi

case "$1" in
  --help|-h)
    usage
    exit 0
    ;;
esac

relative_path="$1"

if [[ "$relative_path" = /* ]]; then
  echo "Pass a path relative to documents/, not an absolute path." >&2
  exit 1
fi

target_path="${DOCUMENTS_DIR}/${relative_path}"

if [[ ! -f "$target_path" ]]; then
  echo "Document not found: $target_path" >&2
  exit 1
fi

rm -f -- "$target_path"
echo "Deleted: $target_path"

curl -fsS -X POST "http://localhost:${RAG_API_HOST_PORT}/ingest/rescan" | python3 -m json.tool
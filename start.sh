#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OLLAMA_HOST_PORT="${OLLAMA_HOST_PORT:-11435}"
RAG_API_HOST_PORT="${RAG_API_HOST_PORT:-8010}"
CONFIG_PATH="${RAG_CONFIG_PATH:-config/config.yaml}"

resolve_config_path() {
  local path="$1"
  if [[ "$path" = /* ]]; then
    printf '%s\n' "$path"
  else
    printf '%s\n' "$ROOT_DIR/$path"
  fi
}

yaml_get_ollama_value() {
  local config_path="$1"
  local key="$2"
  awk -v target="$key" '
    $0 ~ /^ollama:[[:space:]]*$/ { in_ollama=1; next }
    in_ollama && $0 ~ /^[^[:space:]]/ { in_ollama=0 }
    in_ollama {
      pattern = "^[[:space:]]*" target ":[[:space:]]*"
      if ($0 ~ pattern) {
        value = $0
        sub(pattern, "", value)
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
        gsub(/^"|"$/, "", value)
        print value
        exit
      }
    }
  ' "$config_path"
}

cd "$ROOT_DIR"

CONFIG_PATH="$(resolve_config_path "$CONFIG_PATH")"

if [[ ! -f "$CONFIG_PATH" ]]; then
  echo "Config file not found: $CONFIG_PATH" >&2
  exit 1
fi

LLM_MODEL="$(yaml_get_ollama_value "$CONFIG_PATH" "llm_model")"
EMBEDDING_MODEL="$(yaml_get_ollama_value "$CONFIG_PATH" "embedding_model")"
PULLED_MODEL=""

if [[ -z "$LLM_MODEL" || -z "$EMBEDDING_MODEL" ]]; then
  echo "Unable to read llm_model and embedding_model from $CONFIG_PATH" >&2
  exit 1
fi

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

for model in "$LLM_MODEL" "$EMBEDDING_MODEL"; do
  [[ -z "$model" ]] && continue
  if [[ "$model" == "$PULLED_MODEL" ]]; then
    continue
  fi
  echo "Pulling Ollama model: $model"
  docker exec rag-ollama ollama pull "$model"
  PULLED_MODEL="$model"
done

docker compose up -d rag-api

echo "RAG API available on http://localhost:${RAG_API_HOST_PORT}"
echo "Ollama available on http://localhost:${OLLAMA_HOST_PORT}"

#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${ROOT_DIR}/docker-compose.yml"
PROD_COMPOSE_FILE="${ROOT_DIR}/docker-compose.prod.yml"

usage() {
  echo "Usage: ./remove_all.sh"
  echo
  echo "Stops both the standard and production Docker stacks and removes their named volumes."
}

if [[ $# -gt 0 ]]; then
  case "$1" in
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker command not found" >&2
  exit 1
fi

cd "$ROOT_DIR"

down_stack() {
  local label="$1"
  shift

  echo "Removing ${label}..."
  docker compose "$@" down --remove-orphans -v
}

down_stack "standard stack" -f "$COMPOSE_FILE"
down_stack "production stack" -f "$PROD_COMPOSE_FILE"

echo "All project stacks and named volumes removed."
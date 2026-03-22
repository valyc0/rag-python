#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${ROOT_DIR}/docker-compose.yml"
PROD_COMPOSE_FILE="${ROOT_DIR}/docker-compose.prod.yml"
REMOVE_VOLUMES=false

usage() {
  echo "Usage: ./stop.sh [--volumes]"
  echo
  echo "Stops both the standard and production Docker stacks for this project."
  echo "Use --volumes to remove named Docker volumes as well."
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --volumes|-v)
      REMOVE_VOLUMES=true
      shift
      ;;
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
done

if ! command -v docker >/dev/null 2>&1; then
  echo "docker command not found" >&2
  exit 1
fi

cd "$ROOT_DIR"

down_stack() {
  local label="$1"
  shift

  echo "Stopping ${label}..."
  if [[ "$REMOVE_VOLUMES" == true ]]; then
    docker compose "$@" down --remove-orphans -v
  else
    docker compose "$@" down --remove-orphans
  fi
}

down_stack "standard stack" -f "$COMPOSE_FILE"
down_stack "production stack" -f "$PROD_COMPOSE_FILE"

if [[ "$REMOVE_VOLUMES" == true ]]; then
  echo "All project stacks stopped and volumes removed."
else
  echo "All project stacks stopped."
fi
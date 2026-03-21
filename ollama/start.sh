#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "La sorgente di verita' Docker e' il compose in root."
echo "Delego l'avvio allo script principale del progetto."

exec "$ROOT_DIR/start.sh"

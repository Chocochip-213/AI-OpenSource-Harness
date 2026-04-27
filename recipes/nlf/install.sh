#!/usr/bin/env bash
# Install dependencies for this recipe
set -euo pipefail

RECIPE_DIR="$(cd "$(dirname "$0")" && pwd)"
REQ_FILE="${1:-requirements_opt1.txt}"

echo "[install] Installing from $REQ_FILE ..."
pip install -q -r "$RECIPE_DIR/$REQ_FILE"
echo "[install] Done."

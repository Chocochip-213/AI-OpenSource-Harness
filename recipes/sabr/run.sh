#!/usr/bin/env bash
set -euo pipefail
RECIPE_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$RECIPE_DIR/../.." && pwd)"
RECIPE_NAME="$(basename "$RECIPE_DIR")"

echo "[run] Generating notebook: $RECIPE_NAME"
python "$REPO_ROOT/tools/generate_notebook.py" "$RECIPE_NAME"
echo "[run] Output: outputs/notebooks/${RECIPE_NAME}.ipynb"

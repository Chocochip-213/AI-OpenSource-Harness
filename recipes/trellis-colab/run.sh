#!/usr/bin/env bash
# Run the recipe
set -euo pipefail

RECIPE_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "[run] Recipe: trellis-colab"
echo "[run] Checkpoint workflow recipe for TRELLIS.2 on Colab."
echo "[run] Use notebook generation path for execution."
echo "[run] Example: uv run python tools/generate_notebook.py trellis-colab"

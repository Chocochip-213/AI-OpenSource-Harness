#!/usr/bin/env bash
# Run FLUX.2 Klein 4B T-pose conversion
# Required env vars:
#   GARMENT_IMAGE — path to garment image
# Optional:
#   STRENGTH      — denoising strength (default: 0.5)
#   SEED          — random seed (default: 42)
#   OUT_DIR       — output directory (default: ./output)
set -euo pipefail

RECIPE_DIR="$(cd "$(dirname "$0")" && pwd)"
GARMENT_IMAGE="${GARMENT_IMAGE:?ERROR: set GARMENT_IMAGE to your garment photo}"
STRENGTH="${STRENGTH:-0.5}"
SEED="${SEED:-42}"
OUT_DIR="${OUT_DIR:-./output}"

echo "============================================"
echo "[run] FLUX.2 Klein 4B T-pose Conversion"
echo "[run] GARMENT_IMAGE = $GARMENT_IMAGE"
echo "[run] STRENGTH      = $STRENGTH"
echo "[run] SEED          = $SEED"
echo "[run] OUT_DIR       = $OUT_DIR"
echo "============================================"

echo "[run] Use the Colab notebook for full interactive experience with Gradio API."
echo "[run] CLI mode is for batch inference — see notebook_manifest.yaml."

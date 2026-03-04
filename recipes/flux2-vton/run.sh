#!/usr/bin/env bash
# Run FLUX.2 Klein 9B VTON inference
# Required env vars:
#   PERSON_IMAGE  — path to person image
#   GARMENT_IMAGE — path to garment image
# Optional:
#   TARGET_SIZE   — target size key (default: XL(105))
#   FIT_PROFILE   — fit profile key (default: oversized)
#   USE_LORA      — true/false (default: true)
#   SEED          — random seed (default: 42)
#   OUT_DIR       — output directory (default: ./output)
set -euo pipefail

RECIPE_DIR="$(cd "$(dirname "$0")" && pwd)"
PERSON_IMAGE="${PERSON_IMAGE:?ERROR: set PERSON_IMAGE to your person photo}"
GARMENT_IMAGE="${GARMENT_IMAGE:?ERROR: set GARMENT_IMAGE to your garment photo}"
TARGET_SIZE="${TARGET_SIZE:-XL(105)}"
FIT_PROFILE="${FIT_PROFILE:-oversized}"
USE_LORA="${USE_LORA:-true}"
SEED="${SEED:-42}"
OUT_DIR="${OUT_DIR:-./output}"

echo "============================================"
echo "[run] FLUX.2 Klein 9B Virtual Try-On"
echo "[run] PERSON_IMAGE  = $PERSON_IMAGE"
echo "[run] GARMENT_IMAGE = $GARMENT_IMAGE"
echo "[run] TARGET_SIZE   = $TARGET_SIZE"
echo "[run] FIT_PROFILE   = $FIT_PROFILE"
echo "[run] USE_LORA      = $USE_LORA"
echo "[run] SEED          = $SEED"
echo "[run] OUT_DIR       = $OUT_DIR"
echo "============================================"

echo "[run] Use the Colab notebook for full interactive experience."
echo "[run] CLI mode is for batch inference — see notebook_manifest.yaml."

#!/usr/bin/env bash
# Run SwiftTry video virtual try-on inference
# Required env vars:
#   DATA_DIR  — path to dataset (videos/, garments/, etc.)
#   OUT_DIR   — path to save output (default: ./output_result)
# Optional:
#   PAIRS_FILE — test pairs file (default: $DATA_DIR/test_pairs.txt)
#   SWIFTTRY_DIR — cloned repo path (default: ./SwiftTry)
set -euo pipefail

RECIPE_DIR="$(cd "$(dirname "$0")" && pwd)"
SWIFTTRY_DIR="${SWIFTTRY_DIR:-./SwiftTry}"
DATA_DIR="${DATA_DIR:?ERROR: set DATA_DIR to your dataset folder}"
OUT_DIR="${OUT_DIR:-./output_result}"
PAIRS_FILE="${PAIRS_FILE:-$DATA_DIR/test_pairs.txt}"

echo "============================================"
echo "[run] SwiftTry Video Virtual Try-On"
echo "[run] DATA_DIR  = $DATA_DIR"
echo "[run] PAIRS_FILE= $PAIRS_FILE"
echo "[run] OUT_DIR   = $OUT_DIR"
echo "============================================"

cd "$SWIFTTRY_DIR"

# Ensure weight symlink exists
if [ ! -e weights/tiktokdress ] && [ -d pretrained_sd_models/swift_try ]; then
    mkdir -p weights
    ln -sfn "$(pwd)/pretrained_sd_models/swift_try" weights/tiktokdress
    echo "[run] Created weight symlink: weights/tiktokdress -> pretrained_sd_models/swift_try"
fi

python inference.py \
    --data_dir "$DATA_DIR" \
    --test_pairs "$PAIRS_FILE" \
    --save_dir "$OUT_DIR"

echo "[run] Output saved to: $OUT_DIR"

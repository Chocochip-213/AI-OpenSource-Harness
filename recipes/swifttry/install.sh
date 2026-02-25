#!/usr/bin/env bash
# Install dependencies for SwiftTry recipe
# Usage: bash install.sh [requirements_file]
#   Default: requirements_opt2_modern.txt (keeps Colab torch)
#   Fallback: requirements_opt1_legacy.txt (pins upstream versions)
set -euo pipefail

RECIPE_DIR="$(cd "$(dirname "$0")" && pwd)"
REQ_FILE="${1:-requirements_opt2_modern.txt}"

echo "============================================"
echo "[install] SwiftTry — installing from $REQ_FILE"
echo "============================================"

# Show current torch version (should be pre-installed on Colab)
python -c "import torch; print(f'[install] torch={torch.__version__}  CUDA={torch.version.cuda}')" 2>/dev/null || true

pip install -q -r "$RECIPE_DIR/$REQ_FILE"

echo "[install] Verifying critical imports..."
python -c "
import torch, diffusers, transformers, accelerate, cv2, einops, omegaconf
print(f'  torch={torch.__version__}')
print(f'  diffusers={diffusers.__version__}')
print(f'  transformers={transformers.__version__}')
print(f'  accelerate={accelerate.__version__}')
print(f'  CUDA available={torch.cuda.is_available()}')
"

echo "[install] Done."

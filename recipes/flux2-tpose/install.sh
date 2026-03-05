#!/usr/bin/env bash
# Install dependencies for FLUX.2 Klein 4B T-pose recipe
set -euo pipefail

RECIPE_DIR="$(cd "$(dirname "$0")" && pwd)"
REQ_FILE="${1:-requirements_opt1.txt}"

echo "============================================"
echo "[install] FLUX.2 Klein 4B T-pose — installing from $REQ_FILE"
echo "============================================"

python -c "import torch; print(f'[install] torch={torch.__version__}  CUDA={torch.version.cuda}')" 2>/dev/null || true

pip install -q -r "$RECIPE_DIR/$REQ_FILE"

echo "[install] Verifying critical imports..."
python -c "
import torch, diffusers, transformers, accelerate
print(f'  torch={torch.__version__}')
print(f'  diffusers={diffusers.__version__}')
print(f'  transformers={transformers.__version__}')
print(f'  accelerate={accelerate.__version__}')
print(f'  CUDA available={torch.cuda.is_available()}')

try:
    from diffusers import Flux2KleinPipeline
    print('  Flux2KleinPipeline: OK')
except ImportError:
    print('  WARNING: Flux2KleinPipeline not found — may need diffusers git HEAD')
"

echo "[install] Done."

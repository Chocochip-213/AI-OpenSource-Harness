#!/usr/bin/env python3
"""Patch SwiftTry source files for compatibility with diffusers >= 0.26.

Fixes 5 breaking import changes between diffusers 0.24.0 and 0.36.0:
  1. CaptionProjection  → PixArtAlphaTextProjection  (transformer_2d.py)
  2. AdaLayerNorm import path                          (attention.py)
  3. ADDED_KV_ATTENTION_PROCESSORS removed             (unet_2d_condition.py)
  4. CROSS_ATTENTION_PROCESSORS removed                (unet_2d_condition.py)
  5. DualTransformer2DModel path moved                 (unet_2d_blocks.py)
  6. LoRACompatibleConv/Linear future-proofing         (transformer_2d.py)

Usage:
    cd SwiftTry && python ../recipes/swifttry/patches/fix_diffusers_compat.py
    # or from repo root:
    python recipes/swifttry/patches/fix_diffusers_compat.py --repo-dir ./SwiftTry
"""

import argparse
import re
import sys
from pathlib import Path


def patch_file(fpath: Path, replacements: list[tuple[str, str]]) -> bool:
    """Apply text replacements to a file. Returns True if any changes made."""
    if not fpath.exists():
        print(f"  SKIP (not found): {fpath}")
        return False
    text = fpath.read_text(encoding="utf-8")
    original = text
    for old, new in replacements:
        text = text.replace(old, new)
    if text != original:
        fpath.write_text(text, encoding="utf-8")
        print(f"  PATCHED: {fpath}")
        return True
    else:
        print(f"  OK (already patched or no match): {fpath}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Patch SwiftTry for diffusers compat")
    parser.add_argument("--repo-dir", default=".", help="Path to SwiftTry repo root")
    args = parser.parse_args()
    repo = Path(args.repo_dir)

    if not (repo / "inference.py").exists():
        print(f"ERROR: {repo}/inference.py not found. Are you in the SwiftTry repo?")
        sys.exit(1)

    print("[patch] Fixing diffusers 0.24→0.36 import compatibility...\n")
    patched = 0

    # ── 1. transformer_2d.py: CaptionProjection + LoRA compat ──
    f = repo / "src" / "models_attention" / "transformer_2d.py"
    patched += patch_file(f, [
        (
            "from diffusers.models.embeddings import CaptionProjection",
            "try:\n"
            "    from diffusers.models.embeddings import CaptionProjection\n"
            "except ImportError:\n"
            "    from diffusers.models.embeddings import PixArtAlphaTextProjection as CaptionProjection",
        ),
        (
            "from diffusers.models.lora import LoRACompatibleConv, LoRACompatibleLinear",
            "try:\n"
            "    from diffusers.models.lora import LoRACompatibleConv, LoRACompatibleLinear\n"
            "except ImportError:\n"
            "    import torch.nn as nn\n"
            "    LoRACompatibleConv = nn.Conv2d\n"
            "    LoRACompatibleLinear = nn.Linear",
        ),
    ])

    # ── 2. attention.py: AdaLayerNorm + Attention import path ──
    f = repo / "src" / "models_attention" / "attention.py"
    patched += patch_file(f, [
        (
            "from diffusers.models.attention import AdaLayerNorm, Attention, FeedForward",
            "from diffusers.models.attention import FeedForward\n"
            "from diffusers.models.attention_processor import Attention\n"
            "try:\n"
            "    from diffusers.models.attention import AdaLayerNorm\n"
            "except ImportError:\n"
            "    from diffusers.models.normalization import AdaLayerNorm",
        ),
    ])

    # ── 3 & 4. unet_2d_condition.py: ADDED_KV / CROSS + embeddings ──
    f = repo / "src" / "models_attention" / "unet_2d_condition.py"
    patched += patch_file(f, [
        (
            "from diffusers.models.attention_processor import (\n"
            "    ADDED_KV_ATTENTION_PROCESSORS,\n"
            "    CROSS_ATTENTION_PROCESSORS,\n"
            "    AttentionProcessor,\n"
            "    AttnAddedKVProcessor,\n"
            "    AttnProcessor,\n"
            ")",
            "from diffusers.models.attention_processor import (\n"
            "    AttentionProcessor,\n"
            "    AttnAddedKVProcessor,\n"
            "    AttnProcessor,\n"
            ")\n"
            "try:\n"
            "    from diffusers.models.attention_processor import ADDED_KV_ATTENTION_PROCESSORS\n"
            "except ImportError:\n"
            "    ADDED_KV_ATTENTION_PROCESSORS = (AttnAddedKVProcessor,)\n"
            "try:\n"
            "    from diffusers.models.attention_processor import CROSS_ATTENTION_PROCESSORS\n"
            "except ImportError:\n"
            "    CROSS_ATTENTION_PROCESSORS = (AttnProcessor,)",
        ),
        # PositionNet / ImageHintTimeEmbedding removed in diffusers >= 0.26
        (
            "from diffusers.models.embeddings import (\n"
            "    GaussianFourierProjection,\n"
            "    ImageHintTimeEmbedding,\n"
            "    ImageProjection,\n"
            "    ImageTimeEmbedding,\n"
            "    PositionNet,\n"
            "    TextImageProjection,\n"
            "    TextImageTimeEmbedding,\n"
            "    TextTimeEmbedding,\n"
            "    TimestepEmbedding,\n"
            "    Timesteps,\n"
            ")",
            "from diffusers.models.embeddings import (\n"
            "    GaussianFourierProjection,\n"
            "    ImageProjection,\n"
            "    ImageTimeEmbedding,\n"
            "    TextImageProjection,\n"
            "    TextImageTimeEmbedding,\n"
            "    TextTimeEmbedding,\n"
            "    TimestepEmbedding,\n"
            "    Timesteps,\n"
            ")\n"
            "try:\n"
            "    from diffusers.models.embeddings import ImageHintTimeEmbedding\n"
            "except ImportError:\n"
            "    ImageHintTimeEmbedding = None\n"
            "try:\n"
            "    from diffusers.models.embeddings import PositionNet\n"
            "except ImportError:\n"
            "    PositionNet = None",
        ),
    ])

    # ── 5. unet_2d_blocks.py: DualTransformer2DModel path ──
    f = repo / "src" / "models_attention" / "unet_2d_blocks.py"
    patched += patch_file(f, [
        (
            "from diffusers.models.dual_transformer_2d import DualTransformer2DModel",
            "try:\n"
            "    from diffusers.models.dual_transformer_2d import DualTransformer2DModel\n"
            "except ImportError:\n"
            "    try:\n"
            "        from diffusers.models.transformers.dual_transformer_2d import DualTransformer2DModel\n"
            "    except ImportError:\n"
            "        DualTransformer2DModel = None  # not used in SwiftTry inference paths",
        ),
    ])

    print(f"\n[patch] Done. {patched} file(s) patched.")


if __name__ == "__main__":
    main()

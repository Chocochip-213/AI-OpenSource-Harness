#!/usr/bin/env python3
"""Generate `recipes/<name>/exports/` from a recipe's metadata.

Reads `recipes/<name>/recipe.yaml` (+ `notebook_manifest.yaml`) and
substitutes placeholders into the templates at
`recipes/_template/exports/`. The output is what the Spring backend +
Next.js frontend teams treat as the contract — they should never need
to read the recipe's source code or the live Colab notebook.

Generated files (overwrites; the templates are the source of truth):
  exports/model_card.md
  exports/gradio_api.schema.json
  exports/inference_handler.py
  exports/INTEGRATION_BACKEND.md
  exports/INTEGRATION_FRONTEND.md
  exports/assets/.gitkeep

Substitutions:
  {RECIPE_NAME}, {RECIPE_VERSION}, {UPSTREAM_REPO}, {UPSTREAM_REF},
  {PREFERRED_GPU}, {VRAM_MIN_GB}, {PYTHON_VERSION}, {COLAB_VERSION},
  {ASSET_MIME}, {BACKEND_ENV_VAR}

Usage:
    uv run python tools/generate_export.py <recipe>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML required. Install with: uv sync", file=sys.stderr)
    sys.exit(1)


REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = REPO_ROOT / "recipes" / "_template" / "exports"

# Files to copy verbatim from the template, with `{...}` placeholders
# replaced. Anything else in the template directory is copied byte-for-byte.
SUBSTITUTABLE = {
    "model_card.md",
    "gradio_api.schema.json",
    "inference_handler.py",
    "INTEGRATION_BACKEND.md",
    "INTEGRATION_FRONTEND.md",
}


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def build_substitutions(recipe_name: str) -> dict[str, str]:
    recipe_yaml = REPO_ROOT / "recipes" / recipe_name / "recipe.yaml"
    cfg = _load_yaml(recipe_yaml)
    upstream = cfg.get("upstream") or {}
    runtime = cfg.get("runtime") or {}
    mcp = cfg.get("mcp") or {}
    integration = cfg.get("integration") or {}

    return {
        "{RECIPE_NAME}": recipe_name,
        "{RECIPE_VERSION}": str(cfg.get("version") or "0.1.0"),
        "{UPSTREAM_REPO}": str(upstream.get("repo") or "(not set)"),
        "{UPSTREAM_REF}": str(upstream.get("ref") or "(not set)"),
        "{PREFERRED_GPU}": str(mcp.get("preferred_gpu") or runtime.get("gpu") or "(any)"),
        "{VRAM_MIN_GB}": str(runtime.get("vram_min_gb") or "?"),
        "{PYTHON_VERSION}": str(runtime.get("python") or "3.11"),
        "{COLAB_VERSION}": str(runtime.get("colab_version") or "(any current)"),
        "{ASSET_MIME}": str(integration.get("asset_mime") or "application/json"),
        "{BACKEND_ENV_VAR}": str(integration.get("backend_env_var") or "AI_GRADIO_URL"),
    }


def substitute(text: str, mapping: dict[str, str]) -> str:
    out = text
    for k, v in mapping.items():
        out = out.replace(k, v)
    return out


def export_one(template_path: Path, dest_path: Path, mapping: dict[str, str]) -> None:
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    if template_path.name in SUBSTITUTABLE:
        text = template_path.read_text(encoding="utf-8")
        dest_path.write_text(substitute(text, mapping), encoding="utf-8")
    else:
        # binary or non-substitutable — copy verbatim
        dest_path.write_bytes(template_path.read_bytes())


def generate_export(recipe_name: str) -> Path:
    recipe_dir = REPO_ROOT / "recipes" / recipe_name
    if not recipe_dir.exists():
        print(f"ERROR: {recipe_dir} not found", file=sys.stderr)
        sys.exit(1)

    if not TEMPLATE_DIR.exists():
        print(
            f"ERROR: template directory {TEMPLATE_DIR} missing — "
            "the harness's recipes/_template/exports/ should exist.",
            file=sys.stderr,
        )
        sys.exit(1)

    mapping = build_substitutions(recipe_name)
    out_dir = recipe_dir / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)

    written = []
    for src in TEMPLATE_DIR.rglob("*"):
        if src.is_dir():
            continue
        rel = src.relative_to(TEMPLATE_DIR)
        dst = out_dir / rel
        export_one(src, dst, mapping)
        written.append(dst.relative_to(REPO_ROOT))

    print(f"[generate_export] {recipe_name} → {out_dir.relative_to(REPO_ROOT)}/")
    for p in written:
        print(f"  + {p}")
    return out_dir


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("recipe", help="Recipe name (folder under recipes/)")
    args = ap.parse_args()
    generate_export(args.recipe)
    return 0


if __name__ == "__main__":
    sys.exit(main())

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
  {RECIPE_NAME}         raw recipe folder name (e.g. `_mcp-sandbox`)
  {RECIPE_CLASS_NAME}   PascalCase identifier, safe for Java/TS class/type
                        names (e.g. `McpSandbox`). Required because
                        {RECIPE_NAME} may contain hyphens / leading `_`
                        which are invalid in those language identifiers.
  {RECIPE_SNAKE_NAME}   lowercase_underscore identifier, safe for file
                        names without leading `_` (e.g. `mcp_sandbox`).
  {RECIPE_VERSION}, {UPSTREAM_REPO}, {UPSTREAM_REF},
  {PREFERRED_GPU}, {VRAM_MIN_GB}, {PYTHON_VERSION}, {COLAB_VERSION},
  {ASSET_MIME}, {BACKEND_ENV_VAR}, {TEAM_CHANNEL}

Usage:
    uv run python tools/generate_export.py <recipe>
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML required. Install with: uv sync", file=sys.stderr)
    sys.exit(1)


REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = REPO_ROOT / "recipes" / "_template" / "exports"

SUBSTITUTABLE = {
    "model_card.md",
    "gradio_api.schema.json",
    "inference_handler.py",
    "INTEGRATION_BACKEND.md",
    "INTEGRATION_FRONTEND.md",
}

RECIPE_NAME_OK = re.compile(r"^[a-z_][a-z0-9_-]*$")
ENV_VAR_SAFE = re.compile(r"[^A-Z0-9_]")


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _to_pascal(name: str) -> str:
    """`_mcp-sandbox` -> `McpSandbox`; `avatar-rig` -> `AvatarRig`."""
    parts = re.split(r"[^A-Za-z0-9]+", name.lstrip("_"))
    return "".join(p[:1].upper() + p[1:] for p in parts if p) or "Recipe"


def _to_snake(name: str) -> str:
    """`_mcp-sandbox` -> `mcp_sandbox`; `AvatarRig` -> `avatar_rig`."""
    s = name.lstrip("_")
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).lower().strip("_")
    return s or "recipe"


def build_substitutions(recipe_name: str) -> dict[str, str]:
    recipe_yaml = REPO_ROOT / "recipes" / recipe_name / "recipe.yaml"
    cfg = _load_yaml(recipe_yaml)
    upstream = cfg.get("upstream") or {}
    runtime = cfg.get("runtime") or {}
    mcp = cfg.get("mcp") or {}
    integration = cfg.get("integration") or {}

    if not integration:
        print(
            f"[warn] {recipe_name}: recipe.yaml has no `integration:` section — "
            "using defaults (asset_mime=application/json, "
            "backend_env_var=AI_GRADIO_URL, team_channel=#ai-endpoint). "
            "Add the section to make the contract explicit.",
            file=sys.stderr,
        )

    env_var = str(integration.get("backend_env_var") or "AI_GRADIO_URL").upper()
    env_var = ENV_VAR_SAFE.sub("_", env_var)

    return {
        "{RECIPE_NAME}": recipe_name,
        "{RECIPE_CLASS_NAME}": _to_pascal(recipe_name),
        "{RECIPE_SNAKE_NAME}": _to_snake(recipe_name),
        "{RECIPE_VERSION}": str(cfg.get("version") or "0.1.0"),
        "{UPSTREAM_REPO}": str(upstream.get("repo") or "(not set)"),
        "{UPSTREAM_REF}": str(upstream.get("ref") or "(not set)"),
        "{PREFERRED_GPU}": str(mcp.get("preferred_gpu") or runtime.get("gpu") or "(any)"),
        "{VRAM_MIN_GB}": str(runtime.get("vram_min_gb") or "?"),
        "{PYTHON_VERSION}": str(runtime.get("python") or "3.11"),
        "{COLAB_VERSION}": str(runtime.get("colab_version") or "(any current)"),
        "{ASSET_MIME}": str(integration.get("asset_mime") or "application/json"),
        "{BACKEND_ENV_VAR}": env_var,
        "{TEAM_CHANNEL}": str(integration.get("team_channel") or "#ai-endpoint"),
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
        dest_path.write_bytes(template_path.read_bytes())


def _should_skip(src: Path) -> bool:
    parts = src.parts
    if "__pycache__" in parts:
        return True
    if src.suffix in {".pyc", ".pyo"}:
        return True
    return False


def generate_export(recipe_name: str) -> Path:
    if not RECIPE_NAME_OK.match(recipe_name):
        print(
            f"[warn] recipe name '{recipe_name}' is not `[a-z_][a-z0-9_-]*` — "
            "substitutions still run, but downstream consumers (Java/TS "
            "identifiers) may need manual cleanup.",
            file=sys.stderr,
        )

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

    written: list[Path] = []
    template_rels: set[Path] = set()
    for src in TEMPLATE_DIR.rglob("*"):
        if src.is_dir() or _should_skip(src):
            continue
        rel = src.relative_to(TEMPLATE_DIR)
        template_rels.add(rel)
        dst = out_dir / rel
        export_one(src, dst, mapping)
        written.append(dst.relative_to(REPO_ROOT))

    stale: list[Path] = []
    for existing in out_dir.rglob("*"):
        if existing.is_dir() or _should_skip(existing):
            continue
        rel = existing.relative_to(out_dir)
        if rel.parts and rel.parts[0] == "assets":
            continue
        if rel not in template_rels:
            stale.append(existing.relative_to(REPO_ROOT))

    print(f"[generate_export] {recipe_name} -> {out_dir.relative_to(REPO_ROOT)}/")
    for p in written:
        print(f"  + {p}")
    if stale:
        print(
            f"[warn] {len(stale)} file(s) in {out_dir.relative_to(REPO_ROOT)}/ "
            "do not correspond to any template file and were NOT overwritten "
            "(potentially stale after template rename/removal):",
            file=sys.stderr,
        )
        for p in stale:
            print(f"  ? {p}", file=sys.stderr)
    return out_dir


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("recipe", help="Recipe name (folder under recipes/)")
    args = ap.parse_args()
    generate_export(args.recipe)
    return 0


if __name__ == "__main__":
    sys.exit(main())

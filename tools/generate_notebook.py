#!/usr/bin/env python3
"""Generate a Colab-ready notebook (.ipynb) from a recipe's notebook_manifest.yaml.

Supports two manifest formats:
  - Extended: cells list with type/source (recommended)
  - Legacy: install/files/run sections

Usage:
    python tools/generate_notebook.py <recipe_name>
    python tools/generate_notebook.py --recipe <name> --out <path>
"""

import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML required. Install with: pip install pyyaml")
    sys.exit(1)


def get_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def source_to_lines(source: str) -> list[str]:
    """Convert a source string to notebook cell lines."""
    if not source:
        return []
    lines = source.split("\n")
    result = []
    for i, line in enumerate(lines):
        if i < len(lines) - 1:
            result.append(line + "\n")
        elif line:
            result.append(line + "\n")
    return result


def make_cell(cell_type: str, source: list[str], metadata: dict | None = None) -> dict:
    """Create a single notebook cell."""
    cell = {
        "cell_type": cell_type,
        "metadata": metadata or {},
        "source": source,
    }
    if cell_type == "code":
        cell["execution_count"] = None
        cell["outputs"] = []
    return cell


def generate_extended(manifest: dict, recipe_dir: Path) -> list[dict]:
    """Generate cells from extended format (cells list)."""
    cell_defs = manifest.get("cells") or []
    if not cell_defs:
        raise ValueError(
            f"notebook_manifest.yaml has an empty 'cells' list — "
            f"generated notebook would be blank.\n"
            f"Add at least one cell, or remove the 'cells' key to use legacy format."
        )
    cells = []
    for cell_def in cell_defs:
        cell_type = cell_def.get("type", "code")
        source = cell_def.get("source", "")
        metadata = cell_def.get("metadata", {})

        if cell_type not in ("code", "markdown"):
            cell_type = "code"

        lines = source_to_lines(source)
        cells.append(make_cell(cell_type, lines, metadata))
    return cells


def generate_legacy(manifest: dict, recipe_dir: Path) -> list[dict]:
    """Generate cells from legacy format (install/files/run)."""
    if not any(manifest.get(k) for k in ("install", "files", "run")):
        raise ValueError(
            "notebook_manifest.yaml (legacy format) has no 'install', 'files', or 'run' section — "
            "nothing to generate. Add at least one section or switch to extended format (cells list)."
        )
    cells = []

    # Title
    title = manifest.get("title", recipe_dir.name)
    cells.append(make_cell("markdown", [
        f"# {title}\n", "\n",
        f"Auto-generated notebook for recipe: **{recipe_dir.name}**\n",
    ]))

    # Install
    install_deps = manifest.get("install", [])
    if install_deps:
        install_lines = ["# Install dependencies\n"]
        for dep in install_deps:
            install_lines.append(f"!pip install -q {dep}\n")
        cells.append(make_cell("code", install_lines))

    # Files (%%writefile)
    for file_entry in manifest.get("files", []):
        src = file_entry.get("src", "")
        dst = file_entry.get("dst", src)
        desc = file_entry.get("description", "")

        if desc:
            cells.append(make_cell("markdown", [f"## {desc}\n"]))

        src_path = recipe_dir / src
        if src_path.exists():
            content = src_path.read_text(encoding="utf-8")
        else:
            content = f"# TODO: create {src}\n"

        cells.append(make_cell("code", [f"%%writefile {dst}\n", content]))

    # Run
    run_cmd = manifest.get("run", "")
    if run_cmd:
        cells.append(make_cell("markdown", ["## Run\n"]))
        cells.append(make_cell("code", [f"!{run_cmd}\n"]))

    return cells


def _load_recipe_yaml(recipe_dir: Path) -> dict:
    """Return recipe.yaml contents as a dict (or {} if absent/unreadable).

    Recipe.yaml is not required for legacy recipes but, when present, drives
    preferred_gpu injection into the generated notebook.
    """
    path = recipe_dir / "recipe.yaml"
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"WARN: could not read {path}: {e}")
        return {}


def _keepalive_cell(interval_seconds: int = 300) -> dict:
    """Inject a daemon thread that periodically prints to stdout so Colab's
    idle-disconnect timer (~90 min) resets. Only pulled in when
    `recipe.yaml:mcp.keepalive: true`.
    """
    source = (
        "#@title A0) Keepalive (auto-injected — mcp.keepalive: true)\n"
        "# Daemon thread prints a heartbeat every "
        f"{int(interval_seconds)}s so Colab's 90-min idle\n"
        "# timer resets during long investigations. Does not affect the\n"
        "# 12-hour session cap.\n"
        "import threading, time, os\n"
        "_KEEPALIVE_TAG = '__mcp_keepalive_running__'\n"
        "if not globals().get(_KEEPALIVE_TAG):\n"
        "    def _mcp_keepalive():\n"
        "        while True:\n"
        f"            print(f'[keepalive] {{time.strftime(\"%H:%M:%S\")}}', flush=True)\n"
        f"            time.sleep({int(interval_seconds)})\n"
        "    threading.Thread(target=_mcp_keepalive, daemon=True).start()\n"
        "    globals()[_KEEPALIVE_TAG] = True\n"
        "    print('[keepalive] started')\n"
        "else:\n"
        "    print('[keepalive] already running in this kernel')\n"
    )
    return make_cell("code", source_to_lines(source))


def _preferred_gpu_assert_cell(preferred_gpu: str, vram_min_gb: float | None) -> dict:
    """Build a fail-fast Cell A that asserts the actual runtime GPU matches
    the recipe's `mcp.preferred_gpu`. Colab silently downgrades A100→L4 during
    peak hours; catching it in the first cell saves hours of wasted inference.
    """
    vram_assert = ""
    if vram_min_gb:
        vram_assert = (
            f"assert vram >= {float(vram_min_gb):.1f}, (\n"
            f"    f\"VRAM {{vram:.1f}}GB < required {float(vram_min_gb):.1f}GB — \"\n"
            f"    \"request a larger GPU from Runtime > Change runtime type.\"\n"
            f")\n"
        )
    source = (
        "#@title A) GPU preflight (auto-injected from recipe.yaml:mcp.preferred_gpu)\n"
        "# This cell is inserted by tools/generate_notebook.py whenever the recipe\n"
        "# opts into MCP execution. It fails fast if Colab has silently allocated\n"
        "# a smaller GPU than the recipe expects.\n"
        "import torch, sys\n"
        "assert torch.cuda.is_available(), \"No CUDA device visible — select a GPU runtime.\"\n"
        f"expected = {preferred_gpu!r}\n"
        "name = torch.cuda.get_device_name(0)\n"
        "vram = torch.cuda.get_device_properties(0).total_memory / 1e9\n"
        "print(f\"GPU: {name}  |  VRAM: {vram:.1f} GB  |  expected: {expected}\")\n"
        "if expected and expected.lower() not in name.lower():\n"
        "    print(\n"
        "        f\"[warn] allocated {name!r} does not match mcp.preferred_gpu={expected!r}. \"\n"
        "        \"Colab downgrades under load. Consider Runtime > Change runtime type.\",\n"
        "        file=sys.stderr,\n"
        "    )\n"
        + vram_assert
    )
    return make_cell("code", source_to_lines(source))


def generate_notebook(recipe_name: str, out_path: Path | None = None) -> Path:
    repo = get_repo_root()
    recipe_dir = repo / "recipes" / recipe_name
    manifest_path = recipe_dir / "notebook_manifest.yaml"

    if not manifest_path.exists():
        print(f"ERROR: {manifest_path} not found")
        sys.exit(1)

    with open(manifest_path, encoding="utf-8") as f:
        manifest = yaml.safe_load(f)

    recipe_cfg = _load_recipe_yaml(recipe_dir)

    # Detect format: extended (has 'cells') vs legacy (has 'install'/'files'/'run')
    if "cells" in manifest:
        cells = generate_extended(manifest, recipe_dir)
    else:
        cells = generate_legacy(manifest, recipe_dir)

    # --- Auto-inject GPU preflight cell when the recipe opts into MCP ---
    # Rationale: A100→L4 silent downgrades bit the Ever team repeatedly. When
    # a recipe declares `mcp.enabled: true` and a `preferred_gpu`, we prepend
    # an assert cell so the mismatch is caught in Cell A instead of during
    # a 30-minute inference cell.
    mcp_cfg = (recipe_cfg.get("mcp") or {}) if isinstance(recipe_cfg, dict) else {}
    preferred_gpu = mcp_cfg.get("preferred_gpu")
    runtime_cfg = (recipe_cfg.get("runtime") or {}) if isinstance(recipe_cfg, dict) else {}
    vram_min_gb = runtime_cfg.get("vram_min_gb")
    if mcp_cfg.get("enabled") and preferred_gpu:
        cells.insert(0, _preferred_gpu_assert_cell(preferred_gpu, vram_min_gb))
        print(f"[generate_notebook] Injected preferred_gpu={preferred_gpu!r} preflight cell.")
    # Keepalive — inserted after the preflight so GPU checks happen first.
    if mcp_cfg.get("enabled") and mcp_cfg.get("keepalive"):
        insert_at = 1 if preferred_gpu else 0
        cells.insert(insert_at, _keepalive_cell())
        print("[generate_notebook] Injected keepalive cell (mcp.keepalive: true).")

    # GPU type from manifest or default
    gpu_type = manifest.get("gpu_type", "A100")
    # Colab gpuClass mapping: "premium" = A100/V100, "standard" = T4, "high-memory" = L4
    # Reference: Colab's own generated .ipynb metadata (as of 2026.04)
    gpu_class_map = {
        "A100": "premium",
        "V100": "premium",
        "L4": "premium",
        "T4": "standard",
        "CPU": "standard",
    }
    gpu_class = gpu_class_map.get(gpu_type, "premium")

    notebook = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
                "version": "3.10.0",
            },
            "colab": {
                "provenance": [],
                "gpuType": gpu_type,
            },
            "accelerator": "GPU",
            "gpuClass": gpu_class,
        },
        "cells": cells,
    }

    if out_path is None:
        out_dir = repo / "outputs" / "notebooks"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{recipe_name}.ipynb"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(notebook, f, indent=2, ensure_ascii=False)

    print(f"[generate_notebook] Written: {out_path}")
    # outputs/ is gitignored by default — surface this to avoid "where did my notebook go?" confusion
    try:
        rel = out_path.relative_to(repo)
        if str(rel).startswith("outputs"):
            print(f"[generate_notebook] NOTE: {rel.parts[0]}/ is gitignored — "
                  f"upload to Colab or copy to a tracked path if you want it versioned.")
    except ValueError:
        pass
    return out_path


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate Colab notebook from manifest")
    parser.add_argument("recipe", nargs="?", help="Recipe name")
    parser.add_argument("--recipe", dest="recipe_flag", help="Recipe name (alt)")
    parser.add_argument("--out", help="Output path")
    args = parser.parse_args()

    recipe_name = args.recipe or args.recipe_flag
    if not recipe_name:
        print("Usage: python tools/generate_notebook.py <recipe_name>")
        sys.exit(1)

    out_path = Path(args.out) if args.out else None
    generate_notebook(recipe_name, out_path)


if __name__ == "__main__":
    main()

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
    cells = []
    for cell_def in manifest.get("cells", []):
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


def generate_notebook(recipe_name: str, out_path: Path | None = None) -> Path:
    repo = get_repo_root()
    recipe_dir = repo / "recipes" / recipe_name
    manifest_path = recipe_dir / "notebook_manifest.yaml"

    if not manifest_path.exists():
        print(f"ERROR: {manifest_path} not found")
        sys.exit(1)

    with open(manifest_path, encoding="utf-8") as f:
        manifest = yaml.safe_load(f)

    # Detect format: extended (has 'cells') vs legacy (has 'install'/'files'/'run')
    if "cells" in manifest:
        cells = generate_extended(manifest, recipe_dir)
    else:
        cells = generate_legacy(manifest, recipe_dir)

    # GPU type from manifest or default
    gpu_type = manifest.get("gpu_type", "A100")

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
            },
            "accelerator": "GPU",
            "gpuClass": "standard",
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

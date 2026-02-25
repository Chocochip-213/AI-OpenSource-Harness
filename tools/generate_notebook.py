#!/usr/bin/env python3
"""Generate a Colab-ready notebook (.ipynb) from a recipe's notebook_manifest.yaml.

Usage:
    python tools/generate_notebook.py <recipe_name>
    python tools/generate_notebook.py --recipe swifttry --out outputs/notebooks/swifttry_A100.ipynb
"""

import argparse
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


def source_to_lines(source: str) -> list[str]:
    """Convert a source string to a list of lines for notebook format."""
    lines = source.split("\n")
    result = []
    for i, line in enumerate(lines):
        if i < len(lines) - 1:
            result.append(line + "\n")
        elif line:  # skip trailing empty line from YAML block scalar
            result.append(line + "\n")
    return result


def generate_notebook(recipe_name: str) -> dict:
    repo = get_repo_root()
    recipe_dir = repo / "recipes" / recipe_name
    manifest_path = recipe_dir / "notebook_manifest.yaml"

    if not manifest_path.exists():
        print(f"ERROR: {manifest_path} not found")
        sys.exit(1)

    with open(manifest_path, encoding="utf-8") as f:
        manifest = yaml.safe_load(f)

    cells = []

    # --- Title cell ---
    title = manifest.get("title", recipe_name)
    cells.append(make_cell("markdown", [
        f"# {title}\n",
        "\n",
        f"Auto-generated notebook for recipe: **{recipe_name}**\n",
    ]))

    # --- Extended cells format (preferred) ---
    custom_cells = manifest.get("cells", [])
    if custom_cells:
        for cell_def in custom_cells:
            ctype = cell_def.get("type", "code")
            source = cell_def.get("source", "")
            lines = source_to_lines(source)
            cells.append(make_cell(ctype, lines))
    else:
        # --- Legacy format: install / files / run ---
        install_deps = manifest.get("install", [])
        if install_deps:
            install_lines = ["# Install dependencies\n"]
            for dep in install_deps:
                install_lines.append(f"!pip install -q {dep}\n")
            cells.append(make_cell("code", install_lines))

        files = manifest.get("files", [])
        for file_entry in (files or []):
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

            writefile_lines = [f"%%writefile {dst}\n", content]
            cells.append(make_cell("code", writefile_lines))

        run_cmd = manifest.get("run", "")
        if run_cmd:
            cells.append(make_cell("markdown", ["## Run\n"]))
            cells.append(make_cell("code", [f"!{run_cmd}\n"]))

    # --- Assemble notebook ---
    notebook = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3"
            },
            "language_info": {
                "name": "python",
                "version": "3.10.0"
            },
            "colab": {
                "provenance": [],
                "gpuType": "A100",
            },
            "accelerator": "GPU",
        },
        "cells": cells,
    }
    return notebook


def main():
    parser = argparse.ArgumentParser(description="Generate Colab notebook from recipe manifest")
    parser.add_argument("recipe_name", nargs="?", help="Recipe name (positional)")
    parser.add_argument("--recipe", dest="recipe_flag", help="Recipe name (--recipe flag)")
    parser.add_argument("--out", dest="out_path", help="Output .ipynb path (optional)")
    args = parser.parse_args()

    recipe_name = args.recipe_flag or args.recipe_name
    if not recipe_name:
        parser.print_help()
        sys.exit(1)

    repo = get_repo_root()
    notebook = generate_notebook(recipe_name)

    if args.out_path:
        out_path = Path(args.out_path)
        if not out_path.is_absolute():
            out_path = repo / out_path
    else:
        out_dir = repo / "outputs" / "notebooks"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{recipe_name}.ipynb"

    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(notebook, f, indent=2, ensure_ascii=False)

    print(f"[generate_notebook] Written: {out_path.relative_to(repo)}")


if __name__ == "__main__":
    main()

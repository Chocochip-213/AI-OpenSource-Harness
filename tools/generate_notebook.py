#!/usr/bin/env python3
"""Generate a Colab-ready notebook (.ipynb) from a recipe's notebook_manifest.yaml.

Usage:
    python tools/generate_notebook.py <recipe_name>
    python tools/generate_notebook.py _template
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

    # --- Install cell ---
    install_deps = manifest.get("install", [])
    if install_deps:
        install_lines = ["# Install dependencies\n"]
        for dep in install_deps:
            install_lines.append(f"!pip install -q {dep}\n")
        cells.append(make_cell("code", install_lines))

    # --- %%writefile cells ---
    files = manifest.get("files", [])
    for file_entry in files:
        src = file_entry.get("src", "")
        dst = file_entry.get("dst", src)
        desc = file_entry.get("description", "")

        # Description cell
        if desc:
            cells.append(make_cell("markdown", [f"## {desc}\n"]))

        # Read source file
        src_path = recipe_dir / src
        if src_path.exists():
            content = src_path.read_text(encoding="utf-8")
        else:
            content = f"# TODO: create {src}\n"

        writefile_lines = [f"%%writefile {dst}\n", content]
        cells.append(make_cell("code", writefile_lines))

    # --- Run cell ---
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
                "provenance": []
            }
        },
        "cells": cells,
    }
    return notebook


def main():
    if len(sys.argv) < 2:
        print("Usage: python tools/generate_notebook.py <recipe_name>")
        sys.exit(1)

    recipe_name = sys.argv[1]
    repo = get_repo_root()

    notebook = generate_notebook(recipe_name)

    out_dir = repo / "outputs" / "notebooks"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{recipe_name}.ipynb"

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(notebook, f, indent=2, ensure_ascii=False)

    print(f"[generate_notebook] Written: {out_path.relative_to(repo)}")


if __name__ == "__main__":
    main()

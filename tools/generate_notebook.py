#!/usr/bin/env python3
"""Generate a Colab-ready notebook (.ipynb) from a recipe's notebook_manifest.yaml.

Supports two manifest formats:
  - Extended: cells list with type/source (recommended)
  - Legacy: install/files/run sections

Usage:
    python tools/generate_notebook.py <recipe_name>
    python tools/generate_notebook.py --recipe <name> --out <path>
"""

import hashlib
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


def _stable_cell_id(recipe: str, name: str, index: int) -> str:
    """Deterministic cell id derived from (recipe, name, index).

    JEP 62 (nbformat 4.5+) requires `id` matching `[A-Za-z0-9_-]{1,64}`.
    A short hex digest stays within that range and means: same manifest →
    byte-identical notebook → 6-person team merge stays clean. Without
    this, JupyterLab/Colab assign a random UUID on every save and the
    `colab_mcp_sync.py` align falls back to name-only matching, which
    turns every rename into add+remove.
    """
    seed = f"{recipe}|{name or ''}|{index}"
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]


def make_cell(
    cell_type: str,
    source: list[str],
    metadata: dict | None = None,
    cell_id: str | None = None,
) -> dict:
    """Create a single notebook cell. `cell_id` is the JEP 62 id; pass it
    in deterministically (see `_stable_cell_id`) so notebooks are
    reproducible across team members."""
    cell = {
        "cell_type": cell_type,
        "metadata": metadata or {},
        "source": source,
    }
    if cell_id:
        cell["id"] = cell_id
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
    recipe_name = recipe_dir.name
    cells = []
    for index, cell_def in enumerate(cell_defs):
        cell_type = cell_def.get("type", "code")
        source = cell_def.get("source", "")
        metadata = cell_def.get("metadata", {})

        if cell_type not in ("code", "markdown"):
            cell_type = "code"

        # cell_id from manifest if explicit, else deterministic from
        # (recipe, name, index). Stable across regenerations → diff-friendly.
        cell_id = cell_def.get("cell_id") or _stable_cell_id(
            recipe_name, cell_def.get("name", ""), index
        )

        lines = source_to_lines(source)
        cells.append(make_cell(cell_type, lines, metadata, cell_id=cell_id))
    return cells


def generate_legacy(manifest: dict, recipe_dir: Path) -> list[dict]:
    """Generate cells from legacy format (install/files/run)."""
    if not any(manifest.get(k) for k in ("install", "files", "run")):
        raise ValueError(
            "notebook_manifest.yaml (legacy format) has no 'install', 'files', or 'run' section — "
            "nothing to generate. Add at least one section or switch to extended format (cells list)."
        )
    recipe_name = recipe_dir.name
    cells = []
    idx = 0  # deterministic cell-id index across legacy sections

    def _add(cell_type: str, source: list[str], name: str) -> None:
        nonlocal idx
        cells.append(make_cell(
            cell_type, source,
            cell_id=_stable_cell_id(recipe_name, name, idx),
        ))
        idx += 1

    # Title
    title = manifest.get("title", recipe_dir.name)
    _add("markdown", [
        f"# {title}\n", "\n",
        f"Auto-generated notebook for recipe: **{recipe_dir.name}**\n",
    ], "title")

    # Install
    install_deps = manifest.get("install", [])
    if install_deps:
        install_lines = ["# Install dependencies\n"]
        for dep in install_deps:
            install_lines.append(f"!pip install -q {dep}\n")
        _add("code", install_lines, "install")

    # Files (%%writefile)
    for file_entry in manifest.get("files", []):
        src = file_entry.get("src", "")
        dst = file_entry.get("dst", src)
        desc = file_entry.get("description", "")

        if desc:
            _add("markdown", [f"## {desc}\n"], f"file-desc:{dst}")

        src_path = recipe_dir / src
        if src_path.exists():
            content = src_path.read_text(encoding="utf-8")
        else:
            content = f"# TODO: create {src}\n"

        _add("code", [f"%%writefile {dst}\n", content], f"file:{dst}")

    # Run
    run_cmd = manifest.get("run", "")
    if run_cmd:
        _add("markdown", ["## Run\n"], "run-header")
        _add("code", [f"!{run_cmd}\n"], "run")

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
    # Use a fixed cell_id so this auto-injected cell stays at the same id
    # across regenerations (sync diff stability).
    return make_cell("code", source_to_lines(source),
                     cell_id="auto-keepalive")


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
    # Fixed cell_id so this auto-injected preflight stays at the same id
    # across regenerations.
    return make_cell("code", source_to_lines(source),
                     cell_id="auto-gpu-preflight")


def _gradio_serve_cell(recipe_name: str) -> dict:
    """Inject a final cell that wraps `exports/inference_handler.infer()` in
    a Gradio Interface and launches with `share=True`. Output: a public
    `https://xxxx.gradio.live` URL that the Spring backend reads from the
    `AI_GRADIO_URL` env var (see exports/INTEGRATION_BACKEND.md).

    Free Gradio shares last 72h or until the Colab kernel dies, whichever
    is first. Whenever the user re-runs Colab, a new URL is printed —
    they update the backend env. We DON'T auto-publish the URL here
    because that would require a Slack/webhook secret in the notebook,
    which would commit to the repo.
    """
    source = (
        "#@title Z) Gradio serve (auto-injected — mcp.serve_via_gradio: true)\n"
        "# Wraps exports/inference_handler.infer() in a Gradio Interface and\n"
        "# prints a public share URL that the Spring backend reads from\n"
        "# AI_GRADIO_URL. See exports/INTEGRATION_BACKEND.md for the contract.\n"
        "import sys, os, importlib, subprocess\n"
        "# Install gradio if missing — Colab usually has it preinstalled.\n"
        "try:\n"
        "    import gradio as gr\n"
        "except ImportError:\n"
        "    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'gradio'], check=True)\n"
        "    import gradio as gr\n"
        "\n"
        "# Load the recipe's inference handler. We expect exports/ to be in\n"
        "# the same directory as this notebook when uploaded to Colab; for\n"
        "# the in-Colab case we sys.path.insert the recipe directory.\n"
        f"_RECIPE_DIR = os.path.join(os.getcwd(), 'recipes', {recipe_name!r}, 'exports')\n"
        "if os.path.isdir(_RECIPE_DIR) and _RECIPE_DIR not in sys.path:\n"
        "    sys.path.insert(0, _RECIPE_DIR)\n"
        "\n"
        "try:\n"
        "    from inference_handler import infer\n"
        "except Exception as e:\n"
        "    print(f'[gradio_serve] could not import exports/inference_handler.py: {e}')\n"
        "    print('[gradio_serve] Stub: replace exports/inference_handler.py with your real handler.')\n"
        "    def infer(*args, **kwargs):\n"
        "        return {'echo': args, 'kwargs': kwargs}\n"
        "\n"
        "# Single-input fallback signature; recipe authors should customize.\n"
        "# api_name='predict' makes the Gradio 4+/5.x HTTP endpoint predictable:\n"
        "#   POST  <share>/call/predict          -> {'event_id': '...'}\n"
        "#   GET   <share>/call/predict/<event>  -> SSE stream (msg=process_completed)\n"
        "# The Spring side follows exactly that two-step flow — see\n"
        "# exports/INTEGRATION_BACKEND.md for the client snippet.\n"
        f"_iface = gr.Interface(fn=infer, inputs='text', outputs='json', title={recipe_name!r}, api_name='predict')\n"
        "_app, _local_url, _share_url = _iface.launch(share=True, prevent_thread_lock=True, quiet=True)\n"
        "print(f'AI_GRADIO_URL = {_share_url}')\n"
        "print('Copy that URL into the backend\\'s AI_GRADIO_URL env var.')\n"
        "print(f'Backend should POST to {_share_url}/call/predict — see exports/INTEGRATION_BACKEND.md.')\n"
    )
    return make_cell("code", source_to_lines(source),
                     cell_id="auto-gradio-serve")


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
    # Gradio serving cell — appended at the end so all the recipe's setup
    # cells run first, then the handler is wrapped and the share URL printed.
    if mcp_cfg.get("enabled") and mcp_cfg.get("serve_via_gradio"):
        cells.append(_gradio_serve_cell(recipe_name))
        print("[generate_notebook] Injected Gradio serve cell (mcp.serve_via_gradio: true).")
        print("[generate_notebook] Injected keepalive cell (mcp.keepalive: true).")

    # GPU type resolution order (SSOT-first):
    #   1. notebook_manifest.yaml:gpu_type — explicit override wins
    #   2. recipe.yaml:mcp.preferred_gpu  — what MCP is about to assert against
    #   3. recipe.yaml:runtime.gpu        — declared runtime target
    #   4. "A100" fallback
    # Prevents drift where the recipe says "T4" but the notebook metadata
    # quietly recommends A100 because no one set manifest.gpu_type.
    _mcp_pref = mcp_cfg.get("preferred_gpu") if isinstance(mcp_cfg, dict) else None
    _rt_gpu = runtime_cfg.get("gpu") if isinstance(runtime_cfg, dict) else None
    gpu_type = (
        manifest.get("gpu_type")
        or _mcp_pref
        or _rt_gpu
        or "A100"
    )
    # Colab gpuClass mapping is just metadata that seeds the notebook's
    # default suggestion — the USER always picks the actual runtime in
    # Runtime > Change runtime type. Exact options shown there depend on
    # the user's Colab tier and can change whenever Google updates the
    # product, so we intentionally do not enforce a closed list anywhere.
    # Known-standard: T4, CPU.  Everything else → premium.
    _STANDARD_GPUS = {"T4", "CPU"}
    gpu_class = "standard" if str(gpu_type).upper() in _STANDARD_GPUS else "premium"

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

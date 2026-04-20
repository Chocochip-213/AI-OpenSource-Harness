---
name: notebook-builder
description: Use when the user wants to generate, edit, or regenerate a Colab notebook, mentions notebook_manifest.yaml, asks to add/modify/reorder cells, runs tools/generate_notebook.py, or edits outputs/notebooks/*.ipynb. Supports both extended format (cells list with type/source) and legacy format (install/files/run). Validates that cells list is non-empty before generation and injects fail-fast verification patterns (idempotent cells, pipeline caching, assert-after-replace) learned from real portings.
allowed-tools: Read Edit Write Bash
---

# Skill: notebook-builder

## When Active
Triggered when generating, editing, or debugging Colab notebooks.

## Manifest Formats

### Extended Format (recommended for complex recipes)
Each cell is explicitly defined with type and source:
```yaml
title: "My Recipe"
description: "Description"
gpu_type: "A100"  # Sets Colab GPU accelerator metadata

cells:
  - name: "A) GPU Check"
    type: code
    source: |
      import torch
      print(torch.cuda.get_device_name(0))

  - name: "## Setup"
    type: markdown
    source: "Install dependencies and clone repo"

  - name: "B) Install"
    type: code
    source: |
      !pip install -q transformers accelerate
```

### Legacy Format (simple recipes)
```yaml
title: "My Recipe"
install:
  - package1
  - package2>=1.0
files:
  - src: main.py
    dst: main.py
run: "python main.py"
```

## Commands
```bash
uv run python tools/generate_notebook.py <recipe-name>
# Output: outputs/notebooks/<recipe-name>.ipynb
```

## Rules
- Update `notebook_manifest.yaml` before regenerating.
- Extended format: cell names starting with `##` become markdown cells.
- `gpu_type` sets the notebook's accelerator metadata (T4, A100, etc.).
- For legacy format: every file in `files:` must exist under the recipe directory.

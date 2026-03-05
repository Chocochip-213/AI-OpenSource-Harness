# AI Open-Source Harness - Codex Agent Guide

## Purpose
This repository was originally set up with Claude-oriented hooks under `.claude/`.
Codex should use the same source-of-truth workflow and scripts directly.

## Startup Checklist
1. Read `.claude/last_recipe.txt` to identify the active recipe.
2. Run `uv run python scripts/make_context_pack.py`.
3. Read the active recipe docs triad:
   - `recipes/<recipe>/docs/plan.md`
   - `recipes/<recipe>/docs/context.md`
   - `recipes/<recipe>/docs/tasks.md`

## Working Rules
1. Keep recipe docs as SSOT.
2. After meaningful progress, update `recipes/<recipe>/docs/tasks.md`.
3. Keep generated notebook outputs tied to `notebook_manifest.yaml` or `recipe.yaml`.
4. Run smoke checks before finishing:
   - `uv run python scripts/smoke_test.py`
   - Optional: `python -m compileall -q .`

## Useful Commands
- Rebuild context pack: `uv run python scripts/make_context_pack.py`
- Smoke test: `uv run python scripts/smoke_test.py`
- Generate notebook: `uv run python tools/generate_notebook.py <recipe>`

## Windows Convenience
Use `scripts/bootstrap_codex.ps1` for one-step startup and optional smoke test.

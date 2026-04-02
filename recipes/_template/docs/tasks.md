# Tasks

## Setup
- [ ] Copy _template → `recipes/<name>/`
- [ ] Update `recipe.yaml` (model repo, GPU, Python, runtime version)
- [ ] Write `docs/plan.md` (goal, scope, target env)
- [ ] Check `colab-runtimes/SUMMARY.md` for dependency compatibility
- [ ] Check `docs/COMMON_ERRORS.md` for known issues with this model's deps

## Implementation
- [ ] `notebook_manifest.yaml` Cell A: GPU check
- [ ] `notebook_manifest.yaml` Cell B: Dependencies install
- [ ] `notebook_manifest.yaml` Cell C: Fail-fast verification (import all critical deps)
- [ ] `notebook_manifest.yaml` remaining cells: Model load, inference, output
- [ ] `requirements_opt1.txt` — Colab-compatible deps

## Validation
- [ ] `generate_notebook.py` succeeds
- [ ] `smoke_test.py` passes
- [ ] Colab Cell A-C: GPU + deps + verification pass
- [ ] Colab full pipeline: End-to-end success
- [ ] Record metrics in `context.md` (time, VRAM, output quality)
- [ ] Add any new errors to `docs/COMMON_ERRORS.md`

## If Direct pip Fails
<!-- Uncomment the relevant section when strategy changes:

### v2: Runtime Rollback
- [ ] Identify target runtime from SUMMARY.md
- [ ] Test on target runtime
- [ ] Document runtime requirement in Cell A

### v2: Conda Isolation
- [ ] Read docs/PORTING_PATTERNS.md §3 (Conda Isolation)
- [ ] Redesign Cell B for condacolab
- [ ] Add Cell C for conda verification
- [ ] Patch upstream scripts for _MODEL_PYTHON
- [ ] Test on target runtime (2025.07 for Python 3.11)

### v2: Shim / Patch
- [ ] Identify failing build (flash-attn, xformers, etc.)
- [ ] Read docs/PORTING_PATTERNS.md §4 (Shim)
- [ ] Implement shim with all import surfaces covered
- [ ] Create .dist-info metadata if needed
- [ ] Patch model config (assert after replace)
-->

---
> Check off immediately after completing each item.
> When strategy changes (e.g., v1 direct pip → v2 conda), keep v1 items checked
> and add v2 section below — the history of what failed is valuable.
> Decisions → `context.md`. Errors → `context.md` Discovered Issues table.

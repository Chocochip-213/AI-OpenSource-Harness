# Plan

## Goal
<!-- ONE sentence describing input → output. Be concrete.
Good examples (from real portings):
  - "Single photo → rigged GLB avatar via SAM 3D Body + MHR (trellis2)"
  - "Single mesh + skeleton → skinned animation via UniRig diffusion (unirig)"
  - "Person photo + garment image → try-on render via FLUX-VTON (vton-flux)"
Bad:
  - "Run the model" (too vague — missing I/O + approach)
  - "Test the new 4B multimodal model with SOTA results" (marketing speak, no I/O)
-->

## Scope
**In scope**
-
-

**Out of scope**
-
-
<!-- Be explicit — what you WON'T do. Common out-of-scope:
  - Training (Stage 1/2) — inference only
  - Multi-GPU / distributed — single Colab GPU
  - Custom model fine-tuning
  - Web UI / Gradio demo (Colab cells only)
  - Mobile / edge deployment
-->

## Target Environment
| Item | Value | Reason |
|------|-------|--------|
| GPU  | A100  | VRAM ≥ 24GB for 4B model fp16 |
| VRAM | 40GB  | Peak during diffusion step (measured) |
| Python | 3.11 | condacolab requires 3.11 → runtime 2025.07 |
| Colab Runtime | 2025.07 | torch 2.6.0+cu124 matches upstream pin |
| Extra deps | spconv, nvdiffrast | C extensions — conda isolation needed |

<!-- Runtime selection is CONSTRAINT-DRIVEN. Check colab-runtimes/SUMMARY.md.
Decision rules:
  - Model needs Python 3.11 + conda → MUST use 2025.07
  - Model works with Python 3.12, no conda → use latest (2026.01+)
  - Model requires torch >= 2.9 → use 2026.01 or 2026.04
  Document the REASON, not just the value. Ever lesson:
  "just use latest" caused 3-day debugging when conda broke on Python 3.12.
-->

## Approach
<!-- Cell-level plan. Mark dependencies between cells. -->
1. Cell A — GPU check + VRAM assert (fail fast if insufficient)
2. Cell B — Install deltas only (NOT packages already in Colab stock)
3. Cell C — Fail-fast verification: import EVERY critical dep, assert CUDA + VRAM
4. Cell D — Clone upstream at pinned SHA, apply compat-patches (with `assert` after each replace)
5. Cell E — Load model (cache in `globals()` for cell re-run safety)
6. Cell F — Inference + save/download output

## Fallback Strategies
<!-- Which strategies are pre-authorized if v1 (Direct pip) fails?
Check any that are plausible given your deps. See tasks.md v2 section. -->
- [ ] v2a: Runtime Rollback (for torch/Python version mismatch)
- [ ] v2b: Selective Downgrade + Patch (for one version-sensitive package)
- [ ] v2c: Shim / Monkey-patch (for flash-attn, xformers, nvdiffrast build fail)
- [ ] v2d: Conda Isolation (for multi-C-extension ABI conflict — LAST RESORT)

## Success Criteria
- [ ] `generate_notebook.py <name>` succeeds (non-empty cells)
- [ ] `smoke_test.py` passes locally
- [ ] Colab cells run sequentially without error (on cold fresh runtime)
- [ ] Fail-fast cell C catches missing deps BEFORE model load (not 30min later)
- [ ] Model load succeeds + VRAM peak recorded
- [ ] Input → output verified with metrics in `context.md`:
  - [ ] Cold-start time (minutes)
  - [ ] VRAM peak (GB)
  - [ ] Output quality (visual check or metric)
  - [ ] Cost estimate (A100 hour rate × time)

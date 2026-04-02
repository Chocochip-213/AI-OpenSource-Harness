# Plan

## Goal
<!-- One sentence: what does this recipe achieve?
Example: "Single photo → rigged GLB avatar via SAM 3D Body + MHR" -->

## Scope
**In scope**
-
**Out of scope**
-
<!-- Be explicit. Common out-of-scope items:
  - Training (Stage 1/2) — inference only
  - Multi-GPU / distributed — single Colab GPU
  - Custom model fine-tuning
-->

## Target Environment
| Item | Value | Reason |
|------|-------|--------|
| GPU  |       |        |
| VRAM |       |        |
| Python |     |        |
| Colab Runtime |  | <!-- Check colab-runtimes/SUMMARY.md --> |

<!-- Runtime selection is CONSTRAINT-DRIVEN:
  - If model needs Python 3.11 → use 2025.07
  - If model works with 3.12 → use latest (2026.01)
  - If conda needed and Python 3.12 → MUST use 2025.07
  Document the reason for runtime choice.
-->

## Approach
1. GPU check + environment verification
2. Dependencies install
3. Fail-fast dependency verification
4. Clone upstream / download model
5. Load model + inference
6. Output + download

## Success Criteria
- [ ] Notebook generates (`generate_notebook.py`)
- [ ] Colab cells run sequentially without error
- [ ] Model import + weight load succeeds
- [ ] Input → output verified (with metrics: time, VRAM, quality)

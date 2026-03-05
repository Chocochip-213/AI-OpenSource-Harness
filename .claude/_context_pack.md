# Context Pack

**Active Recipe**: `trellis-colab`
**Generated**: auto

## Recipe Docs

### plan.md

```
# Plan

## Goal
Build a TRELLIS.2-focused Colab recipe incrementally, using strict checkpoints.
Each checkpoint must be validated locally first, then verified on Colab when GPU/runtime evidence is required.

## Scope
In scope:
- CP0 recipe scaffold and SSOT docs
- CP1 Colab bootstrap and runtime diagnostics
- CP2 TRELLIS minimum inference PoC
- CP3 output artifact validation
- CP4 post-process MVP (optimization-first subset)
- CP5 notebook-manifest integration
- CP6 repeatable runbook and handoff checklist

Out of scope for initial passes:
- Full production backend integration
- Full WebAR runtime implementation
- Fine-tuning TRELLIS models

## Approach
1. Use `../TrellisDocs` as planning/research source.
2. Keep this recipe docs triad as implementation SSOT.
3. Execute one checkpoint at a time.
4. For each checkpoint:
   - Agent local pre-check
   - User Colab run (if runtime/GPU proof required)
   - Gate decision to proceed
5. Update `tasks.md` immediately after each checkpoint.

## Success Criteria
- Every checkpoint has explicit pass/fail criteria.
- Colab-only checkpoints include user-provided evidence:
  - executed cells
  - tail logs
  - output file listing
  - screenshot(s) when needed
- Final notebook can be executed end-to-end in Colab with documented fallback steps.
```

### context.md

```
# Context

## Architecture
Planned recipe flow:
1. Colab runtime bootstrap and hardware verification
2. Dependency install and version sanity check
3. TRELLIS.2 minimum inference run
4. Output artifact checks (GLB/PBR/filesize/basic validity)
5. Optional post-processing step
6. Notebook manifest wiring for reproducible generation

## Dependencies
Baseline:
- Python 3.11/3.12 (Colab default may change)
- torch / torchvision / torchaudio (GPU build)
- transformers
- diffusers (if needed for helper utilities)
- huggingface-hub
- safetensors

Potential post-process:
- Blender (headless batch path, optional)
- gltf-transform (Draco/KTX2 optimization path)

## Key Decisions
- Checkpoint-first execution model: no monolithic implementation.
- Colab runtime drift is expected:
  - `../TrellisDocs/research/colab-snippet.txt` shows frequent package upgrades.
  - We treat Colab base packages as unstable and verify versions at runtime.
- GPU target for this recipe:
  - Primary: RTX 6000 Blackwell class (reported ~94GB VRAM in user environment)
  - Fallback: A100/H100 class with equivalent memory headroom
- CP gate policy:
  - If a checkpoint fails, do not proceed to the next checkpoint until fixed or explicitly waived.
- CP1 dependency policy:
  - Prefer "install missing only" baseline first.
  - Avoid broad upgrades before runtime snapshot to reduce Colab breakage risk.
- CP2 inference policy:
  - Follow official TRELLIS.2 API path (`Trellis2ImageTo3DPipeline.from_pretrained(...).run(image)`).
  - Use deterministic output root: `/content/trellis_cp_outputs/cp2`.
  - Treat GLB export as optional in CP2; allow partial success if inference works but export binding is unavailable.
- CP2 install policy (2026-03-05 update):
  - Do not use `pip install -e .` at TRELLIS.2 repo root because upstream repo has no root `pyproject.toml/setup.py`.
  - Clone with `--recursive` and run `git submodule update --init --recursive` to ensure `o-voxel/third_party/eigen` is present.
  - Install `o_voxel` from local source (`pip install --no-build-isolation ./o-voxel`) so `cumesh` and `flex_gemm` dependencies are provisioned for mesh decode.
  - Add `/content/TRELLIS.2` to `PYTHONPATH` for direct module import (`trellis2`).
  - Force attention backend to `xformers` (fallback: `flash_attn`) to avoid default backend mismatch.
- CP2 model access policy (2026-03-05 update):
  - Upstream `microsoft/TRELLIS.2-4B/pipeline.json` references gated repos in some runtimes (`facebook/dinov3-vitl16-pretrain-lvd1689m`, `briaai/RMBG-2.0`).
  - At runtime, write a local patched `pipeline.json` that:
    - prefixes relative `ckpts/...` paths with `microsoft/TRELLIS.2-4B/`
    - overrides gated DINOv3 model to a public fallback (`camenduru/dinov3-vitl16-pretrain-lvd1689m`) when weights are present
    - if DINOv3 fallback is unavailable, switch extractor to `DinoV2FeatureExtractor(dinov2_vitl14)` as hard fallback
    - overrides gated RMBG-2.0 to a public fallback (`ZhengPeng7/BiRefNet`)
- CP2 native extension policy (2026-03-05 update):
  - `o_voxel` import may transitively require `nvdiffrast` even before postprocess is used.
  - CP2 first attempts `nvdiffrast` install; if unavailable, it creates a runtime stub so core inference can proceed.
  - In stub mode, GLB export is best-effort and may end as `partial_success_no_glb` (acceptable for CP2 gate).
- CP2 rembg stability policy (2026-03-05 update):
  - BiRefNet can hit mixed-precision mismatch on Colab (`Input type float vs bias half`) during preprocessing.
... (88 more lines)

```

### tasks.md

```
# Tasks

## CP0 - Scaffold and Planning
- [x] Create `recipes/trellis-colab` from template
- [x] Update `recipe.yaml` metadata for TRELLIS Colab target
- [x] Fill `docs/plan.md`
- [x] Fill `docs/context.md`
- [x] Fill `docs/tasks.md` with checkpoint gates

## CP1 - Colab Bootstrap
- [x] Add Colab environment check cell set (GPU, CUDA, VRAM, Python, torch)
- [x] Add dependency install strategy (pin vs compatible range)
- [x] Add runtime version report artifact cell
- [x] Local static validation of notebook manifest structure
- [x] User Colab run and evidence collection

## CP2 - TRELLIS Minimum Inference PoC
- [x] Add minimal TRELLIS inference path (single sample)
- [x] Define deterministic output folder and filenames
- [x] Add failure handling and retry hints
- [x] Local lint/sanity check
- [x] Patch CP2 install flow for Python 3.12 (`pip -e .` 제거, recursive clone + `o_voxel` local install + `PYTHONPATH` import)
- [x] Fix optional GLB export call to current `o_voxel.postprocess.to_glb(...)` signature
- [x] Fix CP2 image upload path resolution when working directory is changed (e.g., `/content/TRELLIS.2`)
- [x] Fix CP2 inference call for latest TRELLIS.2 API (`from_pretrained(..., token=...)` 제거)
- [x] Add CP2 workaround for TRELLIS model loader relative `ckpts/...` fallback path issue
- [x] Add CP2 runtime pipeline patch for gated dependency repos (DINOv3/RMBG) with public fallbacks
- [x] Add CP2 fallback path for missing `nvdiffrast` (install attempt + runtime stub for inference-only mode)
- [x] Make CP2-5 self-heal `nvdiffrast` stub injection so rerun works without repeating CP2-2
- [x] Harden CP2 DINO fallback (use public DINOv3 mirror when weights exist; auto-fallback to DINOv2 extractor)
- [x] Add CP2 rembg mixed-precision recovery (fp32 cast + preprocess off fallback)
- [x] Add CP2 anti-logo-hallucination preprocess (rembg matte + LAB stroke mask + CC filtering + inpaint) and prefer `input_clean.png`
- [x] Align CP2-4b with local proven pipeline (`AR_VTON_PROTOTYPE/services/inference/preprocess_garment.py`: LAB median outlier + garment-interior erode + CC filtering + inpaint)
- [x] Redesign CP2 NumPy integrity flow (subprocess-only probe + hard clean + pinned NumPy + mandatory one-time runtime restart after repair)
- [x] Remove default forced NumPy downgrade; keep version unless integrity probe fails (optional strict pin via `TRELLIS_NUMPY_PIN`)
- [x] Add CP2 transformers stack integrity guard (pin `transformers==4.57.3` / `huggingface_hub==0.36.0`, probe `GenerationMixin` + `AutoModelForImageSegmentation`, restart after repair)
- [x] Add CP2 runtime monkeypatch safety net for NumPy symbol gaps (`_blas_supports_fpe`, `_center`) plus in-kernel import integrity gate
- [x] Add CP2 `TRELLIS_SKIP_RMBG` default path (identity rembg patch + skip `rembg/onnxruntime` install for manual-logo workflow)
- [x] Remove unconditional post-repair stop in CP2-2; continue automatically after repair when in-kernel integrity gate passes
- [x] Add CP2 rembg backend self-heal (`onnxruntime-gpu` -> `onnxruntime` fallback) and guard rembg `SystemExit` with `BaseException`
- [x] Align CP2-5 quality defaults with official TRELLIS.2 behavior (`pipeline_type`, 3-stage sampler config) and high-quality GLB export defaults (`decimation_target=1,000,000`, `texture_size=4096`, `remesh=True`)
- [x] Remove in-notebook logo preprocessing/projection path (`CP2-4b` + `CP4`) and keep Colab flow as pure inference/export
- [x] User Colab run and evidence collection

## CP3 - Output Validation
- [x] Add artifact validation script/cell (existence, size, basic integrity)
- [x] Add summary report table (pass/fail)
- [x] Local test with mock artifacts
- [ ] User Colab validation run

## CP4 - Post-process MVP
- [x] Select minimal post-process subset for MVP checkpoint
- [x] Add executable path (with fallback if unavailable)
- [x] Add quality/performance measurement hooks
- [ ] User Colab run if GPU/runtime dependent

## CP5 - Harness Integration
- [x] Build `notebook_manifest.yaml` for trellis-colab
- [x] Verify notebook generation via `tools/generate_notebook.py`
- [x] Smoke test generated notebook structure
... (15 more lines)

```

## Git Status

```
M .claude/_context_pack.md
 M .claude/last_recipe.txt
?? .gitignore
?? AGENTS.md
?? outputs/notebooks/trellis-colab.ipynb
?? recipes/trellis-colab/
?? scripts/bootstrap_codex.ps1
```

## Git Diff (stat)

```
.claude/_context_pack.md | 341 ++++++++++++++++++++++-------------------------
 .claude/last_recipe.txt  |   2 +-
 2 files changed, 164 insertions(+), 179 deletions(-)
```

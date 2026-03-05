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
- [ ] User end-to-end Colab execution

## CP6 - Runbook Finalization
- [ ] Write execution order and failure matrix
- [ ] Freeze evidence format for each checkpoint
- [ ] Final pass on docs consistency

## Validation
- [x] `uv run python scripts/make_context_pack.py`
- [x] `uv run python scripts/smoke_test.py`
- [x] Confirm checkpoint gate criteria in docs triad

---

> Rule: Check tasks immediately after completion.

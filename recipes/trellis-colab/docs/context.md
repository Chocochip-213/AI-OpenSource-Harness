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
  - Before inference, force rembg model weights to fp32.
  - If preprocessing still fails, retry inference with `preprocess_image=False` and record fallback in report.
- CP2 NumPy runtime drift policy (2026-03-05 update):
  - Colab can surface NumPy file-mix corruption (`ImportError: cannot import name '_center' from numpy._core.umath`) after dependency churn.
  - In CP2-2, default behavior is integrity-first (no forced version pin).
  - Optional strict pin is supported via `TRELLIS_NUMPY_PIN`; repair target fallback can be overridden with `TRELLIS_NUMPY_REPAIR_TARGET` (default `2.4.2`).
  - Repair flow uses hard cleanup: `pip uninstall numpy` + physical purge of stale `numpy*` site-packages entries + pinned reinstall.
  - Probe is subprocess-only (`from numpy._core.umath import _center`) to avoid false negatives from polluted in-kernel module state.
  - If repair occurs, CP2-2 stops and requires one runtime restart before continuing.
- CP2 rembg backend policy (2026-03-05 update):
  - `rembg` requires ONNX Runtime; missing backend can raise `ModuleNotFoundError: onnxruntime` and sometimes `SystemExit`.
  - In CP2-2, install backend with fallback order: `onnxruntime-gpu` -> `onnxruntime`.
  - In CP2-4b / CP4 bbox extraction, catch `BaseException` (not only `Exception`) around rembg calls to avoid kernel-abort behavior and fallback to safe defaults.
- CP2 transformers compatibility policy (2026-03-05 update):
  - Colab base image may carry `transformers` major updates (including 5.x) that break TRELLIS.2 transitive imports.
  - Align CP2 to official TRELLIS.2 Space pin: `transformers==4.57.3` and `huggingface_hub==0.36.0`.
  - Add subprocess integrity probe importing `GenerationMixin` and `AutoModelForImageSegmentation`; on failure force-reinstall pinned stack and require one runtime restart.
- CP2 runtime monkeypatch policy (2026-03-05 update):
  - Add last-resort in-kernel monkeypatches for known binary-mix symbol gaps:
    - `numpy._core._multiarray_umath._blas_supports_fpe` fallback shim (`False` callable/bool)
    - `numpy._core.umath._center` Python vectorized fallback
  - Apply patches before TRELLIS import and run in-kernel integrity check (`GenerationMixin`, `AutoModelForImageSegmentation`) to fail fast with explicit restart guidance.
- CP2 rembg bypass policy (2026-03-05 update):
  - Default to `TRELLIS_SKIP_RMBG=1` for Colab stability when logo/background is handled externally.
  - In skip mode:
    - do not install `rembg` / `onnxruntime` stack
    - patch `trellis2/pipelines/rembg/__init__.py` to identity `BiRefNet` fallback
    - run transformers integrity check without `AutoModelForImageSegmentation`
  - This keeps image-to-3D generation path active while avoiding the most fragile segmentation dependency chain.
- CP2 repair-flow update (2026-03-05 update):
  - After NumPy/Transformers repair, CP2-2 no longer hard-stops immediately.
  - It continues with in-kernel sanitation (`sys.modules` purge + monkeypatch + import integrity gate) and only asks for restart if this gate still fails.
- CP2 anti-logo hallucination policy (2026-03-05 update):
  - Add optional preprocess cell (`CP2-4b`) that follows the local proven logic used in `AR_VTON_PROTOTYPE/services/inference/preprocess_garment.py`:
    - rembg alpha matte (`u2net`) for garment region
    - LAB distance from garment median color to detect logo/graphic outliers
    - heavy garment-interior erode to suppress edge/background false positives
    - morphology + connected-components area filtering
    - OpenCV inpaint (Telea), then optional white-background composite
  - Save `input_clean.png` and `logo_mask.png`; CP2 inference prefers cleaned input when present.
  - This is tuned for garment/logo suppression and can be disabled when preserving small printed details is more important.
- CP2 simple-inference variant (2026-03-05 update):
  - For stable Colab execution, logo handling is moved out of notebook scope.
  - `CP2-4b` is a no-op placeholder and inference input is fixed to `CP2_INPUT/input.png`.
  - User workflow: preprocess/logo-clean locally -> upload final image -> run TRELLIS inference/export only.
- TRELLIS.2 capability scope (2026-03-05 research note):
  - Official TRELLIS.2 4B model card/API is image-conditioned generation (`Input: Single Image`) and mesh-conditioned texturing.
  - Prompt-driven text-to-3D and multi-image fusion are not exposed as official default API in TRELLIS.2; community forks/spaces implement custom multi-image methods (`run_multi_image`) as non-official extensions.
- CP3 validation policy (2026-03-05 update):
  - Validate `cp2_report.json`, `mesh_stats.json`, input image presence, and GLB basic integrity (header/version/size) when GLB is required.
  - CP3 gate accepts CP2 statuses: `success`, `partial_success_no_glb`, `inference_ok`.
  - Reference validator script: `recipes/trellis-colab/tools/validate_cp3_artifacts.py`.
- CP4 logo projection policy (2026-03-05 update):
  - Add CP4 cells to project source-image logo back to UV texture space and export `composite_logo_projected.glb`.
  - UV source priority: existing GLB UV -> xatlas (if available) -> planar fallback.
  - Logo mask priority: `CP2-4b` output (`logo_mask.png`) -> diff(`input.png`, `input_clean.png`) fallback.
  - Front-face orthographic projection + UV triangle rasterization (`cv2.fillConvexPoly` + barycentric interpolation) for deterministic logo transfer.
  - Save artifacts and report under `/content/trellis_cp_outputs/cp2/output/cp4_logo_projection`.
- CP4 status (2026-03-05 update):
  - CP4 logo-projection cells are removed from the active notebook variant.
  - CP4 remains documented as optional downstream/local pipeline work, not Colab default execution.
- CP2 quality parity policy (2026-03-05 update):
  - To reduce quality gap versus official Space, CP2-5 now follows official default-style settings:
    - `pipeline_type=1024_cascade` (override via `TRELLIS_PIPELINE_TYPE`)
    - sampler defaults aligned to official app structure:
      - sparse-structure (`steps=12`, `guidance_strength=7.5`, `guidance_rescale=0.7`, `rescale_t=5.0`)
      - shape-SLat (`steps=12`, `guidance_strength=7.5`, `guidance_rescale=0.5`, `rescale_t=3.0`)
      - tex-SLat (`steps=12`, `guidance_strength=1.0`, `guidance_rescale=0.0`, `rescale_t=3.0`)
    - GLB export defaults: `decimation_target=1000000`, `texture_size=4096`, `remesh=True`, `remesh_band=1`, `remesh_project=0`
  - Run call uses primary API (`shape_slat_sampler_params`, `tex_slat_sampler_params`) and auto-fallback to legacy API (`slat_sampler_params`) for compatibility.
  - Export path prefers latent decode + `pipeline.pbr_attr_layout` when available and drops unsupported `remesh_project` automatically for legacy `o_voxel`.

## References
- `../TrellisDocs/plan_docs/FINAL_PLANNING_DOCUMENT.md`
- `../TrellisDocs/plan_docs/ASSET_PIPELINE.md`
- `../TrellisDocs/plan_docs/REQUIREMENTS_SPECIFICATION.md`
- `../TrellisDocs/research/ar-3d-garment-technical-review.md`
- `../TrellisDocs/research/colab-snippet.txt`
- `../../AR_VTON_PROTOTYPE/services/inference/preprocess_garment.py`
- `../../AR_VTON_PROTOTYPE/services/inference/test_composite_texture.py`
- `https://github.com/microsoft/TRELLIS.2`
- `https://huggingface.co/microsoft/TRELLIS.2-4B`
- `https://huggingface.co/spaces/microsoft/TRELLIS.2/blob/main/app.py`
- `https://huggingface.co/spaces/microsoft/TRELLIS.2/blob/main/requirements.txt`

---

> Rule: Record each implementation decision here with rationale.

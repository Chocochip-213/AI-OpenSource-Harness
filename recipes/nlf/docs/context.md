# Context — NLF

## Authoritative Reference
**OpenCode 10-subagent analysis** at `C:\Users\kmw16\Desktop\climbIdeaResearch\nlf-clone-analysis\`:
- `NLF_PORT_BRIEF.md` (master synthesis, 84 lines)
- `A1_demo_structure.md` … `A10_cellplan.md` (sub-reports, ~1500 lines combined)
- `citation_audit_summary.json` + `citation_audit_v2.json` (5/5 random samples passed; **0 `[CITATION FAILURE]`**, **0 `[CONFLICT]`**, 115 honest UNKNOWN flags)

**Upstream clone** (READ-ONLY, do not modify):
`C:\Users\kmw16\Desktop\climbIdeaResearch\nlf-clone\` HEAD `f8611fc76ff60f262eb0ab2c6abc3947e42a954a` (2025-05-22 main).

**Paper**: NeurIPS'24 — Sárándi & Pons-Moll, "Neural Localizer Fields for Continuous 3D Human Pose
and Shape Estimation". <https://arxiv.org/abs/2407.07532>

**Independent verification by Claude (this session)**: 5/5 random citations from the brief opened
and matched verbatim — `pyproject.toml`, `install_dependencies.sh:67-85`,
`environment_comfortable_py10.yml:5-58`, `nlf/pt/multiperson/multiperson_model.py:80-110`,
`README.md:5`. Confidence: high.

Every "Brief §X" / "A4 §Y" / "A10 cell N" claim below traces to those source files.

## Architecture

```
example_image.jpg  (single frame, any aspect; bundled in upstream — 112 KB)
  ↓
[torchvision.io.read_image]  → uint8 RGB tensor [3, H, W]
  ↓
[.unsqueeze(0).to('cuda')]   → frame_batch [1, 3, H, W]
  ↓
[torch.jit.load('models/nlf_l_multi.torchscript')]
  ↓
NLF model (DINOv2 ViT-L or EfficientNetV2-L backbone — opaque inside TorchScript)
  ├── person detector  (default threshold 0.3, NMS IoU 0.7, max_detections 150)
  ├── pose head        (SMPL parametric + nonparametric heads)
  └── default FOV 55°  (when no intrinsic_matrix passed)
  ↓
[model.detect_smpl_batched(frame_batch)]
  ↓
SMPL prediction dict (per-image batched lists):
  ├── pose                       — SMPL pose parameters
  ├── betas                      — shape parameters
  ├── trans                      — translation
  ├── joints3d                   — 3D parametric joints (mm; ×1000 internally)
  ├── vertices3d                 — 3D parametric mesh verts
  ├── joints2d                   — 2D image-space joints (post-projection)
  ├── vertices2d                 — 2D image-space verts
  ├── joints3d_nonparam, vertices3d_nonparam   — nonparametric counterparts
  ├── joints2d_nonparam, vertices2d_nonparam
  ├── joint_uncertainties, vertex_uncertainties — mm-scaled (Brief §A3)
  └── boxes                       — detection bboxes (returned but not in demo print)
  ↓
[matplotlib scatter(vertices2d, joints2d, image)]
  ↓
overlay PNG (display) + outputs/example_pred.pt (saved + downloaded)
```

**Entry point**: `model.detect_smpl_batched(image_batch)` — TorchScript-exported. The underlying
generic is `detect_parametric_batched` (`nlf/pt/multiperson/multiperson_model.py:84-107`); the SMPL
alias is at `:175` (`detect_smpl_batched = detect_parametric_batched`). Main-path return-dict
construction is at `:221-314` (14 keys including `boxes`); the empty-detection fallback at `:880-894`
returns 13 keys (drops `boxes`).

**Default args** (verbatim from cited file):
- `default_fov_degrees=55.0`
- `internal_batch_size=64`
- `max_detections=150`
- `detector_threshold=0.3`
- `detector_nms_iou_threshold=0.7`
- `model_name='smpl'`

**Code structure** (verified by OpenCode A5 — 126 Python files inventoried in `A5_inventory.json`):
- The TorchScript binary `nlf_l_multi.torchscript` is **self-contained** — does NOT require the
  `nlf/` Python package at runtime. The package contains training code + source-side prediction
  scripts (`predict_tdpw.py`, `predict_emdb.py`).
- `demo.ipynb` has 20 cells (19 code + 1 markdown). **Essential cells**: 1 (PyTorch demo, this is
  our blueprint), 2 (TF demo — skipped), 3 (SMPL-X TorchScript path — skipped, `nlf_l_multi3.torchscript`
  source UNKNOWN), 6 (SMPL-X reconstruction — skipped, npz gated). Cells 9-18 are exploratory
  failures we deliberately exclude (`cuda:1` invalid ordinal, YOLO TorchScript probing,
  buffer-registration tests).
- `pyproject.toml` is **3 lines** — only `[tool.black]`. NLF doesn't declare itself as a
  pip-installable package; consumers download the TorchScript binary directly.
- `install_dependencies.sh` is **118 lines**, Ubuntu-first (uses `apt`, `wget`, `tar`, `make`,
  `micromamba`). Not used in MVP (we don't replicate the env).

## Weights

| Server | File | Size | Verification | Risk |
|---|---|---|---|---|
| GitHub Releases (via `bit.ly/nlf_l_pt` redirect) | `nlf_l_multi.torchscript` | 495,696,900 bytes (473 MB) | OpenCode A8 `curl -IL` confirmed Content-Length | ✅ direct |

If `bit.ly` rotates, fall back to <https://github.com/isarandi/nlf/releases> (authoritative).

**Not used in MVP** (would be needed for SMPL-X reconstruction appendix):
- `nlf_l_multi3.torchscript` — UNKNOWN source (referenced in `demo.ipynb` cell 3 only).
- `SMPLX_NEUTRAL.npz` — gated on smpl-x.is.tue.mpg.de (registration required).
- `nlf_l_multi_0.2.2.torchscript` — exploratory cell only, no acquisition path.
- `yolov8x.torchscript` — also exploratory; demo.ipynb cells 17-18 fail to load due to device.

## Dependencies

| Package | Upstream Asks | Colab 2025.07 Stock | Strategy | Why |
|---------|---|---|---|---|
| `torch` | (no pin install_dependencies.sh:72) | 2.6.0+cu124 | **keep** | TorchScript loads on stock torch (single dispatch call, no version-sensitive ops) |
| `torchvision` | (no pin install_dependencies.sh:73) | 0.21.0+cu124 | **keep** | demo.ipynb cell 1 inline comment: "Must import this for the model to load without error" |
| `Pillow` | env yml `Pillow` | 11.2.1 | **keep** | Used by `torchvision.io.read_image` for JPEG decode |
| `matplotlib` | env yml `matplotlib` | 3.10.x | **keep** | Cell H 2D overlay only |
| `numpy` | env yml `numpy<2.0` | 2.0.2 | **skip** | A4 verified bare TorchScript call doesn't import numpy. Constraint applies only to source-side scripts (`multiperson_model.py:4`, `predict_tdpw.py:14`). MVP is unaffected. |
| `tensorflow==2.15` + `tensorflow-hub` | env yml + install.sh | not on Colab default | **skip** | TF Hub path out of MVP scope |
| `chumpy` | env yml + install.sh | (unspec) | **skip** | A4 confirmed not used by `detect_smpl_batched`. (Was a SABR pain — not a problem here.) |
| `mayavi`, `PySide6` | env yml conda-forge | not pre-installed | **skip** | Headless Colab; GUI viz never invoked |
| `cameralib` (Sárándi editable) | env yml `-e $CODE_DIR/cameralib` | n/a | **skip** | Not on PyPI; git URL `github.com/isarandi/cameralib.git` documented in env yml line 60 (commented). MVP uses returned `vertices2d` / `joints2d` directly so no reprojection helper needed. |
| `smplfitter`, `simplepyutils`, `boxlib`, `rlemasklib`, `barecat3` | env yml editables | n/a | **skip** | A6 verified inference-relevant for source-side scripts only, not for `detect_smpl_batched(image_batch)` |
| `posepile`, `fleras`, `tensorflow-inputs`, `blendipose`, `blendify`, `affine_combining_autoencoder`, `nlf-pipeline`, `poseviz` | env yml editables | n/a | **skip** | A7 verified train/data-only or used by other inference scripts (`predict_tdpw.py` / `predict_emdb.py`). MVP doesn't touch those scripts. |
| `opencv-python`, `imageio`, `imageio-ffmpeg`, `ffmpeg-python`, `av<9` | env yml | various | **skip** | Used by `torch_inputs.py` for video ingestion, not single-image demo |
| `addict`, `einops`, `jpeg4py`, `pyrender`, `tetgen`, `pymeshfix`, `embreex`, `more_itertools`, `setuptools`, `torchdata`, `cachetools`, `cython`, `ezc3d`, `mkl`, `trimesh`, `numba`, `pandas`, `scikit-image`, `scikit-learn`, `scikit-sparse`, `tqdm`, `importlib_resources`, `distutils` | env yml + install.sh | various | **skip** | A4: no scoped use proof for `detect_smpl_batched` path |

`pyproject.toml` contributes nothing — it's only `[tool.black]`. There is no
`[project.dependencies]` to align with.

## Key Decisions

### MVP scope: PyTorch TorchScript single-image path only
- **Context**: NLF demo.ipynb shows 4 paths — PyTorch TorchScript (cell 1), TF Hub (cell 2),
  SMPL-X TorchScript (cell 3), SMPL-X reconstruction (cells 4-8). Each carries different risks.
- **Options considered**: (a) full demo replication; (b) PyTorch only;
  (c) PyTorch + SMPL-X reconstruction; (d) build a video frame loop on top.
- **Choice**: **(b) PyTorch single-image MVP**. SMPL-X TorchScript file `nlf_l_multi3.torchscript`
  has UNKNOWN source. SMPLX_NEUTRAL.npz is gated on smpl-x.is.tue.mpg.de. TF Hub is documented
  "several minutes" to load and produces equivalent output. Video loop has no demo evidence.
- **Outcome**: minimal scope = minimal risk. Defer everything else to optional appendices that can
  be added once MVP is verified stable. Cell plan reflects this (8 cells; SMPL-X / TF / video absent).

### Strategy: Direct pip, no condacolab/mamba
- **Context**: NLF env yml requests Python 3.10, `numpy<2.0`, 14 editable libs by Sárándi, chumpy,
  `tensorflow==2.15`, mayavi GUI. SABR-style would force a 30+ min mamba install dance.
- **Options considered**: (a) condacolab + full env yml replication; (b) Direct pip with full env;
  (c) Direct pip with minimum proven subset.
- **Choice**: **(c) `torch + torchvision` only** (already pre-installed on Colab 2025.07).
  OpenCode A4 dependency triangulation proved the bare `model.detect_smpl_batched(image_batch)`
  call uses only torch + torchvision; everything else in env yml belongs to OTHER paths
  (training, TF, source-side viz scripts, SMPL-X reconstruction).
- **Outcome**: install time goes from ~10 min (env yml) to ~5 sec (`importlib.util.find_spec`
  check; no actual pip install needed on stock 2025.07).

### Pin upstream to f8611fc76ff60f262eb0ab2c6abc3947e42a954a
- **Context**: Reproducibility vs upstream drift. OpenCode analyzed this exact commit.
- **Options considered**: (a) track `main`, (b) pin to verified SHA, (c) pin to a release tag.
- **Choice**: **(b) pin SHA**. NLF's main could rewrite `demo.ipynb` cell layout, change the
  `bit.ly/nlf_l_pt` redirect target, or remove `example_image.jpg` — silently breaking our cells.
  Release tags don't exist for the demo (releases are model assets only, not source).
- **Outcome**: `tasks.md` Reversal section has a quarterly review item to bump the pin if upstream
  pushes valuable fixes.

### Skip `ptu3d` / `cameralib` reprojection helpers
- **Context**: `demo.ipynb` references `ptu3d` without an import (Brief §A2/A5). `cameralib` is
  used in the upstream cell 7 viz only.
- **Options considered**: (a) install `cameralib` from `git+https://github.com/isarandi/cameralib.git`
  (URL documented in env yml line 60 — confirmed by independent verification this session);
  (b) try to guess `ptu3d` source (no evidence in repo); (c) use the model's already-projected
  `vertices2d` / `joints2d` directly with matplotlib.
- **Choice**: **(c) direct matplotlib overlay**. The TorchScript already returns 2D-projected verts
  and joints in image space; reprojection helpers are unnecessary noise for the MVP.
- **Outcome**: zero git installs at runtime; A10 Cell 7 verified uses returned `vertices2d` directly.

### Hardcode DEVICE = "cuda" (never "cuda:1")
- **Context**: `demo.ipynb` cells 9-18 contain a failed `cuda:1` experiment. OpenCode A3 confirmed
  `RuntimeError: CUDA error: invalid device ordinal` on single-GPU Colab.
- **Choice**: Cell E hardcodes `DEVICE = "cuda"` and Cell F's `torch.device("cuda")` context manager.
- **Outcome**: avoids the demo's documented runtime failure mode for free.

### MCP enabled day-1, allow_auto_execution: true
- **Context**: User opted in (`코랩 MCP도 쓰자`, this session). Recipe is small (8 manual cells,
  ~3-5 min total cold).
- **Options considered**: (a) MCP off (manual notebook upload); (b) MCP on, gate every cell;
  (c) MCP on, auto-execute.
- **Choice**: **(c) auto-execute**. User can interrupt anytime. Recipe is short enough that gating
  every cell would add friction without proportional safety. Per-cell backup hook
  (`_mcp_session_log.py` PostToolUse) still snapshots `cells_*.json` automatically.
- **Outcome**: hybrid plan — local scaffold first (this session), MCP iteration when notebook is
  ready to test on real Colab.

### Push the OpenCode UNKNOWNs out of MVP entirely
- **Context**: OpenCode brief flagged 7 UNKNOWNs (`nlf_l_multi3` source, `SMPLX_NEUTRAL` version,
  `ptu3d` source, `cameralib` PyPI presence, `posepile` / `fleras` / `tensorflow-inputs` need-or-not).
- **Choice**: every UNKNOWN affects ONLY the deferred appendix paths (SMPL-X, video, source-side
  scripts). MVP doesn't depend on any of them.
- **Outcome**: zero UNKNOWN-induced blockers for MVP. All flags acknowledged in "Open Questions" below.

## Discovered Issues
| Error | Root Cause | Fix | Verified |
|-------|-----------|-----|----------|
|       |           |     |          |

> Populated during cold-run on Colab. Empty until first run.
> Promote generalizable fixes to `docs/COMMON_ERRORS.md`.

## Risks
| Risk | Probability | Mitigation |
|------|------|------------|
| `bit.ly/nlf_l_pt` redirect breaks (URL service rotation) | Low | Document the resolved GH releases asset URL after first cold run; Cell D can fall back |
| Upstream rewrites `demo.ipynb` removing `example_image.jpg` | Low | SHA pin (`f8611fc7…`) on `upstream.ref` prevents drift |
| Colab runtime 2025.07 deprecation | Med (12-mo horizon) | Quarterly task: re-test on next runtime; runtime list in `colab-runtimes/SUMMARY.md` |
| TorchScript op-signature breakage on torch ≥ 2.7 | Low | Locked to runtime 2025.07 (torch 2.6.0); v2a runtime rollback pre-authorized |
| MCP per-cell backup hook fails silently | Low | `session-end` skill enforces commit before close; `.claude/_hook_errors.log` reviewed each session |
| OOM on T4 16 GB at default `max_detections=150` | Low (we require A100 anyway) | `runtime.vram_min_gb: 16` enforced by harness preflight |
| Sárándi pushes a `nlf_l_multi.torchscript` v2 with breaking output schema | Med | Cell G asserts the 13 expected keys present; will fail-fast |

## Decision Log (reversals allowed)
| Date | Decision / Reversal | Reason |
|------|---------------------|--------|
| 2026-04-27 | Initial: MVP = PyTorch TorchScript single-image only | OpenCode 10-subagent brief verified this is the only fully-evidenced path. SMPL-X / TF / video deferred. |
| 2026-04-27 | Initial: Direct pip (no condacolab) | OpenCode A4: bare `detect_smpl_batched` only needs torch + torchvision (both pre-installed on 2025.07). |
| 2026-04-27 | Initial: pin `upstream.ref` to f8611fc7… | OpenCode analyzed this exact commit; pin prevents silent drift in demo.ipynb / bit.ly target / example_image.jpg. |
| 2026-04-27 | code-reviewer P1 catch: Cell G EXPECTED_KEYS missed `boxes` | Reviewer found main path (`multiperson_model.py:221-314`) returns 14 keys including `boxes`; the :880+ block I cited was the empty-detection fallback (13 keys). Fixed Cell G to assert all 14 (fail-fast on no-detections is desired) + corrected line citations in cell F/G + plan.md/context.md. |
| 2026-04-27 | MCP cold-run cell 0 (preflight) PASSED | Allocated GPU: NVIDIA A100-SXM4-40GB / 42.4 GB VRAM (`expected: A100` matched). First run on CPU runtime correctly fail-fast'd via our assert (proved preflight does its job). User switched to A100 → re-run passed. Backup: outputs/mcp-sessions/nlf/20260427T073718Z.jsonl. |

## Artifact Locations
| Path | Contents | Gitignored? |
|------|----------|-------------|
| `outputs/notebooks/nlf.ipynb` | Generated Colab notebook | Yes |
| `outputs/e2e/nlf/` | Per-cell inference outputs | Yes |
| `outputs/mcp-sessions/nlf/` | MCP session logs (`cells_*.json` snapshots) | Yes |
| `/content/nlf/models/nlf_l_multi.torchscript` (Colab) | 473 MB TorchScript download | n/a (Colab ephemeral) |
| `/content/nlf/outputs/example_pred.pt` (Colab) | Saved SMPL dict for download | n/a (Colab ephemeral) |

## Open Questions (carried from OpenCode UNKNOWNs)
None block MVP. Listed here so future appendix work has a starting point — each carries a named
trigger condition (per `CLAUDE.md` NoMessLeftBehind §6: no unowned TODOs).
1. `nlf_l_multi3.torchscript` source — referenced in `demo.ipynb` cell 3 for SMPL-X output, no public URL.
   **Trigger**: user requests SMPL-X output → ask upstream or scrape future releases.
2. `SMPLX_NEUTRAL.npz` version + alternative source — gated on smpl-x.is.tue.mpg.de.
   **Trigger**: SMPL-X appendix activates → user provides registered access OR identifies HF mirror.
3. `ptu3d` import context — appears in demo viz cells without visible import.
   **Trigger**: irrelevant for MVP; if SMPL-X reconstruction added, identify by inspecting
   `nlf/pt/ptu3d.py` exports vs notebook usage.
4. `cameralib` PyPI presence — git URL is documented (env yml line 60); pip install dry-run not yet performed.
   **Trigger**: any path beyond MVP that uses reprojection helpers.
5. Whether `posepile` / `fleras` / `tensorflow-inputs` are required for source-side inference scripts
   (`predict_tdpw.py` / `predict_emdb.py`). A7 hints yes, but those scripts are out of MVP.
   **Trigger**: user explicitly requests dataset-eval scripts.
6. Video frame loop pattern — no upstream demo. Would need custom `torchvision.io.read_video`
   + per-frame batched inference.
   **Trigger**: user uploads a clip OR climbing-avatar pipeline integration.

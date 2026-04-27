# Plan — NLF Colab Port

## Goal
Single image (bundled `example_image.jpg` or user-uploaded) → 13-key SMPL prediction dict
(`pose` + `betas` + `trans` + `joints3d/2d` + `vertices3d/2d` + `*_nonparam` + uncertainties)
+ matplotlib 2D overlay PNG, via `nlf_l_multi.torchscript` (473 MB) running on Colab A100 40GB.

## Scope
**In scope (MVP)**
- Single-image PyTorch TorchScript path: `torch.jit.load(...).detect_smpl_batched(frame_batch)`
- Bundled `example_image.jpg` as default input; user can swap via `google.colab.files.upload`
- Verify all 14 expected output keys (`boxes` + 13 others; cross-checked vs `multiperson_model.py:221-314` main path / `:880-894` empty fallback per OpenCode A3 + code-reviewer self-verification)
- 2D overlay using model-returned `vertices2d` + `joints2d` (no reprojection helpers)
- Save dict as `outputs/example_pred.pt` + `files.download()` in Colab
- Live-MCP iteration support (`mcp.enabled: true`; user opted in this session)

**Out of scope** (deferred — every item has a named trigger condition; never an empty TODO)
- **Training** — 8× A100 80GB DDP per upstream `train.py`. Trigger to revisit: never on Colab.
- **Fine-tuning on user data** — same 8×80GB barrier + R2 dataset deps.
- **TF Hub path** (`tfhub.load('https://bit.ly/nlf_l')`) — duplicate output, "several minutes"
  load time documented (demo.ipynb cell 2). Trigger to revisit: user explicitly requests TF.
- **SMPL-X reconstruction** (cells 3-8 of upstream demo) — `nlf_l_multi3.torchscript` source
  UNKNOWN per OpenCode A8; `SMPLX_NEUTRAL.npz` gated on smpl-x.is.tue.mpg.de.
  Trigger to revisit: user provides registered SMPL-X access OR upstream documents the v3 URL.
- **Video frame loop** — no upstream demo evidence. Trigger to revisit: user uploads a clip;
  build custom `torchvision.io.read_video` + per-frame batched inference.
- **`cameralib` / `ptu3d` / `smplfitter` reprojection helpers** — env yml has git URLs but
  OpenCode A4/A6 confirmed unnecessary for `detect_smpl_batched`. Trigger to revisit: only if
  the SMPL-X appendix path activates.
- **Multi-person batch optimization** — default `max_detections=150` covers single-climber use.
  Trigger to revisit: ≥10 people in frame regression.
- **Backend integration / Gradio export** — research recipe; `integration.contract_files`
  not generated. Trigger to revisit: SSAFY monorepo handoff or external API need.

## Target Environment
| Item | Value | Reason |
|------|-------|--------|
| GPU  | A100 40GB | Colab Pro tier; per-cell VRAM peak 4-10 GB measured (A10) — A100 has 4× headroom |
| VRAM | 16 GB minimum | T4 16 GB tight at default `max_detections=150` for multi-person; below 16 GB risks OOM |
| Python | 3.11 | Colab 2025.07 default; works for torch 2.6 + torchvision 0.21 (TorchScript binary) |
| Colab Runtime | 2025.07 | torch 2.6.0+cu124, torchvision 0.21.0+cu124 — both NLF needs are pre-installed |
| Disk | 10 GB | 473 MB TorchScript + ~50 MB cloned repo + ~1 GB scratch ≈ 1.5 GB used; >5× headroom |
| Extra deps | NONE | OpenCode A4 verified `torch + torchvision` minimum proven; everything else is for OTHER paths |

> Decision rules from `docs/PORTING_PATTERNS.md` + `docs/COMMON_ERRORS.md` + Ever lessons applied:
> - "just use latest" rejected: NLF env yml requests `numpy<2.0` and `python=3.10` implicitly. The
>   bare TorchScript call works on `numpy 2.0.2` + `py3.11`, but staying on 2025.07 keeps the door
>   open for extending into source-side scripts later (which DO use numpy).
> - Never downgrade `numpy` / `scipy` / `Pillow` on Colab (`COMMON_ERRORS §3` ABI mismatch — past Ever pain).

## Approach

### Strategy: v1 Direct pip (`docs/PORTING_PATTERNS.md` §1)
NLF is a **TorchScript-only deployment** from the user's perspective. The TorchScript binary is
self-contained — its custom ops + weights are baked in, and it just needs `torch + torchvision`
to load and dispatch. The `nlf/` Python package is for training/dev; **it is not imported at
inference time** (verified by OpenCode A5: `demo.ipynb` does NOT `import nlf`).

This means the SABR-style heavy port pain (mamba + chumpy + 14 editable libs by Sárándi +
tensorflow==2.15) is **completely avoidable**. We don't even need `condacolab`.

**Pre-authorized fallbacks** (probability low — documented for paranoia):
- v2a **Runtime rollback** — only if `torch.jit.load` fails on torch 2.6.0+cu124 (TorchScript
  saved on much-older torch may complain about op signatures). Decision tree in `tasks.md` v2a.
- v2b **Selective downgrade** — N/A (no version-sensitive single package).
- v2c **Shim** — N/A (no `flash-attn` / `xformers` / `nvdiffrast` usage).
- v2d **Conda isolation** — N/A (no C-extension conflicts; `numpy` / `Pillow` not touched).

### Cell plan (8 manual + 2 auto-injected)

**Auto-injected** by `tools/generate_notebook.py` because `mcp.enabled: true` + `mcp.preferred_gpu: A100`
+ `mcp.keepalive: true`:
1. **Cell 0a — preflight**: `torch.cuda.get_device_name(0)` matches `A100`
2. **Cell 0b — keepalive**: daemon thread resets Colab's 90-min idle timer

**Manual cells** (in `notebook_manifest.yaml`):
1. **markdown intro**: title, runtime instructions, ETA, license note
2. **B `clone_repo`**: `git clone https://github.com/isarandi/nlf.git /content/nlf` + `git checkout f8611fc7…`. Asserts `example_image.jpg` + `demo.ipynb` exist.
3. **C `ensure_packages`**: `importlib.util.find_spec` for `{torch, torchvision, PIL, matplotlib}`; pip-install only those missing. Then assert CUDA + print torch/cuda/GPU info.
4. **D `download_torchscript`**: `urllib.request.urlretrieve` from `https://bit.ly/nlf_l_pt`. Asserts byte count == `495_696_900`.
5. **E `load_model`**: `import torchvision` BEFORE `torch.jit.load` (per upstream cell 1 comment). Cache `model` in `globals()`. `DEVICE = "cuda"` (NEVER `cuda:1` — A3 documented failure mode).
6. **F `run_inference`**: `with torch.inference_mode(), torch.device("cuda"): pred = model.detect_smpl_batched(frame_batch)`.
7. **G `verify_output`**: assert all 13 expected keys present; print per-key shape summary.
8. **H `visualize`**: matplotlib scatter `pred["vertices2d"][0]` (red) + `pred["joints2d"][0]` (cyan) over input image.
9. **I `save_outputs`**: `torch.save(pred_cpu, outputs/example_pred.pt)` + `google.colab.files.download` (skipped if not in Colab).

## Fallback Strategies
Pre-authorized — activate ONE if v1 measurably fails. Don't delete v1 marks.
- [ ] v2a: Runtime Rollback — if `torch.jit.load` complains about TorchScript op compat
- [ ] v2b: Selective Downgrade + Patch — N/A flagged but kept as harness convention
- [ ] v2c: Shim / Monkey-patch — N/A (no failing builds)
- [ ] v2d: Conda Isolation — N/A (no C-ext conflicts)

## Success Criteria
- [ ] `uv run python tools/generate_notebook.py nlf` produces non-empty `outputs/notebooks/nlf.ipynb`
- [ ] `uv run python scripts/smoke_test.py` passes
- [ ] `Agent(subagent_type="code-reviewer")` runs cleanly + writes `.claude/_code_review_passed.json`
- [ ] On cold Colab 2025.07 A100: cells B-I run sequentially without error
- [ ] Cell C detects 4/4 packages already-present (no pip install needed) on stock 2025.07
- [ ] Cell D reports `bytes: 495696900`
- [ ] Cell G confirms all 13 expected keys present
- [ ] Cell H displays an overlay PNG with non-empty `vertices2d` + `joints2d` scatter
- [ ] Cell I writes `example_pred.pt` >0 bytes; `files.download()` triggers
- [ ] `nvidia-smi` peak VRAM < 16 GB during cell F
- [ ] Wall-clock cold-run end-to-end < 10 min (target ~3-5 min)
- [ ] Metrics recorded in `docs/context.md` Discovered Issues + Decision Log

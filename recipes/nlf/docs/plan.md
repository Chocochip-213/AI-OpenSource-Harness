# Plan — NLF Body Embedding API on Colab

## Goal
Single image POST → 7-dim pose-invariant, height-independent body-shape vector via FastAPI endpoint
on Colab A100 40GB, exposed publicly via cloudflared quick tunnel. Plus full SMPL params (`/infer`)
and pairwise distance (`/compare`) for advanced use cases. Powered by `nlf_l_multi.torchscript`
(473 MB) — Sárándi & Pons-Moll NeurIPS'24 NLF.

## Scope

**In scope (delivered, validated)**
- Single-image PyTorch TorchScript inference: `torch.jit.load(...).detect_smpl_batched(frame_batch)`
- 14-key SMPL output dict (`boxes` + 13 others; cross-checked vs `multiperson_model.py:221-314` main path / `:880-894` empty fallback)
- **7-dim body-shape vector** via Y-span normalization (rigid bone segments only — pose-invariant)
  - Math insight: `rigid_segment / Y_span ≡ rigid_segment / real_height` (the H factor cancels in ratio)
  - Client doesn't need real height to compute distances between vectors
  - Features: `shoulder_w_norm`, `hip_w_norm`, `torso_norm`, `upper_arm_norm`, `forearm_norm`, `thigh_norm`, `shin_norm`
- FastAPI v0.3 server endpoints:
  - `POST /embed` — primary signup endpoint (image → 7-dim vector)
  - `POST /infer` — full SMPL params + vector
  - `POST /compare` — pairwise body-shape distance (N images)
  - `GET /health` + `GET /docs` (Swagger UI)
- cloudflared quick tunnel for public access (session-rotating `*.trycloudflare.com`)
- Cell J forever-loop to keep Colab session alive (idle 0; 12h hard cap unavoidable)
- Live-MCP iteration support during development

**Out of scope** (deferred — every item has a named trigger condition)
- **Training** — 8× A100 80GB DDP per upstream `train.py`. Trigger: never on Colab.
- **TF Hub path** (`tfhub.load('https://bit.ly/nlf_l')`) — duplicate output, "several minutes" load. Trigger: user explicitly requests TF.
- **SMPL-X reconstruction** (cells 3-8 of upstream demo) — `nlf_l_multi3.torchscript` source UNKNOWN; `SMPLX_NEUTRAL.npz` gated on smpl-x.is.tue.mpg.de. Trigger: registered SMPL-X access OR upstream URL.
- **Video frame loop** — no upstream demo. Trigger: user uploads a clip.
- **Permanent named tunnel** — current quick tunnel rotates per session. Trigger: production deploy → Cloudflare account + named tunnel for stable URL.
- **Authentication / rate limiting** — research recipe; quick tunnel is open. Trigger: external user traffic, abuse signal.
- **Multi-person batch optimization** — `max_detections=150` covers single-subject signup use. Trigger: ≥10 people in frame.
- **Multipart filename UTF-8 encoding** — `/compare` response shows mojibake on Korean filenames (`ÁÙ¸®¿£°­`). Vectors+distances unaffected. Trigger: production needs UTF-8 filenames in response.
- **`cameralib` / `ptu3d` / `smplfitter`** — env yml has git URLs, OpenCode A4/A6 confirmed unnecessary for `detect_smpl_batched`. Trigger: SMPL-X path activates.

## Target Environment
| Item | Value | Reason |
|------|-------|--------|
| GPU  | A100 40GB | Live-verified: `NVIDIA A100-SXM4-40GB`, 42.4 GB. Per-cell VRAM peak 4-10 GB measured. |
| VRAM | 16 GB minimum | T4 16 GB tight; <16 GB risks OOM at `max_detections=150`. |
| Python | 3.11+ | Verified 3.12 (Colab 2026.04) AND 3.11 (2025.07). Both work. |
| Colab Runtime | 2025.07 OR 2026.04 | torch 2.6.0+cu124 (2025.07) AND torch 2.10.0+cu128 (2026.04) both load TorchScript. **Forward-compat verified end-to-end.** |
| Disk | 10 GB | 473 MB TorchScript + ~50 MB repo + ~1 GB scratch ≈ 1.5 GB used; >5× headroom. |
| Runtime-installed deps | `fastapi`, `uvicorn[standard]`, `python-multipart`, `requests` | Server stack. `torch` / `torchvision` / `Pillow` / `matplotlib` pre-installed. cloudflared binary downloaded by Cell I. |

> Decision rules from `docs/PORTING_PATTERNS.md` + `docs/COMMON_ERRORS.md`:
> - **Verified runtime portability**: 2025.07 (torch 2.6) AND 2026.04 (torch 2.10) — TorchScript forward-compat works.
> - Never downgrade `numpy` / `scipy` / `Pillow` (`COMMON_ERRORS §3` ABI mismatch).

## Approach

### Strategy: v1 Direct pip (`docs/PORTING_PATTERNS.md` §1)
NLF is a **TorchScript-only deployment** — the `.torchscript` binary is self-contained;
custom ops + weights baked in. The `nlf/` Python package is for training/dev only;
`demo.ipynb` does NOT `import nlf` (verified by OpenCode A5). SABR-style mamba/chumpy/14-editable
dance is **completely avoidable**. No condacolab needed.

Server stack adds 4 packages (fastapi, uvicorn, python-multipart, requests) at runtime via
Cell C. cloudflared binary fetched on demand by Cell I. Pure-Python aware — no native compilation.

**Pre-authorized fallbacks** (all marked done/N/A based on validated runtime):
- v2a Runtime rollback — N/A (2025.07 + 2026.04 both verified working)
- v2b Selective downgrade — N/A (no version-sensitive single package)
- v2c Shim — N/A (no flash-attn / xformers / nvdiffrast)
- v2d Conda isolation — N/A (no C-ext conflicts)

### Cell plan (10 manual + 2 auto-injected)

**Auto-injected** by `tools/generate_notebook.py` (mcp.enabled + preferred_gpu + keepalive):
1. **Cell 0a — preflight**: `torch.cuda.get_device_name(0)` matches `A100`; VRAM ≥ 16 GB
2. **Cell 0b — keepalive (daemon)**: BG heartbeat every 300s (supplements foreground cell J)

**Manual cells** (in `notebook_manifest.yaml`):
1. **markdown intro**: title, runtime, ETA, endpoint usage examples, license
2. **B `clone_repo`**: `git clone` + `git checkout f8611fc7…`. Asserts `example_image.jpg` exists.
3. **C `ensure_packages`**: importlib + pip-install missing — installs torch/torchvision/Pillow/matplotlib/fastapi/uvicorn/python-multipart/requests as needed.
4. **D `download_torchscript`**: `urllib.request.urlretrieve` from `https://bit.ly/nlf_l_pt`. Asserts byte count == `495_696_900`.
5. **E `load_model`**: `import torchvision` BEFORE `torch.jit.load`. Cache `model` in `globals()`. `DEVICE = "cuda"`.
6. **F `smoke_inference`**: bundled `example_image.jpg` → validates `detect_smpl_batched` works before exposing endpoint.
7. **G `verify_keys`**: assert all 14 expected keys present (fail-fast on schema regression).
8. **H `serve` (FastAPI v0.3)**: `/embed` + `/infer` + `/compare` + `/health` + `/docs` on port 7860 in background thread.
9. **I `tunnel` (cloudflared)**: download cloudflared → run quick tunnel → parse public URL from log → print.
10. **J `forever_loop`**: foreground `while True` heartbeat → Colab idle 0 (12h hard cap unavoidable).

## Fallback Strategies — all resolved
- [x] v2a: Runtime Rollback — **N/A**, 2025.07 + 2026.04 both verified
- [x] v2b: Selective Downgrade + Patch — **N/A** confirmed
- [x] v2c: Shim / Monkey-patch — **N/A** (no failing builds)
- [x] v2d: Conda Isolation — **N/A** (no C-ext conflicts)

## Success Criteria — all met
- [x] `uv run python tools/generate_notebook.py nlf` produces 12-cell `outputs/notebooks/nlf.ipynb`
- [x] `uv run python scripts/smoke_test.py` passes (compileall + critical imports)
- [x] `Agent(subagent_type="code-reviewer", model="opus")` ran cleanly + marker written
- [x] On Colab A100: cells B-G run without error (smoke + key verification)
- [x] Cell H starts FastAPI in BG thread; `localhost:7860/health` returns 200 OK
- [x] Cell I prints `https://*.trycloudflare.com` URL within 60s
- [x] Cell J infinite loop maintains kernel alive (verified via `[HH:MM:SS] alive ...` heartbeat)
- [x] External `curl /health` returns `model_loaded:true`, `gpu:A100`
- [x] External `curl /embed` returns 7-dim vector with `pose_invariant:true, height_invariant:true`
- [x] External `curl /compare` 3 images returns pairwise distance (verified deterministic to 4 decimals vs manual prediction)
- [x] Real-world validation: 줄리엔강(193cm) `hip_w_norm=0.081` V-taper signal vs 코미디언 ~0.097 (matches intuition)

> First successful cold run completed 2026-04-28 with tunnel `ranking-aged-easy-southern.trycloudflare.com`.
> All endpoints validated end-to-end. Bug fixes (decode_image PIL→torchvision, np.float32→float) baked into manifest.

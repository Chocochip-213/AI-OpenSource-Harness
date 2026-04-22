# Plan — SABR Colab Port

## Goal
Climbing-style input video (mp4, non-square) → 3D avatar video overlay (mp4) via SABR full pipeline
(FGT/LAFC inpaint → PHALP track → DINOv2 condition → DiT_action diffusion → SMPL render) running
on a Colab A100 40GB with the **context model skipped** (README FAQ path for 40GB tier).

## Scope
**In scope**
- Single Colab notebook that clones upstream, downloads 15 GB of weights, patches Berkeley→UT-Austin
  PHALP URLs and basicModel→SMPL_NEUTRAL rename, installs deps via condacolab+mamba, runs
  `python inference.py --ckpt 0070000.pt --mode 0 --videoDir videos/<one_clip>`.
- Output: single mp4 under `output/<video>.mp4` in the upstream repo root, downloaded/uploaded to user.
- Live-MCP iterative patching during initial port (inference.py context-skip patch is expected).
- Document every exception + fix in `context.md` so second run is reproducible.

**Out of scope**
- Training (`torchrun --nproc_per_node=8 train.py` — 8× A100 80GB DDP, impossible on Colab).
- Fine-tuning on user clips (same 8×80GB barrier; `collect_data.py` R2 deps).
- Full 80GB path (context model ON) — H100 80GB only on Colab Pro+ Enterprise, unreliable.
- Gradio / web UI — SABR is CLI-only; wrapping requires non-trivial refactor (Phase 3).
- Blackwell (RTX PRO 6000) deployment — mmcv-full / mmdet 2.28 / mmpose 0.24 sm_120 incompatible.
  Guide §15 has full risk matrix.
- Color/route-aware motion ("same-color holds only") — SABR is a motion generator with no color
  label signal (guide §9 strong estimate). MVP accepts raw motion.

## Target Environment
| Item | Value | Reason |
|------|-------|--------|
| GPU  | A100 40GB | Colab Pro tier. 80GB not reliably available; context-skip covers 40GB. |
| VRAM | 40GB peak | README FAQ: "skip the context model … 40GB GPU" works. |
| Python | 3.11 (host) + 3.10 (mamba env) | Colab 2025.07 host 3.11 → `condacolab` → `mamba create -n sabr python=3.10` per upstream install.sh. 3.10 needed for chumpy clean build. |
| Colab Runtime | 2025.07 | torch 2.6.0+cu124 host; condacolab 0.1.x known good on 3.11. 2026.xx (3.12) breaks chumpy. |
| Disk | ≥50 GB | 15 GB weights + 5 GB deps + 20 GB scratch (ffmpeg frames × 2, inpainted videos, SMPL render). |
| Extra deps | mmcv-full / mmdet 2.28.1 / mmpose 0.24.0 / flash-attn / xformers / detectron2 / chumpy | Pinned 2022 versions by upstream install.sh. Blackwell-incompat (sm_120) but OK on A100 sm_80. |

## Approach

### Strategy choice — **v1 condacolab + upstream install.sh** (default)
Upstream `install.sh` is tightly coupled to mamba (creates `sabr` env python=3.10, `pytorch-cuda=12.1`,
then a dozen `pip install` inside the activated env). Reproducing with direct pip into Colab base is
fragile — `mmdet==2.28.1` + `mmpose==0.24.0` + `ultralytics==8.0.99` are 2022-05 era and will fight
Colab's 2025 numpy/scipy/torch. `condacolab` resolves this by installing mamba so we run upstream
verbatim.

**Pre-authorized fallbacks**:
- v2a **Runtime rollback** — if condacolab 0.1.x breaks on 2025.07, flip runtime.
- v2b **Direct pip without mamba** — skip condacolab, install into Colab base. Fast IF pins don't
  fight. Use only if v1 measurably too slow.
- v2c **SDPA shim for flash-attn** — `pip install flash-attn --no-build-isolation` often takes 10+
  min or fails on Colab. Monkey-patch DiT to `F.scaled_dot_product_attention`. `docs/PORTING_PATTERNS.md` §4.
- v2d **Manual miniforge** — install miniforge by hand, create env manually. Last resort.

### Cell plan (9 manual + 2 auto-injected by `generate_notebook.py`)

Auto-injected when `mcp.enabled: true` (deferred until user flips flag):
- **preflight**: `torch.cuda.get_device_name(0)` contains "A100" (mcp.preferred_gpu match)
- **keepalive**: daemon thread resets Colab's 90-min idle timer

Manual cells:
1. **Cell A — GPU + disk check**: nvidia-smi, `assert vram >= 40`, `df -h /content`. Fail-fast.
2. **Cell B — Clone + HOME setup**: `export HOME=/root`, `cd $HOME`, `git clone ...`, cd in.
3. **Cell C — Weight download (15GB)**: guide §13 recovery script. curl/wget/gdown from 7 servers.
   Retry on transient failure. Validate file sizes at end.
4. **Cell D — condacolab install + upstream install.sh**: `pip install condacolab` → `condacolab.install()`
   (forces kernel restart) → second half (after restart) runs `bash install.sh` inside mamba env.
5. **Cell E — PHALP URL patch + SMPL convert + CACHE_DIR**: `sed -i` patch `pipeline/context/model.py:670-678`
   Berkeley→UT-Austin. Python snippet: Py2 chumpy→numpy → Py3 pickle → `~/.cache/phalp/3D/models/smpl/SMPL_NEUTRAL.pkl`.
   `cp` PHALP weights with rename (`pose_predictor_40006.ckpt` → `pose_predictor.pth`, etc.).
   **assert** file exists at each destination.
6. **Cell F — context-skip patch to inference.py**: for 40GB path, patch `inference()` to fabricate
   context frames from inpainted frames (duplicate path) OR skip context model forward. Upstream
   has no flag — we add `--skipContext`. Assert patch applied.
7. **Cell G — Input video**: `mkdir videos`, upload via `google.colab.files.upload()` or sample from
   repo. Assert non-square (W != H); SABR latent mode rejects square (line 408).
8. **Cell H — Inference**: `cd ~/virtual-avatar-generation && python inference.py --ckpt 0070000.pt
   --mode 0 --videoDir videos`. Redirect stdout/stderr to log. Expected 5-15 min.
9. **Cell I — Output**: `from IPython.display import Video; Video('output/<name>.mp4')` +
   `files.download()`.

Every cell is idempotent (re-runnable). Patches use `assert 'new_token' in content` after
`str.replace()`.

## Fallback Strategies (pre-authorized — activate without user approval)
- [x] v1: condacolab + upstream install.sh
- [ ] v2a: Runtime rollback — if condacolab fails on 2025.07
- [ ] v2b: Direct pip (skip mamba) — if v1 measurably fails
- [ ] v2c: SDPA shim for flash-attn — activate on first build failure
- [ ] v2d: Manual miniforge — last resort

## Success Criteria
- [ ] `generate_notebook.py sabr` succeeds (non-empty cells)
- [ ] `smoke_test.py` passes locally
- [ ] Colab cells A-C run cold on fresh runtime without error
- [ ] Cell D produces `mamba env list` output showing `sabr` env
- [ ] Cell E: `assert os.path.exists('/root/.cache/phalp/weights/pose_predictor.pth')` and 3 more
- [ ] Cell F: inference.py patched; `assert '--skipContext' in open(...).read()` passes
- [ ] Cell G: video file present, non-square verified
- [ ] Cell H: exit code 0; `ls output/` shows exactly one mp4; file > 1MB
- [ ] Cell I: mp4 displays (visual check — person segment replaced with SMPL avatar)
- [ ] Record metrics in `context.md`:
  - Cold-start time (git clone + weights + deps, expected 20-40 min)
  - Weights download time (15 GB @ Colab bandwidth)
  - `install.sh` duration (mmcv-full compile + flash-attn build)
  - Inference wall time (expected 5-15 min for 10s clip)
  - VRAM peak (expected < 40 GB with context skip; record actual)
  - Output quality (subjective: does SMPL avatar follow the climber?)

## MVP Positioning Anchor
Per guide §16 and user directive "SABR 그냥 뭐 같은색깔 밟든말든 일단 해볼거고": Phase 1 MVP uses
**pre-rendered demo clips** (run this notebook once per clip, upload mp4 to S3/R2, frontend embeds).
No realtime SABR in production MVP. Phase 3 revisits with Blackwell or H100 pool. This recipe is the
one-shot tool that produces those demo clips.

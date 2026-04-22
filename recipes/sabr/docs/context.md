# Context — SABR

## Authoritative Reference
`C:\Users\kmw16\Desktop\climbIdeaResearch\SABR_WEIGHTS_GUIDE.md` (1258 lines, v4 2026-04-21).
Real-measured byte sizes, code line references, 11 known issues, Blackwell risk matrix.
Every claim below that starts with "guide §N" comes from that file. Read it before making any
non-trivial change.

## Architecture

```
input.mp4 (non-square, 10s @ 24fps typical)
  ↓
[ffmpeg extract frames] → original frames
  ↓
[FGT + LAFC + RAFT video inpainting] → inpainted frames (person removed)
  ↓                                    ↓
  ↓                             [GroundingDINO + AOT/DeAOT + DWPose]
  ↓                                    ↓ (SKIPPED in 40GB path — replace with zeros)
  ↓                             context frames
  ↓                                    ↓
  └─→ DINOv2 ViT-L ←─────────────────┘
      (frames → patch tokens; 490×280 → 35×20 = 700 patches × 1024-dim)
  ↓
combined_vector (seqLen=1100, 700, 1024)  # zero_vector pads to 1100
  ↓
DiT_action diffusion (24 layers, hidden=1024, 16 heads; EMA from 0070000.pt)
  ↓
SMPL 161-dim motion sequence (4 bbox + 3 cam + 144 pose_6d + 10 betas)
  ↓
[PHALP render: SMPL body model → 3D verts → pyrender composite]
  ↓
output.mp4 (SMPL avatar overlaid on inpainted video)
```

Entry: `inference.py --mode {0,1} --ckpt <path> --videoDir <folder>`
- `--mode 0` latent: motion completion (requires context frames). **Our target.**
- `--mode 1` noise: pure generation. Experimental.

Code structure (guide §5 "코드 경로 참조"):
- `inference.py` — orchestrator. `inpaint_person()` + `inference()`.
- `pipeline/environment/tool/video_inpainting.py` — FGT+LAFC+RAFT inpainting subprocess.
- `pipeline/context/run_pipeline.py` — GroundingDINO+AOT context extraction (SKIP in 40GB).
- `pipeline/track/scripts/demo.py` — PHALP mocap (SMPL pose per frame).
- `model/diffusion_transformer.py:356` — DiT_action class.
- `pipeline/context/model.py:670-678` — PHALP auto-downloader (Berkeley URLs = 403; PATCH REQUIRED).
- `model/architecture/train.py:316` — checkpoint filename pattern `f"{steps:07d}.pt"` (origin of
  `0070000.pt`).

## Weights (15.0 GB total, 32 files from 8 servers)

Full catalog: guide §4. Summary by server:

| Server | Files | Total | Risk |
|---|---|---|---|
| Cloudflare R2 (smandava) | 1 (0070000.pt) | 8.94 GB | ✅ 200 OK direct |
| Meta FAIR (dl.fbaipublicfiles.com) | 3 (DINOv2 L/B + SAM ViT-H) | 4.13 GB | ✅ |
| HuggingFace (7 repos) | 5 | 1.22 GB | ✅ |
| Ultralytics releases | 1 (YOLOv8l-seg) | 92 MB | ✅ |
| Google Drive (gdown) | 3 (AOT + DeAOT × 2) | 455 MB | ⚠ virus-scan warning; gdown 4.6+ auto-handles |
| UT Austin Pavlakos | 8 (PHALP HMR + pose + 3D) | 309 MB | ✅ (migrated from Berkeley 403) |
| Dropbox (Princeton RAFT) | 1 | 21 MB | ✅ (zipped; unzip + copy) |
| Local numpy generated | 1 (`dinov2_zero_vector.pt`) | 2.87 MB | n/a — in-cell `pickle.dump(np.zeros((1,700,1024), dtype=np.float32))` |

**Dead paths** (do NOT use):
- `weights_download.zip` Google Drive ID `1RWyyXyUMf97JSvBMJRrv3dvBbTDUlPb-` → 404 (guide §11 issue #2).
  Upstream `prepare_data.sh` fails on `unzip weights_download.zip`. **Do NOT run prepare_data.sh.**
- Berkeley PHALP URLs in `pipeline/context/model.py:670-678` → 403. Must sed-patch to UT Austin.
- `github.com/classner/up/raw/master/models/3D/basicModel_...pkl` in `model.py:662` → 404. Use HMR2.0 mirror.

## Dependencies

### Critical (must-have for inference)
| Package | Upstream pin | Colab 2025.07 stock | Strategy | Risk |
|---|---|---|---|---|
| python | 3.10 (mamba) | 3.11 (host) | condacolab + mamba env | Medium — chumpy needs 3.10 |
| pytorch | nightly + cu121 | 2.6.0+cu124 | upstream install.sh overrides | Medium — nightly can shift |
| torchvision | matching | 0.21.0+cu124 | auto via mamba | — |
| mmcv-full | `mim install` (≈1.7) | not in Colab | install via mim | **High** — sm_120 X but sm_80 OK |
| mmdet | 2.28.1 (2022-11) | — | pin | **High** — 2022 era vs modern numpy |
| mmpose | 0.24.0 (2022-05) | — | pin | **High** — same |
| ultralytics | 8.0.99 (2023-05) | — | pin | Medium |
| flash-attn | latest | — | `pip install --no-build-isolation` | **High** — 10+ min build; v2c shim fallback |
| xformers | mamba build | — | `mamba install -c xformers` | Medium |
| detectron2 | git main | — | `pip install git+…` | Medium — CUDA 13 issue (we're 12.x) |
| chumpy | 0.70 (2020) | — | auto via PHALP | Medium — 3.10 OK |
| timm | 0.4.9 (2020) | — | pin | Medium — very old, PHALP-only |
| segment-anything | git main | — | `pip install git+…` | Low |
| pyrender / PyOpenGL 3.1.0 | pin | — | apt + pip | **High** — OpenGL driver sensitive |
| onnxruntime-gpu | CUDA 12.2 | — | pip | Medium |
| hydra-core | — | pip | Low |

### Optional / cloud
firebase-admin, google-cloud-storage, boto3 — only for data collection. Inference skips.

### Missing from install.sh (runtime-required)
- `chumpy` — transitively via PHALP. Py3.10 clean install.
- `scipy` — SMPL internals. Deprecation only.

## Key Decisions

### Decision: Context-skip path (40GB VRAM target)
- **Context**: Full pipeline needs 80 GB (README FAQ). Colab Pro A100 is 40 GB. Pro+ H100 80GB
  unreliable.
- **Options**:
  1. Full on H100 80GB — unreliable availability.
  2. 40GB context-skip (FAQ-endorsed) — "just see what it outputs for raw inpainted frames".
  3. Quantization fp16/int8 — DiT already fp16; context model (GroundingDINO+AOT) isn't the VRAM
     pressure (SAM ViT-H 2.56GB and DiT ≈9GB are).
  4. CPU offloading — subprocess-heavy code would need deep refactor.
- **Choice**: #2 context-skip. Aligns with MVP "사전 렌더링 데모 1-2개".
- **Outcome**: Pending first Colab run. Need to patch inference.py (no flag exists upstream).

### Decision: condacolab + upstream install.sh (vs direct pip)
- **Context**: install.sh is 40 lines of mamba+conda+pip for Python 3.10 with 2022-era pins. Direct
  pip into Colab's 3.11 base would fight numpy/scipy/torch.
- **Options**:
  1. `condacolab` + install.sh verbatim — authoritative reproduction.
  2. Hand-translate to Colab base pip — fragile.
  3. Docker via `udocker` — overkill.
- **Choice**: #1. 3-5 min overhead but deterministic.
- **Outcome**: Pending first Colab run.

### Decision: Defer MCP connection to user command
- **Context**: User said "연결하지말고 일단" during planning (2026-04-21). Plan + cells first, then
  connection on explicit go.
- **Choice**: `recipe.yaml:mcp.enabled: false` until user flips. `allow_auto_execution: true`
  pre-set for live iteration.
- **Outcome**: When user says "connect MCP", flip + `/colab-mcp` + open_colab_browser_connection.

### Decision: slice `:24` (motion completion) NOT `:seqLen` (reconstruction) — 2026-04-22
- **Context**: After L1-L5 fixes made inference produce visible avatar (100% frames blob-tracked), user
  reported "avatar is doing the SAME motion as input — not solving the problem". Diagnosis: my D24 had
  expanded the `overwrite_first_24frames` slice from `[:,:context_tensor.shape[0] + 24]` (→ `:24` in
  skipContext) to `[:,:self.seqLen]` (→ all 1100 positions). Full-position overwrite leaves DiT with 0
  generative freedom — pure reconstruction of PHALP input.
- **Options**:
  1. Keep `:seqLen` — reliable but not a generator, just re-render.
  2. Revert to `:24` — first 1s of user's motion anchored, DiT generates frames 24-1100. MVP intent.
  3. `:0` (no anchor) — DiT samples from training distribution only; will invent climb unrelated to wall.
- **Choice**: #2. Matches upstream variable name `overwrite_first_24frames`. D26 revert; D24 kept off fresh rebuilds.
- **Outcome**: In-progress verification (post-rebuild run, 2026-04-22).
- **Deeper architectural truth** (must communicate to user): even with #2, SABR is a **motion completion
  model**, not an independent climbing AI. Output = variation of user's input motion, grounded in their
  start pose. The goal "wall photo + user betas → AI solves route" needs a different architecture class
  (MDM / PriorMDM + climbing-specific training). Out of scope for this port.

### Decision: SSOT write-through enforcement — 2026-04-22
- **Context**: User called out that I was discussing decisions in chat without writing to SSOT. CLAUDE.md
  rule explicitly says "After every meaningful change, update tasks.md" and "Key Decisions new decisions
  (with reasoning)".
- **Choice**: Reassert discipline — every architecture decision goes into this file in the same turn it
  was made, not at session-end.
- **Outcome**: Backfill performed 2026-04-22 (this entry + cold-run latency + SAM3 clarification + MCP
  hook bug).

## Performance (measured 2026-04-22, 15s input, A100 40GB, cold runtime)
| Phase | Time | Notes |
|---|---|---|
| install.sh + all deps rebuild | ~20 min | condacolab + mamba + source builds (detectron2 9 min) |
| FGT+LAFC+RAFT inpainting | ~16 min | Optical flow + Poisson blending per batch (36 batches). **Main bottleneck.** |
| PHALP tracking | ~5 min | YOLOv8 detection + 4DHumans SMPL regression |
| DINOv2 feature extract | ~1 min | ViT-L per frame |
| DiT diffusion 250 steps | ~6 min | A100 fp16 — stable, @ 1.43s/it |
| SMPL render 359 frames | **~30s** (GPU via EGL/GLFW, ~75ms/frame — corrected 2026-04-22, initial CPU assumption was WRONG) |
| **Total cold run** | ~25-28 min | ~110× slower than real-time |
| **Synthetic-context path** (skip FGT + PHALP) | **~8-12 min** depending on video length (15s/30s/45s) | Most efficient practical mode |

Implication: unacceptable for interactive service. Optimization priorities:
1. **FGT → ProPainter** (CVPR 2023) — 3-5× inpainting speedup, newer architecture, same interface. Likely
   first win.
2. **DiT 250 → 25 steps** (DDIM skip) — ~10× speedup, mild quality loss. Verify motion smoothness after.
3. **SMPL render parallelization** — pyrender is CPU-bound; replace with nvdiffrast or batched GPU rasterizer.

SAM3 is segmentation only (not inpainting) — can replace YOLOv8/Detectron2 mask step but won't solve the
FGT bottleneck. Noted 2026-04-22 after user asked about SAM3.

## Cross-cutting harness bug fixed during this session — 2026-04-22
### MCP hook spill-envelope silent drop
- **Bug**: `.claude/hooks/_mcp_session_log.py:250-257` — when `get_cells` output exceeded
  `MAX_MCP_OUTPUT_TOKENS` (default 25k), Claude Code spilled to a tool-results file and returned
  `{"content":[{"text":"Error: ... saved to <path>..."}]}` instead of `{"cells":[...]}`. Hook's
  `tool_result.get("cells")` returned `None`, `isinstance(cells, list)` fell through, NO snapshot
  written, NO error logged (silent early-return).
- **Evidence**: 5 `get_cells` calls this session landed in jsonl with `output_preview` starting
  `"Error: result (N chars) exceeds maximum allowed tokens. Output has been saved to ..."`. Same silent
  loss pattern that burned the flux2-klein-4b port.
- **Fix**: Patched to parse spill file path from content envelope and re-hydrate `cells` from disk
  before the `isinstance` check. Added `log_error` on re-hydrate failure so future regressions surface.
- **Scope**: `get_cells` only (other MCP tools don't auto-snapshot). Historical sessions with missing
  `latest-cells.json` / `cells_*.json` ratio vs jsonl get_cells count → likely same bug.
- **Commit gate**: `commit_gate.sh` blocks commit on `.claude/hooks/` changes until
  `Agent(subagent_type='code-reviewer')` + `_code_review_passed.json` written.

## Discovered Issues
Seeded from guide §17 (11 issues); verified ones get ✅ as we hit them.

| # | Error | Root cause | Fix | Verified |
|---|---|---|---|---|
| G1 | R2 `weights_download.zip` 404 | Link expired/private | Use per-source (guide §13 script) | ✅ guide |
| G2 | Berkeley PHALP 403 | Server migration | sed-patch `model.py:670-678` to UT Austin | ✅ guide |
| G3 | `classner/up` SMPL 404 | Repo removed | HMR2.0 HF mirror commit-pinned | ✅ guide |
| G4 | chumpy install fails on 3.11+ | setup.py out of date | Force 3.10 via mamba; chumpy-fix fallback | ✅ guide |
| G5 | `scipy.sparse.csc` DeprecationWarning | Old scipy API in SMPL pkl | Warning only | ✅ guide |
| G6 | gdown virus-scan ≥100MB | GDrive large-file flow | gdown 4.6+ auto-`confirm=t` | ✅ guide |
| G7 | Windows `$HOME` unset | Linux-only code | Colab IS Linux — n/a | ✅ guide (Windows-only) |
| G8 | `pose_predictor_40006.ckpt` rename | PHALP expects `pose_predictor.pth` | `cp` with rename Cell E | ✅ guide |
| G9 | `SMPL_NEUTRAL.pkl` rename + Py2→Py3 | PHALP loader expects name | `convert_pkl` snippet Cell E | ✅ guide |
| G10 | `lafc_single/` ZIP unclear | prepare_data.sh ref lost | Per-source bypass | ✅ guide |
| G11 | OpenGL for pyrender | Colab driver dependent | apt libglu1-mesa etc. in install.sh | Unverified — Colab sudo restricted? |
| S1 | inference.py no `--skipContext` | Upstream has no flag | sed patch to add flag + branch | TODO Cell F |
| S2 | Square videos rejected (line 408) | DiT trained non-square only | Reject in Cell G with clear error | TODO |
| S3 | inference.py hardcodes `$HOME/virtual-avatar-generation/` | `inference.py:24` | `export HOME=/root` Cell B + clone to ~/virtual-avatar-generation/ | TODO Cell B |
| S4 | PyTorch 2.6+ `weights_only=True` blocks dict checkpoint | Security change 2024 | Force `weights_only=False` at line 490 | TODO verify |
| L1 | PHALP `video.inference=True` early-return at frame 50 | `PHALP.py:201` gates pkl save | Remove flag from cmd + add schema field `inference: bool` | ✅ 2026-04-21 |
| L2 | `inference.py` motion-completion blocks commented out | Lines 476-510 + 521-528 disabled by upstream | Uncomment both blocks so PHALP → DiT conditioning connects | ✅ 2026-04-21 D23 |
| L3 | Conditioning slice `[:,:context_tensor.shape[0]+24]` covers only 25/1100 positions | skipContext path has 0-length context | Replace with `[:,:self.seqLen]` + padTensor padLength 1100 | ✅ 2026-04-21 D24 |
| L4 | `gaussian_diffusion.py:291` channel broadcast: inpaint(161) vs model_output(322) | DiT learn_sigma=True doubles output channels | `model_output[:, :inpaint.shape[1], :inpaint.shape[-1]] = inpaint` — overwrite first 161 only | ✅ 2026-04-21 D25 |
| L5 | Avatar invisible in output despite pipeline success | L1-L4 combined: no conditioning reached DiT | Fixed by L1-L4 together. Verified: body-shape blob area 2000-3000px aspect 2.0-2.7 in 100% of 24 sampled frames (F0-F345) | ✅ 2026-04-21 |
| L6 | `video.mp4.mp4` double extension breaks ffmpeg | `inference.py:675` iterates `os.listdir` with `.mp4` in name, then `f"{dir}/{video_name}.mp4"` duplicates | Strip `.mp4` suffix from `video_name` inside the loop | ✅ 2026-04-22 D28 |
| L7 | PHALP pkl not saved on fresh rebuild | `inference.py:412` still had `"video.inference=True"` flag; PHALP.py:201 early-returns when `t > 50 and cfg.video.inference == True`. D20 assumed the `+` hydra prefix was present (added by D16) but skipping D16 meant the raw `video.inference=True` passed through | Remove `video.inference=True` line unconditionally; add `overwrite=false` for idempotency | ✅ 2026-04-22 D30 |
| L8 | `RuntimeError: shape '[1100, -1]' is invalid for input of size 51696` at inference.py:521 | `padTensor`'s `padLength` was upstream default 100, but `seqLen = 1100`. PHALP's 359 frames × 24 joints × 6 rot6d = 51696 — not divisible by 1100 | Change `padLength = 100` → `padLength = 1100` (same seqLen). D24 contained this fix but was skipped wholesale (to avoid its slice expansion). D31 isolates just this line | ✅ 2026-04-22 D31 |
| L9 | Avatar visible only for first 24 frames then disappears entirely (not user-motion reconstruction, actual degeneration) | `:24` slice + skipContext + DINOv2 context = zeros combination. DiT trained with real context vectors has no route signal, so beyond anchor frames the generated SMPL params degenerate (joint collapse / off-screen / NaN-like) | **Architectural**: skipContext (40GB FAQ path) fundamentally breaks SABR's generative capability. Two observed modes — `:seqLen` → reconstruction (no AI variation), `:24` → degeneration (no avatar). Paper confirms: SABR needs context model output to generate plausible unseen motion. No code fix possible inside 40GB budget. Need 80GB full context OR architecture pivot (MDM-class) OR context-component swap (GroundingDINO→YOLOv8-seg, AOT→SAM2) | Documented 2026-04-22 |
| L10 | Blackwell RTX PRO 6000 (sm_120, 96GB) cannot run SABR stack — torch itself refuses basic CUDA ops | **Verified via Colab live test 2026-04-22**: GPU = RTX PRO 6000 Blackwell Server Edition, 97887 MiB, compute_cap 12.0, driver 580.82.07, CUDA toolkit 12.5. Colab base has torch 2.6.0+cu124. Test: `torch.randn(1000,1000,device="cuda") @ x.T` → `RuntimeError: CUDA error: no kernel image is available for execution on the device`. torch 2.6+cu124 (Dec 2024) compiled for archs ≤ sm_90 (Hopper); sm_120 needs torch 2.7+ cu128 (2025+). SABR upstream requires torch 2.1.0+cu121 (2023) for mmcv-full 1.7.2 / mmdet 2.28.1 ABI. **Chain incompatibility**: SABR deps need torch 2.1, Blackwell execution needs torch 2.7+. No overlapping torch version exists. Also verified: `mmcv-full==1.7.2` installed but `libcudart.so.11.0` missing (CUDA 11 wheel vs CUDA 12 runtime); `mmcv==2.1.0` installs but ABI mismatch (`undefined symbol at::_ops::zeros_like::call`). | **Blackwell path is closed** for this SABR version without weeks-long upstream rewrite (mmcv 2.x + mmdet 3.x + all ABI consumers). Practical alternatives: (a) A100 40GB Colab (reconstruction-only mode, confirmed working), (b) A100 80GB via RunPod/Lambda ~$2/hr (full context mode, not yet tested), (c) MDM-class pivot. | Documented 2026-04-22 |
| L11 | 40GB skipContext path confirmed UNSUPPORTED for paper-quality output (4-agent parallel verification) | Spawned 4 independent Opus subagents 2026-04-22 with focused angles: (1) README FAQ literal text, (2) inference.py code-path semantics, (3) train.py CFG dropout analysis, (4) GitHub issues + paper + demo materials. **Unanimous verdict**: (1) README line 67 phrases 40GB as `"just see what it outputs for raw inpainted frames"` — hedged, not a quality claim; (2) inference.py has NO built-in context-free branch, DiT.forward(y) treats y as required positional with no None guard; (3) train.py:237-250 ALWAYS loads context frames per sample, grep for `context_dropout_prob`/`drop_context_p`/null-token = zero hits, the `# enables embedding dropout for CFG` comment at train.py:217 is copy-pasted boilerplate from Meta's original DiT (image class labels) — mechanism does not exist in SABR, `dinov2_zero_vector.pt` is padding-only; (4) GitHub issues open count = 0 on both upstream + mirror, paper arXiv 2406.01056 §5.4 only documents 80GB 8×A100, §6.3 (Trajectory Adherence) shows MORE context → better quality (opposite direction of skip), project-page demos are GPU/config unlabeled. **Converging conclusion**: `skipContext` at inference feeds DiT a distribution the model was never trained on (not a valid CFG unconditional sample, since no CFG training regime exists). Output is OOD by construction. Our empirical observations (reconstruction with `:seqLen` slice, avatar-disappearance with `:24` slice) are the expected failure modes — not bugs in our port. | **Architectural reality confirmed at every layer (docs, code, training, community)**. No tuning fix possible. Realistic paths: (a) rent A100/H100 80GB and run full-context mode, (b) accept reconstruction-only output for 40GB tier, (c) pivot to a context-free architecture (e.g. MDM / PriorMDM). | Verified 2026-04-22 via 4 parallel subagents |
| L12 | Synthetic-context path (user-drawn SAM3 masks on wall photo, no climber video) — feasible in hours, runs on **current A100 40GB Colab** (80GB rental NOT needed), quality expectation HIGH per paper §6.5 | **User idea**: instead of climbing video, feed SAM3-labeled wall photo as synthetic context frames. 4-agent investigation + direct paper read (arXiv 2406.01056v1). **Agent findings**: (1) Format trivially replicable via `draw_mask()` at `pipeline/context/run_pipeline.py:107-129`. (2) Training distribution: NO synthetic samples, no CFG dropout, no augmentation (§5.1). (3) Mechanically static inpainted_frames don't crash (time_embed at `diffusion_transformer.py:335` prevents attention collapse). (4) Reimplementation ~hours: SAM-ViT-H + AOT + PHALP + FGT + GroundingDINO all bypassable. **Paper §6.5 direct quotes (CONTRADICTS initial "OOD" framing)**: §3.4 — authors filter training videos with "extreme swinging or zooming"; §6.2 — evaluation protocol uses "high clarity and stable videography, avoiding random camera swings"; §6.5.3 — "best outputs ... where environment and context are crystal clear". **Conclusion**: duplicated wall photo = stable end of camera-motion spectrum = training sweet spot. **VRAM correction (2026-04-22 revision)**: The paper's "80GB required" claim refers to full auto pipeline's peak VRAM when GroundingDINO (~10GB) + SAM-ViT-H (2.4GB) + AOT (~1GB) + PHALP detection (~3GB) all co-reside in memory. Synthetic-context bypasses ALL of these (user provides context JPGs directly). Remaining memory profile: DiT (~15-25GB during diffusion) + DINOv2-L (~1-2GB) + pyrender (~1GB) + overhead (~5GB) = **~25-35GB peak**. Confirmed empirically in today's 40GB run (36GB peak during DiT). **Synthetic-context path runs on current Colab A100 40GB with no rental**. **Time profile on A100 40GB (revised 2026-04-22 with empirical render data)**: Earlier estimate of "render 5-6 min" was WRONG — today's actual log `Done in 27.035s` for 359 frames = ~75ms/frame = GPU-accelerated (pyrender via EGL or GLFW hardware path, install.sh installs both `libosmesa6-dev` + `libglfw3-dev`). Revised breakdown: `draw_mask()` + JPG writes seconds, wall photo duplication to inpainted_frames ~20-40s (scales with output length), DINOv2 features ~1-3 min (scales with frame count), DiT 250 steps **~6 min (fixed, independent of input length** since `seqLen=1100` hardcoded), SMPL render **~30s-1.5 min** (GPU rasterization, 75ms/frame). **Revised totals**: 15s video → ~8 min, 30s → ~10 min, 45s (max) → ~12 min. **Skips vs today's cold path**: FGT 16 min + PHALP 5 min = ~21 min saved. Real remaining OOD risks (§6.5): unnatural routes (§6.5.1), small holds after 368×640 downsampling (§6.5.2), duration >45s (§6.5.4). Gotchas: `width != height` + portrait assert at `inference.py:406-410`, need 5-20 context JPGs (not 1 or 1100). | **Engineering ~half-day**, **runs on free Colab A100 40GB**, **quality = paper-endorsed best-case per §6.1-6.2 criteria**. Failure modes user-controllable (route design + photo resolution), not architectural. Previous "$2-4 A100 80GB rental required" guidance retracted — 80GB was for context EXTRACTION VRAM not context INGESTION. If successful, delivers "wall photo → AI avatar solves route" service vision at paper-endorsed quality tier on free-tier hardware. | Documented 2026-04-22, paper-verified + VRAM analysis revised |

## Risks
| Risk | Prob | Mitigation |
|---|---|---|
| `install.sh` mmcv-full build fails on Colab gcc/CUDA | Medium | v2b pip-only fallback; alt-build shim if only mmcv fails |
| flash-attn build times out (>10 min) | **High** | v2c: monkey-patch DiT to SDPA; skip flash-attn install |
| 15 GB download hits Colab bandwidth cap | Low-Medium | `curl -C -` retry; split cells; GDrive mount fallback |
| pyrender OpenGL fails (no display server) | Medium | `apt install libegl1-mesa` + `PYOPENGL_PLATFORM=egl` env before render |
| OOM with context-skip on specific input | Medium | Reduce video length/res; document VRAM curve vs clip length |
| Inference > MCP timeout_seconds: 1200 | Medium | Raise to 1800 after first measurement |
| PyTorch 2.6+ `weights_only=True` blocks `.pt` load | Medium-High | Force False; `0070000.pt` is a dict |
| SABR output doesn't match "same-color holds" | **Certain** (user-confirmed) | Out-of-scope; MVP = pre-rendered demo |
| Colab session dies mid-inference | Medium | `mcp.keepalive: true` handles idle; add `output/` checkpoints if added later |
| Blackwell RTX PRO 6000 future deployment | Deferred | Phase 3 (guide §15) |

## Decision Log (reversals allowed)
| Date | Decision / Reversal | Reason |
|---|---|---|
| 2026-04-21 | Initial: 40GB context-skip via condacolab | Matches MVP + README FAQ-endorsed |
| 2026-04-21 | End-to-end inference working after D24+D25 | 3 consecutive failures ("no avatar visible") diagnosed via independent Opus subagent → L3 (slice), L4 (channel broadcast) found. Verified via connected-components analysis on output vs inpainted-only: body-shape blob present in 100% of sampled frames. |
| 2026-04-22 | Runtime wipe (idle timeout) forced full rebuild. D1-D25 minus D24 replayed. D16 skipped as "obsolete" → broke D20's anchor match (video.inference=True silent pass-through). Caught late via L7 (D30). | Lesson: D-cell chain has implicit ordering dependencies that aren't documented. Either inline the fix chain into a single `scripts/replay_patches.sh` or tag anchor-dependent cells so skip-decisions can validate. |
| 2026-04-22 | skipContext + `:24` produces DISAPPEARING avatar, not just reconstructed motion. | Architectural limit confirmed (L9). Reverting my earlier wrong claim that "SABR = motion-completion". Correct framing: SABR generates via context model; we disabled it. No 40GB path delivers both (a) avatar visibility AND (b) AI variation from user input. Must either (i) run 80GB full context, (ii) swap context backbone to lighter models, or (iii) pivot architecture. Pending user decision. |
| 2026-04-22 | Blackwell RTX PRO 6000 tested on Colab, confirmed unusable for this SABR stack. | L10 evidence: basic torch CUDA op fails on sm_120 because Colab's torch 2.6+cu124 was compiled for archs ≤ sm_90. Blackwell needs torch 2.7+cu128, but SABR needs torch 2.1+cu121 for mmcv-full 1.7.2 ABI. These two torch versions never overlap. Two OpenMMLab wheel variants tested (1.7.2 + 2.1.0), both fail with ABI/library mismatch. Practical conclusion: **Blackwell VRAM (96GB) is abundant but software stack is too old for this hardware**. Revert to A100 or rent A100 externally. |
| 2026-04-22 | 4-agent parallel verification closes 40GB debate: `skipContext` architecturally unsupported for paper-quality output. | L11 evidence: 4 independent Opus subagents (README FAQ / code paths / training CFG / GitHub+paper) ALL converge on the same conclusion — upstream has no context-free mode, training had no CFG dropout (the code comment claiming otherwise is a boilerplate-copy lie), README 40GB claim is hedged to `"just see what it outputs"`, zero public evidence of 40GB producing AI-generated motion, paper §6.3 shows MORE context → better quality (skipContext is opposite direction). Our empirical modes (reconstruction / degeneration) are the expected OOD responses. No tuning fix exists at this architecture level. |
| 2026-04-22 | New path identified: **synthetic context** (SAM2 on wall photo + 80GB full-context mode) — engineering feasible in hours, quality uncertain. | L12 evidence: 4-agent investigation of "can we hand-craft context frames without a climber video?". (1) Format replication trivial — reuse `draw_mask()` from `pipeline/context/run_pipeline.py:107-129`. (2) Synthetic context is OOD — training saw only real climbs, no CFG, no augmentation. (3) Static inpainted frames run without NaN (time_embed prevents attention collapse) but OOD. (4) Reimplementation ~HOURS — most of the pose+tracking pipeline is bypassable if the user declares "these N holds = route". Practical test plan: rent A100 80GB ($2-4), write minimal SAM2→context cell, run full-context inference. Accepts known quality risk. If successful, delivers "wall photo → AI avatar solves route" service vision. |
| 2026-04-22 | **Paper §6.5 direct read reverses prior "static OOD" caution**. Reading arXiv 2406.01056v1 PDF directly shows training distribution is deliberately biased toward stable cameras. | Initial L12 caution about "static inpainted_frames OOD" was based on generic "training never saw zero-motion" intuition. Paper §3.4 filters out "extreme swinging or zooming" from training data. §6.2 authors' evaluation uses "stable videography, avoiding random camera swings". §6.5.3 lists "Arbitrary videography" as OOD limitation with explicit phrasing *"best outputs ... where environment and context are crystal clear"*. Static wall photo is at the stable-end of the camera-motion axis — closer to training sweet spot than to the paper's documented OOD edge. Synthetic-context path is now a **paper-endorsed best-case input configuration**, not a risky OOD experiment. Remaining concerns: route realism (§6.5.1), hold size after downsampling (§6.5.2), 45s duration cap (§6.5.4). All user-controllable. |
| 2026-04-22 | **VRAM retraction: synthetic-context runs on free 40GB Colab, no 80GB rental needed**. | Earlier L12 entry guided "rent A100 80GB $2-4" based on README FAQ. Direct analysis: paper's "80GB" claim refers to peak VRAM during auto context EXTRACTION (GroundingDINO + SAM-ViT-H + AOT + PHALP detection co-resident). Synthetic-context scenario bypasses ALL of those — user provides context JPGs directly. Remaining memory profile = DiT + DINOv2-L + pyrender = 25-35GB peak. Today's 40GB skipContext run peaked at 36GB (empirical confirm). Synthetic-context path's added ~10 context JPGs through DINOv2 adds <1GB. Total: well within 40GB budget. Expected end-to-end time: ~12-14 min (saves FGT 18min + PHALP 10min vs today's 30-35 min full cold). |

## Synthetic-Context Implementation Guide (2026-04-22, next session 실행용)

사용자 비전 "벽 사진 + SAM3 수동 라벨링 → AI 아바타가 루트 풀기" 구현 가이드. Paper §6.1-6.2 best-case 입력 조건에 부합. 현재 Colab A100 40GB에서 동작 (80GB 렌트 불필요).

> ⚠️ **2026-04-22 16:00 대규모 정정** — 아래 가이드는 **2차 적대적 검수 (9-agent) 이후 버전**. 이전 버전의 중대한 오류들은 아래 "Adversarial Retractions (2026-04-22)" 섹션에 기록.

### Step 1. SAM3 마스크 생성 (사용자 측)
벽 사진 (세로 portrait, 고해상도 e.g. 1080×1920) → SAM3로 홀드마다 클릭 또는 text prompt → N개 binary mask 획득.
```python
from sam3 import SAM3Predictor
predictor = SAM3Predictor("sam3_weights.pt")
hold_masks = predictor.segment_by_clicks(wall_photo_rgb, hold_click_points)
# hold_masks: List[np.ndarray(H,W) bool], 홀드당 1개
```

### Step 2. Context JPG 생성 (`draw_mask()` 재사용)
**포맷 요구사항** (agent 1 검증):
- JPG 3채널 BGR, 원본 해상도 유지, 세로 방향 필수
- **갯수 = 실제 problem의 홀드 수에 맞춤** (상황별):
  - 볼더링 4-8 홀드 루트 → **전체 라벨링** (4-8)
  - 스포츠 클라이밍 10-20 홀드 → **전체 라벨링** (10-20)
  - 롱 루트 20+ 홀드 → 키 홀드 10-20 선별 (seqLen budget 고려)
  - MoonBoard 문제 → problem 홀드만 (벽 전체 홀드 아님, 10-15 typical)
- 훈련 분포: `interactionFramesPeriod=fps*3` 로 3초+ 접촉 홀드만 자동 저장 → 볼더링 평균 4-8. 근데 상한 하드 cap 아님.
- **seqLen budget**: context N + video frames ≤ 1100. 45s @ 24fps = 1080 frames + 20 context = 1100 exactly fit. 초과 시 video feature truncation 발생.
- **핵심 원칙**: "climb할 홀드만" 정확히 선별. 개수 자체 < 라벨 정확성. 볼더링 4개에 20개 라벨링 = 나머지 16개가 잘못된 route 정보로 모델 혼란.
- 경로: `pipeline/context/assets/contextFrames/1/{video_name}/frame_{N}.jpg`
- 내부 스타일: 벽 배경 + 홀드 흰색 α=0.5 블렌드 + 검정 1픽셀 contour

**권장 코드** (Option B — 홀드별 키프레임):
```python
import cv2, numpy as np, os

# draw_mask (pipeline/context/run_pipeline.py:107-129 원본 그대로 포팅)
def draw_mask(frame, mask, obj_ids, intensity_reduction=1):
    img = (frame.copy() * intensity_reduction).astype(np.uint8)
    palette = np.random.randint(0, 255, (max(obj_ids)+1, 3), dtype=np.uint8)
    palette[0] = [0, 0, 0]
    for oid in obj_ids:
        obj = (mask == oid)
        if obj.sum() == 0: continue
        img[obj] = (0.5 * img[obj] + 0.5 * palette[oid]).astype(np.uint8)
        contours, _ = cv2.findContours(obj.astype(np.uint8)*255, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(img, contours, -1, (0, 0, 0), 1)
    return img

# Integer mask: 0=bg, 1..N=hold IDs
N = len(hold_masks)
int_mask = np.zeros(hold_masks[0].shape, dtype=np.int32)
for i, m in enumerate(hold_masks):
    int_mask[m] = i + 1

# Multi-JPG Option B: 각 파일에 한 홀드씩 하이라이트
ctx_dir = f"{HOME}/virtual-avatar-generation/pipeline/context/assets/contextFrames/1/my_wall"
os.makedirs(ctx_dir, exist_ok=True)
wall_bgr = cv2.imread(wall_photo_path)
for i in range(N):
    single = int_mask.copy()
    single[int_mask != i+1] = 0
    jpg = draw_mask(wall_bgr, single, [i+1])
    cv2.imwrite(f"{ctx_dir}/frame_{i:04d}.jpg", jpg)
```

### Step 3. Inpainted_frames 생성 — **삼각대 B-roll 강력 권장** (사진 복제 금지)

**이전 버전 "사진 1장 × N프레임 복제"는 OOD**. 2차 적대적 검수 (agent "Wall photo duplication vs B-roll") 결론:
- Paper §6.2 "stable videography" ≠ 완전 정지 이미지. handheld micro-motion 포함 개념
- NAV-22M 훈련 분포에 static-identical 프레임 ~0%
- 정적 복제 시 DINOv2 feature 전부 동일 → temporal signal 100% positional / 0% content → **motion prior fallback (generic climbing)**
- **삼각대 10초 실촬이 측정 가능하게 나음**

**실행 절차**:
```bash
# 1. 삼각대 세팅, 세로 방향으로 벽 10초 촬영 (사람 없이)
#    스마트폰 기본 카메라, 1080x1920 @ 30fps
#    미세 진동 있어도 OK (오히려 장점). 걷거나 줌하지 말 것

# 2. 24fps로 downsample + FGT 경로 우회용 직접 배치
ffmpeg -i wall_broll.mp4 -vf "fps=24,scale=-2:640" -q:v 2 \
  /root/virtual-avatar-generation/pipeline/environment/data/results/my_wall.mp4

# 3. inference.py가 이 파일을 ffmpeg로 프레임 추출 (자동, data/inputInpaintedFrames/ 에 저장됨)
```

**fallback**: 삼각대 못 쓸 상황이면 사진 복제해도 "돌긴 돎" — 단 품질은 motion prior 수준. MVP 데모로는 허용.

### Step 4. inference.py 수정 포인트 (적대적 검수 반영)

1. **Mode 0 사용 (mode 1 절대 금지)**. 이전 "mode 1 권장" 철회.
   - Training: `predict_xstart=True` (x_0 예측)
   - Mode 1: `create_diffusion(str(250))` → 기본 `predict_xstart=False` → sampler가 epsilon으로 해석 → `_predict_xstart_from_eps(x_0)` 알제브라 무의미 → **250 steps 쓰레기 누적**
   - **Mode 0 = 정답**. Upstream `if self.mode == "latent":` PHALP pkl 블록은 **이미 주석 처리돼있음** → PHALP 안 읽음 → 추가 수정 불필요
   - 실행: `--mode 0` (기본값) 그대로

2. **`inpaint_person()` 3-way AND guard + 3개 upstream 버그 fix**:
   ```python
   def inpaint_person(self):
       inpainted_mp4 = f"{HOME_DIR}/pipeline/environment/data/results/{self.video_name}.mp4"
       context_dir = f"{HOME_DIR}/pipeline/context/assets/contextFrames/1/{self.video_name}"
       context_jpgs = glob.glob(f"{context_dir}/*.jpg")
       # 3-way AND: videos/<name>.mp4 + results/<name>.mp4 + contextFrames/1/<name>/*.jpg
       if (os.path.exists(self.video_path)  # __init__ cv2가 이거에서 w/h 읽음
           and os.path.exists(inpainted_mp4)
           and os.path.isdir(context_dir) 
           and len(context_jpgs) > 0):
           print(f"[synthetic] skip inpaint+context — {inpainted_mp4} + {len(context_jpgs)} ctx JPGs")
           return
       # upstream 버그 fix #1: self.processNumber 초기화
       if not hasattr(self, 'processNumber'):
           self.processNumber = 1
       # ... 기존 body
   ```

3. **Upstream 버그 `inference.py:386` 제거 필수**:
   ```python
   # DELETE THIS LINE — 사용자가 제공한 synthetic context를 삭제함
   # shutil.rmtree(contextFrames_path)
   ```

4. **Upstream 버그 `inference.py:383` fix (getFrameTensors signature)**:
   ```python
   # Before: context_tensor = self.getFrameTensors(contextFrames_path)  # missing 4 args
   # After:
   context_tensor = self.getFrameTensors(contextFrames_path, 
                                          sorted(os.listdir(contextFrames_path)),
                                          newH, newW, self.device)
   ```

5. **`--skipContext` 끄기**: context_frames 실제 주입되게. Upstream에는 이 플래그 없음 (우리 port가 추가) → 기본 경로 복귀.

6. **Video file 필수**: `videos/<name>.mp4` 가 __init__에서 cv2로 w/h 읽히므로 **반드시 존재해야 함**. Step 3의 B-roll을 여기에도 복사:
   ```bash
   cp /tmp/wall_broll.mp4 /root/virtual-avatar-generation/videos/my_wall.mp4
   ```

### Step 5. 실행
```bash
cd /root/virtual-avatar-generation
conda activate sabr
python inference.py --ckpt 0070000.pt --mode 0 --videoDir videos
# --mode 0 (latent, predict_xstart=True, 훈련과 일치). Mode 1 금지.
# NOT --skipContext. context JPGs가 실제로 주입되게.
```

### Step 6. 체형 override (선택, ±1σ 이내만 안전)

**2026-04-22 적대적 검수 정정**: "1줄 개인화" 주장은 **±1σ (±4-5cm 키)** 내에서만 유효.

실제 교체 포인트는 `inference.py:296` (render-time, `self.init_betas` 로 덮어쓰는 자리):
```python
# Before (upstream 기본, #TODO 주석 플래그 있음):
pred_smpl_params['betas'] = self.init_betas   # SMPL 평균 체형 (≈ zeros(10))

# After (사용자 체형 주입):
user_betas = torch.tensor(user_db.get_betas(user_id))  # (10,)
pred_smpl_params['betas'] = user_betas.to(self.device)
```

**실질 리스크**:
- `pred_camera_t_vector`가 예측 betas (generic) 기준으로 fit됨
- 사용자 체형 교체 시 body 이미지 공간에서 **3-8cm float/sink**
- 키 ±10cm 벗어나면 **발-홀드 misalignment 시각적으로 명확**

**±1σ 초과 사용자**: `pred_camera_t` 재계산 필요. SMPL joint regressor로 user_betas 기반 joint 위치 다시 계산 후 weak-perspective 카메라 re-projection. ~1-2시간 추가 엔지니어링.

**저자 인정**: `inference.py:296`에 `#TODO: remove this and see!!!` 주석 — 저자 본인 validation 안 함.

### Step 7. 최적화 적용 순서 (적대적 검수 반영)

**중요**: 내가 이전에 제안한 Option A1 (O1+O2+O3+O3.5)는 9-agent 2차 검수로 **대부분 무효화됨**.

**재검수 결과 기반 새 우선순위**:

1. **DDIM 50 스텝 테스트** (1-line swap, 잠재적 5x DiT speedup) ← Option B 재활성화
   - Paper §6.1 "250 steps" = 서술, not required
   - `predict_xstart=True` 는 step 수에 덜 민감
   - 변경: `create_diffusion(str(250), ...)` → `create_diffusion("ddim50", ...)`, `p_sample_loop` → `ddim_sample_loop`
   - **품질 empirical 검증** (frame-to-frame pose delta, joint jitter metric)
   - 통과 시: DiT 6분 → 1.2분

2. **O2 Renderer hoist** (40-110초 절약) — pyrender #142 leak 회피 조건:
   ```bash
   pip install PyOpenGL==3.1.5 PyOpenGL-accelerate==3.1.5  # version pin 필수
   ```
   + 5-10 프레임 MD5 diff 테스트 전제

3. **Scene/mesh reuse** (추가 10-20%): VRAM leak (#137, #165) monitor 필수. `nvidia-smi` 중간 체크.

4. **torch 2.3 upgrade + torch.compile**: 별도 conda env `sabr_compile` (mmcv 없이 fresh). ~30분 테스트, 단일 클립 ROI 불명확.

❌ **적용 금지**:
- O1 (1440→640): `tracked_cameras[:, 2] /= up_scale` 때문에 아바타 2.5x 커짐 → clip. Naive swap 불가
- O3.5 (DINOv2 compile): xformers `MemEffAttention` C++ extension graph break + CUDA graphs recompile → **단일 클립 net LOSS 35-125초**

### 예상 결과 (재측정)

| 영상 | Baseline | +DDIM 50 | +O2 + Scene reuse | +torch 2.3 compile |
|---|---|---|---|---|
| 15s | 10분 | ~5분 | ~4분 | ~3분 |
| 30s | 10분 | ~5.5분 | ~4.5분 | ~3.5분 |
| 45s | 12분 | ~7분 | ~6분 | ~5분 |

**경고**: 각 단계마다 품질 regression 검증 필수. DDIM 50은 1.2분 A/B 테스트 가능.

### 출력
`output/{video_name}.mp4` (**native 1440** 해상도 유지, O1 철회로). 렌더 품질 paper demo와 호환.

---

## Adversarial Retractions (2026-04-22 16:00)

9-agent 2차 적대적 검수 결과로 이전 Implementation Guide의 핵심 오류 발견:

| 이전 주장 | 검수 결과 | 정정 |
|---|---|---|
| "Mode 1 사용" | **CRITICAL ERROR** | Training objective (x_0) ≠ Mode 1 sampler (epsilon) → 쓰레기 output. **Mode 0 사용** |
| "사진 1장 복제 = paper best-case" | **OOD (WORSE-THAN-TRIPOD-BROLL)** | NAV-22M는 handheld, static-identical ~0%. DINOv2 feature 전부 동일 → temporal content 0%. **삼각대 10s B-roll** |
| "DDIM 50 = 중 품질 리스크" | **근거 없음, 철회** | Paper §6.1 단순 서술. `predict_xstart=True` 덜 민감. MDM/MotionDiffuse도 50 사용. **empirical test** |
| "5-20 context JPG" | **4-8이 정확** | `interactionFramesPeriod=fps*3`로 3초 이상 접촉 홀드만 저장. 볼더링 루트 평균 4-8 |
| "1줄 betas 개인화" | **±1σ 이내만** | `pred_camera_t` 체형 couple됨. 큰/작은 사용자 3-8cm body float |
| "`os.path.exists` 단일 guard" | **3-way AND + 3 upstream 버그** | videos/ + results/ + contextFrames/ 셋 다 체크. `processNumber` 초기화, `getFrameTensors` sig, `rmtree` 제거 |
| "output_resolution 1440→640 1줄 변경" | **O1 NO — camera depth 깨짐** | `tracked_cameras[:, 2] /= up_scale` 커플링. 아바타 clip |
| "torch.compile on DiT = 25-35%" | **실제 8-14%, 5개 breakage** | autocast+reduce-overhead 버그 (#110904), flash_attn stub stride mismatch, 8 einops graph break. torch 2.3+ 필요 |
| "DINOv2 compile = 30%" | **NO — net loss 단일 클립** | xformers `MemEffAttention` graph break, CUDA graphs recompile |
| "ProPainter 3-5x faster" | **실제 2-3x, MVP 범위 밖** | 400-LOC refactor + OOD risk. Synthetic-context path에선 dead code |

**최종 net effect**: 구현 단순해짐 (Mode 0 + 삼각대 B-roll + 4-8 JPG + 3 upstream fix). 속도 최적화는 DDIM 50 empirical test가 가장 큰 잠재 이득.



## Optimization Matrix (2026-04-22, 4-agent 검증, 250 DDPM 유지)

사용자 요청: DDPM steps는 250 그대로 (품질 논문 보증 유지) + 나머지 안전 최적화만.

| # | 최적화 | 공수 | Speedup | 위험 | 소스 |
|---|---|---|---|---|---|
| O1 | `output_resolution` 1440→640 (`inference.py:545` 1-line) | 5분 | render 75ms → 12-18ms (5-6x) | ffmpeg upscale시 mesh edge blur (960 중간값 선호 가능) | Agent 1 검증 |
| O2 | `Renderer()` 루프 밖 hoist (현재 frame마다 재생성) | 30분 | render 추가 20-30% | 없음 | Agent 1 (보너스 발견) |
| O3 | `torch.compile(dit, mode="reduce-overhead", dynamic=False)` + `diffusion_transformer.py:342-343` checkpoint strip | 1-2h | DiT 6분 → 4분 (25-35%) | torch 2.1 graph break 2-3개, FP16 fusion 1e-3 rounding | Agent 2 검증 |
| O3.5 | `torch.compile(dinov2_backbone, mode="reduce-overhead")` — DINOv2 feature 추출 가속 | 5분 (1줄 추가) | DINOv2 3분 → 2분 (30%) | O3와 동일 — negligible | O3 확장 |
| ~~O4~~ | ~~BF16 switch~~ | **SKIP** — 이미 FP16 autocast, A100에서 동일 throughput | 0% | Agent 3 검증 |
| O5 | nvdiffrast 교체 (~150-200 LOC + fragment shader) | 1-2일 | render 54s → 1-2s (batched) | PBR → Lambertian shading 시각 차이 | Agent 4 검증 |

**영상 길이별 예상 시간 (Option A1 = O1+O2+O3+O3.5 적용)**:
| 영상 | DINOv2 (compiled) | DiT (compiled) | Render+setup | **Total** |
|---|---|---|---|---|
| 15s (370 frames) | 40초 | 4분 | 50초 | **~6분** |
| 30s (730 frames) | 1.5분 | 4분 | 1분 | **~6.5분** |
| 45s (1090 frames) | 2분 | 4분 | 1분 | **~7분** |

- Baseline (현재 synthetic-context, 30s): ~10분
- Option A1 (O1~O3.5): 30s **~6.5분**, 45s **~7분**. ROI 최상.
- Option A2 (A1 + O5 nvdiffrast): 추가 1-2일 투자 대비 20초 절약 — real-time 서비스 아니면 불필요.

**Bottleneck 분석**: A1 적용 후 DiT (4분, seqLen=1100 고정)가 합산 시간의 55-65%. Render/DINOv2는 이미 빠름. 더 줄이려면 250 DDPM 감소 필요 (Option B, 품질 보존을 위해 제외).

**구현 순서**: O1 (5분) → O2 (30분) → 테스트 → O3 + O3.5 (1-2h) → 테스트. 각 단계 품질 regression 없음 확인 후 다음으로.

## Service Design Limits (2026-04-22 확정)

사용자 서비스 비전 "유저 사진 + 벽 사진 → 내 체형 아바타가 내 벽 오르는 영상"과 SABR 실제 능력 간 gap:

| 사용자 비전 | SABR 실제 능력 | 격차 해소 가능성 |
|---|---|---|
| 내 벽 사진 → AI가 루트 풀이 | ✅ 80GB full context + synthetic SAM3 labels (§6.5 best-case 입력) | 반나절 구현, $2-4 |
| 벽 사진만으로 가능 | ✅ `draw_mask()` 포팅 + 사진 복제 inpainted_frames | 논문이 암묵적 권장 (§3.4/§6.2/§6.5.3) |
| 내 체형에 맞는 루트 | ❌ DiT 입력에 betas 없음 (mode 1). 루트 선택 / reach / 자세 전부 평균 체형 기준 | **불가능** (모델 레벨 수정 필요) |
| 내 체형으로 렌더 | ✅ 렌더 시점 `smpl(betas=user_betas)` override | 1줄 수정 |
| 체형에 맞는 모션 연결 | ⚠ 모션-체형 mismatch 시각적 artifact | IK 후처리로 완화 가능 (2-3일) |

**핵심 결론**: 루트 시퀀스 선택은 **체형 무관**. 논문 §6.2에서 저자들도 mean shape로 override — 체형 개인화는 이 모델로 불가.

MVP 타협안: "평균 체형 모션 + 사용자 betas 렌더 override". 키 큰 사용자는 팔이 홀드 사이 공중에, 키 작은 사용자는 손이 홀드 너머까지 뻗는 mismatch 있음. IK 후처리 또는 DiT 재훈련 없이는 해결 불가.

## Artifact Locations
| Path | Contents | Gitignored? |
|---|---|---|
| `outputs/notebooks/sabr.ipynb` | Generated notebook | Yes |
| `outputs/e2e/sabr/` | Per-cell outputs | Yes |
| `outputs/mcp-sessions/sabr/` | MCP JSONL + snapshots | Yes |
| `recipes/sabr/exports/` | Backend/frontend contract (generated) | No (committed) |

---

**Reference chain** (new porters read in order):
1. `SABR_WEIGHTS_GUIDE.md` (local auth ref, 1258 lines)
2. This `context.md`
3. `plan.md`
4. `tasks.md`
5. `notebook_manifest.yaml`

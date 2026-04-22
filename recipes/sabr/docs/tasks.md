# Tasks — SABR Colab Port

> **Strategy Fallback Tree**: v1 (condacolab + upstream install.sh) is default. If a step
> measurably fails, log in `context.md` Discovered Issues, activate appropriate v2 section.
> Never delete v1 checkmarks — failure history guides the next porter.

## Setup
- [x] Copy `_template` → `recipes/sabr/`
- [x] `recipe.yaml` updated (upstream.repo, runtime A100 40GB 2025.07, mcp deferred)
- [x] `docs/plan.md` filled (goal / scope / approach / success criteria)
- [x] `docs/context.md` filled (architecture + deps + 15 seeded issues)
- [x] `docs/tasks.md` this file
- [ ] `scripts/set_active_recipe.sh sabr`
- [x] Check `colab-runtimes/SUMMARY.md` — runtime 2025.07 selected
- [x] Check `docs/COMMON_ERRORS.md` — no SABR-specific entries
- [x] Check `docs/PORTING_PATTERNS.md` §3 (conda isolation) matches v1 strategy

## v1 — condacolab + upstream install.sh (default)

### Scaffolding
- [ ] `requirements_opt1.txt` — minimal (condacolab bootstrap only; real deps from install.sh)
- [ ] `notebook_manifest.yaml` Cell A: GPU + VRAM + disk preflight
- [ ] `notebook_manifest.yaml` Cell B: `export HOME=/root`, git clone, cd
- [ ] `notebook_manifest.yaml` Cell C: weights download (15 GB; guide §13)
- [ ] `notebook_manifest.yaml` Cell D: condacolab install + upstream install.sh
- [ ] `notebook_manifest.yaml` Cell E: PHALP URL patch + SMPL convert + CACHE_DIR
- [ ] `notebook_manifest.yaml` Cell F: context-skip patch (inference.py) + assert
- [ ] `notebook_manifest.yaml` Cell G: input video upload + non-square assert
- [ ] `notebook_manifest.yaml` Cell H: run inference
- [ ] `notebook_manifest.yaml` Cell I: display output + files.download()
- [ ] `generate_notebook.py sabr` succeeds (non-empty cells)

### Cold run (first Colab test)
- [ ] `git clone` completes (~30s)
- [ ] Cell C: all 32 files present with correct byte sizes (guide Appendix A)
- [ ] condacolab: kernel restart handled, `sabr` env visible after
- [ ] install.sh completes (expected 15-25 min; record actual)
- [ ] **If flash-attn build fails or >10 min**: activate v2c (SDPA shim); log in `context.md`
- [ ] Cell E: all 9 CACHE_DIR files present; PHALP URL patch verified via grep
- [ ] Cell F: inference.py has `--skipContext`; assert passes
- [ ] Cell G: sample video uploaded, non-square
- [ ] Cell H: `python inference.py` exit 0 (expected 5-15 min; record actual)
- [ ] Cell I: `output/<name>.mp4` exists, > 1 MB, valid mp4
- [ ] VRAM peak < 40 GB (`nvidia-smi` during H); record peak
- [ ] All metrics logged in `context.md`

## v2 — Fallbacks

### v2a — Runtime rollback
Activate when: condacolab 0.1.x fails or mamba hangs on 2025.07.
- [ ] Add "Runtime > Change runtime type > 2025.07 (or older)" markdown to Cell A
- [ ] Re-test Cell D onwards
- [ ] Document in `recipe.yaml.runtime.colab_version`

### v2b — Direct pip (skip mamba)
Activate when: v1 install.sh > 30 min or repeatedly fails.
- [ ] Replace Cell D with transpiled steps: `pip install torch==... mmcv-full mmdet==2.28.1 mmpose==0.24.0 ...`
- [ ] Skip `mamba create`
- [ ] Patch E/F/H to use Colab Py3.11 directly
- [ ] Likely needs chumpy-fix instead of chumpy; shim if needed
- [ ] Re-test fail-fast Cell C
- [ ] Document adjustments in `requirements_opt2.txt`

### v2c — SDPA shim for flash-attn
Activate on: flash-attn build fail or >10 min.
- [ ] Read `docs/PORTING_PATTERNS.md` §4
- [ ] Skip `pip install flash-attn` in install.sh (or comment out)
- [ ] Locate DiT attention: `model/architecture/diffusion_transformer.py` DiTBlock
- [ ] Monkey-patch: `flash_attn_func(...)` → `F.scaled_dot_product_attention(...)`
- [ ] Create stub `flash_attn/__init__.py` with re-exports if modules fail import
- [ ] **assert via import test** — fail-fast
- [ ] Re-run Cell H; confirm diffusion still produces plausible output

### v2d — Manual miniforge
Activate when: v2a fails AND condacolab upstream broken.
- [ ] `wget https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh`
- [ ] `bash Miniforge3-Linux-x86_64.sh -b -p /opt/miniforge`
- [ ] Activate miniforge, create `sabr` env manually
- [ ] Re-run install.sh contents (minus `mamba create`)
- [ ] 5-10 min overhead
- [ ] Document as "condacolab replacement" in `context.md`

## Patches (reusable)

### P1: PHALP URL Berkeley→UT-Austin
File: `pipeline/context/model.py:670-678`
- [ ] `sed -i 's|people.eecs.berkeley.edu/~jathushan|www.cs.utexas.edu/~pavlakos|g' pipeline/context/model.py`
- [ ] Assert: `grep -c pavlakos pipeline/context/model.py` ≥ 5

### P2: SMPL basicModel → SMPL_NEUTRAL.pkl
Python (chumpy→numpy → Py3 pickle).
- [ ] src = `~/virtual-avatar-generation/pipeline/track/data/basicModel_neutral_lbs_10_207_0_v1.0.0.pkl`
- [ ] dst = `~/.cache/phalp/3D/models/smpl/SMPL_NEUTRAL.pkl`
- [ ] Load `encoding='latin1'`; iterate dict; `np.array(v)` for chumpy.Ch types
- [ ] `pickle.dump(d, f, protocol=2)` to dst
- [ ] Assert dst exists, size > 30 MB

### P3: PHALP weight renames
- [ ] `cp hmar_v2_weights.pth ~/.cache/phalp/weights/` (no rename)
- [ ] `cp pose_predictor_40006.ckpt ~/.cache/phalp/weights/pose_predictor.pth`
- [ ] `cp config_40006.yaml ~/.cache/phalp/weights/pose_predictor.yaml`
- [ ] Assert all 3 at destination

### P4: inference.py `--skipContext` flag
File: `inference.py`
- [ ] Add `parser.add_argument('--skipContext', action='store_true')` in `main()` ≈ line 648
- [ ] `RunPipeline.__init__` accept `skip_context` param
- [ ] In `inference()` ≈ line 383 (where `context_tensor = self.getFrameTensors(contextFrames_path)`):
  - If `self.skip_context`: `context_tensor = torch.zeros(1, 3, newH, newW, device=self.device)`
    OR duplicate inpainted frames as context
- [ ] Assert via grep: `'--skipContext' in open('inference.py').read()`

### P5: Force `weights_only=False`
File: `inference.py:490`
- [ ] Before: `self.checkpoint = torch.load(self.checkpoint)`
- [ ] After:  `self.checkpoint = torch.load(self.checkpoint, weights_only=False)`
- [ ] Only if PyTorch 2.6+ active (check via cell). Upstream uses nightly so default may differ.

## Validation (all strategies)
- [ ] `uv run python scripts/smoke_test.py` passes
- [ ] `uv run python tools/generate_notebook.py sabr` succeeds
- [ ] `outputs/notebooks/sabr.ipynb` valid JSON
- [ ] Colab cells run on cold fresh runtime without error
- [ ] `output/<video>.mp4` valid (ffprobe shows h264)
- [ ] Update `context.md` Discovered Issues with every error (even resolved)
- [ ] Promote generalizable fixes to `docs/COMMON_ERRORS.md`
- [ ] Update `CLAUDE.md` Porting Patterns if condacolab+upstream becomes a reusable pattern

## Colab MCP (live) — when user flips `recipe.yaml:mcp.enabled: true`
- [ ] `scripts/set_active_recipe.sh sabr` + `source .claude/.env` before claude
- [ ] User says "connect MCP" → `/colab-mcp` → `open_colab_browser_connection`
- [ ] Cell A preflight (auto): `torch.cuda.get_device_name(0)` contains "A100"
- [ ] Per-cell backup after EVERY `run_code_cell`: call `get_cells(0, N)` — hook writes snapshot
- [ ] No `output over budget` in `.claude/_hook_errors.log` (else raise `mcp.max_tool_output_tokens`)
- [ ] `.claude/_mcp_tool_calls.log` reviewed for unexpected calls
- [ ] MCP edits promoted via `/colab-mcp-sync sabr` — dry-run → review → `--apply`
- [ ] `generate_notebook.py sabr` re-run after `--apply`
- [ ] Close Colab tab cleanly at session end

## Reversal & Re-judgement
- **2026-04-22 D24 reversed by D26**: conditioning slice expansion from `:context_tensor.shape[0] + 24`
  to `:self.seqLen` produced reconstruction mode (no DiT variation) — reverted back to original `:24`
  for motion completion. D24 cell kept in manifest as failure-history per harness rule but NOT replayed
  on fresh rebuilds.
- **2026-04-22 SSOT discipline relapse**: had to backfill Key Decisions (motion-completion rationale,
  cold-run latency table, MCP hook bug) after user caught me discussing in chat without writing.

## Post-success (do before next session-end)
- [x] Promote MCP cells to manifest via `/colab-mcp-sync sabr --apply` — DONE 2026-04-22 (71 cells)
- [ ] Consolidate all D-cells into single `scripts/replay_patches.sh` so fresh-runtime rebuilds are idempotent
- [ ] Pin upstream SHA `e4f1dd2` in `recipe.yaml:upstream.ref`
- [ ] Promote hook fix (`_mcp_session_log.py` spill re-hydration) via code-reviewer + commit
- [x] Decide: stay on SABR (accept motion-completion semantics) or pivot to MDM-class — **STAY with SABR, synthetic-context + full context mode** (2026-04-22, paper §6.5 verified as best-case input)
- [ ] If staying: evaluate FGT → ProPainter replacement — **DROPPED** (synthetic-context 경로는 FGT 스킵하므로 무관)

## Synthetic-Context path (next session, see context.md "Synthetic-Context Implementation Guide")
- [ ] SAM3 setup: install + weights
- [ ] Vertical wall photo 고해상도 촬영 (세로 방향, inference.py:406 assert 통과)
- [ ] SAM3로 홀드 라벨링 (클릭 또는 text prompt)
- [ ] `draw_mask()` 20줄 포팅하여 Colab에 셀로 추가 — Multi-JPG Option B (홀드당 1개)
- [ ] Inpainted_frames 생성 (벽 사진 360/720/1080 프레임 복제)
- [ ] inference.py 수정: (1) mode 1 사용 OR 기본값 변경, (2) `inpaint_person()` 스킵 가드 추가
- [ ] `--skipContext` 제거하고 실행. `videoPklFile` 로드 분기 타지 않는지 확인 (mode=1이면 자동)
- [ ] 첫 실행 검증: 출력에 AI 생성 모션 있는지 (frame-by-frame 차이 분석, 어제 쓴 connected-components 검증 재활용)

## Optimization (synthetic-context 성공 후 추가)
- [ ] O1: `inference.py:545` output_resolution 1440→640
- [ ] O2: Renderer init 루프 밖으로 hoist
- [ ] O3: `torch.compile(dit, reduce-overhead)` + `diffusion_transformer.py:342-343` checkpoint wrapper 제거
- [ ] O3.5: `torch.compile(backbone)` for DINOv2
- [ ] 각 step 후 품질 regression 검증
- [ ] 목표: 30s video 10분 → 6.5분, 45s video → 7분

## 개인화 서비스 (사용자 체형 override, 선택)
- [ ] `user_db` 스키마 설계 (user_id → betas 10-dim + height 측정값)
- [ ] 최초 등록 플로우: 사용자 전신 사진/영상 → PHALP → betas 추출 → DB 저장
- [ ] 매 inference: `inference.py:552` betas_vector를 user_betas로 override
- [ ] 시각적 mismatch 수준 측정 (키 편차 ±10cm에서 손-홀드 거리 오차 얼마)

---
> Check off immediately after each item. Failed steps stay checked with FAIL annotation — they're history.
> Every error → `context.md` Discovered Issues first, then fix notes here.
> Patch recipes P1-P5 are reusable; update if new issues found live.

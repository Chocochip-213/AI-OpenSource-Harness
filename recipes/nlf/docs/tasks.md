# Tasks — NLF Colab Port

> **Strategy Fallback Tree**: v1 (Direct pip on Colab 2025.07) is default and overwhelmingly likely
> to succeed (`torch + torchvision` pre-installed). If anything fails, log in `context.md`
> Discovered Issues and activate the appropriate v2. **Never delete v1 checkmarks** — failure
> history guides future porters (Ever lesson: trellis2 v1→v2 saved ~3 days).

## Setup
- [x] `git checkout -b recipe/nlf` from master
- [x] `cp -r recipes/_template recipes/nlf/`
- [x] `bash scripts/set_active_recipe.sh nlf` (writes `.claude/last_recipe.txt` + `.claude/.env` with `MCP_TIMEOUT=300000ms`)
- [x] OpenCode 10-subagent deep analysis (`nlf-clone-analysis/NLF_PORT_BRIEF.md` + 10 sub-reports)
- [x] Verify OpenCode citations (5/5 random samples passed: `pyproject.toml`, `install_dependencies.sh:67-85`, `environment_*.yml:5-58`, `multiperson_model.py:80-110`, `README.md:5`)
- [x] Update `recipe.yaml` (upstream pin `f8611fc7…`, runtime 2025.07, vram 16, disk 10, MCP enabled, A100, keepalive)
- [x] Write `docs/plan.md` (goal / scope / approach / cell plan / success criteria)
- [x] Write `docs/context.md` (architecture / weights / deps / Key Decisions / risks / decision log)
- [x] Write `docs/tasks.md` (this file)
- [x] `requirements_opt1.txt` — torch + torchvision + Pillow + matplotlib (all pre-installed; documentation only)
- [x] Check `colab-runtimes/SUMMARY.md` — 2025.07 confirmed (Python 3.11, torch 2.6.0+cu124)
- [x] Check `docs/COMMON_ERRORS.md` — N/A for NLF (no flash-attn / spconv / numpy downgrade scenarios)
- [x] Check `docs/PORTING_PATTERNS.md` §1 — Direct pip selected as v1

## v1 — Direct pip (default, try first)

### Scaffolding (this session)
- [x] `notebook_manifest.yaml` markdown header (title, runtime, ETA, license)
- [x] `notebook_manifest.yaml` Cell B `clone_repo` (with SHA checkout + assert example_image.jpg)
- [x] `notebook_manifest.yaml` Cell C `ensure_packages` (importlib.util.find_spec + CUDA assert)
- [x] `notebook_manifest.yaml` Cell D `download_torchscript` (495,696,900 byte assert)
- [x] `notebook_manifest.yaml` Cell E `load_model` (torchvision before torch.jit.load; `cuda`; globals cache)
- [x] `notebook_manifest.yaml` Cell F `run_inference` (`torch.inference_mode` + `torch.device("cuda")`)
- [x] `notebook_manifest.yaml` Cell G `verify_output` (13 keys assert)
- [x] `notebook_manifest.yaml` Cell H `visualize` (matplotlib scatter vertices2d + joints2d)
- [x] `notebook_manifest.yaml` Cell I `save_outputs` (torch.save + files.download)
- [x] `uv run python tools/generate_notebook.py nlf` succeeds (non-empty cells; preflight + keepalive auto-injected)
- [x] `uv run python scripts/smoke_test.py` passes (all .py compile, all imports OK)
- [x] `Agent(subagent_type="code-reviewer")` ran (Opus 4.7) — flagged 1 P1 (Cell G `boxes` key + line citations) + 2 P2 (cell F idempotency comment, orphan exports template). P1 fixed; P2 cell F idempotency note added; P2 exports left as template-inherited (referenced via `recipe.yaml.integration.contract_files`). Marker `.claude/_code_review_passed.json` written.
- [x] First commit: `0227846 feat(nlf): recipe scaffold + adversarial-verified MVP plan` (15 files, 1404 insertions; recipes/sabr/ correctly left untracked)

### Cold run (MCP-driven, runtime 2026.04 / 2025.07 — both verified)
- [x] Cell 0a (auto-injected preflight): `NVIDIA A100-SXM4-40GB`, 42.4 GB VRAM, expected match — PASSED
- [x] Cell 0b (auto-injected keepalive): daemon heartbeat thread alive
- [x] Cell B: `git clone` <60s; `example_image.jpg` + `demo.ipynb` present
- [x] Cell C: 4/4 base packages already installed on 2026.04 (torch 2.10.0+cu128)
- [x] Cell D: 473 MB download <120s; `bytes: 495696900` exact match
- [x] Cell E: model loaded on cuda; image_shape `(3, 853, 1280)` for example_image
- [x] Cell F (v0.3 = smoke_inference): all 14 keys returned including `boxes` (n_persons=2 in example_image.jpg)
- [x] Cell G (v0.3 = verify_keys): EXPECTED 14 keys all present — fail-fast schema check PASS
- [x] Output shapes recorded: pose `(N,72)`, betas `(N,10)`, vertices3d `(N,6890,3)`, joints3d `(N,24,3)` — context.md Architecture
- [x] **Runtime divergence finding**: 2026.04 (torch 2.10) works in addition to 2025.07 (torch 2.6). Forward-compat verified.

### Endpoint serving (this session, post-refactor)
- [x] Manifest v0.3 refactor: H/I/J/K offline cells removed → H serve / I tunnel / J forever-loop added (10 manual + 2 auto-injected = 12 total)
- [x] Cell H FastAPI v0.3 — `/embed` (PRIMARY) + `/infer` + `/compare` + `/health` + `/docs` (Swagger) on :7860 background thread
- [x] Cell I cloudflared quick tunnel — public URL printed within 60s (e.g. `ranking-aged-easy-southern.trycloudflare.com`)
- [x] Cell J forever-loop — foreground heartbeat every 60s → Colab idle 0
- [x] Bug fix: `_decode` PIL→numpy chain failed on torch 2.10 (numpy 2.x non-writeable + bad stride for SMPL TorchScript) → switched to `torchvision.io.decode_image` with `bytearray(raw)` writable buffer
- [x] Bug fix: `rigid_proportions` returned `[np.float32, ...]` → FastAPI jsonable_encoder TypeError → wrap each segment in `float()` for JSON serialization
- [x] External validation: `curl /health` 200 OK with model_loaded+A100 status
- [x] External validation: `curl /embed` × 3 (줄리엔강/김병만/이수근) all return 7-dim vector with `pose_invariant:true, height_invariant:true`
- [x] External validation: `curl /compare` 3-way returns pairwise distance matrix
- [x] **Determinism verified**: predictions matched manual calculation to 4 decimal places (e.g. 김병만↔이수근 predicted 0.0077 / actual 0.0076)
- [x] **Real-world signal**: `hip_w_norm` 줄리엔강 0.0813 (athletic V-taper) vs 코미디언 0.0960~0.0973 — body type correctly differentiated
- [x] Second commit: `501b050 feat(nlf): refactor manifest to endpoint-first (FastAPI + cloudflared) + 2 bug fixes`

## v2 — Strategy Fallback (activate ONE when v1 fails — do not delete v1)

### v2a: Runtime Rollback
**Trigger**: `torch.jit.load` fails with op-signature error on torch 2.6.0+cu124
(unlikely — TorchScript was almost certainly saved on torch ≤ 2.6 given the 2025-05 release date).
- [ ] Identify earliest Colab runtime supporting NLF (check `colab-runtimes/SUMMARY.md` for 2024.xx if available; or rebuild TorchScript from `nlf/pt/multiperson/save_model.py:24-48` — last resort)
- [ ] Update `recipe.yaml.runtime.colab_version`
- [ ] Re-test cells E onwards
- [ ] Document in `context.md` Discovered Issues

### v2b: Selective Downgrade + Patch
**Trigger**: marked **N/A** — no version-sensitive single package in the MVP path. Activate only
if a future appendix (SMPL-X, video, source-side scripts) hits a single-package conflict.
- [ ] Identify the conflicting package
- [ ] `requirements_opt2.txt` with narrow pin
- [ ] Add `str.replace`-with-assert patch cell (per `docs/PORTING_PATTERNS.md` §2)
- [ ] Re-test cell C

### v2c: Shim / Monkey-patch
**Trigger**: marked **N/A** — NLF doesn't depend on `flash-attn` / `xformers` / `nvdiffrast`.
Reserved for hypothetical future appendix paths only.

### v2d: Conda Isolation
**Trigger**: marked **N/A** — no C-extension ABI conflicts in the MVP. NLF env yml has `chumpy` /
`mayavi` / etc but they're not in our minimum subset. Reserved for if MVP scope expands into
source-side scripts that pull in chumpy.

## Validation (all strategies)
- [ ] `smoke_test.py` passes locally
- [ ] `generate_notebook.py` succeeds (non-blank notebook)
- [ ] Colab cells run sequentially without error (cold fresh runtime)
- [ ] Input → output verified with metrics in `context.md`
- [ ] Record every error encountered (even resolved) in `context.md` Discovered Issues
- [ ] Promote generalizable fixes to `docs/COMMON_ERRORS.md`
- [ ] Update `CLAUDE.md` Porting Patterns table if a new pattern emerged

## Colab MCP (live runtime) — `recipe.yaml:mcp.enabled: true`
- [x] `.claude/.env` written by `set_active_recipe.sh nlf` (`MCP_TIMEOUT=300000ms`, `MAX_MCP_OUTPUT_TOKENS=10000`)
- [ ] `source .claude/.env && claude` before MCP session
- [ ] `/colab-mcp` opens browser handshake; approve Colab tab
- [ ] Auto-injected preflight asserts A100 (warn-only on mismatch; `vram_min_gb: 16` is the hard gate)
- [ ] Run cells B-I via MCP `run_code_cell`; per-cell `get_cells` snapshot auto-saved by hook
- [ ] No `output over budget` warnings in `.claude/_hook_errors.log` (else raise `mcp.max_tool_output_tokens` from 10000)
- [ ] `.claude/_mcp_tool_calls.log` reviewed for unexpected calls
- [ ] If any cell modified live: `/colab-mcp-sync nlf --apply` → manifest patched + `.ipynb` regenerated
- [ ] Colab tab closed cleanly; no residual cells from exploration

## Reversal & Re-judgement
- 2026-04-27: Initial — MVP = PyTorch TorchScript single-image only. Scope confirmed by OpenCode
  brief. SMPL-X / TF / video deferred to optional appendices.
- _Quarterly review trigger_: 2026-07-27 — re-bump `upstream.ref` SHA if upstream pushes valuable
  fixes; re-verify cell plan against new HEAD. Sooner if any reported regression.

---
> Check off IMMEDIATELY after each item (not at session end).
> Decisions → `context.md` Key Decisions. Errors → `context.md` Discovered Issues table.
> When v1 fails → keep v1 checked as-is, add v2 section. Failure history is valuable.

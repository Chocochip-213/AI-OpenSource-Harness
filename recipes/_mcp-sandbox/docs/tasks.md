# Tasks — _mcp-sandbox (Phase 2 — DONE 2026-04-20)

> All tasks below were completed during the live cycle on 2026-04-20.
> Detailed run log + 11 findings: `docs/context.md` "Phase 2 Discovered Issues" + "Live cycle complete".
> Sandbox stays in the repo as the canonical reference for Phase-3 readiness checks.

## Pre-flight
- [x] Copy `_template` → `recipes/_mcp-sandbox/`
- [x] Set `recipe.yaml:mcp.enabled: true`, `allow_auto_execution: false`, `preferred_gpu: T4`
- [x] Keep `notebook_manifest.yaml` minimal (3 cells: import, matmul, report)
- [x] `scripts/set_active_recipe.sh _mcp-sandbox` (writes `.claude/.env`)
- [x] `uv run python tools/generate_notebook.py _mcp-sandbox` — preflight + keepalive auto-injected → 4 cells (B/C/D + auto Cell A)

## Fresh Claude session
- [x] Exit prior `claude` process
- [x] `source .claude/.env`
- [x] Start new `claude` session from repo root
- [x] `claude mcp list` — `colab-mcp ✓ Connected`

## Live MCP validation
- [x] Asked Claude: "Open the Colab connection and run the sandbox cells one by one"
- [x] `mcp__colab-mcp__open_colab_browser_connection` returned `{"result": true}` (round 3 — earlier rounds caught the multi-Google-account UX issue)
- [x] Browser tab opened → handshake approved
- [x] PreToolUse hook let the call through (after the matcher fix from `fix(hooks): PreToolUse matcher must be ""` commit, `recipe.yaml:mcp.enabled: true`)
- [x] `.claude/_mcp_tool_calls.log` populated — code/content fields hashed, cell_id in clear
- [x] `outputs/mcp-sessions/_mcp-sandbox/<session>.jsonl` populated — 8 entries this session
- [x] Dynamic tool list: 7 tools surfaced (`add_code_cell`, `add_text_cell`, `update_cell`, `delete_cell`, `move_cell`, `run_code_cell`, `get_cells`)

## First cell runs
- [x] Cell A preflight passed — A100-SXM4-40GB allocated (preferred_gpu=T4 mismatch → soft warn as designed; VRAM ≫ 8 GB)
- [x] Cell B (matmul) → `shape: (1024, 1024)`, `max abs: 147.83`
- [x] Cell C (report) → `Device: NVIDIA A100-SXM4-40GB`, `VRAM 41.82 / 42.41 GB`, `Sandbox OK — Phase 2 handshake validated`
- [x] `allow_auto_execution: false` first attempt was blocked with exit 2 + stderr message reaching Claude verbatim (= live validation of the matcher fix). After flipping to `true`, the 3 runs succeeded.

## Manifest sync round-trip
- [x] Live cells dumped via `mcp__colab-mcp__get_cells` → `outputs/mcp-sessions/_mcp-sandbox/latest-cells.json`
- [x] `uv run python scripts/colab_mcp_sync.py _mcp-sandbox` (dry-run) → `same=0 modify=2 add=1 remove=1` (B's "UPDATED via MCP" suffix dropped via name normalizer; C name mismatch "Tiny matmul" vs "Tiny matmul sanity check" drove add+remove — exactly how name-align works when cell_ids don't overlap)
- [x] Diff reviewed; intentionally NOT applied — manifest stays as the canonical sandbox spec.

## Post-mortem
- [x] Errors → `docs/context.md` "Phase 2 Discovered Issues" (8 findings) + "Additional Phase 2 findings (round 2)" (3 findings)
- [x] `_hook_errors.log` entries triaged — surrogate errors are bash-test-only artifacts (real Claude Code stdin is utf-8); blocked-gate logs are designed signals
- [x] No `output_over_budget: true` in this session (all outputs under 5000-token budget)
- [x] Unexpected tool names documented (the 7 dynamic tools above)
- [x] Colab tab closed
- [x] `/session-end` Step 4.5 MCP teardown executed

## Phase 2 exit criteria — all met
- [x] Notebook generated (non-blank, 4 cells)
- [x] Handshake succeeded (round 3, `result: true`)
- [x] Cell executed via MCP (3 cells executed + 1 update + re-run = 4 successful runs)
- [x] Session log ≥ 3 records (8 records this session)
- [x] Redaction log has no verbatim secrets (16+13 unit tests + this live run all clean)
- [x] Sync round-trip completed (dry-run produced expected diff; intentionally not applied)

## Phase 3 readiness gate
Owner: repo maintainer (@user).
Trigger: 2 consecutive weeks where (a) `_hook_errors.log` shows zero new MCP-related entries AND (b) zero post-sync "manifest differs from live" regressions in any recipe.
When trigger fires: flip `_template/recipe.yaml:mcp.enabled` default to `true` and update CLAUDE.md to mark MCP as the primary iteration path.

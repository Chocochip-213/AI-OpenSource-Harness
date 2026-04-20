# Context — _mcp-sandbox

## Architecture
Browser → Colab runtime (T4) ← colab-mcp server (uvx, Python 3.13) ← Claude Code (stdio).

No model weights. The notebook does:
1. Preflight (GPU + VRAM assert — auto-injected by generate_notebook.py)
2. `import torch`
3. `torch.randn(1024, 1024, device="cuda") @ torch.randn(1024, 1024, device="cuda")`
4. Print result shape + max abs value

## Dependencies
| Package | Upstream Ver | Colab Stock (2025.07) | Strategy |
|---------|-------------|-----------------------|----------|
| torch | (sandbox) | 2.6.0+cu124 | keep |

No other deps — sandbox imports only torch from Colab's stock.

## Key Decisions
See "Phase 2 Discovered Issues" + "Live cycle complete" sections below — every decision and its rationale is recorded there with a 2026-04-20 timestamp. No empty placeholders.

## Discovered Issues
| Error | Root Cause | Fix | Verified |
|-------|-----------|-----|----------|
|       |           |     |          |

Expected classes of surprise to watch for:
- `claude mcp list` shows `disconnected` until first tool call (by design — stdio)
- `open_colab_browser_connection` 60s timeout if browser not signed into Colab
- T4 requested, L4/V100 allocated (peak hours) → preflight assert warns, does not fail
- Dynamic tool list arrives with names we did not predict (actual names are set by
  the Colab browser frontend JS, not the Python MCP server we analyzed)

## Risks
| Risk | Prob | Mitigation |
|------|------|------------|
| uvx v1.0.2 fails to install on first run | medium | `uv cache clean` + `uvx --reinstall` |
| Browser profile not signed into Colab | medium | Sign in manually, retry |
| `claude` process binds to old `.mcp.json` (not our new one) | low | Confirm `claude mcp list` output before proceeding |

## Decision Log (reversals allowed)
| Date | Decision / Reversal | Reason |
|------|---------------------|--------|
| 2026-04-20 | Created sandbox recipe for Phase 2 E2E validation | End of Phase 1 (enforcement complete) required real-handshake proof before any real model ports |

## Artifact Locations
| Path | Contents | Gitignored? |
|------|----------|-------------|
| `outputs/notebooks/_mcp-sandbox.ipynb` | Generated sandbox notebook | Yes |
| `outputs/mcp-sessions/_mcp-sandbox/<session>.jsonl` | Per-call MCP session log | Yes |
| `outputs/mcp-sessions/_mcp-sandbox/latest-cells.json` | Live-cell dump for /colab-mcp-sync | Yes |

## Phase 2 Discovered Issues (live)

| Discovery | Symptom | Root cause | Fix |
|-----------|---------|------------|-----|
| 2026-04-20 | PreToolUse hook did NOT fire for `mcp__colab-mcp__open_colab_browser_connection` despite `matcher: "mcp__"` | Claude Code's PreToolUse matcher does not treat `"mcp__"` as a prefix the way PostToolUse's empty matcher matches everything. The hook code itself is correct (direct stdin pipe writes the audit log fine). | Changed `.claude/settings.json` PreToolUse matcher from `"mcp__"` to `""`; the existing `case '"tool_name"'*'"mcp__'*` filter inside `mcp-tool-monitor.sh` skips non-MCP tools cheaply. |
| 2026-04-20 | `source .claude/.env` was forgotten before `claude` start — recipe-specific MCP_TIMEOUT/MAX_MCP_OUTPUT_TOKENS not applied | User ran `claude` directly. CLAUDE_ACTIVE_RECIPE/MCP_TIMEOUT all `(unset)`. Phase 2 still worked because the handshake is fast and output tiny — but a real recipe with a long install would have hit the 30s default timeout. | No code fix — documentation already says to source first. Consider future: SessionStart hook auto-source `.claude/.env` if it exists. |
| 2026-04-20 | Browser handshake itself succeeded on first try — `open_colab_browser_connection` returned `true`, `notifications/tools/list_changed` delivered 7 dynamic tools (`add_code_cell`, `add_text_cell`, `update_cell`, `delete_cell`, `move_cell`, `run_code_cell`, `get_cells`) | N/A — working as designed. Confirmed the architecture analysis (1 static + N dynamic from browser frontend). | None. |

Tool name leaf shape now confirmed: `run_code_cell` matches the existing `EXECUTING_TOOL_RE` (`^|_)(run|execute|exec|eval)($|_)`), so `allow_auto_execution: false` will block it as designed. Other dynamic tools (`add_code_cell`, `add_text_cell`, `update_cell`, `delete_cell`, `move_cell`, `get_cells`) are non-exec and pass through.

### Additional Phase 2 findings (2026-04-20 round 2)

| # | Discovery | Symptom | Root cause | Fix |
|---|-----------|---------|------------|-----|
| 4 | `get_cells` returns ~415 KB on a freshly-opened Colab tab | First MCP call after handshake returned a Korean welcome notebook full of base64 webp banners; output saved to `~/.claude/projects/.../tool-results/<…>.txt` because Claude Code auto-clipped at its own context cap | colab-mcp opens `https://colab.research.google.com/notebooks/empty.ipynb` which is actually the localized landing notebook for the user's region (Korean here), not an empty doc | Workflow: never call `get_cells` without `cellIndexStart`/`cellIndexEnd` to bound; sandbox docs updated. Fix in upstream not in scope here. |
| 5 | Our PostToolUse `output_over_budget` heuristic is **bypassable** | Claude Code's own response cap truncated the 415 KB output to ~1.1 KB before delivering to PostToolUse, so our budget check saw `output_len: 1146` (under 5000-tok budget) and recorded `output_over_budget: false` | Claude Code intercepts oversize MCP responses before any PostToolUse hook sees them | Limitation acknowledged. Real over-budget signal lives in the saved `tool-results/*.txt` file. Hook still useful for in-budget-but-large outputs. |
| 6 | colab-mcp does **not** support multi-Google-account selection | Browser auto-loads with the wrong default Google account; `webbrowser.open_new()` (server source line 168) hardcodes the URL with no `authuser=` parameter | Upstream design — server can't know which account the user wants | **Resolved via separate Chrome profile per Google account** (used in round 3 handshake, `{"result": true}`). Upstream change is out of this repo's scope — googlecolab/colab-mcp owns it. |
| 7 | `claude mcp reset-project-choices` only takes effect on the **next** `claude` start | After a user rejected an MCP tool call, the same session could not invoke that server again even after reset | Claude Code caches reject decisions in process memory | Documented; recovery is full session restart. |
| 8 | Korean / Japanese sensitive key names (`비밀번호`, `암호`, `パスワード`, `認証`, …) were not redacted by the original English-only key regex | Direct unit test: `redact("비밀번호", "...password123") → "...password123"` (full passthrough) | `SENSITIVE_KEY_RE` covered only English nouns | **Patched**: regex extended with Korean (`비밀번호\|암호\|토큰\|인증`) + Japanese (`パスワード\|トークン\|認証\|秘密`) + missing English (`signature\|nonce`). 13/13 i18n cases now redact, 3/3 non-secret keys still pass. |

### Phase 2 audit matrix (no live MCP needed — all hook-level)

| Round | Cases | Pass | Fail | Notes |
|-------|-------|------|------|-------|
| R1 — PreToolUse exec/non-exec/non-MCP/gate matrix | 17 | 17 | 0 | 8 exec tools blocked (`run_code_cell` … `add_and_run`), 7 non-exec passed, 2 non-MCP passed, gate-1 (`mcp.enabled=false`) blocks |
| R2 — Redaction bypass payloads (English) | 24 | 24 | 0 | All known token formats + nested dicts + PEM envelope + Slack + JWT cleaned |
| R2′ — Redaction i18n (Korean/Japanese) | 13 | 13 | 0 | After SENSITIVE_KEY_RE patch |
| R3 — `/colab-mcp-sync` lifecycle | 7 | 7 | 0 | identical / 1-modify / `--apply` + `.bak` / restore / missing-file / empty-list / cell_id mismatch |
| R4 — Stop / PreCompact / PostToolUse / rotation | 6 | 6 | 0 | recursion guard, light/heavy paths, Edit/Write/NotebookEdit (Bash ignored), resume_state write, 1500→500 rotation |
| **Total** | **67** | **67** | **0** | Zero leaks, zero silent failures across the harness's hook layer |

Live-runtime success criteria still pending (require browser-in-the-loop): handshake `result: true` (1 of 3 attempts so far), MCP-driven cell execution, manifest sync round-trip with real cell deltas.

### Live cycle complete (2026-04-20 round 3 — fresh Chrome profile)

Full dynamic-tool sweep against a real Colab runtime (A100-SXM4-40GB allocated despite `preferred_gpu: T4`, which is fine — preflight is a soft warn):

| Step | Tool | Result |
|------|------|--------|
| 1 | `open_colab_browser_connection` | `{"result": true}` — handshake succeeded |
| 2 | `get_cells(cellIndexEnd=2)` | bounded fetch returned 1 empty cell (no Korean welcome page this time — fresh profile = fresh empty notebook) |
| 3 | `add_code_cell(cellIndex=0..2)` × 3 | new cell IDs `qNfaazRk3puh`, `AXH824OF3qS6`, `LrEkJFFM3quz` |
| 4 | `run_code_cell(qNfaazRk3puh)` with `auto_exec=false` | **PreToolUse blocked with exit 2** — stderr `MCP exec blocked: …allow_auto_execution: false. Confirm with the user…` reached Claude verbatim. **The matcher fix from commit 705e7a1 is live-validated.** |
| 5 | flip `allow_auto_execution: true` → `run_code_cell` × 3 | `torch 2.10.0+cu128`, matmul `(1024,1024) max=147.83`, `Device: NVIDIA A100-SXM4-40GB`, VRAM 41.82/42.41 GB, `Sandbox OK — Phase 2 handshake validated.` |
| 6 | `update_cell(qNfaazRk3puh, ...)` + re-run | new line `[update_cell test] this line was added by /colab-mcp` showed up in stdout — update propagated correctly |
| 7 | `delete_cell(lIYdn1woOS1n)` | empty cell removed |
| 8 | `get_cells` → `latest-cells.json` → `colab_mcp_sync.py _mcp-sandbox` (dry-run) | diff produced cleanly: `same=0 modify=2 add=1 remove=1`. Correction after 2026-04-21 code re-read: the 2 `modify` hits came from Pass 1 (cell_id alignment), NOT from any name normalizer — `scripts/colab_mcp_sync.py` has no "UPDATED via MCP" suffix stripping. The 3rd cell surfaced as add+remove because names differed ("Tiny matmul" vs "Tiny matmul sanity check") and cell_ids did not overlap, so Pass 2 name-align missed. Working as designed. |

PreToolUse audit captured every call with `code` / `content` fields hashed (`<hash:ebe4b60dd719 len:…>`), `cell_id` left in clear (it's an opaque identifier, not a secret). PostToolUse session log captured every output (`output_len: 28..173` — all under the 5000-token budget so `output_over_budget: false` correctly throughout this run).

### Live findings

| # | Finding |
|---|---------|
| 9 | **A100 was allocated even with `preferred_gpu: T4`** — Colab gave the user a *bigger* card. Our preflight emits a `[warn]` (mismatch) but does not fail (VRAM ≥ 8 GB). Behaving exactly as designed. |
| 10 | **`run_code_cell` is a synchronous tool with `MCP_TIMEOUT` cap** (default 30 s, max realistic ~600 s). Long-running tasks (training, large downloads) MUST use the async-job pattern documented in `docs/MCP_INTEGRATION.md` § *Long-running cells* — fire-and-forget thread + status polling cell. **Colab session caps are tier-dependent**: Free ~12 h, Pro / Pro+ ~24 h, and Pro+ adds true background execution that survives a closed tab. Any work that needs to outlive the active session still requires checkpointing to Drive / HF Hub. This is a Colab + Claude-Code architectural limit (synchronous tool round-trips don't get longer just because the runtime does), not a harness bug to fix. |
| 11 | **Sync's `name` align is the matching primary key when no `cell_id` overlaps**. Manifest cells have no `cell_id`; live cells do. So renaming a cell ("Tiny matmul" vs "Tiny matmul sanity check") triggers add+remove rather than modify. For tighter alignment, manifest authors can pre-assign `cell_id` strings and pass them through `add_code_cell` is unsupported (the API doesn't take cellId as input — the server assigns it). Workaround: name cells exactly as they'll appear after `add_code_cell`. |

### Phase 2 exit criteria — all met
- [x] Notebook generated (non-blank)
- [x] Handshake succeeded at least once
- [x] At least one cell executed via MCP (3 cells executed, 1 updated + re-run)
- [x] Session log has ≥ 3 records (current session has 8 entries)
- [x] Redaction log has no verbatim secrets (auto-scan + 67 unit tests + this live run all clean)
- [x] Sync round-trip completed (dry-run shown above; real `--apply` saved for post-Phase-2 commit if the user wants to update the manifest)

**Phase 2 done.** Ready to consider Phase 3 (flip `_template/recipe.yaml:mcp.enabled` default to `true`) once two consecutive weeks pass without an MCP-related regression in `_hook_errors.log`.

## 2026-04-20 (late) — 4-agent pre-push audit

Before pushing the 19 unpushed SSAFY-prep commits, ran a 4-agent
parallel audit (Opus, background) to catch anything brittle:

| Agent | Scope | Result |
|-------|-------|--------|
| 1 | Regression vs 19-commit fix-history | 19/19 PASS, 0 regressions |
| 2 | Claude Code spec re-verification | 5 cosmetic/docs mismatches (no blockers) |
| 3 | MCP × harness deep simulation | 0 P0, 3 P1 (1 docs contradiction, 1 docs-claims-unimplemented-feature, 1 fail-open gap), 7 P2 |
| 4 | Spring/Next.js code-example quality | 7 P0 (javac/tsc breakage), 14 P1 (idiomatic), 11 P2 |

Two follow-up commits landed in response:
- `3707308 fix(exports): BE/FE compile-safe identifiers + Gradio 5.x /call/predict`
- `4898bcf docs: align harness docs with verified Claude Code spec + real code paths`

Key corrections worth remembering:
- The Phase 2 "UPDATED via MCP name normalizer" note above was inaccurate —
  the sync's 2 `modify` hits came from Pass 1 (cell_id) alone, not from any
  name-suffix stripping. `scripts/colab_mcp_sync.py` has no such normalizer.
- Colab ships Gradio 5.x; the legacy `POST /run/predict` one-shot is gone.
  Templates now describe the two-step queued flow
  (`POST /call/predict` → `event_id` → `GET /call/predict/<event_id>` SSE).
- `tools/generate_export.py` previously emitted invalid Java/TS identifiers
  whenever `recipe_name` contained a hyphen or leading underscore (e.g.
  `_mcp-sandbox` → `public class _mcp-sandboxController`). Now derives
  `{RECIPE_CLASS_NAME}` (PascalCase) and `{RECIPE_SNAKE_NAME}`.


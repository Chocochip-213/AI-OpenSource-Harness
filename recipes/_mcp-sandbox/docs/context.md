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
_Filled in as Phase 2 execution surfaces real behavior._

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
| 6 | colab-mcp does **not** support multi-Google-account selection | Browser auto-loads with the wrong default Google account; `webbrowser.open_new()` (server source line 168) hardcodes the URL with no `authuser=` parameter | Upstream design — server can't know which account the user wants | Workaround: separate Chrome profile per Google account (used here). Future: file an upstream feature request for `authuser` param + recipe-yaml `mcp.preferred_google_account` field. |
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

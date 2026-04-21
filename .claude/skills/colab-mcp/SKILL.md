---
name: colab-mcp
description: Live Colab MCP driver. ALWAYS invoke this skill BEFORE calling any mcp__colab-mcp__* tool — it owns the preflight checks, per-cell backup discipline, cleanup rules, token-redaction guarantees, and disconnect recovery. Do NOT call open_colab_browser_connection / add_code_cell / run_code_cell / update_cell / delete_cell / get_cells directly — invoke this skill first; skipping it caused ~90 min + 48 GB of lost work on flux2-klein-4b (2026-04-20) because the per-cell backup rule only activates via this skill. Triggers on any MCP Colab intent — "Colab에서 실행", "live colab", "run on colab", "mcp run", "iterate cells", "interactive colab", "콜랩 실행", or the user asking to run cells, add cells, debug cells in Colab.
allowed-tools: Read, Edit, Write, Bash
---

# Skill: colab-mcp

> **Self-enforcement (read first, every session)** — this skill only has effect
> if invoked via the `Skill` tool. Reading the SKILL.md file as passive
> documentation while hand-running MCP tools is the failure mode that lost
> ~90 min of flux2-klein-4b work on 2026-04-20 (the "매 셀 백업" rule lived
> in this file but was never actually activated). **Invoke this skill AT THE
> START of every MCP session**, before the first `open_colab_browser_connection`
> call. Also invoke `/colab-mcp-sync` periodically MID-SESSION (not just at
> the end) — its whole purpose is to write `latest-cells.json` and the
> manifest before anything can get lost.

## When to Use
User wants Claude to drive a live Colab runtime (cell CRUD + execution + state
inspection) instead of the manual "edit manifest → regenerate → upload → retest"
loop. See `docs/MCP_INTEGRATION.md` for the architecture and trade-offs.

## Preflight (REFUSE if any fails)

1. `.mcp.json` at repo root has a `colab-mcp` server entry → otherwise ask the user to restore it
2. `uvx` is on PATH (`command -v uvx`)
3. Active recipe's `recipe.yaml` has `mcp.enabled: true` — if `false`, **do not proceed**. Respond:
   > MCP is disabled for this recipe. Flip `recipe.yaml` → `mcp.enabled: true` to allow live Colab execution. (Opt-in safety rail.)
4. `notebook_manifest.yaml` exists and `generate_notebook.py` succeeds — MCP is an *iterator on top of* a valid manifest, not a replacement

## Execution Workflow

### 1. Connect (one-time per session)
Invoke the only statically-defined tool:
```
mcp__colab-mcp__open_colab_browser_connection
```
This opens a browser tab. Tell the user:
> A Colab tab is opening. Approve the connection banner (you must be signed into Colab in that browser profile). 60-second timeout.

On success, the MCP server sends `notifications/tools/list_changed` and Claude
sees the dynamic tool surface (add_cell, run_cell, runtime info, etc. —
exact names depend on server version). On failure (returns `false`):
- Tell the user to check their browser's Colab sign-in
- See troubleshooting in `docs/MCP_INTEGRATION.md`

### 2. Runtime sanity check
Run a tiny cell FIRST to verify GPU allocation matches expectations:
```python
import torch, os
print("GPU:", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU")
print("VRAM GB:", torch.cuda.get_device_properties(0).total_memory / 1e9 if torch.cuda.is_available() else 0)
print("Python:", __import__('sys').version)
```
Compare with `recipe.yaml:mcp.preferred_gpu`. If mismatch (A100 requested → L4
allocated), warn the user — Colab silently downgrades during peak hours.

### 3. Iterate cells
Drive the notebook. Each execution is logged to
`outputs/mcp-sessions/<recipe>/<ISO-timestamp>.jsonl` (one JSON object per cell
execution: `{cell_id, source, stdout, stderr, duration_sec, status}`).

If `recipe.yaml:mcp.allow_auto_execution == false` (default), confirm with the
user before running any cell that installs packages, downloads weights, or
modifies the filesystem.

### 4. Long-running work (>3 minutes)
Do NOT wait synchronously. Use the async-job pattern documented in
`docs/MCP_INTEGRATION.md` → *Long-running cells*: launch a thread, poll
`_job["status"]` from subsequent cells. MCP tool round-trips should each be
<30s; the notebook's Python does the waiting.

### 5. Manifest-first discipline — **back up after EVERY cell**
Every cell edit made via MCP is an **un-promoted change**. Rules learned the
hard way (flux2-klein-4b session lost 48 GB + 90 min of work when the Colab
tab died with no local backup):

**Per-cell backup**: after every `run_code_cell` that succeeds, call
`get_cells(cellIndexStart=0, cellIndexEnd=<current_count>)`. The PostToolUse
hook at `.claude/hooks/_mcp_session_log.py` then writes the response to
both `outputs/mcp-sessions/<recipe>/latest-cells.json` AND a timestamped
`cells_<ts>_<ns>.json` snapshot. The **write is deterministic** (hook enforces
it); the **`get_cells` call itself is LLM-judged** — only this SKILL.md
instructs you to make the call after every `run_code_cell`. Nothing
automatic forces the call. That's the actual failure mode (skipping the
call), and why this skill must be invoked before any MCP session. (The
hook's predicate was widened post-2026-04-20 flux2 session after the old
narrow predicate silently dropped partial scans. The hook also prunes to
the last 20 snapshots per session-dir as of 2026-04-21 — unbounded growth
was a separate P0.) Why this matters: `colab-mcp` has no `save_to_drive`
tool, and the notebook in the browser is pure memory until the user
presses Ctrl+S. If the tab dies, those snapshots are the only recovery.

**Cleanup failed cells**: when a cell fails and you replace it with a
working version, `delete_cell` the failed one before moving on. Leftover
broken cells cause visible ghost-iframes (e.g. two Gradio share URLs
rendered, one dead), wrong state when the user re-runs from top, and
noisy `/colab-mcp-sync` diffs.

**Token handling**: do not inline `hf_…` / API tokens into a cell's
source (`login(token="hf_XXX", …)`). The PreToolUse redaction hashes
the source field in the *audit log* but the live Colab notebook still
contains the token bytes in the cell — if the user later saves to
Drive or exports, the token leaks. Ask the user to add the token to
**Colab Secrets** (left sidebar key icon) and read via
`google.colab.userdata.get("HF_TOKEN")`. If the user pastes a token
into chat for speed, warn them to rotate after the session — it's in
conversation history regardless.

At session end, promote everything:
- Append a note to `recipes/<name>/docs/context.md` "Discovered Issues" describing each fix
- Run `/colab-mcp-sync <recipe>` (skill: `.claude/skills/colab-mcp-sync/SKILL.md`, script: `scripts/colab_mcp_sync.py`) — diffs live cells against `notebook_manifest.yaml`, applies on `--apply` with timestamped `.bak`, AND auto-regenerates `outputs/notebooks/<recipe>.ipynb`
- If you leave edits un-promoted, the next `generate_notebook.py` invocation will silently overwrite them

### 6. Graceful disconnect handling
MCP can fail in three modes — each needs a different recovery:

| Signal | Cause | Recovery |
|--------|-------|----------|
| `open_colab_browser_connection` returns `false` | Browser not signed into Colab, or default browser did not open the tab | Check `https://colab.research.google.com` in the user's default browser, then retry |
| Dynamic tools disappear ("no longer available" notice) | MCP server subprocess crashed (rare — usually after an unresponsive tool call) | **Full Claude Code restart required** — `claude mcp list` alone will not respawn the server. Tell the user to exit + `source .claude/.env && claude`, then re-run this skill's Step 1 |
| A `run_code_cell` hangs > 2 min for a cell that should be fast | Server sent the request, Colab ran it, but the WebSocket back is stuck | Do not wait silently. Surface the stall to the user, retry with a smaller cell, consider `delete_cell` + `add_code_cell` + re-run |

If the **Colab runtime** (not the MCP server) dropped — any subsequent MCP tool
will succeed at the MCP level but return stale/empty notebook state. In that
case: re-run setup cells from scratch. If `mcp.keepalive: true`, idle
disconnect is delayed but the 12h hard cap is unavoidable.

## Constraints (hard, from server source)

- **Single connection**: the MCP server rejects a second WebSocket with code 1013. You cannot `/colab-mcp` two recipes in parallel.
- **Browser required**: this skill does NOT work in headless / CI / SSH-forwarded sessions. The server calls `webbrowser.open_new()` and expects a local display.
- **Python 3.13**: provided automatically by `uvx`. Do not try to `pip install colab-mcp` into this harness's venv — it will fail or corrupt the env.
- **No OAuth token**: authentication is "whatever Google account is signed into your browser". There is nothing to configure in `.claude/settings.local.json`.

## On Failure

If MCP is unavailable (server crashed, network, auth), **always fall back gracefully**:
1. Say explicitly: "MCP unavailable — falling back to manual Colab upload."
2. Regenerate the notebook (`uv run python tools/generate_notebook.py <recipe>`)
3. Instruct the user to open `outputs/notebooks/<recipe>.ipynb` in Colab manually

Never silently skip steps. The manual fallback is the original, proven path.

## Output to User

After a successful session, summarize:
- Cells executed / succeeded / failed (with cell IDs)
- Any runtime metrics worth recording in `context.md` (VRAM peak, cold-start time)
- List of cells edited via MCP that **need to be promoted** to `notebook_manifest.yaml`
- Path to the session log jsonl for auditing

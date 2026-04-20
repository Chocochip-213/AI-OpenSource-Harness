---
name: colab-mcp
description: Use when the user wants to run/iterate the current recipe's notebook on a live Colab runtime via the colab-mcp server. Triggers on "Colab에서 실행", "live colab", "run on colab", "mcp run", "iterate cells", "interactive colab". Requires recipe.yaml mcp.enabled=true AND .mcp.json registration (already present in repo root). Enforces manifest-first discipline — every MCP edit is logged and must be promoted back via /colab-mcp-sync. Single-connection and Python 3.13 isolation constraints are documented in docs/MCP_INTEGRATION.md.
allowed-tools: Read Edit Write Bash
---

# Skill: colab-mcp

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

### 5. Manifest-first discipline
Every cell edit made via MCP is an **un-promoted change**. Before session end:
- Append a note to `recipes/<name>/docs/context.md` "Discovered Issues" describing the fix
- Run `/colab-mcp-sync` (future skill) OR manually update `notebook_manifest.yaml` to reflect the working cell content
- If you leave edits un-promoted, the next `generate_notebook.py` invocation will silently overwrite them

### 6. Graceful disconnect handling
Watch for these signals mid-session:
- Any MCP tool returning a connection error → runtime probably dropped (90-min idle or 12-hour cap)
- Tool list becomes empty (`notifications/tools/list_changed` with no tools)

Recovery: call `open_colab_browser_connection` again. State in the Colab notebook
is gone — you need to re-run setup cells. If `mcp.keepalive: true`, idle
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

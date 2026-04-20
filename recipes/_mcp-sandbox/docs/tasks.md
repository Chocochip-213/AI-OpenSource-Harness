# Tasks — _mcp-sandbox (Phase 2)

## Pre-flight (current session)
- [x] Copy `_template` → `recipes/_mcp-sandbox/`
- [x] Set `recipe.yaml:mcp.enabled: true`, `allow_auto_execution: false`, `preferred_gpu: T4`
- [x] Keep `notebook_manifest.yaml` minimal (3 cells: import, matmul, report)
- [ ] `scripts/set_active_recipe.sh _mcp-sandbox` (switches active recipe + writes `.claude/.env`)
- [ ] `uv run python tools/generate_notebook.py _mcp-sandbox` — confirm GPU preflight cell auto-injects, 4+ cells total

## Fresh Claude session (Phase 2 starts here)
- [ ] Exit current `claude` process
- [ ] `source .claude/.env`
- [ ] Start new `claude` session from repo root
- [ ] `claude mcp list` — expect `colab-mcp` (may say disconnected; that's fine for stdio pre-first-call)

## Live MCP validation
- [ ] Ask Claude: "Open the Colab connection for this sandbox and run the cells one by one."
- [ ] Claude calls `mcp__colab-mcp__open_colab_browser_connection`
- [ ] Browser tab opens → approve the handshake (must be signed into Colab)
- [ ] PreToolUse hook lets the call through (`recipe.yaml:mcp.enabled: true`)
- [ ] `.claude/_mcp_tool_calls.log` grows — redacted input summary
- [ ] `outputs/mcp-sessions/_mcp-sandbox/<session>.jsonl` appears, records per-call output
- [ ] Claude inspects dynamic tool list — note the exact tool names used by the Colab frontend

## First cell runs
- [ ] Cell A (auto-injected preflight) passes — T4 allocated, VRAM ≥ 8 GB
- [ ] Cell B (torch matmul) returns `(1024, 1024)` shape
- [ ] Cell C (report) prints non-trivial values
- [ ] `allow_auto_execution: false` — Claude asks before each run (verify by observation)

## Manifest sync round-trip
- [ ] Ask Claude to dump live cells to `outputs/mcp-sessions/_mcp-sandbox/latest-cells.json`
- [ ] `uv run python scripts/colab_mcp_sync.py _mcp-sandbox` — dry-run, expect exit 3 if any diff
- [ ] Review diff; if all `same`, manifest was authoritative (expected on first run)
- [ ] If any `add`/`modify`, `--apply` and commit the resulting manifest change

## Post-mortem (before ending the session)
- [ ] Any errors → `docs/context.md` Discovered Issues
- [ ] Any `_hook_errors.log` entries → triage
- [ ] `output_over_budget: true` anywhere? → check Cell B/C verbosity
- [ ] Unexpected tool names used by the frontend → document in `context.md`
- [ ] Close Colab tab
- [ ] `/session-end` (follow Step 4.5 MCP teardown)

## Phase 2 exit criteria (all required)
- [ ] Notebook generated (non-blank)
- [ ] Handshake succeeded at least once
- [ ] At least one cell executed via MCP
- [ ] Session log has ≥ 3 records
- [ ] Redaction log has no verbatim secrets
- [ ] Sync round-trip completed (manifest matches live, or diff was applied)

When all checked: ready to consider Phase 3 (flip `_template/recipe.yaml:mcp.enabled` default).

---
name: colab-mcp-sync
description: Use after a live Colab MCP session to promote cell-level edits that were made in the browser back into the recipe's notebook_manifest.yaml. Triggers on "mcp sync", "manifest 반영", "promote mcp edits", "sync manifest", "콜랩 변경 반영", "노트북 매니페스트 업데이트", or when the user says the live notebook drifted from the manifest. Produces a diff first; applies only on confirmation. Prevents the "Cell X fix 20 commits" drift that killed Ever's trellis2 iteration.
allowed-tools: Read Edit Write Bash
paths:
  - outputs/mcp-sessions/**/latest-cells.json
  - outputs/mcp-sessions/**/*.cells.json
  - scripts/colab_mcp_sync.py
  - recipes/**/notebook_manifest.yaml
---

# Skill: colab-mcp-sync

## When to Use
After any `/colab-mcp` session where Claude added, modified, or reordered cells
on the live Colab runtime. If those edits are not promoted back into
`recipes/<name>/notebook_manifest.yaml`, the next `generate_notebook.py` run
will silently overwrite them — the exact failure mode that produced Ever's
"Cell X fix" commit pile.

## Preflight
1. The active recipe must have `recipe.yaml:mcp.enabled: true` — otherwise
   the MCP session that produced these edits was blocked by the PreToolUse
   gate and there's nothing to sync.
2. The Colab tab must still be connected. If the runtime disconnected, you
   need to re-open the browser connection and re-derive the cell state
   before running this skill.

## Workflow

### Step 1 — Dump live cells from Colab (auto-saved)
Call the MCP `get_cells` tool. The PostToolUse hook
(`.claude/hooks/_mcp_session_log.py`) **auto-saves** the response to
`outputs/mcp-sessions/<recipe>/latest-cells.json` — you don't need a
manual Write step.

```
mcp__colab-mcp__get_cells (cellIndexStart=0, cellIndexEnd=N, includeOutputs=false)
```

If the live notebook is large (the Korean Colab welcome page is ~415 KB
and trips Claude Code's own MAX_MCP_OUTPUT_TOKENS cap), Claude may
receive a truncated response — the auto-save then writes only the
truncated cells. To avoid that, always pass a small `cellIndexEnd`
matching what the manifest expects (sandbox = 4, typical recipe ≤ 10).

### Step 2 — Run the diff (dry run by default)
```bash
uv run python scripts/colab_mcp_sync.py <recipe>
```
The script prints a unified diff for every modified cell plus a summary of
adds / modifications / removes. **Do not pass `--apply` yet.**

Exit codes:
- `0` — no changes (manifest already matches live notebook)
- `3` — changes found (review the diff in the next step)
- `1` — input error (missing cells file, bad JSON/YAML)

### Step 3 — Human review
Summarize the diff back to the user:
- Which cells changed and why (correlate with `.claude/_mcp_tool_calls.log`
  entries from the session for context)
- Any obvious accidental changes (whitespace-only, debug prints, etc.)
- Any secrets or tokens that slipped into cell source — if present, stop
  and ask the user to redact them before applying

Do NOT proceed to step 4 without explicit user confirmation.

### Step 4 — Apply (one shot — manifest + .ipynb together)
```bash
uv run python scripts/colab_mcp_sync.py <recipe> --apply
```
This now does **two things in one command**:
1. Rewrites `notebook_manifest.yaml` (timestamped `.bak` backup saved
   alongside, e.g. `notebook_manifest.yaml.sync-20260420T0145Z.bak`).
2. Re-runs `tools/generate_notebook.py <recipe>` automatically so the
   `.ipynb` in `outputs/notebooks/` stays in lock-step with the manifest.
   Without this auto-regen, the next manual `generate_notebook.py` run
   (or the next Colab upload) silently undoes the edits we just promoted.

If you intentionally want to inspect the manifest diff before
regenerating, pass `--no-regen`:
```bash
uv run python scripts/colab_mcp_sync.py <recipe> --apply --no-regen
# inspect recipes/<recipe>/notebook_manifest.yaml
uv run python tools/generate_notebook.py <recipe>   # when ready
```

### Step 5 — Verify the round-trip
The `--apply` step printed `[generate_notebook] Written: outputs/notebooks/<recipe>.ipynb`
already. Open that file (or re-upload to Colab) and confirm it matches
what was running in the live tab. If it doesn't, the most likely culprit
is a cell rename that the name-align matcher mis-classified as add+remove —
fix the manifest cell `name` to exactly match the live cell title and
re-run the sync.

### Step 6 — Record in SSOT
- Check off "MCP edits promoted to manifest" in `recipes/<recipe>/docs/tasks.md`
- If a noteworthy decision was made during the MCP session (why a cell was
  restructured, what error prompted the change), add it to
  `recipes/<recipe>/docs/context.md` under "Key Decisions"

## Constraints
- Always dry-run first. `--apply` is destructive (manifest rewrite) even
  though we keep a `.bak` — human review catches bugs the script cannot.
- The JSON dump at `outputs/mcp-sessions/<recipe>/latest-cells.json` is
  gitignored. If you need to share it, scrub secrets manually — the hook
  redaction does NOT touch this file (it is written by Claude, not the hook).
- Do not run two `/colab-mcp-sync` invocations against the same recipe
  concurrently. The manifest rewrite is atomic, but the `.bak` naming uses
  a second-resolution timestamp and can collide.

## Failure modes
- **"latest-cells.json not found"** — step 1 was skipped. Re-fetch from MCP.
- **Diff shows unexpected global cell reordering** — the live notebook was
  reorganized by something other than your session. Check
  `.claude/_mcp_tool_calls.log` for calls made outside this session.
- **Backup file cannot be written** — `recipes/<recipe>/` is read-only or
  full. Fix the filesystem issue; do not edit the manifest by hand because
  that defeats the backup safety rail.

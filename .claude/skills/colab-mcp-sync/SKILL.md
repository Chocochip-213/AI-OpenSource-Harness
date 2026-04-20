---
name: colab-mcp-sync
description: Use after a live Colab MCP session to promote cell-level edits that were made in the browser back into the recipe's notebook_manifest.yaml. Triggers on "mcp sync", "manifest 반영", "promote mcp edits", "sync manifest", "콜랩 변경 반영", "노트북 매니페스트 업데이트", or when the user says the live notebook drifted from the manifest. Produces a diff first; applies only on confirmation. Prevents the "Cell X fix 20 commits" drift that killed Ever's trellis2 iteration.
allowed-tools: Read Edit Write Bash
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

### Step 1 — Dump live cells from Colab
Ask the MCP server for the current notebook state. The exact tool name is
set by the colab-mcp browser runtime (`notifications/tools/list_changed`);
typical names are `get_cells`, `list_cells`, or `get_notebook_state`. Call
it with no arguments.

Write the result to
`outputs/mcp-sessions/<recipe>/latest-cells.json` as a JSON array whose
elements have at minimum `name`, `type`, and `source` (and optionally
`cell_id`). Example:

```json
[
  {"name": "A) GPU preflight", "type": "code", "source": "import torch\n…"},
  {"name": "## Setup", "type": "markdown", "source": "Install dependencies…"},
  {"name": "B) Install", "type": "code", "source": "!pip install -q …"}
]
```

Use the Write tool (not a shell heredoc — JSON needs exact escaping).

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

### Step 4 — Apply
```bash
uv run python scripts/colab_mcp_sync.py <recipe> --apply
```
A timestamped backup of `notebook_manifest.yaml` is saved alongside (e.g.
`notebook_manifest.yaml.sync-20260420T0145Z.bak`) so you can revert if the
rewrite was wrong.

### Step 5 — Verify
```bash
uv run python tools/generate_notebook.py <recipe>
```
Regenerates the `.ipynb` from the updated manifest. The output should match
the live notebook — if it does not, investigate before closing the session.

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

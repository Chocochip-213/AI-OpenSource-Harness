# Colab MCP Integration

> **This file is the SSOT for Colab MCP behavior in this harness.**
> `CLAUDE.md` and `.claude/skills/colab-mcp/SKILL.md` link here; do not duplicate
> content there. When behavior changes, update this file first.

The repo's `.mcp.json` registers [googlecolab/colab-mcp@v1.0.2](https://github.com/googlecolab/colab-mcp)
so Claude Code can drive a live Colab runtime (cell CRUD + execution) instead of the
manual "edit manifest → regenerate → upload → retest" loop.

---

## Status: all enforcement live

Every `recipe.yaml:mcp.*` field is enforced automatically. No declarative-only
fields remain. The PreToolUse gate, PostToolUse session log, cell-injection,
env-var propagation, and manifest reconciliation are all code — not documentation.

| Field | Enforced by |
|-------|-------------|
| `mcp.enabled` | `.claude/hooks/_mcp_monitor.py` — blocks with exit 2 when false |
| `mcp.allow_auto_execution` | `.claude/hooks/_mcp_monitor.py` — blocks `run_*`/`execute_*`/`exec_*` tools when false |
| `mcp.max_tool_output_tokens` | `.claude/hooks/_mcp_session_log.py` — emits `output_over_budget` + warning log |
| `mcp.preferred_gpu` | `tools/generate_notebook.py` — auto-injects Cell A GPU assert |
| `mcp.keepalive` | `tools/generate_notebook.py` — auto-injects heartbeat daemon cell |
| `mcp.timeout_seconds` | `scripts/set_active_recipe.sh` — exports `MCP_TIMEOUT` via `.claude/.env` |
| Redaction | `.claude/hooks/_mcp_monitor.py` — 16-payload bypass suite passes |
| Session trail | `.claude/hooks/_mcp_session_log.py` — `outputs/mcp-sessions/<recipe>/<session>.jsonl` |
| Manifest promotion | `/colab-mcp-sync` skill + `scripts/colab_mcp_sync.py` — diff → apply with backup |

If you discover a gap, the fix is either (a) change the enforcer file above,
or (b) update this table. Do not introduce a third "planned" category.

---

## What this gives you

Once connected, the Colab web frontend exposes a dynamic tool surface (the
exact tool set depends on the Colab browser tab — see *Architecture*):

- Add / modify / reorder notebook cells
- Execute cells and read stdout / stderr / outputs directly
- Observe runtime state (GPU, VRAM, uptime)
- Iterate on failures without the manual "edit manifest → regenerate → upload → retest" loop

Ever porting history: `trellis2` had **20+ "fix: Cell X" commits** on the same
manifest. With MCP, most of those round-trips collapse into a single
conversational iteration.

## What this does NOT give you

- **Not a replacement for `notebook_manifest.yaml`.** MCP is an iteration
  accelerator; the manifest remains authoritative. Changes discovered via MCP
  must be promoted back into the manifest — see *Manifest-first defense*.
- **Not headless / CI-safe.** The initial handshake requires a real browser
  window and a signed-in Google account (see *Authentication & Threat Model*).
- **Not parallel-safe.** The server enforces a **single WebSocket connection at
  a time** — you cannot drive two recipes concurrently.

## Architecture

```
┌─────────────────┐   stdio     ┌──────────────────┐   WebSocket   ┌──────────────────┐
│  Claude Code    │ ──────────► │  colab-mcp proxy │ ───────────── │  Colab browser   │
│  (this process) │ ◄────────── │  (uvx subprocess)│   Bearer tok. │  (actual tools)  │
└─────────────────┘             └──────────────────┘               └──────────────────┘
                                 FastMCPProxy —                    Closed-source JS
                                 relays everything                 runtime implements
                                 to the browser.                   add_cell/run_cell/…
```

Key consequences:
1. Python 3.13 is required for the server — we isolate it via `uvx` so this
   harness's 3.11/3.12 venv is untouched.
2. The server's static tool list has exactly one entry:
   `open_colab_browser_connection`. All real functionality arrives
   dynamically after the browser handshake (MCP `notifications/tools/list_changed`).
3. If the Colab tab is closed or the runtime disconnects, you must call
   `open_colab_browser_connection` again — there is no auto-reattach.

---

## Authentication & Threat Model

### How auth works

There is no OAuth token you paste. The flow:
1. Claude invokes `mcp__colab-mcp__open_colab_browser_connection`.
2. The server opens a local browser tab to
   `https://colab.research.google.com/notebooks/empty.ipynb#mcpProxyToken=<rnd>&mcpProxyPort=<port>`.
3. Because you are already signed into Colab in that browser profile, Colab
   authenticates *you* to itself. The server only checks that the inbound
   WebSocket carries the random `mcpProxyToken` it just generated.
4. The token is a per-process random (`secrets.token_urlsafe(16)`); restarting
   the MCP subprocess invalidates it — reconnection required.

### Threat model — this is NOT "safer than OAuth"

The absence of an OAuth token is **convenience, not a security boundary**.
Colab runs arbitrary Python in the browser session that is already signed
into your Google account. That means any code Claude executes through MCP can
access — without further consent or scope limits:

- **Google Drive** — every file you own, every file shared with you (read/write/delete)
- **Every other Colab notebook** you have in the account
- **Gmail / Calendar / Photos** if connected services are authorized for Python
  runtimes (via the same browser session cookies)
- **Any OAuth app** you have previously granted long-lived access to and that
  accepts the Colab environment's credentials

OAuth, if it were used, would allow `drive.readonly`-style scope pinning. The
current design has **no scope**. Practical implications:

- Never run MCP against your primary Google account for production secrets.
  Use a dedicated development account signed into the target browser profile.
- Treat an MCP-enabled recipe as equivalent to "arbitrary code execution with
  full account access". Review every notebook cell before you approve it.
- `mcp.allow_auto_execution: false` (the default) means Claude asks before
  each cell; flipping it to `true` is equivalent to disabling a seatbelt.
- The MCP server process itself does **not** persist credentials. The trust
  anchor is your browser session cookie — invalidated by signing out or
  clearing cookies.

---

## Setup

### Prerequisites
- `uv` in `PATH` (already required by this harness)
- Google account signed into Colab in your default browser
- `.mcp.json` at repo root (already committed)

### One-time verification
```bash
# Confirm uvx can fetch & run the server (first run compiles, ~60s)
uvx --from git+https://github.com/googlecolab/colab-mcp@v1.0.2 colab-mcp --help

# Confirm Claude Code sees the server
claude mcp list
# Expected:  colab-mcp  ✓ connected (or "disconnected — awaiting connection")
```

If `claude mcp list` shows `disconnected`, that is **normal** until you
actually invoke the first tool — stdio servers only fully handshake on first use.

### Increase timeouts for long installs (recommended)

These are **Claude Code process env vars**, not fields in `.mcp.json`:

```bash
export MCP_TIMEOUT=600000         # 10 minutes — allows pip install of large packages
export MAX_MCP_OUTPUT_TOKENS=10000 # cap per-tool output to avoid context bloat
```

Put these in your shell profile and restart `claude`. The `recipe.yaml:mcp.*`
fields with similar names are informational only; they do **not** propagate
to Claude Code today.

### Per-recipe enablement (opt-in)

MCP is **off by default per recipe**. Opt in via `recipe.yaml`:

```yaml
mcp:
  enabled: true                 # Gate 1 — PreToolUse blocks every mcp__* with exit 2 if false.
  allow_auto_execution: false   # Gate 2 — PreToolUse blocks run_*/execute_*/exec_* when false.
  max_tool_output_tokens: 10000 # PostToolUse flags `output_over_budget` when exceeded.
  preferred_gpu: A100           # generate_notebook.py injects Cell A GPU assert.
  keepalive: false              # generate_notebook.py injects heartbeat daemon cell when true.
  timeout_seconds: 300          # set_active_recipe.sh writes MCP_TIMEOUT to .claude/.env.
```

Changes take effect on the NEXT tool call / NEXT `generate_notebook.py` run /
NEXT `source .claude/.env`. No restart of Claude Code is required for the two
hook gates (they re-read `recipe.yaml` on every call).

---

## Usage

Invoke `/colab-mcp` (or describe the intent — the skill auto-matches on
"Colab에서 실행", "run on colab", "mcp run", etc.). The skill workflow lives in
`.claude/skills/colab-mcp/SKILL.md`.

At a minimum: preflight → call `open_colab_browser_connection` → approve the
browser popup → iterate → before session end, promote MCP-side edits back to
`notebook_manifest.yaml`.

---

## Manifest-first defense

MCP can modify cells live in Colab. If those changes live only in the browser,
`notebook_manifest.yaml` goes stale and the next `generate_notebook.py` run
will undo them. Three guards, all live:

1. **PreToolUse audit log** — `.claude/hooks/_mcp_monitor.py` logs every
   `mcp__*` tool call to `.claude/_mcp_tool_calls.log` with key-based and
   value-based redaction (16-payload bypass suite passes). Every edit leaves
   a trail with the call input, redacted.
2. **PostToolUse session log** — `.claude/hooks/_mcp_session_log.py` captures
   the tool's output per call into
   `outputs/mcp-sessions/<recipe>/<session>.jsonl`. Session id is created by
   `open_colab_browser_connection` and persisted in `.claude/_mcp_session.txt`.
   Each record has: tool, redacted input summary, output length / hash /
   preview, duration, status, over-budget flag.
3. **`/colab-mcp-sync` skill + `scripts/colab_mcp_sync.py`** — dumps live
   cells (Claude fetches them via MCP into `outputs/mcp-sessions/<recipe>/latest-cells.json`),
   aligns by `cell_id` → name → index, prints a unified diff, and
   rewrites `notebook_manifest.yaml` only with `--apply` + a timestamped `.bak`.

The workflow is codified in `recipes/_template/docs/tasks.md`'s "Colab MCP"
section and step 4.5 of `.claude/skills/session-end/SKILL.md`.

---

## Stability guardrails (from real-world MCP bug reports, 2026-Q1)

| Failure | Where it hits | Mitigation |
|---------|---------------|------------|
| 5-min install/model-load exceeds 30s MCP default timeout | `uv pip install <large>` cells | Export `MCP_TIMEOUT=600000` before `claude` |
| Colab 90-min idle → runtime drop, MCP session dead | Long investigation pauses | Call `open_colab_browser_connection` again; `mcp.keepalive` field is planned |
| 12-hour hard cap kills runtime | Overnight experiments | Not bypassable. Checkpoint state to Drive / HF Hub, resume next session |
| A100 requested → downgraded to L4/V100 silently | Peak hours | Cell A asserts `torch.cuda.get_device_name(0)` matches `recipe.yaml:mcp.preferred_gpu` |
| Tool output >25k tokens poisons context | `!pip install` verbose logs, `nvidia-smi -q` | Set `MAX_MCP_OUTPUT_TOKENS=10000` (process env) |
| `claude mcp list` shows "disconnected" | stdout leak (dotenv, print) | uvx isolates Python 3.13 cleanly; colab-mcp src audit confirms stdio-safe |
| MCP hook breaks for teammate without uv | Team clone | Hooks now `graceful-skip` with a warning to `_hook_errors.log` instead of erroring |

### Long-running cells

If a single cell takes >5 minutes, do not wait synchronously. Pattern:

```python
# Cell: async job
import threading, time
_job = {"status": "running", "started": time.time()}
def _run():
    try:
        # ... actual work ...
        _job["status"] = "done"; _job["result"] = result
    except Exception as e:
        _job["status"] = "error"; _job["error"] = str(e)
threading.Thread(target=_run, daemon=True).start()
```
Poll `_job["status"]` from a second cell. MCP tool round-trips should each be
<30s; the notebook's Python does the waiting.

---

## Troubleshooting

### `open_colab_browser_connection` returns false
60-second UI timeout elapsed without the browser tab connecting. Causes:
- Default browser is not signed into Colab → sign in, retry
- Tab opened in a profile that blocks `localhost` WebSockets → different profile
- Corporate proxy / firewall drops `ws://localhost:*` → disable for colab.research.google.com

### Tools "disappear" mid-session
The Colab tab was closed, runtime disconnected, or you switched networks.
`notifications/tools/list_changed` fires and Claude sees an empty list.
Call `open_colab_browser_connection` again.

### `uvx` fails to install colab-mcp
```bash
uv cache clean
uvx --reinstall --from git+https://github.com/googlecolab/colab-mcp@v1.0.2 colab-mcp --help
```
If your corporate env has a private PyPI mirror, add `--index https://pypi.org/simple`.

### Hook errors
Check `.claude/_hook_errors.log`. Every hook failure is recorded with
a timestamp and source. Common entries:
- `WARN no python runtime` — uv is not installed; the hook skipped gracefully
- `blocked: mcp__... (recipe=X)` — `recipe.yaml:mcp.enabled` is not true for
  the active recipe; set it if intentional

### Suspected MCP log contains a secret
`.claude/_mcp_tool_calls.log` is the audit trail. Keys matching
`token|secret|password|passphrase|apikey|api_key|auth|bearer|credential|cert|priv|private|session|pem|rsa|ed25519`
are replaced with `<redacted>`. Values matching known token formats
(`sk-…`, `ghp_…`, `AIza…`, `ya29.…`, JWT, PEM, Slack, `mcpProxyToken=`) are
replaced with `<redacted-value>`. `code/source/script/notebook/content/body/
payload/cell/stdout/stderr/command/query/prompt` fields are hashed (SHA-256,
first 12 hex chars + length). If you believe a leak slipped through, please
file it — the redaction config is at the top of `.claude/hooks/_mcp_monitor.py`.

---

## Security notes (see CLAUDE.md `Security & Platform Notes` for the global view)

- `.mcp.json` is in the repo's shared config surface. Treat any PR that
  modifies it with the same scrutiny as `.claude/settings.json` — both can
  execute arbitrary commands on a session start (CVE-2025-59536 family).
- `uvx git+…` is pinned to tag `v1.0.2`. When upgrading, verify the
  commit SHA corresponds to a reviewed release of `googlecolab/colab-mcp`,
  not just a newly tagged HEAD.
- Hook output (`_mcp_tool_calls.log`, `_hook_errors.log`) is gitignored.
  If you move these files or share logs with someone, scrub them first.

---

## Phase Roadmap

| Phase | Status | Scope | Exit criteria (all met to advance) |
|-------|--------|-------|-----------------------------------|
| **0** — infra | **done** | `.mcp.json`, `recipe.yaml:mcp.enabled`, PreToolUse gate, redacted audit log, `/colab-mcp` skill, docs | 16-payload redaction suite passes; `mcp.enabled: false` blocks with exit 2 |
| **1** — field enforcement | **done** | `mcp.allow_auto_execution` gate, `max_tool_output_tokens` monitor, `preferred_gpu` / `keepalive` cell injection, `timeout_seconds` via `.claude/.env`, per-session JSONL log, `/colab-mcp-sync` skill + script with dry-run/apply/backup | All `(declarative)` tags eliminated; sync skill produces a diff against a live-cells dump and applies it atomically |
| **2** — sandbox | not started | Create `recipes/_mcp-sandbox/` (a tiny recipe) and walk it end-to-end: `/colab-mcp` → iterate → `/colab-mcp-sync` → `/session-end`. Collect real failure modes the unit tests didn't catch. | Notebook generation succeeds; at least one cell executed via MCP; manifest round-tripped without manual edits; failures logged in `context.md` Discovered Issues |
| **3** — default-on | not started | Flip `_template/recipe.yaml:mcp.enabled` default to `true`. Elevate MCP to primary iteration path in CLAUDE.md. | Two consecutive weeks running Phase 2 with zero `output over budget` escalations and zero post-sync "manifest differs from live" regressions |

**Do not skip phases.** Phase 2 exists specifically to catch the failure modes
that only appear under real Colab runtime conditions (idle disconnect,
A100 → L4 downgrade, tool-list shape surprises from the browser frontend).

---

## References

- Server source: https://github.com/googlecolab/colab-mcp
- Pinned tag (current): [v1.0.2](https://github.com/googlecolab/colab-mcp/releases/tag/v1.0.2)
- Local clone analyzed for this design: `C:/Users/kmw16/Desktop/colab-mcp-clone` (read-only)
- Claude Code MCP config spec: https://code.claude.com/docs/en/mcp-servers.md
- Related CVEs (MCP-generation attacks): CVE-2025-59536 (`.mcp.json` / `settings.json` RCE),
  CVE-2026-21852 (`ANTHROPIC_BASE_URL` hijack)

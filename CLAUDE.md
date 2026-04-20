# AI OSS Colab Test Template — CLAUDE.md

## Session Resume

If `.claude/_resume_state.md` exists, it contains critical context from a previous `/fresh-start`.
**Read it FIRST before responding to any user message.** Resume state describes the actual in-progress work
and takes priority over recipe SSOT docs for understanding "current work."

After successfully resuming (user confirms context is correct), delete `_resume_state.md` to prevent stale state.

## Single Source of Truth (SSOT)

Every recipe lives under `recipes/<recipe>/` and its **docs triad** is the SSOT:

| File | Purpose |
|------|---------|
| `recipes/<recipe>/docs/plan.md` | High-level goal, scope, approach |
| `recipes/<recipe>/docs/context.md` | Architecture, dependencies, key decisions |
| `recipes/<recipe>/docs/tasks.md` | Ordered task checklist (checkbox format) |

> **Rule**: Before writing any code, read the active recipe's docs triad.
> After every meaningful change, update `tasks.md` (check off completed items).

## NoMessLeftBehind Rules

1. **No orphan files** — every generated file must be referenced in a recipe's `notebook_manifest.yaml` or `recipe.yaml`.
2. **No silent failures** — all scripts must exit with non-zero on error; hooks must surface errors visibly.
3. **No stale context** — the context pack (`.claude/CLAUDE.md`) is regenerated on session start and after every stop hook. This file is auto-loaded by Claude Code.
4. **No untracked recipes** — running `recipes/<name>/run.sh` must work standalone after `install.sh`.
5. **Commit early, commit often** — each completed task in `tasks.md` should correspond to a commit.

## Active Recipe Tracking

The file `.claude/last_recipe.txt` holds the name of the currently active recipe.
Scripts and hooks read this to know which recipe's docs to consult.

Switch between recipes with the helper (rebuilds context pack automatically):
```bash
scripts/set_active_recipe.sh <recipe-name>   # switch
scripts/set_active_recipe.sh --list          # list available recipes
scripts/set_active_recipe.sh --current       # show active recipe
```

> **Multi-recipe rule**: only one recipe is "active" at a time — the SSOT docs triad
> of the active recipe is what Claude reads on session start. When working on
> several recipes in one day, switch explicitly with the helper.

## Standard Commands

| Command | Description |
|---------|-------------|
| `uv run python scripts/make_context_pack.py` | Rebuild `.claude/CLAUDE.md` (auto-loaded context pack) |
| `uv run python scripts/smoke_test.py` | Run basic compile + import checks |
| `uv run python tools/generate_notebook.py <recipe>` | Generate Colab notebook from manifest |

## Hooks (auto-configured in `.claude/settings.json`)

- **SessionStart** → `session-start.sh` → rebuilds context pack
- **UserPromptSubmit** → `userprompt-submit.sh` → skill auto-suggestion (skill-rules.json matching) + resume-state injection
- **PostToolUse** → `post-tool-use.sh` → tracks edited files to `_edited_files.log` (auto-rotates at 1000 entries)
- **PreCompact** → `pre-compact.sh` → auto-saves SSOT + `_resume_state.md` BEFORE compaction (lossy summary safety net)
- **Stop** → `stop.sh` → NoMessLeftBehind validation (compileall + smoke_test + context_pack); `stop_hook_active` guard prevents recursion (GH #10205)

## Skills

`UserPromptSubmit` hook matches prompts against `.claude/skill-rules.json` and auto-suggests relevant skills.

| Skill | Trigger | Description |
|-------|---------|-------------|
| `/recipe-authoring` | recipe, template, SSOT | Create/modify recipes and docs |
| `/colab-debugging` | pip error, CUDA, ImportError | Debug Colab compatibility issues |
| `/notebook-builder` | notebook, generate, manifest | Generate notebooks from manifests |
| `/session-end` | session end, handoff | Wrap up: docs + memory + commit + push + handoff prompt |
| `/pre-compact` | compact, context full | Persist critical context before auto-compact |
| `/fresh-start` | clear, fresh start, context poisoning | Save to SSOT + /clear for clean restart |

### `/session-end`
1. Update SSOT docs (context.md, tasks.md)
2. Update memory files
3. Context pack rebuild
4. Git commit + push
5. Generate handoff prompt for next session

### `/pre-compact`
1. Identify critical conversation context
2. Persist to docs and memory files
3. Suggest optimal `/compact <summary>` command

### `/fresh-start`
`/compact` 반복보다 `/clear` + SSOT 재읽기가 안정적. compact는 lossy summary 누적으로 맥락 오염 위험.
1. 미저장 맥락을 SSOT docs에 저장
2. Context pack 재생성
3. `/clear` 후 붙여넣을 resume 프롬프트 생성
4. 사용자가 `/clear` 실행 후 프롬프트 붙여넣기 → SSOT 기반 clean restart

> **Rule**: context가 커졌을 때 `/compact` 대신 `/fresh-start`를 권장. SSOT에 모든 맥락이 영속화되어 있으므로 유실 없음.

## Sub-Agents (`.claude/agents/`)

Frontmatter follows Claude Code spec: `name`, `description`, `tools` (space-separated).
Claude auto-delegates based on `description` matching current task.

| Agent | Role | Auto-delegate when |
|-------|------|--------------------|
| `code-reviewer` | Code review, consistency, NoMessLeftBehind | Multiple files edited, before commit, user asks "review" / "ready to ship?" |
| `compat-debugger` | Dependency/ABI resolution | `pip install` fails, `ImportError`, CUDA mismatch, C-ext build fail, "doesn't work in Colab" |
| `plan-architect` | SSOT scaffolding, architecture decisions | New recipe, user asks "how should we approach X?" / "what's the plan?" |

> To force delegation: use Task tool with `subagent_type: <agent-name>`. Claude otherwise
> judges from `description`. Agents receive an isolated context — parent sees only their final summary.

## NoMessLeftBehind (diet103-lite)

Stop hook checks `_edited_files.log` and runs (only if edits exist):
1. `python -m compileall .` — syntax check
2. `scripts/smoke_test.py` — import/compile check
3. `scripts/make_context_pack.py` — context pack refresh

## Adding a New Recipe

```bash
cp -r recipes/_template recipes/<new-name>
scripts/set_active_recipe.sh <new-name>   # atomically switches active recipe + rebuilds context pack
# Edit recipes/<new-name>/docs/plan.md to define the goal
```

## Colab MCP Integration (opt-in)

The repo's `.mcp.json` pins [googlecolab/colab-mcp @ v1.0.2](https://github.com/googlecolab/colab-mcp)
so Claude Code can drive a live Colab runtime (cell CRUD + execution) instead
of the manual "regenerate → upload → retest" loop.

**Authoritative docs**: `docs/MCP_INTEGRATION.md` (SSOT). This section only summarizes
workflow entry points — do not copy content back from there.

### Flow
1. `scripts/set_active_recipe.sh <recipe>` — writes `.claude/.env` with the
   recipe's `mcp.timeout_seconds` and `max_tool_output_tokens` as MCP envs.
2. `source .claude/.env && claude` — starts Claude with those envs applied.
3. `recipes/<recipe>/recipe.yaml` must have `mcp.enabled: true`. The PreToolUse
   hook `_mcp_monitor.py` blocks every `mcp__*` call with exit 2 otherwise.
4. `/colab-mcp` — opens the Colab tab and iterates cells. Every call is
   redacted and appended to `.claude/_mcp_tool_calls.log`; tool output is
   captured to `outputs/mcp-sessions/<recipe>/<session>.jsonl`.
5. `/colab-mcp-sync <recipe>` — before session end, diffs live notebook
   against `notebook_manifest.yaml` and promotes the edits (with user review).

### What is enforced automatically
- `mcp.enabled` — PreToolUse gate
- `mcp.allow_auto_execution` — PreToolUse blocks `run_cell`/`execute_*`/`exec_*` when false
- `mcp.preferred_gpu` — `generate_notebook.py` auto-injects a Cell A that asserts GPU match
- `mcp.keepalive` — `generate_notebook.py` auto-injects a daemon-thread heartbeat cell
- `mcp.max_tool_output_tokens` — PostToolUse flags over-budget outputs in `_hook_errors.log`
- `mcp.timeout_seconds` — exported as `MCP_TIMEOUT` (ms) via `.claude/.env`
- Secret redaction — 16 known-bypass payload tests pass; see `_mcp_monitor.py`

### Verify setup
```bash
uvx --from git+https://github.com/googlecolab/colab-mcp@v1.0.2 colab-mcp --help  # first run ~60s
claude mcp list                                                                    # expect: colab-mcp registered
```

## Security & Platform Notes

### `.claude/settings.json` AND `.mcp.json` are both executable (CVE-2025-59536)
Both files spawn child processes on session start. Treat **any PR that modifies
either file** with the same scrutiny as code changes that could exec on CI:
- `.claude/settings.json` runs shell hooks (SessionStart, PreToolUse, etc.).
- `.mcp.json` spawns MCP server subprocesses; a malicious `command` or `args`
  is arbitrary code execution with your Google/Colab session rights.

Recommended: add both paths to `CODEOWNERS` so merges require reviewer approval.
Keep contributor-specific overrides in `.claude/settings.local.json` and
`.mcp.json.local` (both gitignored) — never commit personal hook/server
commands to the shared files.

### Windows bash.exe hazard (GH #37634)
On Windows, `bash` in `PATH` may resolve to WSL's stub (`C:\Windows\System32\bash.exe`)
instead of Git Bash. This causes hooks to hang or silently fail. If hooks misbehave:
- Verify with `where bash` — Git Bash should appear first
- Fallback: edit `.claude/settings.json` to use absolute path, e.g.
  `"command": "\"C:/Program Files/Git/bin/bash.exe\" .claude/hooks/stop.sh"`
- Ensure `.bashrc` / `.zshrc` don't echo text unconditionally — it pollutes hook JSON.

### Never `git add -A` in automation
The `/session-end` skill uses explicit paths only. `git add -A` / `git add .` can
accidentally stage `.env`, credentials, or other untracked sensitive files. See
`.claude/skills/session-end/SKILL.md` for the vetted staging list.

## Colab Runtime Reference

`colab-runtimes/` contains auto-synced package snapshots from [googlecolab/backend-info](https://github.com/googlecolab/backend-info).

| File | Description |
|------|-------------|
| `colab-runtimes/runtimes.json` | Key packages per runtime version |
| `colab-runtimes/SUMMARY.md` | Side-by-side comparison table |
| `colab-runtimes/<version>/packages.json` | Full package list for a specific runtime |
| `colab-runtimes/quick-reference.md` | Compact reference for AI context |

Sync manually: `python scripts/sync_colab_runtimes.py`
Auto-sync: GitHub Action runs daily (`.github/workflows/sync-colab-runtimes.yml`)

> **Rule**: Before deciding on an install strategy, check `colab-runtimes/runtimes.json` for the target runtime's pre-installed packages. Do NOT hardcode version assumptions.

## Colab Porting Patterns

> Detailed strategies with code: `docs/PORTING_PATTERNS.md`
> Error pattern database: `docs/COMMON_ERRORS.md`

### Strategy Selection (evaluate in order)
1. **Direct pip** — Model deps match Colab stock. Only install missing packages. **Simplest.**
2. **Runtime rollback** — Older Colab runtime has matching torch/Python. **Change runtime version in UI.**
3. **Selective downgrade + patch** — One package needs older version. Downgrade it only, patch API breaks. **Targeted.**
4. **Shim / monkey-patch** — Build fails but torch-native substitute exists (e.g. flash-attn → SDPA). **No build needed.**
5. **Conda isolation** — Multiple C extensions with conflicting ABIs (spconv, nvdiffrast). **Last resort, 3-5 min setup.**

> Each strategy must be **verified in Colab** before documenting as confirmed. Record results in `context.md`.

### Verified Symptom → Fix Table
| Symptom | Verified Fix |
|---------|-------------|
| C extension .so conflict (spconv cumm) | Conda isolation (condacolab 0.1.x + runtime 2025.07) |
| flash-attn build failure | SDPA shim — see `docs/PORTING_PATTERNS.md` §4 |
| numpy/Pillow downgrade crash | Never downgrade. Keep Colab defaults. Conda if truly needed |
| Florence-2 on transformers 5.x | Replace with Qwen2.5-VL or similar native VLM |
| diffusers private API breakage | Selective downgrade + compatibility patch file |
| torch.load weights_only error | `torch.serialization.add_safe_globals([TargetClass])` |
| importlib.metadata for shim | Create `.dist-info/METADATA` file |
| GPU arch mismatch | `TORCH_CUDA_ARCH_LIST` env var |
| condacolab + Python 3.12 | Use runtime 2025.07 (Python 3.11) |
| xformers upgrades torch silently | Pin torch version explicitly in same pip command |
| Heavy preprocessing deps | Skip with flag (e.g. `preprocess_image=False`) |

### Requirements Rules
- **Never downgrade**: numpy, scipy, Pillow, matplotlib (Colab C extension ABI)
- **Never `pip install torch`** in base env (use Colab's pre-compiled version)
- **Pin carefully**: diffusers, xformers (version-sensitive, check Colab stock first)
- **Always fail-fast**: Add dependency verification cell after install, before inference

### Notebook Design Rules (from real projects)
- **Fail-fast verification** — Check all imports immediately after install cells, not 30 min later
- **Idempotent cells** — Every cell should be safe to re-run (skip detection, assert-guarded patches)
- **Pipeline caching** — Cache GPU model objects in `globals()` to survive cell re-runs
- **Config patch with assert** — `str.replace()` without assert is a silent bug source

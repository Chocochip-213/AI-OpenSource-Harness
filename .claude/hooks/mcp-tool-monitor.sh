#!/usr/bin/env bash
# PreToolUse hook (matcher="mcp__") — MCP audit log + recipe.yaml gate.
# Thin wrapper. Logic lives in .claude/hooks/_mcp_monitor.py (testable).
#
# Behavior summary:
#   - Skips silently if stdin is empty or tool_name is not mcp__*.
#   - Gracefully skips (WARN to _hook_errors.log) if no Python runtime is
#     available — does not break other developers' environments.
#   - Delegates to _mcp_monitor.py. Exit code 2 from that script blocks
#     the tool call (PreToolUse contract).
set -u  # no -o pipefail on purpose: we capture python exit explicitly

REPO_ROOT="$(cd "$(dirname "$0")/../.." && (pwd -W 2>/dev/null || pwd))"
ERROR_LOG="$REPO_ROOT/.claude/_hook_errors.log"

# Stash stdin once so we can filter and forward the same payload.
INPUT="$(cat 2>/dev/null || true)"
[ -z "$INPUT" ] && exit 0

# Fast bail-out: most tool calls are not MCP tools. Matcher filtering in
# settings.json already pre-filters, but double-check defensively.
case "$INPUT" in
  *'"tool_name"'*'"mcp__'*) : ;;  # continue
  *) exit 0 ;;
esac

# Discover a Python runtime. Each candidate is exec-smoke-tested because
# Windows MS Store's `python3.exe` shim satisfies `command -v python3`
# but exits 49 with a "Python was not found" stderr — leading to silent
# hook skip with no audit record. Graceful skip if none is available.
PY=""
for cand in "uv run python" python3 python; do
  head_cmd="${cand%% *}"
  if command -v "$head_cmd" >/dev/null 2>&1 && $cand -c "" 2>/dev/null; then
    PY="$cand"
    break
  fi
done
if [ -z "$PY" ]; then
  mkdir -p "$REPO_ROOT/.claude"
  printf '%s [mcp-tool-monitor] WARN no working python runtime (uv/python3/python) — hook skipped\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$ERROR_LOG"
  exit 0
fi

# Delegate. Preserve the child exit code (0 = allow, 2 = block).
printf '%s' "$INPUT" | $PY "$REPO_ROOT/.claude/hooks/_mcp_monitor.py"
exit $?

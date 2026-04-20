#!/usr/bin/env bash
# PostToolUse hook — track Edit/Write/NotebookEdit calls.
# Thin wrapper. Logic lives in .claude/hooks/_post_tool_use.py.
set -u

REPO_ROOT="$(cd "$(dirname "$0")/../.." && (pwd -W 2>/dev/null || pwd))"
ERROR_LOG="$REPO_ROOT/.claude/_hook_errors.log"

INPUT="$(cat 2>/dev/null || true)"
[ -z "$INPUT" ] && exit 0

PY=""
if   command -v uv       >/dev/null 2>&1; then PY="uv run python"
elif command -v python3  >/dev/null 2>&1; then PY="python3"
elif command -v python   >/dev/null 2>&1; then PY="python"
else
  mkdir -p "$REPO_ROOT/.claude"
  printf '%s [post-tool-use] WARN no python runtime — hook skipped\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$ERROR_LOG"
  exit 0
fi

# 1) Normal Edit/Write/NotebookEdit tracking.
printf '%s' "$INPUT" | $PY "$REPO_ROOT/.claude/hooks/_post_tool_use.py"

# 2) MCP tool completion capture (session log). Fast-bail for non-MCP tools
#    so we don't pay the python startup cost for every tool call.
case "$INPUT" in
  *'"tool_name"'*'"mcp__'*)
    printf '%s' "$INPUT" | $PY "$REPO_ROOT/.claude/hooks/_mcp_session_log.py"
    ;;
esac

exit 0

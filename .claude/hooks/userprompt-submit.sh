#!/usr/bin/env bash
# Hook: UserPromptSubmit — skill auto-suggest + SSOT reminder.
# Reads hook payload from stdin, pipes to skill_suggest.py.
# Outputs JSON {additionalContext: ...} to stdout (non-blocking suggest only).
set -u

REPO_ROOT="$(cd "$(dirname "$0")/../.." && (pwd -W 2>/dev/null || pwd))"
LOG_DIR="$REPO_ROOT/.claude"
ERROR_LOG="$LOG_DIR/_hook_errors.log"

# Graceful skip when uv not present — emit the simple SSOT reminder only.
if ! command -v uv >/dev/null 2>&1; then
  mkdir -p "$LOG_DIR"
  printf '%s [userprompt-submit] WARN uv not found — skill suggest skipped\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$ERROR_LOG"
  RECIPE="unknown"
  if [ -f "$LOG_DIR/last_recipe.txt" ]; then
    RECIPE="$(tr -d '[:space:]' < "$LOG_DIR/last_recipe.txt")"
  fi
  echo "{\"additionalContext\": \"[Reminder] Active recipe: $RECIPE — check SSOT docs before proceeding. (uv not installed; skill auto-suggest disabled)\"}"
  exit 0
fi

# Pipe stdin (hook payload JSON) to skill suggest engine.
# Errors go to the shared hook error log instead of /dev/null so we can
# diagnose skill-suggest failures later.
SUGGEST_OUTPUT=$(cat | uv run python "$REPO_ROOT/.claude/hooks/skill_suggest.py" 2>>"$ERROR_LOG" || true)

if [ -n "$SUGGEST_OUTPUT" ]; then
  echo "$SUGGEST_OUTPUT"
else
  # Fallback: simple SSOT reminder
  RECIPE="unknown"
  if [ -f "$REPO_ROOT/.claude/last_recipe.txt" ]; then
    RECIPE="$(tr -d '[:space:]' < "$REPO_ROOT/.claude/last_recipe.txt")"
  fi
  echo "{\"additionalContext\": \"[Reminder] Active recipe: $RECIPE — check SSOT docs before proceeding.\"}"
fi

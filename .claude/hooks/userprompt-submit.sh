#!/usr/bin/env bash
# Hook: UserPromptSubmit — skill auto-suggest + SSOT reminder
# Reads hook payload from stdin, pipes to skill_suggest.py
# Outputs JSON {additionalContext: ...} to stdout (non-blocking suggest only)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LOG_DIR="$REPO_ROOT/.claude"

# Pipe stdin (hook payload JSON) to skill suggest engine
# Log errors instead of silently discarding
SUGGEST_OUTPUT=$(cat | uv run python "$REPO_ROOT/.claude/hooks/skill_suggest.py" 2>>"$LOG_DIR/_skill_suggest.log" || true)

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

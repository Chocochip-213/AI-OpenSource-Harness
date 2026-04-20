#!/usr/bin/env bash
# Hook: PreCompact — auto-save critical context to SSOT before compaction
# lossy-summarizes. Runs /pre-compact skill logic automatically so even if
# auto-compact fires without user intervention, SSOT docs + resume state
# stay current.
#
# Non-blocking: always exit 0 so compaction proceeds.
set -u

REPO_ROOT="$(cd "$(dirname "$0")/../.." && (pwd -W 2>/dev/null || pwd))"
cd "$REPO_ROOT"
ERROR_LOG="$REPO_ROOT/.claude/_hook_errors.log"

# Consume payload (currently unused but keeps stdin drained for upstream).
_=$(cat 2>/dev/null || true)

# Determine active recipe (falls back to _template).
RECIPE="_template"
if [ -f .claude/last_recipe.txt ]; then
  RECIPE="$(tr -d '[:space:]' < .claude/last_recipe.txt)"
fi

# 1) Rebuild context pack — captures current uncommitted changes + SSOT docs.
if command -v uv >/dev/null 2>&1; then
  uv run python scripts/make_context_pack.py >/dev/null 2>&1 \
    || printf '%s [pre-compact] make_context_pack failed\n' \
       "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$ERROR_LOG"
else
  mkdir -p "$REPO_ROOT/.claude"
  printf '%s [pre-compact] WARN uv not found — context pack rebuild skipped\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$ERROR_LOG"
fi

# 2) Write _resume_state.md snapshot from git diff (deterministic).
RESUME=".claude/_resume_state.md"
TS="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

{
  echo "## Auto-saved Pre-Compact State"
  echo ""
  echo "Saved: $TS (UTC) — triggered by PreCompact hook"
  echo ""
  echo "## Active Recipe"
  echo "$RECIPE"
  echo ""
  echo "## Uncommitted Changes"
  echo '```'
  git status --short 2>/dev/null || echo "(no git or not a repo)"
  echo '```'
  echo ""
  echo "## Recent Edits (last 30 from _edited_files.log)"
  echo '```'
  tail -30 .claude/_edited_files.log 2>/dev/null || echo "(no edits tracked this session)"
  echo '```'
  echo ""
  echo "## Recent Commits (last 5)"
  echo '```'
  git log --oneline -5 2>/dev/null || echo "(no commits yet)"
  echo '```'
  echo ""
  echo "## Notes"
  echo "- This state was auto-saved BEFORE /compact ran."
  echo "- If compacted summary is lossy, restore context from:"
  echo "  1. This file ($RESUME)"
  echo "  2. SSOT docs: recipes/$RECIPE/docs/{plan,context,tasks}.md"
  echo "  3. Context pack: .claude/CLAUDE.md"
  echo "- For finer control next time, run /pre-compact skill manually before /compact."
} > "$RESUME"

echo "[hook:pre-compact] Saved resume state + rebuilt context pack before compaction." >&2
exit 0

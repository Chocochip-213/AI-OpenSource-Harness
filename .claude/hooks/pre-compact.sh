#!/usr/bin/env bash
# Hook: PreCompact — auto-save critical context to SSOT before compaction
# lossy-summarizes. Deterministic safety net (the /pre-compact skill was
# retired 2026-04-20 as redundant with this hook — community audit found
# skill-level prose duplicated what the hook already does).
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

# Preserve an in-flight /fresh-start snapshot. If $RESUME already exists,
# has a `Recipe:` header (= written by /fresh-start skill, not a previous
# PreCompact), and was modified within the last 30 minutes, skip the
# overwrite. Otherwise the curated Current Work / Notes / MCP URL sections
# get replaced by a bare git-diff snapshot (bug class: blind overwrite).
if [ -f "$RESUME" ]; then
  if head -10 "$RESUME" 2>/dev/null | grep -qE '^Recipe:[[:space:]]'; then
    MTIME=$(python -c "import os,sys;print(int(os.path.getmtime(r'$RESUME')))" 2>/dev/null \
            || python3 -c "import os,sys;print(int(os.path.getmtime(r'$RESUME')))" 2>/dev/null \
            || echo 0)
    NOW=$(date -u +%s)
    AGE=$((NOW - MTIME))
    if [ "$MTIME" -gt 0 ] && [ "$AGE" -lt 1800 ]; then
      printf '%s [pre-compact] preserved user-authored resume_state (age=%ss)\n' \
        "$TS" "$AGE" >> "$ERROR_LOG" 2>/dev/null || true
      echo "[hook:pre-compact] Preserved existing /fresh-start resume_state (age=${AGE}s)." >&2
      exit 0
    fi
  fi
fi

{
  echo "## Auto-saved Pre-Compact State"
  echo ""
  echo "Recipe: $RECIPE"
  echo "Saved: $TS"
  echo "Branch: $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
  echo ""
  echo "(Auto-saved by PreCompact hook — format matches /fresh-start so make_context_pack.py staleness check works.)"
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
  echo "- For finer control next time, run /fresh-start before /compact (2026-04-20 retired /pre-compact skill — hook-only now)."
} > "$RESUME"

echo "[hook:pre-compact] Saved resume state + rebuilt context pack before compaction." >&2
exit 0

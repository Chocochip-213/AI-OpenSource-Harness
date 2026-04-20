#!/usr/bin/env bash
# Hook: SessionEnd — fires on /clear, /logout, prompt-input-exit.
# Cleans `.claude/_resume_state.md` so next session doesn't re-inject
# stale resume context. Distinct from `Stop` which fires every turn end.
set -u

REPO_ROOT="$(cd "$(dirname "$0")/../.." && (pwd -W 2>/dev/null || pwd))"
ERROR_LOG="$REPO_ROOT/.claude/_hook_errors.log"
RESUME="$REPO_ROOT/.claude/_resume_state.md"

# Read payload to distinguish reason. Claude Code sends matcher info.
INPUT="$(cat 2>/dev/null || true)"

# Always log the reason (best-effort) so we have an audit trail.
mkdir -p "$REPO_ROOT/.claude"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
REASON=$(printf '%s' "$INPUT" | grep -oE '"reason"[[:space:]]*:[[:space:]]*"[^"]+"' | head -1 || true)
printf '%s [session-end] %s\n' "$TS" "${REASON:-(no reason)}" >> "$ERROR_LOG" 2>/dev/null || true

# Drop the resume state — it's been "consumed" by definition. The next
# /fresh-start will write a fresh one.
if [ -f "$RESUME" ]; then
  rm -f "$RESUME" 2>/dev/null || true
fi

exit 0

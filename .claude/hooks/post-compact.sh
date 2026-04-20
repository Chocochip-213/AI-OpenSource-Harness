#!/usr/bin/env bash
# Hook: PostCompact — fires right after /compact (manual or auto).
# Pre-compact already snapshotted state into `_resume_state.md`; once the
# compaction itself is done, that snapshot is no longer authoritative
# (the new compacted history is). Drop it so next /fresh-start writes
# a fresh one rather than serving stale context.
set -u

REPO_ROOT="$(cd "$(dirname "$0")/../.." && (pwd -W 2>/dev/null || pwd))"
ERROR_LOG="$REPO_ROOT/.claude/_hook_errors.log"
RESUME="$REPO_ROOT/.claude/_resume_state.md"

# Drain stdin (we don't need the payload but mustn't leave it hanging).
_=$(cat 2>/dev/null || true)

mkdir -p "$REPO_ROOT/.claude"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf '%s [post-compact] removed stale resume_state\n' "$TS" >> "$ERROR_LOG" 2>/dev/null || true

if [ -f "$RESUME" ]; then
  rm -f "$RESUME" 2>/dev/null || true
fi

exit 0

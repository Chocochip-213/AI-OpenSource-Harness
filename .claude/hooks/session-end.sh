#!/usr/bin/env bash
# Hook: SessionEnd — fires on /clear, /logout, prompt-input-exit.
#
# Audit-only. Does NOT delete `.claude/_resume_state.md` — that file is
# owned by /fresh-start (overwrite on next invocation) and by the
# stale-check in scripts/make_context_pack.py (Recipe-header mismatch
# after recipe switch → ignored). Auto-delete here was the cause of the
# 2026-04-20 seed bug: SessionEnd stripped the file before SessionStart
# could re-inline it via make_context_pack, wiping user resume context.
set -u

REPO_ROOT="$(cd "$(dirname "$0")/../.." && (pwd -W 2>/dev/null || pwd))"
ERROR_LOG="$REPO_ROOT/.claude/_hook_errors.log"

INPUT="$(cat 2>/dev/null || true)"

mkdir -p "$REPO_ROOT/.claude"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
REASON=$(printf '%s' "$INPUT" | grep -oE '"reason"[[:space:]]*:[[:space:]]*"[^"]+"' | head -1 || true)
printf '%s [session-end] %s\n' "$TS" "${REASON:-(no reason)}" >> "$ERROR_LOG" 2>/dev/null || true

exit 0

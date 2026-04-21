#!/usr/bin/env bash
# Hook: PostCompact — fires right after /compact (manual or auto).
#
# Audit-only. Does NOT delete `.claude/_resume_state.md`. Rationale:
# /compact often fails or is cancelled mid-run (Claude Code contract
# still fires PostCompact), and the resume snapshot is the user's only
# safety net. The stale-check in scripts/make_context_pack.py
# (Recipe-header mismatch across recipe switches → section ignored)
# and /fresh-start's overwrite-on-next-call are sufficient cleanup.
set -u

REPO_ROOT="$(cd "$(dirname "$0")/../.." && (pwd -W 2>/dev/null || pwd))"
ERROR_LOG="$REPO_ROOT/.claude/_hook_errors.log"

_=$(cat 2>/dev/null || true)

mkdir -p "$REPO_ROOT/.claude"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf '%s [post-compact] audit\n' "$TS" >> "$ERROR_LOG" 2>/dev/null || true

exit 0

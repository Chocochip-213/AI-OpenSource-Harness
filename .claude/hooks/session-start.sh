#!/usr/bin/env bash
# Hook: SessionStart — rebuild the context pack so Claude sees current SSOT.
# Graceful-skips when uv/python is unavailable so other devs' environments
# aren't broken by the hook alone.
set -u

REPO_ROOT="$(cd "$(dirname "$0")/../.." && (pwd -W 2>/dev/null || pwd))"
cd "$REPO_ROOT"
ERROR_LOG="$REPO_ROOT/.claude/_hook_errors.log"

if ! command -v uv >/dev/null 2>&1; then
  mkdir -p "$REPO_ROOT/.claude"
  printf '%s [session-start] WARN uv not found — context pack rebuild skipped\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$ERROR_LOG"
  echo "[hook:session-start] uv not installed — skipping context pack rebuild. Install uv to enable." >&2
  exit 0
fi

echo "[hook:session-start] Rebuilding context pack..."
uv run python scripts/make_context_pack.py
echo "[hook:session-start] Context pack ready: .claude/CLAUDE.md (auto-loaded)"

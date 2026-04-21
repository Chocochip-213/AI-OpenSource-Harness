#!/usr/bin/env bash
# Hook: Stop — NoMessLeftBehind verification (lightweight).
# Only runs checks if files were edited this session.
set -u

REPO_ROOT="$(cd "$(dirname "$0")/../.." && (pwd -W 2>/dev/null || pwd))"
cd "$REPO_ROOT"
ERROR_LOG="$REPO_ROOT/.claude/_hook_errors.log"

# --- Infinite loop guard (GitHub #10205) ---
# If Claude re-triggered Stop while we're still inside a Stop hook,
# skip immediately to prevent recursion. Read hook payload from stdin once.
INPUT="$(cat 2>/dev/null || true)"
if [ -n "$INPUT" ] && printf '%s' "$INPUT" | grep -q '"stop_hook_active"[[:space:]]*:[[:space:]]*true'; then
  echo "[hook:stop] stop_hook_active=true — skipping to prevent recursion." >&2
  exit 0
fi

# Graceful skip when uv not present.
if ! command -v uv >/dev/null 2>&1; then
  mkdir -p "$REPO_ROOT/.claude"
  printf '%s [stop] WARN uv not found — Stop checks skipped\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$ERROR_LOG"
  echo "[hook:stop] uv not installed — skipping compile/smoke checks. Install uv to enable." >&2
  exit 0
fi

LOG_FILE="$REPO_ROOT/.claude/_edited_files.log"
ERRORS=0

# --- Check if any files were edited ---
if [ -f "$LOG_FILE" ] && [ -s "$LOG_FILE" ]; then
  EDIT_COUNT=$(wc -l < "$LOG_FILE")
  echo "[hook:stop] $EDIT_COUNT file edit(s) tracked this session." >&2

  # (a) compileall — lightweight syntax check
  echo "[hook:stop] Running compileall..." >&2
  if uv run python -m compileall -q . 2>&1; then
    echo "[hook:stop] compileall: OK" >&2
  else
    echo "[hook:stop] compileall: FAILED" >&2
    ERRORS=$((ERRORS + 1))
  fi

  # (b) smoke test — capture exit code properly (not through pipe)
  echo "[hook:stop] Running smoke_test..." >&2
  SMOKE_EXIT=0
  uv run python scripts/smoke_test.py 2>&1 || SMOKE_EXIT=$?
  if [ "$SMOKE_EXIT" -eq 0 ]; then
    echo "[hook:stop] smoke_test: OK" >&2
  else
    echo "[hook:stop] smoke_test: FAILED (exit=$SMOKE_EXIT, non-blocking)" >&2
  fi

  # (c) refresh context pack
  echo "[hook:stop] Refreshing context pack..." >&2
  uv run python scripts/make_context_pack.py 2>&1 \
    || printf '%s [stop] make_context_pack failed\n' \
       "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$ERROR_LOG"

  echo "[hook:stop] Tip: consider running 'ruff format .' or 'black .' on edited files." >&2

  # DO NOT truncate $LOG_FILE here — Stop fires every turn end (not once
  # per session). Truncating every turn made the 100KB/1000-line rotator
  # in _post_tool_use.py dead code, and emptied the buffer that PreCompact
  # and docs-discipline depend on. The rotator handles growth.
else
  echo "[hook:stop] No file edits tracked — skipping heavy checks." >&2
  uv run python scripts/make_context_pack.py 2>&1 \
    || printf '%s [stop] make_context_pack failed\n' \
       "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$ERROR_LOG"
fi

if [ "$ERRORS" -gt 0 ]; then
  echo "[hook:stop] $ERRORS check(s) FAILED." >&2
  exit 1
fi

echo "[hook:stop] All checks passed." >&2
exit 0

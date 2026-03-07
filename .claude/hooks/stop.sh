#!/usr/bin/env bash
# Hook: Stop — NoMessLeftBehind verification (lightweight)
# Only runs checks if files were edited this session.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

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
  uv run python scripts/make_context_pack.py 2>&1 || true

  echo "[hook:stop] Tip: consider running 'ruff format .' or 'black .' on edited files." >&2

  # Clear the edit log for next session
  > "$LOG_FILE"
else
  echo "[hook:stop] No file edits tracked — skipping heavy checks." >&2
  uv run python scripts/make_context_pack.py 2>&1 || true
fi

if [ "$ERRORS" -gt 0 ]; then
  echo "[hook:stop] $ERRORS check(s) FAILED." >&2
  exit 1
fi

echo "[hook:stop] All checks passed." >&2
exit 0

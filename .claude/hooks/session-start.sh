#!/usr/bin/env bash
# Hook: SessionStart — rebuild context pack on every new session
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

echo "[hook:session-start] Rebuilding context pack..."
uv run python scripts/make_context_pack.py
echo "[hook:session-start] Context pack ready: .claude/_context_pack.md"

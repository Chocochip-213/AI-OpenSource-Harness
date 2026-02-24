#!/usr/bin/env bash
# Hook: PostToolUse — track edited files for NoMessLeftBehind verification
# Reads hook payload from stdin, appends edit events to _edited_files.log
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LOG_FILE="$REPO_ROOT/.claude/_edited_files.log"

# Read hook payload from stdin
PAYLOAD=$(cat)

# Extract tool name and file path from payload
TOOL_NAME=$(echo "$PAYLOAD" | uv run python -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_name', ''))
except: pass
" 2>/dev/null || true)

# Only track file-editing tools
case "$TOOL_NAME" in
  Edit|Write|NotebookEdit)
    FILE_PATH=$(echo "$PAYLOAD" | uv run python -c "
import sys, json
try:
    d = json.load(sys.stdin)
    inp = d.get('tool_input', {})
    print(inp.get('file_path', inp.get('notebook_path', '')))
except: pass
" 2>/dev/null || true)
    if [ -n "$FILE_PATH" ]; then
      # Append as JSONL (use env vars to avoid quoting/escape issues)
      _TOOL="$TOOL_NAME" _FILE="$FILE_PATH" uv run python -c "
import json, os
from datetime import datetime, timezone
entry = {
    'ts': datetime.now(timezone.utc).isoformat(),
    'tool': os.environ['_TOOL'],
    'file': os.environ['_FILE']
}
print(json.dumps(entry))
" >> "$LOG_FILE" 2>/dev/null || true
    fi
    ;;
esac

# Never block — always exit 0
exit 0

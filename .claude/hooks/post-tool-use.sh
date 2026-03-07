#!/usr/bin/env bash
# Hook: PostToolUse — track edited files for NoMessLeftBehind verification
# Single python invocation to minimize overhead (runs on EVERY tool call)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LOG_FILE="$REPO_ROOT/.claude/_edited_files.log"

# Single python call: parse payload, check tool, write log entry
cat | uv run python -c "
import sys, json
from datetime import datetime, timezone
from pathlib import Path

log_file = Path('$LOG_FILE')

try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)

tool = d.get('tool_name', '')
if tool not in ('Edit', 'Write', 'NotebookEdit'):
    sys.exit(0)

inp = d.get('tool_input', {})
fp = inp.get('file_path', inp.get('notebook_path', ''))
if not fp:
    sys.exit(0)

entry = json.dumps({
    'ts': datetime.now(timezone.utc).isoformat(),
    'tool': tool,
    'file': fp,
})
with open(log_file, 'a', encoding='utf-8') as f:
    f.write(entry + '\n')
" 2>/dev/null || true

exit 0

#!/usr/bin/env bash
# PreToolUse gate: blocks `git commit` when harness files are staged
# without a recent `.claude/_code_review_passed.json` marker.
#
# Purpose: force code-reviewer sub-agent invocation before committing
# changes to files that define Claude Code behaviour (CLAUDE.md, hooks,
# skills, agents, settings, .mcp.json, tools/, scripts/). Self-review
# has empirically failed in this project — the gate is deterministic.
#
# Marker format (JSON): {"timestamp": "<iso>", "agent_id": "<hex>",
# "verdict": "ready|needs-fixes", "files_reviewed": ["path1", ...]}
# Gate passes only when verdict == "ready" AND marker.mtime > max(staged.mtime).
#
# Bypass: `CLAUDE_SKIP_COMMIT_GATE=1 git commit ...` for emergency fixes.
# Log an entry to .claude/_hook_errors.log on bypass so the skip is audited.
set -u

# Discover a Python runtime — match mcp-tool-monitor.sh. Systems without
# the `python` alias (python3-only Linux distros) previously fell through
# to `CMD=""` and silently passed every git commit through the gate.
PY=""
if   command -v uv       >/dev/null 2>&1; then PY="uv run python"
elif command -v python3  >/dev/null 2>&1; then PY="python3"
elif command -v python   >/dev/null 2>&1; then PY="python"
else
    REPO_ROOT_FOR_LOG="$(cd "$(dirname "$0")/../.." 2>/dev/null && (pwd -W 2>/dev/null || pwd))"
    mkdir -p "$REPO_ROOT_FOR_LOG/.claude"
    printf '%s [commit_gate] no python runtime — hook fail-open skipped\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$REPO_ROOT_FOR_LOG/.claude/_hook_errors.log" 2>/dev/null || true
    exit 0
fi

INPUT="$(cat 2>/dev/null || true)"
CMD=$(printf '%s' "$INPUT" | $PY -c "import sys,json
try:
    print(json.loads(sys.stdin.read() or '{}').get('tool_input', {}).get('command', ''))
except Exception:
    pass" 2>/dev/null || echo "")

# Not a git commit → pass silently
if ! printf '%s' "$CMD" | grep -qE '(^|[ &;|])git[[:space:]]+commit([[:space:]]|$)'; then
    exit 0
fi

# Explicit bypass
if [ "${CLAUDE_SKIP_COMMIT_GATE:-0}" = "1" ]; then
    REPO_ROOT="$(cd "$(dirname "$0")/../.." 2>/dev/null && (pwd -W 2>/dev/null || pwd))"
    printf '%s [commit_gate] BYPASSED via CLAUDE_SKIP_COMMIT_GATE=1\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$REPO_ROOT/.claude/_hook_errors.log" 2>/dev/null
    exit 0
fi

REPO_ROOT="$(cd "$(dirname "$0")/../.." && (pwd -W 2>/dev/null || pwd))"
cd "$REPO_ROOT" || exit 0

STAGED="$(git diff --cached --name-only 2>/dev/null)"
if [ -z "$STAGED" ]; then
    exit 0  # nothing staged — let git commit produce its own empty-commit error
fi

# Is anything staged a harness file?
HARNESS_STAGED=$(printf '%s\n' "$STAGED" | grep -E '^(CLAUDE\.md|\.claude/(hooks|skills|agents|settings\.json|skill-rules\.json)|\.mcp\.json|tools/|scripts/|docs/.*\.md|recipes/_template/|\.github/|\.gitattributes)' || true)
if [ -z "$HARNESS_STAGED" ]; then
    exit 0  # no harness file staged — normal commit, pass
fi

MARKER="$REPO_ROOT/.claude/_code_review_passed.json"
if [ ! -f "$MARKER" ]; then
    cat >&2 <<EOF
[commit_gate] BLOCKED — harness files staged without code-reviewer pass.
[commit_gate] Staged harness files:
$(printf '%s' "$HARNESS_STAGED" | sed 's/^/  - /')
[commit_gate] Required: run Agent(subagent_type='code-reviewer') on the
              staged diff, then write $MARKER with
              {"timestamp": "<iso>", "agent_id": "<id>",
               "verdict": "ready", "files_reviewed": [...]}.
[commit_gate] Emergency bypass: CLAUDE_SKIP_COMMIT_GATE=1 git commit ...
EOF
    exit 2
fi

# Parse verdict + mtime (Windows cp949 default breaks json.load — force utf-8)
VERDICT=$($PY -c "import json;print(json.load(open(r'$MARKER',encoding='utf-8')).get('verdict',''))" 2>/dev/null || echo "")
if [ "$VERDICT" != "ready" ]; then
    echo "[commit_gate] BLOCKED — marker verdict is '$VERDICT' (not 'ready')." >&2
    echo "[commit_gate] Address reviewer findings, re-run Agent(subagent_type='code-reviewer'), update marker." >&2
    exit 2
fi

# Marker must be newer than every staged harness file
MARKER_TS=$($PY -c "import os,sys;print(int(os.path.getmtime(r'$MARKER')))" 2>/dev/null || echo 0)
STALE_FILES=""
while IFS= read -r f; do
    [ -z "$f" ] && continue
    [ -f "$REPO_ROOT/$f" ] || continue
    FILE_TS=$($PY -c "import os,sys;print(int(os.path.getmtime(r'$REPO_ROOT/$f')))" 2>/dev/null || echo 0)
    if [ "$FILE_TS" -gt "$MARKER_TS" ]; then
        STALE_FILES="$STALE_FILES  - $f\n"
    fi
done <<< "$HARNESS_STAGED"

if [ -n "$STALE_FILES" ]; then
    printf "[commit_gate] BLOCKED — marker is older than these staged files (modified after the last review):\n" >&2
    printf "$STALE_FILES" >&2
    echo "[commit_gate] Re-run Agent(subagent_type='code-reviewer') to refresh the marker, or amend the marker timestamp by writing a new one." >&2
    exit 2
fi

echo "[commit_gate] PASS — marker verdict=ready, mtime>staged." >&2
exit 0

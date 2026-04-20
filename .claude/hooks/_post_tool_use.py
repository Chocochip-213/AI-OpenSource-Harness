#!/usr/bin/env python3
"""PostToolUse hook — track edited files for NoMessLeftBehind verification.

Appends a JSON record to .claude/_edited_files.log whenever Edit / Write /
NotebookEdit succeeds, and rotates the log past ~100KB. All error paths
write to .claude/_hook_errors.log instead of swallowing silently.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LOG_FILE = REPO_ROOT / ".claude" / "_edited_files.log"
ERROR_LOG = REPO_ROOT / ".claude" / "_hook_errors.log"

MAX_LOG_BYTES = 100_000
MAX_LINES = 1000
KEEP_LINES = 500


def log_error(msg: str) -> None:
    try:
        ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now(timezone.utc).isoformat()} [post_tool_use] {msg}\n")
        try:
            if ERROR_LOG.stat().st_size > 50_000:
                lines = ERROR_LOG.read_text(encoding="utf-8").splitlines()
                if len(lines) > 500:
                    ERROR_LOG.write_text("\n".join(lines[-300:]) + "\n", encoding="utf-8")
        except Exception:
            pass
    except Exception:
        pass


def main() -> int:
    try:
        raw = sys.stdin.read()
    except Exception as e:
        log_error(f"stdin read failed: {e}")
        return 0
    if not raw.strip():
        return 0
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        log_error(f"payload JSON parse failed: {e}")
        return 0

    tool = payload.get("tool_name", "")
    if tool not in ("Edit", "Write", "NotebookEdit"):
        return 0

    inp = payload.get("tool_input") or {}
    fp = inp.get("file_path") or inp.get("notebook_path") or ""
    if not fp:
        return 0

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "tool": tool,
        "file": fp,
    }
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            # ensure_ascii=True for the same lone-surrogate safety reason as
            # _mcp_monitor — file paths can contain Windows Git Bash CJK.
            f.write(json.dumps(entry, ensure_ascii=True) + "\n")
    except Exception as e:
        log_error(f"write failed: {e}")
        return 0

    try:
        if LOG_FILE.stat().st_size > MAX_LOG_BYTES:
            lines = LOG_FILE.read_text(encoding="utf-8").splitlines()
            if len(lines) > MAX_LINES:
                LOG_FILE.write_text("\n".join(lines[-KEEP_LINES:]) + "\n", encoding="utf-8")
    except Exception as e:
        log_error(f"rotate failed: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""PostToolUse tail for MCP tool calls — writes per-session JSONL session log.

Works with `.claude/hooks/_mcp_monitor.py` (PreToolUse, which logs and
enforces gating). This script runs AFTER the MCP tool call completes and
captures the real tool output for manifest reconciliation by
`/colab-mcp-sync`.

Output path:   outputs/mcp-sessions/<recipe>/<session-id>.jsonl
Session id:    opened on the first open_colab_browser_connection call,
               persisted in .claude/_mcp_session.txt; reset when that tool
               is re-invoked (= reconnection).

Each JSONL entry:
    {
      "ts": ISO8601,
      "recipe": <name>,
      "tool": "mcp__…",
      "input_summary": <redacted summary — same logic as audit log>,
      "output_len": int,
      "output_truncated": bool,
      "output_preview": <first 2KB of stringified result, redacted>,
      "output_hash": sha256[:16] of full result,
      "duration_ms": int | null,
      "status": "ok" | "error",
      "error": str | null
    }

Exit codes: always 0 (post-hook must not block subsequent tools).
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ERROR_LOG = REPO_ROOT / ".claude" / "_hook_errors.log"
LAST_RECIPE_FILE = REPO_ROOT / ".claude" / "last_recipe.txt"
SESSION_ID_FILE = REPO_ROOT / ".claude" / "_mcp_session.txt"

# Re-use redaction helpers from the PreToolUse monitor so behavior stays aligned.
sys.path.insert(0, str(Path(__file__).parent))
try:
    from _mcp_monitor import redact, SENSITIVE_VALUE_RES, FULL_VALUE_POISONS  # type: ignore
    from _recipe_config import active_recipe_config, MCP_DEFAULTS  # type: ignore
except Exception as _imp_err:  # pragma: no cover - defensive
    redact = None  # type: ignore
    SENSITIVE_VALUE_RES = []  # type: ignore
    FULL_VALUE_POISONS = None  # type: ignore
    active_recipe_config = None  # type: ignore
    MCP_DEFAULTS = {}  # type: ignore
    _import_error = _imp_err
else:
    _import_error = None

OUTPUT_PREVIEW_BYTES = 2048
# Rough chars-per-token ratio for output_len→token budget check. Claude
# tokenizer averages ~4 chars/token; we stay conservative.
CHARS_PER_TOKEN = 4


def log_error(msg: str) -> None:
    try:
        ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now(timezone.utc).isoformat()} [mcp_session_log] {msg}\n")
    except Exception:
        pass


def active_recipe() -> str:
    try:
        if LAST_RECIPE_FILE.exists():
            return LAST_RECIPE_FILE.read_text(encoding="utf-8").strip() or "_template"
    except Exception as e:
        log_error(f"last_recipe read failed: {e}")
    return "_template"


def get_session_id(tool: str) -> str:
    """Return the current session id. Reset to a fresh one whenever a new
    connection is opened (the browser handshake tool)."""
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if tool.endswith("open_colab_browser_connection"):
        SESSION_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
        SESSION_ID_FILE.write_text(now, encoding="utf-8")
        return now
    if SESSION_ID_FILE.exists():
        try:
            sid = SESSION_ID_FILE.read_text(encoding="utf-8").strip()
            if sid:
                return sid
        except Exception as e:
            log_error(f"session id read failed: {e}")
    # No prior session — caller tripped the safety rail; use the current time
    # so later audits can still correlate the orphan call.
    return f"orphan-{now}"


def _scrub_preview(s: str) -> str:
    if not s:
        return s
    if FULL_VALUE_POISONS is not None and FULL_VALUE_POISONS.search(s):
        return "<redacted-envelope>"
    out = s
    for pat in SENSITIVE_VALUE_RES:
        out = pat.sub("<redacted-value>", out)
    return out


def _stringify_output(result) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    try:
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception:
        return str(result)


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

    tool = (payload.get("tool_name") or "").strip()
    if not tool.startswith("mcp__"):
        return 0

    if _import_error is not None:
        log_error(f"monitor import failed, falling back to raw: {_import_error}")

    # Prefer the shared parser (same cfg as PreToolUse). Fall back to minimal
    # recipe-name lookup if the import failed.
    if callable(active_recipe_config):
        recipe, mcp_cfg = active_recipe_config()
    else:
        recipe = active_recipe()
        mcp_cfg = dict(MCP_DEFAULTS)
    session_id = get_session_id(tool)

    tool_input = payload.get("tool_input") or {}
    tool_result = payload.get("tool_response")
    if tool_result is None:
        # Some Claude Code versions send 'tool_result' instead
        tool_result = payload.get("tool_result")

    # Status + duration (Claude Code adds these on PostToolUse payloads when
    # available; we read defensively).
    status = "ok"
    error_msg = None
    if isinstance(tool_result, dict):
        if tool_result.get("is_error") or tool_result.get("error"):
            status = "error"
            error_msg = str(tool_result.get("error") or tool_result.get("content") or "")[:400]
    duration_ms = payload.get("duration_ms")

    output_str = _stringify_output(tool_result)
    full_hash = hashlib.sha256(output_str.encode("utf-8", errors="replace")).hexdigest()[:16]
    truncated = len(output_str) > OUTPUT_PREVIEW_BYTES
    preview = _scrub_preview(output_str[:OUTPUT_PREVIEW_BYTES])

    # Input summary — reuse monitor's redact if available.
    if callable(redact):
        input_summary = redact("", tool_input)
    else:
        input_summary = "<redaction unavailable>"

    # Output budget enforcement (advisory — the actual context cap is set by
    # MAX_MCP_OUTPUT_TOKENS env; we record + warn so users see the overrun).
    budget_tokens = int(mcp_cfg.get("max_tool_output_tokens") or 0)
    est_tokens = len(output_str) // CHARS_PER_TOKEN if CHARS_PER_TOKEN else 0
    over_budget = bool(budget_tokens and est_tokens > budget_tokens)
    if over_budget:
        log_error(
            f"output over budget: {tool} est_tokens={est_tokens} "
            f"budget={budget_tokens} (recipe={recipe}, session={session_id}) — "
            f"consider raising mcp.max_tool_output_tokens or trimming the upstream output"
        )

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "recipe": recipe,
        "session": session_id,
        "tool": tool,
        "input_summary": input_summary,
        "output_len": len(output_str),
        "output_est_tokens": est_tokens,
        "output_truncated": truncated,
        "output_over_budget": over_budget,
        "output_preview": preview,
        "output_hash": full_hash,
        "duration_ms": duration_ms if isinstance(duration_ms, (int, float)) else None,
        "status": status,
        "error": error_msg,
    }

    session_log = REPO_ROOT / "outputs" / "mcp-sessions" / recipe / f"{session_id}.jsonl"
    try:
        session_log.parent.mkdir(parents=True, exist_ok=True)
        with open(session_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        log_error(f"session log write failed: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

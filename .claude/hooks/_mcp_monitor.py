#!/usr/bin/env python3
"""MCP tool-call monitor — invoked as PreToolUse for matcher='mcp__'.

Responsibilities:
  1. Parse stdin JSON payload (PreToolUse schema).
  2. Short-circuit if tool_name is not mcp__*.
  3. Enforce per-recipe opt-in: block (exit 2) if active recipe's
     recipes/<name>/recipe.yaml does not set mcp.enabled: true.
  4. Redact secrets and append a structured audit record to
     .claude/_mcp_tool_calls.log. Rotate at ~200KB.

Called by .claude/hooks/mcp-tool-monitor.sh (thin wrapper). Kept as a
separate file so redaction logic is testable in isolation.

Exit codes:
  0  allow tool call
  2  block tool call (PreToolUse contract — Claude sees stderr)
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LOG_FILE = REPO_ROOT / ".claude" / "_mcp_tool_calls.log"
ERROR_LOG = REPO_ROOT / ".claude" / "_hook_errors.log"
LAST_RECIPE_FILE = REPO_ROOT / ".claude" / "last_recipe.txt"

# Shared config reader — keeps PreToolUse and PostToolUse in sync.
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent))
from _recipe_config import active_recipe_config  # noqa: E402

# Tool-name patterns that trigger code execution. A blocklist so we don't
# approve arbitrary code runs when `allow_auto_execution: false`. Matched
# against the last component of `mcp__<server>__<tool>`.
EXECUTING_TOOL_RE = re.compile(
    r"(^|_)(run|execute|exec|eval)($|_)|add_and_run|insert_and_run",
    re.IGNORECASE,
)

MAX_LOG_BYTES = 200_000
MAX_LINES = 2000
KEEP_LINES = 1000
MAX_VALUE_LEN = 120

# ---- redaction rules ----

# Key names (case-insensitive substring) → full redact.
# English standard set + common Korean/Japanese secret-related terms.
# Adding Latin coverage beyond English is intentionally narrow — wide CJK
# matching has high false-positive cost (e.g. "키" alone matches index_key
# in transliterated kor projects). Stick to unambiguous secret nouns.
SENSITIVE_KEY_RE = re.compile(
    r"token|secret|password|passphrase|apikey|api_key|auth|bearer|"
    r"credential|cert|priv|private|session|pem|rsa|ed25519|"
    r"signature|nonce|"
    # Korean
    r"비밀번호|암호|토큰|인증|"
    # Japanese
    r"パスワード|トークン|認証|秘密",
    re.IGNORECASE,
)

# If these appear ANYWHERE in a string value, the entire value is redacted
# (treats the value as a secret envelope rather than trying to scrub parts).
FULL_VALUE_POISONS = re.compile(
    r"-----BEGIN [A-Z ]+-----",
)

# Value patterns → scrub wherever they appear (even under innocuous keys).
SENSITIVE_VALUE_RES = [
    re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),                          # OpenAI/Anthropic-style
    re.compile(r"ghp_[A-Za-z0-9]{30,}"),                             # GitHub PAT
    re.compile(r"gho_[A-Za-z0-9]{30,}"),                             # GitHub OAuth
    re.compile(r"AIza[0-9A-Za-z\-_]{35}"),                           # Google API key
    re.compile(r"ya29\.[A-Za-z0-9_\-]{20,}"),                        # Google OAuth access token
    re.compile(r"eyJ[A-Za-z0-9\-_]{10,}\.[A-Za-z0-9\-_\.]{10,}"),    # JWT-ish
    re.compile(r"xox[baprs]-[0-9]+-[0-9]+[A-Za-z0-9\-]*"),           # Slack
    re.compile(r"mcpProxyToken=[A-Za-z0-9_\-]+"),                    # colab-mcp handshake
]

# Field names whose VALUE is treated as untrusted content — we log a hash only.
CODE_FIELD_RE = re.compile(
    r"^(code|source|script|notebook|content|body|payload|cell|"
    r"stdout|stderr|command|query|prompt)$",
    re.IGNORECASE,
)


def log_error(msg: str) -> None:
    try:
        ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now(timezone.utc).isoformat()} [mcp_monitor] {msg}\n")
        # Bound the error log so a runaway hook doesn't fill disk.
        try:
            if ERROR_LOG.stat().st_size > 50_000:
                lines = ERROR_LOG.read_text(encoding="utf-8").splitlines()
                if len(lines) > 500:
                    ERROR_LOG.write_text("\n".join(lines[-300:]) + "\n", encoding="utf-8")
        except Exception:
            pass
    except Exception:
        pass  # never crash the hook on error-log write failure


def _scrub_str(s: str) -> str:
    # If the value is an envelope containing a known-secret marker (PEM etc.),
    # replace the entire value — partial redaction leaves secret bytes exposed.
    if FULL_VALUE_POISONS.search(s):
        return "<redacted-envelope>"
    out = s
    for pat in SENSITIVE_VALUE_RES:
        out = pat.sub("<redacted-value>", out)
    if len(out) > MAX_VALUE_LEN:
        out = out[:MAX_VALUE_LEN] + f"…(len:{len(s)})"
    return out


def redact(key: str, value):
    """Recursively redact dict/list/scalar. Key/value rules applied together."""
    if key and CODE_FIELD_RE.match(key):
        s = str(value)
        digest = hashlib.sha256(s.encode("utf-8", errors="replace")).hexdigest()[:12]
        return f"<hash:{digest} len:{len(s)}>"
    if key and SENSITIVE_KEY_RE.search(key):
        return "<redacted>"
    if isinstance(value, dict):
        return {k: redact(k, v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact("", v) for v in value]
    if isinstance(value, str):
        return _scrub_str(value)
    s = str(value)
    if len(s) > MAX_VALUE_LEN:
        s = s[:MAX_VALUE_LEN] + f"…(len:{len(str(value))})"
    return s


def _tool_leaf(tool: str) -> str:
    """`mcp__server__leaf` → `leaf` (for executing-tool pattern match)."""
    parts = tool.split("__")
    return parts[-1] if parts else tool


def rotate_log() -> None:
    try:
        if LOG_FILE.exists() and LOG_FILE.stat().st_size > MAX_LOG_BYTES:
            lines = LOG_FILE.read_text(encoding="utf-8").splitlines()
            if len(lines) > MAX_LINES:
                LOG_FILE.write_text("\n".join(lines[-KEEP_LINES:]) + "\n", encoding="utf-8")
    except Exception as e:
        log_error(f"rotate failed: {e}")


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

    tool = payload.get("tool_name", "") or ""
    if not tool.startswith("mcp__"):
        return 0

    recipe, mcp_cfg = active_recipe_config()

    def _audit(status: str, extra: dict | None = None) -> None:
        """Append one redacted line to the audit log. Used for both allowed
        and blocked calls so post-mortem reviewers can answer "what was
        blocked, when?" without joining two log files.

        ensure_ascii=True is intentional: Windows Git Bash forwards lone
        surrogates (\\udcXX) for CJK input, which json.dumps refuses to
        encode as utf-8 — that previously dropped audit lines silently.
        """
        try:
            tool_input = payload.get("tool_input") or {}
            redacted = redact("", tool_input) if callable(redact) else "<redact unavailable>"
            entry = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "recipe": recipe,
                "tool": tool,
                "status": status,
                "input": redacted,
            }
            if extra:
                entry.update(extra)
            LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=True) + "\n")
            rotate_log()
        except Exception as e:
            log_error(f"audit write failed for {tool}: {e}")

    # --- Gate 1: opt-in check ---
    if not mcp_cfg.get("enabled"):
        msg = (
            f"MCP call blocked: {tool}. "
            f"recipes/{recipe}/recipe.yaml does not have mcp.enabled: true. "
            f"Set mcp.enabled: true to opt in. See docs/MCP_INTEGRATION.md."
        )
        sys.stderr.write(f"[hook:mcp_monitor] {msg}\n")
        log_error(f"blocked (gate=enabled): {tool} (recipe={recipe})")
        _audit("blocked", {"gate": "enabled"})
        return 2

    # --- Gate 2: auto-execution consent ---
    # When `mcp.allow_auto_execution: false`, every code-execution tool needs
    # an explicit re-invocation from the user. We block here and ask Claude to
    # confirm with the human before retrying.
    leaf = _tool_leaf(tool)
    is_exec = bool(EXECUTING_TOOL_RE.search(leaf))
    if is_exec and not mcp_cfg.get("allow_auto_execution"):
        msg = (
            f"MCP exec blocked: {tool}. "
            f"recipes/{recipe}/recipe.yaml has mcp.allow_auto_execution: false. "
            f"Confirm with the user before running code on the live Colab runtime, "
            f"then either (a) flip allow_auto_execution: true for this session or "
            f"(b) have the user approve this specific call."
        )
        sys.stderr.write(f"[hook:mcp_monitor] {msg}\n")
        log_error(f"blocked (gate=auto_exec): {tool} (recipe={recipe})")
        _audit("blocked", {"gate": "auto_exec"})
        return 2

    # --- Log redacted call (allowed) ---
    _audit("allowed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Tiny YAML reader for the active recipe's `mcp:` block.

Shared by PreToolUse (_mcp_monitor.py) and PostToolUse (_mcp_session_log.py)
so both hooks observe the same configuration. Intentionally avoids PyYAML
(not guaranteed to be installed) — hand-rolled scanner handles the subset of
YAML that this harness writes.

Returns a typed dict with sensible defaults on any ambiguity:
    {
      "enabled": bool,
      "allow_auto_execution": bool,
      "max_tool_output_tokens": int,
      "preferred_gpu": str | None,
      "keepalive": bool,
      "timeout_seconds": int,
    }
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LAST_RECIPE_FILE = REPO_ROOT / ".claude" / "last_recipe.txt"


def session_id_file_for(recipe: str) -> Path:
    """Per-recipe session-id file. Splitting prevents cross-recipe contamination
    when the user switches `last_recipe.txt` while an MCP session is open —
    each recipe's PostToolUse log stays paired with its own session id.
    """
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", recipe) or "_default"
    return REPO_ROOT / ".claude" / f"_mcp_session_{safe}.txt"

MCP_DEFAULTS: Dict[str, Any] = {
    "enabled": False,
    "allow_auto_execution": False,
    "max_tool_output_tokens": 10000,
    "preferred_gpu": None,
    "keepalive": False,
    "timeout_seconds": 300,
}

_BOOL_TRUE = {"true", "yes", "on", "1"}
_BOOL_FALSE = {"false", "no", "off", "0", "null", "~", "none"}


def _coerce(key: str, raw: str) -> Any:
    raw = raw.strip()
    # Strip trailing comments (# not inside quotes — good enough for our YAML subset)
    if "#" in raw and not (raw.startswith('"') or raw.startswith("'")):
        raw = raw.split("#", 1)[0].strip()
    raw = raw.strip('"').strip("'")
    default = MCP_DEFAULTS.get(key)
    if isinstance(default, bool):
        lowered = raw.lower()
        if lowered in _BOOL_TRUE:
            return True
        if lowered in _BOOL_FALSE:
            return False
        return default
    if isinstance(default, int):
        try:
            return int(raw)
        except (TypeError, ValueError):
            return default
    # strings and None
    if raw.lower() in _BOOL_FALSE:
        return None
    return raw or default


def parse_mcp_block(recipe_yaml_path: Path) -> Dict[str, Any]:
    cfg: Dict[str, Any] = dict(MCP_DEFAULTS)
    if not recipe_yaml_path.exists():
        return cfg
    try:
        text = recipe_yaml_path.read_text(encoding="utf-8")
    except Exception:
        return cfg

    in_block = False
    block_indent: int | None = None
    for line in text.splitlines():
        stripped = line.rstrip()
        if not stripped or stripped.lstrip().startswith("#"):
            continue
        if re.match(r"^mcp:\s*$", stripped):
            in_block = True
            block_indent = 0
            continue
        if in_block:
            indent = len(line) - len(line.lstrip())
            if indent <= (block_indent or 0):
                break
            m = re.match(
                r"\s+(enabled|allow_auto_execution|max_tool_output_tokens|"
                r"preferred_gpu|keepalive|timeout_seconds)\s*:\s*(.*)$",
                line,
            )
            if m:
                key = m.group(1)
                cfg[key] = _coerce(key, m.group(2))
    return cfg


def active_recipe_name() -> str:
    try:
        if LAST_RECIPE_FILE.exists():
            return LAST_RECIPE_FILE.read_text(encoding="utf-8").strip() or "_template"
    except Exception:
        pass
    return "_template"


def active_recipe_config() -> tuple[str, Dict[str, Any]]:
    name = active_recipe_name()
    path = REPO_ROOT / "recipes" / name / "recipe.yaml"
    return name, parse_mcp_block(path)


if __name__ == "__main__":
    import json, sys
    name, cfg = active_recipe_config()
    print(json.dumps({"recipe": name, "mcp": cfg}, indent=2, default=str))

#!/usr/bin/env python3
"""Generate .claude/_context_pack.md from active recipe docs + git status."""

import os
import subprocess
import sys
from pathlib import Path


def get_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def read_file_safe(path: Path, max_lines: int = 60) -> str:
    """Read file, return content truncated to max_lines."""
    if not path.exists():
        return f"(file not found: {path})\n"
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    content = "\n".join(lines[:max_lines])
    if len(lines) > max_lines:
        content += f"\n... ({len(lines) - max_lines} more lines)\n"
    return content


def get_active_recipe(repo: Path) -> str:
    last_recipe = repo / ".claude" / "last_recipe.txt"
    if last_recipe.exists():
        return last_recipe.read_text(encoding="utf-8").strip()
    return "_template"


def git_command(args: list[str], cwd: Path) -> str:
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True, text=True, cwd=str(cwd), timeout=10
        )
        return result.stdout.strip() if result.returncode == 0 else f"(git error: {result.stderr.strip()})"
    except Exception as e:
        return f"(git unavailable: {e})"


def build_context_pack(repo: Path) -> str:
    recipe = get_active_recipe(repo)
    docs_dir = repo / "recipes" / recipe / "docs"

    sections = []
    sections.append(f"# Context Pack\n\n**Active Recipe**: `{recipe}`")
    sections.append(f"**Generated**: auto\n")

    # --- Recipe docs ---
    sections.append("## Recipe Docs\n")
    for doc_name in ("plan.md", "context.md", "tasks.md"):
        doc_path = docs_dir / doc_name
        sections.append(f"### {doc_name}\n")
        sections.append(f"```\n{read_file_safe(doc_path)}\n```\n")

    # --- Uncommitted changes (strongest signal of current work) ---
    git_status = git_command(['status', '--short'], repo)
    git_diff_stat = git_command(['diff', '--stat'], repo)
    git_diff_names = git_command(['diff', '--name-only'], repo)
    has_changes = bool(git_status.strip()) and not git_status.startswith("(git")

    if has_changes:
        sections.append("## Uncommitted Changes (IN PROGRESS)\n")
        sections.append(f"```\n{git_status}\n```\n")
        sections.append(f"Changed files:\n```\n{git_diff_stat}\n```\n")

    # --- Resume state (written by /fresh-start skill) ---
    resume_path = repo / ".claude" / "_resume_state.md"
    if resume_path.exists():
        sections.append("## Resume State (from /fresh-start)\n")
        sections.append(read_file_safe(resume_path, max_lines=40))
        sections.append("")

    if not has_changes:
        sections.append("## Git Status\n")
        sections.append(f"```\n{git_status}\n```\n")

    return "\n".join(sections)


def main():
    repo = get_repo_root()
    claude_dir = repo / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)

    content = build_context_pack(repo)

    # Primary: .claude/CLAUDE.md — auto-loaded by Claude Code on every session
    auto_load_path = claude_dir / "CLAUDE.md"
    auto_load_path.write_text(content, encoding="utf-8")
    print(f"[make_context_pack] Written to {auto_load_path.relative_to(repo)}")

    # Legacy: _context_pack.md — keep for backward compat (gitignored)
    legacy_path = claude_dir / "_context_pack.md"
    legacy_path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()

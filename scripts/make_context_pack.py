#!/usr/bin/env python3
"""Generate .claude/CLAUDE.md from active recipe docs + git status + resume state."""

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
    recipe_yaml = repo / "recipes" / recipe / "recipe.yaml"

    sections = []
    sections.append(f"# Context Pack\n\n**Active Recipe**: `{recipe}`")
    sections.append(f"**Generated**: auto\n")

    # Orphan-recipe warning — `set_active_recipe.sh` validates the triad
    # but --force bypass (and historical recipe-switch states) can still
    # produce sessions where docs are missing. Surface loudly so Claude
    # doesn't quietly plan against a phantom SSOT.
    missing = []
    for fname in ("plan.md", "context.md", "tasks.md"):
        if not (docs_dir / fname).exists():
            missing.append(f"docs/{fname}")
    if not recipe_yaml.exists():
        missing.append("recipe.yaml")
    if missing:
        sections.append(
            "> **WARNING: ORPHAN RECIPE** — `" + recipe + "` is active but "
            "missing: " + ", ".join(missing) + ". "
            "Either `scripts/set_active_recipe.sh <valid-recipe>` to switch, "
            "or scaffold with `cp -r recipes/_template recipes/" + recipe + "`.\n"
        )

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
    # Stale-check: if the resume state was saved for a different recipe than
    # the one now active, it's leftover from a recipe switch — skip it to
    # prevent hallucinated reconciliation between two states.
    resume_path = repo / ".claude" / "_resume_state.md"
    if resume_path.exists():
        raw = resume_path.read_text(encoding="utf-8", errors="replace")
        saved_for = None
        # Widened from 10 to 40 lines to tolerate user preambles before
        # the header (matches `read_file_safe(..., max_lines=40)` truncation).
        for line in raw.splitlines()[:40]:
            if line.lower().startswith("recipe:"):
                saved_for = line.split(":", 1)[1].strip()
                break
        # Corruption detection: `errors="replace"` substitutes U+FFFD
        # for any byte it can't decode. That would make saved_for
        # something like "flux2\ufffd-klein" and the stale-check would
        # always fire (silently dropping a valid fresh-start snapshot
        # from the pack). Detect and surface explicitly.
        if saved_for and "\ufffd" in saved_for:
            sections.append(
                f"## Resume State — CORRUPT (encoding error in `Recipe:` header)\n"
                f"`.claude/_resume_state.md` contains undecodable bytes in its "
                f"`Recipe:` line. This usually means a Windows CJK path leaked a "
                f"lone surrogate into the file. NOT loading it. Inspect the file "
                f"and either fix the header manually or re-run `/fresh-start` to "
                f"regenerate.\n"
            )
        elif saved_for and saved_for != recipe:
            sections.append(
                f"## Resume State — IGNORED (stale: saved for `{saved_for}`, active `{recipe}`)\n"
                f"A `_resume_state.md` exists but its `Recipe:` header does not match "
                f"the current active recipe. It is NOT being loaded into this context. "
                f"Delete `.claude/_resume_state.md` or re-run `/fresh-start` after "
                f"switching back to `{saved_for}` if that was intentional.\n"
            )
        else:
            # Inline the resume state inside a fenced block. The skill
            # template uses `##` section headers (Current Work / Next Steps
            # / Notes). Without a fence, those headers become peers of
            # the `## Resume State (from /fresh-start)` wrapper AND of
            # this script's own `## Uncommitted Changes (IN PROGRESS)`
            # section — breaking the hierarchy and inviting the reader
            # to reconcile two "Uncommitted Changes" sections that say
            # different things.
            # Use a 4-backtick fence so nested 3-backtick blocks inside
            # (from /fresh-start's `## Uncommitted Changes` git-status
            # dump, or pre-compact.sh's auto-save) don't terminate it
            # early.
            sections.append("## Resume State (from /fresh-start)\n")
            sections.append("````markdown")
            sections.append(read_file_safe(resume_path, max_lines=40))
            sections.append("````\n")

    if not has_changes:
        sections.append("## Git Status\n")
        sections.append(f"```\n{git_status}\n```\n")

    return "\n".join(sections)


def main():
    repo = get_repo_root()
    claude_dir = repo / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)

    content = build_context_pack(repo)

    # .claude/CLAUDE.md — auto-loaded by Claude Code on every session.
    # The legacy `.claude/_context_pack.md` dual-write was removed 2026-04-21:
    # nothing consumed it (the bootstrap prompt was updated to read CLAUDE.md),
    # it was accidentally tracked in the initial commit so every regeneration
    # dirtied a file users then might have `git add`-ed — leaking personal
    # session state (recipe name, uncommitted file list, resume content) to
    # the shared master branch.
    auto_load_path = claude_dir / "CLAUDE.md"
    auto_load_path.write_text(content, encoding="utf-8")
    print(f"[make_context_pack] Written to {auto_load_path.relative_to(repo)}")


if __name__ == "__main__":
    main()

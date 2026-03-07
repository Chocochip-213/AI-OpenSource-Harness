#!/usr/bin/env python3
"""Skill auto-suggestion engine.

Reads hook payload JSON from stdin, matches prompt against skill-rules.json,
outputs JSON with suggested skills as additionalContext.
"""

import fnmatch
import json
import re
import sys
from pathlib import Path


def load_skill_rules(repo_root: Path) -> list[dict]:
    rules_path = repo_root / ".claude" / "skill-rules.json"
    if not rules_path.exists():
        return []
    with open(rules_path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("skills", [])


def load_recent_edits(repo_root: Path) -> list[str]:
    """Read recent file paths from _edited_files.log (JSONL)."""
    log_path = repo_root / ".claude" / "_edited_files.log"
    if not log_path.exists():
        return []
    paths = []
    try:
        for line in log_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                file_path = entry.get("file", "")
                if file_path:
                    try:
                        rel = str(Path(file_path).relative_to(repo_root))
                    except ValueError:
                        rel = file_path
                    paths.append(rel.replace("\\", "/"))
            except json.JSONDecodeError:
                continue
    except Exception:
        pass
    return paths


def match_skill(skill: dict, prompt: str) -> tuple[bool, str]:
    """Check if prompt matches a skill. Returns (matched, reason)."""
    prompt_lower = prompt.lower()

    # Keyword match
    for kw in skill.get("keywords", []):
        if kw.lower() in prompt_lower:
            return True, f"keyword '{kw}'"

    # Intent pattern match
    for pattern in skill.get("intentPatterns", []):
        try:
            if re.search(pattern, prompt):
                return True, f"pattern '{pattern[:40]}...'"
        except re.error:
            continue

    return False, ""


def match_skill_paths(skill: dict, edited_paths: list[str]) -> tuple[bool, str]:
    """Check if any recently edited file matches a skill's pathPatterns."""
    for pattern in skill.get("pathPatterns", []):
        for path in edited_paths:
            if fnmatch.fnmatch(path, pattern):
                return True, f"edited file '{path}' matches '{pattern}'"
    return False, ""


def suggest_skills(prompt: str, edited_paths: list[str], repo_root: Path) -> list[dict]:
    skills = load_skill_rules(repo_root)
    matches = []
    seen = set()

    for skill in skills:
        name = skill["name"]

        # Input 1: Prompt text matching
        matched, reason = match_skill(skill, prompt)
        if matched and name not in seen:
            matches.append({
                "name": name,
                "reason": reason,
                "hint": skill.get("hint", ""),
                "priority": skill.get("priority", 50),
            })
            seen.add(name)

        # Input 2: Recently edited file path matching
        if name not in seen and edited_paths:
            matched, reason = match_skill_paths(skill, edited_paths)
            if matched:
                matches.append({
                    "name": name,
                    "reason": reason,
                    "hint": skill.get("hint", ""),
                    "priority": skill.get("priority", 50),
                })
                seen.add(name)

    # Sort by priority (lower = higher priority)
    matches.sort(key=lambda x: x["priority"])
    return matches


def main():
    repo_root = Path(__file__).resolve().parent.parent.parent

    # Read hook payload from stdin
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, Exception):
        payload = {}

    # Extract prompt from hook payload (UserPromptSubmit schema)
    prompt = payload.get("prompt", "")
    if not prompt:
        sys.exit(0)

    # Load recently edited file paths (Input 2)
    edited_paths = load_recent_edits(repo_root)

    matches = suggest_skills(prompt, edited_paths, repo_root)

    if not matches:
        sys.exit(0)

    # Build additionalContext output — MINIMAL to conserve tokens.
    # Only include skill name + hint (1-2 lines per skill).
    # Do NOT inject full SKILL.md content — Claude will read it if needed.
    lines = ["[Skill Suggestions]"]
    for m in matches:
        lines.append(f"  -> /{m['name']} (matched: {m['reason']})")
        if m["hint"]:
            lines.append(f"     {m['hint']}")

    # Read active recipe for SSOT reminder
    recipe = "_template"
    recipe_file = repo_root / ".claude" / "last_recipe.txt"
    if recipe_file.exists():
        recipe = recipe_file.read_text(encoding="utf-8").strip()

    lines.append(f"[SSOT] Active recipe: {recipe} — check docs/{{plan,context,tasks}}.md")

    # Output as JSON for hook additionalContext
    output = {"additionalContext": "\n".join(lines)}
    print(json.dumps(output))


if __name__ == "__main__":
    main()

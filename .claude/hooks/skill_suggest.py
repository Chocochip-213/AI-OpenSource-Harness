#!/usr/bin/env python3
"""Skill auto-suggestion engine.

Reads hook payload JSON from stdin, matches prompt against skill-rules.json,
outputs JSON with suggested skills as additionalContext.
"""

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


def suggest_skills(prompt: str, repo_root: Path) -> list[dict]:
    skills = load_skill_rules(repo_root)
    matches = []

    for skill in skills:
        matched, reason = match_skill(skill, prompt)
        if matched:
            matches.append({
                "name": skill["name"],
                "reason": reason,
                "hint": skill.get("hint", ""),
                "priority": skill.get("priority", 50),
            })

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
        # No prompt in payload — nothing to suggest
        sys.exit(0)

    matches = suggest_skills(prompt, repo_root)

    if not matches:
        sys.exit(0)

    # Build additionalContext output
    lines = ["[Skill Suggestions]"]
    for m in matches:
        lines.append(f"  -> {m['name']} (matched: {m['reason']})")
        if m["hint"]:
            lines.append(f"     Hint: {m['hint']}")

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

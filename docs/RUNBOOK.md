# Runbook — AI OSS Colab Test Template

## Hook Verification

### Quick Check: Are hooks configured correctly?

```bash
# 1. Verify settings.json has all 4 hooks
uv run python -c "
import json
with open('.claude/settings.json') as f:
    hooks = json.load(f).get('hooks', {})
expected = ['SessionStart', 'UserPromptSubmit', 'PostToolUse', 'Stop']
for h in expected:
    status = 'OK' if h in hooks else 'MISSING'
    print(f'  {h}: {status}')
"
```

### Test Each Hook Manually

```bash
# SessionStart — should rebuild context pack
bash .claude/hooks/session-start.sh

# UserPromptSubmit — test skill suggestion (pipe a fake payload)
echo '{"prompt":"add a new recipe for SwiftTry"}' | bash .claude/hooks/userprompt-submit.sh

# PostToolUse — test edit tracking (pipe a fake Edit event)
echo '{"tool_name":"Edit","tool_input":{"file_path":"test.py"}}' | bash .claude/hooks/post-tool-use.sh
cat .claude/_edited_files.log

# Stop — should run checks if edits were tracked
bash .claude/hooks/stop.sh
```

### Verify Skill Rules

```bash
# List all configured skills
uv run python -c "
import json
with open('.claude/skill-rules.json') as f:
    skills = json.load(f).get('skills', [])
for s in skills:
    print(f\"  {s['name']} (priority={s['priority']}, enforcement={s['enforcement']})\")
"
```

## Common Workflows

### Add a New Recipe
```bash
cp -r recipes/_template recipes/<name>
echo "<name>" > .claude/last_recipe.txt
# Edit docs/plan.md, then start implementation
```

### Generate Notebook
```bash
uv run python tools/generate_notebook.py <recipe-name>
# Output: outputs/notebooks/<recipe-name>.ipynb
```

### Full Smoke Test
```bash
uv run python -m compileall . && uv run python scripts/smoke_test.py
```

## Skill Suggestion — Manual Test (3 Samples)

```bash
# 1) Recipe keyword → expect: recipe-authoring
echo '{"prompt":"add a new recipe for SwiftTry"}' | bash .claude/hooks/userprompt-submit.sh
# Expected: -> recipe-authoring (matched: keyword 'recipe')

# 2) Colab debug keyword → expect: colab-debugging
echo '{"prompt":"fix pip install torch conflict in Colab"}' | bash .claude/hooks/userprompt-submit.sh
# Expected: -> colab-debugging (matched: keyword 'pip')

# 3) Notebook intent → expect: notebook-builder
echo '{"prompt":"generate the notebook for my recipe"}' | bash .claude/hooks/userprompt-submit.sh
# Expected: -> notebook-builder (matched: pattern 'generate.*notebook')
```

File-path matching test (requires `_edited_files.log` entries):
```bash
echo '{"ts":"2026-01-01","tool":"Edit","file":"recipes/test/docs/plan.md"}' > .claude/_edited_files.log
echo '{"prompt":"check status"}' | bash .claude/hooks/userprompt-submit.sh
# Expected: -> recipe-authoring (matched: edited file ... matches 'recipes/**/docs/**')
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Hook fails with "uv not found" | uv not in PATH | Ensure `~/.local/bin` is in PATH |
| skill_suggest.py errors | Invalid JSON in skill-rules.json | Validate: `uv run python -m json.tool .claude/skill-rules.json` |
| compileall fails | Syntax error in .py file | Check the reported file path and fix |
| smoke_test warns about yaml | PyYAML not installed | `uv pip install pyyaml` (optional) |

# Skill: recipe-authoring

## When Active
Triggered when creating, modifying, or managing recipes and their SSOT docs.

## Workflow
1. **Read** the SSOT triad before any change:
   - `recipes/<name>/docs/plan.md` — goal & scope
   - `recipes/<name>/docs/context.md` — architecture & decisions
   - `recipes/<name>/docs/tasks.md` — checkbox progress
2. **Update** `tasks.md` after completing each step (check off the item).
3. **Record** every decision in `context.md` → "Key Decisions" with rationale.
4. **Verify** `recipe.yaml` references the correct requirements file and entry point.

## New Recipe Checklist
```bash
cp -r recipes/_template recipes/<name>
echo "<name>" > .claude/last_recipe.txt
```
Then fill: `plan.md` → `recipe.yaml` → code files → `notebook_manifest.yaml` → `tasks.md` checkoffs.

## Constraints
- Every generated file must appear in `recipe.yaml` or `notebook_manifest.yaml` (NoMessLeftBehind).
- `install.sh` and `run.sh` must work standalone.

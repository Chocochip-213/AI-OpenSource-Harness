# Add New Recipe

## Usage
```
Provide a recipe name and description, then follow these steps.
```

## Steps

1. **Copy template**:
   ```bash
   cp -r recipes/_template recipes/<recipe-name>
   echo "<recipe-name>" > .claude/last_recipe.txt
   ```

2. **Edit the docs triad** — fill in the three SSOT files:
   - `recipes/<recipe-name>/docs/plan.md` — goal, scope, approach
   - `recipes/<recipe-name>/docs/context.md` — architecture, deps, decisions
   - `recipes/<recipe-name>/docs/tasks.md` — ordered task checklist

3. **Edit recipe.yaml** — update name, description, requirements choice

4. **Add dependencies** to `requirements_opt1.txt` (or opt2)

5. **Add code files** to the recipe directory

6. **Update notebook_manifest.yaml** — list all files to include in the Colab notebook

7. **Test locally**:
   ```bash
   bash recipes/<recipe-name>/install.sh
   bash recipes/<recipe-name>/run.sh
   ```

8. **Generate notebook**:
   ```bash
   python tools/generate_notebook.py <recipe-name>
   ```

9. **Commit** with a message referencing the recipe name.

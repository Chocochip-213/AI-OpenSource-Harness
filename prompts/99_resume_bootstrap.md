# Resume Bootstrap

You are resuming work on the **AI OSS Colab Test Template**.

## Steps

1. **Read the context pack** to understand current state:
   ```
   Read .claude/_context_pack.md
   ```

2. **Check active recipe**:
   ```
   Read .claude/last_recipe.txt
   ```

3. **Review tasks.md** for the active recipe to find next unchecked item:
   ```
   Read recipes/<recipe>/docs/tasks.md
   ```

4. **Continue from the first unchecked task**.

5. After completing work, verify:
   ```bash
   python scripts/smoke_test.py
   python scripts/make_context_pack.py
   ```

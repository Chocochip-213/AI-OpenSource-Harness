# Bootstrap All

You are setting up the **AI OSS Colab Test Template** from scratch.

## Instructions

1. Run through the full bootstrap checklist:
   - Verify directory structure exists
   - Verify CLAUDE.md is present and correct
   - Verify `.claude/settings.json` hooks are configured
   - Verify all hook scripts exist and are executable
   - Verify `scripts/make_context_pack.py` runs without error
   - Verify `scripts/smoke_test.py` passes
   - Verify `recipes/_template/` is complete

2. Run the context pack generator:
   ```bash
   python scripts/make_context_pack.py
   ```

3. Run the smoke test:
   ```bash
   python scripts/smoke_test.py
   ```

4. Report status and any issues found.

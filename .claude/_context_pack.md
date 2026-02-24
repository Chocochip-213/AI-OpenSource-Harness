# Context Pack

**Active Recipe**: `_template`
**Generated**: auto

## Recipe Docs

### plan.md

```
# Plan

## Goal
<!-- What does this recipe accomplish? -->

## Scope
<!-- What's in / out of scope? -->

## Approach
<!-- High-level strategy -->

## Success Criteria
<!-- How do we know it works? -->
```

### context.md

```
# Context

## Architecture
<!-- How components connect -->

## Dependencies
<!-- Key libraries and versions -->

## Key Decisions
<!-- Every decision goes here with rationale. Example: -->
<!-- - Chose opt1 (minimal deps) because Colab free tier has limited install time -->

## References
<!-- Links, papers, docs -->

---

> **Rule**: When a decision is made during implementation, add it to "Key Decisions" with the reasoning.
> This file is the permanent record — don't let knowledge stay only in chat history.
```

### tasks.md

```
# Tasks

## Setup
- [ ] Copy _template to `recipes/<name>`
- [ ] Update `recipe.yaml` with real values
- [ ] Fill out `docs/plan.md`

## Implementation
- [ ] Add main code files
- [ ] Add dependencies to `requirements_opt1.txt`
- [ ] Update `notebook_manifest.yaml`

## Validation
- [ ] Run `install.sh` successfully
- [ ] Run `run.sh` successfully
- [ ] Generate and test Colab notebook

---

> **Rule**: Check off each task immediately upon completion.
> Every decision made during implementation must be recorded in `context.md` → "Key Decisions".
```

## Git Status

```
M .claude/_context_pack.md
 M .claude/hooks/post-tool-use.sh
 M .claude/hooks/skill_suggest.py
 M .claude/skill-rules.json
 M docs/RUNBOOK.md
?? .claude/_edited_files.log
?? .claude/hooks/__pycache__/
?? .claude/skills/
?? __pycache__/
?? scripts/__pycache__/
?? tools/__pycache__/
```

## Git Diff (stat)

```
.claude/_context_pack.md       | 26 +++++++++------
 .claude/hooks/post-tool-use.sh | 10 +++---
 .claude/hooks/skill_suggest.py | 75 ++++++++++++++++++++++++++++++++++++++----
 .claude/skill-rules.json       | 11 ++++---
 docs/RUNBOOK.md                | 23 +++++++++++++
 5 files changed, 120 insertions(+), 25 deletions(-)
```

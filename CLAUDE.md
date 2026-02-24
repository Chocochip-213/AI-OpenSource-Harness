# AI OSS Colab Test Template — CLAUDE.md

## Single Source of Truth (SSOT)

Every recipe lives under `recipes/<recipe>/` and its **docs triad** is the SSOT:

| File | Purpose |
|------|---------|
| `recipes/<recipe>/docs/plan.md` | High-level goal, scope, approach |
| `recipes/<recipe>/docs/context.md` | Architecture, dependencies, key decisions |
| `recipes/<recipe>/docs/tasks.md` | Ordered task checklist (checkbox format) |

> **Rule**: Before writing any code, read the active recipe's docs triad.
> After every meaningful change, update `tasks.md` (check off completed items).

## NoMessLeftBehind Rules

1. **No orphan files** — every generated file must be referenced in a recipe's `notebook_manifest.yaml` or `recipe.yaml`.
2. **No silent failures** — all scripts must exit with non-zero on error; hooks must surface errors visibly.
3. **No stale context** — the context pack (`.claude/_context_pack.md`) is regenerated on session start and after every stop hook.
4. **No untracked recipes** — running `recipes/<name>/run.sh` must work standalone after `install.sh`.
5. **Commit early, commit often** — each completed task in `tasks.md` should correspond to a commit.

## Active Recipe Tracking

The file `.claude/last_recipe.txt` holds the name of the currently active recipe.
Scripts and hooks read this to know which recipe's docs to consult.

## Standard Commands

| Command | Description |
|---------|-------------|
| `uv run python scripts/make_context_pack.py` | Rebuild `.claude/_context_pack.md` |
| `uv run python scripts/smoke_test.py` | Run basic compile + import checks |
| `uv run python tools/generate_notebook.py <recipe>` | Generate Colab notebook from manifest |

## Hooks (auto-configured in `.claude/settings.json`)

- **SessionStart** → `session-start.sh` → rebuilds context pack
- **UserPromptSubmit** → `userprompt-submit.sh` → **스킬 자동 추천** (skill-rules.json 기반 매칭 → additionalContext 주입)
- **PostToolUse** → `post-tool-use.sh` → 편집된 파일 경로를 `_edited_files.log`에 추적
- **Stop** → `stop.sh` → **NoMessLeftBehind 검증** (편집 이력 있을 때만: compileall + smoke_test + context_pack 갱신)

## Skill Auto-Suggestion

`UserPromptSubmit` 훅이 `.claude/skill-rules.json`의 규칙과 프롬프트를 매칭하여 관련 스킬을 자동 추천한다.
현재 등록된 스킬: **recipe-authoring**, **colab-debugging**, **notebook-builder**.

## NoMessLeftBehind (diet103-lite)

Stop 훅에서 `_edited_files.log`를 확인하여, 편집된 파일이 있을 때만:
1. `python -m compileall .` — 문법 검증
2. `scripts/smoke_test.py` — 임포트/컴파일 체크
3. `scripts/make_context_pack.py` — 컨텍스트 팩 갱신

포맷터(`ruff format` / `black`)는 자동 실행하지 않고 권장만 출력한다.

## Sub-Agents (`.claude/agents/`)

| Agent | Role | Auto-delegate when |
|-------|------|--------------------|
| `code-reviewer` | 코드 리뷰, 일관성 검증 | 코드 완성 후 커밋 전, "review" 요청 시 |
| `compat-debugger` | 설치/패키지 충돌 해결 | pip 실패, ImportError, Colab 호환성 문제 시 |
| `plan-architect` | SSOT docs 생성/관리 | 새 레시피 시작, 아키텍처 결정 필요 시 |

## Adding a New Recipe

```bash
cp -r recipes/_template recipes/<new-name>
echo "<new-name>" > .claude/last_recipe.txt
# Then edit recipes/<new-name>/docs/plan.md to define the goal
```

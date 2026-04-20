---
name: fresh-start
description: Use when context window is getting full (proactive at ~60% per Chroma context-rot research), user says "/compact 대신", mentions "맥락 오염", "context pollution", "fresh start", "clean slate", or Claude has been corrected ≥2× on the same issue. Saves in-progress state to .claude/_resume_state.md (based on git diff, not tasks.md speculation), rebuilds context pack, then instructs user to run /clear. Prefer this over /compact — GH anthropics/claude-code #46602 documents compact summarizer hallucinating fabricated user directives.
allowed-tools: Read, Edit, Write, Bash
---

# Skill: fresh-start

## When to Use (priority order)
1. Context usage crosses ~40-60% (proactive per Chroma context-rot research — degradation starts well before full).
2. Claude has been corrected ≥2× on the same bug in one session (context is polluted).
3. Switching from one recipe/task to an unrelated one.
4. `/compact` has already fired once and you see model drift — do NOT re-compact.

### Lighter alternatives — try these FIRST
- `Esc+Esc` / `/rewind` — Claude Code built-in checkpoint restore. Cheapest if only the last few turns went bad.
- `claude --continue` / `claude --resume <id>` — cross-session pickup without losing the JSONL transcript.

Use this skill only when the lighter options can't undo enough context damage.

## Why /clear > /compact
- `/compact`: LLM-summarizes the conversation. Documented to hallucinate fabricated directives (GH anthropics/claude-code #46602 — a fabricated "keep working until nothing left" summary once drove 44 unwanted URL fetches). Lossy + unverifiable.
- `/clear` + SSOT reload: only files the user controls survive. Lossless for committed decisions; everything else must be made durable BEFORE /clear.

## Steps

### 1. Save in-progress context to files
현재 conversation 중 아직 파일에 없는 것들을 저장:

```bash
RECIPE=$(cat .claude/last_recipe.txt 2>/dev/null | tr -d '[:space:]')
RECIPE=${RECIPE:-_template}
[ -d "recipes/$RECIPE/docs" ] || echo "WARN: recipes/$RECIPE/docs/ missing — _resume_state.md will be the SOLE surviving context"
```

- `recipes/$RECIPE/docs/context.md` → Key Decisions, Discovered Issues 추가
- `recipes/$RECIPE/docs/tasks.md` → 완료 항목 `[x]`, 새 항목 추가
- Memory files → 세션에서 얻은 안정적 패턴/인사이트 (session-end 스킬의 §5 참조)

### 1.5. (MCP only) Save live-Colab state BEFORE wiping context
If `recipes/$RECIPE/recipe.yaml:mcp.enabled: true` and a live Colab tab is open:
1. Call `mcp__colab-mcp__get_cells(0, <count>)` once — PostToolUse hook auto-snapshots `latest-cells.json` + timestamped `cells_<ts>_<ns>.json`.
2. Run `/colab-mcp-sync <recipe>` — promote MCP cell edits into `notebook_manifest.yaml` BEFORE /clear. Skipping this caused ~90 min + 48 GB of lost work on flux2-klein-4b (2026-04-20).
3. Record the Gradio share URL / runtime indicator in `_resume_state.md §Notes` so the next session can tell whether to reconnect or cold-start.
4. Do NOT close the Colab tab — `/clear` only wipes Claude context, not the Colab runtime. Keep the tab so the next session can reconnect.

### 2. Analyze uncommitted changes (CRITICAL)
Run `git diff --stat` + `git status --short`. **Uncommitted changes are the strongest signal of current work** — they outrank `tasks.md` speculation.

### 3. Write resume state with a Recipe header
`.claude/_resume_state.md` 첫 줄에 recipe 헤더 필수 (staleness 감지용):

```markdown
Recipe: {active-recipe-name}
Saved: {ISO 8601 UTC}
Branch: {git-branch}

## Uncommitted Changes (진행 중 작업의 근거)
- [git diff에서 파악한 수정/삭제/추가 파일 목록]
- [각 변경이 무엇을 위한 것인지 한줄 설명]

## Current Work
- [uncommitted changes 기반으로 실제 진행 중인 작업]

## Next Steps
- [현재 작업의 남은 부분 → 그 다음 tasks.md 미완료 항목]

## Key Files
- [작업 중인 파일 경로들]

## Notes
- [clear 후 알아야 할 주의사항, MCP 상태, 외부 리소스 URL 등]
```

**규칙**: "Current Work"는 `git diff`가 보여주는 실제 작업. 추측 금지.

### 4. Rebuild context pack
```bash
command -v uv >/dev/null && uv run python scripts/make_context_pack.py \
  || echo "WARN: uv not found — context pack not regenerated. _resume_state.md still written."
```

`make_context_pack.py`가 `_resume_state.md`를 `.claude/CLAUDE.md`에 inline 복사한다. `Recipe:` 헤더가 현재 `last_recipe.txt`와 다르면 자동 stale 감지 + 로드 거부 (recipe 스위치 이후 이전 상태 주입으로 인한 환각 방지).

### 5. Instruct user
다음 안내 출력:

```
준비 완료. 아래를 실행하세요:
  /clear
그 후 아무 요청만 하면 됩니다 (예: "이어서 작업해줘").
SSOT 문서 + resume state가 .claude/CLAUDE.md 통해 자동 로드됩니다.
```

## After /clear — what actually survives
1. User runs `/clear`
2. `SessionEnd` hook fires → `.claude/_resume_state.md` **is deleted** (by design — `session-end.sh`).
3. But its content has **already been inlined into `.claude/CLAUDE.md`** by Step 4's `make_context_pack.py`, so nothing is lost.
4. `SessionStart` hook rebuilds `.claude/CLAUDE.md` again (this time without `_resume_state.md` since it's gone) — Recipe Docs + Uncommitted Changes section still present.
5. Claude Code auto-loads `.claude/CLAUDE.md` every session.
6. User says "이어서 해줘" → Claude reads the pack.

Single-channel survival. No `UserPromptSubmit` second-injection any more (removed 2026-04-20 — was burning tokens on the duplicate and creating "two sources" reconciliation risk).

## Constraints (honest)
- Only what you wrote to files survives. Mid-session reasoning, rejected approaches, and debug narratives that never hit `context.md` ARE lost. This is an improvement on `/compact` (which hallucinates per GH #46602) but NOT a silver bullet. Write decisions to `context.md` during the session, not only at `/fresh-start` time.
- `_resume_state.md` is `.gitignored` (.gitignore:19) — never `git add` it.
- Keep `_resume_state.md` ≤40 lines — matches `make_context_pack.py:read_file_safe(..., max_lines=40)` truncation.
- Windows Git Bash: verify `where bash` puts Git Bash first; WSL stub breaks Step 4 (see root CLAUDE.md §Windows bash.exe hazard).

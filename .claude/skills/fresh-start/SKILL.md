# Skill: fresh-start

## When to Use
Context window가 커졌을 때 `/compact` 대신 사용. `/fresh-start`로 호출.
compact는 반복할수록 맥락이 오염되므로 (lossy summary 누적), clean slate + SSOT 재읽기가 더 안정적.

## Why /clear > /compact
- `/compact`: 요약이 반복될수록 불확실한 맥락 누적 → 예측 불가능한 동작
- `/clear` + SSOT 재읽기: 파일에 저장된 확실한 맥락만 사용 → 항상 예측 가능

## Steps

### 1. Save current context to files
현재 conversation에서 아직 파일에 반영 안 된 것들을 저장:

```bash
RECIPE=$(cat .claude/last_recipe.txt)
```

- `recipes/$RECIPE/docs/context.md` → Key Decisions, Discovered Issues 추가
- `recipes/$RECIPE/docs/tasks.md` → 완료 항목 `[x]` 체크, 새 항목 추가
- Memory files → 세션에서 얻은 안정적 패턴/인사이트

### 2. Analyze uncommitted changes (CRITICAL)
`git diff --stat`과 `git status`를 반드시 실행하여 현재 실제로 수정 중인 파일을 파악한다.
**uncommitted 변경이 resume state의 가장 강력한 신호** — tasks.md보다 우선.

### 3. Write resume state
`.claude/_resume_state.md`에 현재 작업 상태를 저장 (context pack에 자동 포함됨):

```markdown
## Uncommitted Changes (진행 중인 작업의 근거)
- [git diff에서 파악한 수정/삭제/추가 파일 목록]
- [각 변경이 무엇을 위한 것인지 한줄 설명]

## Current Work
- [uncommitted changes 기반으로 실제 진행 중인 작업 설명]
- [recipe 작업인지, 인프라 작업인지, 정리 작업인지 명확히]

## Next Steps
- [현재 작업의 남은 부분]
- [그 다음 tasks.md 미완료 항목]

## Key Files
- [작업 중인 파일 경로들]

## Notes
- [clear 후 알아야 할 주의사항]
- [어떤 브랜치/리모트에서 작업 중인지]
```

**규칙**: "Current Work"는 반드시 uncommitted changes와 일치해야 함.
tasks.md의 다음 항목이 아니라, git diff가 보여주는 실제 작업을 기술할 것.

이 파일은 `make_context_pack.py`가 `.claude/CLAUDE.md`에 포함시킨다.
`.claude/CLAUDE.md`는 Claude Code가 자동 로드하므로 `/clear` 후 즉시 resume state를 인식한다.
추가로 UserPromptSubmit hook이 첫 프롬프트에 resume state를 additionalContext로 주입한다.

### 4. Rebuild context pack
```bash
uv run python scripts/make_context_pack.py
```
이 시점에서 _context_pack.md에 SSOT docs + resume state가 모두 포함됨.

### 5. Instruct user
다음 안내를 출력:

```
준비 완료. 아래를 실행하세요:
  /clear
그 후 아무 작업 요청만 하면 됩니다 (예: "이어서 작업해줘").
SSOT 문서와 resume state가 자동으로 로드됩니다.
```

## After /clear Flow
1. 사용자가 `/clear` 실행
2. SessionStart hook → `make_context_pack.py` → `.claude/CLAUDE.md` 재생성
3. `.claude/CLAUDE.md`는 Claude Code가 자동 로드 (resume state 포함)
4. UserPromptSubmit hook도 `_resume_state.md` 내용을 additionalContext로 주입 (이중 안전장치)
5. CLAUDE.md "Session Resume" 규칙 → Claude가 resume state를 최우선으로 읽음
6. 사용자가 "이어서 해줘" 한마디면 작업 재개

## Constraints
- 파일에 반영 안 된 중요 맥락이 있으면 반드시 저장 후 clear 안내
- `_resume_state.md`는 간결하게 (30줄 이내) — context pack 크기 제한
- compact와 달리 유실 걱정 없음 — 모든 맥락이 파일에 영속화됨

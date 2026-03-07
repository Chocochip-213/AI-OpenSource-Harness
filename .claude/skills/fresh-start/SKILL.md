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

### 2. Rebuild context pack
```bash
uv run python scripts/make_context_pack.py
```

### 3. Generate resume prompt
`/clear` 후 붙여넣을 프롬프트를 코드 블록으로 출력:

```
## Resume Prompt (paste after /clear)

레시피 `$RECIPE` 작업 이어서 진행.

### 현재 상태
- [무엇이 동작하는지]
- [무엇이 안 되는지]

### 다음 작업
- [tasks.md에서 다음 미완료 항목]

### 핵심 파일
- [작업 중인 파일 경로들]

먼저 `recipes/$RECIPE/docs/{plan,context,tasks}.md`를 읽고 현재 상태를 파악한 후 다음 작업을 진행해줘.
```

### 4. Instruct user
다음 안내를 출력:

```
위 프롬프트를 복사한 후:
1. /clear 실행
2. 복사한 프롬프트 붙여넣기
3. Claude가 SSOT 문서를 읽고 작업 재개
```

## Constraints
- 파일에 반영 안 된 중요 맥락이 있으면 반드시 저장 후 clear 안내
- resume 프롬프트에 "먼저 docs를 읽어라"를 반드시 포함 (Claude가 SSOT부터 읽도록)
- compact와 달리 유실 걱정 없음 — 모든 맥락이 파일에 영속화됨

# Skill: session-end

## When to Use
Session 마무리 시. 다른 컴퓨터/세션으로 작업을 넘길 때. `/session-end`로 호출.

## Steps (execute in order)

### 1. Read active recipe docs
```bash
RECIPE=$(cat .claude/last_recipe.txt)
```
Read `recipes/$RECIPE/docs/{plan,context,tasks}.md`

### 2. Analyze this session
- 이번 세션에서 완료한 작업
- 내린 결정과 그 이유
- 발생한 에러와 해결책

### 3. Update context.md
- "Key Decisions"에 새 결정 추가 (이유 포함)
- "Discovered Issues"에 새 이슈 추가

### 4. Update tasks.md
- 완료 항목 체크오프 `[x]`
- 세션 중 발견된 새 항목 추가

### 5. Update memory files
Auto-memory directory에 프로젝트 학습 저장:
- `MEMORY.md` — 프로젝트 전체 상태 요약 (200줄 이내)
- 토픽별 파일 필요 시 생성

### 6. Rebuild context pack
```bash
uv run python scripts/make_context_pack.py
```

### 7. Git commit + push
```bash
git add -A && git commit -m "docs: session-end — [요약]"
git push origin HEAD
```

### 8. Generate handoff prompt
코드 블록으로 출력:
```
프로젝트: [프로젝트명]  |  브랜치: [브랜치명]  |  레시피: [레시피명]

### 이전 세션 완료 사항
- [bullet points]

### 현재 상태
- [동작하는 것 / 안 되는 것 / 대기 중]

### 다음 작업
- [bullet points]

### 핵심 파일
- [path: description]

### 주의사항
- [있으면 기술]
```

## Constraints
- 커밋 전 `uv run python scripts/smoke_test.py` 통과 확인
- 민감 파일(.env 등) 커밋 금지
- 핸드오프 프롬프트는 새 세션에서 즉시 작업 재개 가능할 수준으로

---
name: pre-compact
description: Use when the user anticipates /compact (manual or auto), says "compact 전에", "맥락 정리", "context almost full", "pre-compact", or auto-compact is imminent. Persists critical context (decisions, error-fix pairs, in-progress state) to SSOT docs and memory files BEFORE compaction lossy-summarizes them. Then generates a recommended /compact summary. NOTE: For long-running sessions, prefer /fresh-start over /compact — file-based recovery has no pollution risk. This skill exists as a fallback when compaction is unavoidable.
allowed-tools: Read Edit Write Bash
---

# Skill: pre-compact

## When to Use
Context window가 거의 가득 찼을 때 (auto-compact 전에 수동 실행). `/pre-compact`로 호출.

## Purpose
Auto-compact는 중요한 맥락을 누락할 수 있다.
이 스킬은 compact 전에 중요 맥락을 영속 파일에 저장하고,
수동 `/compact`를 위한 최적 요약을 제안한다.

## Steps

### 1. Identify critical context
현재 conversation에서 식별:
- 현재 진행 중인 작업 상태
- 이번 세션 결정과 이유
- 에러 패턴과 해결책 (재현 비용 높은 정보)
- 작업 중인 파일 경로
- 아직 파일에 반영 안 된 임시 상태

### 2. Persist to files
```bash
RECIPE=$(cat .claude/last_recipe.txt)
```
- `recipes/$RECIPE/docs/context.md` — 미반영 결정/이슈
- `recipes/$RECIPE/docs/tasks.md` — 현재 진행도
- Memory files — 디버깅 인사이트, 안정 패턴

### 3. Present to user
```
## Pre-Compact Report

### Files에 저장 완료 (compact 후 안전)
- context.md: [추가 내용]
- tasks.md: [업데이트 내용]

### Conversation에만 존재하는 중요 맥락
- [유실 가능 정보]

### Recommended compact command
```

### 4. Generate compact summary
`/compact` 에 넣을 한 문단 요약:
- 현재 작업과 접근 방식
- 핵심 파일 경로
- 최근 에러/해결책
- 다음 단계

## Constraints
- 이 스킬 자체가 context를 많이 소모하면 안 됨 — 간결하게
- compact summary는 한 문단 이내

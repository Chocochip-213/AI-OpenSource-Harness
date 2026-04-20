---
name: session-end
description: Use when the user wraps up work for the day, wants to hand off to another machine or session, says "session end", "세션 마무리", "오늘 끝", "다른 컴퓨터로 넘기기", "handoff". Updates SSOT docs (context.md decisions, tasks.md checkoffs), refreshes memory files, rebuilds context pack, commits with explicit paths (never git add -A — sensitive file leak risk), then generates a handoff prompt. Requires user confirmation before git push.
allowed-tools: Read Edit Write Bash
---

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

### 4.5. (MCP only) Close out the live Colab session
If this session used `/colab-mcp`:
1. Confirm the Colab browser tab is still connected (if not, edits cannot be synced).
2. Run `/colab-mcp-sync <recipe>` — diffs live notebook against
   `notebook_manifest.yaml` and asks for confirmation before applying.
3. Regenerate the notebook to verify the sync was clean:
   `uv run python tools/generate_notebook.py <recipe>`.
4. Close the Colab tab so the MCP server shuts its WebSocket cleanly
   (idle disconnect also works but leaves a dangling session id).
5. Review `.claude/_hook_errors.log` for any `output over budget` warnings
   from the session and decide whether to bump `mcp.max_tool_output_tokens`.

Skipping this step is the #1 cause of the Ever-era "Cell X fix 20 commits"
drift — MCP edits that never make it into the manifest get silently overwritten
on the next `generate_notebook.py` run.

### 5. Update memory files
Auto-memory directory에 프로젝트 학습 저장:
- `MEMORY.md` — 프로젝트 전체 상태 요약 (200줄 이내)
- 토픽별 파일 필요 시 생성

### 6. Rebuild context pack
```bash
uv run python scripts/make_context_pack.py
```

### 7. Git commit + push (SECURITY: explicit paths only)

**절대 `git add -A` 또는 `git add .` 금지** — 민감 파일(`.env`, API 키, 토큰) 실수 커밋 방지.
CVE-2025-59536(`.claude/settings.json` RCE)을 포함해 repo-wide staging은 공격 벡터.

```bash
# (a) 변경 내용 검증 — untracked 포함
git status

# (b) 명시 경로로만 add (프로젝트 구조에 맞게 조정)
git add recipes/ docs/ scripts/ tools/ \
        .claude/skills/ .claude/agents/ .claude/settings.json .claude/skill-rules.json \
        colab-runtimes/ CLAUDE.md README.md .gitignore

# (c) staged 결과 다시 확인 — 의도치 않은 파일 있는지
git diff --cached --stat
git diff --cached --name-only

# (d) 민감 파일 자동 스캔 (fail-safe)
if git diff --cached --name-only | grep -Ei '\.(env|pem|key)$|credentials|secret|token'; then
  echo "FATAL: staged a suspicious file. Unstage with: git reset HEAD <path>"
  exit 1
fi

# (e) 커밋
git commit -m "docs: session-end — [요약]"
```

**Push는 반드시 사용자 확인 후**:
```bash
# 사용자에게 보여주고 승인 받은 후에만:
git push origin HEAD
```
새 브랜치면 `-u origin <branch>` 명시. `git push --force`는 절대 금지.

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
- **`git add -A` / `git add .` 절대 금지** — 민감 파일 실수 커밋 방지 (Step 7 참조)
- push 전 사용자 명시 확인
- `git push --force` 금지 (published commits는 amend 금지, 새 commit 생성)
- 핸드오프 프롬프트는 새 세션에서 즉시 작업 재개 가능할 수준으로
- 코드 블록(triple backticks)으로 감싸서 출력 — 사용자가 바로 복사 가능해야 함

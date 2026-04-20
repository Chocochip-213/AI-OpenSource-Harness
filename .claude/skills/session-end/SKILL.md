---
name: session-end
description: Use when the user wraps up work for the day, wants to hand off to another machine or session, says "session end", "세션 마무리", "오늘 끝", "다른 컴퓨터로 넘기기", "handoff". Updates SSOT docs (context.md decisions, tasks.md checkoffs), refreshes memory files, rebuilds context pack, commits with explicit paths (never git add -A — sensitive file leak risk), then generates a handoff prompt. Requires user confirmation before git push.
allowed-tools: Read, Edit, Write, Bash
---

# Skill: session-end

## When to Use
Session 마무리 / 다른 컴퓨터로 넘기기 / "handoff" 요청 시.

## Steps (execute in order)

### 1. Read active recipe docs
```bash
RECIPE=$(cat .claude/last_recipe.txt 2>/dev/null | tr -d '[:space:]')
RECIPE=${RECIPE:-_template}
```
Read `recipes/$RECIPE/docs/{plan,context,tasks}.md`.

### 2. Analyze this session
- 이번 세션 완료 작업
- 내린 결정 + 이유
- 발생 에러 + 해결책

### 3. Update context.md
- "Key Decisions" 새 결정 (이유 포함)
- "Discovered Issues" 새 이슈

### 4. Update tasks.md
- 완료 항목 `[x]` 체크
- 세션 중 발견된 새 항목 추가

### 4.5. (MCP only) Close out the live Colab session
If `recipe.yaml:mcp.enabled: true` and a live Colab tab is connected:
1. Run `/colab-mcp-sync <recipe>` — diff live vs manifest, apply with confirmation.
2. Regenerate: `uv run python tools/generate_notebook.py <recipe>`.
3. Close the Colab tab (clean WebSocket shutdown).
4. `rm -f .claude/_mcp_session.txt .claude/_mcp_session_*.txt` so next session starts with a clean session id.
5. Review `.claude/_hook_errors.log` for `output over budget` warnings → decide whether to bump `mcp.max_tool_output_tokens`.

Skipping this is the #1 cause of Ever-era "Cell X fix 20 commits" drift.

### 5. Update memory files
Auto-memory at `~/.claude/projects/<derived>/memory/` per Anthropic spec:
- `MEMORY.md` = 인덱스만 (200줄 OR 25KB 먼저 도달하는 것까지 — Anthropic 공식 auto-load 한도)
- 상세 내용은 토픽 파일 (`feedback_*.md`, `user_*.md`, `project_*.md`, `reference_*.md`) — 길이 제한 없음, on-demand 로드

### 6. Rebuild context pack
```bash
uv run python scripts/make_context_pack.py
```

### 6.5. (If this session edited harness files) Pass code-reviewer gate
If you edited `CLAUDE.md` / `.claude/{hooks,skills,agents,settings.json}` / `.mcp.json` / `tools/` / `scripts/` / `docs/*.md` / `recipes/_template/` / `.github/` / `.gitattributes` this session, `commit_gate.sh` will block `git commit`. Run:

```
Agent(subagent_type="code-reviewer")
```

After verdict, write `.claude/_code_review_passed.json`:
```json
{"timestamp": "<iso>", "agent_id": "<id>", "verdict": "ready", "files_reviewed": [...]}
```

Then `touch .claude/_code_review_passed.json` to refresh mtime > staged files.

### 7. Git commit + push (SECURITY: explicit paths only)

**절대 `git add -A` 또는 `git add .` 금지** — 민감 파일(`.env`, 토큰) 실수 커밋 방지.

```bash
# (a) 상태 확인
git status
BRANCH=$(git rev-parse --abbrev-ref HEAD)

# (b) 브랜치 안전 가드 — 통합 브랜치 직접 push 금지
case "$BRANCH" in
  master|main|develop|AI/develop|BE/develop|FE/develop)
    echo "WARN: $BRANCH is a shared integration branch. Session-end commits should go to a feature branch."
    ;;
esac

# (c) 명시 경로 add
git add recipes/ docs/ scripts/ tools/ \
        .claude/skills/ .claude/agents/ .claude/hooks/ \
        .claude/settings.json .claude/skill-rules.json \
        .mcp.json .github/ .gitattributes \
        colab-runtimes/ CLAUDE.md README.md .gitignore

# (d) 무시해야 할 backup 파일 자동 언스테이지
git reset HEAD $(git diff --cached --name-only 2>/dev/null | grep -E '\.bak$|\.sync-.*\.bak$') 2>/dev/null || true

# (e) staged 재확인
git diff --cached --stat
git diff --cached --name-only

# (f) 민감 파일 스캔 (확장된 regex)
if git diff --cached --name-only | grep -Ei '\.(env|pem|key|p12|pfx|jks|keystore|crt)($|\.)|credentials|secret|token|service-account|\.env\.(local|production|development)'; then
  echo "FATAL: staged a suspicious file. Unstage with: git reset HEAD <path>"
  exit 1
fi
# 2026 권장: gitleaks도 있으면 같이
if command -v gitleaks >/dev/null 2>&1; then
  gitleaks protect --staged --no-banner || { echo "FATAL: gitleaks flagged staged content"; exit 1; }
fi

# (g) 커밋 (SSAFY 모노레포 모드면 Korean 14-prefix — docs/SSAFY_CONVENTIONS.md 참조)
if [ -d ../front ] && [ -d ../back ]; then
  # SSAFY: feat:/fix:/docs:/chore: 14-prefix, 한국어 50자, 마침표 없음
  git commit -m "docs: 세션 마무리 — [한 줄 요약]"
else
  git commit -m "docs: session-end — [one-line summary]"
fi
```

Push는 **사용자 확인 후**:
```bash
git push origin HEAD   # 새 브랜치면 -u origin <branch>
```

`git push --force` 금지. 사용자가 Yes 안 했으면 push 안 함.

### 8. Generate handoff prompt
채팅에 출력 + `.claude/handoffs/YYYY-MM-DD-HHMM.md`에도 저장 (로 컴파일 후에도 유지):

```
프로젝트: [프로젝트명]  |  브랜치: [브랜치명]  |  레시피: [레시피명]
HEAD: [git rev-parse --short HEAD]
브랜치 상태: [git status -sb 첫 줄 — ahead/behind]
Uncommitted: [git status --porcelain 요약 (있으면 경고)]

### 이전 세션 완료 사항
- [bullet points]

### 현재 상태
- [동작하는 것 / 안 되는 것 / 대기 중]

### 다음 작업
- [bullet points]

### 핵심 파일
- [path: description]

### 주의사항 (Do Not Touch)
- [사용자가 이미 거절한 접근, memory/feedback_*.md 기반]
- [환각 유발 패턴이 있다면 기록]

### MCP 상태
- _mcp_session*.txt: [존재 / 정리됨]
- Colab 탭: [닫힘 / 대기 중]
```

## Constraints
- Stop 훅이 smoke_test 자동 실행 — 실패 시 커밋 전에 surface됨 (redundant check 불필요)
- **`git add -A` / `git add .` 절대 금지** — 민감 파일 실수 커밋 방지
- push 전 사용자 명시 확인
- `git push --force` 금지 (published commits는 amend 금지, 새 commit 생성)
- 핸드오프 프롬프트는 새 세션/새 machine에서 즉시 재개 가능할 수준 — git SHA + branch state 필수
- 코드 블록(triple backticks)으로 감싸서 출력 + `.claude/handoffs/`에 파일로도 저장

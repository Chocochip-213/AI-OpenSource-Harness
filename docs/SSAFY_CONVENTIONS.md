# SSAFY 6인 팀 — Commit / Branch / 통합 컨벤션

> 이 문서는 이 하네스가 **SSAFY monorepo (`<repo>/ai/`)에 들어갔을 때**
> Claude Code(이 AI 도구) 본인이 따라야 할 룰을 명시한다. 별도 OSS
> 저장소 시점의 commit history는 영어 Conventional이지만, monorepo
> 안에서는 무조건 아래 SSAFY 룰을 따른다.

---

## 1. Commit 메시지 컨벤션

### 1.1 Prefix 14개 (영어 소문자)

| prefix | 의미 |
|---|---|
| `feat` | 새 기능 |
| `fix` | 버그 수정 |
| `docs` | 문서 |
| `style` | 포매팅·세미콜론 등 코드 동작 변경 없음 |
| `refactor` | 리팩토링 |
| `test` | 테스트 코드 |
| `chore` | 패키지/잡일 (e.g. `.gitignore`) |
| `design` | UI/CSS 디자인 |
| `comment` | 주석 추가/변경 |
| `rename` | 파일/폴더명 변경만 |
| `remove` | 파일 삭제만 |
| `breaking change` | 큰 API 변경 |
| `hotfix` | 치명적 긴급 수정 |
| `setting` | 기본 세팅 |

### 1.2 형식 규칙
- 제목: `<prefix>: <한국어 요약>` (영문 50자 이내, 끝 `.` 금지)
- 빈 줄 후 본문 (선택) — **무엇을 + 왜** (어떻게는 코드가 말한다)
- 본문 여러 항목은 `- ` 글머리 기호
- **한 commit = 한 가지 문제** (추적성)

### 1.3 예시
```
feat: AI Gradio 엔드포인트 스펙 export 추가

- recipes/<name>/exports/gradio_api.schema.json 자동 생성
- backend 팀이 RestTemplate 클라이언트 자동 생성 가능
- INTEGRATION_BACKEND.md에 사용법 명시
```

### 1.4 CLI multi-line
```bash
git commit -m "feat: 회원가입 기능 추가

- 회원가입 API 연동
- 입력 검증 추가"
```

---

## 2. Branch 컨벤션

### 2.1 형식
```
<type>/<be|fe|ai>/<S14P11A607-N>-<짧은-설명>
```
- `<type>`: `feature` | `fix` | `hotfix`
- `<be|fe|ai>`: 도메인 — Spring 백엔드 / Next.js 프론트엔드 / **AI는 `ai`**
- `<S14P11A607-N>`: JIRA 티켓
- `<짧은-설명>`: 영어 소문자 + 하이픈

### 2.2 AI 작업 예시
```
feature/ai/S14P11A607-44-trellis-recipe
fix/ai/S14P11A607-78-gradio-url-refresh
hotfix/ai/S14P11A607-91-mcp-monitor-crash
```

### 2.3 도메인별 develop 브랜치
- `FE/develop`, `BE/develop`, `AI/develop`
- feature 브랜치 → 본인 도메인 develop으로 PR
- 도메인 develop → `develop` (통합) → `main`

---

## 3. AI 작업 표준 SOP (이 하네스 사용 시)

### 3.1 새 작업 시작
```bash
cd <S14P11A607>/ai           # 항상 ai/ 폴더 안에서 claude 실행
git checkout AI/develop
git pull
# JIRA에서 태스크 생성, 티켓 번호 받기 (예: S14P11A607-44)
git checkout -b feature/ai/S14P11A607-44-<설명>
scripts/set_active_recipe.sh <recipe-name>
source .claude/.env
claude
```

### 3.2 작업 중
- recipe SSOT 문서 (plan/context/tasks) 작성·업데이트
- `notebook_manifest.yaml` 편집
- 필요 시 MCP로 Colab에서 라이브 iteration (`/colab-mcp`)
- 변경 후 `tasks.md` 즉시 체크오프

### 3.3 작업 완료
```bash
uv run python tools/generate_notebook.py <recipe>
uv run python tools/generate_export.py <recipe>   # backend/frontend 팀 산출물
uv run python scripts/smoke_test.py
git add ai/recipes/<recipe>/ ai/outputs/notebooks/<recipe>.ipynb   # 명시 경로만
git commit -m "feat: <recipe> 모델 포팅 + Gradio 엔드포인트 export

- ...
- ..."
git push origin feature/ai/S14P11A607-44-<설명>
# GitLab UI에서 PR 생성 → AI/develop 으로
```

---

## 4. SSAFY monorepo 안에서 이 하네스 위치 가정

```
S14P11A607/                       ← 팀 monorepo 루트 (GitLab)
├── front/                        ← Next.js (FE 팀 2명)
├── back/                         ← Spring (BE 팀 2명)
├── ai/                           ← **이 하네스 통째 cp -r**
│   ├── .claude/                  (Claude Code는 ai/ 안에서 실행해야 인식)
│   ├── .mcp.json
│   ├── recipes/<name>/
│   │   └── exports/              ← backend·frontend 팀이 가져갈 산출물
│   ├── tools/
│   ├── scripts/
│   └── ...
├── docs/                         ← 팀 공유 문서
└── README.md
```

**중요**: Claude Code는 반드시 `cd ai/` 후 `claude`로 실행. 그래야
`.claude/`, `.mcp.json`, hook들이 인식됨. monorepo 루트에서 실행하면 동작 안 함.

---

## 5. 주요 차이점 (이 하네스 OSS 시점 vs SSAFY 시점)

| 항목 | OSS 시점 (현재) | SSAFY 시점 (`<repo>/ai/` 안) |
|------|----------------|----------------------------|
| Commit | 영어 Conventional Commits | 한국어 + 14 prefix |
| Branch | `master` 단일 | `feature/ai/S14P11A607-N-...` |
| PR 대상 | (없음) | GitLab MR → `AI/develop` |
| CI | GitHub Actions | GitLab CI (`.gitlab-ci.yml`, `paths: ['ai/**']` 필터) |
| CODEOWNERS | `.github/CODEOWNERS` (이 repo) | monorepo 루트의 `.github/CODEOWNERS` 또는 `CODEOWNERS`에 `ai/` 경로 등록 |
| Secret/env | `.claude/.env`, `.claude/settings.local.json` (gitignored) | 같음. JIRA·GitLab token은 `.claude/settings.local.json` |

---

## 6. Claude Code 자체 룰 (Claude가 따라야 할 것)

이 하네스가 SSAFY monorepo 안에 있을 때, Claude는:

1. **모든 commit message를 한국어 SSAFY 컨벤션으로** 작성
2. **branch 이름은 `feature/ai/S14P11A607-N-<설명>`** 형식 — JIRA 티켓 번호 모르면 사용자에게 물어봄
3. **`git add -A` 절대 금지** (`session-end` skill 룰 그대로 적용)
4. **PR push는 사용자 명시 승인 후만**
5. **monorepo 루트 (`<repo>`)는 건드리지 않음** — `ai/` 내부에서만 작업
6. **다른 도메인 (`front/`, `back/`) 직접 수정해야 할 때만** 별도 branch 만들고 (`feature/be/S14P11A607-N-...`) 사용자 confirm 받은 후

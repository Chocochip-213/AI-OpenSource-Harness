# AI OpenSource Harness

[한국어](#한국어) | [English](#english)

---

# 한국어

AI 오픈소스 모델을 Google Colab에서 실행하기 위한 Claude Code 기반 자동화 하네스입니다.

## 이게 뭔가요?

GitHub에서 흥미로운 AI 오픈소스 모델을 발견했을 때, Colab에서 돌리려면 이런 문제들을 해결해야 합니다:
- Colab 기본 패키지와의 의존성 충돌 (numpy, Pillow 등 C extension)
- CUDA/GPU 호환성 (Blackwell, A100, T4 각각 다른 torch 버전 필요)
- 네이티브 C 확장 빌드 실패 (nvdiffrast, CuMesh 등)
- 환경 제약 (런타임 초기화, 디스크 제한, 세션 타임아웃)

이 하네스는 그 과정을 구조화하고 자동화합니다:
- **레시피 시스템** — 모델별 포팅 프로젝트를 체계적으로 관리 (SSOT 문서 3종)
- **노트북 생성기** — YAML 매니페스트 → Colab `.ipynb` 자동 생성 (GPU preflight / Gradio serve 자동 주입)
- **Claude Code 훅** — 자동 검증, 스킬 추천, 맥락 관리, `/clear` 후 자동 복구
- **Colab 런타임 추적** — Colab 런타임별 패키지 버전 자동 수집 및 비교
- **Live Colab 이터레이션** — `colab-mcp` 통합으로 노트북 재업로드 없이 브라우저 런타임을 직접 제어 (opt-in per recipe)
- **Exports 계약** — Spring/Next.js 팀이 recipe의 `exports/`에서 바로 가져갈 수 있는 타입 안전한 통합 문서 + JSON Schema + 핸들러

## 빠른 시작

### 사전 요구사항

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) 설치
- [uv](https://docs.astral.sh/uv/) (Python 패키지 매니저)
- Git

### 1. 클론

```bash
git clone https://github.com/Chocochip-213/AI-OpenSource-Harness.git
cd AI-OpenSource-Harness
```

### 2. Claude Code 시작

```bash
claude
```

첫 세션 시작 시 훅이 자동 설정됩니다:
```
[hook:session-start] Context pack ready
```

### 3. 레시피 만들기

```bash
cp -r recipes/_template recipes/my-model
scripts/set_active_recipe.sh my-model     # writes .claude/last_recipe.txt + .claude/.env, rebuilds context pack
```

그리고 Claude에게: **"recipes/my-model/docs/plan.md를 편집해줘. [모델명]을 Colab에서 돌리고 싶어."**

### 4. 노트북 생성

`recipes/my-model/notebook_manifest.yaml` 편집 후:

```bash
uv run python tools/generate_notebook.py my-model
# -> outputs/notebooks/my-model.ipynb
```

Colab에 업로드하고 테스트!

## 프로젝트 구조

```
AI-OpenSource-Harness/
├── .claude/                       # Claude Code 인프라
│   ├── hooks/                     # 라이프사이클 훅 (8개 이벤트 + 보조 스크립트)
│   ├── skills/                    # 슬래시 명령 정의 (8개)
│   ├── agents/                    # 서브에이전트 정의 (3개)
│   ├── settings.json              # 훅 설정 (CODEOWNERS-보호)
│   ├── settings.local.json        # 로컬 오버라이드 (gitignored)
│   └── skill-rules.json           # 하네스 고유: 스킬 매칭 키워드 힌트
├── .mcp.json                      # colab-mcp 서버 등록 (opt-in, CODEOWNERS-보호)
├── .github/
│   ├── CODEOWNERS                 # .mcp.json / settings.json / hooks 병합 리뷰 강제
│   └── workflows/
│       └── sync-colab-runtimes.yml # 일일 자동 동기화
├── .gitattributes                 # 공유 파일 병합 전략 (union / ours)
├── recipes/
│   └── _template/                 # 새 레시피의 기본 템플릿
│       ├── docs/                  # SSOT 문서 3종
│       │   ├── plan.md            # 목표, 범위, 접근법
│       │   ├── context.md         # 아키텍처, 의사결정, Colab 호환성
│       │   └── tasks.md           # 체크리스트
│       ├── exports/               # BE/FE 통합 계약 (Spring + Next.js)
│       │   ├── model_card.md      # 모델 설명 + 실측 성능 + 실패 모드
│       │   ├── gradio_api.schema.json # Gradio 5.x 엔드포인트 계약
│       │   ├── inference_handler.py   # infer() 단일 진입점
│       │   ├── INTEGRATION_BACKEND.md # Spring (RestClient) 1-page 가이드
│       │   ├── INTEGRATION_FRONTEND.md # Next.js (TypeScript) 1-page 가이드
│       │   └── assets/            # 샘플 I/O (테스트용)
│       ├── recipe.yaml            # 메타데이터 + 런타임 + MCP 플래그 + integration 계약
│       ├── notebook_manifest.yaml # 노트북 셀 정의
│       ├── install.sh / run.sh
│       └── requirements_*.txt
├── colab-runtimes/                # Colab 런타임 패키지 데이터 (자동 생성)
│   ├── runtimes.json              # 런타임별 주요 패키지 버전
│   ├── SUMMARY.md                 # 비교표
│   └── <version>/packages.json    # 전체 패키지 목록
├── scripts/
│   ├── make_context_pack.py       # 컨텍스트 팩 생성기
│   ├── set_active_recipe.sh       # 활성 레시피 스위칭 + .claude/.env 생성
│   ├── colab_mcp_sync.py          # 라이브 Colab ↔ 매니페스트 4-pass 정렬
│   ├── smoke_test.py              # 문법 + 임포트 검증
│   └── sync_colab_runtimes.py     # Colab 런타임 데이터 동기화
├── tools/
│   ├── generate_notebook.py       # YAML → .ipynb (GPU preflight / Gradio serve 자동 주입)
│   └── generate_export.py         # recipe.yaml → recipes/<name>/exports/ (BE/FE 계약 렌더)
├── docs/
│   ├── RUNBOOK.md                 # 훅 검증 가이드
│   ├── MCP_INTEGRATION.md         # colab-mcp 2-gate enforcement + sync 계약 (SSOT)
│   ├── SSAFY_CONVENTIONS.md       # 하네스가 <repo>/ai/에 드롭될 때의 규칙
│   ├── PORTING_PATTERNS.md        # 전략 5단계 (direct pip → conda isolation)
│   └── COMMON_ERRORS.md           # 에러 → 검증된 수정 데이터베이스
└── CLAUDE.md                      # Claude Code 지시사항 (SSOT 운용 규칙)
```

## 핵심 개념

### 레시피 (Recipe)

하나의 오픈소스 모델을 Colab에 포팅하는 독립적인 프로젝트 단위입니다.
`recipes/<name>/` 아래에 Colab 노트북 생성에 필요한 모든 것이 들어 있습니다.

### SSOT 문서 3종 (Documentation Triad)

| 파일 | 역할 |
|------|------|
| `plan.md` | 목표, 범위, 타겟 환경, 성공 기준 |
| `context.md` | 아키텍처, 의존성, 의사결정 (이유 포함), Colab 호환성 노트 |
| `tasks.md` | 순서 있는 체크리스트 (완료 시 체크) |

### 노트북 매니페스트

**확장 형식** (권장):
```yaml
title: "My Model"
gpu_type: A100  # 선택, 기본값 A100
cells:
  - type: markdown
    source: |
      # My Model
  - type: code
    source: |
      !pip install torch transformers
```

**레거시 형식** (간단):
```yaml
title: "My Model"
install: [torch, transformers]
run: "python inference.py"
```

### 훅 (Hooks)

`.claude/settings.json`에 등록된 **8개 이벤트**. 재귀 방지 가드(stdin JSON `stop_hook_active`) 적용됨.

| 훅 | 시점 | 동작 |
|----|------|------|
| SessionStart | 세션 시작 | 컨텍스트 팩 재생성 |
| UserPromptSubmit | 메시지 전송 | 관련 스킬 자동 추천 (resume-state 주입은 2026-04-20 제거 — `make_context_pack.py`의 CLAUDE.md inlining로 일원화) |
| PreToolUse | 도구 호출 전 | MCP 2-gate 강제 (`mcp.enabled`, `allow_auto_execution`) + 민감값 레닥션 |
| PostToolUse | 도구 호출 후 | 편집 이력 추적 + MCP 세션 로그 + budget 초과 경고 |
| Stop | 세션 종료 | NoMessLeftBehind 검증 (compileall + smoke + context pack) |
| PreCompact | compact 직전 | SSOT + `_resume_state.md` 자동 저장 (lossy summary 안전망) |
| PostCompact | compact 후 | 컨텍스트 팩 재로드 지원 |
| SessionEnd | `/clear`/종료 | 세션 정리 훅 |

### 스킬 (슬래시 명령)

| 명령 | 용도 |
|------|------|
| `/recipe-authoring` | 레시피 생성/수정 |
| `/colab-debugging` | Colab 설치/런타임 에러 디버깅 |
| `/notebook-builder` | 매니페스트에서 노트북 생성 |
| `/colab-mcp` | 라이브 Colab 런타임에서 현재 레시피 실행 (opt-in per recipe) |
| `/colab-mcp-sync` | 라이브 노트북 편집을 매니페스트로 역-반영 (드리프트 방지) |
| `/fresh-start` | 맥락 오염 / compact 임박 시 — SSOT 저장 + `/clear` 후 자동 복구 (`/pre-compact` 스킬은 2026-04-20 폐지, PreCompact 훅으로 대체) |
| `/session-end` | 세션 마무리 — 문서 저장, 커밋, 핸드오프 프롬프트 생성 |

### 서브에이전트 (Sub-Agents)

`.claude/agents/` 아래에 정의된 3개. Claude가 `description` 매칭으로 자동 위임.

| 에이전트 | 역할 | 자동 위임 시점 |
|---------|------|---------------|
| `code-reviewer` | 코드 리뷰 + NoMessLeftBehind 검사 | 여러 파일 편집 후, 커밋 전, "review" 요청 시 |
| `compat-debugger` | 의존성/ABI 충돌 진단 | pip 실패, ImportError, CUDA 미스매치, C-ext 빌드 실패 |
| `plan-architect` | SSOT 스캐폴딩 + 아키텍처 결정 | 새 레시피, "how should we approach X?" |

## Live Colab 이터레이션 (MCP — opt-in)

`recipe.yaml:mcp.enabled: true`로 설정하면 Claude가 브라우저 탭의
Colab 런타임을 **직접 제어**합니다. "manifest 편집 → notebook 재생성 →
Colab 업로드 → 에러 → 처음부터" 루프 대신 셀을 그대로 iterate.

### 2-gate 강제 (PreToolUse 훅)

| Gate | 대상 | 차단 조건 |
|------|------|----------|
| Gate 1 — `mcp.enabled` | 모든 `mcp__*` 도구 | `false`일 때 exit 2 + stderr 안내 |
| Gate 2 — `allow_auto_execution` | `run_*`/`execute_*`/`exec_*`/`eval_*` | `false`일 때 exit 2 — 사용자 확인 필요 |

모든 호출은 redacted되어 `.claude/_mcp_tool_calls.log`로 감사 기록.
세션 전체는 `outputs/mcp-sessions/<recipe>/<session>.jsonl`에 영속화.

### 워크플로우

```bash
scripts/set_active_recipe.sh <recipe>     # .claude/.env에 MCP_TIMEOUT/MAX_MCP_OUTPUT_TOKENS 기록
source .claude/.env && claude              # env를 Claude 프로세스에 전파
claude mcp list                            # colab-mcp 등록 확인
# Claude에게: "Colab 연결 열고 현재 레시피 셀들 실행해줘"
```

편집이 끝나면 **반드시** `/colab-mcp-sync <recipe>` — 라이브 편집을
매니페스트로 역-반영. 건너뛰면 다음 `generate_notebook.py` 실행 시
라이브 편집이 무음으로 덮어써집니다 (Ever trellis2 시절의 "Cell X
fix 20 commits" 드리프트 원인).

자세한 내용: `docs/MCP_INTEGRATION.md` (SSOT)

## BE/FE 통합 계약 (exports/)

recipe를 Spring 백엔드 + Next.js 프론트엔드에서 소비할 때, 그들이
recipe 소스 코드를 읽어야 한다면 계약이 잘못 설계된 것. 모든 팀은
`recipes/<name>/exports/`에서 **6개 파일**만 가져갑니다.

| 파일 | 소비자 |
|------|--------|
| `model_card.md` | 양쪽 — 모델이 무엇을 하는지, I/O, 실측 성능, 실패 모드, 호환성 중단 정책 |
| `gradio_api.schema.json` | BE — Gradio 5.x `POST /call/predict` 두-단계 플로우 (event_id + SSE 폴링) 계약 |
| `inference_handler.py` | AI 팀 자체 — `infer()` 단일 진입점 (Gradio + 향후 FastAPI/Modal이 이걸 래핑) |
| `INTEGRATION_BACKEND.md` | BE (Spring Boot 3.2+) — `RestClient` 예제 + `application.yml` + `@MockitoBean` 테스트 |
| `INTEGRATION_FRONTEND.md` | FE (Next.js) — TypeScript 타입 + fetch 래퍼 + 에셋 렌더링 분기 |
| `assets/` | 양쪽 — 샘플 I/O (offline 개발 + 백엔드 테스트 stub) |

### 재생성

```bash
uv run python tools/generate_export.py <recipe>
```

`recipe.yaml`의 `integration:` 섹션 + 파생 식별자를 템플릿에 치환해서
`recipes/<recipe>/exports/` 전체를 재생성합니다. 식별자 안전:
- `{RECIPE_CLASS_NAME}` — PascalCase (Java 클래스명, TS 타입명용)
- `{RECIPE_SNAKE_NAME}` — lowercase_underscore (TS 파일명용)
- `{BACKEND_ENV_VAR}` — `[A-Z0-9_]`로 정규화 (Spring `@Value` 호환)

> 템플릿 편집은 `recipes/_template/exports/`에서 — 특정 recipe의
> `exports/`를 직접 고치지 말 것 (다음 재생성 시 덮어써짐).

## SSAFY 모노레포 통합

이 하네스가 SSAFY-스타일 모노레포의 `<repo>/ai/` 아래에 드롭될 때,
**OSS 영문 기본값 대신** `docs/SSAFY_CONVENTIONS.md`의 규칙이 적용됩니다:

- 커밋 메시지: 한국어 + 14-prefix (`feat:`/`fix:`/`docs:`/...), 50자, 마침표 금지
- 브랜치: `feature/ai/S14P11A607-N-<desc>` (BE/FE는 `be`/`fe` slot)
- PR 대상: GitLab MR로 `AI/develop` 브랜치 (`master`가 아니라)
- 항상 `cd ai/ && claude` — 이 폴더의 `.claude/` + `.mcp.json` 로드
- 형제 폴더 `front/` / `back/` 수정은 **사용자 명시 승인** 없이는 금지

감지는 수동 (사용자가 맥락 신호를 주거나 프롬프트에 `S14P11A607`
등장). `.claude/last_recipe.txt`와 `.env`는 양쪽 모드에서 동일하게 작동.

## 보안 노트

- **`.claude/settings.json`과 `.mcp.json`은 세션 시작 시 자식 프로세스를 spawn**합니다.
  두 파일을 수정하는 PR은 CI 실행 권한 변경과 동등한 수준으로 리뷰.
  `.github/CODEOWNERS`에 등록되어 있어 병합 시 소유자 승인 필요.
- **개인 오버라이드는 `.claude/settings.local.json`과 `.mcp.json.local`** (둘 다
  gitignored). 공유 파일에 개인 훅/서버 커맨드 커밋 금지.
- **`/session-end`는 `git add -A` 금지** — 명시 경로만 스테이징.
  `.env` / 자격증명 / 민감 파일 실수 커밋 차단.
- **Windows Git Bash 주의**: `where bash`가 WSL stub(`C:\Windows\System32\bash.exe`)이
  아닌 Git Bash를 먼저 반환해야 훅이 정상 작동. 자세한 내용은 `CLAUDE.md` §Security.

## `/fresh-start` — 맥락 오염 없는 세션 리셋

Claude Code로 장시간 작업하다 보면 컨텍스트 윈도우가 가득 차는 문제가 발생합니다.
일반적으로 `/compact`를 사용하지만, 반복할수록 **요약의 요약**이 누적되어 맥락이 오염됩니다 (hallucination 위험 증가).

`/fresh-start`는 이 문제를 근본적으로 해결합니다:

### `/compact` vs `/fresh-start`

| | `/compact` | `/fresh-start` |
|---|---|---|
| 방식 | 대화를 요약하여 압축 | SSOT 파일에 저장 → `/clear` → 재로드 |
| 반복 시 | lossy summary 누적 → 맥락 오염 | 항상 파일 기반 → 오염 없음 |
| 맥락 유실 | 요약 과정에서 세부사항 손실 | 모든 맥락이 파일에 영속화 |
| 예측 가능성 | 낮음 (어떤 맥락이 남았는지 불확실) | 높음 (파일에 있는 것만 사용) |

### 작동 원리

```
┌─────────────────────────────────────────────────┐
│  1. 미저장 맥락을 SSOT 파일에 영속화            │
│     - context.md: 의사결정, 발견된 이슈          │
│     - tasks.md: 완료 체크, 새 항목 추가          │
│     - _resume_state.md: 현재 작업 상태 스냅샷    │
│                                                  │
│  2. Context pack 재생성                          │
│     - SSOT docs + resume state → 단일 파일로 통합│
│                                                  │
│  3. /clear 안내                                  │
│     - 사용자가 /clear 실행                       │
│     - 대화 기록 완전 초기화                      │
│                                                  │
│  4. 자동 복구                                    │
│     - Context pack이 자동 로드 (CLAUDE.md 참조)  │
│     - "이어서 해줘" 한마디로 작업 재개           │
└─────────────────────────────────────────────────┘
```

### 사용 방법

**Step 1**: 컨텍스트가 커졌다고 느껴지면 Claude에게 입력:
```
/fresh-start
```

**Step 2**: Claude가 현재 맥락을 파일에 저장하고 안내합니다:
```
준비 완료. 아래를 실행하세요:
  /clear
그 후 아무 작업 요청만 하면 됩니다 (예: "이어서 작업해줘").
```

**Step 3**: `/clear` 실행 후 작업 재개:
```
이어서 작업해줘
```
→ Claude가 SSOT 파일에서 맥락을 자동으로 읽어 바로 작업을 이어갑니다.

### 핵심 메커니즘: `_resume_state.md`

`/fresh-start`가 생성하는 상태 스냅샷 파일입니다. `git diff`를 분석하여 **실제 진행 중인 작업**을 기록합니다:

```markdown
## Uncommitted Changes (진행 중인 작업의 근거)
- M recipes/my-model/notebook_manifest.yaml — 셀 D 수정 중

## Current Work
- Cell D의 native ext 빌드 스크립트 디버깅 중

## Next Steps
- Cell E 테스트 진행
- tasks.md의 다음 미완료 항목 확인

## Key Files
- recipes/my-model/notebook_manifest.yaml
```

이 파일은 context pack에 자동 포함되므로, `/clear` 후에도 Claude가 즉시 맥락을 파악합니다.

### 언제 사용하나요?

- 대화가 길어져서 Claude 응답이 느려지거나 부정확해질 때
- `/compact`를 이미 2회 이상 사용했을 때
- Claude가 이전 맥락을 혼동하기 시작할 때

> **팁**: 이 하네스에서는 모든 맥락이 SSOT 파일에 영속화되므로, `/compact`보다 `/fresh-start`를 항상 권장합니다.
> **주의**: 다른 컴퓨터로 작업을 이동할 때는 `/fresh-start`가 아니라 `/session-end`를 사용하세요 (아래 "세션 연속성" 참조).

## 세션 연속성 (Session Continuity)

이 하네스는 세 가지 시나리오에서 작업 맥락이 유실되지 않도록 설계되었습니다.

### 시나리오 비교

| 상황 | 사용 명령 | 맥락 전달 경로 |
|------|-----------|----------------|
| **같은 PC, 컨텍스트 오버플로** | `/fresh-start` | `_resume_state.md` (로컬 파일) + SSOT docs |
| **같은/다른 PC, 세션 종료** | `/session-end` | SSOT docs (git 커밋) + 핸드오프 프롬프트 |
| **새로 git clone** | 없음 | SSOT docs만 (plan + context + tasks) |

핵심 차이: `_resume_state.md`는 로컬 전용 파일(gitignored)이므로 **같은 PC에서만 동작**합니다.
다른 PC로 이동하거나 새로 clone할 때는 SSOT docs가 유일한 맥락 원천입니다.

### 시나리오 1: 같은 PC에서 컨텍스트 오버플로

작업 중 Claude의 컨텍스트 윈도우가 가득 찼을 때.

```
사용자: /fresh-start
Claude: [SSOT 파일 업데이트 + _resume_state.md 생성]
        준비 완료. /clear 를 실행하세요.
사용자: /clear
사용자: 이어서 해줘
Claude: [_resume_state.md + SSOT 자동 로드 → 즉시 작업 재개]
```

`_resume_state.md`에 uncommitted changes와 현재 작업 상태가 기록되므로,
커밋하지 않은 작업 중간 상태에서도 완벽하게 복구됩니다.

### 시나리오 2: 다른 PC로 작업 이동 (또는 세션 마무리)

작업을 멈추고 다른 환경에서 이어받을 때.

```
사용자: /session-end
Claude: [SSOT 파일 업데이트 + git commit + push]
        핸드오프 프롬프트:
        ┌────────────────────────────────────┐
        │ 프로젝트: my-model                  │
        │ 이전 세션: Cell D까지 성공           │
        │ 다음 작업: Cell E native ext 빌드   │
        │ 핵심 파일: notebook_manifest.yaml   │
        └────────────────────────────────────┘

--- 다른 PC에서 ---

$ git pull
$ claude
사용자: [핸드오프 프롬프트 붙여넣기]
Claude: [SSOT docs 자동 로드 + 핸드오프 프롬프트 반영 → 작업 재개]
```

`/session-end`는 모든 맥락을 SSOT docs에 커밋하고, 핸드오프 프롬프트를 생성합니다.
새 PC에서는 `git pull` 후 핸드오프 프롬프트를 붙여넣으면 됩니다.

### 시나리오 3: 새로 git clone (핸드오프 프롬프트 없이)

핸드오프 프롬프트를 잃어버렸거나, 시간이 지난 후 작업을 재개할 때.

```
$ git clone <repo-url>
$ cd <repo>
$ claude
사용자: recipes/my-model 레시피 이어서 작업해줘
Claude: [SSOT docs 자동 로드 → plan/context/tasks 기반으로 작업 재개]
```

SSOT docs(`plan.md`, `context.md`, `tasks.md`)만으로도 작업 재개가 가능합니다.
`tasks.md`의 체크리스트에서 마지막 완료 항목을 보고 다음 작업을 판단합니다.

> **핵심 원칙**: 모든 중요 맥락은 반드시 SSOT 파일에 영속화됩니다.
> `_resume_state.md`와 핸드오프 프롬프트는 **편의성을 위한 가속기**이지, 유일한 맥락 원천이 아닙니다.
> 둘 다 없어도 SSOT docs만으로 작업 재개가 가능하도록 설계되었습니다.

### 어떤 명령을 사용해야 하나요?

```
컨텍스트가 커졌다 → /fresh-start
오늘 작업 끝     → /session-end
compact 임박     → /fresh-start (/pre-compact 스킬은 2026-04-20 폐지, PreCompact 훅이 대체)
```

## Colab 런타임 패키지 추적

`colab-runtimes/` 디렉토리에 [googlecolab/backend-info](https://github.com/googlecolab/backend-info)에서 자동 수집한 Colab 런타임별 패키지 버전이 저장됩니다.

```bash
# 수동 동기화
python scripts/sync_colab_runtimes.py

# 자동 동기화 (GitHub Action, 매일 실행)
# .github/workflows/sync-colab-runtimes.yml
```

### 주요 파일
| 파일 | 설명 |
|------|------|
| `colab-runtimes/runtimes.json` | 런타임별 주요 패키지 버전 (JSON) |
| `colab-runtimes/SUMMARY.md` | 런타임 비교표 (사람 읽기용) |
| `colab-runtimes/<version>/packages.json` | 특정 런타임의 전체 패키지 목록 |
| `colab-runtimes/quick-reference.md` | AI 컨텍스트용 간결 참조 |

### 활용 방법
오픈소스 모델을 Colab에 포팅할 때:
1. 모델이 필요로 하는 torch/Python 버전 확인
2. `colab-runtimes/SUMMARY.md`에서 어떤 런타임이 가장 잘 맞는지 비교
3. 런타임 롤백이 가능하면 가장 간단한 해결책 (Colab: Runtime > Change runtime type > Runtime version)

## Colab 포팅 시 체크리스트

오픈소스 AI 모델을 Colab에 포팅할 때 확인할 사항:

1. **타겟 런타임 선택**: `colab-runtimes/SUMMARY.md`에서 모델 요구사항과 가장 가까운 런타임 확인
2. **의존성 비교**: 모델의 `requirements.txt` vs Colab 사전 설치 패키지 비교
3. **충돌 유형 파악**: pip으로 해결 가능한가? 런타임 롤백이 필요한가? 격리 환경이 필요한가?
4. **단계별 검증**: 각 설치 단계를 Colab에서 실제로 실행하여 결과 확인

### Requirements 파일 규칙

- **Colab 기본 패키지 주의**: numpy, scipy, Pillow 등은 Colab에 사전 설치되어 있으므로 버전 충돌 가능
- **버전 민감 패키지 고정**: torch, diffusers, xformers 등은 정확한 버전 지정 필요
- **Upstream 기준**: 모델 저자가 테스트한 환경과 최대한 일치시키기

## 작업 흐름

```
1. GitHub에서 흥미로운 AI 모델 발견
2. 레시피 생성:       cp -r recipes/_template recipes/my-model
3. 활성화:            scripts/set_active_recipe.sh my-model
4. Claude에게 포팅 목표 전달 (recipes/my-model/docs/plan.md 작성)
5. Claude가 의존성 해결, notebook_manifest.yaml 작성
6. 노트북 생성:       uv run python tools/generate_notebook.py my-model
7. (선택) Live iteration: mcp.enabled: true → source .claude/.env && claude → /colab-mcp
8. Colab에서 테스트, 에러 발생 시 Claude에게 전달 → 반복
9. (MCP 사용 시) /colab-mcp-sync my-model 으로 라이브 편집 → 매니페스트 역-반영
10. BE/FE 계약 생성: uv run python tools/generate_export.py my-model
11. /session-end 로 세션 마무리 (SSOT 커밋 + 핸드오프)
```

---

# English

A Claude Code-powered harness for porting open-source AI models to Google Colab notebooks.

## What is this?

When you find an interesting open-source AI model on GitHub and want to run it on Colab, you typically face these challenges:
- Dependency conflicts with Colab's pre-installed packages (numpy, Pillow, and other C extensions)
- CUDA/GPU compatibility issues (Blackwell, A100, and T4 each require different torch versions)
- Native C extension build failures (nvdiffrast, CuMesh, etc.)
- Environment constraints (runtime resets, disk limits, session timeouts)

This harness structures and automates that entire process:
- **Recipe system** — manage each model's porting project in a structured, reproducible way (SSOT triad)
- **Notebook generator** — auto-generate Colab `.ipynb` notebooks from YAML manifests (GPU preflight + Gradio serve auto-injected)
- **Claude Code hooks** — auto-validation, skill suggestions, context management, auto-recovery after `/clear`
- **Colab runtime tracking** — auto-collect and compare package versions across Colab runtimes
- **Live Colab iteration** — drive a browser-side Colab runtime directly via `colab-mcp` integration; no notebook re-upload loop (opt-in per recipe)
- **Exports contract** — type-safe integration docs + JSON Schema + handler that Spring/Next.js teammates pull from the recipe's `exports/`

## Quick Start

### Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Git

### 1. Clone

```bash
git clone https://github.com/Chocochip-213/AI-OpenSource-Harness.git
cd AI-OpenSource-Harness
```

### 2. Start Claude Code

```bash
claude
```

Hooks auto-configure on the first session start:
```
[hook:session-start] Context pack ready
```

### 3. Create a Recipe

```bash
cp -r recipes/_template recipes/my-model
scripts/set_active_recipe.sh my-model     # writes .claude/last_recipe.txt + .claude/.env, rebuilds context pack
```

Then tell Claude: **"Edit recipes/my-model/docs/plan.md. I want to run [model name] on Colab."**

### 4. Generate the Notebook

After editing `recipes/my-model/notebook_manifest.yaml`:

```bash
uv run python tools/generate_notebook.py my-model
# -> outputs/notebooks/my-model.ipynb
```

Upload to Colab and test!

## Project Structure

```
AI-OpenSource-Harness/
├── .claude/                       # Claude Code infrastructure
│   ├── hooks/                     # Lifecycle hooks (8 events + helper scripts)
│   ├── skills/                    # Slash command definitions (8)
│   ├── agents/                    # Sub-agent definitions (3)
│   ├── settings.json              # Hook configuration (CODEOWNERS-protected)
│   ├── settings.local.json        # Local overrides (gitignored)
│   └── skill-rules.json           # Harness-local: extra skill match keywords
├── .mcp.json                      # colab-mcp server registration (opt-in, CODEOWNERS-protected)
├── .github/
│   ├── CODEOWNERS                 # Enforces review on .mcp.json / settings.json / hooks
│   └── workflows/
│       └── sync-colab-runtimes.yml # Daily auto-sync
├── .gitattributes                 # Shared-file merge strategy (union / ours)
├── recipes/
│   └── _template/                 # Base template for new recipes
│       ├── docs/                  # SSOT documentation triad
│       │   ├── plan.md            # Goal, scope, approach
│       │   ├── context.md         # Architecture, decisions, Colab compatibility
│       │   └── tasks.md           # Ordered checklist
│       ├── exports/               # BE/FE integration contract (Spring + Next.js)
│       │   ├── model_card.md      # Model description + measured perf + failure modes
│       │   ├── gradio_api.schema.json # Gradio 5.x endpoint contract
│       │   ├── inference_handler.py   # infer() single entrypoint
│       │   ├── INTEGRATION_BACKEND.md # Spring (RestClient) 1-page guide
│       │   ├── INTEGRATION_FRONTEND.md # Next.js (TypeScript) 1-page guide
│       │   └── assets/            # Sample I/O (offline dev stubs)
│       ├── recipe.yaml            # Metadata + runtime + MCP flags + integration contract
│       ├── notebook_manifest.yaml # Notebook cell definitions
│       ├── install.sh / run.sh
│       └── requirements_*.txt
├── colab-runtimes/                # Colab runtime package data (auto-generated)
│   ├── runtimes.json              # Key package versions per runtime
│   ├── SUMMARY.md                 # Side-by-side comparison table
│   └── <version>/packages.json    # Full package list per runtime
├── scripts/
│   ├── make_context_pack.py       # Context pack generator
│   ├── set_active_recipe.sh       # Recipe switch + .claude/.env write
│   ├── colab_mcp_sync.py          # Live Colab ↔ manifest 4-pass aligner
│   ├── smoke_test.py              # Syntax + import validation
│   └── sync_colab_runtimes.py     # Colab runtime data sync
├── tools/
│   ├── generate_notebook.py       # YAML → .ipynb (GPU preflight / Gradio serve auto-injected)
│   └── generate_export.py         # recipe.yaml → recipes/<name>/exports/ (BE/FE contract render)
├── docs/
│   ├── RUNBOOK.md                 # Hook verification guide
│   ├── MCP_INTEGRATION.md         # colab-mcp 2-gate enforcement + sync contract (SSOT)
│   ├── SSAFY_CONVENTIONS.md       # Rules that apply when harness sits at <repo>/ai/
│   ├── PORTING_PATTERNS.md        # Strategy ladder (direct pip → conda isolation)
│   └── COMMON_ERRORS.md           # Error → verified fix database
└── CLAUDE.md                      # Claude Code instructions (SSOT operating rules)
```

## Key Concepts

### Recipe

A self-contained project unit for porting a single open-source model to Colab.
Everything needed to generate a Colab notebook lives under `recipes/<name>/`.

### SSOT Documentation Triad

| File | Purpose |
|------|---------|
| `plan.md` | Goal, scope, target environment, success criteria |
| `context.md` | Architecture, dependencies, decisions (with reasoning), Colab compatibility notes |
| `tasks.md` | Ordered checklist (check off items as they are completed) |

### Notebook Manifest

**Extended format** (recommended):
```yaml
title: "My Model"
gpu_type: A100  # optional, defaults to A100
cells:
  - type: markdown
    source: |
      # My Model
  - type: code
    source: |
      !pip install torch transformers
```

**Legacy format** (simple):
```yaml
title: "My Model"
install: [torch, transformers]
run: "python inference.py"
```

### Hooks

`.claude/settings.json` registers **8 events**. Recursion guard via stdin-JSON `stop_hook_active` field.

| Hook | Trigger | Action |
|------|---------|--------|
| SessionStart | Session begins | Rebuild context pack |
| UserPromptSubmit | Message sent | Auto-suggest relevant skills (resume-state injection removed 2026-04-20 — consolidated into `make_context_pack.py` CLAUDE.md inlining) |
| PreToolUse | Before tool call | Enforce MCP 2-gate (`mcp.enabled`, `allow_auto_execution`) + sensitive-value redaction |
| PostToolUse | After tool call | Track edit history + MCP session log + output-budget warnings |
| Stop | Session ends | NoMessLeftBehind validation (compileall + smoke + context pack) |
| PreCompact | Before compact | Auto-save SSOT + `_resume_state.md` (lossy-summary safety net) |
| PostCompact | After compact | Support re-loading context pack |
| SessionEnd | `/clear` or termination | Session cleanup hook |

### Skills (Slash Commands)

| Command | Purpose |
|---------|---------|
| `/recipe-authoring` | Create or modify recipes |
| `/colab-debugging` | Debug Colab install/runtime errors |
| `/notebook-builder` | Generate notebooks from manifests |
| `/colab-mcp` | Run the current recipe on a live Colab runtime (opt-in per recipe) |
| `/colab-mcp-sync` | Promote live-notebook edits back into the manifest (drift prevention) |
| `/fresh-start` | Context pollution / compact imminent — save to SSOT + `/clear` for clean restart (also covers the retired `/pre-compact` intent; that skill was removed 2026-04-20 — the PreCompact hook handles the same job deterministically) |
| `/session-end` | Wrap up session — save docs, commit, generate handoff prompt |

### Sub-Agents

3 agents under `.claude/agents/`. Claude auto-delegates based on `description` matching.

| Agent | Role | Auto-delegate when |
|-------|------|--------------------|
| `code-reviewer` | Code review + NoMessLeftBehind checks | Multiple files edited, before commit, user asks "review" |
| `compat-debugger` | Dependency / ABI conflict diagnosis | pip fails, ImportError, CUDA mismatch, C-ext build fail |
| `plan-architect` | SSOT scaffolding + architecture decisions | New recipe, user asks "how should we approach X?" |

## Live Colab Iteration (MCP — opt-in)

Set `recipe.yaml:mcp.enabled: true` and Claude can **directly drive** a
browser-attached Colab runtime. No more "edit manifest → regenerate
notebook → upload to Colab → hit error → restart" loop — iterate cells
in place.

### 2-gate enforcement (PreToolUse hook)

| Gate | Target | Blocks when |
|------|--------|-------------|
| Gate 1 — `mcp.enabled` | All `mcp__*` tools | `false` → exit 2 with stderr guidance |
| Gate 2 — `allow_auto_execution` | `run_*`/`execute_*`/`exec_*`/`eval_*` tools | `false` → exit 2, requires user confirmation |

Every call is redacted and audited to `.claude/_mcp_tool_calls.log`.
Full sessions are persisted to `outputs/mcp-sessions/<recipe>/<session>.jsonl`.

### Workflow

```bash
scripts/set_active_recipe.sh <recipe>     # writes .claude/.env with MCP_TIMEOUT / MAX_MCP_OUTPUT_TOKENS
source .claude/.env && claude              # propagate env to the Claude process
claude mcp list                            # verify colab-mcp is registered
# Ask Claude: "Open the Colab connection and run the current recipe's cells"
```

When finished, **always** run `/colab-mcp-sync <recipe>` — promotes
live edits back into the manifest. Skipping it causes the next
`generate_notebook.py` run to silently overwrite your live work
(this is the "Cell X fix 20 commits" drift that plagued the
Ever-era trellis2 iteration).

Full details: `docs/MCP_INTEGRATION.md` (SSOT)

## BE/FE Integration Contract (exports/)

If a Spring backend or Next.js frontend needs to read the recipe's
source code to integrate, the contract is broken. Every team pulls
**6 files** from `recipes/<name>/exports/` and nothing else:

| File | Consumer |
|------|----------|
| `model_card.md` | Both — what the model does, I/O, measured perf, failure modes, breaking-change policy |
| `gradio_api.schema.json` | BE — Gradio 5.x `POST /call/predict` two-step contract (event_id + SSE polling) |
| `inference_handler.py` | AI team itself — `infer()` single entrypoint (Gradio + future FastAPI/Modal wrap this) |
| `INTEGRATION_BACKEND.md` | BE (Spring Boot 3.2+) — `RestClient` example + `application.yml` + `@MockitoBean` testing |
| `INTEGRATION_FRONTEND.md` | FE (Next.js) — TypeScript types + fetch wrapper + asset rendering branches |
| `assets/` | Both — sample I/O (offline dev stubs + backend test fixtures) |

### Regenerating

```bash
uv run python tools/generate_export.py <recipe>
```

Substitutes `recipe.yaml:integration:` fields + derived identifiers
into the templates and rewrites `recipes/<recipe>/exports/` entirely.
Identifier safety:
- `{RECIPE_CLASS_NAME}` — PascalCase (Java class / TS type names)
- `{RECIPE_SNAKE_NAME}` — lowercase_underscore (TS file names)
- `{BACKEND_ENV_VAR}` — normalized to `[A-Z0-9_]` (Spring `@Value` safe)

> Edit templates under `recipes/_template/exports/` — do NOT edit a
> specific recipe's `exports/` by hand, next regeneration will overwrite.

## SSAFY Monorepo Integration

When this harness lives under `<repo>/ai/` in a SSAFY-style monorepo,
the rules in `docs/SSAFY_CONVENTIONS.md` apply **instead of the OSS
English defaults**:

- Commit messages: Korean + 14-prefix (`feat:`/`fix:`/`docs:`/...), 50 chars, no trailing dot
- Branch: `feature/ai/S14P11A607-N-<desc>` (BE/FE use `be`/`fe` slot)
- PR target: `AI/develop` via GitLab MR (not `master`)
- Always `cd ai/ && claude` — picks up this folder's `.claude/` + `.mcp.json`
- Modifying sibling `front/` / `back/` requires **explicit user-confirmed** cross-domain branch

Detection is manual (user signals context, or prompt mentions
`S14P11A607`). `.claude/last_recipe.txt` and `.env` behave identically
in both modes.

## Security Notes

- **`.claude/settings.json` and `.mcp.json` both spawn child processes on
  session start.** Treat any PR modifying either file with the same
  scrutiny as CI-exec permission changes. `.github/CODEOWNERS` enforces
  review on merge.
- **Personal overrides live in `.claude/settings.local.json` and
  `.mcp.json.local`** (both gitignored). Never commit personal
  hook/server commands to the shared files.
- **`/session-end` never uses `git add -A`** — explicit paths only.
  Prevents accidental commits of `.env` / credentials / other
  sensitive untracked files.
- **Windows Git Bash gotcha**: `where bash` must return Git Bash's
  `bash` first, NOT the WSL stub at `C:\Windows\System32\bash.exe`,
  or hooks hang/fail silently. See `CLAUDE.md` §Security for fallback.

## `/fresh-start` — Context-Clean Session Reset

When working with Claude Code for extended periods, the context window fills up.
The usual fix is `/compact`, but repeated compaction creates **summaries of summaries**, leading to context pollution (increased hallucination risk).

`/fresh-start` solves this problem at the root:

### `/compact` vs `/fresh-start`

| | `/compact` | `/fresh-start` |
|---|---|---|
| Method | Summarize and compress the conversation | Save to SSOT files → `/clear` → reload |
| On repeat | Lossy summaries accumulate → context pollution | Always file-based → no pollution |
| Context loss | Details lost during summarization | All context persisted in files |
| Predictability | Low (unclear what context remains) | High (only uses what's in files) |

### How It Works

```
┌──────────────────────────────────────────────────────┐
│  1. Persist unsaved context to SSOT files            │
│     - context.md: decisions, discovered issues       │
│     - tasks.md: check off completed, add new items   │
│     - _resume_state.md: current work state snapshot  │
│                                                      │
│  2. Rebuild context pack                             │
│     - SSOT docs + resume state → single file         │
│                                                      │
│  3. Prompt user to /clear                            │
│     - User runs /clear                               │
│     - Conversation history fully reset               │
│                                                      │
│  4. Auto-recovery                                    │
│     - Context pack auto-loads (referenced by CLAUDE.md)│
│     - Say "continue" and work resumes instantly      │
└──────────────────────────────────────────────────────┘
```

### Usage

**Step 1**: When you feel the context is getting large, type:
```
/fresh-start
```

**Step 2**: Claude saves current context to files and prompts you:
```
Ready. Run the following:
  /clear
Then just ask to continue (e.g., "continue where we left off").
```

**Step 3**: After `/clear`, resume work:
```
continue where we left off
```
→ Claude auto-reads context from SSOT files and picks up right where you left off.

### Key Mechanism: `_resume_state.md`

A state snapshot file generated by `/fresh-start`. It analyzes `git diff` to record **what's actually in progress**:

```markdown
## Uncommitted Changes (evidence of in-progress work)
- M recipes/my-model/notebook_manifest.yaml — editing cell D

## Current Work
- Debugging native ext build script in Cell D

## Next Steps
- Proceed to Cell E testing
- Check next incomplete item in tasks.md

## Key Files
- recipes/my-model/notebook_manifest.yaml
```

This file is auto-included in the context pack, so Claude immediately understands the context even after `/clear`.

### When to Use

- Conversation is long and Claude responses become slow or inaccurate
- You've already used `/compact` 2+ times
- Claude starts confusing previous context

> **Tip**: In this harness, all context is persisted in SSOT files, so `/fresh-start` is always preferred over `/compact`.
> **Note**: To hand off work to a different machine, use `/session-end` instead (see "Session Continuity" below).

## Session Continuity

This harness is designed to preserve work context across three scenarios.

### Scenario Comparison

| Situation | Command | Context Transfer |
|-----------|---------|-----------------|
| **Same PC, context overflow** | `/fresh-start` | `_resume_state.md` (local file) + SSOT docs |
| **Same/different PC, end of session** | `/session-end` | SSOT docs (git committed) + handoff prompt |
| **Fresh git clone** | none | SSOT docs only (plan + context + tasks) |

Key difference: `_resume_state.md` is a local-only file (gitignored) — it **only works on the same machine**.
When moving to another PC or cloning fresh, SSOT docs are the sole source of context.

### Scenario 1: Same PC, Context Overflow

When Claude's context window fills up during a long session.

```
You:    /fresh-start
Claude: [Updates SSOT files + creates _resume_state.md]
        Ready. Run /clear.
You:    /clear
You:    continue where we left off
Claude: [Auto-loads _resume_state.md + SSOT → instantly resumes]
```

`_resume_state.md` records uncommitted changes and current work state,
so even mid-work with uncommitted changes, recovery is seamless.

### Scenario 2: Moving to Another PC (or Ending a Session)

When you're done for the day or switching to a different machine.

```
You:    /session-end
Claude: [Updates SSOT files + git commit + push]
        Handoff prompt:
        ┌────────────────────────────────────────┐
        │ Project: my-model                       │
        │ Previous session: Cells A-D passed      │
        │ Next task: Cell E native ext build      │
        │ Key file: notebook_manifest.yaml        │
        └────────────────────────────────────────┘

--- On the new PC ---

$ git pull
$ claude
You:    [paste handoff prompt]
Claude: [Auto-loads SSOT docs + handoff context → resumes work]
```

`/session-end` commits all context to SSOT docs and generates a handoff prompt.
On the new PC, just `git pull` and paste the prompt.

### Scenario 3: Fresh Git Clone (No Handoff Prompt)

When you lost the handoff prompt, or are resuming after a long break.

```
$ git clone <repo-url>
$ cd <repo>
$ claude
You:    continue working on recipes/my-model
Claude: [Auto-loads SSOT docs → resumes from plan/context/tasks]
```

SSOT docs alone (`plan.md`, `context.md`, `tasks.md`) are sufficient to resume.
Claude reads `tasks.md` to find the last completed item and determines the next step.

> **Core principle**: All critical context must be persisted in SSOT files.
> `_resume_state.md` and handoff prompts are **convenience accelerators**, not the sole source of truth.
> Even without them, work can resume from SSOT docs alone.

### Which Command Should I Use?

```
Context getting large → /fresh-start
Done for the day     → /session-end
Compact imminent     → /fresh-start (/pre-compact skill retired 2026-04-20; PreCompact hook handles the write)
```

## Colab Runtime Tracking

The `colab-runtimes/` directory stores per-runtime package versions auto-collected from [googlecolab/backend-info](https://github.com/googlecolab/backend-info).

```bash
# Manual sync
python scripts/sync_colab_runtimes.py

# Auto sync (GitHub Action, runs daily)
# .github/workflows/sync-colab-runtimes.yml
```

### Key Files

| File | Description |
|------|-------------|
| `colab-runtimes/runtimes.json` | Key package versions per runtime (JSON) |
| `colab-runtimes/SUMMARY.md` | Runtime comparison table (human-readable) |
| `colab-runtimes/<version>/packages.json` | Full package list for a specific runtime |
| `colab-runtimes/quick-reference.md` | Compact reference for AI context windows |

### How to Use

When porting an open-source model to Colab:
1. Check the torch/Python versions the model requires
2. Compare against `colab-runtimes/SUMMARY.md` to find the best-matching runtime
3. If a runtime rollback works, that's the simplest fix (Colab: Runtime > Change runtime type > Runtime version)

## Colab Porting Checklist

Things to verify when porting an open-source AI model to Colab:

1. **Choose target runtime**: Check `colab-runtimes/SUMMARY.md` for the runtime closest to model requirements
2. **Compare dependencies**: Model's `requirements.txt` vs Colab's pre-installed packages
3. **Identify conflict type**: Solvable with pip? Need a runtime rollback? Need an isolated environment?
4. **Validate step by step**: Run each install step in Colab and verify the results

### Requirements File Rules

- **Watch Colab defaults**: numpy, scipy, Pillow, etc. are pre-installed — version conflicts are common
- **Pin version-sensitive packages**: torch, diffusers, xformers need exact version pinning
- **Match upstream**: Align as closely as possible with the environment the model author tested on

## Workflow

```
1.  Find an interesting AI model on GitHub
2.  Create a recipe:       cp -r recipes/_template recipes/my-model
3.  Activate:               scripts/set_active_recipe.sh my-model
4.  Tell Claude your porting goal (author recipes/my-model/docs/plan.md)
5.  Claude resolves dependencies, writes notebook_manifest.yaml
6.  Generate notebook:      uv run python tools/generate_notebook.py my-model
7.  (Optional) Live iter:   mcp.enabled: true → source .claude/.env && claude → /colab-mcp
8.  Test on Colab — paste errors back to Claude → iterate
9.  (If MCP) Promote drift: /colab-mcp-sync my-model  (live edits → manifest)
10. Render BE/FE contract:  uv run python tools/generate_export.py my-model
11. Wrap up with /session-end (SSOT commit + handoff prompt)
```

## License

MIT

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
- **레시피 시스템** — 모델별 포팅 프로젝트를 체계적으로 관리
- **노트북 생성기** — YAML 매니페스트 -> Colab `.ipynb` 자동 생성
- **Claude Code 훅** — 자동 검증, 스킬 추천, 맥락 관리
- **Colab 런타임 추적** — Colab 런타임별 패키지 버전 자동 수집 및 비교

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
echo "my-model" > .claude/last_recipe.txt
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
├── .claude/                      # Claude Code 인프라
│   ├── hooks/                    # 라이프사이클 훅 (4개)
│   ├── skills/                   # 슬래시 명령 정의 (6개)
│   ├── agents/                   # 서브에이전트 정의 (3개)
│   ├── settings.json             # 훅 설정
│   └── skill-rules.json          # 스킬 매칭 규칙
├── recipes/
│   └── _template/                # 새 레시피의 기본 템플릿
│       ├── docs/                 # SSOT 문서 3종
│       │   ├── plan.md           # 목표, 범위, 접근법
│       │   ├── context.md        # 아키텍처, 의사결정, Colab 호환성
│       │   └── tasks.md          # 체크리스트
│       ├── recipe.yaml           # 메타데이터 + 런타임 요구사항
│       ├── notebook_manifest.yaml # 노트북 셀 정의
│       ├── install.sh / run.sh
│       └── requirements_*.txt
├── colab-runtimes/                  # Colab 런타임 패키지 데이터 (자동 생성)
│   ├── runtimes.json              # 런타임별 주요 패키지 버전
│   ├── SUMMARY.md                 # 비교표
│   └── <version>/packages.json   # 전체 패키지 목록
├── scripts/
│   ├── make_context_pack.py      # 컨텍스트 팩 생성기
│   ├── smoke_test.py             # 문법 + 임포트 검증
│   └── sync_colab_runtimes.py    # Colab 런타임 데이터 동기화
├── tools/
│   └── generate_notebook.py      # YAML -> .ipynb 변환기
├── .github/workflows/
│   └── sync-colab-runtimes.yml   # 일일 자동 동기화
├── docs/RUNBOOK.md               # 훅 검증 가이드
└── CLAUDE.md                     # Claude Code 지시사항
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

| 훅 | 시점 | 동작 |
|----|------|------|
| SessionStart | 세션 시작 | 컨텍스트 팩 재생성 |
| UserPromptSubmit | 메시지 전송 | 관련 스킬 자동 추천 |
| PostToolUse | 파일 편집 | 편집 이력 추적 |
| Stop | 세션 종료 | 코드 검증, 컨텍스트 갱신 |

### 스킬 (슬래시 명령)

| 명령 | 용도 |
|------|------|
| `/recipe-authoring` | 레시피 생성/수정 |
| `/colab-debugging` | Colab 설치/런타임 에러 디버깅 |
| `/notebook-builder` | 매니페스트에서 노트북 생성 |
| `/fresh-start` | 맥락 오염 시 — SSOT 저장 + `/clear` 후 자동 복구 |
| `/session-end` | 세션 마무리 — 문서 저장, 커밋, 핸드오프 프롬프트 생성 |
| `/pre-compact` | 컨텍스트 부족 시 — 중요 맥락 영속화 + compact 요약 제안 |

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
- 다른 컴퓨터/세션에서 작업을 이어받을 때
- Claude가 이전 맥락을 혼동하기 시작할 때

> **팁**: 이 하네스에서는 모든 맥락이 SSOT 파일에 영속화되므로, `/compact`보다 `/fresh-start`를 항상 권장합니다.

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
2. 레시피 생성:  cp -r recipes/_template recipes/my-model
3. Claude에게 포팅 목표 전달
4. Claude가 plan 작성, 의존성 해결, 노트북 매니페스트 생성
5. 노트북 생성:  uv run python tools/generate_notebook.py my-model
6. Colab에서 테스트, 에러 발생 시 Claude에게 전달
7. 반복하여 완성
8. /session-end 로 세션 마무리
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
- **Recipe system** — manage each model's porting project in a structured, reproducible way
- **Notebook generator** — auto-generate Colab `.ipynb` notebooks from YAML manifests
- **Claude Code hooks** — auto-validation, skill suggestions, and context management
- **Colab runtime tracking** — auto-collect and compare package versions across Colab runtimes

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
echo "my-model" > .claude/last_recipe.txt
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
├── .claude/                      # Claude Code infrastructure
│   ├── hooks/                    # Lifecycle hooks (4)
│   ├── skills/                   # Slash command definitions (6)
│   ├── agents/                   # Sub-agent definitions (3)
│   ├── settings.json             # Hook configuration
│   └── skill-rules.json          # Skill matching rules
├── recipes/
│   └── _template/                # Base template for new recipes
│       ├── docs/                 # SSOT documentation triad
│       │   ├── plan.md           # Goal, scope, approach
│       │   ├── context.md        # Architecture, decisions, Colab compatibility
│       │   └── tasks.md          # Ordered checklist
│       ├── recipe.yaml           # Metadata + runtime requirements
│       ├── notebook_manifest.yaml # Notebook cell definitions
│       ├── install.sh / run.sh
│       └── requirements_*.txt
├── colab-runtimes/               # Colab runtime package data (auto-generated)
│   ├── runtimes.json             # Key package versions per runtime
│   ├── SUMMARY.md                # Side-by-side comparison table
│   └── <version>/packages.json   # Full package list per runtime
├── scripts/
│   ├── make_context_pack.py      # Context pack generator
│   ├── smoke_test.py             # Syntax + import validation
│   └── sync_colab_runtimes.py    # Colab runtime data sync
├── tools/
│   └── generate_notebook.py      # YAML -> .ipynb converter
├── .github/workflows/
│   └── sync-colab-runtimes.yml   # Daily auto-sync
├── docs/RUNBOOK.md               # Hook verification guide
└── CLAUDE.md                     # Claude Code instructions
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

| Hook | Trigger | Action |
|------|---------|--------|
| SessionStart | Session begins | Rebuild context pack |
| UserPromptSubmit | Message sent | Auto-suggest relevant skills |
| PostToolUse | File edited | Track edit history |
| Stop | Session ends | Code validation, context refresh |

### Skills (Slash Commands)

| Command | Purpose |
|---------|---------|
| `/recipe-authoring` | Create or modify recipes |
| `/colab-debugging` | Debug Colab install/runtime errors |
| `/notebook-builder` | Generate notebooks from manifests |
| `/fresh-start` | Context pollution — save to SSOT + `/clear` for clean restart |
| `/session-end` | Wrap up session — save docs, commit, generate handoff prompt |
| `/pre-compact` | Context running low — persist critical context + suggest compact summary |

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
- Handing off work to a different machine or session
- Claude starts confusing previous context

> **Tip**: In this harness, all context is persisted in SSOT files, so `/fresh-start` is always preferred over `/compact`.

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
1. Find an interesting AI model on GitHub
2. Create a recipe:  cp -r recipes/_template recipes/my-model
3. Tell Claude your porting goal
4. Claude writes the plan, resolves dependencies, generates the notebook manifest
5. Generate notebook:  uv run python tools/generate_notebook.py my-model
6. Test on Colab — when errors occur, paste them back to Claude
7. Iterate until it works
8. Wrap up with /session-end
```

## License

MIT

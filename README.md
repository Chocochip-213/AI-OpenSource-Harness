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
- **실전 패턴** — 여러 모델 포팅에서 축적한 Colab 호환성 솔루션

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
│   ├── skills/                   # 슬래시 명령 정의 (5개)
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
├── scripts/
│   ├── make_context_pack.py      # 컨텍스트 팩 생성기
│   └── smoke_test.py             # 문법 + 임포트 검증
├── tools/
│   └── generate_notebook.py      # YAML -> .ipynb 변환기
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
| `/session-end` | 세션 마무리 — 문서 저장, 커밋, 핸드오프 프롬프트 생성 |
| `/pre-compact` | 컨텍스트 부족 시 — 중요 맥락 영속화 + compact 요약 제안 |

## Colab 포팅 패턴

여러 모델 포팅 경험에서 얻은 교훈 (SwiftTry, TRELLIS.2, Flux2-VTON, Flux2-TPose):

### 전략 선택

| 모델 유형 | 전략 | 조건 |
|-----------|------|------|
| 경량 (pip만 필요) | **Direct pip** | Colab 기본 torch 유지 |
| 중량 (네이티브 C 확장) | **Conda 격리** | condacolab으로 깨끗한 환경 |

### 자주 발생하는 문제와 해결법

| 문제 | 해결법 |
|------|--------|
| numpy/Pillow C extension 충돌 | Conda 격리 (프로세스 내 .so 교체 불가) |
| flash-attn 빌드 실패 | `ATTN_BACKEND=xformers` |
| spconv wheel 없음 | `spconv-cu124`, 대안 `torchsparse` |
| 네이티브 확장 빌드 실패 | 단계적 설치 (try/except), 로컬 클론 경로 사용 |
| GPU 아키텍처 불일치 (Blackwell) | compute capability 자동 감지, torch 버전 매칭 |
| rembg/BiRefNet 의존성 체인 | `preprocess_image=False` + RGBA 입력 |
| condacolab이 Python 3.12에서 실패 | runtime 2025.07 (Python 3.11) 사용 |

### Requirements 파일 규칙

- **절대 고정하지 말 것**: numpy, scipy, Pillow, matplotlib (Colab 기본값 유지)
- **반드시 고정할 것**: torch, diffusers, xformers (버전 민감, ABI 영향)
- **Upstream 버전에 맞출 것**: 모델 저자가 테스트한 버전과 일치

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

This harness automates the process of getting open-source AI models running on Google Colab:
- **Recipe system** — structured project for each porting effort
- **Notebook generator** — YAML manifest to Colab `.ipynb`
- **Claude Code hooks** — auto-validation, skill suggestions, context management
- **Battle-tested patterns** — solutions from porting SwiftTry, TRELLIS.2, Flux2-VTON, Flux2-TPose

## Quick Start

```bash
git clone https://github.com/Chocochip-213/AI-OpenSource-Harness.git
cd AI-OpenSource-Harness
claude  # Start Claude Code — hooks auto-configure

# Create a recipe
cp -r recipes/_template recipes/my-model
echo "my-model" > .claude/last_recipe.txt

# Generate notebook
uv run python tools/generate_notebook.py my-model
# Upload outputs/notebooks/my-model.ipynb to Colab
```

## Key Concepts

- **Recipe**: Self-contained porting project in `recipes/<name>/`
- **SSOT Triad**: `plan.md` (goal) + `context.md` (decisions) + `tasks.md` (checklist)
- **Manifest**: YAML cell definitions -> `.ipynb` notebook
- **Hooks**: Auto-validate on stop, auto-suggest skills on prompt
- **Skills**: `/recipe-authoring`, `/colab-debugging`, `/notebook-builder`, `/session-end`, `/pre-compact`

## Colab Patterns

| Problem | Solution |
|---------|----------|
| C extension conflicts | Conda isolated env |
| flash-attn fails | `ATTN_BACKEND=xformers` |
| spconv missing | `spconv-cu124` or `torchsparse` |
| Native ext fails | Staged install, local paths |
| GPU mismatch | Auto-detect compute cap |
| condacolab on 3.12 | Use runtime 2025.07 |

## Architecture

See [Korean section above](#프로젝트-구조) for full directory tree.

## Verifying Setup

```bash
# Check hooks
uv run python scripts/smoke_test.py

# Test skill suggestion
echo '{"prompt":"fix pip install error in colab"}' | bash .claude/hooks/userprompt-submit.sh
```

See `docs/RUNBOOK.md` for detailed hook testing.

## License

MIT

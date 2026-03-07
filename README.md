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
| `/session-end` | 세션 마무리 — 문서 저장, 커밋, 핸드오프 프롬프트 생성 |
| `/pre-compact` | 컨텍스트 부족 시 — 중요 맥락 영속화 + compact 요약 제안 |

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

This harness automates the process of getting open-source AI models running on Google Colab:
- **Recipe system** — structured project for each porting effort
- **Notebook generator** — YAML manifest to Colab `.ipynb`
- **Claude Code hooks** — auto-validation, skill suggestions, context management
- **Colab runtime tracking** — auto-synced package snapshots for dependency planning

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

## Colab Runtime Tracking

`colab-runtimes/` auto-syncs package snapshots from [googlecolab/backend-info](https://github.com/googlecolab/backend-info).

```bash
python scripts/sync_colab_runtimes.py   # Manual sync
# GitHub Action runs daily: .github/workflows/sync-colab-runtimes.yml
```

When porting a model, check `colab-runtimes/SUMMARY.md` to find the best-matching runtime version.

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

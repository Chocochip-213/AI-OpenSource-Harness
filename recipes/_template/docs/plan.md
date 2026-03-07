# Plan

## Goal

<!-- What are you trying to achieve? Be specific. -->

## Scope

**In scope**
- <!-- Core inference / main functionality -->
- <!-- Colab compatibility patches -->

**Out of scope**
- <!-- Gradio UI, video rendering, etc. -->

## Target Environment

| Resource | Requirement |
|----------|-------------|
| GPU | <!-- A100 / T4 / L4 --> |
| VRAM | <!-- >= 24GB / >= 12GB --> |
| Python | <!-- 3.10 / 3.11 --> |
| Runtime | <!-- Colab default / 2025.07 --> |

## Approach

1. <!-- GPU/VRAM check -->
2. <!-- Clone upstream at pinned commit -->
3. <!-- Install deps (direct pip or conda) -->
4. <!-- Apply compat patches -->
5. <!-- Inference test -->

## Success Criteria

- [ ] Notebook generates without error
- [ ] Colab에서 셀 순차 실행 성공
- [ ] Pipeline/model import 성공
- [ ] Weight load 성공
- [ ] Single input -> output (결과 확인)

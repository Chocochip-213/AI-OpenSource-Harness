# Context — FLUX.2 Klein 4B Garment T-pose Conversion

## Architecture

```
Input (garment photo)
  |
  +- Phase 1: Preprocessing
  |   +- rembg: 배경 제거 -> RGBA
  |   +- 흰색 배경 합성 -> RGB
  |   +- 중앙 정렬 + 리사이즈 (1024x1024)
  |
  +- Phase 2: img2img Inference
  |   +- Flux2KleinPipeline (4B distilled, bfloat16)
  |   +- image= 전처리된 의류 이미지
  |   +- strength= 0.4~0.6 (denoising)
  |   +- num_inference_steps= 4 (Klein 증류)
  |   +- prompt= T-pose 변환 프롬프트
  |
  +- Phase 3: Output
      +- T-pose 의류 이미지 (PNG, 흰색 배경, 1024x1024)
```

## Model

| 항목 | 값 |
|------|-----|
| Model ID | `black-forest-labs/FLUX.2-klein-4B` |
| Parameters | 4B |
| Architecture | Rectified flow transformer |
| License | Apache 2.0 |
| Inference Steps | 4 (distilled) |
| VRAM | ~13GB (bf16), cpu_offload로 추가 절약 |
| guidance_scale | 1.0 (증류 모델 권장) |

## Prompt Engineering Strategy

BFL 공식 가이드 + fal.ai Klein 프롬프트 가이드 기반:

### 구조: Subject + Action + Style + Context
```
flat-lay photograph of a {garment_type} in T-pose position,
both sleeves spread horizontally, front view, centered on pure white background.
Same fabric texture, colors, patterns, and logos as the reference garment.
Studio lighting, soft shadows, high detail, sharp focus.
Professional product photography, 85mm lens, f/5.6.
```

### 원칙
1. **100단어 이내** — Klein은 짧은 프롬프트에 최적화
2. **자연어 서술** — 키워드 나열 대신 완전한 문장
3. **앞에 오는 단어가 더 강함** — T-pose/flat-lay를 맨 앞에
4. **No negative prompts** — FLUX.2는 negative prompt 미지원
5. **구체적 속성 바인딩** — "same colors and patterns" > 추상적 "preserve details"

### strength 가이드
- 0.3~0.4: 원본 거의 유지 — 포즈 변환 약함
- 0.45~0.55: **최적 범위** — 포즈 변환 + 디테일 보존 균형
- 0.6~0.7: 강한 변환 — 패턴/색상 드리프트 가능
- 0.7+: 원본과 무관한 이미지 생성 위험

## Colab 환경 (2026-02-23 기준)

| Package | Colab 버전 | 필요 조건 |
|---------|-----------|----------|
| torch | 2.10.0 | OK |
| diffusers | 0.36.0 | Flux2KleinPipeline 포함 확인 필요, 없으면 git HEAD |
| transformers | 5.0.0 | OK |
| huggingface-hub | 1.4.1 | OK |
| gradio | 5.50.0 | OK |

## Dependencies

| Package | Version | Notes |
|---------|---------|-------|
| torch | Colab native | CUDA 12.x+ |
| diffusers | >=0.36.0 or git HEAD | Flux2KleinPipeline |
| transformers | >=5.0.0 | text encoder |
| accelerate | >=1.12.0 | model loading |
| sentencepiece | latest | Qwen3 tokenizer |
| rembg | latest | 배경 제거 |
| gradio | >=5.0 | Web UI + API |
| Pillow | latest | 이미지 처리 |

## Key Decisions

- **4B vs 9B**: 4B 선택 — VRAM 13GB로 T4/L4에서도 동작, 속도 더 빠름, T-pose 변환에 9B 품질 불필요
- **img2img vs txt2img**: img2img — 원본 의류의 색상/패턴 보존을 위해 reference image 필수
- **rembg 전처리**: 배경 제거 후 img2img에 넣어야 의류에만 집중
- **Gradio share=True**: Colab에서 외부 API 접근을 위해 공유 URL 생성
- **strength 0.5 기본값**: 포즈 변환과 디테일 보존의 균형점

## References

- FLUX.2 Klein 4B: https://huggingface.co/black-forest-labs/FLUX.2-klein-4B
- BFL Prompting Guide: https://docs.bfl.ai/guides/prompting_guide_flux2
- fal.ai Klein Prompt Guide: https://fal.ai/learn/devs/flux-2-klein-prompt-guide
- fal.ai Klein User Guide: https://fal.ai/learn/devs/flux-2-klein-user-guide

---

> **Rule**: When a decision is made during implementation, add it to "Key Decisions" with the reasoning.

# Context — FLUX.2 Klein 9B Garment T-pose Conversion

## Architecture

```
Input (garment photo)
  |
  +- Phase 1: Preprocessing
  |   +- rembg: 배경 제거 -> RGBA
  |   +- 흰색 배경 합성 -> RGB
  |   +- 중앙 정렬 + 리사이즈 (1024x1024)
  |
  +- Phase 2: In-Context Conditioned Generation
  |   +- Flux2KleinPipeline (4B distilled, bfloat16)
  |   +- image= 전처리된 의류 이미지 (참조 토큰으로 concatenate)
  |   +- num_inference_steps= 4 (Klein 증류)
  |   +- guidance_scale= 1.0 (증류 모델)
  |   +- prompt= T-pose 변환 프롬프트
  |   NOTE: strength 파라미터 없음 — in-context conditioning 방식
  |
  +- Phase 3: Output
      +- T-pose 의류 이미지 (PNG, 흰색 배경, 1024x1024)
```

## Model

| 항목 | 값 |
|------|-----|
| Model ID | `black-forest-labs/FLUX.2-klein-9B` |
| Parameters | 9B |
| Architecture | Rectified flow transformer |
| License | Non-commercial (gated) |
| Inference Steps | 4 (distilled) |
| VRAM | ~29GB (bf16), 40GB+ GPU는 full GPU mode |
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

### In-Context Conditioning (NOT img2img)
FLUX.2 Klein은 전통적 img2img (noise → denoise) 방식이 아닌 **in-context conditioning** 사용:
- 참조 이미지가 추가 visual token으로 transformer에 concatenate됨
- `strength` 파라미터 없음 — 프롬프트로 변환 강도 제어
- 변환 정도는 프롬프트의 구체성과 참조 이미지와의 차이에 의존
- 프롬프트가 더 중요: "same fabric texture, colors, patterns" 등 명시 필수

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

- **9B 선택**: 102GB Blackwell에서 full GPU mode 가능. 9B가 4B보다 변환 품질 우수. VTON LoRA도 9B 기반
- **In-context conditioning**: FLUX.2는 전통적 img2img가 아닌 참조 이미지를 visual token으로 전달하는 방식. strength 파라미터 없음
- **rembg 전처리**: 배경 제거 후 참조 이미지로 넣어야 의류에만 집중
- **Gradio share=True**: Colab에서 외부 API 접근을 위해 공유 URL 생성
- **프롬프트 의존도 높음**: strength 대신 프롬프트로 변환 정도를 제어. "same fabric/colors/patterns" 등 구체적 바인딩 필수

## References

- FLUX.2 Klein 9B: https://huggingface.co/black-forest-labs/FLUX.2-klein-9B
- BFL Prompting Guide: https://docs.bfl.ai/guides/prompting_guide_flux2
- fal.ai Klein Prompt Guide: https://fal.ai/learn/devs/flux-2-klein-prompt-guide
- fal.ai Klein User Guide: https://fal.ai/learn/devs/flux-2-klein-user-guide

---

> **Rule**: When a decision is made during implementation, add it to "Key Decisions" with the reasoning.

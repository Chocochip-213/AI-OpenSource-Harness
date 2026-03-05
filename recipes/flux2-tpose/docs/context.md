# Context — FLUX.2 Klein 9B Garment T-pose Conversion

## Architecture

```
Input (garment photo)
  |
  +- Phase 1: VLM Auto-Captioning
  |   +- Florence-2-large-ft (florence-community, native transformers 5.x)
  |   +- <MORE_DETAILED_CAPTION> → 의류 구체적 묘사
  |   +- 원본 이미지에서 캡셔닝 (전처리 전)
  |
  +- Phase 2: Preprocessing
  |   +- 1536x1024 흰색 캔버스 중앙 배치 (70% fill)
  |   +- 배경 제거 없음 — in-context conditioning이 처리
  |
  +- Phase 3: Anchor-Delta Prompt Construction
  |   +- "Flat-lay product photograph of {VLM caption}."
  |   +- Anchor: 보존 속성 (garment type, neckline, closures, fabric...)
  |   +- Negation: "Do not add a hood. Do not change the neckline."
  |   +- Delta: "Change only the sleeve position: rotate horizontally"
  |
  +- Phase 4: In-Context Conditioned Generation
  |   +- Flux2KleinPipeline (9B distilled, bfloat16)
  |   +- image=[preprocessed] (리스트, BFL Space 패턴)
  |   +- num_inference_steps=4, guidance_scale=2.5 (distilled에서 무시됨)
  |   +- NOTE: strength 파라미터 없음
  |
  +- Phase 5: Output
      +- T-pose 의류 이미지 (PNG, 흰배경, 1536x1024)
```

## Models

| 항목 | 생성 모델 | 캡셔닝 모델 |
|------|----------|------------|
| Model ID | `black-forest-labs/FLUX.2-klein-9B` | `florence-community/Florence-2-large-ft` |
| Parameters | 9B | 0.77B |
| Class | `Flux2KleinPipeline` | `Florence2ForConditionalGeneration` |
| VRAM | ~29GB (bf16) | ~1.5GB (bf16) |
| Steps | 4 (distilled) | N/A |
| License | Non-commercial (gated) | MIT |

## Prompt Engineering — Anchor-Delta Pattern

BFL Kontext Guide + 커뮤니티 리서치 기반:

### 구조
1. **Establish reference**: VLM 캡션으로 의류를 구체적으로 명명
2. **Anchor (보존)**: 보존할 속성을 변경보다 앞에 배치
3. **Explicit negation**: "Do not add a hood" 등 부정 제약 삽입
4. **Delta (변경)**: 최소한의 포즈 변경만 지시

### 프롬프트 템플릿
```
Flat-lay product photograph of {VLM caption}.
Preserve exactly from the reference: the garment type, neckline shape,
collar construction, all closures, fabric texture, all colors, all patterns,
all logos, sleeve length, and overall proportions.
Do not add a hood. Do not change the neckline.
Do not add or remove pockets, zippers, buttons, or drawstrings.
Change only the sleeve position: rotate both sleeves outward to spread
horizontally from the shoulder seams, symmetric left and right.
Front view, centered on pure white background, fully visible, no person, no mannequin.
```

### 핵심 원칙
1. **VLM 캡션이 앵커** — 추상적 "the garment" 대신 구체적 묘사 사용
2. **보존을 변경보다 앞에** — decoder-only attention에서 앞 토큰이 더 강함
3. **명시적 부정** — FLUX.2는 negative prompt 미지원, positive에 삽입
4. **guidance_scale 무시됨** — distilled 모델에서는 프롬프트 텍스트만 유효

## Florence-2 호환 이슈 (transformers 5.x)

MiaoshouAI Florence-2 remote code가 transformers ≤4.49까지만 호환:
- `additional_special_tokens` AttributeError (processor)
- `forced_bos_token_id` AttributeError (model config)

**해결**: `florence-community/Florence-2-large-ft` 사용
- transformers 5.x 네이티브 지원 (trust_remote_code 불필요)
- `Florence2ForConditionalGeneration` + `AutoProcessor`
- `<MORE_DETAILED_CAPTION>` + `post_process_generation` 정상 동작

## Dependencies

| Package | Version | Notes |
|---------|---------|-------|
| torch | Colab native | CUDA 12.x+ |
| diffusers | git HEAD | Flux2KleinPipeline |
| transformers | >=5.0.0 | Florence2ForConditionalGeneration 네이티브 |
| accelerate | >=1.12.0 | model loading |
| sentencepiece | latest | Qwen3 tokenizer |
| gradio | >=5.0 | Web UI + API |

## Key Decisions

- **9B 선택**: 102GB Blackwell에서 full GPU mode. 4B보다 변환 품질 우수
- **VLM 자동 캡셔닝**: 맨투맨→후디, 반팔→긴팔 변환 방지. 입력 이미지를 구체적으로 묘사
- **florence-community**: MiaoshouAI PromptGen은 transformers 5.x 호환 불가
- **rembg 제거**: 불필요 — in-context conditioning이 원본 해석
- **garment_type 하드코딩 제거**: VLM 캡션이 자동으로 의류 종류 파악
- **Anchor-Delta 패턴**: 보존 먼저, 변경 나중 + 명시적 부정 제약
- **guidance_scale 무시**: distilled 모델에서는 효과 없음 (Base 9B에서만 작동)

## References

- FLUX.2 Klein 9B: https://huggingface.co/black-forest-labs/FLUX.2-klein-9B
- Florence-2-large-ft: https://huggingface.co/florence-community/Florence-2-large-ft
- BFL Kontext Prompting Guide: https://docs.bfl.ml/guides/prompting_guide_kontext_i2i
- fal.ai Klein Prompt Guide: https://fal.ai/learn/devs/flux-2-klein-prompt-guide

---

> **Rule**: When a decision is made during implementation, add it to "Key Decisions" with the reasoning.

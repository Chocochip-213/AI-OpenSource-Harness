# Context — FLUX.2 Klein 9B Garment T-pose Conversion

## Architecture

```
Input (garment photo)
  |
  +- Phase 1: VLM Auto-Captioning
  |   +- Qwen2.5-VL-3B-Instruct (bf16 + SDPA)
  |   +- 짧은 식별 캡션만: "a black long-sleeve hoodie"
  |   +- 로고/그래픽/패턴은 캡션에 포함하지 않음 (참조 이미지가 보존)
  |
  +- Phase 2: Preprocessing
  |   +- 1536x1024 흰색 캔버스 중앙 배치 (70% fill)
  |   +- 배경 제거 없음 — in-context conditioning이 처리
  |
  +- Phase 3: Anchor-Delta Prompt Construction
  |   +- "Professional flat-lay product photograph of {caption}."
  |   +- Anchor: "Preserve every visual detail exactly as shown in the reference image"
  |   +- Delta: "Both arms spread straight out, forming a T-shape"
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
| Model ID | `black-forest-labs/FLUX.2-klein-9B` | `Qwen/Qwen2.5-VL-3B-Instruct` |
| Parameters | 9B | 3B |
| Class | `Flux2KleinPipeline` | `Qwen2_5_VLForConditionalGeneration` |
| VRAM | ~29GB (bf16) | ~6GB (bf16) |
| Steps | 4 (distilled) | N/A |
| License | Non-commercial (gated) | Apache 2.0 |

## Prompt Engineering — Anchor-Delta Pattern

BFL Kontext Guide + 반복 실험 기반:

### 구조
1. **Establish reference**: VLM 캡션으로 의류 종류만 고정 (짧은 식별)
2. **Anchor (보존)**: "reference image" 기반 시각 보존 강조
3. **Delta (변경)**: 팔 방향만 지시 — 소매 길이/구조 언급 금지
4. **금지어**: "symmetric" (비대칭 강제), "sleeves fully extended" (반팔 고스트), "rotate" (왜곡)

### 프롬프트 템플릿 (현재)
```
Professional flat-lay product photograph of {caption},
laid flat on a white surface, viewed from directly above.
Both arms spread straight out to the left and right, forming a T-shape.
The garment is neatly arranged.
Preserve every visual detail exactly as shown in the reference image:
same logos, graphics, prints, fabric, neckline, closures, and proportions.
Pure white background, centered, no person, no mannequin, no hanger.
```

### 핵심 원칙
1. **캡션 = 식별만** — "a black long-sleeve hoodie" (로고/패턴 묘사 X → VLM 환각 차단)
2. **보존 = 참조 이미지 기반** — 텍스트로 디테일 묘사하면 모델이 환각 생성
3. **소매 중립** — 소매 길이/확장 언급 안 함 → 캡션의 sleeve length가 자연 반영
4. **guidance_scale 무시됨** — distilled 모델에서는 프롬프트 텍스트만 유효

## Florence-2 → Qwen2.5-VL 교체 경위

Florence-2는 transformers 5.x에서 전면 실패:
1. MiaoshouAI: remote code가 transformers ≤4.49까지만 호환
2. florence-community: lm_head.weight tying 깨짐 → 가비지 캡션
   - dtype 문제(bf16 buffer 불일치)와 별개로 weight tying 자체 미작동
   - `tie_weights()` 강제 호출로도 해결 불가
3. 근본 원인: transformers 5.x의 Florence2 weight tying 구현 버그

**최종 해결**: `Qwen/Qwen2.5-VL-3B-Instruct`로 교체
- transformers 5.x 네이티브, weight tying 문제 없음
- chat template API (apply_chat_template → processor → generate)
- bf16 + Flash Attention 2 (Blackwell 최적화)

## Dependencies

| Package | Version | Notes |
|---------|---------|-------|
| torch | Colab native | CUDA 12.x+ |
| diffusers | git HEAD | Flux2KleinPipeline |
| transformers | >=5.0.0 | Qwen2_5_VLForConditionalGeneration 네이티브 |
| flash-attn | latest | Blackwell Flash Attention 2 |
| accelerate | >=1.12.0 | model loading |
| sentencepiece | latest | Qwen3 tokenizer |
| gradio | >=5.0 | Web UI + API |

## Key Decisions

- **9B 선택**: 102GB Blackwell에서 full GPU mode. 4B보다 변환 품질 우수
- **VLM 자동 캡셔닝**: 맨투맨→후디, 반팔→긴팔 변환 방지. 입력 이미지를 구체적으로 묘사
- **Qwen2.5-VL 교체**: Florence-2 전면 실패 (lm_head weight tying 버그) → Qwen2.5-VL-3B
- **Blackwell 최적화**: flash-attn + torch.compile + bf16 텐서코어
- **rembg 제거**: 불필요 — in-context conditioning이 원본 해석
- **garment_type 하드코딩 제거**: VLM 캡션이 자동으로 의류 종류 파악
- **Anchor-Delta 패턴**: 보존 먼저, 변경 나중 + 명시적 부정 제약
- **guidance_scale 무시**: distilled 모델에서는 효과 없음 (Base 9B에서만 작동)

## References

- FLUX.2 Klein 9B: https://huggingface.co/black-forest-labs/FLUX.2-klein-9B
- Qwen2.5-VL-3B: https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct
- BFL Kontext Prompting Guide: https://docs.bfl.ml/guides/prompting_guide_kontext_i2i
- fal.ai Klein Prompt Guide: https://fal.ai/learn/devs/flux-2-klein-prompt-guide

---

> **Rule**: When a decision is made during implementation, add it to "Key Decisions" with the reasoning.

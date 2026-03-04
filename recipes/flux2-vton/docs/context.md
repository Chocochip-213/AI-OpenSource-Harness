# Context — FLUX.2 Klein 9B VTON with Size Control

## Architecture (v7 — Pipeline D: Two-Pass VTON with Mask-Based Size Control)

```
Pipeline A: Klein 9B (증류) + FITSPEC v4 (빠른 테스트용)
  Cells E-1~E-3 → F → G → H → I
  프롬프트만으로 VTON. 사이즈 제어 불가 (FITSPEC v1~v4 한계 확인).

Pipeline D: Two-Pass VTON + 마스크 기반 사이즈 제어 (주력)
  1. 공통 셋업 (Cells E-1~E-3, F):
     FITSPEC v4 입력 + 모델 로딩

  2. Q-1: Garment Pre-Scaling (SV-VTON Dual-Factor):
     garment image를 타겟 사이즈에 비례 확대
     M(1.00x) → L(1.08x) → XL(1.15x) → 2XL(1.25x)

  3. Q-2: Pass 1 — Quality VTON:
     Flux2KleinPipeline + VTON LoRA → fitted result (M 기준)
     옷 정체성(텍스처/색상/디자인) 확보

  4. Q-3: Garment Segmentation:
     SegFormer(label 4=upper-clothes) → base garment mask
     face(11), arms(14,15) 보호

  5. Q-4: SiCo Directional Dilation:
     방향별 마스크 확장:
       상단: 절대 확장 금지 (어깨 앵커)
       좌/우: delta * 8px (품/어깨 넓어짐)
       하단: delta * 12px (기장 증가)
     M(0px) → L(+8/12px) → XL(+16/24px) → 2XL(+24/36px)

  6. Q-5: Pass 2 — Image-Space Compositing:
     기하학적 garment 확대 + Poisson MIXED_CLONE
     Pass 1 garment 영역을 dilated mask bbox로 리사이즈
     callback 라텐트 블렌딩 폐기 (아우라/고스팅/색빠짐 원인)

  7. Q-7: LanPaint 폴백 (callback 실패 시 ComfyUI 대안)

삭제됨: Pipeline C (Klein+ComfyUI+LanPaint) — Pipeline D에 통합
```

---

## FITSPEC 버전 이력 (v1 → v4)

### v1: cm 절대값 직접 전달 (실패)
- **접근**: FITSPEC_JSON에 size_chart_cm(총장/어깨/가슴단면/소매) + fit_profiles + baseline_assumption을 구조화하여 프롬프트에 JSON 통째로 삽입
- **프롬프트**: `"Apply the target_size measurements (total_length 73cm, shoulder_width 64cm...)"`
- **결과**: M/L/XL/2XL이 모두 같은 핏으로 수렴. cm 숫자가 weak conditioning.
- **원인**: NeurIPS 2024 연구 — diffusion model의 text encoder는 "rudimentary numerical skills"만 보유. 수치를 물리적 치수로 시각화하지 못함.

### v2: cm → 신체 랜드마크 기반 (한계)
- **접근**: cm 차이를 신체 랜드마크 지시어로 번역. "shoulder seam drops 5cm past natural shoulder point", "hem falls to mid-hip"
- **프롬프트**: `build_fitspec_prompt()`가 `delta_chest`, `delta_shoulder` 계산 → 랜드마크 cue 생성
- **개선**: v1 대비 사이즈 차이 확실히 개선됨
- **한계**: cm 참조 잔존("5cm past"), 프롬프트 400자+ 비대, 개인 체형 미반영
- **추가 문제**: 마스크 없이 multi-reference 방식이라 옷 디자인 drift + 포즈 변경 발생. "preserve person" 지시어도 weak conditioning.

### v3: 패션 어휘 하드코딩 (개선 but 정적)
- **접근**: deep research 수행 → cm 완전 제거. 사이즈별 FASHION_MAP에 패션 매거진 어휘 하드코딩.
- **연구 근거**:
  - FLUX.2 → negative prompt 미지원 (확인)
  - FLUX.2 → prompt weighting `(word:1.5)` 미지원
  - Decoder-only LLM positional bias → 앞에 오는 단어가 더 강함
  - Qwen3 → 패션 레지스터 영어 이해 (패션 잡지/이커머스 캡션으로 학습)
  - IDM-VTON garment descriptor `[sleeve][neckline][type]` → CLIP-I 4% 향상
  - SV-VTON (2025) → 텍스트만으로 사이즈 제어 불가, 마스크 기반 공간 제어 필요
  - "fabric pooling", "bunching" > 추상적 "air gap"
- **프롬프트**: `"TRYON ... {fm['fit']}, {fm['silhouette']}, {fm['shoulders']}..."` (~60-80 words)
- **한계**: 사이즈별 묘사가 고정값 → 개인 체형(키/몸무게/어깨너비 등)을 전혀 반영하지 않음. 어깨 40cm인 사람과 50cm인 사람에게 같은 XL 옷을 입히면 실제로 완전히 다른 핏인데, 같은 프롬프트가 나옴.

### v4: 인체-의류 비율(ratio) 기반 동적 생성 (현재)
- **접근**: 인체 11개 치수 + 의류 4개 실측 → ratio 계산 → 구간별 패션 visual cue 자동 매핑
- **핵심 비율**:
  - `shoulder_ratio = garment_shoulder / body_shoulder` → 1.0=정핏, 1.15=살짝 드롭, 1.30=눈에 띄는 드롭, 1.40+=극단 드롭
  - `chest_ease = garment_flat×2 - body_chest_circ` → 0=딱맞음, 10=여유, 20=박시, 35+=텐트
  - `length_ratio = garment_length / body_torso` → 1.45=힙, 1.55=힙 아래, 1.65+=허벅지
  - `sleeve_ratio = garment_sleeve / body_arm` → 0.80=반팔, 0.95=손목, 1.05+=손 덮음
- **프롬프트 구조** (Qwen3 최적화):
  ```
  TRYON {fit}-fit garment on the same {height}cm {build}-build person.
  The reference garment worn in {fit} fit:
  {shoulder_cue}, {chest_cue}.
  {hem_cue}, {sleeve_cue}.
  {fabric_cue}.
  Garment fully worn on body.
  Preserve exact face, skin tone, hairstyle, pants, shoes, background, lighting, and pose.
  ```
- **장점**: 같은 XL이라도 키 160cm/어깨 40cm 사람과 키 185cm/어깨 50cm 사람에게 다른 시각적 묘사가 자동 생성됨

---

## Qwen3 Text Encoder 연구 결과

### 아키텍처
- **모델**: Qwen3-8B-FP8 (8.2B params, 40 layers, hidden 4096)
- **어휘**: 151,669 토큰 (BBPE), 119개 언어 (한국어 포함)
- **인코딩 과정**: chat template → tokenize → forward → **층 9/18/27 hidden states 추출** → concat → [batch, 512, 12288]
- **thinking mode OFF**: `enable_thinking=False` — 추론이 아닌 임베딩 추출 전용

### CLIP 대비 우위
| 항목 | CLIP | Qwen3 |
|------|------|-------|
| 토큰 한도 | 77 | 512 |
| 어휘 | 49K (영어 전용) | 151K (119개 언어) |
| 수량 인식 | 0.47 | 0.65 (counting benchmark) |
| 공간 이해 | 20.82 | 39.69 |
| 속성 바인딩 | 0.06 | 0.37 |
| JSON 이해 | 불가 | 네이티브 (코드/구조화 데이터 학습) |

### 프롬프트 최적화 원칙
1. **자연어 서술 > 키워드 나열** — Qwen3는 LLM이라 문맥 이해 우수
2. **앞에 오는 단어가 더 강함** — decoder-only causal attention → fit category를 맨 앞에
3. **패션 레지스터 영어** — 잡지/이커머스 어휘 (trained on fashion blogs)
4. **100단어 이내** — Klein 최적, 긴 프롬프트는 "create confusion" (BFL 공식 가이드)
5. **JSON은 시맨틱 앵커** — 프롬프트 내부가 아닌 계산 입력으로 사용하고, 출력은 자연어
6. **수치는 문맥 단서** — cm/kg를 정확히 시각화 못하지만 "175cm tall average-build person"은 체형 맥락 제공
7. **한국어 가능** — 하지만 기술 프롬프트는 영어가 더 정확 (학습 데이터 양)

---

## 모델 선택 이력

### Klein 9B (증류, 4-step) — 현재 사용
- **모델**: `black-forest-labs/FLUX.2-klein-9B`
- **LoRA**: `fal/flux-klein-9b-virtual-tryon-lora` (Apache 2.0)
- **장점**: LoRA가 이 모델 기준으로 학습됨, 구도/인물 보존 우수, 4-step 빠름
- **한계**: 핏 차이 미미 ("그나마" 수준), 마스크 없이 포즈/디자인 drift

### Klein Base 9B (비증류, 25-50 steps) — 시도 후 폐기
- **모델**: `black-forest-labs/FLUX.2-klein-base-9B`
- **시도 이유**: 증류 모델의 핏 차이 한계 극복 위해 비증류 모델 시도
- **실패 기록**:
  - **구도 미보존**: 상반신 입력 → 전신 출력. 완전히 다른 구도 생성
  - **성별 변경**: 남성 사진 입력 → 여성 특징(가슴, 붉은 입술) 생성
  - **하의 실종**: blank_bottom(gray) 3번째 reference → 하의 제거
  - **후드 벗기**: GARMENT_DESC("t-shirt") ≠ 실제 garment(hoodie) → 옷을 팔에 걸침
  - **LoRA 비호환**: LoRA는 증류 Klein 9B 기준 학습 → 비증류에서 구도 보존력 저하
- **결론**: "증류로 복귀하자" — 비증류 모델은 창의적 자유도가 높아 VTON에 부적합

### FLUX.2 [dev] (32B) — 검토만
- **모델**: `black-forest-labs/FLUX.2-dev`
- **불가 이유**: 32B → A100 80GB에서 OOM. 다른 아키텍처라 VTON LoRA 비호환.

---

## 실패 기록 (전체)

### 프롬프트 관련
| 실패 | 원인 | 해결 |
|------|------|------|
| cm 숫자 직접 전달 → 핏 차이 없음 | diffusion model의 수치 이해 한계 | ratio → visual cue 번역 (v4) |
| `(oversized:1.5)` 가중치 → 무시됨 | FLUX.2는 prompt weighting 미지원 | 자연어 강조 ("dramatically", "prominently") |
| negative prompt → TypeError | FLUX.2는 negative prompt 미지원 | 제거, positive-only 프롬프트 |
| "Editorial fashion photograph" → 여성 생성 | 패션 사진 편향 (학습 데이터) | 제거, "the same person from reference" |
| GARMENT_DESC "t-shirt" + 실제 hoodie → 벗기 | 텍스트-이미지 불일치 | GARMENT_DESC 제거, "the reference garment" |
| "a person" → 성별 변경 | 일반 지시어가 학습 편향 유발 | "the same {build}-build person" |

### 입력/출력 관련
| 실패 | 원인 | 해결 |
|------|------|------|
| blank_bottom(gray) → 하의 실종 | gray 3rd ref가 "바지 없음"으로 해석 | `blank_bottom = person_image` |
| 고정 1024×768 → 전신 출력 | 세로 긴 포맷이 전신 유도 | 입력 이미지 비율 매칭 동적 해상도 |
| Composite(Cell I) 품질 저하 | 생성 이미지 구도가 원본과 다르면 합성 불가 | 증류 모델 복귀로 구도 보존력 향상 |

### 파이프라인/모델 관련
| 실패 | 원인 | 해결 |
|------|------|------|
| FluxDifferentialImg2Img | FLUX.1 전용 community pipeline, Klein 9B(FLUX.2 아키텍처) 호환 불가 | 불가 |
| FluxInpaintPipeline | FLUX.1 Transformer class 불일치 | 불가 |
| FluxFillPipeline | FLUX.1 전용 | 불가 |
| Flux2KleinPipeline mask_image | `__call__`에 mask_image 파라미터 없음. PR #13050 미완성 | 불가 (2026-03) |
| CatVTON-FLUX | concat 방식이 해상도 절반, Fill-dev 기본 퀄리티 낮음, 색상 비일관 | Option B 삭제 |
| Klein Base 9B + LoRA | LoRA가 증류 모델 기준 학습 → 비증류에서 구도 미보존 | 증류 모델 복귀 |

### ComfyUI 관련 (Pipeline C)
| 실패 | 원인 | 해결 |
|------|------|------|
| CheckpointLoaderSimple → CLIP/VAE=None | Klein 9B safetensors에서 model만 로드 | UNETLoader + CLIPLoader + VAELoader 분리 |
| DualCLIPLoader(type:flux) | FLUX.1용 dual encoder, Klein 9B는 Qwen3 단일 | CLIPLoader(type:flux2) 단일 |
| CLIPTextEncodeFlux | CLIP=None이라 tokenize 에러 | CLIPTextEncode 표준 노드 |
| Qwen3 4-shard HF format | ComfyUI CLIPLoader는 단일 safetensors만 | Cell O-1에서 4개 샤드 → 1개 병합 |
| Garment composite → 사람 흰색 | composite 로직이 garment를 마스크 bbox에 강제 리사이즈 → 왜곡 | Person 이미지 직접 VAEEncode |

---

## Dependencies

| Package | Version | Notes |
|---------|---------|-------|
| torch | Colab native (2.x) | CUDA 12.x+ |
| diffusers | git HEAD or >=0.32.0 | Flux2KleinPipeline 필요 |
| transformers | >=4.47.0 | Qwen3 tokenizer + SegFormer |
| accelerate | >=1.2.0 | 모델 로딩 |
| sentencepiece | latest | Qwen3 text encoder |
| peft | >=0.14.0 | LoRA fuse/unfuse |
| sam2 | latest | SAM2 Image Predictor (Pipeline C) |
| onnxruntime-gpu | latest | DWPose ONNX 추론 (Pipeline C) |
| ComfyUI | latest | Pipeline C: headless 서버 |
| LanPaint | latest | Pipeline C: training-free inpainting sampler |

## Key Decisions

### 기본 인프라
- **Flux2KleinPipeline probe-upgrade 패턴** — stable PyPI에 없을 수 있어 Cell B에서 try/except → git HEAD 설치 → SIGKILL(Colab 재시작).
- **Multi-reference 3장 입력** — Klein 9B Edit: `image=[person, garment, person]`. 3번째 ref는 person_image 자체 (gray placeholder 사용 시 하의 실종).
- **LoRA fuse 전략** — `fuse_lora()` + `unload_lora_weights()` → PEFT 오버헤드 제거.
- **`total_memory` 속성** — PyTorch `total_mem` 아닌 `total_memory` 사용.
- **동적 해상도** — 입력 이미지 비율 매칭. 고정 1024×768은 전신 출력 유발.

### FITSPEC v4 설계 결정
- **인체 치수 11개 수집** — 키/몸무게/어깨너비/어깨둘레/가슴둘레/골반너비/골반둘레/팔길이/다리길이/몸통길이/인신길이. 비율 계산의 분모 역할.
- **의류 실측 4개** — 총장/어깨/가슴단면/소매. 무신사 등 이커머스에서 수집 가능한 표준 항목.
- **ratio → visual cue 자동 매핑** — cm 절대값이 아닌 비율 구간별 패션 어휘 생성. 같은 XL이라도 체형에 따라 다른 프롬프트.
- **fit_profiles 보조 역할** — 핏/촉감/신축/비침/두께/계절감은 fabric behavior cue로만 사용. 주요 시각 차이는 ratio에서.
- **JSON은 계산 입력** — 프롬프트 안에 JSON 삽입하지 않음. JSON으로 ratio 계산 후 자연어 프롬프트만 출력.
- **BMI 기반 체형 분류** — slim/average/athletic/broad → 프롬프트에 build descriptor로 포함.

### Composite Pipeline (Cell I)
- SegFormer B2 Clothes: label 4 = upper-clothes (IoU 0.78)
- Exclude face(11), arms(14,15) with dilated buffer
- Erode → feather → Poisson seamlessClone
- **한계**: 생성 이미지 구도가 원본과 다르면 합성 품질 저하. 증류 모델의 구도 보존력에 의존.

### Pipeline D 설계 결정 (v7)
- **3개 독립 리서치 교차검증** — Claude/GPT/Gemini 모두 "프롬프트만으로 사이즈 제어 불가, 마스크/공간 제어 필수" 결론.
- **Two-Pass 아키텍처** — Pass 1(품질 확보) → Pass 2(사이즈 강제). 단일 패스로는 품질+사이즈 동시 제어 불가.
- **SV-VTON Dual-Factor** — 마스크 확장 + garment 비례 확대 두 축 동시 조작. 마스크만으로는 빈 공간, 스케일만으로는 효과 미미.
- **SiCo 방향별 확장** — 상단 고정(어깨 앵커) + 좌/우/하단만 확장. 균일 확장은 옷이 떠보이는 현상 발생.
- **callback_on_step_end (v2 fix)** — FLUX.2는 packed latent `[B, (H/16)*(W/16), C*4]` 사용. 초기 구현은 `dim==3`에서 no-op → garment drift + 핏 동일. 수정: spatial→packed 변환 후 sequence-space masking. Flow-matching: `(1-σ)*x₀ + σ*noise`. Fallback: image-space warp + Poisson.
- **garment identity 보존** — Pass 2에서 `build_size_refinement_prompt` (별도 함수) 대신 `build_fitspec_prompt(size_override=TARGET)` 사용. 원본 garment image 유지 (scaled garment 제거). 마스크만으로 사이즈 제어.
- **Double-VTON 방지 (v3 fix)** — Pass 2 입력을 `image=[pass1_result, garment, pass1_result]` → `image=[person_image, garment, person_image]`로 변경. Pass 1 결과(이미 옷 입은 사람)를 다시 VTON 모델에 넣으면 덧씌우기 효과(원래 옷 비침, 색상 희석) 발생. 원본 person 사용 + callback이 마스크 밖을 Pass 1 latent로 보존하므로 동일 효과.
- **Sigma 정합 (v3 fix)** — callback_on_step_end는 `scheduler.step()` 이후 실행 → latents가 NEXT sigma 레벨. `timestep.float()` (현재 스텝)로 원본 노이징하면 레벨 불일치 → 고스팅. 수정: `scheduler.sigmas[step_index]` 사용 (step 후 증가된 인덱스 = 다음 sigma).
- **"zipped up" 제거 (v3 fix)** — `build_fitspec_prompt`에 하드코딩된 "zipped up and properly fitted"가 후드를 지퍼 후드집업으로 변환. "properly fitted"만 유지.
- **Arm/Face 보호 (v2 fix)** — SiCo dilation이 팔 영역까지 확장 → 소매 잘림. Q-3에서 `PROTECT_MAP` (dilated arms+face) 저장 → Q-4에서 dilation 후 + Gaussian blur 후 2회 제외.
- **callback_on_step_end 폐기 (v4 fix)** — 4차례 시도 실패: (1) packed latent NO-OP → 핏 동일, (2) sigma 불일치 → 고스팅, (3) double-VTON → 오버레이/색빠짐, (4) 근본적으로 두 디노이징 경로를 라텐트 공간에서 합치면 seam/아우라 불가피. → **이미지 공간 합성**으로 전환: Pass 1 garment bbox를 dilated bbox로 기하학적 리사이즈 + Poisson MIXED_CLONE. 추가 diffusion 추론 없음.
- **Pipeline C 삭제** — Pipeline D가 마스크 기반 접근을 더 나은 방식으로 통합. ComfyUI는 Q-7 폴백으로만 최소 사용.

### 사이즈 제어 리서치 결론 (3개 교차검증)
| 개념 | Claude | GPT | Gemini |
|------|--------|-----|--------|
| 프롬프트만으로 사이즈 제어 불가 | O | O | O |
| 마스크 dilation = 사이즈 제어 | O (SV-VTON) | O (SiCo) | O |
| 방향별 확장 (상단 고정) | O (SiCo λ) | O (SiCo) | O |
| Garment 비례 확대 | O (SV-VTON dual) | O (노브B) | O |
| Two-pass pipeline | O | O | O |

---

## References

- FLUX.2 Klein: https://huggingface.co/black-forest-labs/FLUX.2-klein-9B
- FLUX.2 Klein Base: https://huggingface.co/black-forest-labs/FLUX.2-klein-base-9B
- VTON LoRA: https://huggingface.co/fal/flux-klein-9b-virtual-tryon-lora
- FLUX.2 Klein Prompting Guide: https://docs.bfl.ml/guides/prompting_guide_flux2_klein
- FLUX.2 Prompt Guide (fal.ai): https://fal.ai/learn/devs/flux-2-klein-prompt-guide
- Qwen3-8B: https://huggingface.co/Qwen/Qwen3-8B
- FLUX.2 Text Encoders (DeepWiki): https://deepwiki.com/black-forest-labs/flux2/3.2-text-encoders
- LLM Text Encoder for Diffusion (arXiv): https://arxiv.org/html/2406.11831v1
- Decoder-Only LLM as Controller (arXiv): https://arxiv.org/html/2502.04412v1
- CatVTON-FLUX: https://github.com/nftblackmagic/catvton-flux
- SegFormer B2: https://huggingface.co/mattmdjaga/segformer_b2_clothes
- LanPaint: https://github.com/scraed/LanPaint
- Klein Inpaint PR: https://github.com/huggingface/diffusers/issues/13005
- SAM2: https://github.com/facebookresearch/sam2
- NeurIPS 2024 (numerical skills): referenced in SV-VTON analysis

---

> **Rule**: When a decision is made during implementation, add it to "Key Decisions" with the reasoning.
> This file is the permanent record — don't let knowledge stay only in chat history.

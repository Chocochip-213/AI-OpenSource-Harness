# Context Pack

**Active Recipe**: `flux2-vton`
**Generated**: auto

## Recipe Docs

### plan.md

```
# Plan — FLUX.2 Klein 9B Virtual Try-On with Size Control

## Goal
FLUX.2 Klein 9B + VTON LoRA를 사용하여 person image에 garment를 입히되,
**마스크 기반 공간 제어**로 사이즈/핏을 강제한다.

FITSPEC v1→v4 프롬프트 엔지니어링만으로는 사이즈 제어 불가능 확인됨.
3개 독립 리서치(Claude/GPT/Gemini) 모두 동일한 결론:
> **사이즈 제어 = 공간/마스크 제어. 텍스트 제어 불가.**

## Scope

### In scope
- **Pipeline A**: Prompt-Only (FITSPEC v4, 빠른 테스트용, 사이즈 제어 없음)
- **Pipeline D**: Two-Pass VTON (주력)
  - Pass 1: 품질 VTON (옷 정체성 확보)
  - SV-VTON: garment image 비례 확대
  - SiCo: 방향별 마스크 확장 (상단 고정, 좌/우/하단 확장)
  - Pass 2: callback_on_step_end 라텐트 마스킹 (사이즈 강제)
  - 4-Size 비교 그리드 (M/L/XL/2XL)
- LanPaint 폴백 (callback 실패 시 ComfyUI 대안)
- Colab A100 80GB 최적화

### Out of scope
- 하의(바지/스커트) VTON (탑 전용)
- 비디오 VTON
- Size-Conditioned LoRA 학습 (Phase 5 장기)
- Warp-to-Diffusion (Phase 5 장기)

### 삭제됨
- ~~Pipeline C (Klein+ComfyUI+LanPaint)~~ — Pipeline D에 통합
- ~~FITSPEC 프롬프트만으로 사이즈 제어~~ — 불가능 확인

## Approach
1. **Pass 1**: Flux2KleinPipeline + VTON LoRA → fitted VTON (M 사이즈 기준)
2. **SV-VTON Dual-Factor**: garment image를 타겟 사이즈에 비례 확대
3. **SegFormer**: Pass 1 결과에서 garment mask 추출 (label 4)
4. **SiCo Dilation**: 방향별 마스크 확장 (상단 고정 = 어깨 앵커)
5. **Pass 2**: callback_on_step_end로 마스크 밖 보존 + 마스크 안 재생성
6. **4-Size Grid**: M→2XL 루프로 사이즈별 결과 비교

## Success Criteria
1. Cell F: 모델 로드 OOM 없이 완료 (A100 80GB)
2. Q-2: Pass 1 → fitted VTON 정상 생성
3. Q-3: SegFormer → garment mask 추출 확인 (mask > 5%)
4. Q-4: SiCo dilation → M < L < XL < 2XL 마스크 면적 증가
5. Q-5: Pass 2 → callback 또는 fallback 정상 작동
6. Q-6: 4-size 그리드 → M < L < XL < 2XL 실루엣 크기 증가 확인
```

### context.md

```
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
... (212 more lines)

```

### tasks.md

```
# Tasks — FLUX.2 Klein 9B VTON with Size Control

## Setup
- [x] Copy _template to `recipes/flux2-vton`
- [x] recipe.yaml, requirements, install.sh, run.sh
- [x] docs triad (plan.md, context.md, tasks.md)

## Common Cells (Pipeline A/D 공통)
- [x] Cells Header~C: GPU/deps/auth
- [x] Cells D: Image upload (person + garment)
- [x] PIPELINE 토글 파라미터 (Global Settings: A/D 선택)

## FITSPEC Evolution
- [x] FITSPEC v1: cm 절대값 JSON → weak conditioning 실패
- [x] FITSPEC v2: cm→랜드마크 + contrast cue → 개선되었으나 프롬프트 비대
- [x] FITSPEC v3: 패션 어휘 하드코딩 → 체형 미반영 한계
- [x] FITSPEC v4: 인체 치수(11개) + 의류 실측(4개) → ratio 기반 동적 프롬프트

## Pipeline A: Klein 9B Prompt-Only (if PIPELINE == "A")
- [x] Cell E-1: Body Measurements 입력 폼
- [x] Cell E-2: Garment Size Chart + fit_profiles
- [x] Cell E-3: build_fitspec_prompt() v4 — ratio→visual cue 변환
- [x] Cell F: Klein pipeline load + LoRA fuse
- [x] Cell G: Single inference (v4 prompt, dynamic resolution)
- [x] Cell H: 4-Size grid (v4: body-garment ratio)
- [x] Cell I: Composite post-processing (SegFormer + Poisson)

## Pipeline D: Two-Pass VTON (if PIPELINE == "D") — 주력
- [x] Q-0: Pipeline D Setup (SegFormer 로드 + 헬퍼 함수)
- [x] Q-1: Garment Pre-Scaling (SV-VTON dual-factor)
- [x] Q-2: Pass 1: Quality VTON (fitted result)
- [x] Q-3: Garment Segmentation (SegFormer label=4)
- [x] Q-4: SiCo Directional Dilation (방향별 마스크 확장)
- [x] Q-5: Pass 2: Size-Aware Re-Inpainting (callback_on_step_end)
- [x] Q-6: 4-Size Comparison Grid (M/L/XL/2XL)
- [x] Q-7: Pass 2 ALT: LanPaint Fallback

## 삭제됨: Pipeline C (Klein+ComfyUI+LanPaint)
- ~~Cells J-0~J-4: SAM2+DWPose 마스크 생성~~ → Pipeline D에 SegFormer 통합
- ~~Cells O-0~O-5: ComfyUI+LanPaint 인페인팅~~ → Q-7 폴백으로 최소 잔존

## 삭제됨: Option B (CatVTON-FLUX)
- ~~Cell K~M: CatVTON 파이프라인~~ — 색상/품질 부족으로 삭제

## 모델 선택 이력
- [x] Klein 9B (증류) — 최초 선택, LoRA 기준 모델
- [x] Klein Base 9B (비증류) 시도 → 구도 미보존/성별 변경/하의 실종 → 폐기
- [x] Klein 9B (증류) 복귀 — VTON LoRA 호환성 + 구도 보존

## 사이즈 제어 리서치
- [x] Claude/GPT/Gemini 3개 독립 리서치 → "프롬프트만으로 사이즈 제어 불가" 결론
- [x] SV-VTON, SiCo, FitControler, COTTON, QuantFit-VTON → 전부 마스크/레이아웃 기반
- [x] Pipeline D 아키텍처 설계 (Two-Pass + SiCo + callback)

## Validation
- [ ] YAML 검증 통과
- [ ] .ipynb 생성 완료
- [ ] smoke_test 통과
- [ ] Colab 테스트: Q-0→Q-2→Q-3→Q-4→Q-5→Q-6 실행

... (3 more lines)

```

## Git Status

```
M .claude/_context_pack.md
 M .claude/_edited_files.log
 M outputs/notebooks/flux2-vton.ipynb
 M recipes/flux2-vton/notebook_manifest.yaml
?? .claude/hooks/__pycache__/
?? __pycache__/
?? recipes/flux2-vton/patches/
?? "recipes/flux2-vton/research/\353\240\210\354\240\204\353\223\234\355\225\251\354\204\261\354\260\220\353\271\240.png"
?? recipes/swifttry/patches/__pycache__/
?? scripts/__pycache__/
?? tools/__pycache__/
```

## Git Diff (stat)

```
.claude/_context_pack.md                  |  15 +-
 .claude/_edited_files.log                 |   4 +
 outputs/notebooks/flux2-vton.ipynb        | 688 +++++++++---------------------
 recipes/flux2-vton/notebook_manifest.yaml | 678 +++++++++--------------------
 4 files changed, 413 insertions(+), 972 deletions(-)
```

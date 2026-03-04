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

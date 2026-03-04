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

---

> Check off each task upon completion. Record decisions in context.md.

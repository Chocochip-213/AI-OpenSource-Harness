# Plan — FLUX.2 Klein 4B Garment T-pose Conversion

## Goal
단일 의류 사진(평면촬영, 행거샷, 착용샷 등)을 입력받아 **T-pose 형태의 정면 의류
이미지**로 변환하는 Colab 기반 Gradio API 서비스.

변환된 T-pose 이미지는 후속 3D 메시 생성 파이프라인(Hunyuan3D-2mini)의 입력으로 사용됨.

## Scope

### In scope
- FLUX.2 Klein 4B (증류, 4-step) img2img 파이프라인
- rembg 기반 배경 제거 전처리
- T-pose 변환 프롬프트 엔지니어링
- Gradio 웹 UI + API 엔드포인트 (share=True)
- Colab A100/L4/T4 GPU 지원 (cpu_offload로 VRAM 절약)
- strength(denoising) 파라미터 조절 (0.4~0.6)

### Out of scope
- VTON (가상 착용) — 별도 flux2-vton 레시피
- 3D 메시 생성 (후속 파이프라인)
- LoRA 학습/파인튜닝
- 비디오 변환

## Approach
1. **배경 제거**: rembg로 의류만 추출 -> 흰 배경에 센터링
2. **img2img 변환**: Flux2KleinPipeline + 프롬프트로 T-pose 변환
   - strength 0.4~0.6: 원본 디테일 보존 vs 포즈 변환 균형
   - 4 steps (Klein 증류 모델이므로 충분)
3. **프롬프트 엔지니어링**: BFL 가이드 기반 Subject+Action+Style+Context 구조
4. **Gradio 서비스**: 업로드 -> 전처리 -> 추론 -> 결과 반환 (API 모드 포함)

## Success Criteria
1. Colab에서 모델 로드 OOM 없이 완료
2. rembg 배경 제거 정상 동작
3. T-pose 변환: 양팔 수평 펼침 + 정면 시점 + 원본 색상/패턴 인식 가능
4. Gradio API 엔드포인트로 외부에서 호출 가능
5. 추론 시간: 1장당 10초 이내

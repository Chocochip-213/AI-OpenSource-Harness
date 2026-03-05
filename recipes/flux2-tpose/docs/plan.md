# Plan — FLUX.2 Klein 9B Garment T-pose Conversion

## Goal
단일 의류 사진(평면촬영, 행거샷, 착용샷 등)을 입력받아 **T-pose 형태의 정면 의류
이미지**로 변환하는 Colab 기반 Gradio API 서비스.

변환된 T-pose 이미지는 후속 3D 메시 생성 파이프라인(Hunyuan3D-2mini)의 입력으로 사용됨.

## Scope

### In scope
- FLUX.2 Klein 9B (증류, 4-step) img2img 파이프라인
- rembg 기반 배경 제거 전처리
- T-pose 변환 프롬프트 엔지니어링
- Gradio 웹 UI + API 엔드포인트 (share=True)
- Blackwell 102GB full GPU mode / A100 80GB 지원 (40GB 미만 시 cpu_offload)
- 프롬프트 엔지니어링으로 변환 정도 제어 (in-context conditioning 방식)

### Out of scope
- VTON (가상 착용) — 별도 flux2-vton 레시피
- 3D 메시 생성 (후속 파이프라인)
- LoRA 학습/파인튜닝
- 비디오 변환

## Approach
1. **배경 제거**: rembg로 의류만 추출 -> 흰 배경에 센터링
2. **In-context conditioned 변환**: Flux2KleinPipeline + 프롬프트로 T-pose 변환
   - 참조 이미지를 visual token으로 전달 (전통적 img2img가 아닌 in-context conditioning)
   - 4 steps (Klein 증류 모델이므로 충분), guidance_scale=1.0
3. **프롬프트 엔지니어링**: BFL 가이드 기반 Subject+Action+Style+Context 구조
4. **Gradio 서비스**: 업로드 -> 전처리 -> 추론 -> 결과 반환 (API 모드 포함)

## Success Criteria
1. Colab에서 모델 로드 OOM 없이 완료
2. rembg 배경 제거 정상 동작
3. T-pose 변환: 양팔 수평 펼침 + 정면 시점 + 원본 색상/패턴 인식 가능
4. Gradio API 엔드포인트로 외부에서 호출 가능
5. 추론 시간: 1장당 10초 이내

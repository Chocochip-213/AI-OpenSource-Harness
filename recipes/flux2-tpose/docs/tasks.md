# Tasks — FLUX.2 Klein 9B Garment T-pose Conversion

## Setup
- [x] Copy _template to `recipes/flux2-tpose`
- [x] SSOT docs triad (plan.md, context.md, tasks.md)
- [x] recipe.yaml
- [x] requirements_opt1.txt
- [x] install.sh, run.sh

## Notebook Cells
- [x] Cell A: GPU Check + VRAM 확인
- [x] Cell B: Dependencies 설치 (diffusers probe-upgrade + SIGKILL 재시작)
- [x] Cell C: HuggingFace Auth (토큰)
- [x] Cell D: Model Loading (Flux2KleinPipeline, VRAM 자동 분기)
- [x] Cell D2: Florence-2 Captioner (florence-community/Florence-2-large-ft)
- [x] Cell E: Preprocessing + Auto-Captioning 함수
- [x] Cell F: VLM-Guided Prompt Builder (Anchor-Delta 패턴)
- [x] Cell G: Single Inference Test (캡셔닝 → 프롬프트 → 추론)
- [x] Cell H: Gradio App + API Endpoint

## Notebook Generation
- [x] notebook_manifest.yaml 작성
- [x] .ipynb 생성 완료 (outputs/notebooks/flux2-tpose.ipynb)

## API Fix (2026-03-05 Session 1)
- [x] Flux2KleinPipeline API 검증: strength 파라미터 존재하지 않음 확인
- [x] In-context conditioning 방식으로 노트북 수정 (strength 제거)
- [x] 4B → 9B 전환
- [x] 1024x1024 → 1536x1024 (소매 공간 확보)
- [x] garment_type 하드코딩 제거
- [x] rembg 배경제거 제거

## VLM Captioning + Prompt Rewrite (2026-03-05 Session 2)
- [x] 맨투맨→후디, 반팔→긴팔 변환 문제 진단
- [x] Florence-2 VLM 자동 캡셔닝 도입
- [x] Anchor-Delta 프롬프트 패턴 적용
- [x] guidance_scale이 distilled에서 무시됨 확인
- [x] Florence-2 transformers 5.x 호환 이슈 해결 (3단계 디버깅)
- [x] florence-community 네이티브 체크포인트로 최종 전환
- [x] Colab 로드 + 추론 동작 확인

## Validation
- [x] smoke_test 통과
- [x] Colab 테스트: 모델 로드 동작 확인
- [ ] 의류 종류 보존 품질 확인 (맨투맨→맨투맨, 반팔→반팔)
- [ ] T-pose 변환 포즈 정확도 확인
- [ ] Gradio API 엔드투엔드 테스트

---

> Check off each task upon completion. Record decisions in context.md.

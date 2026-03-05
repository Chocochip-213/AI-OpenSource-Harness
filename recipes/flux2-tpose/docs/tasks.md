# Tasks — FLUX.2 Klein 4B Garment T-pose Conversion

## Setup
- [x] Copy _template to `recipes/flux2-tpose`
- [x] SSOT docs triad (plan.md, context.md, tasks.md)
- [x] recipe.yaml
- [x] requirements_opt1.txt
- [x] install.sh, run.sh

## Notebook Cells
- [x] Cell A: GPU Check + VRAM 확인
- [x] Cell B: Dependencies 설치 (diffusers probe-upgrade 포함)
- [x] Cell C: HuggingFace Auth (토큰)
- [x] Cell D: Model Loading (Flux2KleinPipeline + cpu_offload)
- [x] Cell E: Preprocessing (rembg 배경 제거 + 흰배경 합성)
- [x] Cell F: Prompt Engineering (T-pose 변환 프롬프트 빌더)
- [x] Cell G: Single Inference Test (img2img T-pose 변환)
- [x] Cell H: Gradio App + API Endpoint

## Notebook Generation
- [x] notebook_manifest.yaml 작성
- [x] .ipynb 생성 완료 (outputs/notebooks/flux2-tpose.ipynb)

## Validation
- [x] smoke_test 통과
- [ ] Colab 테스트: 모델 로드 -> 추론 -> Gradio API 동작 확인

---

> Check off each task upon completion. Record decisions in context.md.

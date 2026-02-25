# Context Pack

**Active Recipe**: `swifttry`
**Generated**: auto

## Recipe Docs

### plan.md

```
# Plan — SwiftTry

## Goal
Colab-ready inference recipe for **SwiftTry** (AAAI 2025): given a person video and a garment image, produce a try-on result video using diffusion-based video inpainting.

## Scope
**In scope**
- Video virtual try-on inference (`inference.py`)
- Automated weight download (5 HF repos + SD-Inpainting)
- Two install strategies: opt2_modern (default) / opt1_legacy (fallback)
- A100 notebook with user-configurable data paths

**Out of scope**
- Training (Stage 1 / Stage 2)
- Dataset redistribution (TikTokDress, VVT)
- Training (Stage 1 / Stage 2)와 데이터셋 전처리 파이프라인 (별도 도구)
- Image-only try-on (`inference_image.py`)

## Approach
1. Clone upstream at pinned commit SHA
2. Install deps via opt2_modern (keep Colab torch, install compatible diffusers stack)
3. Download weights via upstream `tools/download_weights.py` + separate SD-Inpainting snapshot
4. Symlink `weights/tiktokdress -> pretrained_sd_models/swift_try` to bridge config path mismatch
5. User provides DATA_DIR with pre-processed videos; notebook runs `inference.py`
6. User 모드: 업로드된 동영상/의류에 대해 DWPose + SegFormer 기반 자동 전처리 (포즈 추출, 마스크 생성)

## Success Criteria
- `install.sh` completes without error on fresh Colab A100 runtime
- `python tools/download_weights.py` downloads all 5 weight sets
- `python inference.py --data_dir ... --test_pairs ... --save_dir ...` produces output MP4s
- Notebook cells run top-to-bottom with only DATA_DIR edit required
```

### context.md

```
# Context — SwiftTry

## Architecture
SwiftTry reconceptualizes video virtual try-on as **conditional video inpainting** using Stable Diffusion v1.5.

```
Input: person video (.mp4) + garment image (.png)
  |
  +-- ReferenceUNet (2D) --- encodes garment appearance
  +-- DenoisingUNet (3D)  --- diffusion backbone with motion modules
  +-- PoseGuider          --- DWPose skeleton conditioning
  +-- CLIP Image Encoder  --- visual features
  +-- VAE (SD-vae-ft-mse) --- encode/decode latent frames
  |
Output: try-on video (.mp4)
```

Inference pipeline: `src.pipelines.pipeline_swift_try.TryOnVideoPipeline`
- 25 DDIM steps, CFG scale 3.5, v-prediction, zero-SNR
- Context window: 16 frames, fp16 precision
- Repaint mode: blend result with original via gaussian-blurred mask

## Dependencies
Colab baseline as of 2026-01-20: torch 2.9.0, torchvision 0.24.0, torchaudio 2.9.0, diffusers 0.36.0, accelerate 1.12.0, numpy 2.x, peft 0.18.1, xformers (matched).

| Package | opt2_modern | opt1_legacy | Notes |
|---------|-------------|-------------|-------|
| torch | Colab native (2.9.0) | 2.0.1 | opt1 CUDA 11.8 binary — extreme risk on Colab CUDA 12.x |
| diffusers | 0.24.0 (downgrade) | 0.24.0 | Pinned — upstream uses private UNet APIs removed in 0.25+ |
| transformers | >=4.30.2,<4.46 | 4.30.2 | |
| accelerate | >=0.21.0 (Colab has 1.12.0) | 0.21.0 | |
| xformers | auto (match torch 2.9) | 0.0.22 | Must match torch+CUDA exactly |
| onnxruntime-gpu | latest | 1.16.3 | DWPose ONNX inference |
| clip | GitHub SHA pin | GitHub SHA pin | OpenAI CLIP archive |

## Key Decisions
- **opt2_modern as default** — Colab pre-installs torch with matching CUDA; downgrading is high-risk and slow. We keep native torch and install compatible satellite packages.
- **Upstream ref pinned to SHA `57d3f0b`** — Ensures reproducibility; master HEAD as of 2026-02-24.
- **SD-Inpainting downloaded separately** — `download_weights.py` omits `runwayml/stable-diffusion-inpainting` but it's required by all inference configs (`pretrained_base_model_path`). We add a `snapshot_download` step.
- **Weight path symlink** — Config `tryon_video_tiktok.yaml` expects `weights/tiktokdress/` but `download_weights.py` saves to `pretrained_sd_models/swift_try/`. Symlink bridges the gap without patching config files.
- **diffusers NOT pinned — patched instead** — Upstream uses diffusers 0.24.0 internal APIs, but downgrading on Colab causes massive dependency collapse (torch/accelerate/etc all conflict). Instead we keep Colab's diffusers 0.36.0 and apply `patches/fix_diffusers_compat.py` which fixes 5 breaking imports: CaptionProjection rename, AdaLayerNorm move, ADDED_KV/CROSS_ATTENTION_PROCESSORS removal, DualTransformer2DModel path change, LoRA compat classes.
- **numpy 건드리지 않음** — Colab torch 2.9.0은 numpy 2.x ABI로 빌드됨. numpy<2.0으로 다운그레이드 시 `dtype size changed` 크래시 발생. Colab 기본값 유지 필수.
- **Colab 기본 패키지 핀 금지** — scipy, scikit-learn, tqdm, Pillow 등 Colab 프리인스톨 패키지를 구버전으로 핀하면 의존성 충돌 대량 발생 (giddy, spopt, jax, shap 등과 충돌). 없는 패키지만 설치.
- **torchsde>=0.2.6** — 0.2.5는 메타데이터 오류로 pip>=24.1에서 설치 불가.
- **CLIP: open-clip-torch + ftfy** — OpenAI CLIP 직접 빌드 대신 open-clip-torch 사용 (빌드 실패 회피).
- **User 모드 입력 해상도: W=384, H=512** — SwiftTry Stage2 학습 해상도(configs/train/stage2_tiktok_sam2mask.yaml)와 추론 해상도(configs/prompts/tryon_video_tiktok.yaml) 정확히 일치. 이전 256x256은 학습 해상도의 절반 미만으로 텍스트/로고 환각 심화 (latent 32x32→로고 ~5x2px). 384x512에서 latent 48x64→로고 ~10x4px으로 디테일 보존 개선. inference.py가 내부적으로 이 해상도로 리사이즈하므로 입력도 동일하게 맞춤.
- **User 모드 마스크: SegFormer 퍼-프레임 시맨틱 세그멘테이션** — SAM2 기반 마스킹 3차례 시도 후 구조적 한계로 교체. SAM2 Video Predictor는 네거티브 포인트 프롬프트를 무시하여 얼굴/머리카락이 항상 마스크에 포함됨. Image Predictor→Video Predictor 전파 방식도 전파 시 마스크 drift 발생. 키포인트 기반 팔 추정은 팔 붙이고 있을 때 비율 이상. **해결**: `mattmdjaga/segformer_b2_clothes` (transformers 내장) 퍼-프레임 추론. 18-class 시맨틱 레이블로 얼굴(11)/머리카락(2) 구조적 제외, 팔(14=L-arm, 15=R-arm) 픽셀 정확 세그멘테이션. TARGET_LABELS={4,7,14,15} (upper-clothes, dress, left-arm, right-arm). 3프레임 rolling median 시간적 스무딩 + dilation 5회. SAM2 대비: 추가 의존성 없음, VRAM ~850MB (vs ~2GB), 속도 ~15초/200프레임 (vs ~70초), 코드량 ~80줄 (vs ~360줄).
- **SegFormer 마스크 후처리 정상화** — 이전에 가상옷 수축 문제를 마스크 후처리로 과보상(binary_closing, dilation 12, kernal_size=1). 근본 원인 분석 결과 **DWPose stickwidth=4**가 최유력 — 포즈 스켈레톤이 garment 실루엣의 유일한 공간 블루프린트. 과보상 제거: binary_closing 삭제, dilation 12→5 복원, kernal_size sed 패치 삭제(업스트림 기본값 h//50 유지). **consensus mask는 유지** — 프레임별 SegFormer 예측 불일치로 중앙 아랫배 구멍 문제를 해결하는 별개 역할. 최종 파이프라인: temporal median → consensus union → `binary_fill_holes` → `binary_dilation(5)`.
- **stickwidth 파라미터화 (효과 없음 확인)** — DWPose `stickwidth`(업스트림 기본=4)를 Colab form 파라미터로 노출 (4/8/12/16). 4→8→12 실험 결과 가상옷 크기에 변화 없음. stickwidth는 시각화 두께만 변경하며, inference.py는 DWPose 시각화를 PoseGuider 입력으로 사용하나 공간 블루프린트보다는 관절 위치 가이드 역할. 파라미터는 실험용으로 유지하되 가상옷 수축의 원인이 아님을 확인.
- **REPAINT_KERNEL 파라미터화 (기본값 1)** — inference.py의 repaint gaussian blur. H-3에 Colab form 파라미터 추가. 1=하드엣지, 3=최소 소프트닝, 10≈업스트림 기본. 단, 이것만으로는 가상옷 수축 미해결 (블러는 부차적 요인).
- **마스크 경로 불일치 — model input vs repaint (근본 원인 가설)** — inference.py 내부에서 마스크가 두 갈래로 분기: (1) `prepare_mask_and_masked_image()`에서 `>= 0.5` binarize → model input, (2) `repaint()`에서 원본 PIL mask → GaussianBlur → 연속값 블렌딩. mp4 H.264 손실 압축 + Pillow BICUBIC resize가 binary mask 경계에 gray 중간값 생성 → binarize 시 gray 픽셀(<128)이 0으로 탈락하여 model이 인페인트하지 않으나, repaint는 같은 gray 픽셀을 연속값으로 사용하여 인페인트 안 된 영역이 부분 노출 → "가상옷보다 마스크가 큰" 갭 발생. **Fix**: (A) `REPAINT_BINARIZE=True` — repaint 직전 `mask.point(>=128→255, else 0)` binarize로 두 경로 일치, (B) `MASK_RESIZE_NEAREST=True` — mask resize를 NEAREST로 강제하여 gray 경계 생성 방지. H-2.5 진단 셀로 면적 차이/히스토그램/시각화 검증 가능. git checkout → Python patching으로 멱등성 보장.
- **얼굴/목 영역 제외** — SegFormer upper-clothes 레이블(4)이 칼라/목선을 포함하고 dilation(5)이 위로 확장되어 마스크가 목까지 올라감. 목이 마스킹되면 diffusion 모델이 목에 옷을 생성→목 꺾임 아티팩트. **해결**: SegFormer face label(11)을 수집하여 `NECK_MARGIN = H * 0.07` (≈36px at 512px) 만큼 확장 후 최종 마스크에서 차감. 얼굴+목 영역이 깔끔하게 제외되어 원본 피부 유지.
- **consensus 마스크 공간 제한 (bbox)** — consensus 복원 후 턱/원거리 의자 오감지 발생. SegFormer가 일부 프레임에서 턱을 upper-clothes로 오분류→30% threshold로 consensus에 고정. 원거리 배경 의자의 옷도 동일. **해결**: raw_masks의 median(50%)→connected components→최대 component의 bbox(좌우 20%, 상하 5% 패딩)→consensus를 bbox 내부로만 제한. 턱은 median에서 제외(일부 프레임만 오분류), 원거리 의자는 별도 작은 component→bbox 밖. 옷 중앙 구멍은 bbox 내부에서 consensus(30%)가 여전히 작동.
- **SAM2 마스킹 실패 기록** — (1) Video Predictor: negative points 완전 무시→얼굴 포함, (2) Image Predictor+Video Predictor 2단계: Image Predictor에서는 negative 작동하나 Video Predictor 전파 시 마스크 drift로 다시 얼굴 포함, (3) 팔 마스크: 키포인트(팔꿈치/손목) 기반 추정이라 팔 붙이고 있으면 두께/비율 이상. 3차례 시도 모두 실패하여 SAM2 완전 제거 결정.
- **텍스트/로고 환각은 SD v1.5 근본 한계** — 8x 공간 압축 + 4채널 VAE latent로 fine text 보존 불가. 현존 비디오 VTON 모델 중 완전 해결한 것 없음 (open problem). 후처리 로고 합성(OCR→워프→blend)이 가장 실용적 no-retrain 대안.
- **DWPose 내부 API 직접 호출** — `DWposeDetector.__call__`은 시각화+confidence만 반환하지만, 내부적으로 `inference_detector(session, img)` → person bbox, `Wholebody.__call__(img)` → keypoints (N,134,2) + scores (N,134) 제공. upstream 코드 수정 없이 직접 호출하여 person bbox/keypoints 추출. detector() + pose_estimation() 이중 호출로 ~30초 추가 비용(200프레임) 발생하나 정확도 우선.
- **Person Bbox AND** — DWPose YOLOX person bbox + 패딩(pad_x=0.10, pad_y=0.05)으로 마스크를 사람 영역으로 제한. SegFormer가 배경 의자 패딩을 upper-clothes로 오분류하는 문제(connected component bbox로도 인접물체 분리 불가했던 문제)를 person-level bbox로 해결.
- **Pose Hull AND (옵션)** — 상체 keypoints(neck, shoulders, elbows, wrists, hips) convex hull + expand 20px. person bbox보다 타이트하여 정밀 제한 가능하나 기본 비활성화(오탐 위험).
- **Hood 조건부 합성** — SegFormer hat(1) 레이블이 후드를 포함하나 TARGET_LABELS에 미포함이었음. 무조건 포함 시 배경 모자까지 마스킹. 해결: upper-clothes(4) 인접(dilation radius=15) hat 픽셀만 조건부 합성. PERSON_BBOX_AND가 최종 단계에서 배경 hat도 필터링.
- **Face/Hair/Neck 제외 강화** — 기존 SegFormer face(11) dilation만으로 부족. (1) DWPose face keypoints(nose, eyes, ears) → 타원 근사 → exclude 추가, (2) hair(2) 완전 제외 추가. FACE_EXCLUDE_MODE="segformer+dwpose"가 기본.
... (55 more lines)

```

### tasks.md

```
# Tasks — SwiftTry

## Setup
- [x] Copy _template to `recipes/swifttry`
- [x] Update `recipe.yaml` with upstream info and pinned SHA
- [x] Fill out `docs/plan.md`
- [x] Fill out `docs/context.md`
- [x] Set `.claude/last_recipe.txt` to swifttry

## Implementation
- [x] Create `requirements_opt2_modern.txt` (Colab 기본 유지, 없는 것만 설치)
- [x] Create `requirements_opt1_legacy.txt` (upstream-pinned fallback)
- [x] Write `install.sh` with opt2 default + verification
- [x] Write `run.sh` with env-var-driven data paths
- [x] Create `patches/fix_diffusers_compat.py` — 5 breaking import fixes for diffusers 0.36
- [x] Write `notebook_manifest.yaml` with all required cells
- [x] Enhance `generate_notebook.py` to support `cells` list format + --recipe/--out flags
- [x] Generate `outputs/notebooks/swifttry_A100.ipynb`
- [x] Add demo section G (auto-download 1 sample from HF TikTokDress)

## Colab Compat Fixes
- [x] Remove numpy<2.0 pin (torch 2.9 ABI requires numpy 2.x)
- [x] Remove scipy/scikit-learn/tqdm/Pillow version pins (use Colab defaults)
- [x] Fix torchsde==0.2.5 → >=0.2.6 (pip metadata bug)
- [x] Remove diffusers pin → use Colab 0.36.0 + patch
- [x] Remove CLIP GitHub zip → use open-clip-torch + ftfy

## Visual Artifact Fixes
- [x] H-3: repaint blur 축소 — `sed -i` 로 inference.py의 `kernal_size = h // 50` → `kernal_size = 3`
- [x] H-2: 얼굴 링 아티팩트 수정 — `face_exclude` dilation(15) + clothing_mask 보호
- [x] H-2 v2: SegFormer→DWPose 키포인트 기반 SAM2 프롬프팅 (실패 — SAM2 구조적 한계)
- [x] H-2 v3: SAM2 완전 제거 → SegFormer 퍼-프레임 시맨틱 세그멘테이션 교체

## Garment Shrink Fix
- [x] H-2: 마스크 과보상 제거 — consensus mask, binary_closing 삭제, dilation 12→5
- [x] H-3: kernal_size sed 패치 삭제 (업스트림 기본값 h//50 유지)
- [x] H-2: STICK_WIDTH 파라미터 추가 (4/8/12/16 Colab form)
- [x] H-2: stickwidth 변경 시 DWPose 프레임 자동 재생성
- [x] context.md: 과보상 제거 + stickwidth 파라미터화 기록

## Garment Shrink Fix v2
- [x] H-3: REPAINT_KERNEL 파라미터 추가 (1/3/5/10 Colab form) + sed 패치 복원
- [x] H-2: consensus 마스크 공간 제한 — median→connected components→largest bbox
- [x] context.md: stickwidth 무효 기록, REPAINT_KERNEL/consensus bbox 결정 기록
- [x] H-3: REPAINT_KERNEL 기본값 3→1 (하드엣지 — 가상옷 크기 최대 보존)
- [x] H-2: 얼굴/목 영역 제외 — face label(11) dilation(H*0.07) 차감
- [x] context.md: 목 제외 + REPAINT_KERNEL=1 결정 기록

## Mask Mismatch Fix (model input vs repaint)
- [x] SwiftTry 소스 분석 — prepare_mask_and_masked_image() binarize vs repaint() 연속값 경로 확인
- [x] H-2.5: 마스크 품질 진단 셀 — mp4 round-trip gray 오염, 면적 차이, 히스토그램, 시각화
- [x] H-3: REPAINT_BINARIZE + MASK_RESIZE_NEAREST 옵션 추가 (Python patching, git checkout 멱등성)
- [x] H-3: sed 방식 → Python re.sub/replace 방식으로 교체 (복잡한 패치 지원)
- [x] context.md: 마스크 경로 불일치 근본 원인 분석 + Fix 결정 기록
- [ ] Colab 테스트: H-2.5 진단 → 가설 검증 (예/아니오)
- [ ] Colab 테스트: Fix 적용 후 가상옷 수축 개선 확인

## Mask Precision PRs

### PR-1: Debug Dump + Metrics
... (121 more lines)

```

## Git Status

```
M .claude/settings.local.json
 M outputs/notebooks/swifttry_A100.ipynb
 M recipes/swifttry/docs/context.md
 M recipes/swifttry/docs/tasks.md
 M recipes/swifttry/notebook_manifest.yaml
?? .claude/hooks/__pycache__/
?? __pycache__/
?? outputs/notebooks/swifttry_A100.ipynb.v4bak
?? recipes/swifttry/docs/context.md.v4bak
?? recipes/swifttry/docs/tasks.md.v4bak
?? recipes/swifttry/notebook_manifest.yaml.v4bak
?? recipes/swifttry/patches/__pycache__/
?? scripts/__pycache__/
?? tools/__pycache__/
```

## Git Diff (stat)

```
.claude/settings.local.json             |   4 +-
 outputs/notebooks/swifttry_A100.ipynb   | 299 +++++++++++++++++++++++---------
 recipes/swifttry/docs/context.md        |   3 +
 recipes/swifttry/docs/tasks.md          |  20 ++-
 recipes/swifttry/notebook_manifest.yaml | 299 +++++++++++++++++++++++---------
 5 files changed, 451 insertions(+), 174 deletions(-)
```

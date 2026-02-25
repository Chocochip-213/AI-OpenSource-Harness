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
- **Temporal/Morphology 파라미터화** — TEMPORAL_WINDOW(1/3/5/7), MORPH_CLOSE_KERNEL(0/3/5/7), DILATION_ITER(0~15). 기존 하드코딩 값을 Colab form으로 노출하여 실험 용이.
- **2-Mask 전략 (unet_agnostic vs comp_garment)** — model input(prepare_mask_and_masked_image)은 broader mask가 유리(더 넓은 인페인트 영역), repaint compositing은 tighter mask가 유리(원본 피부 보존). DUAL_MASK=True 시 Step 2.7에서 두 변형 생성: unet_agnostic(base + UNET_EXTRA_DILATION) → videos_mask/, comp_garment(base + COMP_DILATION + seam band) → videos_mask_comp/. H-3에서 USE_COMP_MASK_REPAINT=True로 repaint 경로를 comp mask로 전환.
- **Debug Dump + Metrics** — DEBUG_DUMP=True 시 파이프라인 각 단계(raw→consensus→filled→dilated→face_excl) 마스크 PNG + overlay + metrics.json 저장. 지표: leakage_outside_person, face_intrusion, hole_rate, temporal_iou, flicker_score.
- **SAM2 여전히 사용 불가 (2026-02 기준)** — GitHub Issue #695 (facebookresearch/sam2), Ultralytics #16089/#16705 모두 확인. Video Predictor가 negative points를 완전 무시하여 얼굴 항상 포함. SAM2Long (ICCV 2025 memory tree), SAM2Plus (Kalman filter)가 drift 완화하나 negative point 근본 해결 아님. VRAM ~2GB, 속도 ~70초/200프레임 → SegFormer 대비 2.4배 VRAM, 4.7배 느림.
- **SAM3 관찰 대상 (2025-11 출시)** — 네이티브 텍스트 프롬프트("upper body clothing"), negative box prompt(이미지 모드) 지원. 그러나 비디오 트래킹에 negative box 미포함, box prompt 버그 보고 (Issue #204), gated model→HuggingFace 승인 필요, 프로덕션 검증 3개월 미만. 향후 마이그레이션 후보로 관찰, 현재는 위험도 높음.
- **Consensus bbox PAD_X 0.20→0.08 축소** — W=384에서 PAD_X=77px(20%)이 consensus bbox를 전체 프레임 너비로 확장하여 양쪽에 오분류 주입. 8%로 축소(31px)하여 consensus bbox 범위 절감. CONSENSUS_PAD_X, CONSENSUS_THRESHOLD Colab form 파라미터로 노출.
- **Consensus threshold 0.30→0.45 상향** — 30% threshold는 불안정 프레임의 오분류까지 consensus에 포함. 45%로 상향하여 더 안정적인 프레임에서만 consensus에 반영.
- **Edge-aware dilation (uniform dilation 대체)** — `binary_dilation(iterations=3)`이 이미지 에지와 무관하게 모든 방향으로 동일 확장하여 의류 경계 바깥으로 1-2cm 삐져나옴. cv2.Canny로 이미지 에지 검출 후, 1px씩 반복 확장하되 강한 에지에 도달하면 확장 중단. 추가 의존성 없음 (cv2 이미 사용 중). EDGE_DILATION=True 기본, EDGE_DILATION_MAX=5, EDGE_THRESHOLD=30 Colab form 파라미터.
- **Arm symmetry correction (반팔 비대칭 보정)** — 반팔일 때 한쪽 소매만 SegFormer upper-clothes로 분류되고 다른 쪽은 arm으로 분류되는 문제. person bbox 중앙 기준 좌우 마스크 면적 비교 → 한쪽이 30% 미만이면 큰 쪽을 수평 반전하여 union. heuristic이며 완벽하지 않으나 비대칭 개선에 효과적. ARM_SYMMETRY=True 기본.
- **Garment-adaptive arm masking (v2 최종)** — 가먼트 소매 길이에 따라 INCLUDE_ARMS 자동 결정. 타겟 가먼트를 SegFormer에 추론 → arm(14/15)/upper(4) 비율로 긴팔/반팔 판정 (arm_ratio < 0.05 = 긴팔). **긴팔 가먼트 → INCLUDE_ARMS=True**: 영상 속 맨 팔도 마스크 포함하여 모델이 소매 생성 가능. **반팔 가먼트 → INCLUDE_ARMS=False 유지**: 원본 팔 피부 보존하여 일렁임/아티팩트 방지. 이전 시도(INCLUDE_ARMS 항상 True, ARM_SYMMETRY 미러링, SLEEVE_ARM_MERGE) 모두 제거 — 반팔→반팔에서 불필요한 팔 재생성이 오히려 퀄리티 저하.
- **Consensus interior-only mode** — `merged = np.maximum(smoothed, consensus)` (union)가 마스크 외부 오분류 픽셀을 매 프레임에 강제 주입하여 1-2cm 삐져나옴의 근본 원인. 수정: consensus를 smoothed 마스크 내부(+3px 버퍼)에서만 적용하여 내부 빈틈은 채우되 외부 확장은 차단. CONSENSUS_MODE="interior" 기본, "union"(기존 동작)/"off" 선택 가능.
- **[v3] DWPose-Guided 파이프라인 재설계** — v2의 edge-aware dilation, consensus interior, arm symmetry 모두 실패 (배 구멍 여전, 외곽 악화, 30+ 파라미터 복잡도). 근본 원인 3가지: (1) 학습 데이터(SAM2+DWPose로 생성한 타이트 마스크)와의 분포 불일치 — SegFormer+dilation+consensus가 너무 느슨, (2) SegFormer waistline 불안정 — upper-clothes(4)/pants(6)/belt(8) 경계 프레임마다 달라져 배 구멍 발생, (3) 후처리 과잉 — SegFormer 오류를 후처리로 메우려 했지만 새 문제 생성. **해결**: `make_upper_body_hull_mask()` (neck→shoulders→elbows→wrists→hips convex hull)이 이미 구현되어 있었으나 비활성화. 이를 파이프라인의 공간적 뼈대로 승격: (A) hull pre-filter — SegFormer 추론 직후, consensus 전에 raw_masks × hull → 외곽 오탐 제거, (B) hull consensus mode — DWPose hull을 consensus 버퍼로 사용 → 배가 hull 내부 → 구멍 채움, (C) dilation 최소화(3→1) + edge dilation 기본 off. HULL_MASK=True, HULL_EXPAND_PX=15 기본.
- **[v3] SAM2 Image Predictor 재평가** — Video Predictor만 실패한 것을 SAM2 전체 포기로 확대한 것은 과잉 반응. Image Predictor는 negative point 작동, per-frame 사용 가능. 그러나 VRAM ~2GB(SegFormer의 2.4배), 속도 ~70초/200프레임(4.7배), 아키텍처 변경 대규모 → Phase 2 옵션으로 보류. DWPose hull + SegFormer 하이브리드로 먼저 해결 시도.
- **[v3] POSE_HULL_AND 제거 → HULL_MASK 대체** — 기존 POSE_HULL_AND는 dilation 후 hull로 재클리핑하는 방식이었으나, v3에서는 raw_masks 단계에서 hull pre-filter로 적용. pre-filter가 AND보다 효과적: consensus 전에 오탐 제거 → consensus 자체가 깨끗.
- **[v3] CONSENSUS_MODE="hull" 추가** — DWPose hull을 consensus 버퍼로 사용. 기존 "interior" 모드는 smoothed contours의 convex hull을 사용했으나, smoothed가 배 구멍을 이미 포함하면 convex hull도 그만큼 움푹함. DWPose hull은 항상 full torso 포함 → 배 구멍에 consensus 확실히 적용.
- **Data not bundled** — TikTokDress dataset is not redistributable. Notebook provides path variables for user to mount their own data.
- **Colab baseline 2026-01-20** — torch 2.9.0, diffusers 0.36.0→downgraded to 0.24.0, accelerate 1.12.0 (kept). The diffusers downgrade is intentional and required; upstream patches `UNet2DConditionModel` internals.

## Data Requirements
```
DATA_DIR/
├── videos/           # Original person videos (.mp4)
├── garments/         # Garment images (.png), one per test pair
├── videos_mask/      # Binary segmentation masks (.mp4)
├── videos_masked/    # Inpainted/masked person videos (.mp4)
├── videos_dwpose/    # DWPose skeleton videos (.mp4)
└── test_pairs.txt    # Space-separated: "video_name.mp4 garment_name.png"
```

Preprocessing tools exist in `tools/` (extract_dwpose_from_vid.py, etc.) but are out of scope for this inference-only recipe.

## Pretrained Weights (auto-downloaded)
| Component | HuggingFace Repo | Local Path |
|-----------|-----------------|------------|
| SD v1.5 UNet | runwayml/stable-diffusion-v1-5 | pretrained_sd_models/stable-diffusion-v1-5/ |
| SD Inpainting | runwayml/stable-diffusion-inpainting | pretrained_sd_models/stable-diffusion-inpainting/ |
| Image Encoder | lambdalabs/sd-image-variations-diffusers | pretrained_sd_models/image_encoder/ |
| DWPose | yzd-v/DWPose | pretrained_sd_models/DWPose/ |
| VAE | stabilityai/sd-vae-ft-mse | pretrained_sd_models/sd-vae-ft-mse/ |
| SwiftTry | NMHung/SwiftTry | pretrained_sd_models/swift_try/ |

## References
- Paper: https://arxiv.org/abs/2412.10178
- Project: https://swift-try.github.io/
- Code: https://github.com/VinAIResearch/SwiftTry
- Weights: https://huggingface.co/NMHung/SwiftTry
- Dataset: https://huggingface.co/datasets/nguyenquivinhquang/TikTokDress

---

> **Rule**: When a decision is made during implementation, add it to "Key Decisions" with the reasoning.
> This file is the permanent record — don't let knowledge stay only in chat history.

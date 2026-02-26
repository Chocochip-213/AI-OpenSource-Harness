# SwiftTry API Spec — 전처리 ↔ 추론 기술 인터페이스

> **목적**: SwiftTry를 Colab 데모에서 서비스 형태로 전환할 때, 백엔드 팀이 전처리 모듈을 독립 구현할 수 있도록 정확한 데이터 계약(data contract)을 정의한다.
>
> **기준 코드**: `recipes/swifttry/notebook_manifest.yaml` H-2 (전처리), H-3 (추론) — upstream SHA `57d3f0b`

---

## 1. Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                      SwiftTry Pipeline                              │
│                                                                     │
│  사용자 입력                                                         │
│  ┌───────────┐  ┌────────────┐                                      │
│  │ person.mp4│  │garment.png │                                      │
│  └─────┬─────┘  └─────┬──────┘                                      │
│        │              │                                              │
│  ══════╪══════════════╪══════════════════════  전처리 경계  ═════════ │
│        │              │                                              │
│        ▼              │                                              │
│  ┌───────────┐        │                                              │
│  │  ffprobe  │ FPS/W/H│                                              │
│  └─────┬─────┘        │                                              │
│        ▼              │                                              │
│  ┌───────────┐        │                                              │
│  │ 프레임 추출│ PyAV   │                                              │
│  └─────┬─────┘        │                                              │
│        │              │                                              │
│   ┌────┴─────┐   ┌────┴──────────┐                                   │
│   ▼          ▼   ▼               │                                   │
│ ┌──────┐ ┌──────────┐ ┌──────────────────┐                           │
│ │DWPose│ │SAM2 Image│ │SegFormer 1-shot  │                           │
│ │      │ │Predictor │ │(garment sleeve)  │                           │
│ └──┬───┘ └────┬─────┘ └───────┬──────────┘                           │
│    │          │               │                                      │
│    │     point prompts   INCLUDE_ARMS                                │
│    │     from keypoints  자동 결정                                    │
│    │          │               │                                      │
│    ▼          ▼               │                                      │
│ ┌──────────────────┐          │                                      │
│ │  후처리 파이프라인  │◄─────────┘                                      │
│ │ (dilation, fill,  │                                                │
│ │  face exclude,    │                                                │
│ │  person bbox AND) │                                                │
│ └────────┬─────────┘                                                 │
│          │                                                           │
│          ▼                                                           │
│ ┌──────────────────┐                                                 │
│ │  ffmpeg 인코딩    │                                                 │
│ │ (libx264/yuv420p)│                                                 │
│ └────────┬─────────┘                                                 │
│          │                                                           │
│  ════════╪════════════════════════════════  전처리 출력  ═════════════ │
│          ▼                                                           │
│  ┌───────────────────────────────────┐                                │
│  │ videos_mask/{id}.mp4              │                                │
│  │ videos_masked/{id}.mp4            │                                │
│  │ videos_dwpose/{id}.mp4            │                                │
│  │ test_pairs.txt                    │                                │
│  └──────────────┬────────────────────┘                                │
│                 │                                                     │
│  ═══════════════╪════════════════════════  추론 경계  ════════════════ │
│                 ▼                                                     │
│  ┌──────────────────────────┐                                        │
│  │ TryOnController          │                                        │
│  │  .tryon_video()          │                                        │
│  │  ├── read_frames() PyAV  │                                        │
│  │  ├── prepare_mask        │                                        │
│  │  ├── TryOnVideoPipeline  │                                        │
│  │  │   (SD1.5 + MotionMod) │                                        │
│  │  └── repaint()           │                                        │
│  └──────────┬───────────────┘                                        │
│             ▼                                                        │
│  ┌──────────────────┐                                                │
│  │ result.mp4        │                                                │
│  └──────────────────┘                                                │
└─────────────────────────────────────────────────────────────────────┘
```

**핵심 경계**: 전처리가 4개 MP4 + `test_pairs.txt`를 생성하면, 추론은 이 파일들만 읽어서 결과를 생성한다. 두 모듈은 파일 시스템만으로 통신한다.

---

## 2. Architecture

### Colab Gradio 데모 구조

현재 Colab 노트북에서는 전처리와 추론이 **같은 GPU, 같은 프로세스**에서 순차 실행된다:

```
[H-2] 전처리 (DWPose → SAM2 → 후처리 → ffmpeg)
  │
  │  SegFormer / SAM2 모델 해제 → VRAM 반환
  │
  ▼
[H-3] 추론 (TryOnController → TryOnVideoPipeline)
```

### 모델 상주 패턴 (Pipeline Transplant)

H-3는 모델 캐싱을 통해 재실행 시 로딩을 건너뛴다:

1. 첫 실행: `TryOnController(config_path)` → 내부에서 `TryOnVideoPipeline` 생성 → 모델 ~6GB GPU 상주
2. `globals()['_swifttry_controller']`에 controller 캐싱
3. 재실행: `_cached_pipeline = _swifttry_controller.pipeline` 추출
4. 새 controller 생성 후 `controller.pipeline = _cached_pipeline` 이식
5. `tryon_video()` 내부 `if self.pipeline is None:` 체크로 로딩 스킵

```python
# 캐시 추출
_cached_pipeline = None
if '_swifttry_controller' in globals():
    _ctrl = globals()['_swifttry_controller']
    if _ctrl is not None and hasattr(_ctrl, 'pipeline') and _ctrl.pipeline is not None:
        _cached_pipeline = _ctrl.pipeline

# 패치된 모듈 재로드 (매 실행마다 inference.py 패치가 달라질 수 있음)
if 'inference' in sys.modules:
    del sys.modules['inference']
import inference as _swifttry_inf

# 컨트롤러 생성 + 파이프라인 이식
_swifttry_controller = _swifttry_inf.TryOnController(_config_path)
if _cached_pipeline is not None:
    _swifttry_controller.pipeline = _cached_pipeline
```

### 서비스 전환 시 아키텍처

```
[Backend API]                    [Inference Server]
  전처리 GPU/CPU                   추론 전용 GPU
  DWPose + SAM2                    TryOnVideoPipeline 상주
       │                                │
       └── S3/NFS ── 4 MP4s ───────────►┘
                     test_pairs.txt
```

---

## 3. 전처리 파이프라인 (Backend 팀 핵심)

### 입력

| 항목 | 형식 | 설명 |
|------|------|------|
| 인물 영상 | `.mp4` | 임의 해상도 W×H, 임의 FPS |
| 가먼트 이미지 | `.png` | RGB, 임의 해상도 (배경 투명/흰색) |

### 처리 순서

```
Step 0: 비디오 정보 + 프레임 추출
Step 1: DWPose 시각화 + bbox/keypoints 추출
Step 1.5: Person mask 계산 (bbox + hull)
Step 2: SAM2 Image Predictor 퍼-프레임 마스크 생성
  └── Garment sleeve detection (SegFormer 1-shot)
  └── sam2_mode 후처리 오버라이드
Step 2 후처리: face exclude, person bbox AND, largest blob 등
Step 3: ffmpeg 비디오 인코딩 (mask, dwpose, masked)
```

### Step 0: 비디오 정보 + 프레임 추출

```python
# ffprobe로 FPS, W, H 추출
probe = subprocess.run(
    ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", mp4_path],
    capture_output=True, text=True
)
streams = json.loads(probe.stdout)["streams"]
vid_stream = [s for s in streams if s["codec_type"] == "video"][0]
fps_parts = vid_stream["r_frame_rate"].split("/")
FPS = round(int(fps_parts[0]) / int(fps_parts[1]))
W, H = int(vid_stream["width"]), int(vid_stream["height"])

# PyAV로 프레임 추출
container = av.open(mp4_path)
orig_frames = []  # List[np.ndarray], shape (H, W, 3), dtype uint8, RGB
for frame in container.decode(video=0):
    arr = frame.to_ndarray(format='rgb24')
    orig_frames.append(arr)
container.close()
```

### Step 1: DWPose

- **모델**: `yzd-v/DWPose` (ONNX — YOLOX detector + Wholebody pose estimator)
- **라이브러리**: `src.dwpose.DWposeDetector` (upstream 코드)
- **출력 1**: 포즈 시각화 PNG (W×H, `stickwidth=4` 기본)
- **출력 2**: Person bboxes, keypoints (N,134,2), scores (N,134)

```python
from src.dwpose import DWposeDetector
from src.dwpose.onnxdet import inference_detector as dwpose_detect_persons

detector = DWposeDetector().to("cuda")

for i, frame_arr in enumerate(orig_frames):
    # 시각화 (내부: YOLOX detect + pose estimate + draw)
    pil = Image.fromarray(frame_arr)
    pose_img, _ = detector(pil)
    pose_resized = pose_img.resize((W, H), Image.LANCZOS)
    # → pose_frames_dir/{i:05d}.png

    # bbox/keypoints 추출 (별도 ONNX 호출)
    bgr = cv2.cvtColor(frame_arr, cv2.COLOR_RGB2BGR)
    bboxes = dwpose_detect_persons(detector.pose_estimation.session_det, bgr)
    kps, scores = detector.pose_estimation(bgr)
    # bboxes: ndarray (N, 5) — [x1, y1, x2, y2, conf]
    # kps: ndarray (N, 134, 2) — 18 body + 116 face/hand keypoints
    # scores: ndarray (N, 134)
```

> **ONNX 호출 횟수**: 4회/프레임 (detector(pil) 내부 2회 + 별도 2회). `draw_bodypose()` 직접 호출이 불가능하여(시그니처가 candidate/subset 구조) 절약 불가.

### Step 1.5: Person Mask

```python
def make_person_bbox_mask(bboxes, W, H, pad_x=0.10, pad_y=0.05):
    """최대 person bbox + 패딩 → binary mask (H, W)"""
    # 최대 면적 bbox 선택 → 패딩 → 0/1 mask

def make_upper_body_hull_mask(kps, scores, W, H, expand_px=20):
    """상체 keypoints convex hull → binary mask (H, W)"""
    # UPPER_IDX = [1(neck), 2(R_shoulder), 3(R_elbow), 4(R_wrist),
    #              5(L_shoulder), 6(L_elbow), 7(L_wrist), 8(R_hip), 11(L_hip)]
    # score > 0.3 인 포인트만 사용 → cv2.convexHull → cv2.fillConvexPoly
    # expand_px > 0이면 cv2.dilate(MORPH_ELLIPSE(3,3), iterations=expand_px)
```

### Step 2: SAM2 Image Predictor (기본 마스크 엔진)

- **모델**: `facebook/sam2.1-hiera-large` (기본) / base-plus / small / tiny 선택 가능
- **라이브러리**: `sam2.sam2_image_predictor.SAM2ImagePredictor`
- **FP16 강제**: `model.half()` + `torch.autocast("cuda", dtype=torch.float16)`

**포인트 프롬프트 구성 (DWPose keypoints → SAM2)**:

| 타입 | Keypoints | 조건 |
|------|-----------|------|
| **Positive** | neck(1), R_shoulder(2), L_shoulder(5) | score > 0.3 |
| **Positive** | mid-torso (neck↔hip 50%), lower-torso (75%) | neck + any hip available |
| **Negative** | nose(0), L_eye(14), R_eye(15), L_ear(16), R_ear(17) | score > 0.3 |
| **Negative** | R_wrist(4), L_wrist(7) | `INCLUDE_ARMS=False`일 때만 |

```python
sam2_predictor = SAM2ImagePredictor.from_pretrained(SAM2_MODEL)
sam2_predictor.model = sam2_predictor.model.half()  # FP16

for i in range(n_frames):
    with torch.autocast("cuda", dtype=torch.float16):
        sam2_predictor.set_image(orig_frames[i])

    # Build points from DWPose keypoints (위 표 참조)
    all_points = np.array(pos_points + neg_points, dtype=np.float32)
    labels = np.array([1]*len(pos_points) + [0]*len(neg_points), dtype=np.int32)

    with torch.autocast("cuda", dtype=torch.float16):
        masks_pred, scores_pred, _ = sam2_predictor.predict(
            point_coords=all_points,
            point_labels=labels,
            multimask_output=True,  # 3개 후보 중 최고 점수 선택
        )
    best_idx = int(np.argmax(scores_pred))
    mask = masks_pred[best_idx].astype(np.uint8)  # binary (H, W)
```

**Face mask (SAM2 모드)**: SegFormer 없이 DWPose keypoints → 타원 근사로 face mask 생성

```python
face_kp_idx = [0(nose), 14(L_eye), 15(R_eye), 16(L_ear), 17(R_ear)]
# score > 0.3인 포인트 3개 이상 → 중심 + 최대 거리*1.5+10 반경 타원
cv2.ellipse(dw_face, center, (radius, int(radius*1.3)), 0, 0, 360, 1, -1)
```

### Garment Sleeve Detection (SegFormer 1-shot)

가먼트 이미지를 SegFormer에 1회 추론하여 긴팔/반팔 자동 판정:

```python
# mattmdjaga/segformer_b2_clothes — 18 class semantic segmentation
# upper-clothes(4) vs arm(14,15) 비율로 판정
arm_ratio = gar_arm_px / gar_upper_px
garment_is_long = (arm_ratio < 0.05)  # 5% 미만 = 긴팔

# 긴팔 → INCLUDE_ARMS=True (SAM2에서 wrist negative 제거)
# 반팔 → INCLUDE_ARMS=False 유지 (원본 팔 피부 보존)
```

### Step 2 후처리 (SAM2 모드)

SAM2 모드에서는 후처리가 최소화됨:

```
CONSENSUS_MODE = "off"  (SAM2에는 시맨틱 레이블 없으므로)
DILATION_ITER = form 값 그대로 (기본 3)
```

**퍼-프레임 후처리 순서**:

```
1. Temporal smoothing    — raw_masks[i-half:i+half] median (TEMPORAL_WINDOW=3)
2. (consensus skip)      — SAM2 모드에서는 off
3. Hole fill             — cv2.floodFill 4-corner + 크기 제한 (FILL_HOLE_MAX_PCT=10%)
4. Morphological closing — 선택적 (MORPH_CLOSE_KERNEL=0이면 skip)
5. Edge-aware dilation   — cv2.Canny edge barrier + iterative expand (EDGE_DILATION=True)
   또는 uniform dilation — cv2.dilate(iterations=DILATION_ITER) (EDGE_DILATION=False)
6. Person bbox AND       — 배경 물체 제거
7. Face/Hair exclude     — DWPose ellipse face mask * (1 - clothing_protect) 차감
8. Largest blob          — connected components → 최대만 유지
```

### Step 3: ffmpeg 비디오 인코딩

전처리 출력 4개 MP4를 각각 인코딩:

```bash
# 마스크 비디오
ffmpeg -y -framerate {FPS} -i "{mask_frames_dir}/%05d.png" \
    -c:v libx264 -pix_fmt yuv420p -crf 18 "{mask_vid_path}" -loglevel warning

# DWPose 시각화 비디오
ffmpeg -y -framerate {FPS} -i "{pose_frames_dir}/%05d.png" \
    -c:v libx264 -pix_fmt yuv420p -crf 18 "{dwpose_vid_path}" -loglevel warning

# Masked (agnostic) 비디오 — 마스크 영역을 gray(128)로 채움
ffmpeg -y -framerate {FPS} -i "{masked_frames_dir}/%04d.png" \
    -c:v libx264 -pix_fmt yuv420p -crf 18 "{masked_vid_path}" -loglevel warning
```

> **masked 프레임 네이밍**: `%04d` (4자리). mask/dwpose 프레임은 `%05d` (5자리). 이 불일치는 의도적 — masked 프레임은 별도 루프에서 생성.

---

## 4. 추론 엔드포인트

### `TryOnController.tryon_video()` 시그니처

```python
# inference.py — upstream TryOnController
out_path = controller.tryon_video(
    ref_cloth_image: str,      # 가먼트 이미지 절대 경로 (.png)
    video_path: str,           # 원본 비디오 (.mp4)
    masked_video_path: str,    # 마스크된 비디오 (.mp4) — gray 128 inpaint region
    mask_video_path: str,      # 바이너리 마스크 비디오 (.mp4)
    pose_video_path: str,      # DWPose 시각화 비디오 (.mp4)
    clip_length: int = 10000,  # 처리 프레임 수 (내부에서 min(clip_length, 총프레임)으로 clamp)
    repaint: bool = True,      # 마스크 외부 원본 블렌딩
    save_dir: str = ...,       # 결과 저장 디렉토리
    overlap_value: int = 0,    # 슬라이딩 윈도우 오버랩 (내부 context scheduler가 처리)
)
# → 반환: 결과 MP4 경로
```

**호출 예시** (Colab H-3):

```python
out_path = _swifttry_controller.tryon_video(
    ref_cloth_image=f"{USER_DIR}/garments/{cloth_id}",
    video_path=f"{USER_DIR}/videos/{video_id}",
    masked_video_path=f"{USER_DIR}/videos_masked/{video_id}",
    mask_video_path=f"{USER_DIR}/videos_mask/{video_id}",
    pose_video_path=f"{USER_DIR}/videos_dwpose/{video_id}",
    clip_length=10000,
    repaint=True,
    save_dir=USER_OUT,
    overlap_value=0,
)
```

### `read_frames()` — MP4만 지원

```python
# src/utils/util.py
def read_frames(video_path):
    """PyAV 기반 MP4 읽기. 디렉토리 경로 X, 이미지 시퀀스 X."""
    container = av.open(video_path)
    # → PIL Image 리스트 반환
```

> **주의**: `read_frames()`는 `.mp4` 파일 경로만 받는다. 프레임 디렉토리 경로나 이미지 시퀀스를 전달하면 실패한다.

### inference.py 패치 4종

서비스 환경에서도 동일 패치를 적용해야 한다. 원본 복원 후 패치 (멱등성):

```python
# 1) git checkout → 원본 복원
subprocess.run(["git", "checkout", "inference.py"], cwd="/content/SwiftTry")

code = open(inf_path).read()

# Patch 1: repaint kernal_size (기본 1 — 하드엣지)
code = re.sub(r'kernal_size = .*', f'kernal_size = {REPAINT_KERNEL}', code)

# Patch 2: repaint 직전 mask binarize (REPAINT_BINARIZE=True)
# gray 경계 → 0/255 정리 → model input과 repaint 경로 일치
code = code.replace(
    'mask = mask.filter(ImageFilter.GaussianBlur(kernal_size))',
    'mask = mask.point(lambda p: 255 if p >= 128 else 0)\n'
    '    mask = mask.filter(ImageFilter.GaussianBlur(kernal_size))'
)

# Patch 3: mask resize NEAREST (BICUBIC gray 방지)
code = code.replace(
    "mask_pil.convert('L').resize((width, height))",
    "mask_pil.convert('L').resize((width, height), Image.NEAREST)"
)

# Patch 4 (선택): comp_garment mask로 repaint 경로 전환 (DUAL_MASK 시)
code = code.replace(
    'os.path.join(data_dir, "videos_mask"',
    'os.path.join(data_dir, "videos_mask_comp"'
)

open(inf_path, 'w').write(code)
```

### 추론 내부 파이프라인

```
tryon_video()
  ├── read_frames(video_path)           # 원본 프레임
  ├── read_frames(masked_video_path)    # masked 프레임
  ├── read_frames(mask_video_path)      # 마스크
  ├── read_frames(pose_video_path)      # DWPose
  ├── load ref_cloth_image (PIL)
  │
  ├── if self.pipeline is None:
  │     load_all_models()               # ~6GB, ~20초
  │
  ├── prepare_mask_and_masked_image()
  │     └── mask >= 0.5 binarize        # ← model input 경로
  │
  ├── TryOnVideoPipeline.__call__()
  │     ├── context_scheduler(context_frames=16, random_shift)
  │     ├── ShiftCaching (attention cache)
  │     ├── 25 DDIM steps, CFG 3.5, v-prediction, zero-SNR
  │     └── VAE decode
  │
  └── repaint()
        ├── load mask → GaussianBlur(kernal_size)  # ← repaint 경로
        └── blend: result * mask + original * (1-mask)
```

---

## 5. 디렉토리 구조 + 파일 형식

### 전처리 출력 디렉토리

```
{USER_DIR}/
├── videos/
│   └── {sample_id}.mp4          # 원본 영상 (사용자 업로드, W×H@FPS)
├── garments/
│   └── {garment_id}.png         # 가먼트 이미지 (RGB PNG)
├── videos_mask/
│   └── {sample_id}.mp4          # 바이너리 마스크 (흰색=인페인트 영역)
├── videos_masked/
│   └── {sample_id}.mp4          # 원본 + 마스크 영역을 gray(128)로 채움
├── videos_dwpose/
│   └── {sample_id}.mp4          # DWPose 스켈레톤 시각화
├── test_pairs.txt               # "video_name.mp4 garment_name.png" 한 줄씩
│
├── _frames/{sample_id}/         # [중간] 원본 프레임 JPG
│   └── {00000..N}.jpg
├── _pose_frames/{sample_id}/    # [중간] DWPose 시각화 PNG
│   └── {00000..N}.png
├── _mask_frames/{sample_id}/    # [중간] 마스크 프레임 PNG
│   └── {00000..N}.png
└── _masked_frames/{sample_id}/  # [중간] masked 프레임 PNG
    └── {0000..N}.png            # ← %04d 주의 (다른 디렉토리는 %05d)
```

### 추론 출력 디렉토리

```
{USER_OUT}/
└── canvas/
    └── {video_name}-{garment_name}.mp4   # 결과 영상
```

### 비디오 코덱 스펙

| 속성 | 전처리 출력 | 추론 출력 |
|------|------------|----------|
| Codec | libx264 | libx264 |
| Pixel format | yuv420p | yuv420p |
| CRF | 18 | — (`save_videos_grid()` 기본값) |
| FPS | 원본 FPS | **30fps 고정** (주의) |
| 해상도 | 원본 W×H | 384×512 (추론 내부 리사이즈) |

### 해상도 규칙

- **전처리**: 원본 해상도 W×H 그대로 유지. 모든 마스크/포즈 프레임도 W×H.
- **추론 내부**: `inference.py`가 `read_frames()` 후 내부적으로 **384×512**로 리사이즈. 이 해상도는 Stage2 학습 해상도(`configs/train/stage2_tiktok_sam2mask.yaml`)와 정확히 일치.

### `test_pairs.txt` 형식

```
{video_name}.mp4 {garment_name}.png
```

- 공백 구분, 한 줄에 1쌍
- 파일 확장자 포함
- 경로는 상대 (videos/, garments/ 하위 파일명)

예시:
```
sample1.mp4 tshirt_white.png
sample1.mp4 hoodie_black.png
```

---

## 6. Gradio 인터페이스 설계

### 입력 위젯

```python
import gradio as gr

with gr.Blocks() as demo:
    with gr.Row():
        video_input = gr.Video(label="인물 영상 (.mp4)")
        garment_input = gr.Image(label="가먼트 (.png)", type="filepath")

    with gr.Row():
        # 전처리 파라미터
        dilation = gr.Slider(0, 15, value=3, step=1, label="DILATION_ITER")
        edge_dilation = gr.Checkbox(value=True, label="EDGE_DILATION")
        edge_threshold = gr.Slider(10, 100, value=30, step=10, label="EDGE_THRESHOLD")

    with gr.Row():
        # 추론 파라미터
        repaint_kernel = gr.Dropdown([1, 3, 5, 10], value=1, label="REPAINT_KERNEL")
        repaint_binarize = gr.Checkbox(value=True, label="REPAINT_BINARIZE")
        mask_resize_nearest = gr.Checkbox(value=True, label="MASK_RESIZE_NEAREST")

    output_video = gr.Video(label="Try-On 결과")
    run_btn = gr.Button("실행")
```

### 의사 코드

```python
def tryon_pipeline(video_path, garment_path, dilation, edge_dilation, ...):
    # 1. 전처리
    sample_id = generate_id()
    work_dir = create_temp_dir()

    frames, fps, w, h = extract_frames(video_path)            # PyAV
    pose_frames, bboxes, keypoints = run_dwpose(frames)        # DWPose
    masks = run_sam2_per_frame(frames, keypoints, garment_path) # SAM2
    masks = postprocess(masks, bboxes, keypoints, dilation, ...)
    encode_videos(work_dir, frames, masks, pose_frames, fps)   # ffmpeg

    write_test_pairs(work_dir, sample_id, garment_name)

    # 2. 추론
    result_path = controller.tryon_video(
        ref_cloth_image=garment_path,
        video_path=f"{work_dir}/videos/{sample_id}.mp4",
        masked_video_path=f"{work_dir}/videos_masked/{sample_id}.mp4",
        mask_video_path=f"{work_dir}/videos_mask/{sample_id}.mp4",
        pose_video_path=f"{work_dir}/videos_dwpose/{sample_id}.mp4",
        clip_length=10000,
        repaint=True,
        save_dir=output_dir,
    )

    # 3. 반환
    return result_path
```

---

## 7. VRAM 요구사항

### 모듈별 VRAM

| 모듈 | 단독 VRAM | 비고 |
|------|----------|------|
| DWPose (ONNX) | ~0.5 GB | YOLOX + Wholebody ONNX |
| SegFormer (mattmdjaga/segformer_b2_clothes) | ~0.85 GB | garment 1-shot만 (SAM2 모드 시) |
| SAM2 Image Predictor (hiera-large, FP16) | ~1.5 GB | `model.half()` + autocast |
| TryOnVideoPipeline (SD1.5 + MotionModules) | ~6.0 GB | ReferenceUNet + DenoisingUNet + VAE + CLIP |

### 동시 로드

- **전처리**: DWPose + SAM2 + SegFormer(1-shot) ≈ **2.85 GB** (SAM2 해제 후 SegFormer 로드, 또는 순차)
- **추론**: TryOnVideoPipeline ≈ **6.0 GB**
- **전처리 → 추론 순차 실행 시 최대**: ~**6.0 GB** (전처리 모델 해제 후 추론)
- **전처리 + 추론 동시 상주**: ~**9-10 GB**

### GPU별 예상 성능

| GPU | VRAM | 전처리 (200프레임) | 추론 (200프레임) | 비고 |
|-----|------|-------------------|-----------------|------|
| RTX PRO 6000 Blackwell | 96 GB GDDR7 | ~40s | ~90s | Colab G4 tier, BW ~2.0 TB/s |
| A100 80GB | 80 GB HBM2e | ~45s | ~120s | BW 2.0 TB/s |
| H100 80GB | 80 GB HBM3 | ~35s | ~80s | BW 3.35 TB/s, 4th gen Tensor Core |
| T4 16GB | 16 GB GDDR6 | ~120s | ~300s | 최소 사양, BW 0.32 TB/s |

> SAM2 encoding은 bandwidth-bound, diffusion 추론은 compute-bound. H100은 두 가지 모두에서 이점.

---

## 8. 알려진 문제 / 주의사항

### 8.1 H.264 마스크 압축 → gray 경계 → REPAINT_BINARIZE 필수

MP4(H.264) 손실 압축이 binary mask의 경계에 gray 중간값(1-254)을 생성한다.

- **Model input 경로** (`prepare_mask_and_masked_image()`): `>= 0.5` binarize → gray 경계 픽셀이 0으로 탈락 → 모델이 해당 영역을 인페인트하지 않음
- **Repaint 경로**: 원본 PIL mask에 GaussianBlur → 연속값(0~1) 블렌딩 → gray 픽셀에서 인페인트 안 된 영역이 부분 노출

**해결**: `REPAINT_BINARIZE=True` (repaint 직전 `mask.point(>=128→255, else 0)`), `MASK_RESIZE_NEAREST=True` (resize 시 gray 방지)

### 8.2 `save_videos_grid()` 기본 30fps

`src/utils/util.py`의 `save_videos_grid()`는 출력을 **30fps 고정**으로 인코딩한다. 원본 영상의 FPS가 30이 아니면 재생 속도가 달라진다.

서비스에서는 결과 MP4를 원본 FPS로 re-encode하거나, `save_videos_grid()`를 패치해야 한다.

### 8.3 CWD 의존성 (config 상대 경로)

`inference.py`의 `TryOnController`는 config YAML 내부의 상대 경로를 CWD 기준으로 해석한다. 추론 실행 전 CWD를 SwiftTry 루트로 변경해야 한다:

```python
_prev_cwd = os.getcwd()
os.chdir("/content/SwiftTry")
try:
    controller.tryon_video(...)
finally:
    os.chdir(_prev_cwd)
```

### 8.4 masked 프레임 네이밍 불일치

| 디렉토리 | 네이밍 패턴 | 자릿수 |
|---------|-----------|--------|
| `_frames/` | `{i:05d}.jpg` | 5자리 |
| `_pose_frames/` | `{i:05d}.png` | 5자리 |
| `_mask_frames/` | `{i:05d}.png` | 5자리 |
| `_masked_frames/` | `{i:04d}.png` | **4자리** |

서비스 구현 시 통일 권장.

### 8.5 SAM2 구조적 한계

- **Video Predictor**: negative points를 완전 무시 → 얼굴 항상 포함. GitHub Issue #695.
- **Image→Video 전파**: Image Predictor에서는 negative 작동하나 Video Predictor 전파 시 마스크 drift.
- **현재 해결**: Image Predictor per-frame만 사용 (Video Predictor 사용 안 함).

### 8.6 텍스트/로고 환각

SD v1.5의 8x 공간 압축 + 4채널 VAE latent로 fine text 보존이 불가능하다. 384×512에서 latent 48×64 → 로고 ~10×4px. 현존 비디오 VTON 모델 중 완전 해결한 것 없음 (open problem). 후처리 로고 합성(OCR→워프→blend)이 가장 실용적 no-retrain 대안.

---

## 9. 전처리 파라미터 레퍼런스

### SAM2 관련

| 파라미터 | 기본값 | 타입 | 영향 | 권장 |
|---------|--------|------|------|------|
| `MASK_ENGINE` | `"sam2"` | string | 마스크 생성 엔진 | `"sam2"` (SegFormer 폐기됨) |
| `SAM2_MODEL` | `"facebook/sam2.1-hiera-large"` | string | SAM2 모델 크기 | large (정확도↑), tiny (속도↑) |

**SAM2 포인트 프롬프트**:
- **Positive**: neck, shoulders, mid-torso(neck↔hip 50%), lower-torso(75%)
- **Negative**: nose, eyes, ears (얼굴 제외), wrists (반팔 시 팔 제외)
- 모든 keypoint는 score > 0.3 일 때만 사용

### 마스크 후처리 관련

| 파라미터 | 기본값 | 타입 | 영향 | 권장 |
|---------|--------|------|------|------|
| `DILATION_ITER` | `3` | int (0-15) | 마스크 확장 반복 횟수 | 3 (SAM2 기본) |
| `EDGE_DILATION` | `True` | bool | 이미지 에지에서 확장 정지 | True (의류 경계 보존) |
| `EDGE_DILATION_MAX` | `5` | int (1-15) | edge-aware 최대 확장 스텝 | 5 |
| `EDGE_THRESHOLD` | `30` | int (10-100) | Canny edge 검출 임계값 | 30 (낮을수록 민감) |
| `FILL_HOLE_MAX_PCT` | `10` | int (0-50) | 마스크 면적 대비 최대 hole 크기 % | 10 |
| `TEMPORAL_WINDOW` | `3` | int [1,3,5,7] | temporal median 윈도우 크기 | 3 |
| `MORPH_CLOSE_KERNEL` | `0` | int [0,3,5,7] | morphological closing 커널 (0=skip) | 0 |
| `KEEP_LARGEST_BLOB` | `True` | bool | 최대 connected component만 유지 | True |

### 인물 감지 관련

| 파라미터 | 기본값 | 타입 | 영향 | 권장 |
|---------|--------|------|------|------|
| `PERSON_BBOX_AND` | `True` | bool | person bbox로 마스크 클리핑 | True (배경 물체 제거) |
| `BBOX_PAD_X` | `0.10` | float | bbox 좌우 패딩 비율 | 0.10 |
| `BBOX_PAD_Y` | `0.05` | float | bbox 상하 패딩 비율 | 0.05 |
| `HULL_MASK` | `False` | bool | DWPose hull pre-filter | False (SAM2 모드에서는 불필요) |
| `HULL_EXPAND_PX` | `15` | int (0-40) | hull 확장 픽셀 | 15 |

### 얼굴/머리카락 제외 관련

| 파라미터 | 기본값 | 타입 | 영향 | 권장 |
|---------|--------|------|------|------|
| `FACE_EXCLUDE_MODE` | `"segformer+dwpose"` | string | 얼굴 제외 방법 | "segformer+dwpose" |
| `HAIR_EXCLUDE` | `True` | bool | 머리카락 마스크에서 제외 | True |
| `PANTS_EXCLUDE` | `True` | bool | 바지/다리 마스크에서 제외 | True |
| `HOOD_MERGE` | `True` | bool | hat→upper 인접 hood 포함 | True |
| `HOOD_MERGE_RADIUS` | `15` | int (5-30) | hood 인접 판정 dilation 반복 | 15 |
| `HOOD_FROM_HAIR` | `True` | bool | hair→upper 인접도 hood로 판정 | True |
| `SCARF_MERGE` | `False` | bool | scarf(17) 조건부 합성 | False |

> SAM2 모드에서는 시맨틱 레이블(hat, hair, scarf, pants)이 없으므로 Hood/Hair/Scarf/Pants 관련 파라미터는 무시됨. Face exclude는 DWPose keypoint 타원만 사용.

### 가먼트 적응 관련

| 파라미터 | 기본값 | 타입 | 영향 | 권장 |
|---------|--------|------|------|------|
| `GARMENT_ADAPTIVE_ARMS` | `True` | bool | 가먼트 소매 길이 자동 감지 | True |
| `INCLUDE_ARMS` | `False` | bool | 팔 영역 마스크 포함 (auto override 가능) | False (GARMENT_ADAPTIVE_ARMS가 자동 결정) |

### 추론 패치 관련

| 파라미터 | 기본값 | 타입 | 영향 | 권장 |
|---------|--------|------|------|------|
| `REPAINT_KERNEL` | `1` | int [1,3,5,10] | repaint GaussianBlur 크기 | 1 (하드엣지 — 가상옷 보존) |
| `REPAINT_BINARIZE` | `True` | bool | repaint 직전 mask 이진화 | **True 필수** (gray 경계 정리) |
| `MASK_RESIZE_NEAREST` | `True` | bool | mask resize를 NEAREST로 강제 | **True 필수** (BICUBIC gray 방지) |
| `USE_COMP_MASK_REPAINT` | `False` | bool | repaint에 comp_garment mask 사용 | False (DUAL_MASK 시만 사용) |

### 컨센서스 관련 (SegFormer 모드 전용, SAM2 모드에서는 off)

| 파라미터 | 기본값 | 타입 | 영향 | 권장 |
|---------|--------|------|------|------|
| `CONSENSUS_MODE` | `"interior"` | string [hull/interior/union/off] | consensus 적용 방식 | "off" (SAM2 모드 자동) |
| `CONSENSUS_PAD_X` | `0.08` | float | consensus bbox 좌우 패딩 | 0.08 |
| `CONSENSUS_THRESHOLD` | `0.45` | float | consensus 포함 프레임 비율 | 0.45 |

### 디버그

| 파라미터 | 기본값 | 타입 | 영향 | 권장 |
|---------|--------|------|------|------|
| `DEBUG_DUMP` | `False` | bool | 각 단계 마스크 PNG + metrics.json 저장 | False (개발 시 True) |
| `STICK_WIDTH` | `4` | int [4,8,12,16] | DWPose 시각화 선 두께 | 4 (가상옷 크기에 무관) |

### Dual Mask (선택적, 실험용)

| 파라미터 | 기본값 | 타입 | 영향 | 권장 |
|---------|--------|------|------|------|
| `DUAL_MASK` | `False` | bool | model input / repaint 마스크 분리 | False |
| `UNET_EXTRA_DILATION` | `8` | int (0-20) | UNet 마스크 추가 확장 | 8 |
| `COMP_DILATION` | `3` | int (0-10) | compositing 마스크 dilation | 3 |
| `SEAM_BAND_PX` | `5` | int (0-15) | 경계 seam band 블러 폭 | 5 |

---

> **최종 확인**: 이 문서의 모든 경로, 시그니처, 파라미터는 `recipes/swifttry/notebook_manifest.yaml` (H-2 lines 654-1761, H-3 lines 1923-2103)과 `recipes/swifttry/docs/context.md`의 85개 기술 결정 기록에 기반한다. 문서만으로 전처리 모듈을 독립 구현할 수 있도록 self-contained하게 작성되었다.

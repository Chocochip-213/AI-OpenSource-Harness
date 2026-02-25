# SwiftTry Video Virtual Try-On — 가상옷 수축 + 마스크 품질 문제 리서치

## 프로젝트 개요

**SwiftTry** (https://github.com/VinAIResearch/SwiftTry, arxiv 2412.10178)를 Google Colab에서 실행하는 노트북을 만들고 있다. 업스트림의 demo 모드(TikTokDress 데이터셋)는 잘 작동하지만, **user 모드**(사용자가 자기 영상+옷 이미지 업로드)에서 전처리(마스크/DWPose 생성)를 직접 수행할 때 여러 시각적 문제가 발생한다.

### SwiftTry 아키텍처 (관련 부분만)

```
Input: person_video (.mp4) + garment_image (.png)
  │
  ├─ ReferenceUNet (2D)  ─── garment appearance 인코딩
  ├─ DenoisingUNet (3D)  ─── SD v1.5 기반 diffusion backbone + motion modules
  ├─ PoseGuider          ─── DWPose skeleton conditioning (시각화 이미지 입력)
  ├─ CLIP Image Encoder  ─── visual features
  ├─ VAE (SD-vae-ft-mse) ─── encode/decode latent frames
  │
  ├─ Inference params: 25 DDIM steps, CFG 3.5, v-prediction, zero-SNR
  ├─ Context window: 16 frames, fp16
  ├─ Resolution: W=384, H=512 (latent 48x64)
  │
  └─ **Repaint (post-process)**:
     mask_blurred = GaussianBlur(mask_video, (kernal_size, kernal_size))
     output = generated * mask_blurred + original * (1 - mask_blurred)
     (업스트림 기본: kernal_size = h // 50 ≈ 10)
```

### 입력 데이터 구조 (SwiftTry가 기대하는 것)

```
DATA_DIR/
├── videos/           # 원본 사람 비디오 (.mp4)
├── garments/         # 옷 이미지 (.png)
├── videos_mask/      # 바이너리 마스크 비디오 (.mp4) ← 흰색=옷 영역
├── videos_masked/    # 마스킹된 사람 비디오 (.mp4) ← 옷 영역=회색(128)
├── videos_dwpose/    # DWPose 스켈레톤 비디오 (.mp4)
└── test_pairs.txt    # "video.mp4 garment.png"
```

**TikTokDress 데이터셋** (학습+데모용): 마스크는 SAM2 기반으로 생성됨. 학습 해상도 = 추론 해상도 = 384x512.

---

## 현재 상태 — 관찰되는 문제들

### 문제 1: 가상옷이 마스크보다 작게 생성됨 (핵심 문제)

**현상**:
- 마스크는 원래 옷 영역을 정확하게(또는 약간 넓게) 커버하고 있음
- 그런데 SwiftTry가 생성하는 가상옷은 마스크 영역보다 확연히 작음
- 마스크 영역 내에서 가상옷이 차지하지 않는 "갭 영역"이 존재
- 이 갭 영역에 diffusion 모델이 주변 사물/배경을 예측 생성
- 프레임마다 예측이 달라서 울렁거림(temporal flickering) 발생
- 결과적으로 원래 옷이 그대로 보이는 것처럼 느껴짐

**시각적 묘사**:
```
┌──────────────────────────────┐
│   원본 프레임 (mask=0 영역)    │  ← repaint로 원본 유지
│                              │
│  ┌────────────────────────┐  │
│  │ 마스크 영역 (mask=1)     │  │  ← repaint로 생성 결과 사용
│  │                        │  │
│  │  ┌──────────────────┐  │  │
│  │  │   가상옷 (작음)    │  │  │  ← 모델이 실제 생성한 garment
│  │  └──────────────────┘  │  │
│  │                        │  │
│  │  ↑ 이 갭: 모델이 배경/  │  │  ← 가상옷 경계~마스크 경계 사이
│  │    사물로 채움 → 울렁거림│  │
│  └────────────────────────┘  │
│                              │
└──────────────────────────────┘
```

**repaint 공식과의 관계**:
- `output = generated * mask_blurred + original * (1 - mask_blurred)`
- REPAINT_KERNEL=1 (no blur)일 때: mask 경계는 하드엣지. 하지만 문제는 경계가 아님.
- 문제는 **mask=1인 영역 내부**에서 모델이 생성한 garment가 전체를 채우지 못함
- mask=1 영역 중 garment가 없는 부분 → 모델이 그냥 "뭔가"를 생성 → 배경/사물 hallucination
- REPAINT_KERNEL과 무관한 문제일 수 있음

### 문제 2: 후드 모자가 마스크에서 누락

**현상**:
- 사용자가 후드티(hoodie)를 입고 있는 영상
- SegFormer가 후드 모자(hood) 부분을 upper-clothes(4)로 인식하지 않음
- 후드 모자는 아마 hat(1) 또는 hair(2)로 분류되는 것으로 추정
- 현재 TARGET_LABELS = {4, 7, 14, 15} 에 hat(1)이 미포함
- 결과: 가상옷 생성 시 원래 후드 모자가 그대로 남아 있음 → 가상옷과 불일치

**SegFormer (mattmdjaga/segformer_b2_clothes) 18-class 레이블**:
```
 0: Background      6: Pants        12: Left-leg
 1: Hat             7: Dress        13: Right-leg
 2: Hair            8: Belt         14: Left-arm
 3: Sunglasses      9: Left-shoe    15: Right-arm
 4: Upper-clothes  10: Right-shoe   16: Bag
 5: Skirt          11: Face         17: Scarf
```

### 문제 3: 배경 의자의 패딩 점퍼가 마스크에 포함

**현상**:
- 배경에 의자가 있고, 그 의자에 패딩 점퍼가 걸쳐져 있음
- 카메라 각도상 사용자의 팔 바로 옆에 겹쳐 보임
- SegFormer는 2D 시맨틱 세그멘테이션 → depth 정보 없음
- 패딩 점퍼도 upper-clothes(4)로 분류됨
- 사용자 옷과 물리적으로 인접 → connected component 분석에서 같은 component로 연결
- consensus bbox로도 걸러지지 않음 (팔 옆에 있으니 bbox 내부)

### 문제 4: 마스크가 목까지 올라감 (대응 완료, 미테스트)

**현상**:
- SegFormer upper-clothes(4)가 칼라/목선까지 포함
- binary_dilation(5)이 위로 확장 → 마스크가 목까지
- diffusion 모델이 목에 옷을 생성 → 목 꺾임 아티팩트
- **대응**: face label(11) dilation(H*0.07) 차감 구현 (아직 테스트 안 됨)

---

## 지금까지 시도한 것들 (시간순)

### 시도 1: 마스크 후처리 과보상 (초기)
- **내용**: binary_closing + dilation 12 + kernal_size=1 sed 패치
- **결과**: 마스크가 너무 확장되어 다른 문제 발생. "과보상"으로 판단하여 제거.
- **교훈**: 마스크를 키운다고 garment가 커지지 않음. 마스크 확장은 오히려 갭 영역만 증가.

### 시도 2: DWPose stickwidth 파라미터화 (4→8→12)
- **가설**: PoseGuider에 입력되는 DWPose 시각화의 스켈레톤 두께가 garment 실루엣의 공간 블루프린트
- **내용**: stickwidth를 4→8→12로 변경하여 더 두꺼운 스켈레톤 생성
- **결과**: 가상옷 크기에 **변화 없음**
- **교훈**: stickwidth는 시각화 렌더링 두께만 변경. PoseGuider는 관절 위치 가이드 역할이지 garment 크기를 결정하지 않음.

### 시도 3: REPAINT_KERNEL 파라미터화
- **가설**: repaint의 gaussian blur(kernal_size=h//50≈10)가 마스크 경계를 소프트닝 → 가상옷이 원본에 "녹아듦"
- **내용**: kernal_size를 파라미터화하여 1/3/5/10 선택 가능
- **REPAINT_KERNEL=1 결과**: 경계 블러는 제거되었으나, **가상옷 자체가 여전히 작게 생성됨**. 블러 제거와 무관하게 garment가 마스크 영역을 채우지 못함. 갭 영역의 hallucination + flickering 지속.
- **교훈**: repaint blur는 부차적 문제. 근본 원인은 **모델이 생성하는 garment 크기 자체**가 마스크보다 작다는 것.

### 시도 4: Consensus 마스크 공간 제한 (bbox)
- **목적**: 턱/원거리 의자 오감지 방지
- **내용**: median(50%) → connected components → largest component bbox → consensus를 bbox 내부로만 제한
- **결과**: 멀리 떨어진 물체는 걸러지나, 팔 옆에 인접한 의자 패딩은 같은 component로 연결되어 여전히 포함.

### 시도 5: 얼굴/목 영역 제외 (구현 완료, 미테스트)
- **내용**: face label(11) dilation(H*0.07) 차감
- **상태**: 코드 작성 완료, Colab에서 미테스트

### 시도 6: 마스크 경로 불일치 분석 + Fix (구현 완료, Colab 테스트 대기)
- **가설**: inference.py 내부에서 마스크가 두 갈래로 분기됨:
  - **Model input path**: `prepare_mask_and_masked_image()` → numpy `/ 255.0` → `>= 0.5` binarize → 0/1
  - **Repaint path**: 원본 PIL mask → `GaussianBlur(kernal_size)` → `np.array(mask) / 255` → 연속값 0~1
  - mp4 H.264 손실 압축 + Pillow BICUBIC resize가 binary mask 경계에 gray 중간값 생성
  - Model: gray(예: 100) → 100/255=0.39 < 0.5 → binarize to 0 → 인페인트 안 함
  - Repaint: 같은 gray 100 → 0.39 → 39% generated + 61% original 블렌딩
  - generated는 인페인트 안 된 hallucination → 갭/울렁거림
- **구현 Fix**:
  - `REPAINT_BINARIZE=True`: repaint 직전 `mask.point(lambda p: 255 if p >= 128 else 0)` → 두 경로의 mask 의미 일치
  - `MASK_RESIZE_NEAREST=True`: mask resize를 NEAREST로 → gray 경계 생성 방지
  - `git checkout inference.py` → Python patching으로 멱등성 보장
- **검증 도구**: H-2.5 진단 셀 — mp4 round-trip gray 오염 정도, PNG vs MP4 면적 손실, 히스토그램, 시각화 제공
- **상태**: 코드 구현 완료, Colab 테스트 대기

---

## inference.py 마스크 처리 경로 (소스 기반 확인)

### Path 1: Model Input (prepare_mask_and_masked_image)
```python
# src/pipelines/pipeline_swift_try.py
# PIL Image branch:
masks = np.concatenate([np.array(m.convert("L"))[None, None, :] for m in masks], axis=0)
masks = masks.astype(np.float32) / 255.0
masks[masks < 0.5] = 0    # ← BINARIZE HERE
masks[masks >= 0.5] = 1   # ← BINARIZE HERE
masks = torch.from_numpy(masks)
# 이후 F.interpolate로 latent 해상도(48x64)로 다운샘플
# UNet에 9채널 입력: noisy_latent(4) + mask(1) + masked_image_latent(4)
```

### Path 2: Repaint (post-processing)
```python
# inference.py
def repaint(person, mask, result):
    _, h = result.size
    kernal_size = h // 50  # ≈ 10
    if kernal_size % 2 == 0:
        kernal_size += 1
    mask = mask.filter(ImageFilter.GaussianBlur(kernal_size))  # ← NO BINARIZE
    person_np = np.array(person)
    result_np = np.array(result)
    mask_np = np.array(mask) / 255  # ← 연속값 0~1
    mask_np = mask_np[:, :, None]
    repaint_result = person_np * (1 - mask_np) + result_np * mask_np
    return Image.fromarray(repaint_result.astype(np.uint8))
```

### 두 경로에 전달되는 mask 객체
```python
# inference.py tryon_video()
mask_list = [mask_pil.convert('L').resize((width, height))  # ← BICUBIC default!
             for mask_pil in read_frames(mask_video_path)]

# 같은 mask_list가 양쪽에 전달:
video = self.pipeline(..., mask_list[:clip_length], ...)  # → Path 1 (binarized)
result_video = repaint_video(image_list, mask_list, ...)   # → Path 2 (continuous)
```

**핵심**: mask_list의 PIL 객체들이 mp4 디코딩 후 gray 오염된 상태에서 양 경로에 전달됨.
Path 1은 binarize로 gray를 정리하지만, Path 2는 gray를 그대로 사용 → 불일치.

---

## 현재 마스크 생성 파이프라인 (전체)

```python
# 1. SegFormer 배치 추론
TARGET_LABELS = {4, 7, 14, 15}  # upper-clothes, dress, left-arm, right-arm
FACE_LABEL = 11
DILATION_ITER = 5
NECK_MARGIN = int(H * 0.07)

raw_masks = []   # per-frame clothing mask
face_masks = []  # per-frame face mask

for batch:
    preds = segformer(frames)  # (B, H, W) class predictions
    for pred in preds:
        raw_masks.append(  np.isin(pred, TARGET_LABELS)  )
        face_masks.append( pred == FACE_LABEL )

# 2. Consensus mask (bbox-restricted)
stacked = np.stack(raw_masks)              # (N, H, W)
median_mask = (stacked.mean(0) >= 0.5)     # 50% threshold = 안정 영역
labeled, n = ndimage_label(median_mask)    # connected components
main_clothing = largest_component(labeled)  # 가장 큰 = 본인 의류
body_bbox = bounding_box(main_clothing, pad_x=20%, pad_y=5%)
consensus = (stacked.mean(0) >= 0.3) * body_bbox  # 30% threshold, bbox 내부만

# 3. Per-frame 후처리
for i in range(n_frames):
    smoothed = temporal_median(raw_masks, window=3)  # 3프레임 rolling median
    merged = max(smoothed, consensus)                # consensus union
    filled = binary_fill_holes(merged)
    dilated = binary_dilation(filled, iter=5)
    # 얼굴/목 제외
    if face_masks[i].any():
        face_zone = binary_dilation(face_masks[i], iter=NECK_MARGIN)
        dilated = dilated * (1 - face_zone)
    save(dilated)
```

---

## 해결이 필요한 질문들

### Q1 (핵심): 왜 SwiftTry가 마스크보다 작은 garment를 생성하는가?

가능한 원인 후보:
1. **학습 데이터 마스크 vs 우리 마스크의 특성 차이** — TikTokDress SAM2 마스크는 옷에 tight하고, 우리 SegFormer 마스크는 더 넓을 수 있음. 모델이 tight 마스크에 최적화되어 우리 마스크에서 전체를 채우지 못함?
2. **videos_masked 생성 방식 차이** — 우리는 mask=1인 곳을 회색(128)으로 채움. TikTokDress는 어떻게 생성하는지? agnostic mask의 생성 방식이 다르면 conditioning이 달라짐.
3. **모델 구조적 한계** — SD v1.5 latent 48x64에서 garment 경계 정밀도 한계?
4. **ReferenceUNet이 garment 크기를 결정** — 마스크와 무관하게 garment appearance에서 크기를 추론?
5. **inference.py의 다른 처리** — repaint 외에 resize, crop, padding 등이 garment에 영향?
6. **DWPose와 마스크의 상호작용** — PoseGuider가 마스크 범위를 넘어서는 garment를 억제?

### Q2: 인접 배경 물체(의자 패딩)를 걸러내려면?

- SegFormer는 depth 정보 없음
- Connected component로는 인접 물체와 분리 불가
- DWPose keypoint 기반으로 body region을 더 정밀하게 잡을 수 있는가?
- 또는 다른 segmentation 모델(depth-aware)?

### Q3: 후드 같은 특수 의류 부위를 마스크에 포함시키려면?

- TARGET_LABELS에 hat(1), scarf(17) 추가하면 되는가?
- 아니면 모자/스카프는 try-on에서 제외해야 하는가?
- SwiftTry가 후드를 포함한 garment를 생성할 수 있는가? (학습 데이터에 후드 포함?)

### Q4: TikTokDress 데이터셋의 마스크 생성 방법은?

- SAM2로 생성한다고 알려져 있는데, 정확한 프로세스는?
- agnostic mask (videos_masked)는 어떻게 만드는지?
- 마스크의 tight/loose 정도가 garment 품질에 어떤 영향?
- inference.py 내부에서 mask를 어떻게 사용하는지? (latent space 변환? 직접 사용?)

---

## 환경 정보

- Google Colab A100 GPU
- torch 2.9.0, CUDA 12.x
- diffusers 0.36.0 (Colab 기본, compatibility patch 적용)
- SwiftTry commit: 57d3f0b8b25509d4b650db68391c1ad11b86e833
- 입력 해상도: 384x512 (학습 해상도와 동일)
- SegFormer: mattmdjaga/segformer_b2_clothes (HuggingFace)

---

## 참고 링크

- SwiftTry Paper: https://arxiv.org/abs/2412.10178
- SwiftTry Code: https://github.com/VinAIResearch/SwiftTry
- SwiftTry Weights: https://huggingface.co/NMHung/SwiftTry
- TikTokDress Dataset: https://huggingface.co/datasets/nguyenquivinhquang/TikTokDress
- SegFormer Clothes: https://huggingface.co/mattmdjaga/segformer_b2_clothes
- SwiftTry inference.py: https://github.com/VinAIResearch/SwiftTry/blob/main/inference.py
- SwiftTry pipeline: https://github.com/VinAIResearch/SwiftTry/blob/main/src/pipelines/pipeline_swift_try.py

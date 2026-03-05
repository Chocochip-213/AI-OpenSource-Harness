# AR 바디 트래킹 파이프라인 설계 문서

> **문서 버전**: 1.1
> **최종 갱신**: 2026-03-03
> **범위**: MediaPipe Pose Landmarker + Depth Anything V2 → Kalidokit → 신체 측정 → 핏 평가 → Three.js 본 리깅

---

## 1. 개요

### 1.1 아키텍처 요약

AutoFit v2의 바디 트래킹 파이프라인은 5단계로 구성된다.

```
웹캠 (Camera API)
  │
  ├─────────────────────────────┐
  ▼                             ▼
MediaPipe Pose Landmarker     Depth Anything V2
  │  33 키포인트 + 3D 좌표       │  Metric Depth (미터 단위)
  │  + 월드 좌표                 │  ONNX Runtime Web
  │                             │
  ▼                             ▼
1-Euro Filter 적응형 스무딩    Depth Map 처리
  │  속도 적응형 지터 제거,       │  사용자 영역 depth 추출
  │  오클루전 보간
  │                             │
  └──────────────┬──────────────┘
                 │
                 ▼
  Body Measurer (신체 치수 계산)
    │  depth + keypoints → 7개 신체 치수 (cm)
    │  카메라 거리(m) + 핀홀 카메라 역투영
    │
    ▼
  Fit Evaluation Engine
    │  신체 치수 vs 의류 실측 치수 → 핏 타입 분류
    │  적합도(%) + 정확도(%) 산출
    │
    ▼
  Kalidokit 포즈→본 매핑
    │  각 본의 쿼터니언/오일러 회전값
    │
    ▼
  Three.js SkinnedMesh 본 업데이트
    │  바디 메쉬 + 의류 리깅
    │  + 핏 평가 오버레이
    │
    ▼
  R3F 렌더 (카메라 배경 + 3D 오버레이 + 핏 UI)
```

### 1.2 설계 원칙

- **WebXR 미사용**: WebXR Device API는 AR 세션을 위한 표준이지만, 가상 시착에서는
  카메라 피드 + canvas 오버레이 방식이 더 넓은 호환성과 제어를 제공한다.
- **클라이언트 사이드 처리**: 카메라 영상은 서버로 전송하지 않으며, 모든 추론은
  브라우저 내에서 수행한다 (프라이버시 보장).
- **점진적 강등**: Heavy 모델 → Lite 모델 자동 폴백.

---

## 2. MediaPipe Pose Landmarker

### 2.1 모델 선택

| 모델 | 키포인트 | 정확도 | 속도 (모바일) | 용도 |
|------|---------|--------|-------------|------|
| **Heavy** | 33 | 최고 | 30-40fps | 데스크톱 기본 |
| Full | 33 | 높음 | 40-50fps | 데스크톱/모바일 기본 |
| Lite | 33 | 보통 | 50-60fps | 모바일 폴백 |

**기본 선택(권장)**:

- 데스크톱: Heavy (정확도 우선)
- 모바일: Full (성능/배터리 균형)

**폴백 조건(예시)**: FPS < 25 지속 3초 → 한 단계 다운그레이드(Heavy→Full→Lite)

### 2.2 키포인트 정의 (33개)

```
인덱스  키포인트명           영역
──────  ──────────────────  ──────
  0     코                   얼굴
  1     왼쪽 눈 안쪽         얼굴
  2     왼쪽 눈              얼굴
  3     왼쪽 눈 바깥쪽       얼굴
  4     오른쪽 눈 안쪽       얼굴
  5     오른쪽 눈            얼굴
  6     오른쪽 눈 바깥쪽     얼굴
  7     왼쪽 귀              얼굴
  8     오른쪽 귀            얼굴
  9     입 왼쪽              얼굴
 10     입 오른쪽            얼굴
 11     왼쪽 어깨            상반신
 12     오른쪽 어깨          상반신
 13     왼쪽 팔꿈치          상반신
 14     오른쪽 팔꿈치        상반신
 15     왼쪽 손목            상반신
 16     오른쪽 손목          상반신
 17     왼쪽 새끼손가락      상반신
 18     오른쪽 새끼손가락    상반신
 19     왼쪽 검지            상반신
 20     오른쪽 검지          상반신
 21     왼쪽 엄지            상반신
 22     오른쪽 엄지          상반신
 23     왼쪽 힙              하반신
 24     오른쪽 힙            하반신
 25     왼쪽 무릎            하반신
 26     오른쪽 무릎          하반신
 27     왼쪽 발목            하반신
 28     오른쪽 발목          하반신
 29     왼쪽 뒤꿈치          하반신
 30     오른쪽 뒤꿈치        하반신
 31     왼쪽 발끝            하반신
 32     오른쪽 발끝          하반신
```

### 2.3 출력 데이터 구조

각 키포인트는 두 가지 좌표계로 제공된다.

**Normalized Landmarks (NDC)**:
```typescript
interface NormalizedLandmark {
  x: number;  // 0.0 ~ 1.0 (이미지 너비 기준)
  y: number;  // 0.0 ~ 1.0 (이미지 높이 기준)
  z: number;  // 깊이 (카메라 기준 상대값, 힙 깊이 ≈ 원점)
  visibility: number;  // 0.0 ~ 1.0 (키포인트가 보이는 정도)
  presence: number;    // 0.0 ~ 1.0 (키포인트가 존재하는 확률)
}
```

**World Landmarks (미터 단위)**:
```typescript
interface WorldLandmark {
  x: number;  // 미터 단위 (힙 중심 원점 기준)
  y: number;  // 미터 단위
  z: number;  // 미터 단위
  visibility: number;
  presence: number;
}
```

### 2.4 초기화 설정

```typescript
import { PoseLandmarker, FilesetResolver } from '@mediapipe/tasks-vision';

const vision = await FilesetResolver.forVisionTasks(
  'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision/wasm'
);

const poseLandmarker = await PoseLandmarker.createFromOptions(vision, {
  baseOptions: {
    modelAssetPath: 'pose_landmarker_heavy.task',
    delegate: 'GPU',  // WebGL delegate (가능 시)
  },
  runningMode: 'VIDEO',
  numPoses: 1,                        // 단일 사용자
  minPoseDetectionConfidence: 0.5,    // 감지 신뢰도 임계값
  minPosePresenceConfidence: 0.5,     // 존재 신뢰도 임계값
  minTrackingConfidence: 0.5,         // 트래킹 신뢰도 임계값
  outputSegmentationMasks: false,     // 세그멘테이션 마스크 불필요
});
```

### 2.5 추론 루프

```typescript
function trackFrame(videoElement: HTMLVideoElement, timestamp: number): void {
  const result = poseLandmarker.detectForVideo(videoElement, timestamp);

  if (result.landmarks.length > 0) {
    const landmarks = result.landmarks[0];       // Normalized (33개)
    const worldLandmarks = result.worldLandmarks[0]; // World (33개)

    // 스무딩 필터 적용
    const smoothed = smoothingFilter.apply(landmarks, worldLandmarks);

    // 포즈→본 매핑
    const boneRotations = mapPoseToBones(smoothed);

    // Three.js 본 업데이트
    updateSkeletonBones(boneRotations);
  }
}

// requestAnimationFrame 기반 루프
function animate(): void {
  const timestamp = performance.now();
  trackFrame(videoRef.current!, timestamp);
  requestAnimationFrame(animate);
}
```

---

## 2b. Depth Anything V2 Metric Depth 통합

### 2b.1 모델 개요

Depth Anything V2 Metric Depth는 단안 카메라 영상에서 각 픽셀의 거리(미터) **추정치**를 출력한다.
절대 스케일을 목표로 하지만, 디바이스/렌즈/조명/배경에 따라 오차가 커질 수 있으므로 **캘리브레이션 + 품질 게이트 + 폴백**을 전제로 통합한다.

| 항목 | 값 |
|------|-----|
| 모델 | Depth Anything V2 Metric Depth (Small) |
| 입력 | RGB 이미지 (518×518 리사이즈) |
| 출력 | depth map (float32, H×W, 미터 단위) |
| 런타임 | ONNX Runtime Web (WebGL/WebGPU backend) |
| 모델 크기 | ~100MB (ONNX quantized) |
| 추론 시간 (데스크톱) | ~15ms (WebGPU) / ~25ms (WebGL) |
| 추론 시간 (모바일) | ~40ms (WebGL) |
| 유효 거리 범위 | 0.5 ~ 4.0m |

### 2b.2 모델 로딩 및 초기화

```typescript
import * as ort from 'onnxruntime-web';

class DepthSensor {
  private session: ort.InferenceSession | null = null;
  private readonly MODEL_INPUT_SIZE = 518;

  async initialize(modelPath: string): Promise<void> {
    // WebGPU 우선, WebGL 폴백
    const executionProviders = navigator.gpu
      ? ['webgpu', 'webgl']
      : ['webgl'];

    this.session = await ort.InferenceSession.create(modelPath, {
      executionProviders,
      graphOptimizationLevel: 'all',
    });
  }

  // 모델 상태 확인
  get isReady(): boolean {
    return this.session !== null;
  }
}
```

### 2b.3 추론 루프

```typescript
async inferDepth(videoFrame: HTMLVideoElement): Promise<Float32Array> {
  if (!this.session) throw new Error('Depth 모델 미초기화');

  // 1. 비디오 프레임 → 518×518 리사이즈
  const canvas = new OffscreenCanvas(this.MODEL_INPUT_SIZE, this.MODEL_INPUT_SIZE);
  const ctx = canvas.getContext('2d')!;
  ctx.drawImage(videoFrame, 0, 0, this.MODEL_INPUT_SIZE, this.MODEL_INPUT_SIZE);

  // 2. 이미지 데이터 → ONNX 텐서 (CHW, float32, 정규화)
  const imageData = ctx.getImageData(0, 0, this.MODEL_INPUT_SIZE, this.MODEL_INPUT_SIZE);
  const inputTensor = this.preprocessImage(imageData);

  // 3. 추론
  const feeds = { image: inputTensor };
  const results = await this.session.run(feeds);

  // 4. depth map 반환 (float32, 미터 단위)
  return results.depth.data as Float32Array;
}
```

### 2b.4 카메라-사용자 거리 추출

```typescript
function extractUserDistance(
  depthMap: Float32Array,
  depthWidth: number,
  depthHeight: number,
  landmarks: NormalizedLandmark[]
): number {
  // 핵심 키포인트(어깨, 힙)의 depth 값을 샘플링
  const keyIndices = [11, 12, 23, 24]; // 좌우 어깨, 좌우 힙
  const depths: number[] = [];

  for (const idx of keyIndices) {
    const lm = landmarks[idx];
    if (lm.visibility < 0.5) continue;

    // NDC 좌표 → depth map 픽셀 좌표
    const px = Math.round(lm.x * depthWidth);
    const py = Math.round(lm.y * depthHeight);

    // 3×3 영역 평균 (노이즈 완화)
    const depth = sampleDepthArea(depthMap, depthWidth, depthHeight, px, py, 3);
    if (depth > 0.5 && depth < 4.0) {
      depths.push(depth);
    }
  }

  // 중앙값 기반 거리 산출 (아웃라이어 제거)
  depths.sort((a, b) => a - b);
  return depths[Math.floor(depths.length / 2)] ?? 0;
}
```

### 2b.5 사용자 감지 (Depth 기반)

depth map을 분석하여 0.5~4m 범위 내 사용자 존재를 자동 감지한다.

```typescript
interface UserDetectionResult {
  detected: boolean;      // 사용자 감지 여부
  distance: number;       // 카메라-사용자 거리 (m)
  message: string;        // 사용자 안내 메시지
}

function detectUser(
  depthMap: Float32Array,
  depthWidth: number,
  depthHeight: number
): UserDetectionResult {
  // 화면 중앙 영역 (40~60%)의 depth 분석
  const centerDepths: number[] = [];
  const startX = Math.floor(depthWidth * 0.3);
  const endX = Math.floor(depthWidth * 0.7);
  const startY = Math.floor(depthHeight * 0.2);
  const endY = Math.floor(depthHeight * 0.8);

  for (let y = startY; y < endY; y += 4) {
    for (let x = startX; x < endX; x += 4) {
      const d = depthMap[y * depthWidth + x];
      if (d > 0.3 && d < 5.0) centerDepths.push(d);
    }
  }

  if (centerDepths.length === 0) {
    return { detected: false, distance: 0, message: '카메라 앞에 서 주세요' };
  }

  centerDepths.sort((a, b) => a - b);
  const medianDepth = centerDepths[Math.floor(centerDepths.length / 2)];

  if (medianDepth < 0.5) {
    return { detected: false, distance: medianDepth, message: '카메라에서 조금 멀어져 주세요' };
  }
  if (medianDepth > 4.0) {
    return { detected: false, distance: medianDepth, message: '카메라에 가까이 와 주세요' };
  }

  return { detected: true, distance: medianDepth, message: '' };
}
```

### 2b.6 MediaPipe와 저주기 Depth 결합

Pose는 30~60Hz로 처리하고, Depth는 1~5Hz 저주기로 처리하여 전체 프레임 지연/발열을 억제한다.

```typescript
type FrameResult = {
  poseResult: PoseLandmarkerResult;
  depthMap?: Float32Array; // 최신 depth (있을 때만)
};

// ⚠️ GPU 경합 주의: WebGL 백엔드에서 MediaPipe Pose와 Depth Anything V2가
// 동일 GPU 리소스를 공유하면 프레임 드롭이 발생할 수 있다.
// 완화 전략:
// 1. Depth 추론을 저주기(1~5Hz)로 제한하여 Pose와 시간적으로 분리
// 2. Depth를 CPU(WASM) 백엔드로 실행 (정확도 유지, 지연 증가)
// 3. requestIdleCallback으로 Depth 추론을 유휴 시간에 스케줄링
class DepthScheduler {
  private lastDepthAt = 0;
  private latestDepth: Float32Array | undefined;

  constructor(private readonly intervalMs: number) {}

  async maybeUpdate(videoElement: HTMLVideoElement, depthSensor: DepthSensor): Promise<void> {
    const now = performance.now();
    if (now - this.lastDepthAt < this.intervalMs) return;
    this.lastDepthAt = now;

    try {
      this.latestDepth = await depthSensor.inferDepth(videoElement);
    } catch {
      // Depth 실패 시 최신값 유지(또는 undefined로 리셋) + 품질 게이트에서 자동 비활성화
    }
  }

  getLatest(): Float32Array | undefined {
    return this.latestDepth;
  }
}

async function processFrame(
  videoElement: HTMLVideoElement,
  timestamp: number,
  poseLandmarker: PoseLandmarker,
  depthScheduler: DepthScheduler,
  depthSensor: DepthSensor
): Promise<FrameResult> {
  const poseResult = poseLandmarker.detectForVideo(videoElement, timestamp);
  void depthScheduler.maybeUpdate(videoElement, depthSensor);
  return { poseResult, depthMap: depthScheduler.getLatest() };
}
```

---

## 3. Kalidokit 포즈 매핑

### 3.1 매핑 개요

Kalidokit은 MediaPipe의 33개 키포인트를 Three.js 본 시스템의 회전값으로 변환한다.
각 관절의 회전은 쿼터니언 또는 오일러 각도로 출력된다.

### 3.2 상반신 본 매핑

| 본 이름 | 입력 키포인트 | 출력 | 설명 |
|---------|-------------|------|------|
| Spine | 11, 12, 23, 24 | pitch, roll | 몸통 전후/좌우 기울기 |
| Spine1 | 11, 12 | pitch, roll | 상부 척추 |
| Chest | 11, 12 | pitch, roll, yaw | 가슴 회전 |
| Neck | 0, 11, 12 | pitch, yaw, roll | 목 회전 |
| Head | 0, 1~10 | pitch, yaw, roll | 머리 회전 (눈/코/입 기반) |
| LeftUpperArm | 11, 13 | pitch, roll, yaw | 왼쪽 상완 |
| LeftLowerArm | 13, 15 | pitch | 왼쪽 전완 (팔꿈치 굽힘) |
| LeftHand | 15, 17, 19, 21 | pitch, yaw | 왼쪽 손목 |
| RightUpperArm | 12, 14 | pitch, roll, yaw | 오른쪽 상완 |
| RightLowerArm | 14, 16 | pitch | 오른쪽 전완 |
| RightHand | 16, 18, 20, 22 | pitch, yaw | 오른쪽 손목 |

### 3.3 하반신 본 매핑

| 본 이름 | 입력 키포인트 | 출력 | 설명 |
|---------|-------------|------|------|
| Hips | 23, 24 | position, rotation | 루트 본 (위치 + 회전) |
| LeftUpperLeg | 23, 25 | pitch, roll | 왼쪽 허벅지 |
| LeftLowerLeg | 25, 27 | pitch | 왼쪽 종아리 (무릎 굽힘) |
| LeftFoot | 27, 29, 31 | pitch | 왼쪽 발 |
| RightUpperLeg | 24, 26 | pitch, roll | 오른쪽 허벅지 |
| RightLowerLeg | 26, 28 | pitch | 오른쪽 종아리 |
| RightFoot | 28, 30, 32 | pitch | 오른쪽 발 |

### 3.4 얼굴 회전 (Head Rotation)

```typescript
interface FaceRotation {
  yaw: number;    // 좌우 회전 (라디안)
  pitch: number;  // 상하 회전 (라디안)
  roll: number;   // 기울임 (라디안)
}

// 눈, 코, 입 키포인트의 상대적 위치로 머리 회전각 계산
// Kalidokit 내부에서 자동 처리
```

### 3.5 출력 형식

```typescript
interface PoseRigResult {
  // 각 본의 회전값
  Hips: { position: Vector3; rotation: Euler; };
  Spine: { rotation: Euler; };
  Chest: { rotation: Euler; };
  Neck: { rotation: Euler; };
  Head: { rotation: Euler; };
  LeftUpperArm: { rotation: Euler; };
  LeftLowerArm: { rotation: Euler; };
  LeftHand: { rotation: Euler; };
  RightUpperArm: { rotation: Euler; };
  RightLowerArm: { rotation: Euler; };
  RightHand: { rotation: Euler; };
  LeftUpperLeg: { rotation: Euler; };
  LeftLowerLeg: { rotation: Euler; };
  LeftFoot: { rotation: Euler; };
  RightUpperLeg: { rotation: Euler; };
  RightLowerLeg: { rotation: Euler; };
  RightFoot: { rotation: Euler; };
}
```

### 3.6 Kalidokit 사용 예시

```typescript
import * as Kalidokit from 'kalidokit';

// ⚠️ Kalidokit 호환성 주의 (Deprecated 라이브러리):
// Kalidokit은 2022년 이후 업데이트가 중단된 상태(deprecated)이며,
// 구버전 @mediapipe/holistic (v1) 콜백 API 기준으로 설계되었다.
// 본 프로젝트의 @mediapipe/tasks-vision (v2) Promise API와 호환되지 않으므로
// 반드시 어댑터 레이어가 필요하다.
//
// 주요 비호환 포인트:
// - v1: results.poseLandmarks (NormalizedLandmarkList)
//   v2: result.landmarks[0] (NormalizedLandmark[])
// - v1: 콜백 기반 onResults()
//   v2: Promise 기반 detectForVideo()
// - v2에서 visibility가 undefined일 수 있음 (v1은 항상 number)
//
// 권장 전략: Kalidokit 소스(~350줄, 의존성 제로)를 인라인 포크하여
// v2 포맷에 맞게 어댑터를 작성한다. M2 착수 전 PoC 필수.

function mapPoseToBones(
  landmarks: NormalizedLandmark[],
  worldLandmarks: WorldLandmark[]
): PoseRigResult {
  // Kalidokit.Pose.solve()는 MediaPipe 키포인트를 받아
  // Three.js 호환 본 회전값을 반환한다
  const poseRig = Kalidokit.Pose.solve(worldLandmarks, landmarks, {
    runtime: 'mediapipe',
    enableLegs: true,
  });

  return poseRig;
}
```

---

## 4. VRM 아바타 프리셋

### 4.1 VRM 포맷 채택 근거

| 항목 | SMPL | 커스텀 glTF | VRM 아바타 |
|------|------|-----------|-----------|
| 라이선스 | 학술/상업 별도 라이선스 | 자체 제작 (제한 없음) | MIT (three-vrm) |
| 본 구조 | 자체 정의 | 커스텀 | VRMHumanoid (표준화) |
| Kalidokit 호환 | 별도 매핑 필요 | 별도 매핑 필요 | **네이티브 호환** |
| 생태계 | 학술 위주 | - | pixiv 유지보수, VTuber 생태계 |
| 런타임 비용 | WASM shape blending | glTF 로드 | glTF 확장 로드 |
| 웹 호환 | 별도 WASM 포팅 필요 | glTF 표준 | glTF 확장 (three-vrm) |

**결론**: VRM 포맷은 Kalidokit과 네이티브 호환되는 본 구조(VRMHumanoid)를 제공하며,
three-vrm 라이브러리를 통해 Three.js/R3F에서 즉시 사용 가능하다.
VRM의 표준화된 본 네이밍은 별도 매핑 테이블 없이 Kalidokit 출력을 직접 적용할 수 있어
개발 비용을 크게 절감한다.

### 4.2 프리셋 구성

| 프리셋 ID | 성별 | 사이즈 | 어깨폭(cm) | 가슴(cm) | 허리(cm) | 힙(cm) | 팔길이(cm) | 다리안쪽(cm) | 키(cm) |
|----------|------|--------|-----------|---------|---------|--------|-----------|------------|--------|
| M-XS | 남성 | XS | 40 | 86 | 72 | 90 | 57 | 75 | 165 |
| M-S | 남성 | S | 42 | 89 | 76 | 93 | 58 | 76 | 170 |
| M-M | 남성 | M | 44 | 92 | 80 | 96 | 60 | 78 | 175 |
| M-L | 남성 | L | 46 | 98 | 86 | 100 | 62 | 80 | 178 |
| M-XL | 남성 | XL | 48 | 104 | 92 | 104 | 63 | 81 | 180 |
| M-XXL | 남성 | XXL | 50 | 110 | 98 | 108 | 64 | 82 | 183 |
| F-XS | 여성 | XS | 36 | 78 | 60 | 84 | 54 | 72 | 155 |
| F-S | 여성 | S | 38 | 82 | 64 | 88 | 55 | 73 | 158 |
| F-M | 여성 | M | 40 | 86 | 68 | 92 | 57 | 75 | 163 |
| F-L | 여성 | L | 42 | 92 | 74 | 96 | 58 | 76 | 165 |
| F-XL | 여성 | XL | 44 | 98 | 80 | 100 | 59 | 77 | 168 |
| F-XXL | 여성 | XXL | 46 | 104 | 86 | 104 | 60 | 78 | 170 |

**기준값**: M 남성 프리셋 = 키 175, 가슴 92, 허리 80, 힙 96, 어깨 44, 팔길이 60, 다리안쪽 78

**사이즈 범위**: XS, S, M, L, XL, XXL, FREE

### 4.3 Depth 기반 정밀 신체 측정 알고리즘

Depth Anything V2 Metric Depth의 절대 거리(m)와 MediaPipe 33 키포인트를 결합하여 사용자의 실제 신체 치수를 센티미터 단위로 계산한다.

#### 핀홀 카메라 모델 기반 역투영

카메라 초점 거리(focal length)와 depth 값을 이용하여 픽셀 거리를 실세계 거리로 변환한다.

#### 카메라 Focal Length 획득

핀홀 카메라 모델 역투영에 필수적인 focal length는 다음 순서로 획득한다:

1. **MediaStreamTrack.getCapabilities()** (지원 시):
   `focalLength` 속성이 있으면 직접 사용
2. **기본값 폴백**: 일반적인 스마트폰 웹캠의 focal length 기본값 사용
   - 스마트폰 전면 카메라: ~3.5mm (35mm 환산 ~28mm)
   - 노트북 웹캠: ~3.6mm (35mm 환산 ~60mm)
   - 화각(FOV)에서 역산: `f = (imageWidth / 2) / tan(FOV / 2)`
3. **사용자 캘리브레이션**: 알려진 크기의 기준 물체(A4 용지, 신용카드 등)를
   카메라에 비춰 focal length를 역산하는 선택적 캘리브레이션 단계

> **MVP 전략**: 기본값 폴백(옵션 2)을 사용하되, 사용자가 키를 직접 입력하면
> 해당 값으로 스케일 팩터를 보정하여 정확도를 높인다.

```typescript
interface BodyMeasurement {
  shoulder_width_cm: number;          // 어깨너비
  chest_circumference_cm: number;     // 가슴둘레
  waist_circumference_cm: number;     // 허리둘레
  hip_circumference_cm: number;       // 힙둘레
  height_cm: number;                  // 키
  arm_length_cm: number;              // 팔길이
  inseam_cm: number;                  // 인심
  accuracy: number;                   // 측정 정확도 (%, 상한 99)
  confidence: number;                 // 신뢰도 (0~1)
}

> API 저장 시 필드 매핑(예시):
> - `accuracy` → `measurement_accuracy`
> - `confidence` → `confidence_score`

function measureBody(
  landmarks: NormalizedLandmark[],
  worldLandmarks: WorldLandmark[],
  depthMap: Float32Array,
  depthWidth: number,
  depthHeight: number,
  cameraFocalLength: number,
  imageWidth: number,
  imageHeight: number
): BodyMeasurement {
  // 1. 카메라-사용자 절대 거리 추출 (m)
  const userDistance = extractUserDistance(depthMap, depthWidth, depthHeight, landmarks);

  // 2. 픽셀 거리 → 실세계 거리 변환 함수
  const pixelToRealCm = (pixelDist: number): number => {
    return (pixelDist * userDistance * 100) / cameraFocalLength;
  };

  // 3. 어깨너비 (키포인트 11-12 픽셀 거리)
  const shoulderPixelDist = Math.sqrt(
    ((landmarks[11].x - landmarks[12].x) * imageWidth) ** 2 +
    ((landmarks[11].y - landmarks[12].y) * imageHeight) ** 2
  );
  const shoulder_width_cm = pixelToRealCm(shoulderPixelDist);

  // 4. 가슴둘레 추정: 어깨너비 기반이 아닌 키포인트 11-12 간 거리(가슴 키포인트) 사용
  // chest_circumference ≈ chest_width * π (타원 근사)
  // ⚠️ 정면 영상만으로는 전후 깊이를 알 수 없으므로 추정치이며,
  //    성별/체형에 따라 오차가 크다. 사용자 입력 폴백을 우선한다.
  const chestPixelDist = Math.sqrt(
    ((landmarks[11].x - landmarks[12].x) * imageWidth) ** 2 +
    ((landmarks[11].y - landmarks[12].y) * imageHeight) ** 2
  );
  const chestWidth = pixelToRealCm(chestPixelDist);
  const chest_circumference_cm = chestWidth * Math.PI;

  // 5. 허리둘레 (힙 키포인트 23-24 기반, 해부학적 보정 적용)
  // 키포인트 23/24는 해부학적으로 hip joint이므로, 정확한 허리(waist) 위치보다 아래에 있다.
  // 허리둘레 추정: 키포인트 23-24 간 거리에 waist/hip 비율 보정을 적용한다.
  // waist_width ≈ hip_width * 0.85 (통계적 허리/힙 비율)
  // waist_circumference ≈ waist_width * π (타원 근사)
  const hipPixelDist = Math.sqrt(
    ((landmarks[23].x - landmarks[24].x) * imageWidth) ** 2 +
    ((landmarks[23].y - landmarks[24].y) * imageHeight) ** 2
  );
  const hipWidth = pixelToRealCm(hipPixelDist);
  const waistWidth = hipWidth * 0.85;
  const waist_circumference_cm = waistWidth * Math.PI;

  // 6. 힙둘레 (hip 키포인트 23-24 간 거리 × π 타원 근사)
  // hipWidth는 위의 허리둘레 계산에서 이미 산출됨
  const hip_circumference_cm = hipWidth * Math.PI;

  // 7. 키 (머리 꼭대기 ~ 발목 + 보정)
  const headToAnkle = Math.sqrt(
    ((landmarks[0].x - landmarks[27].x) * imageWidth) ** 2 +
    ((landmarks[0].y - landmarks[27].y) * imageHeight) ** 2
  );
  const height_cm = pixelToRealCm(headToAnkle) * 1.08;

  // 8. 팔길이 (어깨→팔꿈치→손목 누적)
  const upperArm = distance2D(landmarks[11], landmarks[13], imageWidth, imageHeight);
  const forearm = distance2D(landmarks[13], landmarks[15], imageWidth, imageHeight);
  const arm_length_cm = pixelToRealCm(upperArm + forearm);

  // 9. 인심 (힙→무릎→발목 누적)
  const upperLeg = distance2D(landmarks[23], landmarks[25], imageWidth, imageHeight);
  const lowerLeg = distance2D(landmarks[25], landmarks[27], imageWidth, imageHeight);
  const inseam_cm = pixelToRealCm(upperLeg + lowerLeg);

  // 10. 정확도/신뢰도 계산
  const accuracy = calculateAccuracy(landmarks, userDistance);

  // calculateConfidence: 측정 신뢰도 산출
  // 측정 신뢰도는 다음 요소의 가중 평균으로 산출:
  // - 포즈 감지 confidence (MediaPipe visibility 평균)
  // - 키포인트 가시성 (필수 키포인트의 visibility > 0.7 비율)
  // - 카메라 거리 적정성 (1.5~3m 범위 내)
  const confidence = calculateConfidence(landmarks);

  return {
    shoulder_width_cm, chest_circumference_cm, waist_circumference_cm,
    hip_circumference_cm, height_cm, arm_length_cm, inseam_cm,
    accuracy, confidence,
  };
}

function calculateAccuracy(
  landmarks: NormalizedLandmark[],
  distance: number
): number {
  // 거리가 1~2.5m일 때 최적, 양 끝에서 감소
  const distanceFactor = 1 - Math.abs(distance - 1.75) / 3.25;
  // 키포인트 visibility 평균
  const visibilityFactor = landmarks.reduce((sum, lm) => sum + lm.visibility, 0) / landmarks.length;
  // 상한 99%
  return Math.min(distanceFactor * visibilityFactor * 100, 99);
}

function calculateConfidence(landmarks: NormalizedLandmark[]): number {
  // 신체 측정에 필수적인 키포인트들의 visibility 기반 신뢰도
  // 코(0), 좌우 어깨(11,12), 좌우 힙(23,24), 좌우 무릎(25,26), 좌우 발목(27,28)
  const requiredIndices = [0, 11, 12, 23, 24, 25, 26, 27, 28];
  const visibilitySum = requiredIndices.reduce(
    (sum, idx) => sum + (landmarks[idx]?.visibility ?? 0), 0
  );
  return (visibilitySum / requiredIndices.length) * 100;
}
```

### 4.4 Fit Type Calculation (핏 타입 분류)

신체 측정 결과와 의류 실측 치수를 비교하여 핏 타입을 자동 분류한다.

```typescript
type FitType = 'slim' | 'regular' | 'oversize';

interface FitEvaluation {
  fitType: FitType;
  suitabilityPct: number;  // 종합 적합도 (%)
  accuracyPct: number;     // 측정 정확도 (%, 상한 99)
  details: {
    shoulder: { bodyCm: number; garmentCm: number; diffCm: number; fit: FitType };
    chest: { bodyCm: number; garmentCm: number; diffCm: number; fit: FitType };
    waist: { bodyCm: number; garmentCm: number; diffCm: number; fit: FitType };
    hip: { bodyCm: number; garmentCm: number; diffCm: number; fit: FitType };
  };
}

function evaluateFit(
  body: BodyMeasurement,
  garmentVariant: GarmentVariant
): FitEvaluation {
  // 항목별 여유량 (의류 치수 - 신체 치수)
  const diffs = {
    shoulder: (garmentVariant.shoulder_width_cm ?? 0) - body.shoulder_width_cm,
    chest: (garmentVariant.chest_cm ?? 0) - body.chest_circumference_cm,
    waist: (garmentVariant.waist_cm ?? 0) - body.waist_circumference_cm,
    hip: (garmentVariant.hip_cm ?? 0) - body.hip_circumference_cm,
  };

  // 항목별 핏 타입 분류
  const classifyFit = (diff: number): FitType => {
    if (diff < 3) return 'slim';
    if (diff <= 8) return 'regular';
    return 'oversize';
  };

  const details = {
    shoulder: { bodyCm: body.shoulder_width_cm, garmentCm: garmentVariant.shoulder_width_cm ?? 0, diffCm: diffs.shoulder, fit: classifyFit(diffs.shoulder) },
    chest: { bodyCm: body.chest_circumference_cm, garmentCm: garmentVariant.chest_cm ?? 0, diffCm: diffs.chest, fit: classifyFit(diffs.chest) },
    waist: { bodyCm: body.waist_circumference_cm, garmentCm: garmentVariant.waist_cm ?? 0, diffCm: diffs.waist, fit: classifyFit(diffs.waist) },
    hip: { bodyCm: body.hip_circumference_cm, garmentCm: garmentVariant.hip_cm ?? 0, diffCm: diffs.hip, fit: classifyFit(diffs.hip) },
  };

  // 종합 핏 타입 (다수결)
  const fitCounts = { slim: 0, regular: 0, oversize: 0 };
  Object.values(details).forEach(d => fitCounts[d.fit]++);
  const fitType: FitType = Object.entries(fitCounts)
    .sort((a, b) => b[1] - a[1])[0][0] as FitType;

  // 종합 적합도 (각 항목이 해당 핏 타입 적정 범위 내인지 평가)
  const suitabilityPct = calculateSuitability(details, fitType);

  return {
    fitType,
    suitabilityPct,
    accuracyPct: Math.min(body.accuracy, 99),
    details,
  };
}

function calculateSuitability(
  details: FitEvaluation['details'],
  targetFitType: FitType
): number {
  // 핏 타입별 적정 여유량 범위
  const ranges: Record<FitType, [number, number]> = {
    slim: [0, 3],
    regular: [3, 8],
    oversize: [8, 15],
  };

  const [min, max] = ranges[targetFitType];
  let totalScore = 0;
  let count = 0;

  for (const item of Object.values(details)) {
    if (item.garmentCm === 0) continue; // 치수 미입력 항목 제외
    const diff = item.diffCm;
    if (diff >= min && diff <= max) {
      totalScore += 100;
    } else {
      // 범위 벗어난 정도에 비례하여 감소
      const deviation = diff < min ? min - diff : diff - max;
      totalScore += Math.max(0, 100 - deviation * 10);
    }
    count++;
  }

  return count > 0 ? totalScore / count : 0;
}
```

---

## 5. 최적화 전략

### 5.1 트래킹 루프 최적화

```
┌──────────────────────────────────────────────────────────────────────┐
│                requestAnimationFrame 루프                             │
│                                                                      │
│  [프레임 캡처] ──┬──▶ [MediaPipe 추론] ──▶ [스무딩] ──┐              │
│                  │                                     │              │
│                  └──▶ [Depth 추론(1~5Hz)] ──────────────┤              │
│                                                        ▼              │
│                              [신체 측정] ──▶ [핏 평가] ──▶ [본 업데이트] │
│       ↑                                                               │
│       │                                                               │
│       └─────── 포즈 30~60Hz + Depth 1~5Hz (저주기 결합) ─────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

**프레임 버짓 분배**:

| 단계 | 타겟 시간 | 비고 |
|------|----------|------|
| 카메라 프레임 캡처 | < 1ms | drawImage로 canvas에 복사 |
| MediaPipe 추론 | < 12ms | GPU delegate 사용 시 |
| Depth Anything V2 추론(저주기) | 15~50ms | 1~5Hz로 실행, rAF 프레임과 분리(WebGPU/WebGL) |
| 스무딩 필터 | < 0.5ms | 1-Euro Filter (EMA 수준 비용, 적응형 컷오프) |
| 신체 측정 계산 | < 1ms | depth + 키포인트 연산 |
| 핏 평가 계산 | < 0.5ms | 치수 비교 + 핏 분류 |
| Kalidokit 매핑 | < 0.5ms | 벡터/쿼터니언 연산 |
| 본 업데이트 + 렌더 | < 3ms | Three.js 씬 그래프 갱신 + 핏 오버레이 |
| **총계(포즈 루프 기준)** | **< 20ms** | **목표: 50~60fps. Depth는 별도 저주기 작업으로 결합** |

### 5.2 1-Euro Filter 적응형 스무딩

키포인트 좌표의 프레임간 떨림(지터)을 제거하기 위해 1-Euro Filter를 적용한다.

> **EMA 대비 장점**: 고정 alpha EMA는 정지 시 떨림과 빠른 동작 시 지연 사이에서
> 타협할 수밖에 없다. 1-Euro Filter는 입력 신호의 속도(dx/dt)에 따라 컷오프 주파수를
> 적응적으로 조절하여, **저속 → 강한 스무딩(지터 제거)**, **고속 → 약한 스무딩(지연 최소화)**
> 를 동시에 달성한다.
>
> - **논문**: Casiez, Roussel, Vogel. "1€ Filter: A Simple Speed-based Low-pass Filter
>   for Noisy Input in Interactive Systems" (CHI 2012)
> - **구현 참고**: `@webarkit/oneeurofilter-ts` (TypeScript, MIT)

```typescript
class OneEuroFilter {
  private minCutoff: number;
  private beta: number;
  private dCutoff: number;
  private xFilter: LowPassFilter;
  private dxFilter: LowPassFilter;
  private lastTime: number | null = null;

  constructor(minCutoff: number = 1.0, beta: number = 0.5, dCutoff: number = 1.0) {
    // minCutoff: 최소 컷오프 주파수 (정지 시 스무딩 강도, 낮을수록 부드러움)
    // beta: 속도 계수 (높을수록 빠른 동작에 민감하게 반응)
    // dCutoff: 도함수 컷오프 주파수 (속도 추정 스무딩)
    // 권장 시작값: minCutoff=1.0, beta=0.5, dCutoff=1.0
    // → 정지 시 지터 < 1px, 빠른 제스처 시 지연 < 2프레임 (30fps 기준)
    this.minCutoff = minCutoff;
    this.beta = beta;
    this.dCutoff = dCutoff;
    this.xFilter = new LowPassFilter();
    this.dxFilter = new LowPassFilter();
  }

  filter(value: number, timestamp: number): number {
    const dt = this.lastTime !== null ? timestamp - this.lastTime : 1 / 60;
    this.lastTime = timestamp;

    // 속도(도함수) 추정
    const dx = this.xFilter.hasLastValue()
      ? (value - this.xFilter.lastValue()) / dt
      : 0;
    const smoothedDx = this.dxFilter.filter(dx, this.alpha(this.dCutoff, dt));

    // 속도에 따른 적응형 컷오프 주파수
    const cutoff = this.minCutoff + this.beta * Math.abs(smoothedDx);

    return this.xFilter.filter(value, this.alpha(cutoff, dt));
  }

  private alpha(cutoff: number, dt: number): number {
    const tau = 1.0 / (2 * Math.PI * cutoff);
    return 1.0 / (1.0 + tau / dt);
  }
}

class LowPassFilter {
  private y: number | null = null;
  private s: number | null = null;

  filter(value: number, alpha: number): number {
    if (this.s === null) {
      this.s = value;
    } else {
      this.s = alpha * value + (1 - alpha) * this.s;
    }
    this.y = value;
    return this.s;
  }

  hasLastValue(): boolean { return this.y !== null; }
  lastValue(): number { return this.y!; }
}

// 33개 키포인트 × 3축(x, y, z) = 99개 필터 인스턴스
class PoseSmoother {
  private filters: OneEuroFilter[][];

  constructor(minCutoff = 1.0, beta = 0.5, dCutoff = 1.0) {
    this.filters = Array.from({ length: 33 }, () =>
      [new OneEuroFilter(minCutoff, beta, dCutoff),  // x
       new OneEuroFilter(minCutoff, beta, dCutoff),  // y
       new OneEuroFilter(minCutoff, beta, dCutoff)]  // z
    );
  }

  apply(current: NormalizedLandmark[], timestamp: number): NormalizedLandmark[] {
    return current.map((landmark, i) => {
      // visibility가 낮은 키포인트는 필터 건너뜀 (이전 출력 유지)
      if (landmark.visibility < 0.5) return landmark;

      return {
        x: this.filters[i][0].filter(landmark.x, timestamp),
        y: this.filters[i][1].filter(landmark.y, timestamp),
        z: this.filters[i][2].filter(landmark.z, timestamp),
        visibility: landmark.visibility,
        presence: landmark.presence,
      };
    });
  }
}
```

### 5.3 오클루전 처리

키포인트가 가려졌을 때(visibility 낮음) 처리 전략:

```typescript
function handleOcclusion(
  current: NormalizedLandmark,
  previous: NormalizedLandmark,
  threshold: number = 0.5
): NormalizedLandmark {
  if (current.visibility >= threshold) {
    // 정상: 현재 값 사용
    return current;
  }

  if (current.visibility >= 0.3) {
    // 부분 오클루전: 이전 값과 블렌딩
    const blend = current.visibility / threshold;
    return {
      x: blend * current.x + (1 - blend) * previous.x,
      y: blend * current.y + (1 - blend) * previous.y,
      z: blend * current.z + (1 - blend) * previous.z,
      visibility: current.visibility,
      presence: current.presence,
    };
  }

  // 완전 오클루전: 이전 값 유지
  return { ...previous, visibility: current.visibility, presence: current.presence };
}
```

### 5.4 모바일 폴백

```typescript
class AdaptiveTracker {
  private currentModel: 'heavy' | 'full' | 'lite' = 'heavy';
  private fpsHistory: number[] = [];
  private readonly DOWNGRADE_THRESHOLD = 25;  // fps
  private readonly DOWNGRADE_DURATION = 3000; // ms (3초)

  checkPerformance(fps: number): void {
    this.fpsHistory.push(fps);

    // 최근 3초간 평균 FPS 계산
    const recentFps = this.fpsHistory.slice(-Math.ceil(this.DOWNGRADE_DURATION / 16.67));
    const avgFps = recentFps.reduce((a, b) => a + b, 0) / recentFps.length;

    if (avgFps < this.DOWNGRADE_THRESHOLD) {
      this.downgradeModel();
    }
  }

  private downgradeModel(): void {
    if (this.currentModel === 'heavy') {
      this.currentModel = 'full';
      this.reinitialize('full');
    } else if (this.currentModel === 'full') {
      this.currentModel = 'lite';
      this.reinitialize('lite');
    }
    // lite에서는 더 이상 다운그레이드 불가
  }

  private reinitialize(model: string): void {
    // MediaPipe 모델 재로드
    // 사용자에게 "품질 최적화 중..." 알림 표시
  }
}
```

---

## 6. 좌표계 변환

### 6.1 좌표계 정의

```
MediaPipe NDC 좌표계:          Three.js 월드 좌표계:
                                       +Y (위)
  (0,0)────────(1,0)                    │
    │              │                    │
    │   이미지     │            ────────┼────────▶ +X (오른쪽)
    │              │                   ╱│
  (0,1)────────(1,1)                  ╱ │
                                    +Z  │
  x: 0→1 (왼→오)                (카메라 쪽)
  y: 0→1 (위→아래)
  z: 깊이 (카메라 기준)
```

### 6.2 NDC → Three.js 변환

```typescript
function ndcToThreeJS(
  landmark: NormalizedLandmark,
  canvasWidth: number,
  canvasHeight: number
): THREE.Vector3 {
  // MediaPipe NDC → Three.js 좌표 변환
  // x: [0, 1] → [-aspect/2, aspect/2] (좌우 반전 = 미러링)
  // y: [0, 1] → [0.5, -0.5] (상하 반전)
  // z: 상대 깊이 → Three.js z좌표

  const aspect = canvasWidth / canvasHeight;

  return new THREE.Vector3(
    -(landmark.x - 0.5) * aspect,  // 미러링: x 반전
    -(landmark.y - 0.5),           // y축 반전
    -landmark.z * 0.5              // 깊이 스케일 조정
  );
}
```

### 6.3 월드 좌표 활용

```typescript
function worldToThreeJS(worldLandmark: WorldLandmark): THREE.Vector3 {
  // MediaPipe 월드 좌표는 힙 중심 원점, 미터 단위
  // Three.js 좌표계와 축 방향 매핑:
  //   MediaPipe x (왼→오) → Three.js x (반전, 미러링)
  //   MediaPipe y (위→아래) → Three.js y (반전)
  //   MediaPipe z (카메라→사용자) → Three.js z (반전)

  return new THREE.Vector3(
    -worldLandmark.x,   // 미러링
    -worldLandmark.y,   // y축 반전
    -worldLandmark.z    // z축 반전
  );
}
```

### 6.4 카메라 미러링 처리

가상 시착은 "거울" 경험이므로, 좌우 반전(미러링)을 적용한다.

```typescript
// 방법 1: 카메라 피드 CSS 미러링
videoElement.style.transform = 'scaleX(-1)';

// 방법 2: Three.js 씬 x축 반전
scene.scale.x = -1;

// 방법 3: 좌표 변환 시 x 부호 반전 (위 함수에서 이미 적용)

// 주의: 미러링은 한 곳에서만 적용해야 한다.
// 권장: 좌표 변환 단계에서 x 반전 (방법 3)
```

### 6.5 깊이(z) 보정

MediaPipe의 z 좌표는 절대 깊이가 아닌 상대 깊이이므로 보정이 필요하다.

```typescript
class DepthCalibrator {
  private referenceHipDepth: number = 0;
  private calibrated: boolean = false;

  // 초기 캘리브레이션: 사용자가 정면을 바라볼 때 힙 깊이를 기준으로 설정
  calibrate(worldLandmarks: WorldLandmark[]): void {
    const leftHip = worldLandmarks[23];
    const rightHip = worldLandmarks[24];
    this.referenceHipDepth = (leftHip.z + rightHip.z) / 2;
    this.calibrated = true;
  }

  // 프레임별 깊이 보정
  correctDepth(worldLandmarks: WorldLandmark[]): WorldLandmark[] {
    if (!this.calibrated) return worldLandmarks;

    const currentHipDepth = (worldLandmarks[23].z + worldLandmarks[24].z) / 2;
    const depthOffset = currentHipDepth - this.referenceHipDepth;

    return worldLandmarks.map(lm => ({
      ...lm,
      z: lm.z - depthOffset,  // 힙 기준 상대 깊이로 정규화
    }));
  }
}
```

---

## 7. Three.js 본 리깅 통합 (VRM)

### 7.1 VRM 본 구조 (VRMHumanoid)

VRM 포맷은 VRMHumanoid 인터페이스를 통해 표준화된 본 구조를 제공한다.
Kalidokit의 출력 본 이름과 VRM의 humanoid bone 이름이 직접 매핑된다.

```
hips (루트)
├── spine
│   ├── chest
│   │   └── upperChest
│   │       ├── neck
│   │       │   └── head
│   │       ├── leftShoulder
│   │       │   └── leftUpperArm
│   │       │       └── leftLowerArm
│   │       │           └── leftHand
│   │       └── rightShoulder
│   │           └── rightUpperArm
│   │               └── rightLowerArm
│   │                   └── rightHand
├── leftUpperLeg
│   └── leftLowerLeg
│       └── leftFoot
│           └── leftToes
└── rightUpperLeg
    └── rightLowerLeg
        └── rightFoot
            └── rightToes
```

### 7.2 VRM 모델 로드 및 본 업데이트

```typescript
import { VRMLoaderPlugin, VRMHumanBoneName } from '@pixiv/three-vrm';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader';

// VRM 모델 로드
const loader = new GLTFLoader();
loader.register((parser) => new VRMLoaderPlugin(parser));

// VRM 아바타 경로: assets/optimized/body-presets/body_{gender}_{size}.vrm
// 예시: assets/optimized/body-presets/body_male_M.vrm
const gltf = await loader.loadAsync('assets/optimized/body-presets/body_male_M.vrm');
const vrm = gltf.userData.vrm;

// VRMHumanoid API를 통한 본 업데이트
function updateVRMBones(
  vrm: VRM,
  poseRig: PoseRigResult
): void {
  const humanoid = vrm.humanoid;

  // Kalidokit 본 이름 → VRM 본 이름 매핑
  const boneMap: Record<string, VRMHumanBoneName> = {
    Hips: VRMHumanBoneName.Hips,
    Spine: VRMHumanBoneName.Spine,
    Chest: VRMHumanBoneName.Chest,
    Neck: VRMHumanBoneName.Neck,
    Head: VRMHumanBoneName.Head,
    LeftUpperArm: VRMHumanBoneName.LeftUpperArm,
    LeftLowerArm: VRMHumanBoneName.LeftLowerArm,
    LeftHand: VRMHumanBoneName.LeftHand,
    RightUpperArm: VRMHumanBoneName.RightUpperArm,
    RightLowerArm: VRMHumanBoneName.RightLowerArm,
    RightHand: VRMHumanBoneName.RightHand,
    LeftUpperLeg: VRMHumanBoneName.LeftUpperLeg,
    LeftLowerLeg: VRMHumanBoneName.LeftLowerLeg,
    LeftFoot: VRMHumanBoneName.LeftFoot,
    RightUpperLeg: VRMHumanBoneName.RightUpperLeg,
    RightLowerLeg: VRMHumanBoneName.RightLowerLeg,
    RightFoot: VRMHumanBoneName.RightFoot,
  };

  for (const [kalidoName, vrmBoneName] of Object.entries(boneMap)) {
    const rigData = poseRig[kalidoName as keyof PoseRigResult];
    if (!rigData) continue;

    const boneNode = humanoid.getNormalizedBoneNode(vrmBoneName);
    if (!boneNode) continue;

    // 회전 적용
    if ('rotation' in rigData) {
      const { x, y, z } = rigData.rotation;
      boneNode.rotation.set(x, y, z);
    }

    // 위치 적용 (Hips 루트 본만)
    if ('position' in rigData && vrmBoneName === VRMHumanBoneName.Hips) {
      const { x, y, z } = rigData.position;
      boneNode.position.set(x, y, z);
    }
  }

  // VRM 내부 상태 갱신 (SpringBone 등)
  vrm.update(deltaTime);
}
```

### 7.3 기존 방식 (일반 SkinnedMesh)

VRM을 사용하지 않는 일반 glTF 모델의 경우 기존 Three.js Skeleton API를 사용한다.

```typescript
function updateSkeletonBones(
  skeleton: THREE.Skeleton,
  poseRig: PoseRigResult
): void {
  const bones = skeleton.bones;

  for (const bone of bones) {
    const rigData = poseRig[bone.name as keyof PoseRigResult];
    if (!rigData) continue;

    // 회전 적용
    if ('rotation' in rigData) {
      const { x, y, z } = rigData.rotation;
      bone.rotation.set(x, y, z);
    }

    // 위치 적용 (Hips 루트 본만)
    if ('position' in rigData && bone.name === 'Hips') {
      const { x, y, z } = rigData.position;
      bone.position.set(x, y, z);
    }
  }
}
```

---

## 8. 에러 처리 및 복구

| 상황 | 감지 방법 | 복구 전략 |
|------|----------|----------|
| 카메라 권한 거부 | getUserMedia 에러 | 마네킹 뷰 폴백 + 권한 안내 |
| MediaPipe 모델 로드 실패 | createFromOptions 에러 | CDN 재시도 (최대 3회) → 에러 메시지 |
| 포즈 감지 실패 (사람 없음) | landmarks.length === 0 | 마지막 유효 포즈 유지, 3초 후 초기 포즈 |
| FPS 급락 (< 15fps) | 프레임 시간 측정 | 모델 다운그레이드 → 해상도 축소 |
| WebGL 컨텍스트 손실 | webglcontextlost 이벤트 | 씬 재초기화 |

---

## 부록 A: 성능 벤치마크 타겟

| 디바이스 분류 | 예시 | 트래킹 모델 | 타겟 FPS |
|-------------|------|-----------|---------|
| 데스크톱 고사양 | RTX 3060+ | Heavy | 60fps |
| 데스크톱 저사양 | Intel UHD | Full | 45fps |
| 모바일 고사양 | Galaxy S24, iPhone 15 | Full | 45fps |
| 모바일 중사양 | Galaxy A54, iPhone 13 | Lite | 30fps |
| 모바일 저사양 | 3년+ 구형 | Lite + 해상도 축소 | 25fps |

### Depth 모델 성능 벤치마크

| 디바이스 분류 | 예시 | Depth 백엔드 | 추론 시간 | 결합 FPS |
|-------------|------|-------------|----------|---------|
| 데스크톱 고사양 | RTX 3060+ | WebGPU | ~12ms | 50fps |
| 데스크톱 저사양 | Intel UHD | WebGL | ~30ms | 35fps |
| 모바일 고사양 | Galaxy S24, iPhone 15 | WebGL | ~35ms | 30fps |
| 모바일 중사양 | Galaxy A54, iPhone 13 | WebGL | ~50ms | 25fps |
| 모바일 저사양 | 3년+ 구형 | 비활성화 | N/A | 30fps (Depth 미사용) |

---

## 부록 B: 참고 프로젝트

| 프로젝트 | 설명 | 관련 기술 |
|---------|------|----------|
| **Wawa Sensei VTuber Tutorial** | MediaPipe + Kalidokit + three-vrm 풀스택 튜토리얼 | VRM 아바타 바디 트래킹의 가장 가까운 레퍼런스 |
| Kalidokit 공식 데모 | MediaPipe → VRM 본 매핑 데모 | 포즈 매핑 검증 |
| @pixiv/three-vrm 예제 | VRM 모델 로드 + 본 조작 예제 | three-vrm API 사용법 |

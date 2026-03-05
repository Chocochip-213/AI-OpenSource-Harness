# WebAR v2 아키텍처 설계 문서

> AutoFit v2 — 브라우저 기반 가상 피팅 시스템 아키텍처

## 1. 개요

AutoFit v2는 기존 PySide6 네이티브 파이프라인을 **WebAR 기반 브라우저 가상 피팅 시스템**으로 전환한다. 사용자는 별도 앱 설치 없이 모바일/데스크톱 브라우저에서 의류를 가상 착용할 수 있다.

### 핵심 목표
- **접근성**: 별도 설치 없이 브라우저에서 즉시 피팅
- **성능**: 모바일 기기에서 30fps 이상 실시간 렌더링
- **에셋 경량화**: Draco + KTX2 압축으로 2MB 이내 에셋

### 기술 스택 변경 요약

| 영역 | v1 (네이티브) | v2 (WebAR) |
|------|---------------|------------|
| 렌더링 | OpenGL + CUDA interop | Three.js (WebGL 2.0) |
| UI | PySide6 + QML | React 18 + TypeScript |
| 포즈 추정 | RTMPose (TensorRT) | MediaPipe Pose (WASM) |
| 물리/의류 변형 | NVIDIA Warp (GPU XPBD) | SkinnedMesh 본 바인딩(P0) + Normal Map(P1) / VAT(P2, 선택) |
| 에셋 포맷 | OBJ/FBX | glTF 2.0 / GLB (Draco + KTX2) |
| 배포 | systemd (호스트 직접) | Nginx 정적 서빙 + CDN |

---

## 2. 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                        클라이언트 (브라우저)                       │
│                                                                 │
│  ┌──────────┐  ┌──────────────────┐  ┌──────────────┐         │
│  │ MediaPipe │  │ Depth Anything V2 │  │  React UI    │         │
│  │ Pose      │  │ Metric Depth(ONNX)│  │  컴포넌트     │         │
│  │ (WASM)    │  └──────┬───────────┘  └──────┬───────┘         │
│  └─────┬────┘         │                   │                   │
│        │               │                │                      │
│        └───── AR 세션 ──┤                │                      │
│               │         │                │                      │
│               ▼         ▼                │                      │
│  ┌──────────────────────────┐            │                      │
│  │  Body Measurer           │            │                      │
│  │  (신체 치수 계산)         │            │                      │
│  └────────────┬─────────────┘            │                      │
│               ▼                          │                      │
│  ┌──────────────────────────┐            │                      │
│  │  Fit Evaluation Engine   │            │                      │
│  │  (핏 타입/적합도/정확도)  │            │                      │
│  └──────────────────────────┘            │                      │
│               │                          │                      │
│  ┌────────────┴──────────────────────────┘                      │
│  │  Three.js 렌더러 (WebGL 2.0) + 핏 평가 오버레이              │
│  └──────────────────────────────────────────────┘              │
│                                                                 │
│  ┌──────────────────────────────────────────────┐              │
│  │  SDK Layer (@autofit/*)                       │              │
│  │  코어 / 바디트래커 / 핏평가 / 렌더러 / UI     │              │
│  └──────────────────────────────────────────────┘              │
│               │                         │                      │
│         카메라 피드                  사용자 인터랙션             │
└─────────────────┬─────────────────────────┬─────────────────────┘
                  │                         │
                  │      HTTPS / REST       │
                  ▼                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                        서버 (Docker Compose)                     │
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │  Nginx   │  │ FastAPI  │  │PostgreSQL│  │  Redis   │       │
│  │ (정적/   │→│ (REST    │→│  (16)    │  │  (7)     │       │
│  │  리버스  │  │  API)    │  │          │  │  (캐시)  │       │
│  │  프록시) │  │          │  │          │  │          │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
│                                                                 │
│  ┌──────────┐  정적 에셋 서빙                                    │
│  │ CDN /    │  (GLB, 텍스처, 썸네일, ONNX 모델)                  │
│  │ Storage  │                                                   │
│  └──────────┘                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. 프론트엔드 아키텍처

### 3-1. 기술 스택

| 라이브러리 | 버전 | 용도 |
|-----------|------|------|
| React | 18.x | UI 프레임워크 |
| TypeScript | 5.x | 타입 안전성 |
| Vite | 5.x | 빌드 도구 |
| Three.js | r160+ | 3D 렌더링 (WebGL 2.0) |
| @react-three/fiber | 8.x | React Three.js 바인딩 |
| @react-three/drei | 9.x | Three.js 유틸리티 |
| MediaPipe Pose Landmarker | @mediapipe/tasks-vision | 실시간 포즈 추정 (WASM) |
| Zustand | 4.x | 상태 관리 |
| TanStack Query | 5.x | 서버 상태 관리 |
| Tailwind CSS | 3.x | 스타일링 |

### 3-2. 디렉토리 구조

```
frontend/
├── src/
│   ├── App.tsx
│   ├── main.tsx
│   ├── ar/                     # AR 코어 모듈
│   │   ├── BodyTracker.ts
│   │   ├── PoseMapper.ts
│   │   ├── BodyMeshManager.ts
│   │   ├── ClothSimulator.ts
│   │   └── GarmentLoader.ts
│   ├── scene/                  # Three.js 씬
│   │   ├── TryOnScene.tsx
│   │   ├── CameraFeed.tsx
│   │   ├── LightingSetup.tsx
│   │   └── MaterialVariant.tsx
│   ├── components/
│   │   ├── GarmentSelector.tsx
│   │   ├── SizeSelector.tsx
│   │   ├── ColorPicker.tsx
│   │   ├── ShopNowButton.tsx
│   │   └── LoadingOverlay.tsx
│   ├── hooks/
│   │   ├── useBodyTracking.ts
│   │   ├── useGarment.ts
│   │   └── useClothSim.ts
│   ├── stores/
│   │   ├── tryOnStore.ts
│   │   └── catalogStore.ts
│   ├── api/
│   └── lib/
├── public/
│   └── models/                 # 정적 3D 모델 (개발용)
├── package.json
├── vite.config.ts
├── tsconfig.json
└── tailwind.config.ts
```

### 3-3. AR 렌더링 파이프라인

```
카메라 프레임
    │
    ├──────────────────────┐
    ▼                      ▼
MediaPipe Pose (WASM)   Depth Anything V2 (ONNX)
    │                      │
    ├── 33개 랜드마크 좌표   ├── depth map (미터 단위)
    │                      │
    └──────────┬───────────┘
               │
               ▼
    Body Measurer (신체 치수 계산)
               │
               ├── 7개 신체 치수 (cm)
               │
               ▼
    Fit Evaluation Engine
               │
               ├── 핏 타입 / 적합도% / 정확도%
               │
               ▼
    포즈 변환 (랜드마크 → 바디 본 회전)
               │
               ▼
    Three.js 씬 업데이트
               │
               ├── 바디 메쉬: 본 회전 적용
               ├── 의류 메쉬: 스키닝 + 핏 타입별 메쉬 선택
               ├── 카메라 피드: 배경 텍스처
               └── 핏 평가 오버레이: 사이드바 UI
               │
               ▼
    WebGL 2.0 렌더링 (30fps+)
               │
               ▼
    Canvas 출력
```

### 3-4. 포즈 추정 (MediaPipe Pose)

MediaPipe Pose는 브라우저에서 WASM으로 실행되며, 33개 신체 랜드마크를 실시간 추정한다.

**주요 랜드마크 매핑:**

| MediaPipe 인덱스 | 관절명 | Three.js 본 |
|-----------------|--------|-------------|
| 11, 12 | 어깨 좌/우 | shoulder_L, shoulder_R |
| 13, 14 | 팔꿈치 좌/우 | elbow_L, elbow_R |
| 23, 24 | 엉덩이 좌/우 | hip_L, hip_R |
| 25, 26 | 무릎 좌/우 | knee_L, knee_R |

**성능 최적화:**

- Pose Landmarker는 `@mediapipe/tasks-vision` 기반으로 로드한다.
- 입력 해상도는 기기 성능에 따라 640x480 등으로 다운스케일한다.
- 떨림은 모델 옵션이 아니라 **1-Euro Filter 적응형 스무딩** 으로 제어한다 (속도 기반 적응형 컷오프, CHI 2012).

---

## 4. 백엔드 아키텍처

### 4-1. 기술 스택

| 라이브러리 | 버전 | 용도 |
|-----------|------|------|
| FastAPI | 0.109+ | REST API 프레임워크 |
| SQLAlchemy | 2.0 | ORM (비동기) |
| Alembic | 1.13+ | DB 마이그레이션 |
| PostgreSQL | 16 | 메인 데이터베이스 |
| Redis | 7 | 캐시 + 세션 |
| PyJWT | 2.8+ | JWT 인증 (python-jose에서 전환) |
| passlib | 1.7+ | 비밀번호 해싱 |

### 4-2. 레이어 구조

```
API 라우터 (app/api/v1/)
    │
    ▼
서비스 레이어 (app/services/)
    │
    ▼
ORM 모델 (app/models/)
    │
    ▼
PostgreSQL 16
```

### 4-3. 디렉토리 구조

```
backend/
├── app/
│   ├── main.py                 # FastAPI 앱 팩토리
│   ├── config.py               # pydantic-settings 설정
│   ├── database.py             # SQLAlchemy async engine/session
│   ├── models/
│   │   ├── user.py             # User ORM
│   │   ├── brand.py            # Brand ORM
│   │   ├── garment.py          # Garment ORM
│   │   ├── garment_image.py    # GarmentImage ORM
│   │   ├── garment_variant.py  # GarmentVariant ORM
│   │   ├── body_preset.py      # BodyPreset ORM
│   │   ├── body_measurement.py # BodyMeasurement ORM
│   │   ├── fitting_session.py  # FittingSession ORM
│   │   ├── fit_evaluation.py   # FitEvaluation ORM
│   │   └── sdk_config.py       # SDKConfig ORM
│   ├── schemas/
│   │   ├── auth.py             # 인증 요청/응답
│   │   ├── garment.py          # 의류 요청/응답
│   │   ├── body_preset.py      # 바디 프리셋 응답
│   │   └── fitting_session.py  # 피팅 세션 요청/응답
│   ├── api/v1/
│   │   ├── auth.py             # 인증 라우터
│   │   ├── garments.py         # 의류 라우터
│   │   ├── body_presets.py     # 바디 프리셋 라우터
│   │   ├── fitting_sessions.py # 피팅 세션 라우터
│   │   ├── assets.py           # 에셋 업로드 라우터
│   │   └── stats.py            # 통계 라우터
│   ├── services/
│   │   ├── auth_service.py     # 인증 비즈니스 로직
│   │   ├── garment_service.py  # 의류 CRUD
│   │   └── stats_service.py    # 통계 집계
│   └── core/
│       ├── security.py         # JWT + 비밀번호
│       ├── deps.py             # 의존성 주입
│       └── exceptions.py       # 커스텀 예외
├── alembic/                    # 마이그레이션
├── tests/
│   ├── features/               # BDD .feature 파일
│   ├── unit/
│   └── integration/
└── pyproject.toml
```

---

## 5. 인프라 아키텍처

### 5-1. Docker Compose 구성

```yaml
# docker-compose.yml 서비스 구성
services:
  nginx:        # 리버스 프록시 + 정적 서빙 (80, 443)
  api:          # FastAPI (8000)
  postgres:     # PostgreSQL 16 (5432)
  redis:        # Redis 7 (6379)
  prometheus:   # 메트릭 수집 (9090)
  grafana:      # 대시보드 (3000)
```

### 5-2. Nginx 라우팅

```
/                → 프론트엔드 SPA (정적 파일)
/api/v1/*        → FastAPI 백엔드 (리버스 프록시)
/assets/*        → 에셋 정적 서빙 (GLB, 이미지)
/admin/*         → 관리 대시보드 SPA
```

### 5-3. 환경별 배포

| 환경 | 프론트엔드 | 백엔드 | DB |
|------|-----------|--------|-----|
| 개발 | Vite dev server (5173) | uvicorn --reload (8000) | Docker PostgreSQL |
| 스테이징 | Nginx 정적 서빙 | Docker FastAPI | Docker PostgreSQL |
| 프로덕션 | Nginx + CDN | Docker FastAPI (gunicorn) | Docker PostgreSQL (볼륨 마운트) |

---

## 6. 데이터 플로우

### 6-1. 의류 카탈로그 조회

```
사용자 → React UI → API 요청 (GET /api/v1/garments)
                        → FastAPI → SQLAlchemy → PostgreSQL
                        ← JSON 응답 (의류 목록 + 썸네일 URL)
React UI ← 의류 목록 렌더링
```

### 6-2. AR 피팅 세션

```
1. 사용자가 의류 선택 → POST /api/v1/fitting-sessions (세션 생성)
2. GLB 모델 다운로드 ← CDN/Nginx (Draco + KTX2 압축)
3. 카메라 스트림 시작 → MediaPipe Pose (WASM)
4. 포즈 랜드마크 → Three.js 본 매핑
5. 의류 메쉬 스키닝 + 렌더링 (30fps)
6. 세션 종료 → PUT /api/v1/fitting-sessions/{id} (소요 시간 기록)
```

### 6-3. 에셋 업로드 (관리자)

```
관리자 → 관리 대시보드 → POST /api/v1/assets/upload (멀티파트)
                           → FastAPI → 파일 저장 → 정적 에셋 디렉토리
                           ← asset_url 반환
관리자 → POST /api/v1/garments (model_url = asset_url)
```

### 6-4. 에셋 생성 상태 알림

3D 에셋 비동기 생성의 진행 상태를 관리 대시보드에 전달하기 위해:
- **MVP**: REST 폴링 (GET /api/v1/garments/{id} → asset_status 필드, 10초 간격)
- **확장**: Server-Sent Events (SSE) `/api/v1/events/asset-status` 엔드포인트로 실시간 알림

### 6-5. 신체 측정 + 핏 평가

```
1. 카메라 프레임 → MediaPipe Pose + Depth Anything V2 (병렬 추론)
2. 키포인트 33개 + depth map → Body Measurer
   │  카메라-사용자 절대 거리(m) 추출
   │  핀홀 카메라 모델 역투영으로 키포인트 간 실제 거리(cm) 계산
   │  7개 신체 치수 산출 (어깨/가슴/허리/힙/키/팔길이/인심)
3. 신체 치수 + 의류 실측 치수 → Fit Evaluation Engine
   │  항목별 여유량 계산 → 핏 타입 분류 (slim/regular/oversize)
   │  적합도(%) + 정확도(%) 산출
4. 평가 결과 → evaluationStore (Zustand) → UI 오버레이 갱신
5. 주기적 저장 → POST /api/v1/body-measurements + POST /api/v1/fit-evaluations
```

---

## 7. 성능 최적화 전략

### 7-1. 에셋 로딩

| 전략 | 설명 |
|------|------|
| Draco 압축 | 메쉬 크기 80~90% 감소 |
| KTX2 텍스처 | GPU 네이티브 디코딩, 메모리 절약 |
| 지연 로딩 | 카탈로그는 썸네일만, 피팅 시 GLB 로드 |
| 캐시 | Service Worker + Cache API로 반복 로드 방지 |
| CDN | 정적 에셋 CDN 서빙 (지연 시간 감소) |

### 7-2. 렌더링

| 전략 | 설명 |
|------|------|
| LOD | 거리 기반 폴리곤 단계 조절 |
| VAT | 물리 시뮬 사전 베이킹 (런타임 연산 제거) |
| 인스턴싱 | 동일 재질 메쉬 배칭 |
| 해상도 조절 | 기기 성능에 따라 렌더 해상도 동적 조절 |

### 7-3. 네트워크

| 전략 | 설명 |
|------|------|
| 프리페치 | 다음 카탈로그 페이지 미리 로드 |
| Brotli 압축 | Nginx에서 정적 파일 Brotli 압축 |
| HTTP/2 | 멀티플렉싱으로 병렬 에셋 로드 |
| 이미지 최적화 | 썸네일 WebP 변환, 반응형 크기 |

---

## 8. 보안

| 영역 | 방안 |
|------|------|
| 인증 | JWT (HS256, 15분 만료) + Refresh Token(7일, HttpOnly 쿠키 권장) |
| 비밀번호 | bcrypt 해싱 (cost factor 12) |
| CORS | 허용 오리진 화이트리스트 |
| Rate Limiting | API 요청 제한 (100req/min per IP) |
| 파일 업로드 | 확장자/MIME 검증, 최대 50MB |
| HTTPS | TLS 1.3 (Let's Encrypt) |
| XSS | Content-Security-Policy 헤더 |
| SQL Injection | SQLAlchemy 파라미터 바인딩 |

### 개발 환경 HTTPS 설정

카메라 접근(`getUserMedia`)은 HTTPS가 필수이다. 로컬 개발 시:

1. **mkcert로 로컬 SSL 인증서 생성**:
   ```bash
   mkcert -install
   mkcert localhost 127.0.0.1
   ```

2. **Vite 설정** (`vite.config.ts`):
   ```typescript
   import fs from 'fs';
   export default defineConfig({
     server: {
       https: {
         key: fs.readFileSync('./localhost-key.pem'),
         cert: fs.readFileSync('./localhost.pem'),
       },
     },
   });
   ```

### 에러 핸들링 전략

**API 에러 응답 형식**:
```json
{
  "error": {
    "code": "GARMENT_NOT_FOUND",
    "message": "요청한 의류를 찾을 수 없습니다.",
    "details": {}
  }
}
```

**프론트엔드 에러 바운더리**: React ErrorBoundary로 3D 씬 크래시 격리
**네트워크 장애**: TanStack Query의 retry + offline 감지로 자동 재시도
**카메라 권한 거부**: 폴백 UI (정적 이미지 기반 시착 미리보기)

---

## 9. SDK Architecture

> **스코프 조정**: SDK 모듈화는 MVP 이후 후속 작업으로 분류한다.
> MVP에서는 `frontend/` 일체형 앱으로 구현한다.

### 9-1. 모듈 구조

```
@autofit/
├── core/              # 초기화, 설정, 라이프사이클
│   ├── AutoFitSDK.ts      # 메인 SDK 클래스
│   ├── config.ts          # SDK 설정 타입
│   └── events.ts          # 이벤트 시스템
├── body-tracker/      # MediaPipe + Depth Anything V2 통합
│   ├── BodyTracker.ts     # 통합 트래킹 매니저
│   ├── DepthSensor.ts     # Depth 모델 래퍼
│   └── PoseEstimator.ts   # MediaPipe 래퍼
├── fit-evaluator/     # 신체 측정 + 핏 평가
│   ├── BodyMeasurer.ts    # depth+키포인트 → 신체 치수
│   ├── FitEvaluator.ts    # 신체 vs 의류 치수 비교
│   └── types.ts           # 핏 타입, 측정 결과 타입
├── renderer/          # Three.js 렌더링
│   ├── SceneManager.ts    # 3D 씬 관리
│   ├── GarmentLoader.ts   # 의류 GLB 로더
│   └── FitOverlay.ts      # 핏 평가 오버레이 렌더러
└── ui/                # 선택적 UI 컴포넌트
    ├── TryOnWidget.tsx    # 시착 위젯
    └── FitPanel.tsx       # 핏 평가 패널
```

### 9-2. SDK 초기화 예시

```typescript
import { AutoFitSDK } from '@autofit/core';

const sdk = new AutoFitSDK({
  apiKey: 'af_live_abc123...',
  container: document.getElementById('try-on'),
  enableDepth: true,         // Depth Anything V2 활성화
  enableFitEvaluation: true, // 실시간 핏 평가 활성화
  offline: {
    enabled: true,           // 오프라인 모드 지원
    cacheModels: true,       // ONNX 모델 캐시
    cacheAssets: true,       // GLB 에셋 캐시
  },
});

await sdk.initialize();
await sdk.loadGarment('garment-id-123');
sdk.startTryOn();

// 핏 평가 결과 이벤트
sdk.on('fitEvaluation', (result) => {
  console.log(result.fitType);       // 'regular'
  console.log(result.suitabilityPct); // 87.5
  console.log(result.accuracyPct);    // 92.3
});

> SDK 내부 타입은 camelCase를 사용하고, API 저장 시 snake_case로 매핑한다.
> - `suitabilityPct` → `suitability_pct`
> - `accuracyPct` → `accuracy_pct`
```

### 9-3. 오프라인 지원

| 캐시 대상 | 저장소 | 크기 | 갱신 주기 |
|-----------|--------|------|----------|
| ONNX 모델 (Depth Anything V2) | IndexedDB | ~100MB | 모델 버전 변경 시 |
| MediaPipe WASM + 모델 | Service Worker Cache | ~10MB | 라이브러리 업데이트 시 |
| GLB 의류 에셋 | IndexedDB | 에셋당 1~5MB | 에셋 업데이트 시 |
| 의류 카탈로그 JSON | IndexedDB | ~1MB | 1시간 TTL |

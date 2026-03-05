# 기술 스택 및 아키텍처 결정 근거 문서 (v2.1 — WebAR)

> **문서 버전**: 2.1
> **최종 갱신**: 2026-03-03
> **작성 기준**: 순수 엔지니어링 관점 — 라이선스, 성능, 생태계, 팀 역량

---

## 1. 개요

### 1.1 v1 → v2 전환 배경

v1(매장 미러)은 NVIDIA GPU가 장착된 전용 디바이스를 전제로 설계되었다.
TensorRT, CUDA-GL interop, Warp XPBD 등 네이티브 GPU 스택에 의존하여
고성능을 달성했으나, 다음 한계가 명확했다.

| 항목 | v1 매장 미러 | v2 WebAR |
|------|-------------|----------|
| 배포 단위 | 매장별 전용 디바이스 | 브라우저 URL 접속 |
| 하드웨어 의존 | NVIDIA GPU 필수 | GPU 없어도 동작 |
| 사용자 접근성 | 매장 방문 필수 | 온라인 어디서나 |
| 유지보수 | 매장별 원격 관리 | 서버 배포 1회 |
| 확장성 | 디바이스 수 = 매장 수 | 동시 접속 100명+ (목표, 수평 확장 전제) |

**결론**: 온라인 의류 쇼핑몰 연동을 목표로, 브라우저 기반 WebAR로 전환한다.

### 1.2 기술 선정 기준

1. **라이선스**: MIT/Apache 2.0 우선, AGPL/상업용 라이선스 제외
2. **성능**: 모바일 30fps 이상 렌더링 + 트래킹 동시 달성
3. **생태계**: npm 주간 다운로드 수, GitHub 스타, 문서 품질, 커뮤니티 활성도
4. **팀 역량**: React/TypeScript 경험 활용 극대화

---

## 2. 기술 스택 상세

### 2.1 3D 렌더링: Three.js + react-three-fiber (R3F)

**선정 근거**:
- WebGL 2.0 기본 지원 + WebGPU renderer 공식 개발 중
- React 컴포넌트 모델과 완벽 통합 (선언적 씬 그래프)
- 가상 시착 오픈소스 레퍼런스 최다 (Shopify AR, Snap AR 등 참조)
- npm 주간 다운로드 200만+ (2026년 2월 기준)
- glTF/GLB 네이티브 로더, Draco/KTX2 확장 지원

**대안 비교**:

| 라이브러리 | 장점 | 탈락 사유 |
|-----------|------|----------|
| Babylon.js | PBR 품질 우수, WebGPU 지원 | 번들 크기 1.5MB+(gzip), React 통합 비공식 |
| PlayCanvas | 에디터 내장, 모바일 최적화 | SaaS 종속(에디터), 자체 호스팅 제한 |
| A-Frame | 선언적 HTML 태그 | 대규모 씬 성능 제한, 커스텀 셰이더 어려움 |

**라이선스**: MIT

---

### 2.2 Body Tracking: MediaPipe Pose Landmarker (Heavy)

**선정 근거**:
- 33개 키포인트 + 3D 좌표(x, y, z) + 월드 좌표(미터 단위)
- 모바일 30~60fps, 데스크톱 60fps 안정
- 브라우저 네이티브 실행 (WASM + WebGL delegate)
- Google 공식 지원, 장기 유지보수 보장

**대안 비교**:

| 라이브러리 | 키포인트 | 3D 지원 | FPS(모바일) | 라이선스 | 탈락 사유 |
|-----------|---------|---------|------------|---------|----------|
| MediaPipe Heavy | 33 | O (월드 좌표) | 30-60 | Apache 2.0 | **채택** |
| TF.js MoveNet | 17 | X (2D만) | 30-50 | Apache 2.0 | 3D 미지원, 키포인트 부족 |
| OpenPose | 25 | O | N/A(웹 미지원) | AGPL | 라이선스 불가, 웹 미지원 |
| BodyPix | 17 | X | 15-25 | Apache 2.0 | 성능 부족, 공식 지원 종료됨 (deprecated) |

**라이선스**: Apache 2.0

---

### 2.2b Depth Sensing: Depth Anything V2 Metric Depth

> **스코프 조정**: Depth Anything V2 통합은 ONNX 변환, 웹 최적화, 폴백 로직까지 고려하면
> 단독으로 2~3주가 소요될 수 있다. MVP에서는 P2로 하향하고, 신체 측정은
> 사용자 직접 입력 또는 포즈 기반 비율 추정(pose_scale)으로 폴백한다.

**선정 근거**:
- 단안 카메라 영상으로부터 depth map을 추정 (Metric Depth는 절대 스케일을 목표로 하나 보정/품질 게이트가 필요할 수 있음)
- ONNX Runtime Web으로 브라우저 네이티브 실행 (WebGL/WebGPU backend)
- MediaPipe 키포인트와 결합하여 신체 치수(cm) 추정 품질을 개선

**운영 정책 (필수)**:
- Depth는 **기본 비활성화 또는 저주기(예: 1~5Hz)** 로만 실행한다 (Pose 30Hz/Render 60Hz와 분리)
- ONNX 초기화 실패/메모리 압박/저사양/열화(thermal throttling) 감지 시 자동 비활성화하고 폴백(`pose_scale`/`user_input`)을 사용한다
- Depth 출력은 환경에 따라 오차가 커질 수 있으므로, UI에는 "정확도" 대신 **신뢰도(표시용) + 품질 상태(좋음/보통/나쁨)** 를 함께 노출한다

**모델 스펙**:

| 항목 | 값 |
|------|-----|
| 모델 | Depth Anything V2 Metric Depth (Small) |
| 입력 해상도 | 518×518 |
| 출력 | 단안 depth map (float32, 절대 스케일을 목표로 함) |
| 모델 크기 (ONNX) | ~100MB |
| 추론 시간 (데스크톱) | ~15ms |
| 추론 시간 (모바일) | ~40ms |
| 런타임 | ONNX Runtime Web (WebGL/WebGPU backend) |

**대안 비교**:

| 모델 | 절대 스케일 목표 | 웹 호환 | 모델 크기 | 탈락 사유 |
|------|----------|---------|----------|----------|
| **Depth Anything V2 Metric** | O (미터) | O (ONNX) | ~100MB | **채택(단, 보정/폴백 전제)** |
| MiDaS v3.1 | X (상대) | O (ONNX) | ~100MB | 절대 스케일 미지원 |
| ZoeDepth | O (미터) | △ (PyTorch) | ~350MB | 웹 실행 어려움, 무거움 |
| DepthPro (Apple) | O (미터) | X | ~500MB | 웹 미지원, 라이선스 제한 |

**라이선스**: Apache 2.0 (코드 기준). 모델 가중치/재배포 조건은 별도 확인이 필요하다.

---

### 2.3 포즈→본 매핑: Kalidokit

**선정 근거**:
- MediaPipe 33 키포인트 랜드마크 → Three.js 본 회전값(쿼터니언/오일러) 자동 변환
- 상반신/하반신/얼굴 회전 모두 지원
- 소스 350줄 미만, 의존성 제로 — 필요 시 포크 후 커스텀 용이
- VTuber/바디 트래킹 분야에서 검증된 정확도

> ⚠️ **호환성 주의**: Kalidokit은 구버전 `@mediapipe/pose` (v1 API) 기준으로 설계되었다.
> 본 프로젝트에서 사용하는 `@mediapipe/tasks-vision` (v2 API)의 랜드마크 출력 포맷이
> 다를 수 있으므로 어댑터 레이어가 필요할 수 있다. **M2 착수 전 PoC 필수.**
>
> - v1: `results.poseLandmarks` (NormalizedLandmarkList)
> - v2: `result.landmarks` (NormalizedLandmark[][])
>
> Kalidokit은 350줄 미만, 의존성 제로이므로 필요 시 포크하여 v2 포맷에 맞게 수정 가능하다.

**라이선스**: MIT

---

### 2.4 Cloth Simulation: 우선순위 기반 계층화

> 상세 설계는 `docs/CLOTH_SIMULATION.md` 참조

**우선순위 계층**:

| 우선순위 | 방식 | 설명 |
|---------|------|------|
| **P0 (MVP)** | SkinnedMesh 본 바인딩 | Kalidokit 본 회전으로 의류 SkinnedMesh 변형, VRM 아바타 본 구조에 의류 바인딩 |
| **P1 (MVP 필수)** | Normal Map Animation | 관절 각도 → 주름 노멀맵 블렌딩, LBS 한계(Candy-Wrapper, 주름 부재) 보완. GPU 비용 < 0.5ms |
| **P2** | VAT 프리베이크 | Blender cloth sim → glTF VAT, 물리 연산 제로 |
| **P3 (스코프 아웃)** | 런타임 물리 (WebGPU XPBD) | 6주 6명 팀에서 구현 비현실적, 도전 과제로 분류 |

**선정 근거**:
- SkinnedMesh 본 바인딩(P0)은 포즈 추종의 기반이지만, LBS(Linear Blend Skinning) 고유 한계로
  Candy-Wrapper 효과, 주름/접힘 부재, 드레이프 부재 등 시각 결함이 발생한다
- Normal Map Animation(P1)은 GPU 비용 < 0.5ms로 이러한 LBS 결함을 효과적으로 보완하므로 MVP 필수
- P0 + P1 조합으로 정면 시착 기준 충분한 시각 품질 확보 (업계 표준: EA DICE, Activision CoD GDC 2019)
- 런타임 물리는 MVP 범위 밖으로 분류하여 개발 리스크 제거

---

### 2.5 물리 엔진: Rapier.js (@react-three/rapier)

**선정 근거**:
- Rust WASM 네이티브 빌드로 Ammo.js 대비 2~3배 빠른 성능
- TypeScript 타입 정의 내장, R3F 공식 통합 (@react-three/rapier)
- 충돌 감지(의류-바디 관통 방지) + 강체 물리(액세서리) 용도
- Cloth sim을 SkinnedMesh+Normal Map+VAT로 대체하므로 SoftBody 불필요

**대안 비교**:

| 라이브러리 | 장점 | 단점 | 비고 |
|-----------|------|------|------|
| **Rapier.js** | Rust WASM 네이티브, 빠르고 가벼움, TS 타입 내장, R3F 공식 통합 | SoftBody 미지원 | **채택** |
| Ammo.js | C++ Bullet 포팅, SoftBody(btSoftBody) 지원 | 무거움(1MB+ WASM), API 혼란(C++ 직접 매핑), TS 타입 미흡 | SoftBody 불필요하므로 탈락 |
| Cannon-es | 경량, TS 지원 | 기능 부족, 유지보수 불안정 | 생태계 부족 |

**라이선스**: MIT (Apache 2.0 dual)

---

### 2.6 아바타: three-vrm + VRM

**선정 근거**:
- VRM 포맷은 일본 pixiv에서 유지보수하는 3D 아바타 표준 (glTF 확장)
- Kalidokit과 네이티브 호환 — VRM 본 구조(VRMHumanoid)가 Kalidokit 출력과 직접 매핑
- 풀바디 리깅 + 표정(BlendShape) + 시선(LookAt) 내장
- three-vrm은 Three.js 공식 생태계, R3F에서 바로 사용 가능
- VTuber 분야에서 검증된 안정성 (Wawa Sensei 튜토리얼 등 레퍼런스 다수)

**라이선스**: MIT

---

### 2.6b Fit Evaluation Engine

**개요**: 사용자의 실측 신체 치수와 의류 실측 치수를 비교하여 핏 타입(슬림핏/레귤러핏/오버핏)을 자동 분류하고, 적합도(%) 및 정확도(%)를 실시간 산출하는 엔진이다.

**핏 타입 정의**:

| 코드 | 한국어 | 기준 (의류 치수 - 신체 치수) |
|------|--------|---------------------------|
| `slim` | 슬림핏 | 여유량 < 3cm |
| `regular` | 레귤러핏(적정핏) | 여유량 3~8cm |
| `oversize` | 오버핏 | 여유량 > 8cm |

**측정 항목** (7개):
- `shoulder_width_cm`: 어깨너비
- `chest_circumference_cm`: 가슴둘레
- `waist_circumference_cm`: 허리둘레
- `hip_circumference_cm`: 힙둘레
- `height_cm`: 키
- `arm_length_cm`: 팔길이
- `inseam_cm`: 인심

**정확도 상한**: 99 (표시용 신뢰도 캡, 실제 실측 정확도를 의미하지 않음)

---

### 2.6c SDK Architecture

> **⚠️ 스코프 조정**: SDK 모듈화(@autofit/* 패키지 분리)는 6주 일정 내 구현이 비현실적이다.
> MVP에서는 `frontend/` 일체형 앱으로 구현하고, SDK 분리는 후속 작업으로 분류한다.

**개요**: AutoFit 가상 시착 기능을 외부 쇼핑몰에 통합할 수 있도록 모듈러 ES module SDK로 설계한다. 온라인/오프라인 모두 지원하며, 개발자 친화적 API를 제공한다.

**SDK 코어 모듈 구성**:

| 모듈 | 설명 |
|------|------|
| `@autofit/core` | 초기화, 설정, 라이프사이클 관리 |
| `@autofit/body-tracker` | MediaPipe + Depth Anything V2 통합 바디 트래킹 |
| `@autofit/fit-evaluator` | 신체 측정 + 핏 평가 엔진 |
| `@autofit/renderer` | Three.js + R3F 기반 3D 렌더링 |
| `@autofit/ui` | 시착 UI 컴포넌트 (선택적) |

**오프라인 지원**: Service Worker + IndexedDB로 ONNX 모델과 GLB 에셋을 로컬 캐시, 네트워크 없이 시착 가능

---

### 2.7 프론트엔드

| 항목 | 선택 | 근거 |
|------|------|------|
| 프레임워크 | React 18 | 팀 전원 경험 보유, R3F 통합 |
| 언어 | TypeScript (strict) | 타입 안전성, 3D 좌표/본 타입 필수 |
| 빌드 | Vite | HMR 속도, ESM 네이티브 |
| 상태 관리 | Zustand | 경량, 3D 씬 상태 연동 용이 |
| 서버 상태 관리 | TanStack Query 5.x | API 캐싱, 자동 리페치, 옵티미스틱 업데이트 |
| 스타일 | Tailwind CSS | 유틸리티 퍼스트, 반응형 |
| 3D | Three.js + R3F + drei | 씬 그래프 선언적 관리 |
| UI 컴포넌트 | Shadcn/ui | 커스텀 용이, Tailwind 기반 |

---

### 2.8 백엔드

| 항목 | 선택 | 근거 |
|------|------|------|
| 프레임워크 | FastAPI | async 네이티브, OpenAPI 자동 생성 |
| ORM | SQLAlchemy 2.0 + Alembic | async 세션, 마이그레이션 관리 |
| 인증 | JWT (PyJWT + passlib) | 무상태 인증, 프론트엔드 호환 |
| 캐시/Pub-Sub | Redis 7 | 에셋 메타 캐시, 세션 이벤트 |

> **참고**: python-jose는 메인테이너 활동이 감소한 상태이다. PyJWT 또는 python-jose[cryptography] 포크로 전환을 검토할 수 있다. 현재 프로젝트에서는 기존 코드베이스 호환성을 위해 python-jose를 유지하되, 보안 패치가 필요한 경우 PyJWT로 마이그레이션한다.

---

### 2.9 데이터베이스

| 항목 | 선택 | 근거 |
|------|------|------|
| RDBMS | PostgreSQL 16 | 의류 카탈로그, 피팅 세션, JSON 필드 |
| 캐시 | Redis 7 | 에셋 URL 캐시, 세션 임시 데이터 |

---

### 2.10 3D 에셋 포맷

| 항목 | 선택 | 근거 |
|------|------|------|
| 메쉬 | glTF 2.0 / GLB | 웹 3D 표준, Three.js 네이티브 지원 |
| 압축 | Draco | 메쉬 크기 80~90% 감소 |
| 텍스처 | KTX2 (Basis Universal) | GPU 직접 디코딩, 메모리 75% 절약 |
| 리깅 | glTF 스킨 + 본 | 표준 리깅, VRM Humanoid 본 구조 호환 |

---

### 2.11 패키지 관리

| 영역 | 도구 | 근거 |
|------|------|------|
| Python (BE) | uv | pip 대비 10~100배 빠른 설치 |
| Node.js (FE) | pnpm | 디스크 효율적, 엄격한 의존성 |

---

### 2.12 테스트

| 영역 | 도구 | 근거 |
|------|------|------|
| BE 단위/BDD | pytest + pytest-bdd | Given/When/Then 시나리오 |
| FE 단위 | Vitest | Vite 네이티브, Jest 호환 |
| FE E2E | Playwright | 크로스 브라우저, WebGL 캔버스 캡처 |
| 3D 시각 회귀 | Playwright + 스크린샷 비교 | 렌더링 결과 픽셀 비교 |

---

### 2.13 인프라

| 항목 | 선택 | 근거 |
|------|------|------|
| 컨테이너 | Docker Compose | BE + DB + Redis 통합 |
| 정적 서빙 | Nginx | FE 빌드 결과물 + 리버스 프록시 |
| 모니터링 | Prometheus + Grafana | API 레이턴시, 에셋 로드 시간 |
| CI/CD | GitHub Actions | PR 자동 테스트, 빌드, 배포 |

---

## 3. 아키텍처 다이어그램

### 3.1 전체 데이터 플로우

```
┌─────────────────────────────────────────────────────────────────────┐
│                        브라우저 (React + R3F)                        │
│                                                                     │
│  ┌──────────┐    ┌───────────┐    ┌───────────┐    ┌─────────────┐ │
│  │ 웹캠     │───▶│ MediaPipe │───▶│ Kalidokit │───▶│ Three.js    │ │
│  │ (Camera  │    │ Pose      │    │ 포즈→본   │    │ 본 리깅     │ │
│  │  API)    │    │ Landmarker│    │ 매핑      │    │ + 렌더링    │ │
│  └────┬─────┘    └───────────┘    └───────────┘    └──────┬──────┘ │
│       │                                                    │        │
│       ▼                                                    │        │
│  ┌──────────────────────┐    ┌──────────────────┐         │        │
│  │ Depth Anything V2    │───▶│ Body Measurer    │         │        │
│  │ Metric Depth (ONNX)  │    │ (신체 치수 계산) │         │        │
│  └──────────────────────┘    └────────┬─────────┘         │        │
│                               ▼                            │        │
│  ┌──────────────────────────────────────────────────────┐ │        │
│  │              Fit Evaluation Engine                    │ │        │
│  │  핏 타입 분류 + 적합도/정확도 산출 → UI 오버레이      │◀┘        │
│  └──────────────────────────────────────────────────────┘          │
│                                                                     │
│  ┌──────────────────────────────────────────────────────┐          │
│  │              Cloth Simulation Layer                   │          │
│  │  P0: SkinnedMesh 본 바인딩 + P1: NormalMap + P2: VAT │          │
│  └──────────────────────────────────────────────────────┘          │
│                                                                     │
│  ┌──────────────────────┐    ┌──────────────────────┐              │
│  │ UI (카탈로그/사이즈) │    │ 상태관리 (Zustand)   │              │
│  └──────────────────────┘    └──────────────────────┘              │
│                                                                     │
│  ┌──────────────────────────────────────────────────────┐          │
│  │              SDK Layer (@autofit/*)                   │          │
│  │  코어 / 바디트래커 / 핏평가 / 렌더러 / UI            │          │
│  └──────────────────────────────────────────────────────┘          │
└────────────────────────────────────┬────────────────────────────────┘
                                     │ REST API (HTTPS)
                                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         서버 인프라                                  │
│                                                                     │
│  ┌────────────┐    ┌──────────┐    ┌──────────┐    ┌────────────┐  │
│  │   Nginx    │───▶│ FastAPI  │───▶│PostgreSQL│    │   Redis    │  │
│  │ (정적서빙 │    │ (BE API) │    │   16     │    │     7      │  │
│  │ +리버스PX)│    │          │◀──▶│          │    │(캐시/PubSub)│  │
│  └────────────┘    └──────────┘    └──────────┘    └────────────┘  │
│                                                                     │
│  ┌──────────────────────┐    ┌──────────────────────┐              │
│  │ Prometheus + Grafana │    │    에셋 스토리지      │              │
│  │   (모니터링)         │    │  (glTF/GLB/KTX2)     │              │
│  └──────────────────────┘    └──────────────────────┘              │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 렌더링 파이프라인 상세

```
프레임 루프 (권장: 스케줄 분리)

- Pose 추론: video frame 기준(최대 30Hz)
- Depth 추론(선택): 저주기(예: 1~5Hz) 또는 측정 모드에서만
- 렌더: requestAnimationFrame(최대 60Hz)

1. 카메라 프레임 캡처
   │
2. MediaPipe Pose Landmarker 추론 → 33 키포인트 (x, y, z, visibility, presence)
   │
3. (선택) Depth Anything V2 Metric Depth 추론 → depth map(추정치) / 스케일 보정 값 업데이트
   │
4. 1-Euro Filter 적응형 스무딩 + 품질 게이트(가림/거리/지터) 적용
   │
5. (가능 시) Keypoints(+Depth/보정) → 신체 치수 계산 (7개 항목, cm)
   │
6. 신체 치수 vs 의류 실측 치수 → 핏 타입 분류 + 적합도/정확도(신뢰도) 산출
   │
7. Kalidokit 포즈→본 매핑 (본 회전)
   │
8. VRM 아바타 본 업데이트 (three-vrm)
   │
9. 의류 SkinnedMesh 본 바인딩 (P0) + (선택) Normal Map 블렌딩 (P1)
   │
10. R3F 렌더 (WebGL/WebGPU) + 핏 평가 UI 오버레이
```

---

## 4. 브라우저 호환성 매트릭스

| 브라우저 | Cloth 모드 | Depth 모델 | 예상 FPS | 비고 |
|---------|-----------|-----------|---------|------|
| **데스크톱 Chrome 120+** | SkinnedMesh + NormalMap | Depth Anything V2 (WebGPU, 저주기) | 55-60fps | 최적 경험 |
| **데스크톱 Edge 120+** | SkinnedMesh + NormalMap | Depth Anything V2 (WebGPU, 저주기) | 55-60fps | Chromium 기반 |
| **데스크톱 Firefox 최신** | SkinnedMesh + NormalMap | Depth Anything V2 (WebGL, 저주기) | 40-55fps | ONNX WebGL fallback |
| **데스크톱 Safari 17.4+** | SkinnedMesh + NormalMap | Depth Anything V2 (WebGL, 저주기) | 40-55fps | WebGL 2.0 기반 |
| **Android Chrome 120+** | SkinnedMesh + NormalMap | Depth Anything V2 (저주기) 또는 비활성화 | 25-40fps | 모바일 GPU 제한 |
| **Android Chrome (저사양)** | SkinnedMesh only | Depth 비활성화 | 30-60fps | NormalMap+Depth 생략 |
| **iOS Safari 17+** | SkinnedMesh + NormalMap | Depth 비활성화(기본) / 실험적 옵션 | 25-40fps | WebKit 메모리/열 제약 |
| **iOS Safari 16 이하** | SkinnedMesh only | Depth 비활성화 | 25-30fps | MediaPipe 성능 제한 |

### ONNX Runtime Web 전제조건(요약)

- `webgpu` execution provider는 `navigator.gpu` 지원 여부에 따라 활성화된다.
- `wasm` execution provider에서 threads/SIMD를 쓰려면 `crossOriginIsolated`(COOP/COEP)가 필요할 수 있다.
- 전제조건 미충족 시 성능이 크게 떨어질 수 있으므로, 런타임에서 탐지 후 Depth 기능을 자동 비활성화한다.

### 기능 감지 및 자동 선택

```typescript
// 런타임 기능 감지 순서
const tier = detectRenderTier();

function detectRenderTier(): 'full' | 'skinned-normalmap' | 'skinned-only' {
  // 1단계: WebGL 2.0 + GPU 성능 확인
  const gl = document.createElement('canvas').getContext('webgl2');
  if (!gl) return 'skinned-only';

  const gpuTier = estimateGPUTier(gl);

  // 2단계: GPU 성능 충분 + ONNX Runtime 지원 → 풀 기능 (NormalMap + Depth(선택/저주기))
  if (gpuTier >= 3 && supportsONNXRuntime()) {
    return 'full';  // SkinnedMesh + NormalMap (+ Depth Anything V2 선택)
  }

  // 3단계: 중간 성능 → NormalMap만 (Depth 비활성화)
  if (gpuTier >= 2) {
    return 'skinned-normalmap';  // SkinnedMesh + Normal Map
  }

  // 4단계: 최소 모드 (NormalMap + Depth 모두 생략)
  return 'skinned-only';
}
```

---

## 5. v1 → v2 기술 매핑

| v1 (매장 미러) | v2 (WebAR) | 전환 근거 |
|---------------|-----------|----------|
| RTMPose + TensorRT | MediaPipe Pose Landmarker | 브라우저 네이티브, GPU 불필요 |
| CUDA-GL interop | WebGL/WebGPU | 브라우저 표준 그래픽 API |
| Warp XPBD (NVIDIA) | SkinnedMesh + NormalMap + VAT | 본 바인딩 MVP, 런타임 물리 스코프 아웃 |
| OpenGL + moderngl | Three.js + R3F | React 통합, 선언적 씬 그래프 |
| PySide6 + QML | React + Tailwind | 웹 UI, 모바일 반응형 |
| CUDA 스트림 파이프라이닝 | requestAnimationFrame 루프 | 브라우저 이벤트 루프 기반 |
| systemd 서비스 | Nginx 정적 서빙 | 서버 배포 1회, CDN 가능 |

---

## 부록 A: 의존성 라이선스 요약

| 패키지 | 라이선스 | 상업 이용 |
|--------|---------|----------|
| Three.js | MIT | O |
| react-three-fiber | MIT | O |
| @react-three/drei | MIT | O |
| MediaPipe | Apache 2.0 | O |
| Kalidokit | MIT | O |
| Rapier.js | MIT / Apache 2.0 | O |
| three-vrm | MIT | O |
| Draco | Apache 2.0 | O |
| Basis Universal (KTX2 트랜스코더) | Apache 2.0 | O |
| React | MIT | O |
| Vite | MIT | O |
| Tailwind CSS | MIT | O |
| Zustand | MIT | O |
| TanStack Query | MIT | O |
| FastAPI | MIT | O |
| SQLAlchemy | MIT | O |
| PostgreSQL | PostgreSQL License | O |
| Redis | BSD-3 | O |
| Depth Anything V2 | Apache 2.0 (코드 기준) | O |
| ONNX Runtime Web | MIT | O |
| TRELLIS.2 | MIT | O |
| Material Anything | MIT | O |
| Robust Weight Transfer | GPL-3.0 | O (서버 측 처리) |

> 모델 가중치/데이터셋 라이선스 및 재배포 조건(특히 Depth 모델)은 별도 확인이 필요하다.
> TRELLIS.2 (MIT), Material Anything (오픈소스), Robust Weight Transfer (GPL-3.0)는 각각의 라이선스 조건을 준수해야 한다. GPL-3.0인 Robust Weight Transfer는 백엔드 서버 측 처리에만 사용하며, 프론트엔드 코드에 포함하지 않는다.

> 모든 핵심 의존성이 MIT/Apache 2.0/BSD 계열로, 상업적 사용에 제한 없음.

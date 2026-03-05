# 의류 3D 가상화 및 실시간 영상 합성 기술 검토서

> **작성일**: 2026-03-05
> **목적**: TRELLIS.2 기반 의류 3D 가상화 + 착용 스타일 템플릿 시스템 + 실시간 영상 합성의 기술적 실현 가능성 검토
> **핵심 결론**: 기술적으로 구현 가능하나, 단일 모델/도구로 해결되는 문제가 아니라 여러 최신 연구를 조합해야 하는 통합 엔지니어링 프로젝트

---

## 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [초기 검토: Meshy AI 평가 및 한계](#2-초기-검토-meshy-ai-평가-및-한계)
3. [TRELLIS.2 기반 재설계](#3-trellis2-기반-재설계)
4. [단계별 기술 상세 검토](#4-단계별-기술-상세-검토)
5. [착용 스타일 템플릿 시스템](#5-착용-스타일-템플릿-시스템)
6. [멀티레이어 충돌 처리](#6-멀티레이어-충돌-처리)
7. [권장 전체 아키텍처](#7-권장-전체-아키텍처)
8. [기술적 실현 가능성 종합 판정](#8-기술적-실현-가능성-종합-판정)
9. [핵심 리스크와 완화 전략](#9-핵심-리스크와-완화-전략)
10. [권장 최소 기술 스택](#10-권장-최소-기술-스택)
11. [참고 자료](#11-참고-자료)

---

## 1. 프로젝트 개요

### 목표

의류의 3D 가상화(재질, 제직방식, 사이즈 등 포함)를 수행한 후, 이를 실시간 영상에 합성하여 가상 피팅 서비스를 구현한다.

### 핵심 요구사항

- 의류 이미지/텍스트로부터 고품질 3D 모델 생성
- 재질 및 텍스처의 사실적 표현 (PBR 기반)
- 사이즈 파라미터화 (가슴둘레, 허리둘레, 엉덩이둘레, 기장 등)
- 다양한 착용 방식의 템플릿화 (넣입, 빼입, 단추 열기/잠그기, 허리 매기, 목 매기, 레이어드)
- 생성된 3D 의류를 실시간 카메라 영상 위에 합성

### 전체 파이프라인 구조

```
┌─────────────────────────────────────────────────────────────────────┐
│                        [오프라인 준비 단계]                            │
│                                                                     │
│  ① 의류 이미지 → TRELLIS.2 → 3D 메시(GLB/PBR)                       │
│  ② 착용 템플릿 시스템 (넣입/빼입/단추/레이어드 등)                      │
│  ③ 템플릿 기반 메시 변형 + SMPL 바디 피팅 + 리깅                       │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                        [실시간 합성 단계]                              │
│                                                                     │
│  ④ 카메라 → Pose Estimation → 3D Body Mesh 추정                     │
│  ⑤ 의류 메시 → Body에 드레이핑 (Neural Cloth Sim)                     │
│  ⑥ 렌더링 + 카메라 프레임 합성 → 출력                                 │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. 초기 검토: Meshy AI 평가 및 한계

### 2.1 Meshy AI 개요

Meshy AI는 텍스트/이미지로부터 3D 모델을 생성하는 AI 플랫폼으로, 4천만 개 이상의 모델이 생성되고 500만 명 이상의 크리에이터가 사용 중이다.

- **Text-to-3D**: 텍스트 프롬프트로 1분 이내 3D 모델 생성
- **Image-to-3D**: 2D 이미지를 3D 모델로 변환
- **AI Texturing**: PBR 텍스처(Diffuse, Roughness, Metallic, Normal) 자동 생성
- **출력 포맷**: OBJ, FBX, USDZ, GLB, STL, BLEND

### 2.2 Meshy AI 버전 히스토리 (2025~2026)

| 버전 | 시기 | 주요 업데이트 |
|------|------|-------------|
| Meshy 5 Preview | 2025.07 | 멀티뷰 입력 지원, 기하학 정밀도 향상, 500+ 애니메이션 추가 |
| Meshy 6 Preview | 2025.10 | 조각 수준 디테일, 3D→이미지/영상 워크스페이스, 배치 생성 |
| CES 2026 | 2026.01 | AI Creative Lab (3D→실물 제조 파이프라인) |

### 2.3 Meshy AI의 의류 3D 생성 한계

| 항목 | 지원 여부 | 비고 |
|------|-----------|------|
| 의류 형태 3D 생성 | O | Text-to-3D, Image-to-3D 모두 지원 |
| PBR 텍스처 생성 | O | Diffuse, Roughness, Metallic, Normal 맵 |
| 다양한 포맷 출력 | O | FBX, GLB, OBJ, USDZ, BLEND 등 |
| 시각적 재질감 표현 | △ | 프롬프트 기반으로 "보이는" 질감은 가능 |
| **제직방식 물리 시뮬레이션** | **X** | 물리적 직물 특성(인장강도, 전단, 굴곡) 파라미터 미지원 |
| **정확한 사이즈 스펙** | **X** | AI 생성 모델은 임의 스케일 출력, 정밀 치수 보장 불가 |
| **직물 역학적 드레이프** | **X** | 정적 3D 메시 생성 도구이며, 천 시뮬레이션 엔진 아님 |
| **봉제선/솔기 표현** | **△** | 텍스처로 시각적 표현 가능하나 구조적 봉제 시뮬레이션 불가 |

### 2.4 Meshy AI 단독 사용 불가 판정 사유

Meshy AI는 **범용 3D 에셋 생성기**이지, **의류 전문 CAD/시뮬레이션 도구가 아니다.** 재질·제직방식·사이즈를 "물리적으로 정확하게" 반영하려면 패션 전문 3D 도구가 필요하며, 실시간 영상 합성은 별도의 AR/렌더링 엔진과의 통합이 필수적이다.

### 2.5 실시간 AR 합성 기술 현황 (Meshy 검토 시점)

| 솔루션 | 방식 | 실시간 여부 | 비고 |
|--------|------|-------------|------|
| Snap Garment Transfer | 2D→3D 변환 후 AR 합성 | O | 상반신 의류 위주, Lens Studio 기반 |
| Kivisense AR Try-On | 3D Body Mesh + 물리 시뮬레이션 | O | 모바일 최적화, 자체 물리엔진 탑재 |
| uDraper | Unreal Engine 기반 실시간 천 시뮬레이션 | O | 게임엔진 플러그인 형태 |

---

## 3. TRELLIS.2 기반 재설계

### 3.1 TRELLIS.2 선정 사유

Meshy AI의 한계를 고려하여, Microsoft의 **TRELLIS.2**를 3D 의류 생성 기반 모델로 재선정하였다.

### 3.2 TRELLIS.2 핵심 스펙

| 항목 | 사양 |
|------|------|
| 파라미터 수 | 4B (40억) |
| 출력 해상도 | 최대 1536³ voxel |
| 생성 속도 (H100) | 512³ ~3초, 1024³ ~17초, 1536³ ~60초 |
| PBR 지원 | Base Color, Metallic, Roughness, Alpha(투명도) |
| 출력 포맷 | .glb (Unity/Unreal/Blender 즉시 호환) |
| 라이선스 | MIT (상업적 사용 가능) |
| GPU 요구사항 | NVIDIA 24GB+ (A100, H100에서 검증) |

### 3.3 TRELLIS.2의 의류 생성 적합성

| 항목 | 평가 | 근거 |
|------|------|------|
| 의류 형태 생성 | **우수** | O-Voxel이 open surface(의류) 토폴로지를 명시적으로 지원 — 기존 iso-surface 방식의 한계 극복 |
| PBR 재질 | **우수** | Base Color, Metallic, Roughness, Alpha 모두 지원 |
| 생성 속도 | **우수** | H100 기준 512³에서 ~3초 |
| 출력 포맷 | **적합** | .glb 출력 → Unity/Unreal/Blender 즉시 호환 |
| 의류 도메인 특화 | **미흡** | 범용 3D 모델이므로 의류 데이터로 fine-tune 필요 |
| Fine-tune 가능 여부 | **가능** | MIT 라이선스, 전체 학습 코드베이스 공개, 커스텀 데이터셋 fine-tune 문서화 |

### 3.4 O-Voxel 표현의 핵심 이점

TRELLIS.2의 O-Voxel은 "field-free" sparse voxel 구조로, 기존 iso-surface 방식이 어려워하는 다음을 지원한다:

- **Open surface** (의류, 나뭇잎 등)
- **Non-manifold geometry** (복잡한 토폴로지)
- **Enclosed interior** (내부 구조)
- **투명/반투명 재질**

의류는 본질적으로 open surface이므로, 이 특성이 의류 3D 생성에 구조적으로 적합하다.

### 3.5 Fine-tuning 전략

TRELLIS.2는 전체 학습 코드베이스가 공개되어 있으며, 커스텀 데이터셋으로 fine-tune이 가능하다:

- 원본 데이터셋: TRELLIS-500K (Objaverse(XL), ABO, 3D-FUTURE 등에서 큐레이션)
- 학습 전 3D 에셋을 O-Voxel 표현으로 변환 필요 (mesh → O-Voxel → compact latent)
- 고해상도 fine-tune 설정: `shape_vae_next_dc_f16c32_fp16_ft_512.json`
- 의류 전문 3D 데이터셋으로 fine-tune하여 봉제선, 디테일 품질 향상 가능

---

## 4. 단계별 기술 상세 검토

### 4.1 SMPL 바디 피팅 + 사이즈 시스템

#### 핵심 기술

| 기술 | 역할 | 비고 |
|------|------|------|
| **SMPL-X** | 전신 3D 바디 모델 (손, 얼굴 포함) | MPI 제공 |
| **SMPLify-X** | 2D 이미지 → SMPL 파라미터 추정 | OpenPose 키포인트 기반 |
| **CAPE** | SMPL 위 의류 변형 모델링 | Graph Conv. 기반 |

#### SMPL 파라미터 체계

```
사용자 신체 정보 입력 (키, 몸무게, 체형 또는 사진)
        ↓
SMPL-X 모델 파라미터화
  - β (shape): 10~300 차원 체형 파라미터
  - θ (pose): 관절 회전
        ↓
의류 메시를 SMPL body 위에 드레이핑
  - 의류 정점 = SMPL 정점 + displacement offset
  - CAPE/SCULPT 모델로 pose-dependent 변형 학습
```

#### 사이즈 시스템 구현

SMPL의 β 파라미터를 실제 신체 치수(가슴둘레, 허리둘레, 엉덩이둘레)로 매핑하는 regression 모델이 존재하므로, 사용자가 치수를 입력하면 해당 체형의 SMPL 모델을 생성하고 그 위에 의류를 드레이핑하는 방식이 현실적이다.

### 4.2 실시간 Pose Estimation

| 모델 | FPS | 키포인트 | 3D 지원 | 적합 환경 |
|------|-----|---------|---------|-----------|
| **MediaPipe BlazePose** | 30+ | 33 | O | 모바일/웹 |
| **DensePose** | 4~25 | UV 전체 | O | 서버 사이드 |
| **RTMW** | 실시간 | 133 (whole-body) | O | GPU 서버 |
| **NVIDIA BodyTrack** | 실시간 | 전신 | O | NVIDIA GPU |

#### BlazePose 파이프라인

- 2단계 detector-tracker ML 파이프라인
- 디텍터가 프레임 내 포즈 ROI를 먼저 감지
- 바디 트래커가 33개 키포인트를 정규화 및 3D 프레임으로 회귀
- GHUM 리프터 모듈(MLP-Mixer 아키텍처)로 75개 키포인트 → SMPL 통계 바디 모델 파라미터 매핑

### 4.3 실시간 Cloth Simulation

| 기술 | 실시간 여부 | 멀티레이어 | 정확도 | 비고 |
|------|------------|-----------|--------|------|
| 전통 물리 시뮬레이션 (PBD) | △ (단일 의류만) | X | 높음 | 연산량 과다 |
| **UNIC** (Neural Deformation Field) | **O** | X | 중상 | Marvelous Designer보다 빠름 |
| **GNN 기반** (SAGS-GNN 등) | **O** | △ | 중상 | self-collision 처리 가능 |
| **Gaussian Garments** | △ | **O** | 높음 | 멀티레이어 리사이즈/리포즈 가능 |
| **LayersNet** | △ | **O** | 중상 | 바람 등 외력 대응 |

### 4.4 렌더링 + 영상 합성

| 플랫폼 | 렌더링 엔진 | AR 합성 | 적합 시나리오 |
|--------|------------|---------|-------------|
| Unity + AR Foundation | URP/HDRP | ARKit/ARCore | 네이티브 앱 (모바일) |
| Unreal Engine | Nanite/Lumen | ARActor | 고품질 PC/콘솔 |
| Three.js + WebXR | WebGL/WebGPU | WebXR API | 웹 기반 서비스 |
| Snap Lens Studio | 자체 엔진 | Garment Transfer | SNS 연동 간편 |

---

## 5. 착용 스타일 템플릿 시스템

### 5.1 템플릿화 대상 및 구현 전략

| 착용 방식 | 기하학적 변형 유형 | 난이도 | 권장 접근법 |
|-----------|-------------------|--------|-------------|
| **넣입 (tuck-in)** | 하의 안으로 메시 클리핑 + 변형 | ★★★☆☆ | Body mesh의 waist 기준 clipping plane + 메시 변형 |
| **빼입 (untucked)** | 기본 드레이프 상태 | ★★☆☆☆ | 기본 시뮬레이션 결과 그대로 사용 |
| **단추 열기** | 앞판 메시 분리 + 열림 각도 | ★★★★☆ | 메시를 좌/우 패널로 분리 → Blend Shape 또는 Bone 기반 열림 제어 |
| **단추 잠그기** | 패널 결합 + 경계 정렬 | ★★★☆☆ | 닫힌 상태를 기본 토폴로지로, 열림을 Morph Target으로 |
| **허리에 매기** | 소매/몸판을 허리 위치에 래핑 | ★★★★☆ | Bone constraint로 waist 주변 래핑 포즈 사전 정의 |
| **목에 매기** | 의류를 neck 위치에 드레이핑 | ★★★☆☆ | Neck bone 기준 attachment point + 중력 시뮬레이션 |
| **레이어드** | 다중 의류 간 충돌 처리 | ★★★★★ | 멀티레이어 cloth collision — 가장 어려운 부분 |

### 5.2 파라메트릭 의류 모델 설계

```
[GarmentCode / GarmentX]  ← 파라메트릭 패턴 정의 (DSL 기반)
        ↓
[착용 스타일 파라미터]
  - tuck_state: enum {tucked, untucked, half_tucked}
  - button_state: float [0.0 = 완전 잠금 ~ 1.0 = 완전 열림]
  - wrap_target: enum {none, waist, neck, shoulder}
  - layer_order: int (레이어 순서)
  - size_params: {chest, waist, hip, length, sleeve_length}
        ↓
[Differentiable Cloth Simulator로 최종 형상 결정]
```

### 5.3 핵심 참고 논문 및 도구

| 기술 | 역할 | 핵심 특징 |
|------|------|-----------|
| **GarmentCode** | 파라메트릭 봉제 패턴 DSL | 소매, 칼라, 스커트 등을 파라메트릭 컴포넌트로 프로그래밍, 신체 치수 기반 리타겟팅 지원 |
| **GarmentX** | 3D garment 생성 | single-layer open-structure, 시뮬레이터와 직접 연동 가능 |
| **SMPLicit** | 토폴로지 인식 의류 생성 | 민소매~후드~오픈 재킷, 사이즈/핏 제어 가능, 저차원 해석 가능한 파라미터 벡터 |
| **Design2GarmentCode** | 디자인→패턴 자동 변환 | 디자인 컨셉 → 파라메트릭 봉제 패턴 자동 변환 |

---

## 6. 멀티레이어 충돌 처리

### 6.1 멀티레이어의 정의

멀티레이어는 **의류 간 겹침/중첩**을 의미한다:

- **상하의 조합**: 상의 메시가 하의 메시 위에 올라가면서 두 메시 간 충돌 처리 필요
  - 예: 셔츠 넣입 시 셔츠 메시가 바지 메시 안쪽으로 들어가야 함
- **상의 레이어드**: 이너 위에 아우터를 겹쳐 입는 경우
  - 예: 티셔츠 → 셔츠 → 자켓 순서로 3장이 겹침

### 6.2 연산 복잡도

```
단일 의류:   Body ↔ 의류1        → 충돌면 1쌍
2벌 겹침:    Body ↔ 의류1 ↔ 의류2  → 충돌면 3쌍
3벌 겹침:    Body ↔ 1 ↔ 2 ↔ 3    → 충돌면 6쌍
```

레이어가 하나 추가될 때마다:

- **메시 간 관통(penetration) 방지** 연산이 기하급수적으로 증가
- 안쪽 옷이 바깥쪽 옷의 형태에 영향을 주고, 그 역도 성립 (양방향 상호작용)
- 안쪽 옷의 두께만큼 바깥 옷이 밀려나는 간격 유지 필요

### 6.3 관련 최신 연구

| 기술 | 핵심 내용 |
|------|-----------|
| **Gaussian Garments** | 멀티뷰 비디오에서 시뮬레이션 가능한 의류 복원, GNN으로 self-penetration 방지, 멀티레이어 아웃핏 자동 모델링 |
| **LayersNet** (ICCV 2023) | 멀티레이어 의류 애니메이션, 인체/바람 등 외력 대응 |
| **SimAvatar** (CVPR 2025) | 시뮬레이션 가능한 아바타 + 레이어드 헤어/의류 |

### 6.4 현실적 완화 전략

| 전략 | 설명 |
|------|------|
| **사전 베이크** | 대표 포즈 N개에 대해 오프라인으로 멀티레이어 시뮬레이션 → Blend Shape로 저장 |
| **런타임 보간** | 실시간에는 가장 가까운 사전 포즈 2~3개를 보간만 수행 (연산량 극감) |
| **레이어 수 제한** | 실시간 서비스에서는 **최대 2~3레이어**로 제한하면 충분히 실용적 |

상하의 조합 + 아우터 1벌 정도(3레이어)까지는 현재 기술로 실시간 처리가 현실적인 범위이다.

---

## 7. 권장 전체 아키텍처

```
═══════════════════════════════════════════════════════════════
                    [오프라인 에셋 파이프라인]
═══════════════════════════════════════════════════════════════

  의류 이미지/텍스트
       │
       ▼
  ┌──────────────┐     ┌───────────────────┐
  │  TRELLIS.2   │────▶│  Raw 3D Mesh      │
  │  (fine-tuned │     │  (.glb + PBR)     │
  │   on garment │     └───────┬───────────┘
  │   dataset)   │             │
  └──────────────┘             ▼
                    ┌──────────────────────┐
                    │  GarmentCode 기반     │
                    │  파라메트릭 템플릿화   │
                    │                      │
                    │  params: {           │
                    │    tuck_state,       │
                    │    button_openness,  │
                    │    wrap_target,      │
                    │    layer_order,      │
                    │    size: {β params}  │
                    │  }                   │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │  Differentiable      │
                    │  Cloth Simulator     │
                    │  (사전 시뮬레이션)     │
                    │  → Blend Shape 베이크 │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │  SMPL-X 바디 피팅     │
                    │  + 리깅/스키닝        │
                    │  → 최종 에셋 저장     │
                    └──────────────────────┘

═══════════════════════════════════════════════════════════════
                    [실시간 렌더링 파이프라인]
═══════════════════════════════════════════════════════════════

  카메라 영상 (30fps)
       │
       ├──▶ MediaPipe/RTMW ──▶ 2D/3D Keypoints
       │                            │
       │                            ▼
       │                     SMPL-X Fitting
       │                     (실시간 체형+포즈)
       │                            │
       │                            ▼
       │                     Neural Cloth Sim
       │                     (UNIC / GNN 기반)
       │                     + 멀티레이어 충돌처리
       │                            │
       │                            ▼
       │                     의류 메시 변형 완료
       │                            │
       └──────────┬─────────────────┘
                  │
                  ▼
           GPU 렌더링 (Unity URP / Three.js)
           + 카메라 프레임 합성
                  │
                  ▼
           최종 출력 (실시간 영상)
```

---

## 8. 기술적 실현 가능성 종합 판정

| 구성요소 | 가능 여부 | 난이도 | 필요 조건 |
|----------|----------|--------|-----------|
| TRELLIS.2 의류 3D 생성 | **가능** | ★★★☆☆ | 의류 데이터셋 fine-tune, GPU(24GB+) |
| 사이즈 파라미터화 | **가능** | ★★★☆☆ | SMPL β 파라미터 ↔ 실측 치수 매핑 |
| 넣입/빼입 템플릿 | **가능** | ★★★☆☆ | Clipping + Blend Shape |
| 단추 열기/잠그기 | **가능** | ★★★★☆ | 메시 분리 + Morph Target 제어 |
| 허리/목 매기 | **가능** | ★★★★☆ | Bone constraint + 중력 sim 사전 정의 |
| 단일 의류 실시간 합성 | **가능** | ★★★★☆ | Neural cloth sim + pose estimation |
| **멀티레이어 실시간 합성** | **조건부 가능** | ★★★★★ | GNN cloth sim + 고성능 GPU, 최신 연구 수준 |
| 전체 파이프라인 통합 | **가능하나 고난도** | ★★★★★ | 6개월+ 개발, ML+그래픽스 전문 인력 필요 |

---

## 9. 핵심 리스크와 완화 전략

### Risk 1: TRELLIS.2 출력물의 의류 품질

- **문제**: 범용 모델이라 봉제선, 디테일이 부족할 수 있음
- **완화**: 의류 3D 데이터셋으로 fine-tune + 후처리 자동화 파이프라인 구축

### Risk 2: 착용 스타일 템플릿의 일반화

- **문제**: 모든 의류 × 모든 착용방식 조합을 수동 정의하면 조합 폭발
- **완화**: GarmentCode식 파라메트릭 DSL로 규칙 기반 자동 생성 → 수동 작업 최소화

### Risk 3: 멀티레이어 실시간 충돌 처리

- **문제**: 2벌 이상의 의류 간 물리 시뮬레이션은 현재 실시간이 매우 어려움
- **완화**: 사전 시뮬레이션으로 대표 포즈별 Blend Shape를 베이크 → 실시간에는 보간만 수행 (하이브리드 접근)

### Risk 4: 실시간 성능

- **문제**: Pose estimation + SMPL fitting + cloth sim + rendering을 매 프레임 처리
- **완화**: pose estimation은 경량 모델(BlazePose), cloth sim은 Neural 방식(UNIC), 렌더링은 GPU 최적화

---

## 10. 권장 최소 기술 스택

| 역할 | 권장 기술 | 대안 |
|------|-----------|------|
| 3D 의류 생성 | **TRELLIS.2** (fine-tuned) | Meshy AI, Rodin Gen-2 |
| 파라메트릭 템플릿 | **GarmentCode** + 자체 DSL | SMPLicit, GarmentX |
| 바디 모델 | **SMPL-X** | GHUM (Google) |
| Pose Estimation | **MediaPipe BlazePose** (모바일) / **RTMW** (서버) | DensePose, OpenPose |
| Cloth Simulation | **UNIC** (단일) / **GNN 기반** (멀티레이어) | Gaussian Garments |
| 렌더링/합성 | **Unity + AR Foundation** (앱) / **Three.js + WebXR** (웹) | Unreal Engine |
| 사이즈 추정 | **SMPLify-X** (사진→체형) | 직접 치수 입력 |

---

## 11. 참고 자료

### 3D 생성 모델

- [TRELLIS.2 공식 페이지](https://microsoft.github.io/TRELLIS.2/)
- [TRELLIS.2 GitHub](https://github.com/microsoft/TRELLIS.2)
- [TRELLIS.2-4B HuggingFace](https://huggingface.co/microsoft/TRELLIS.2-4B)
- [TRELLIS-500K 데이터셋](https://huggingface.co/datasets/JeffreyXiang/TRELLIS-500K)
- [Meshy AI 공식 사이트](https://www.meshy.ai/)
- [Meshy 6 Preview 발표](https://www.newsfilecorp.com/release/270549/)
- [Meshy CES 2026](https://www.advancedmanufacturing.org/news-desk/events/ces/meshy-unveils-ai-creative-lab-at-ces-2026/)

### 파라메트릭 의류 모델링

- [GarmentCode (ACM ToG)](https://dl.acm.org/doi/10.1145/3618351)
- [GarmentX](https://arxiv.org/html/2504.20409)
- [SMPLicit (CVPR 2021)](https://ar5iv.labs.arxiv.org/html/2103.06871)
- [Design2GarmentCode](https://arxiv.org/html/2412.08603v1)
- [GarmentCodeData 데이터셋](https://arxiv.org/html/2405.17609v1)

### 바디 모델 및 Pose Estimation

- [SMPL-X](https://smpl-x.is.tue.mpg.de/)
- [CAPE](https://www.researchgate.net/figure/CAPE-model-for-clothed-humans_fig1_343456738)
- [MediaPipe BlazePose](https://research.google/blog/on-device-real-time-body-pose-tracking-with-mediapipe-blazepose/)
- [DensePose](http://densepose.org/)
- [RTMW](https://arxiv.org/html/2407.08634v1)
- [SMPL Virtual Try-On (SDH)](https://sdh.global/projects/virtual-try-on-room-with-smpl-anthropometry/)

### Cloth Simulation

- [UNIC - Neural Garment Deformation](https://igl-hkust.github.io/UNIC/)
- [SAGS-GNN](https://www.sciencedirect.com/science/article/abs/pii/S0097849325000573)
- [Gaussian Garments](https://arxiv.org/html/2409.08189v1)
- [LayersNet (ICCV 2023)](https://openaccess.thecvf.com/content/ICCV2023/papers/Shao_Towards_Multi-Layered_3D_Garments_Animation_ICCV_2023_paper.pdf)
- [SimAvatar (CVPR 2025)](https://openaccess.thecvf.com/content/CVPR2025/papers/Li_SimAvatar_Simulation-Ready_Avatars_with_Layered_Hair_and_Clothing_CVPR_2025_paper.pdf)
- [Garment Draping 비교 연구](https://arxiv.org/html/2405.11056v1)
- [GAPS: Garment Draping](https://arxiv.org/html/2312.01490v2)
- [uDraper](https://udraper.com/)

### AR / 실시간 합성

- [Snap Garment Transfer](https://ar.snap.com/blog/lens-studio-5.0.17)
- [Kivisense AR Try-On](https://tryon.kivisense.com/)
- [Shopify AR Try-On 가이드](https://www.shopify.com/blog/ar-try-on-clothes)

### 기타

- [3D Fashion Industry 과제 (Optitex)](https://3dinsider.optitex.com/3d-challenges-in-the-fashion-industry/)
- [FabricDiffusion](https://arxiv.org/html/2410.01801v1)
- [Meshy API Docs](https://docs.meshy.ai/en/api/rate-limits)

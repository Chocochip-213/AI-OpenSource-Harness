# Cloth Simulation 설계 문서 (우선순위 기반 계층화)

> **문서 버전**: 2.0
> **최종 갱신**: 2026-02-28
> **범위**: 웹 브라우저 의류 시뮬레이션 설계 (SkinnedMesh 본 바인딩 MVP + 확장 계층)

---

## 1. 개요

### 1.1 목표

웹 브라우저에서 실시간으로 의류의 물리적 거동(중력, 흔들림, 주름)을
시뮬레이션하여, 가상 시착의 몰입감을 극대화한다.

### 1.2 우선순위 계층화

```
┌─────────────────────────────────────────────────────────────┐
│                  우선순위 기반 Cloth Simulation                │
│                                                             │
│  P0 (MVP): SkinnedMesh 본 바인딩                             │
│    → Kalidokit 본 회전으로 의류 SkinnedMesh 변형              │
│    → VRM 아바타 본 구조에 의류 바인딩                          │
│    → 핏 타입(slim/regular/oversize)별 메쉬 자동 선택           │
│                                                             │
│  P1 (MVP 필수): Normal Map Animation                        │
│    → 관절 각도 기반 주름 노멀맵 블렌딩                         │
│    → 물리 연산 없이 시각적 디테일 보완                         │
│    → P0만으로는 Candy-Wrapper/주름 부재 등 품질 부족           │
│    → GPU 비용 < 0.5ms, 정면 뷰에서 사실감 대폭 향상           │
│                                                             │
│  P2: VAT 프리베이크                                          │
│    → Blender cloth sim → 텍스처 인코딩                       │
│    → 사전 정의 모션에 대한 고품질 변형                         │
│                                                             │
│  P3 (스코프 아웃): 런타임 물리                                │
│    → WebGPU XPBD 또는 WASM 기반 물리                         │
│    → 6주 6명 팀에서 구현 비현실적, 도전 과제로 분류            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 도전 과제

| 과제 | 설명 |
|------|------|
| 디바이스 다양성 | 데스크톱 GPU부터 저사양 모바일까지 커버 |
| 브라우저 API 파편화 | WebGPU(Chrome/Edge) vs WebGL(Firefox/Safari) |
| 실시간 제약 | 16.67ms(60fps) 프레임 버짓 내에서 렌더 + 트래킹 동시 |
| 인터랙션 | 포즈 변경에 따른 의류 반응 |

### 1.4 해결 전략

MVP에서는 SkinnedMesh 본 바인딩(P0) + Normal Map Animation(P1)을 함께 구현한다.
P0만으로는 LBS의 Candy-Wrapper 효과, 주름/접힘 부재, 드레이프 미표현 등
시각적 사실성이 부족하다 (EA DICE, Activision GDC 2019 "Wrinkling Normal Maps" 등
산업 레퍼런스에서 확인). P1은 GPU 비용 < 0.5ms로 정면 뷰에서 사실감을 대폭 향상시키므로
MVP 필수로 포함한다. VAT(P2)는 특정 모션 시퀀스에 대한 고품질 표현이 필요할 때 확장한다.
런타임 물리(P3)는 도전 과제로 분류한다.

---

## 2. P0: SkinnedMesh 본 바인딩 (MVP)

### 2.1 개요

VRM 아바타의 본 구조에 의류 glTF 메쉬를 바인딩하여,
아바타 포즈 변경 시 의류가 자동으로 따라가도록 한다.
런타임 물리 연산 없이 본 가중치(bone weight)만으로 의류 변형을 구현하므로,
모든 디바이스에서 안정적인 성능을 보장한다.

### 2.2 VRM 아바타 → 의류 바인딩

의류 메쉬는 VRM 아바타와 동일한 스켈레톤을 공유한다.
의류 glTF를 제작할 때 아바타 스켈레톤 기준으로 본 가중치를 설정하면,
런타임에는 스켈레톤 참조만 교체하면 된다.

```typescript
// VRM 아바타 본에 의류 SkinnedMesh 바인딩
function bindGarmentToAvatar(
  garmentMesh: THREE.SkinnedMesh,
  avatarSkeleton: THREE.Skeleton
): void {
  // 의류 메쉬의 본을 아바타 스켈레톤의 본으로 교체
  // ⚠️ bind()는 bindMatrix를 리셋하므로, 이미 바인딩된 메쉬에는
  // garmentMesh.skeleton = avatarSkeleton 으로 스켈레톤만 교체하는 것이 안전하다.
  // bind()를 다시 호출하면 의도치 않은 변환이 발생할 수 있다.
  garmentMesh.skeleton = avatarSkeleton;
  garmentMesh.bind(avatarSkeleton);
}
```

### 2.2b VRM 아바타-의류 본 매핑 가이드

의류 glTF의 본 이름은 VRM Humanoid 본 이름과 일치해야 한다:

| VRM Humanoid 본 | Blender 리깅 시 본 이름 | 용도 |
|----------------|----------------------|------|
| hips | hips | 전체 위치/회전 루트 |
| spine | spine | 상체 기울기 |
| chest | chest | 상의 상단 |
| upperArm_L/R | upper_arm.L/R | 소매 상단 |
| lowerArm_L/R | lower_arm.L/R | 소매 하단 |
| upperLeg_L/R | upper_leg.L/R | 하의 상단 |
| lowerLeg_L/R | lower_leg.L/R | 하의 하단 |

Blender에서 의류를 리깅할 때, VRM 아바타의 아마처를 직접 임포트하여
동일한 본 이름/계층 구조를 공유하도록 한다.

### 2.3 본 가중치 전이 (Bone Weight Transfer)

의류 메쉬에 본 가중치를 부여하는 두 가지 방법:

**방법 1: 오프라인 가중치 전이 (권장)**
- Blender에서 아바타 메쉬 → 의류 메쉬로 "Transfer Weights" 수행
- 의류 glTF에 가중치가 포함된 상태로 내보내기
- 런타임 비용 제로

**방법 2: 런타임 가중치 계산**
- 의류 버텍스에서 가장 가까운 아바타 버텍스의 가중치를 복사
- 초기 로드 시 1회만 수행
- 범용성은 높으나 로드 시간 증가

```typescript
interface GarmentAsset {
  mesh: THREE.SkinnedMesh;      // 본 가중치 포함 의류 메쉬
  pinBones: string[];           // 고정 본 (어깨, 허리 등)
  garmentType: 'top' | 'bottom' | 'dress' | 'outer' | 'accessory'; // 치마는 bottom에 포함
}

// 의류 로드 및 아바타 바인딩
async function loadAndBindGarment(
  garmentUrl: string,
  vrm: VRM
): Promise<GarmentAsset> {
  const gltf = await loader.loadAsync(garmentUrl);
  const garmentMesh = gltf.scene.children[0] as THREE.SkinnedMesh;

  // 아바타 스켈레톤에 바인딩
  const avatarSkeleton = vrm.scene.getObjectByProperty(
    'type', 'SkinnedMesh'
  ) as THREE.SkinnedMesh;

  bindGarmentToAvatar(garmentMesh, avatarSkeleton.skeleton);

  // 씬에 추가
  vrm.scene.add(garmentMesh);

  return {
    mesh: garmentMesh,
    pinBones: gltf.userData.pinBones ?? [],
    garmentType: gltf.userData.garmentType ?? 'top',
  };
}
```

### 2.4 의류 타입별 고정 본

| 의류 타입 | 고정 본 | 자유 영역 |
|----------|---------|----------|
| 상의/top (T셔츠) | leftShoulder, rightShoulder, neck | 소매 끝단, 밑단 |
| 아우터/outer (재킷) | leftShoulder, rightShoulder, neck, chest | 소매, 라펠, 밑단 |
| 하의/bottom (바지) | hips | 바지 끝단 |
| 하의/bottom (치마) | hips | 전체 치맛단 |
| 원피스/dress | leftShoulder, rightShoulder, spine | 치맛단 |

### 2.5 한계 및 보완

- **Candy-Wrapper 효과**: LBS(Linear Blend Skinning)가 관절 회전 시 중간 메쉬를 과도 수축 (팔꿈치/무릎 굽힘 시 소매가 비정상적으로 납작해짐) → P1 Normal Map으로 시각적 보완
- **주름/접힘 부재**: 정적 토폴로지만 변환하므로 새 주름 생성 불가 → P1 Normal Map 필수
- **드레이프 미표현**: 중력에 의한 처짐/흔들림 표현 불가 → P1 Normal Map으로 시각적 보완
- **관통 문제**: 빠른 포즈 변경 시 의류가 바디를 관통할 수 있음 → Rapier.js 충돌 감지로 보완
- **소재별 차이 없음**: 면/실크/데님 등 재질 차이 표현 불가 → P1 Normal Map + 텍스처로 보완

### 2.6 핏 타입별 메쉬 선택 및 시뮬레이션 파라미터

> **MVP 스코프 조정**: MVP에서는 regular 핏만 제작한다.
> slim/oversize는 런타임에서 본 스케일링으로 근사하며, 후속에서 별도 메쉬로 교체한다.

#### 핏 타입별 메쉬 선택 로직

사용자의 핏 평가 결과에 따라 적절한 핏 타입 메쉬를 자동 선택하여 로드한다.

```typescript
type FitType = 'slim' | 'regular' | 'oversize';

interface FitTypeMeshConfig {
  fitType: FitType;
  meshSuffix: string;        // GLB 파일 접미사
  boneInfluenceRadius: number; // 본 영향 반경 (높을수록 부드러운 변형)
  collisionMargin: number;    // 충돌 마진 (높을수록 바디와 간격 넓음)
  normalMapIntensity: number; // 노멀맵 강도 (0~1)
}

const FIT_TYPE_CONFIGS: Record<FitType, FitTypeMeshConfig> = {
  slim: {
    fitType: 'slim',
    meshSuffix: '_slim',
    boneInfluenceRadius: 0.8,   // 타이트: 본 영향 반경 작음, 밀착 변형
    collisionMargin: 0.002,     // 최소 마진: 바디에 밀착
    normalMapIntensity: 0.9,    // 강한 주름: 밀착 시 주름 강조
  },
  regular: {
    fitType: 'regular',
    meshSuffix: '_regular',
    boneInfluenceRadius: 1.0,   // 표준: 기본 본 영향 반경
    collisionMargin: 0.005,     // 표준 마진
    normalMapIntensity: 0.6,    // 중간 주름
  },
  oversize: {
    fitType: 'oversize',
    meshSuffix: '_oversize',
    boneInfluenceRadius: 1.3,   // 넉넉: 본 영향 반경 넓음, 부드러운 변형
    collisionMargin: 0.01,      // 넓은 마진: 바디와 간격 유지
    normalMapIntensity: 0.3,    // 약한 주름: 오버사이즈는 주름 적음
  },
};

async function loadFitTypeMesh(
  garmentVariant: { model_url: string; fit_type: FitType },
  vrm: VRM
): Promise<GarmentAsset> {
  const config = FIT_TYPE_CONFIGS[garmentVariant.fit_type];
  const meshUrl = garmentVariant.model_url;

  const gltf = await loader.loadAsync(meshUrl);
  const garmentMesh = gltf.scene.children[0] as THREE.SkinnedMesh;

  // 아바타 스켈레톤에 바인딩
  bindGarmentToAvatar(garmentMesh, getAvatarSkeleton(vrm));

  return {
    mesh: garmentMesh,
    config,
    pinBones: gltf.userData.pinBones ?? [],
    garmentType: gltf.userData.garmentType ?? 'top',
  };
}
```

#### 핏 타입별 본 가중치 차이

| 핏 타입 | 본 영향 반경 | 효과 | 시각적 특징 |
|---------|------------|------|-----------|
| `slim` | 0.8 (좁음) | 본 회전에 타이트하게 추종 | 몸에 밀착, 주름 많음 |
| `regular` | 1.0 (표준) | 기본 추종 | 적당한 여유, 자연스러운 실루엣 |
| `oversize` | 1.3 (넓음) | 본 회전에 느슨하게 추종 | 넉넉한 실루엣, 부드러운 움직임 |

#### 핏 타입별 충돌 마진

| 핏 타입 | 충돌 마진 | Rapier.js 충돌체 | 설명 |
|---------|----------|-----------------|------|
| `slim` | 0.002m | 바디 표면에 밀착 | 최소 간격, 관통 감지 민감 |
| `regular` | 0.005m | 약간 간격 | 표준 간격, 자연스러운 핏 |
| `oversize` | 0.01m | 넓은 간격 | 바디와 충분한 공간, 넉넉한 핏 표현 |

---

## 3. 런타임 물리 시뮬레이션

> **P3 도전 과제 -- MVP 범위 밖**
>
> 6주 6명 팀에서 WebGPU XPBD 구현은 현실적으로 어려움.
> MVP에서는 SkinnedMesh(P0) + Normal Map(P1)으로 충분한 시착 경험을 제공한다.
> 아래 내용은 향후 확장 시 참고 자료로 보존한다.

### 3.1 Tier 1: WebGPU Compute Shader XPBD

#### 3.1.1 알고리즘 개요

XPBD(Extended Position-Based Dynamics)는 위치 기반 물리 시뮬레이션의 확장판으로,
compliance 파라미터를 통해 재질 특성을 정밀하게 제어한다.

```
매 프레임 물리 스텝:

1. 외력 적용 (중력, 바람)
   │  v_i = v_i + dt * f_ext / m_i
   │  x_pred = x_i + dt * v_i
   │
2. 충돌 감지 (바디 SDF)
   │  SDF(x_pred) < 0 → 충돌 후보
   │
3. XPBD 솔버 반복 (서브스텝 × 반복)
   │  for each substep:
   │    for each constraint:
   │      Δx = solve_constraint(x, λ, α)
   │      x_pred += Δx
   │
4. 속도 업데이트
   │  v_i = (x_pred - x_i) / dt
   │
5. 위치 확정
      x_i = x_pred
```

#### 3.1.2 제약 조건 (Constraints)

| 제약 | 설명 | compliance (α) | 역할 |
|------|------|----------------|------|
| Distance | 인접 파티클 간 거리 유지 | 1e-8 ~ 1e-6 | 천 늘어남 방지 |
| Bending | 삼각형 쌍의 이면각 유지 | 1e-6 ~ 1e-3 | 주름/구김 강성 |
| Pin | 고정점을 본 위치에 부착 | 0 (무한 강성) | 어깨/허리 고정 |

#### 3.1.3 고정 핀 정의

의류 메쉬의 특정 버텍스를 바디 본에 부착(pin)하여 의류가 떨어지지 않게 한다.

| 의류 타입 | 고정 핀 위치 | 부착 본 |
|----------|------------|---------|
| 상의/top (T셔츠) | 양쪽 어깨 꼭대기, 목둘레 | LeftShoulder, RightShoulder, Neck |
| 아우터/outer (재킷) | 양쪽 어깨, 목둘레, 가슴 중앙 | LeftShoulder, RightShoulder, Neck, Chest |
| 하의/bottom (바지) | 허리 둘레 전체 | Hips |
| 하의/bottom (치마) | 허리 둘레 전체 | Hips |
| 원피스/dress | 양쪽 어깨 + 허리 | LeftShoulder, RightShoulder, Spine |

**자유 노드 (물리 시뮬레이션 대상)**:
- 치맛단, 소매 끝단, 후드, 칼라, 리본
- 고정 핀에서 멀수록 자유도 높음

#### 3.1.4 바디 충돌 (SDF 기반)

```
바디 SDF = union(타원체 10개)

타원체 매핑:
  머리      → 구 (키포인트 0 중심)
  몸통 상부 → 타원체 (키포인트 11-12-23-24)
  몸통 하부 → 타원체 (키포인트 23-24)
  왼팔 상부 → 캡슐 (키포인트 11-13)
  왼팔 하부 → 캡슐 (키포인트 13-15)
  오른팔 상부 → 캡슐 (키포인트 12-14)
  오른팔 하부 → 캡슐 (키포인트 14-16)
  왼다리    → 캡슐 (키포인트 23-25-27)
  오른다리  → 캡슐 (키포인트 24-26-28)
  힙       → 타원체 (키포인트 23-24 중심)
```

충돌 해소:
```typescript
function resolveCollision(
  particlePos: vec3,
  bodySDF: (p: vec3) => number
): vec3 {
  const distance = bodySDF(particlePos);

  if (distance < 0) {
    // SDF 그래디언트 = 표면 법선
    const normal = sdfGradient(bodySDF, particlePos);
    // 표면 바깥으로 밀어냄
    return vec3.add(particlePos, vec3.scale(normal, -distance + 0.001));
  }

  return particlePos;
}
```

#### 3.1.5 WebGPU Compute Shader 구조

```wgsl
// XPBD 솔버 compute shader (WGSL)

@group(0) @binding(0) var<storage, read_write> positions: array<vec4f>;
@group(0) @binding(1) var<storage, read_write> velocities: array<vec4f>;
@group(0) @binding(2) var<storage, read> constraints: array<Constraint>;
@group(0) @binding(3) var<storage, read_write> lambdas: array<f32>;
@group(0) @binding(4) var<uniform> params: SimParams;

struct SimParams {
  dt: f32,
  gravity: vec3f,
  num_substeps: u32,
  num_iterations: u32,
}

struct Constraint {
  type: u32,        // 0=distance, 1=bending, 2=pin
  idx_a: u32,
  idx_b: u32,
  rest_value: f32,
  compliance: f32,
}

@compute @workgroup_size(256)
fn predict_positions(@builtin(global_invocation_id) id: vec3u) {
  let i = id.x;
  if (i >= arrayLength(&positions)) { return; }

  // 외력 적용
  velocities[i] += vec4f(params.gravity * params.dt, 0.0);
  positions[i] += velocities[i] * params.dt;
}

@compute @workgroup_size(256)
fn solve_distance_constraints(@builtin(global_invocation_id) id: vec3u) {
  let c = id.x;
  if (c >= arrayLength(&constraints)) { return; }

  let constraint = constraints[c];
  if (constraint.type != 0u) { return; }

  let a = constraint.idx_a;
  let b = constraint.idx_b;
  let diff = positions[b].xyz - positions[a].xyz;
  let dist = length(diff);
  let rest = constraint.rest_value;

  // XPBD 보정
  let alpha_tilde = constraint.compliance / (params.dt * params.dt);
  let delta_lambda = (dist - rest - alpha_tilde * lambdas[c]) /
                     (1.0 + 1.0 + alpha_tilde);

  let correction = normalize(diff) * delta_lambda * 0.5;

  // 원자적 업데이트 (실제로는 Jacobi 스타일로 분리 필요)
  positions[a] += vec4f(correction, 0.0);
  positions[b] -= vec4f(correction, 0.0);
  lambdas[c] += delta_lambda;
}
```

#### 3.1.6 시뮬레이션 파라미터

| 파라미터 | 값 | 설명 |
|---------|-----|------|
| 타임스텝 (dt) | 1/60초 | 60fps 기준 |
| 서브스텝 | 4회 | dt를 4분할하여 안정성 확보 |
| 솔버 반복 | 10회 | 서브스텝당 제약 반복 횟수 |
| 중력 | (0, -9.81, 0) m/s^2 | 기본 중력 |
| 댐핑 | 0.99 | 속도 감쇠 (에너지 소산) |

#### 3.1.7 재질 프리셋

| 재질 | Distance α | Bending α | 파티클 질량 | 특성 |
|------|-----------|-----------|-----------|------|
| 면 (Cotton) | 1e-8 | 1e-5 | 0.3 kg/m^2 | 중간 강성, 자연스러운 주름 |
| 실크 (Silk) | 1e-7 | 1e-3 | 0.1 kg/m^2 | 유연, 흐르는 느낌 |
| 데님 (Denim) | 1e-9 | 1e-7 | 0.5 kg/m^2 | 높은 강성, 적은 주름 |
| 니트 (Knit) | 1e-6 | 1e-4 | 0.2 kg/m^2 | 신축성, 부드러운 주름 |
| 가죽 (Leather) | 1e-9 | 1e-8 | 0.6 kg/m^2 | 매우 높은 강성 |
| 시폰 (Chiffon) | 1e-6 | 1e-2 | 0.05 kg/m^2 | 매우 유연, 투명 |

---

### 3.2 Rapier.js 충돌 감지 (물리 보조)

#### 3.2.1 개요

Rapier.js는 SoftBody를 지원하지 않으므로 cloth sim 자체에는 사용할 수 없다.
대신 **충돌 감지(의류-바디 관통 방지)** 와 **강체 물리(액세서리)**에 활용한다.

SkinnedMesh 본 바인딩(P0)에서 빠른 포즈 변경 시 발생할 수 있는
의류-바디 관통 문제를 Rapier.js 충돌 감지로 보완한다.

```typescript
import { RigidBody, CuboidCollider } from '@react-three/rapier';

// 바디 충돌체 설정 (아바타 본 위치 기반)
function createBodyColliders(vrm: VRM): ColliderConfig[] {
  return [
    { bone: 'chest', shape: 'cuboid', halfExtents: [0.15, 0.2, 0.1] },
    { bone: 'hips', shape: 'cuboid', halfExtents: [0.15, 0.1, 0.1] },
    { bone: 'leftUpperArm', shape: 'capsule', halfHeight: 0.12, radius: 0.04 },
    { bone: 'rightUpperArm', shape: 'capsule', halfHeight: 0.12, radius: 0.04 },
    // ... 필요한 본에 충돌체 추가
  ];
}
```

#### 핏 타입별 충돌 파라미터 적용

```typescript
function applyFitTypeCollisionParams(
  colliders: ColliderConfig[],
  fitType: FitType
): ColliderConfig[] {
  const config = FIT_TYPE_CONFIGS[fitType];

  return colliders.map(collider => ({
    ...collider,
    // 핏 타입에 따라 충돌체 크기 조정
    halfExtents: collider.halfExtents
      ? collider.halfExtents.map(e => e + config.collisionMargin) as [number, number, number]
      : undefined,
    radius: collider.radius
      ? collider.radius + config.collisionMargin
      : undefined,
  }));
}
```

#### 3.2.2 Ammo.js btSoftBody (P3 참고용)

> **P3 참고 자료** -- 아래 코드는 런타임 물리(P3) 구현 시 참고용으로 보존한다.
> Ammo.js는 SoftBody를 지원하지만, 무거운 WASM 번들(1MB+)과
> TypeScript 타입 미흡 등의 DX 문제로 채택하지 않았다.

```typescript
import Ammo from 'ammo.js';

function createClothSoftBody(
  meshVertices: Float32Array,
  meshIndices: Uint32Array,
  pinVertices: number[]
): Ammo.btSoftBody {
  const softBodyHelper = new Ammo.btSoftBodyHelpers();
  const worldInfo = physicsWorld.getWorldInfo();

  // 메쉬에서 소프트 바디 생성
  const softBody = softBodyHelper.CreateFromTriMesh(
    worldInfo,
    meshVertices,
    meshIndices,
    meshIndices.length / 3,
    true  // 랜덤 인덱스
  );

  // 재질 설정
  const sbConfig = softBody.get_m_cfg();
  sbConfig.set_viterations(10);     // 속도 솔버 반복
  sbConfig.set_piterations(10);     // 위치 솔버 반복
  sbConfig.set_kDF(0.5);           // 동적 마찰
  sbConfig.set_kDP(0.01);          // 댐핑
  sbConfig.set_kCHR(1.0);         // 강체 충돌 경도

  // 고정 핀 설정
  for (const vertexIdx of pinVertices) {
    softBody.appendAnchor(vertexIdx, rigidBody, false, 1.0);
  }

  // 질량 설정
  softBody.setTotalMass(0.3, false);

  return softBody;
}
```

---

## 4. P2: VAT 프리베이크 (Vertex Animation Texture)

### 4.1 개요

VAT는 사전에 Blender 등에서 물리 시뮬레이션을 수행하고,
프레임별 버텍스 위치를 텍스처로 인코딩하는 기법이다.
런타임에는 vertex shader에서 텍스처를 샘플링하여 버텍스를 변위시킨다.

```
┌──────────────────────────────────────────────┐
│              오프라인 제작 (Blender)           │
│                                              │
│  1. 바디 + 의류 메쉬 설정                     │
│  2. 모션 시퀀스 재생 (걷기, 팔 올리기 등)     │
│  3. Cloth Simulation 실행                    │
│  4. 프레임별 버텍스 위치 → 텍스처 인코딩       │
│  5. glTF + VAT 확장으로 내보내기              │
│                                              │
└──────────────────────────────┬───────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────┐
│              런타임 (브라우저)                 │
│                                              │
│  1. glTF + VAT 텍스처 로드                    │
│  2. 현재 포즈 → 가장 가까운 모션 프레임 선택  │
│  3. Vertex shader에서 텍스처 샘플링           │
│  4. 버텍스 위치 변위                          │
│                                              │
└──────────────────────────────────────────────┘
```

### 4.2 제작 공정

#### 4.2.1 모션 시퀀스 정의

| 시퀀스 ID | 동작 | 프레임 수 | 루프 | 설명 |
|----------|------|----------|------|------|
| idle | 정면 서기 | 60 | O | 기본 대기 |
| walk | 걷기 | 120 | O | 좌우 팔 흔들림 |
| turn_left | 왼쪽 회전 | 60 | X | 90도 회전 |
| turn_right | 오른쪽 회전 | 60 | X | 90도 회전 |
| arm_raise | 양팔 올리기 | 90 | X | T-포즈까지 |
| squat | 스쿼트 | 90 | X | 하체 굽힘 |

#### 4.2.2 텍스처 인코딩

```
VAT 텍스처 레이아웃:
  - 너비: 버텍스 수 (최대 4096)
  - 높이: 프레임 수 (최대 4096)
  - 채널: RGBA (x, y, z, 예비)
  - 포맷: RGBA16F (half-float, 정밀도 + 크기 균형)

텍스처 좌표:
  u = vertex_index / num_vertices
  v = frame_index / num_frames

인코딩:
  texel.rgb = vertex_position - rest_position  (변위 벡터)
  texel.a = 예비 (노멀 z 성분 또는 메타데이터)
```

#### 4.2.3 Blender 내보내기 스크립트

```python
# Blender Python 스크립트 (개요)
import bpy
import numpy as np

def export_vat(cloth_obj, frame_start, frame_end, output_path):
    """의류 오브젝트의 VAT 텍스처를 생성한다."""
    mesh = cloth_obj.data
    num_verts = len(mesh.vertices)
    num_frames = frame_end - frame_start + 1

    # 기본 포즈 (frame 0) 의 버텍스 위치
    bpy.context.scene.frame_set(frame_start)
    rest_positions = np.array([v.co for v in mesh.vertices])

    # 프레임별 변위 수집
    displacements = np.zeros((num_frames, num_verts, 4), dtype=np.float16)

    for f in range(num_frames):
        bpy.context.scene.frame_set(frame_start + f)
        # 평가된 메쉬에서 버텍스 위치 추출
        depsgraph = bpy.context.evaluated_depsgraph_get()
        eval_obj = cloth_obj.evaluated_get(depsgraph)
        eval_mesh = eval_obj.data

        for v_idx, vert in enumerate(eval_mesh.vertices):
            disp = np.array(vert.co) - rest_positions[v_idx]
            displacements[f, v_idx, :3] = disp

    # 텍스처로 저장 (OpenEXR 또는 PNG16)
    save_vat_texture(displacements, output_path)
```

#### 4.2.4 런타임 Vertex Shader

```glsl
// VAT vertex shader (GLSL ES 3.0)

uniform sampler2D vatTexture;    // VAT 텍스처
uniform float numVertices;       // 총 버텍스 수
uniform float numFrames;         // 총 프레임 수
uniform float currentFrame;      // 현재 프레임 (0 ~ numFrames-1)

attribute float vertexIndex;     // 버텍스 인덱스 (0 ~ numVertices-1)

void main() {
  // VAT 텍스처에서 변위 샘플링
  float u = (vertexIndex + 0.5) / numVertices;
  float v = (currentFrame + 0.5) / numFrames;

  vec4 displacement = texture2D(vatTexture, vec2(u, v));

  // 원본 위치 + 변위 = 최종 위치
  vec3 animatedPosition = position + displacement.xyz;

  gl_Position = projectionMatrix * modelViewMatrix * vec4(animatedPosition, 1.0);
}
```

### 4.3 장단점 분석

| 항목 | 장점 | 단점 |
|------|------|------|
| 성능 | 물리 연산 제로, GPU 텍스처 샘플링만 | - |
| 품질 | Blender의 고품질 cloth sim 결과 그대로 | 사전 정의된 동작만 재현 |
| 인터랙션 | - | 실시간 포즈 반응 불가 |
| 용량 | - | 텍스처 추가 (모션당 2~10MB) |
| 제작 비용 | - | 모션별 별도 베이킹 필요 |

### 4.4 포즈→VAT 프레임 매핑

런타임에서 사용자 포즈와 가장 유사한 VAT 프레임을 선택한다.

```typescript
interface VATSequence {
  id: string;
  frames: number;
  loop: boolean;
  poseKeyframes: PoseSnapshot[];  // 각 프레임의 포즈 정보
}

function selectVATFrame(
  currentPose: PoseRigResult,
  sequences: VATSequence[]
): { sequenceId: string; frame: number; blend: number } {
  let bestMatch = { sequenceId: '', frame: 0, distance: Infinity, blend: 0 };

  for (const seq of sequences) {
    for (let f = 0; f < seq.frames; f++) {
      const dist = poseSimilarity(currentPose, seq.poseKeyframes[f]);
      if (dist < bestMatch.distance) {
        bestMatch = { sequenceId: seq.id, frame: f, distance: dist, blend: 0 };
      }
    }
  }

  // 인접 프레임 간 보간 (부드러운 전환)
  const nextFrame = (bestMatch.frame + 1) % sequences.find(
    s => s.id === bestMatch.sequenceId
  )!.frames;
  bestMatch.blend = calculateBlendFactor(currentPose, bestMatch);

  return bestMatch;
}
```

---

## 5. P1: Normal Map Animation

### 5.1 개요

물리 시뮬레이션 없이 관절 각도에 따른 주름을 표현하기 위해,
프리셋 노멀맵을 블렌딩하는 방식이다.
물리 연산 비용 제로로 시각적 품질을 향상시킨다.

### 5.2 관절 각도→주름 매핑

```
관절 각도 범위 → 노멀맵 세트

팔꿈치 (0°~150°):
  0°~30°   → 노멀맵 A (주름 없음, 펴진 소매)
  30°~90°  → 노멀맵 A→B 블렌딩 (약한 주름)
  90°~150° → 노멀맵 B→C 블렌딩 (강한 주름)

무릎 (0°~120°):
  0°~20°   → 노멀맵 A (펴진 바지)
  20°~70°  → 노멀맵 A→B 블렌딩
  70°~120° → 노멀맵 B→C 블렌딩

허리 굽힘 (0°~90°):
  0°~30°   → 노멀맵 A (펴진 상태)
  30°~60°  → 노멀맵 A→B 블렌딩
  60°~90°  → 노멀맵 B (최대 주름)
```

### 5.3 노멀맵 프리셋 세트

의류 타입별로 2~4장의 노멀맵 프리셋을 준비한다.

| 의류 타입 | 노멀맵 수 | 변화 영역 | 설명 |
|----------|----------|----------|------|
| T셔츠 | 3장 | 소매(팔꿈치), 앞판(허리) | 팔꿈치 굽힘, 허리 굽힘 주름 |
| 셔츠 | 4장 | 소매, 앞판, 등판 | 칼라 포함, 더 정밀한 주름 |
| 바지 | 3장 | 무릎, 허벅지, 엉덩이 | 무릎 굽힘 주름 |
| 치마 | 2장 | 전체 | 정적(서기)/동적(걷기) |
| 재킷 | 4장 | 소매, 앞판, 등판, 라펠 | 가장 복잡한 주름 패턴 |

### 5.3b 핏 타입별 노멀맵 강도

핏 타입에 따라 노멀맵 블렌딩 강도를 조정한다. 슬림핏은 주름이 강하고, 오버핏은 주름이 약하다.

| 핏 타입 | 노멀맵 강도 | 근거 |
|---------|-----------|------|
| `slim` | 0.9 (강함) | 몸에 밀착되어 관절 주름이 선명하게 드러남 |
| `regular` | 0.6 (중간) | 적당한 여유량으로 자연스러운 주름 |
| `oversize` | 0.3 (약함) | 넉넉한 여유로 주름이 거의 없음, 부드러운 표면 |

```typescript
function getAdjustedWrinkleBlend(
  elbowAngle: number,
  fitType: FitType
): { blendFactorAB: number; blendFactorBC: number } {
  const intensity = FIT_TYPE_CONFIGS[fitType].normalMapIntensity;

  let blendFactorAB = 0;
  let blendFactorBC = 0;

  if (elbowAngle < 30) {
    blendFactorAB = 0;
    blendFactorBC = 0;
  } else if (elbowAngle < 90) {
    blendFactorAB = ((elbowAngle - 30) / 60) * intensity;
    blendFactorBC = 0;
  } else {
    blendFactorAB = intensity;
    blendFactorBC = Math.min(((elbowAngle - 90) / 60) * intensity, intensity);
  }

  return { blendFactorAB, blendFactorBC };
}
```

### 5.4 런타임 블렌딩

```typescript
// Three.js ShaderMaterial에서 노멀맵 블렌딩

const wrinkleShader = {
  uniforms: {
    normalMapA: { value: normalTexA },  // 주름 없음
    normalMapB: { value: normalTexB },  // 약한 주름
    normalMapC: { value: normalTexC },  // 강한 주름
    blendFactorAB: { value: 0.0 },     // A↔B 블렌딩 (0~1)
    blendFactorBC: { value: 0.0 },     // B↔C 블렌딩 (0~1)
  },

  fragmentShader: `
    uniform sampler2D normalMapA;
    uniform sampler2D normalMapB;
    uniform sampler2D normalMapC;
    uniform float blendFactorAB;
    uniform float blendFactorBC;

    varying vec2 vUv;

    void main() {
      vec3 normalA = texture2D(normalMapA, vUv).xyz * 2.0 - 1.0;
      vec3 normalB = texture2D(normalMapB, vUv).xyz * 2.0 - 1.0;
      vec3 normalC = texture2D(normalMapC, vUv).xyz * 2.0 - 1.0;

      // 2단계 블렌딩
      vec3 blendedAB = mix(normalA, normalB, blendFactorAB);
      vec3 finalNormal = mix(blendedAB, normalC, blendFactorBC);

      // 참고: WebGL 2.0 (GLSL ES 3.0)에서는 gl_FragColor 대신 out 변수 사용이 표준이나,
      // Three.js ShaderMaterial이 내부적으로 변환 처리하므로 현재 코드로 동작한다.
      gl_FragColor = vec4(normalize(finalNormal) * 0.5 + 0.5, 1.0);
    }
  `,
};

// 관절 각도에 따라 블렌드 팩터 업데이트
function updateWrinkleBlend(elbowAngle: number): void {
  if (elbowAngle < 30) {
    material.uniforms.blendFactorAB.value = 0;
    material.uniforms.blendFactorBC.value = 0;
  } else if (elbowAngle < 90) {
    material.uniforms.blendFactorAB.value = (elbowAngle - 30) / 60;
    material.uniforms.blendFactorBC.value = 0;
  } else {
    material.uniforms.blendFactorAB.value = 1;
    material.uniforms.blendFactorBC.value = Math.min((elbowAngle - 90) / 60, 1);
  }
}
```

### 5.5 Normal Map + SkinnedMesh 결합

P0(SkinnedMesh 본 바인딩)과 P1(Normal Map Animation)을 결합하면
큰 동작은 본 바인딩으로, 미세한 주름은 노멀맵으로 표현하여 최적의 품질을 달성한다.

```
SkinnedMesh 본 바인딩 (거시적 동작)     Normal Map (미시적 주름)
  │ 본 회전에 의한 메쉬 변형              │ 표면 디테일
  │ 포즈 추종                            │ 관절 주름, 접힘
  │                                      │
  └──────────────┬───────────────────────┘
                 │
                 ▼
          최종 렌더링 출력
  (본 바인딩 메쉬 + 주름 노멀맵)
```

---

## 6. 품질 모드 선택

### 6.1 기능 감지 플로우

MVP에서는 SkinnedMesh(P0) + Normal Map(P1)이 기본이다. P1은 MVP 필수이며,
저사양 디바이스에서만 P0 only로 폴백한다.

```
시작
  │
  ▼
WebGL 2.0 지원?  ──(예)──▶  GPU Tier ≥ 2?  ──(예)──▶  P0 + P1: SkinnedMesh + NormalMap (MVP 기본)
  │                            │
  (아니오)                     (아니오)
  │                            │
  ▼                            ▼
P0 only:                    P0 only:
SkinnedMesh만              SkinnedMesh만
(저사양 폴백)              (저사양 폴백)
```

### 6.2 구현

```typescript
type ClothMode = 'skinned-normalmap' | 'skinned-only';

function detectClothMode(): ClothMode {
  // WebGL 2.0 + GPU 성능 확인
  const canvas = document.createElement('canvas');
  const gl = canvas.getContext('webgl2');
  if (gl) {
    const gpuTier = estimateGPUTier(gl);
    if (gpuTier >= 2) {
      return 'skinned-normalmap';  // P0 + P1
    }
  }

  return 'skinned-only';  // P0만
}

function estimateGPUTier(gl: WebGL2RenderingContext): number {
  // GPU 성능 추정 (0~4)
  // TODO: 프로덕션에서는 detect-gpu 라이브러리(https://github.com/TimvanScherpenzeel/detect-gpu) 사용 권장
  // 정규식 기반 판별은 GPU 모델명 패턴 변화에 취약하다
  const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
  if (!debugInfo) return 1;

  const renderer = gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL);

  // 알려진 GPU 등급 매핑
  if (/RTX|RX\s?[567]/i.test(renderer)) return 4;  // 고성능 데스크톱
  if (/GTX|RX\s?[34]/i.test(renderer)) return 3;   // 중간 데스크톱
  if (/Intel.*Iris|Adreno\s?[67]/i.test(renderer)) return 2;  // iGPU/모바일 고성능
  if (/Intel.*UHD|Adreno\s?[45]|Mali/i.test(renderer)) return 1;  // 저성능

  return 1;  // 알 수 없음 → 보수적
}
```

### 6.3 사용자 수동 전환

자동 선택 외에 사용자가 직접 품질을 전환할 수 있는 UI를 제공한다.

```typescript
interface ClothQualityOption {
  mode: ClothMode;
  label: string;
  description: string;
  available: boolean;
}

const qualityOptions: ClothQualityOption[] = [
  {
    mode: 'skinned-normalmap',
    label: '표준 품질',
    description: 'SkinnedMesh + Normal Map (주름 표현)',
    available: hasWebGL2,
  },
  {
    mode: 'skinned-only',
    label: '경량 모드',
    description: 'SkinnedMesh만 (노멀맵 생략)',
    available: true,  // 항상 가능
  },
];
```

---

## 6b. 핏 평가 오버레이 렌더링

### 6b.1 UI 구성

핏 평가 결과를 3D 씬 위에 오버레이하여 사용자에게 실시간 피드백을 제공한다.

```
┌──────────────────────────────────────────────────────────┐
│  ┌─────────────────┐                                     │
│  │ 핏 평가 사이드바 │     [3D 시착 씬]                    │
│  │                 │                                     │
│  │ 핏 타입: 레귤러핏│                                     │
│  │ 적합도: 87%     │                                     │
│  │ 정확도: 92%     │                                     │
│  │                 │                                     │
│  │ ▼ 상세 보기     │                                     │
│  │ ┌─────────────┐ │                                     │
│  │ │ 어깨 +2.8cm │ │                                     │
│  │ │ 가슴 +3.5cm │ │                                     │
│  │ │ 허리 -0.3cm │ │                                     │
│  │ │ 힙   +4.2cm │ │                                     │
│  │ └─────────────┘ │                                     │
│  └─────────────────┘                                     │
└──────────────────────────────────────────────────────────┘
```

### 6b.2 시각 디자인

| 요소 | 스타일 | 설명 |
|------|--------|------|
| 사이드바 배경 | 반투명 (rgba(0,0,0,0.7)) | 3D 씬 위 오버레이, 씬 가리지 않음 |
| 핏 타입 뱃지 | 슬림핏=파란, 레귤러핏=초록, 오버핏=주황 | 색상으로 핏 구분 |
| 적합도 게이지 | 0~100% 프로그레스 바 | 직관적 적합도 표시 |
| 정확도 표시 | 소수점 1자리 | 상한 99% 명시 |
| 치수 차이 | 양수=초록(여유), 음수=빨강(타이트) | 색상으로 여유/타이트 구분 |

### 6b.3 업데이트 주기

| 항목 | 주기 | 설명 |
|------|------|------|
| 핏 타입 분류 | 1초 | 신체 재측정 결과 반영 |
| 적합도/정확도 | 1초 | 측정 갱신에 연동 |
| 상세 치수 차이 | 1초 | 각 항목별 갱신 |
| 시각 애니메이션 | 60fps | 게이지/뱃지 트랜지션 |

```typescript
interface FitOverlayProps {
  fitType: FitType;
  suitabilityPct: number;
  accuracyPct: number;
  details: {
    shoulder: { diffCm: number; fit: FitType };
    chest: { diffCm: number; fit: FitType };
    waist: { diffCm: number; fit: FitType };
    hip: { diffCm: number; fit: FitType };
  };
  isExpanded: boolean;
  onToggleExpand: () => void;
}

// 핏 타입별 뱃지 색상
const FIT_TYPE_COLORS: Record<FitType, string> = {
  slim: '#3B82F6',     // 파란색
  regular: '#10B981',  // 초록색
  oversize: '#F59E0B', // 주황색
};
```

---

## 7. 성능 목표 및 최적화

### 7.1 성능 목표

| 모드 | 타겟 FPS | 프레임 버짓 | GPU 메모리 | 비고 |
|------|---------|-----------|-----------|------|
| SkinnedMesh + NormalMap (P0+P1) | 60fps | < 3ms | ~20MB | MVP 기본 |
| SkinnedMesh only (P0) | 60fps | < 1ms | ~10MB | 저사양 폴백 |
| + VAT (P2) | 60fps | ~0ms (텍스처 샘플링) | ~30MB | 확장 |

### 7.2 최적화 전략

#### 메쉬 LOD (Level of Detail)

```
카메라 거리에 따른 메쉬 LOD:

거리 < 1m  → LOD 0: 원본 메쉬 (5,000 버텍스)
거리 1~2m  → LOD 1: 간소화 (3,000 버텍스)
거리 2~3m  → LOD 2: 간소화 (1,500 버텍스)
거리 > 3m  → LOD 3: 최소 (800 버텍스)

※ 가상 시착은 보통 1~2m 거리이므로 LOD 0~1이 주 사용 범위
```

#### 서브스텝 적응

```typescript
function adaptSubsteps(currentFps: number, targetFps: number): number {
  if (currentFps >= targetFps) return 4;        // 여유 있음: 최대 서브스텝
  if (currentFps >= targetFps * 0.8) return 3;  // 약간 부족
  if (currentFps >= targetFps * 0.6) return 2;  // 부족
  return 1;                                      // 심각: 최소 서브스텝
}
```

#### 프레임 스킵

```typescript
class PhysicsScheduler {
  private frameCount = 0;
  private physicsInterval = 1;  // 매 프레임 물리 (기본)

  // FPS 부족 시 물리를 2프레임에 1회만 실행
  adaptInterval(currentFps: number, targetFps: number): void {
    if (currentFps < targetFps * 0.7) {
      this.physicsInterval = 2;  // 격 프레임 물리
    } else {
      this.physicsInterval = 1;  // 매 프레임 물리
    }
  }

  shouldRunPhysics(): boolean {
    this.frameCount++;
    return this.frameCount % this.physicsInterval === 0;
  }
}
```

### 7.3 메모리 관리

| 리소스 | 예상 크기 | 관리 전략 |
|--------|----------|----------|
| VRM 아바타 | 5~15MB | 초기 1회 로드, 캐시 |
| 의류 메쉬 (GLB) | 1~5MB | Draco 압축, 온디맨드 로드 |
| VAT 텍스처 | 2~10MB/모션 | KTX2 압축, 필요 모션만 로드 |
| 노멀맵 프리셋 | 0.5~1MB/장 | KTX2 압축, 의류 로드 시 함께 |
| Rapier.js WASM | ~2MB | 초기 1회 로드 |
| Depth Anything V2 ONNX | ~100MB (초기 로드) | IndexedDB 캐시, 세션간 재사용 |

---

## 8. 에셋 파이프라인

### 8.1 의류 에셋 제작→배포 플로우

```
1. 3D 모델링 (Blender/CLO3D/Marvelous Designer)
   │  의류 메쉬 + 리깅 + UV 맵핑
   │
2. 물리 프리셋 정의
   │  고정 핀 위치, 재질 파라미터
   │
3. VAT 베이킹 (선택)
   │  모션별 cloth sim → VAT 텍스처 내보내기
   │
4. 노멀맵 제작
   │  관절 각도별 주름 노멀맵 렌더링
   │
5. glTF 내보내기
   │  메쉬 + 리깅 + 텍스처 + VAT + 노멀맵
   │
6. 서버 업로드
   │  Draco 압축 + KTX2 변환 (자동)
   │
7. CDN 배포
      클라이언트에서 on-demand 로드
```

### 8.2 glTF 확장 정의

```json
{
  "extensions": {
    "AUTOFIT_cloth_physics": {
      "material": "cotton",
      "pinVertices": [0, 1, 2, 50, 51, 52],
      "pinBones": ["LeftShoulder", "RightShoulder", "Neck"],
      "distanceCompliance": 1e-8,
      "bendingCompliance": 1e-5,
      "particleMass": 0.3
    },
    "AUTOFIT_vat": {
      "sequences": [
        {
          "id": "idle",
          "texture": "vat_idle.ktx2",
          "frames": 60,
          "fps": 30,
          "loop": true
        },
        {
          "id": "walk",
          "texture": "vat_walk.ktx2",
          "frames": 120,
          "fps": 30,
          "loop": true
        }
      ]
    },
    "AUTOFIT_wrinkle_maps": {
      "sets": [
        {
          "joint": "leftElbow",
          "maps": ["wrinkle_elbow_flat.ktx2", "wrinkle_elbow_mid.ktx2", "wrinkle_elbow_deep.ktx2"],
          "angleRange": [0, 150]
        }
      ]
    }
  }
}
```

---

## 부록 A: XPBD 수학 요약

### Distance Constraint

두 파티클 `i`, `j` 사이 거리를 `d` 로 유지:

```
C(x_i, x_j) = |x_j - x_i| - d = 0

∇C_i = -(x_j - x_i) / |x_j - x_i|
∇C_j = +(x_j - x_i) / |x_j - x_i|

Δλ = (-C - α̃ · λ) / (w_i + w_j + α̃)
  여기서 α̃ = α / (Δt)²
  w = 1/mass (역질량)

Δx_i = -w_i · Δλ · ∇C_i
Δx_j = -w_j · Δλ · ∇C_j
```

### Bending Constraint

삼각형 쌍의 이면각 `θ`를 `θ_rest`로 유지:

```
C(θ) = θ - θ_rest = 0

θ = arccos(n_1 · n_2)
  여기서 n_1, n_2는 인접 삼각형의 법선 벡터
```

---

## 부록 B: 브라우저 API 호환성 참고

| API | Chrome | Firefox | Safari | Android Chrome | iOS Safari |
|-----|--------|---------|--------|---------------|------------|
| WebGPU | 113+ | Flag only | 17.4+ (일부) | 미지원 | 미지원 |
| WebGL 2.0 | 56+ | 51+ | 15+ | 56+ | 15+ |
| SharedArrayBuffer | 68+ | 79+ | 15.2+ | 89+ | 15.2+ |
| WASM SIMD | 91+ | 89+ | 16.4+ | 91+ | 16.4+ |
| OffscreenCanvas | 69+ | 105+ | 16.4+ | 69+ | 16.4+ |

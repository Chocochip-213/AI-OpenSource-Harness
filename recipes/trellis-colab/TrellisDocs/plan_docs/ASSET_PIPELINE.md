# 에셋 파이프라인 설계 문서

> AutoFit v2 WebAR — 3D 의류 에셋 생성부터 런타임 배포까지

## 1. 개요

AutoFit v2의 3D 의류 에셋은 **업체 상품 등록**을 시작으로 다음 파이프라인을 거쳐 최종 런타임에 배포된다.

```
업체 상품 등록 (관리 대시보드)
    │ 상품 사진 업로드 (정면/측면/후면/디테일/다각도)
    │ 사이즈별 실측 치수 입력
    │ 핏 타입별 변형 정의 (slim/regular/oversize)
    ↓
Image-to-3D + PBR 추출 (TRELLIS.2, 셀프호스트 GPU)
    │ 상품 사진 → 참조 3D 모델 + 풀 PBR 맵 자동 생성
    │ 출력: GLB (Albedo + Normal + Roughness + Metallic)
    │ [선택] Material Anything으로 PBR 보정
    ↓
Blender 헤드리스 자동화
    │ QuadriFlow 리메쉬 (50k 폴리곤 이하)
    │ Robust Weight Transfer (VRM 바디 프리셋 → 의류 본 웨이트 전사)
    │ 사이즈 검증: 메쉬 치수 vs 입력 치수 ±2cm 이내
    │ 핏 타입 변형 생성: slim/regular/oversize 스케일링
    ↓
gltf-transform (자동화)
    │ Draco 압축 + KTX2 텍스처 + 최적화
    ↓
최종 GLB → CDN 서빙 → 브라우저 로드
```

- **입력**: 업체가 업로드한 실제 상품 사진 (정면/후면/측면/다각도)
- **출력**: Draco 압축된 GLB + KTX2 텍스처
- **목표**: 모바일 기기에서 60fps 렌더링 가능한 경량 에셋

---

## 2. 에셋 생성 워크플로우

### Step 0: 업체 상품 등록

업체가 관리 대시보드에서 상품을 등록하는 단계이다.

**상품 기본 정보 입력:**
- 상품명, 카테고리(top/bottom/dress/outer/accessory), 소재, 핏, 브랜드

**상품 이미지 업로드:**

| 구분 | 이미지 타입 | 설명 |
|------|-----------|------|
| 필수 | 정면(front) | 최소 1장 |
| 권장 | 정면 + 후면(back) + 측면(side) | 최소 3장 권장 |
| 선택 | 다각도(multi_angle), 플랫레이(flat_lay), 디테일(detail) | 이미지가 많을수록 3D 생성 품질 향상 |

**사이즈별 실측 치수 입력:**

| 카테고리 | 필수 치수 항목 |
|---------|---------------|
| 상의 (top) | 어깨너비, 가슴둘레, 총장, 소매길이 |
| 하의 (bottom) | 허리둘레, 힙둘레, 총장, 인심, 밑위 |
| 원피스 (dress) | 어깨너비, 가슴둘레, 허리둘레, 총장 |
| 아우터 (outer) | 어깨너비, 가슴둘레, 총장, 소매길이 |
| 액세서리 (accessory) | 해당 치수만 |

**사이즈**: XS, S, M, L, XL, XXL, FREE

### Step 1: Image-to-3D + PBR 생성 (TRELLIS.2)

| 항목 | 설명 |
|------|------|
| 생성 방식 | Image-to-3D + 풀 PBR (TRELLIS.2 셀프호스트) |
| 입력 | 업체가 업로드한 실제 상품 사진 (앞/뒤/옆) |
| 출력 포맷 | GLB (Albedo + Normal + Roughness + Metallic PBR 맵 포함) |
| 처리 방식 | TRELLIS.2 셀프호스트 GPU 서버 추론 |
| 상태 추적 | pending → processing → ready / failed |

> **TRELLIS.2 참고** (Microsoft, MIT 라이선스):
> - GitHub: `https://github.com/microsoft/TRELLIS.2`
> - 모델: HuggingFace `microsoft/TRELLIS.2-4B`
> - 라이선스: MIT (상업 이용 가능)
> - GPU 요구: VRAM 24GB+ (A5000/A6000/H100)
> - 입력: 단일 이미지 또는 다중 이미지 (앞/뒤/옆)
> - 출력: GLB with 풀 PBR (Albedo, Normal, Roughness, Metallic + 투명도)
> - O-Voxel 표현: 의류처럼 열린 표면(open surface)을 네이티브 처리
> - 소요 시간: 3초(512³) ~ 60초(1536³), H100 기준
> - 텍스처 해상도: 최대 4K
>
> **[선택] Material Anything (CVPR 2025)**: PBR 품질 보정
> - GitHub: `https://github.com/3DTopia/MaterialAnything`
> - 라이선스: 오픈소스
> - 기존 3D 모델의 PBR 머티리얼을 향상
> - TRELLIS.2 출력의 Normal/Roughness가 부족할 때 후처리로 사용

**주의사항:**
- AI 생성 모델은 폴리곤이 불규칙하므로 반드시 리토폴로지 수행
- UV가 자동 생성되므로 Blender에서 재작업 필요
- 메쉬 방향(법선)이 뒤집힌 경우 Blender에서 `Recalculate Outside` 적용

**실측 치수 연동:**
- API 호출 시 의류 실측 치수(어깨너비, 가슴둘레, 총장 등)를 메타데이터로 전달
- TRELLIS.2는 텍스트 프롬프트를 사용하지 않으므로, 핏 타입별 변형(slim/regular/oversize)은 regular 기본 메쉬에서 런타임 스케일링으로 생성한다
- 실측 치수는 Blender 후처리 단계에서 메쉬 스케일 보정에 사용된다

### Step 2: Blender 후처리 (Image-to-3D 결과물 가공)

Blender 3.6+ 기준으로 Image-to-3D 결과물에 대해 다음 작업을 순차 수행한다.

#### 2-1. 리토폴로지 (고폴리 → 저폴리)
- Quad Remesher 또는 Instant Meshes 활용
- 목표 삼각형 수: 모바일 3,000~8,000 / 데스크톱 8,000~15,000
- 에지 루프가 의류 솔기(seam)를 따르도록 조정

#### 2-2. UV 언랩 + 텍스처 베이킹
- 고폴리 → 저폴리로 노멀맵 베이킹
- UV 아일랜드 패딩: 최소 4px (밉맵 블리딩 방지)
- 텍스처 베이킹 대상: Base Color, Normal, ORM (팩킹)

#### 2-3. 자동 리깅 (Robust Weight Transfer)
- **Robust Weight Transfer** (SIGGRAPH Asia 2023, GPL-3.0) 알고리즘으로 VRM 바디 프리셋의 본 웨이트를 의류 메쉬에 자동 전사한다
- 2단계 알고리즘:
  1. **고신뢰 전사**: VRM 바디 메쉬와 의류 메쉬 간 최근접점 대응으로 신뢰도 높은 영역의 웨이트를 직접 복사
  2. **라플라시안 인페인팅**: 나머지 영역(겨드랑이, 사타구니 등 전사 실패 구간)을 라플라시안 스무딩으로 자동 보간
- GitHub: `https://github.com/sentfromspacevr/robust-weight-transfer`
- 의존성: numpy, scipy, libigl
- Blender 헤드리스에서 Python 스크립트로 완전 자동 실행
- 의류 타입별 필수 본 구성은 기존과 동일 (VRM Humanoid 본 이름 기준):
  - 상의: spine, chest, leftShoulder/rightShoulder, leftUpperArm/rightUpperArm
  - 하의: hips, leftUpperLeg/rightUpperLeg, leftLowerLeg/rightLowerLeg
  - 원피스: 상의 + 하의 전체
  - 아우터: 상의와 동일 (소매/밑단 자유 영역 추가)

> **폴백**: Robust Weight Transfer 실패 시 Blender 기본 `Armature Deform with Automatic Weights` 사용
> **폴백2**: UniRig (MIT, SIGGRAPH 2025) — AI 기반 자동 스켈레톤 + 스키닝 생성. VRM 본 이름 리매핑 필요.

#### 2-4. 물리 시뮬레이션 설정 (VAT 베이킹용)
- Cloth 시뮬레이션으로 자연스러운 주름 생성
- VAT(Vertex Animation Texture)로 베이킹하여 런타임 재생
- 프레임 수: 30~60 프레임 (걷기/회전 동작)

#### 2-5. 사이즈 검증 + 핏 타입 변형 생성

**사이즈 검증:**
Blender에서 후처리된 메쉬의 실제 치수를 측정하여 입력 실측 치수와 비교한다.

```python
# scripts/validate_garment_size.py
import bpy
import mathutils

def measure_garment_dimensions(obj):
    """의류 메쉬의 실제 치수를 측정한다."""
    bbox = [obj.matrix_world @ mathutils.Vector(corner) for corner in obj.bound_box]

    width = max(v.x for v in bbox) - min(v.x for v in bbox)   # 어깨너비 방향
    height = max(v.z for v in bbox) - min(v.z for v in bbox)   # 총장 방향
    depth = max(v.y for v in bbox) - min(v.y for v in bbox)    # 가슴둘레 방향

    # ⚠️ 제한사항: 바운딩 박스 기반 검증은 어깨너비, 총장 등 직선 치수에는 유효하나,
    # 가슴둘레/허리둘레 같은 둘레(circumference) 치수는 깊이 축 정보가 필요하므로
    # 바운딩 박스만으로는 정확한 비교가 불가능하다. 둘레 치수는 참고값으로만 사용한다.
    return {
        'width_cm': width * 100,    # Blender 단위(m) → cm
        'height_cm': height * 100,
        'depth_cm': depth * 100,
    }

def validate_against_spec(measured, spec, tolerance_cm=2.0):
    """측정 치수와 입력 스펙 비교. ±tolerance_cm 이내면 통과."""
    results = {}
    for key in spec:
        if key in measured:
            diff = abs(measured[key] - spec[key])
            results[key] = {
                'measured': measured[key],
                'spec': spec[key],
                'diff_cm': diff,
                'pass': diff <= tolerance_cm,
            }
    return results
```

**핏 타입 변형 생성:**

> **MVP 스코프 조정**: 핏 타입별 별도 메쉬 생성(slim/regular/oversize)은 에셋 수량이 3배로
> 증가하므로, MVP에서는 **regular만 제작**한다. slim/oversize는 런타임 스케일링으로 근사하며,
> 후속 작업에서 별도 메쉬로 교체한다.

하나의 기본 메쉬(regular)에서 slim/oversize 변형을 생성한다.

```python
# 핏 타입별 스케일 팩터
FIT_SCALE_FACTORS = {
    'slim': {'x': 0.95, 'y': 0.95, 'z': 1.0},     # 폭/깊이 5% 축소
    'regular': {'x': 1.0, 'y': 1.0, 'z': 1.0},     # 기준
    'oversize': {'x': 1.08, 'y': 1.08, 'z': 1.02},  # 폭/깊이 8% 확대, 길이 2% 확대
}

def generate_fit_variants(base_obj, output_dir):
    """regular 메쉬에서 slim/oversize 변형을 생성한다."""
    for fit_type, scales in FIT_SCALE_FACTORS.items():
        variant = base_obj.copy()
        variant.data = base_obj.data.copy()
        variant.scale = (scales['x'], scales['y'], scales['z'])
        bpy.context.collection.objects.link(variant)
        # GLB 내보내기
        export_path = f"{output_dir}/{base_obj.name}_{fit_type}.glb"
        # ... 내보내기 로직
```

#### 2-6. Blender Python 자동화 스크립트
```python
# scripts/blender_export.py
# Blender에서 --background 모드로 실행
# 사용법: blender --background --python scripts/blender_export.py -- input.fbx output.glb
```

주요 자동화 항목:
- GLB 임포트 (TRELLIS.2 출력) → 스케일/축 보정
- QuadriFlow 리메쉬 (목표 50k 폴리곤)
- VRM 바디 프리셋 로드 + Robust Weight Transfer 실행
- 머티리얼을 glTF PBR로 변환
- LOD(Level of Detail) 자동 생성
- GLB 내보내기 (Draco 미적용 — 다음 단계에서 처리)

### Step 3: 에셋 최적화

#### gltf-transform: GLB 변환 + Draco 메쉬 압축
```bash
# Draco 압축 적용
npx gltf-transform draco input.glb output.glb \
  --method edgebreaker \
  --encode-speed 5 \
  --decode-speed 5 \
  --quantize-position 14 \
  --quantize-normal 10 \
  --quantize-texcoord 12

# 미사용 데이터 정리
npx gltf-transform prune output.glb output.glb

# 메쉬 결합 (드로우콜 최소화)
npx gltf-transform join output.glb output.glb
```

#### KTX2: 텍스처 압축 (GPU 디코딩)
```bash
# 텍스처를 KTX2 (ETC1S/UASTC) 포맷으로 변환
npx gltf-transform ktx2 output.glb output.glb \
  --slots "baseColorTexture,normalTexture,occlusionTexture,metallicRoughnessTexture" \
  --compression uastc \
  --quality 128
```

#### 검증
```bash
# 폴리곤 수, 텍스처 크기, 파일 크기 확인
npx gltf-transform inspect output.glb
```

검증 기준:
- 삼각형 수가 대상 범위 내인지
- 텍스처 해상도가 규격에 맞는지
- 최종 파일 크기가 목표 이내인지

---

## 3. 에셋 규격

| 대상 | 삼각형 수 | 텍스처 해상도 | 핏 타입 변형 | 파일 크기 목표 |
|------|-----------|---------------|------------|----------------|
| 상의/아우터 (모바일) | 3,000~8,000 | 1024x1024 | MVP: regular만 | < 2MB |
| 상의/아우터 (데스크톱) | 8,000~15,000 | 2048x2048 | MVP: regular만 | < 5MB |
| 하의/원피스 (모바일) | 3,000~8,000 | 1024x1024 | MVP: regular만 | < 2MB |
| 하의/원피스 (데스크톱) | 8,000~15,000 | 2048x2048 | MVP: regular만 | < 5MB |
| 바디 프리셋 (.vrm) | 5,000~10,000 | 1024x1024 | 해당 없음 | < 3MB |
| 액세서리 | 1,000~3,000 | 512x512 | 해당 없음 | < 1MB |

**LOD 전략 (선택사항):**

| LOD 레벨 | 삼각형 비율 | 사용 거리 |
|----------|-------------|-----------|
| LOD0 | 100% | 0~2m |
| LOD1 | 50% | 2~5m |
| LOD2 | 25% | 5m+ |

---

## 4. 텍스처 채널

모든 텍스처는 glTF 2.0 PBR(Metallic-Roughness) 워크플로우를 따른다.

| 채널 | 접미사 | 설명 | 포맷 |
|------|--------|------|------|
| Base Color | `_basecolor` | PBR 기본 색상 (알파 = 투명도) | sRGB |
| Normal | `_normal` | 표면 주름/디테일 (탄젠트 스페이스) | Linear |
| ORM | `_orm` | R=Occlusion, G=Roughness, B=Metallic (팩킹) | Linear |

**ORM 팩킹 규칙:**
- R 채널: Ambient Occlusion (0=차폐, 1=노출)
- G 채널: Roughness (0=매끈, 1=거친)
- B 채널: Metallic (0=비금속, 1=금속 — 의류는 대부분 0)

---

## 5. 네이밍 규칙

### 에셋 파일
```
권장(프로덕션): DB의 ID를 파일 경로에 반영한다.

assets/optimized/garments/<garment_id>/<variant_id>.glb

공개 URL 예시:
/assets/garments/<garment_id>/<variant_id>.glb

참고(개발/샘플용, 사람 친화적 이름):
{category}_{name}_{color}_{size}_{fit_type}.glb

카테고리:
  top     — 상의 (티셔츠, 셔츠 등)
  bottom  — 하의 (바지, 스커트 등)
  dress   — 원피스/투피스
  outer   — 아우터 (자켓, 코트, 가디건 등)
  acc     — 액세서리 (모자, 가방, 안경 등)

핏 타입:
  slim    — 슬림핏
  regular — 레귤러핏(적정핏)
  oversize — 오버핏

예시:
  top_tshirt_white_M_regular.glb
  top_tshirt_white_M_slim.glb
  top_tshirt_white_M_oversize.glb
  outer_jacket_black_L_regular.glb
  bottom_jeans_blue_M_slim.glb
  bottom_skirt_red_S_regular.glb
  dress_summer_floral_M_regular.glb
  acc_cap_navy.glb  (액세서리는 핏 타입 없음)
```

### 텍스처 파일
```
{category}_{name}_{color}_{size}_{fit_type}_{channel}.{ext}

예시:
  top_tshirt_white_M_regular_basecolor.png
  top_tshirt_white_M_regular_normal.png
  top_tshirt_white_M_regular_orm.png
```

---

## 6. 바디 메쉬 프리셋

사용자 체형에 맞는 바디 메쉬를 선택하여 의류를 피팅한다.

### 프리셋 목록

경로: `assets/optimized/body-presets/body_{gender}_{size}.vrm`

| 프리셋 ID | 파일명 | 성별 | 사이즈 |
|-----------|--------|------|--------|
| 1 | `body_male_XS.vrm` | 남성 | XS |
| 2 | `body_male_S.vrm` | 남성 | S |
| 3 | `body_male_M.vrm` | 남성 | M |
| 4 | `body_male_L.vrm` | 남성 | L |
| 5 | `body_male_XL.vrm` | 남성 | XL |
| 6 | `body_male_XXL.vrm` | 남성 | XXL |
| 7 | `body_female_XS.vrm` | 여성 | XS |
| 8 | `body_female_S.vrm` | 여성 | S |
| 9 | `body_female_M.vrm` | 여성 | M |
| 10 | `body_female_L.vrm` | 여성 | L |
| 11 | `body_female_XL.vrm` | 여성 | XL |
| 12 | `body_female_XXL.vrm` | 여성 | XXL |

**사이즈 범위**: XS, S, M, L, XL, XXL, FREE

### 바디 메쉬 사양
- 폴리곤: 5,000~10,000 삼각형
- 리깅: VRM Humanoid 아마처 (VRMHumanBoneName 표준)
- 블렌드 셰이프: 체형 조절용 (shoulder_width, waist, hip)
- T-포즈 기준 내보내기

---

## 7. 스크립트

### optimize.sh — gltf-transform + Draco 일괄 압축

```bash
#!/bin/bash
# 사용법: ./scripts/optimize.sh <입력 디렉토리> <출력 디렉토리>
#
# 입력 디렉토리 내 모든 .glb 파일을 Draco 압축 + KTX2 변환하여
# 출력 디렉토리에 저장한다.

INPUT_DIR="${1:?입력 디렉토리를 지정하세요}"
OUTPUT_DIR="${2:?출력 디렉토리를 지정하세요}"

mkdir -p "$OUTPUT_DIR"

for file in "$INPUT_DIR"/*.glb; do
    filename=$(basename "$file")
    echo "[최적화] $filename ..."

    # Draco 압축
    npx gltf-transform draco "$file" "$OUTPUT_DIR/$filename" \
        --method edgebreaker \
        --quantize-position 14 \
        --quantize-normal 10 \
        --quantize-texcoord 12

    # KTX2 텍스처 압축
    npx gltf-transform ktx2 "$OUTPUT_DIR/$filename" "$OUTPUT_DIR/$filename" \
        --compression uastc \
        --quality 128

    # 미사용 데이터 정리
    npx gltf-transform prune "$OUTPUT_DIR/$filename" "$OUTPUT_DIR/$filename"

    echo "[완료] $filename → $(du -h "$OUTPUT_DIR/$filename" | cut -f1)"
done

echo "=== 전체 최적화 완료 ==="
```

### validate.sh — 폴리곤/텍스처/크기 검증

```bash
#!/bin/bash
# 사용법: ./scripts/validate.sh <에셋 디렉토리>
#
# 에셋 디렉토리 내 모든 .glb 파일의 규격을 검증한다.

ASSET_DIR="${1:?에셋 디렉토리를 지정하세요}"
MAX_FILE_SIZE_MB=5
ERRORS=0

for file in "$ASSET_DIR"/*.glb; do
    filename=$(basename "$file")
    filesize=$(du -m "$file" | cut -f1)

    echo "--- 검증: $filename ---"

    # 파일 크기 확인
    if [ "$filesize" -gt "$MAX_FILE_SIZE_MB" ]; then
        echo "  [경고] 파일 크기 초과: ${filesize}MB (목표: <${MAX_FILE_SIZE_MB}MB)"
        ERRORS=$((ERRORS + 1))
    else
        echo "  [통과] 파일 크기: ${filesize}MB"
    fi

    # gltf-transform inspect로 상세 정보 출력
    npx gltf-transform inspect "$file"

    echo ""
done

if [ "$ERRORS" -gt 0 ]; then
    echo "=== 검증 실패: ${ERRORS}개 경고 발견 ==="
    exit 1
else
    echo "=== 전체 검증 통과 ==="
fi
```

---

## 8. 상품 이미지 촬영 가이드

TRELLIS.2 Image-to-3D 입력 품질을 높이기 위한 상품 이미지 촬영 가이드라인이다.

> TRELLIS.2는 다중 이미지(앞/뒤/옆) 입력을 지원한다. 3장 이상의 다각도 촬영이 PBR 품질과 형태 정확도를 크게 향상시킨다.

| 항목 | 권장 사항 |
|------|----------|
| 해상도 | 1024×1024 이상 |
| 배경 | 단색 (흰색/회색 권장) |
| 조명 | 균일한 조명, 강한 그림자 피하기 |
| 구도 | 상품이 화면의 70% 이상 차지 |
| 다각도 | 가능하면 턴테이블 위에서 8~12장 촬영 |
| 파일 형식 | JPEG / PNG |
| 파일 크기 | 최대 10MB/장 |

**촬영 팁:**
- 상품의 형태가 명확히 보이도록 주름을 정리한 상태에서 촬영
- 배경과 상품의 색상 대비가 충분해야 AI가 형태를 정확히 인식
- 플랫레이(flat_lay) 촬영 시 상품을 평평하게 펼쳐서 촬영
- 디테일 사진은 로고, 단추, 지퍼 등 특징적인 부분을 클로즈업

---

## 8b. 사이즈 정확 메쉬 검증 체크리스트

3D 메쉬가 입력 실측 치수를 정확히 반영하는지 검증하기 위한 체크리스트이다.

### 자동 검증 항목

| # | 검증 항목 | 기준 | 검증 방법 |
|---|----------|------|----------|
| 1 | 메쉬 바운딩 박스 치수 | 입력 치수 ±2cm | Blender Python 스크립트 자동 측정 |
| 2 | 핏 타입 간 크기 차이 | slim < regular < oversize | 세 변형의 바운딩 박스 비교 |
| 3 | 본 가중치 유효성 | 모든 버텍스에 가중치 할당됨 | 가중치 합 > 0 검증 |
| 4 | UV 겹침 없음 | UV 아일랜드 겹침 0% | Blender UV 검증 도구 |
| 5 | 법선 방향 | 외부 방향 일관성 | Blender Recalculate Outside 후 검증 |

### 수동 검증 항목 (QA)

| # | 검증 항목 | 기준 | 검증 방법 |
|---|----------|------|----------|
| 1 | 시각적 비례감 | 자연스러운 의류 비율 | VRM 아바타에 착용 후 목시 검수 |
| 2 | 핏 타입별 실루엣 | slim=밀착, regular=표준, oversize=넉넉 | 세 변형 나란히 비교 |
| 3 | 관절 변형 | 팔/다리 굽힘 시 메쉬 깨짐 없음 | 포즈 변경 테스트 |
| 4 | 텍스처 정합 | 솔기/패턴 일치 | 텍스처 맵핑 시각 검수 |

---

## 9. 디렉토리 구조

```
assets/
├── raw/                        # TRELLIS.2 원본 출력 (GLB + PBR) — Git 미추적
├── blender/                    # Blender 프로젝트/템플릿/스크립트
├── optimized/                  # 최종 런타임 에셋 (압축 GLB — Git 추적)
│   ├── garments/               # 의류 GLB ({garment_id}/{variant_id}.glb)
│   ├── body-presets/           # 바디 프리셋 VRM (body_{gender}_{size}.vrm)
│   ├── textures/               # 공유 텍스처 (KTX2)
│   └── vat/                    # VAT 베이킹 데이터
└── scripts/                    # 변환/검증 자동화 스크립트
    ├── robust_weight_transfer.py  # Robust Weight Transfer 자동 리깅
```

> 런타임에서는 정적 서빙 경로를 `/assets/*`로 통일하고,
> 서버(Nginx 등)에서 `assets/optimized/*`를 `/assets/*`로 매핑한다.

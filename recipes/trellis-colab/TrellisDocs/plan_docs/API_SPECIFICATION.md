# REST API 명세서

> AutoFit v2 WebAR — 백엔드 REST API 전체 명세

## 1. 공통 설계 원칙

| 항목 | 설명 |
|------|------|
| Base URL | `/api/v1` |
| 인증 방식 | JWT Bearer Token + SDK API Key (`X-API-Key`) |
| 응답 형식 | `application/json` |
| 문자 인코딩 | UTF-8 |
| 페이지네이션 | 오프셋 기반 (`page`, `per_page`) |
| API 버전 | v1 |

### 공통 응답 형식

**성공 응답 (단일 리소스):**

- 별도 래핑 없이 리소스 JSON을 직접 반환한다.
- `201 Created`인 경우 `Location` 헤더에 생성된 리소스 URL을 포함할 수 있다.

**목록 응답 (페이지네이션):**
```json
{
  "items": [ ... ],
  "total": 100,
  "page": 1,
  "per_page": 20
}
```

- 페이지네이션이 필요 없는 소규모 목록(예: 바디 프리셋)은 **배열(JSON array)** 을 직접 반환할 수 있다.
- 페이지네이션이 필요한 목록은 위의 envelope(`items/total/page/per_page`) 형식을 사용한다.

**에러 응답:**
```json
{
  "detail": "에러 메시지",
  "code": "ERROR_CODE",
  "trace_id": "01J3Z9H8Q6K7V8W9X0Y1Z2A3B4",
  "fields": [
    { "field": "email", "reason": "이메일 형식이 올바르지 않습니다." }
  ]
}
```

> `trace_id`, `fields`는 선택 필드이며, 서버에서 제공 가능한 경우에만 포함한다.

### 공통 에러 코드

| HTTP 상태 | 코드 | 설명 |
|-----------|------|------|
| 400 | `VALIDATION_ERROR` | 요청 데이터 유효성 검증 실패 |
| 401 | `UNAUTHORIZED` | 인증 토큰 없음 또는 만료 |
| 403 | `FORBIDDEN` | 권한 부족 또는 브랜드 범위 위반 |
| 404 | `NOT_FOUND` | 리소스를 찾을 수 없음 |
| 409 | `CONFLICT` | 리소스 충돌 (중복 등) |
| 422 | `UNPROCESSABLE_ENTITY` | 요청 형식 오류 |
| 500 | `INTERNAL_ERROR` | 서버 내부 오류 |

### 인증 헤더

```
Authorization: Bearer <access_token>
```

### SDK 인증 헤더

```
X-API-Key: <api_key>
```

- SDK/임베드 호출은 **브라우저의 `Origin` 헤더**를 기준으로 `sdk_configs.allowed_origins`를 검증한다.
- 요청 바디의 `origin` 값은 신뢰하지 않는다.

### 권한 표기 규칙

- `(public)`: 인증 없이 호출 가능
- `(user)`: 로그인 사용자
- `(vendor)`: 업체 담당자(자기 브랜드 범위)
- `(manager)`: 운영자
- `(admin)`: 시스템 관리자

> `vendor`는 `users.brand_id` 범위 내 리소스만 수정할 수 있다.

### 멱등성 (Idempotency)

네트워크 재시도/중복 클릭으로 동일한 `POST`가 반복 호출될 수 있으므로, 아래 헤더를 지원한다.

```
Idempotency-Key: <uuid>
```

- **적용 대상(권장)**: 세션 생성/저장, 신체 측정 저장, 핏 평가 저장, 3D 생성 요청, 업로드 계열
- **보관 기간(권장)**: 24시간
- 동일 키로 동일 요청이 들어오면 동일 응답을 반환한다.

### 부분 업데이트 규칙

> **부분 업데이트 규칙**: 본 API에서 `PUT` 메서드는 전체 교체(full replacement)가 아닌
> 부분 업데이트(partial update) 시맨틱으로 사용한다. 전달된 필드만 업데이트되며,
> 생략된 필드는 기존 값을 유지한다. 이는 RESTful 엄밀 정의와 다르나,
> 클라이언트 구현 편의를 위해 채택한 설계 결정이다.

### SDK(임베드) 호출 범위

`X-API-Key` 기반으로 호출 가능한 엔드포인트는 아래로 제한한다(권장).

- 카탈로그 조회: `GET /api/v1/garments`, `GET /api/v1/garments/{id}`, `GET /api/v1/garments/{garment_id}/variants`
- 바디 프리셋 조회: `GET /api/v1/body-presets`
- 즉석 핏 평가(저장 없음): `POST /api/v1/garments/{garment_id}/evaluate-fit`
- (선택) 익명 세션 로그: `POST /api/v1/fitting-sessions` (user_id=NULL, sdk_config_id 자동 설정)

---

## 2. 인증 API (Auth)

### POST /api/v1/auth/register

회원가입.

**요청:**
```json
{
  "email": "user@example.com",
  "password": "securePassword123!",
  "name": "홍길동"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| email | string | O | 이메일 (RFC 5322 형식) |
| password | string | O | 비밀번호 (최소 8자, 영문+숫자+특수문자) |
| name | string | O | 사용자 이름 (2~100자) |

> 본 엔드포인트는 **일반 사용자(user)** 가입만 지원한다. `vendor/manager/admin` 계정은 관리자 기능으로 생성한다.

**응답 (201 Created):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "name": "홍길동",
  "created_at": "2026-02-27T09:00:00Z"
}
```

**에러:**
- `409 CONFLICT`: 이미 등록된 이메일

---

### POST /api/v1/auth/login

로그인. JWT 액세스 토큰을 발급한다.

**요청:**
```json
{
  "email": "user@example.com",
  "password": "securePassword123!"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| email | string | O | 등록된 이메일 |
| password | string | O | 비밀번호 |

**응답 (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 900
}
```

**부가 동작(권장):** Refresh Token을 `HttpOnly` 쿠키로 설정한다.

```
Set-Cookie: refresh_token=<token>; HttpOnly; Secure; SameSite=Lax; Path=/api/v1/auth/; Max-Age=604800
```

**에러:**
- `401 UNAUTHORIZED`: 이메일 또는 비밀번호 불일치

---

### POST /api/v1/auth/refresh

Refresh Token으로 Access Token을 재발급한다.

- **인증**: `refresh_token` 쿠키
- **권한**: `(user|vendor|manager|admin)`

**응답 (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 900
}
```

**부가 동작(권장):** Refresh Token 회전(rotate) 시 새로운 `refresh_token` 쿠키를 다시 설정한다.

**에러:**
- `401 UNAUTHORIZED`: refresh token 만료/폐기

---

### POST /api/v1/auth/logout

현재 Refresh Token을 폐기하고 로그아웃 처리한다.

- **인증**: `refresh_token` 쿠키

**응답 (204 No Content):** 본문 없음

**부가 동작(권장):** `refresh_token` 쿠키 삭제(`Max-Age=0`).

---

## 3. 사용자 API (Users)

### GET /api/v1/users/me

현재 로그인 사용자 정보를 조회한다.

- **인증**: JWT Bearer

**응답 (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "name": "홍길동",
  "role": "user",
  "brand_id": null,
  "created_at": "2026-02-27T09:00:00Z"
}
```

---

### GET /api/v1/users (manager|admin)

사용자 목록을 조회한다.

**쿼리 파라미터:**

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|----------|------|------|--------|------|
| search | string | X | - | 이메일/이름 검색 |
| role | string | X | - | 역할 필터 (`user`, `vendor`, `manager`, `admin`) |
| page | integer | X | 1 | 페이지 번호 |
| per_page | integer | X | 20 | 페이지당 항목 수 |

**응답 (200 OK):**
```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "email": "vendor@modernwear.co.kr",
      "name": "모던웨어 담당자",
      "role": "vendor",
      "brand_id": "aa0e8400-e29b-41d4-a716-446655440001",
      "is_active": true,
      "created_at": "2026-03-01T09:00:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "per_page": 20
}
```

---

### POST /api/v1/users (admin)

관리자가 사용자 계정을 생성한다.

**요청:**
```json
{
  "email": "vendor@modernwear.co.kr",
  "password": "securePassword123!",
  "name": "모던웨어 담당자",
  "role": "vendor",
  "brand_id": "aa0e8400-e29b-41d4-a716-446655440001",
  "is_active": true
}
```

> `role=vendor`인 경우 `brand_id`는 필수다.

**응답 (201 Created):** 생성된 사용자 객체 반환

---

### PUT /api/v1/users/{id} (admin)

관리자가 사용자 계정을 수정한다(역할/브랜드/활성화 포함).

**응답 (200 OK):** 수정된 사용자 객체 반환

---

## 4. 브랜드 API (Brands)

### POST /api/v1/brands (admin)

브랜드(업체) 등록. 관리자 권한 필요.

**요청:**
```json
{
  "name": "모던웨어",
  "logo_url": "/assets/brands/modernwear_logo.png",
  "website_url": "https://modernwear.co.kr",
  "contact_email": "biz@modernwear.co.kr"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| name | string | O | 브랜드/업체명 (1~200자) |
| logo_url | string | X | 로고 이미지 URL |
| website_url | string | X | 웹사이트 URL |
| contact_email | string | X | 담당자 이메일 |

**응답 (201 Created):**
```json
{
  "id": "aa0e8400-e29b-41d4-a716-446655440001",
  "name": "모던웨어",
  "logo_url": "/assets/brands/modernwear_logo.png",
  "website_url": "https://modernwear.co.kr",
  "contact_email": "biz@modernwear.co.kr",
  "is_active": true,
  "created_at": "2026-03-01T09:00:00Z"
}
```

---

### GET /api/v1/brands

브랜드 목록 조회. 검색 및 페이지네이션을 지원한다.

**쿼리 파라미터:**

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|----------|------|------|--------|------|
| search | string | X | - | 브랜드명 검색 (LIKE 매칭) |
| page | integer | X | 1 | 페이지 번호 |
| per_page | integer | X | 20 | 페이지당 항목 수 (최대 100) |

**응답 (200 OK):**
```json
{
  "items": [
    {
      "id": "aa0e8400-e29b-41d4-a716-446655440001",
      "name": "모던웨어",
      "logo_url": "/assets/brands/modernwear_logo.png",
      "website_url": "https://modernwear.co.kr",
      "contact_email": "biz@modernwear.co.kr",
      "is_active": true,
      "created_at": "2026-03-01T09:00:00Z"
    }
  ],
  "total": 3,
  "page": 1,
  "per_page": 20
}
```

---

### GET /api/v1/brands/{id}

브랜드 상세 조회.

**경로 파라미터:**

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| id | UUID | 브랜드 ID |

**응답 (200 OK):**
```json
{
  "id": "aa0e8400-e29b-41d4-a716-446655440001",
  "name": "모던웨어",
  "logo_url": "/assets/brands/modernwear_logo.png",
  "website_url": "https://modernwear.co.kr",
  "contact_email": "biz@modernwear.co.kr",
  "is_active": true,
  "created_at": "2026-03-01T09:00:00Z",
  "updated_at": "2026-03-01T09:00:00Z"
}
```

**에러:**
- `404 NOT_FOUND`: 해당 ID의 브랜드 없음

---

### PUT /api/v1/brands/{id} (admin)

브랜드 정보 수정. 관리자 권한 필요.

**요청:**
```json
{
  "name": "모던웨어 코리아",
  "website_url": "https://modernwear.co.kr/new"
}
```

모든 필드는 선택적이며, 전달된 필드만 업데이트된다.

**응답 (200 OK):** 수정된 브랜드 객체 반환

---

### DELETE /api/v1/brands/{id} (admin)

브랜드 삭제 (소프트 삭제: `is_active = false`). 관리자 권한 필요.

**응답 (204 No Content):** 본문 없음

---

## 5. 의류 카탈로그 API (Garments)

### GET /api/v1/garments

의류 목록 조회. 카테고리 필터링, 검색, 페이지네이션을 지원한다.

**쿼리 파라미터:**

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|----------|------|------|--------|------|
| category | string | X | - | 카테고리 필터 (`top`, `bottom`, `dress`, `outer`, `accessory`) |
| search | string | X | - | 의류명 검색 (LIKE 매칭) |
| page | integer | X | 1 | 페이지 번호 |
| per_page | integer | X | 20 | 페이지당 항목 수 (최대 100) |

**응답 (200 OK):**
```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "name": "기본 티셔츠",
      "category": "top",
      "description": "편안한 면 소재의 기본 티셔츠",
      "thumbnail_url": "/assets/thumbnails/top_tshirt_white.jpg",
      "model_url": "/assets/garments/550e8400-e29b-41d4-a716-446655440001/660e8400-e29b-41d4-a716-446655440010.glb",
      "asset_status": "ready",
      "brand": {
        "id": "aa0e8400-e29b-41d4-a716-446655440001",
        "name": "모던웨어",
        "logo_url": "/assets/brands/modernwear_logo.png"
      },
      "images": [
        {
          "id": "bb0e8400-e29b-41d4-a716-446655440001",
          "image_url": "/assets/images/top_tshirt_front.jpg",
          "image_type": "front",
          "is_primary": true
        }
      ],
      "variant_count": 4,
      "created_at": "2026-02-20T12:00:00Z"
    }
  ],
  "total": 42,
  "page": 1,
  "per_page": 20
}
```

---

### GET /api/v1/garments/{id}

의류 상세 조회. 변형(variants) 목록을 포함한다.

**경로 파라미터:**

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| id | UUID | 의류 ID |

**응답 (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440001",
  "name": "기본 티셔츠",
  "category": "top",
  "description": "편안한 면 소재의 기본 티셔츠",
  "thumbnail_url": "/assets/thumbnails/top_tshirt_white.jpg",
  "model_url": "/assets/garments/550e8400-e29b-41d4-a716-446655440001/660e8400-e29b-41d4-a716-446655440010.glb",
  "asset_status": "ready",
  "brand": {
    "id": "aa0e8400-e29b-41d4-a716-446655440001",
    "name": "모던웨어",
    "logo_url": "/assets/brands/modernwear_logo.png",
    "website_url": "https://modernwear.co.kr"
  },
  "images": [
    {
      "id": "bb0e8400-e29b-41d4-a716-446655440001",
      "image_url": "/assets/images/top_tshirt_front.jpg",
      "image_type": "front",
      "sort_order": 0,
      "is_primary": true
    },
    {
      "id": "bb0e8400-e29b-41d4-a716-446655440002",
      "image_url": "/assets/images/top_tshirt_back.jpg",
      "image_type": "back",
      "sort_order": 1,
      "is_primary": false
    }
  ],
  "variants": [
    {
      "id": "660e8400-e29b-41d4-a716-446655440010",
      "color": "white",
      "pattern": null,
      "size": "M",
      "fit_type": "regular",
      "is_default": true,
      "model_url": "/assets/garments/550e8400-e29b-41d4-a716-446655440001/660e8400-e29b-41d4-a716-446655440010.glb",
      "shoulder_width_cm": 44.0,
      "chest_cm": 96.0,
      "total_length_cm": 68.0,
      "waist_cm": null,
      "hip_cm": null,
      "sleeve_length_cm": 22.0,
      "inseam_cm": null,
      "rise_cm": null
    },
    {
      "id": "660e8400-e29b-41d4-a716-446655440011",
      "color": "black",
      "pattern": null,
      "size": "M",
      "fit_type": "regular",
      "is_default": false,
      "model_url": "/assets/garments/550e8400-e29b-41d4-a716-446655440001/660e8400-e29b-41d4-a716-446655440011.glb",
      "shoulder_width_cm": 44.0,
      "chest_cm": 96.0,
      "total_length_cm": 68.0,
      "waist_cm": null,
      "hip_cm": null,
      "sleeve_length_cm": 22.0,
      "inseam_cm": null,
      "rise_cm": null
    }
  ],
  "created_at": "2026-02-20T12:00:00Z"
}
```

**에러:**
- `404 NOT_FOUND`: 해당 ID의 의류 없음

---

### POST /api/v1/garments (vendor|manager|admin)

의류(상품) 등록. vendor/manager/admin 권한 필요. 업체가 상품을 등록하고, 이미지 업로드 후 3D 에셋을 생성하는 플로우의 첫 단계.

**요청:**
```json
{
  "brand_id": "aa0e8400-e29b-41d4-a716-446655440001",
  "name": "기본 티셔츠",
  "category": "top",
  "description": "편안한 면 소재의 기본 티셔츠",
  "thumbnail_url": "/assets/thumbnails/top_tshirt_white.jpg",
  "model_url": "/assets/garments/550e8400-e29b-41d4-a716-446655440001/660e8400-e29b-41d4-a716-446655440010.glb"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| brand_id | UUID | 조건부 | manager/admin은 필수. vendor는 자신의 `brand_id`가 자동 적용되며 요청 값은 무시된다 |
| name | string | O | 의류명 (1~200자) |
| category | string | O | 카테고리 (`top`, `bottom`, `dress`, `outer`, `accessory`) |
| description | string | X | 설명 |
| thumbnail_url | string | X | 썸네일 URL |
| model_url | string | X | 3D 모델 URL (GLB, 직접 업로드 시) |

**응답 (201 Created):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440001",
  "name": "기본 티셔츠",
  "category": "top",
  "description": "편안한 면 소재의 기본 티셔츠",
  "thumbnail_url": "/assets/thumbnails/top_tshirt_white.jpg",
  "model_url": null,
  "asset_status": "pending",
  "brand": {
    "id": "aa0e8400-e29b-41d4-a716-446655440001",
    "name": "모던웨어",
    "logo_url": "/assets/brands/modernwear_logo.png"
  },
  "images": [],
  "is_active": true,
  "created_at": "2026-02-27T09:00:00Z"
}
```

---

### PUT /api/v1/garments/{id} (vendor|manager|admin)

의류 정보 수정. vendor/manager/admin 권한 필요.

**요청:**
```json
{
  "name": "프리미엄 티셔츠",
  "description": "유기농 면 소재의 프리미엄 티셔츠",
  "is_active": true
}
```

모든 필드는 선택적이며, 전달된 필드만 업데이트된다.

**응답 (200 OK):** 수정된 의류 객체 반환

---

### DELETE /api/v1/garments/{id} (vendor|manager|admin)

의류 삭제 (소프트 삭제: `is_active = false`). vendor/manager/admin 권한 필요.

**응답 (204 No Content):** 본문 없음

---

## 6. 상품 이미지 API (Garment Images)

### POST /api/v1/garments/{garment_id}/images (vendor|manager|admin)

상품 이미지 업로드. 멀티파트 파일 업로드로 다중 파일을 지원한다. vendor/manager/admin 권한 필요.

**경로 파라미터:**

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| garment_id | UUID | 의류 ID |

**요청:** `multipart/form-data`

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| files[] | file[] | O | 업로드할 이미지 파일들 (PNG, JPG, WEBP) |
| image_type | string | O | 이미지 유형 (`front`, `back`, `side_left`, `side_right`, `detail`, `multi_angle`, `flat_lay`) |

**파일 크기 제한:** 파일당 최대 10MB

**응답 (201 Created):**
```json
[
  {
    "id": "bb0e8400-e29b-41d4-a716-446655440001",
    "image_url": "/assets/images/garment_550e_front_001.jpg",
    "image_type": "front",
    "sort_order": 0
  },
  {
    "id": "bb0e8400-e29b-41d4-a716-446655440002",
    "image_url": "/assets/images/garment_550e_front_002.jpg",
    "image_type": "front",
    "sort_order": 1
  }
]
```

**에러:**
- `404 NOT_FOUND`: 해당 ID의 의류 없음
- `413 REQUEST_ENTITY_TOO_LARGE`: 파일 크기 초과
- `415 UNSUPPORTED_MEDIA_TYPE`: 지원하지 않는 파일 형식

---

### GET /api/v1/garments/{garment_id}/images

특정 의류의 이미지 목록 조회. `is_primary=true`인 이미지가 우선 정렬된다.

**경로 파라미터:**

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| garment_id | UUID | 의류 ID |

**응답 (200 OK):**
```json
[
  {
    "id": "bb0e8400-e29b-41d4-a716-446655440001",
    "image_url": "/assets/images/garment_550e_front_001.jpg",
    "image_type": "front",
    "sort_order": 0,
    "is_primary": true
  },
  {
    "id": "bb0e8400-e29b-41d4-a716-446655440003",
    "image_url": "/assets/images/garment_550e_back_001.jpg",
    "image_type": "back",
    "sort_order": 1,
    "is_primary": false
  }
]
```

---

### PUT /api/v1/garments/{garment_id}/images/{image_id} (vendor|manager|admin)

이미지 정보 수정 (정렬 순서, 대표 이미지 설정). vendor/manager/admin 권한 필요.

**경로 파라미터:**

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| garment_id | UUID | 의류 ID |
| image_id | UUID | 이미지 ID |

**요청:**
```json
{
  "sort_order": 0,
  "is_primary": true
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| sort_order | integer | X | 정렬 순서 |
| is_primary | boolean | X | 대표 이미지 여부 |

**응답 (200 OK):** 수정된 이미지 객체 반환

---

### DELETE /api/v1/garments/{garment_id}/images/{image_id} (vendor|manager|admin)

이미지 삭제. vendor/manager/admin 권한 필요.

**응답 (204 No Content):** 본문 없음

---

## 7. 3D 에셋 생성 API (Generate 3D)

### POST /api/v1/garments/{garment_id}/generate-3d (vendor|manager|admin)

업로드된 상품 이미지 기반으로 TRELLIS.2 Image-to-3D 생성을 요청한다. 비동기 처리되며(TRELLIS.2 메쉬 생성 → Material Anything 재질 생성 → Robust Weight Transfer 자동 리깅 → Draco/KTX2 최적화), 완료 시 `asset_status`가 `ready` 또는 `failed`로 변경된다. vendor/manager/admin 권한 필요.

**전제조건:** 해당 의류에 `garment_images`가 1장 이상 존재해야 한다.

**경로 파라미터:**

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| garment_id | UUID | 의류 ID |

**요청 (선택):**
```json
{
  "include_measurements": true,
  "target_fit_types": ["slim", "regular", "oversize"]
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| include_measurements | boolean | X | true 시 의류 실측 치수를 3D 생성에 반영 |
| target_fit_types | string[] | X | 생성할 핏 타입 목록 (기본: ["regular"]) |

**응답 (202 Accepted):**
```json
{
  "garment_id": "550e8400-e29b-41d4-a716-446655440001",
  "asset_status": "generating",
  "estimated_time_seconds": 120
}
```

**에러:**
- `404 NOT_FOUND`: 해당 ID의 의류 없음
- `400 VALIDATION_ERROR`: 업로드된 이미지가 없음
- `409 CONFLICT`: 이미 처리 중인 상태 (`generating`/`rigging`/`optimizing`)

---

### GET /api/v1/garments/{garment_id}/asset-status

3D 에셋 생성 상태 조회.

**경로 파라미터:**

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| garment_id | UUID | 의류 ID |

**응답 (200 OK):**
```json
{
  "garment_id": "550e8400-e29b-41d4-a716-446655440001",
  "asset_status": "ready",
  "model_url": "/assets/garments/550e8400-e29b-41d4-a716-446655440001/660e8400-e29b-41d4-a716-446655440010.glb",
  "error_message": null,
  "updated_at": "2026-03-01T09:05:00Z"
}
```

`asset_status` 값:
- `pending`: 이미지만 업로드됨, 3D 미생성
- `generating`: TRELLIS.2 메쉬 생성 중
- `rigging`: Robust Weight Transfer 자동 리깅 중
- `optimizing`: Draco/KTX2 압축 최적화 중
- `ready`: 3D 에셋 준비 완료 (`model_url` 설정됨)
- `failed`: 생성 실패 (`error_message`에 원인 포함)

### GET /api/v1/events/asset-status (SSE, 확장)

Server-Sent Events 스트림으로 에셋 생성 상태 변경을 실시간 전달한다.

> **MVP**: 폴링 방식 (GET /api/v1/garments/{id}의 asset_status 필드, 10초 간격)으로 대체.
> SSE는 후속 최적화로 분류한다.

---

## 8. 의류 변형 API (Garment Variants)

### GET /api/v1/garments/{garment_id}/variants

특정 의류의 변형(색상/패턴/사이즈) 목록 조회.

**경로 파라미터:**

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| garment_id | UUID | 의류 ID |

**응답 (200 OK):**
```json
[
  {
    "id": "660e8400-e29b-41d4-a716-446655440010",
    "color": "white",
    "pattern": null,
    "size": "M",
    "fit_type": "regular",
    "is_default": true,
    "model_url": "/assets/garments/550e8400-e29b-41d4-a716-446655440001/660e8400-e29b-41d4-a716-446655440010.glb",
    "shoulder_width_cm": 44.0,
    "chest_cm": 96.0,
    "total_length_cm": 68.0,
    "waist_cm": null,
    "hip_cm": null,
    "sleeve_length_cm": 22.0,
    "inseam_cm": null,
    "rise_cm": null
  },
  {
    "id": "660e8400-e29b-41d4-a716-446655440011",
    "color": "white",
    "pattern": null,
    "size": "L",
    "fit_type": "regular",
    "is_default": false,
    "model_url": "/assets/garments/550e8400-e29b-41d4-a716-446655440001/660e8400-e29b-41d4-a716-446655440011.glb",
    "shoulder_width_cm": 46.0,
    "chest_cm": 100.0,
    "total_length_cm": 70.0,
    "waist_cm": null,
    "hip_cm": null,
    "sleeve_length_cm": 23.0,
    "inseam_cm": null,
    "rise_cm": null
  }
]
```

---

### POST /api/v1/garments/{garment_id}/variants (vendor|manager|admin)

의류 변형 추가. vendor/manager/admin 권한 필요.

**요청:**
```json
{
  "color": "navy",
  "pattern": "stripe",
  "size": "L",
  "fit_type": "regular",
  "is_default": false,
  "model_url": "/assets/garments/550e8400-e29b-41d4-a716-446655440001/660e8400-e29b-41d4-a716-446655440099.glb",
  "shoulder_width_cm": 46.0,
  "chest_cm": 100.0,
  "total_length_cm": 70.0,
  "sleeve_length_cm": 23.0
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| color | string | O | 색상 (1~50자) |
| pattern | string | X | 패턴 (무지, 스트라이프 등) |
| size | string | O | 사이즈 (`XS`, `S`, `M`, `L`, `XL`, `XXL`, `FREE`) |
| fit_type | string | X | 핏 타입 (`slim`, `regular`, `oversize`), 기본값 `regular` |
| is_default | boolean | X | 기본 변형 여부 (의류당 1개만 true 가능) |
| model_url | string | X | 변형별 별도 3D 모델 URL |
| shoulder_width_cm | float | X | 어깨너비 (cm) |
| chest_cm | float | X | 가슴둘레 (cm) |
| total_length_cm | float | X | 총장 (cm) |
| waist_cm | float | X | 허리둘레 (cm) |
| hip_cm | float | X | 힙둘레 (cm) |
| sleeve_length_cm | float | X | 소매길이 (cm) |
| inseam_cm | float | X | 인심 (cm, 하의용) |
| rise_cm | float | X | 밑위 (cm, 하의용) |

**응답 (201 Created):** 생성된 변형 객체 반환 (치수 필드 포함)

**에러:**
- `409 CONFLICT`: 동일 (garment_id, color, size, fit_type) 조합 중복

---

## 9. 피팅 세션 API (Fitting Sessions)

### POST /api/v1/fitting-sessions

피팅 세션 시작. 사용자가 의류를 가상 착용할 때 생성한다.

- **인증**: JWT Bearer 또는 `X-API-Key`
- `X-API-Key`로 호출된 경우 `user_id`는 NULL로 저장되며, `sdk_config_id`는 API 키로부터 결정된다.

**요청:**
```json
{
  "garment_id": "550e8400-e29b-41d4-a716-446655440001",
  "variant_id": "660e8400-e29b-41d4-a716-446655440010",
  "body_preset_id": "770e8400-e29b-41d4-a716-446655440002",
  "depth_distance_m": 1.85
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| garment_id | UUID | O | 피팅할 의류 ID |
| variant_id | UUID | X | 변형 ID (미지정 시 기본 변형) |
| body_preset_id | UUID | X | 바디 프리셋 ID |
| depth_distance_m | float | X | 카메라-사용자 거리 (m, Depth Anything V2 측정) |

**응답 (201 Created):**
```json
{
  "id": "880e8400-e29b-41d4-a716-446655440099",
  "garment_id": "550e8400-e29b-41d4-a716-446655440001",
  "variant_id": "660e8400-e29b-41d4-a716-446655440010",
  "body_preset_id": "770e8400-e29b-41d4-a716-446655440002",
  "depth_distance_m": 1.85,
  "measurement_id": null,
  "created_at": "2026-02-27T09:30:00Z"
}
```

---

### PUT /api/v1/fitting-sessions/{id}

피팅 세션 업데이트. 세션 종료 시 소요 시간과 스크린샷을 기록한다.

> `screenshot_url`은 개인정보(배경/얼굴 등)를 포함할 수 있으므로, **공개 `/assets/*` 경로에 저장하지 않는 것을 권장**한다.
> 운영에서는 private bucket + 단기 서명 URL 또는 인증이 필요한 다운로드 엔드포인트를 사용한다.

**요청:**
```json
{
  "duration_seconds": 45,
  "screenshot_url": "/assets/screenshots/session_880e8400.jpg",
  "measurement_id": "990e8400-e29b-41d4-a716-446655440001"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| duration_seconds | integer | X | 피팅 소요 시간 (초) |
| screenshot_url | string | X | 스크린샷 URL |
| measurement_id | UUID | X | 연결할 신체 측정 ID |

**응답 (200 OK):** 업데이트된 세션 객체 반환

---

### GET /api/v1/fitting-sessions

현재 사용자의 피팅 세션 이력 조회.

**쿼리 파라미터:**

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|----------|------|------|--------|------|
| page | integer | X | 1 | 페이지 번호 |
| per_page | integer | X | 20 | 페이지당 항목 수 |

**응답 (200 OK):**
```json
{
  "items": [
    {
      "id": "880e8400-e29b-41d4-a716-446655440099",
      "garment": {
        "id": "550e8400-e29b-41d4-a716-446655440001",
        "name": "기본 티셔츠",
        "thumbnail_url": "/assets/thumbnails/top_tshirt_white.jpg"
      },
      "variant": {
        "color": "white",
        "size": "M"
      },
      "duration_seconds": 45,
      "screenshot_url": "/assets/screenshots/session_880e8400.jpg",
      "created_at": "2026-02-27T09:30:00Z"
    }
  ],
  "total": 15,
  "page": 1,
  "per_page": 20
}
```

---

## 10. 즐겨찾기 API (Favorites)

### POST /api/v1/favorites (user)

의류를 즐겨찾기에 추가한다.

**요청:**
```json
{
  "garment_id": "550e8400-e29b-41d4-a716-446655440001"
}
```

**응답 (201 Created):**
```json
{
  "garment_id": "550e8400-e29b-41d4-a716-446655440001",
  "created_at": "2026-03-01T10:10:00Z"
}
```

**에러:**
- `409 CONFLICT`: 이미 즐겨찾기된 의류

---

### GET /api/v1/favorites (user)

즐겨찾기 목록을 조회한다.

**쿼리 파라미터:**

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|----------|------|------|--------|------|
| page | integer | X | 1 | 페이지 번호 |
| per_page | integer | X | 20 | 페이지당 항목 수 |

**응답 (200 OK):**
```json
{
  "items": [
    {
      "garment_id": "550e8400-e29b-41d4-a716-446655440001",
      "name": "기본 티셔츠",
      "thumbnail_url": "/assets/thumbnails/top_tshirt_white.jpg",
      "created_at": "2026-03-01T10:10:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "per_page": 20
}
```

---

### DELETE /api/v1/favorites/{garment_id} (user)

즐겨찾기에서 제거한다.

**응답 (204 No Content):** 본문 없음

---

## 11. 바디 프리셋 API (Body Presets)

### GET /api/v1/body-presets

사용 가능한 바디 프리셋 목록 조회.

**쿼리 파라미터:**

| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| gender | string | X | 성별 필터 (`male`, `female`) |

**응답 (200 OK):**
```json
[
  {
    "id": "770e8400-e29b-41d4-a716-446655440001",
    "gender": "male",
    "size": "M",
    "model_url": "/assets/body-presets/body_male_M.glb",
    "shoulder_width": 44.0,
    "chest": 92.0,
    "waist": 80.0,
    "hip": 96.0,
    "height_cm": 175.0,
    "arm_length": 60.0,
    "inseam": 78.0
  },
  {
    "id": "770e8400-e29b-41d4-a716-446655440002",
    "gender": "female",
    "size": "S",
    "model_url": "/assets/body-presets/body_female_S.glb",
    "shoulder_width": 36.0,
    "chest": 82.0,
    "waist": 64.0,
    "hip": 88.0,
    "height_cm": 158.0,
    "arm_length": 52.0,
    "inseam": 70.0
  }
]
```

---

## 12. 에셋 업로드 API (Asset Upload)

### POST /api/v1/assets/upload (vendor|manager|admin)

에셋 파일 직접 업로드. Blender 후처리 완료된 GLB 등을 직접 업로드하는 용도. 멀티파트 폼 데이터로 전송한다. vendor/manager/admin 권한 필요.

**요청:** `multipart/form-data`

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| file | file | O | 업로드할 파일 (GLB, PNG, JPG, WEBP) |
| category | string | O | 에셋 카테고리 (`garment`, `body_preset`, `thumbnail`, `screenshot`) |

**파일 크기 제한:** 최대 50MB

**응답 (201 Created):**
```json
{
  "asset_url": "/assets/garments/550e8400-e29b-41d4-a716-446655440001/880e8400-e29b-41d4-a716-446655440002.glb",
  "file_size": 1847293,
  "format": "glb",
  "uploaded_at": "2026-02-27T10:00:00Z"
}
```

**에러:**
- `413 REQUEST_ENTITY_TOO_LARGE`: 파일 크기 초과
- `415 UNSUPPORTED_MEDIA_TYPE`: 지원하지 않는 파일 형식

---

### DELETE /api/v1/assets/{asset_id} (manager|admin)

업로드된 에셋 파일을 삭제한다. 연결된 garment의 model_url이 자동으로 null로 업데이트된다.

- **권한**: manager, admin
- **응답**: 204 No Content
- **에러**: 404 (에셋 미존재), 409 (활성 피팅 세션에서 사용 중)

---

## 13. 통계 API (Stats)

### GET /api/v1/stats/fitting-sessions (vendor|manager|admin)

피팅 세션 통계 조회.

- `vendor`: 자기 브랜드 범위만 조회 가능
- `manager|admin`: 전체 또는 특정 브랜드 조회 가능

**쿼리 파라미터:**

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|----------|------|------|--------|------|
| period | string | X | `7d` | 기간 (`1d`, `7d`, `30d`, `90d`) |
| brand_id | UUID | X | - | 브랜드 스코프(선택). `vendor`는 무시되고 자기 `brand_id`로 강제된다 |

**응답 (200 OK):**
```json
{
  "total_sessions": 1523,
  "avg_duration": 38.5,
  "total_users": 342,
  "top_garments": [
    {
      "garment_id": "550e8400-e29b-41d4-a716-446655440001",
      "name": "기본 티셔츠",
      "session_count": 234,
      "avg_duration": 42.1
    },
    {
      "garment_id": "550e8400-e29b-41d4-a716-446655440005",
      "name": "슬림핏 청바지",
      "session_count": 189,
      "avg_duration": 35.7
    }
  ],
  "daily_trend": [
    { "date": "2026-02-21", "sessions": 198 },
    { "date": "2026-02-22", "sessions": 215 },
    { "date": "2026-02-23", "sessions": 243 },
    { "date": "2026-02-24", "sessions": 201 },
    { "date": "2026-02-25", "sessions": 189 },
    { "date": "2026-02-26", "sessions": 232 },
    { "date": "2026-02-27", "sessions": 245 }
  ],
  "period": "7d"
}
```

---

## 14. 신체 측정 API (Body Measurements)

### POST /api/v1/body-measurements

신체 측정 결과를 저장한다. 클라이언트에서 Depth Anything V2 + MediaPipe로 측정한 결과를 서버에 기록한다.

**요청:**
```json
{
  "session_id": "880e8400-e29b-41d4-a716-446655440099",
  "measurement_method": "depth",
  "camera_distance_m": 1.85,
  "shoulder_width_cm": 44.2,
  "chest_circumference_cm": 96.5,
  "waist_circumference_cm": 80.3,
  "hip_circumference_cm": 95.8,
  "height_cm": 175.5,
  "arm_length_cm": 60.2,
  "inseam_cm": 78.5,
  "measurement_accuracy": 87.5,
  "confidence_score": 0.92,
  "depth_model_version": "v2-metric-small"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| session_id | UUID | O | 피팅 세션 ID |
| measurement_method | string | X | 측정 방식 (`depth`, `pose_scale`, `user_input`), 기본값 `depth` |
| camera_distance_m | float | X | 카메라-사용자 거리 (m, depth 사용 시) |
| shoulder_width_cm | float | X | 어깨너비 (cm) |
| chest_circumference_cm | float | X | 가슴둘레 (cm) |
| waist_circumference_cm | float | X | 허리둘레 (cm) |
| hip_circumference_cm | float | X | 힙둘레 (cm) |
| height_cm | float | X | 키 (cm) |
| arm_length_cm | float | X | 팔길이 (cm) |
| inseam_cm | float | X | 인심 (cm) |
| measurement_accuracy | float | X | 측정 신뢰도(표시용, %, 상한 99) |
| confidence_score | float | X | 신뢰도 점수 (0~1) |
| depth_model_version | string | X | Depth 모델 버전 |

**응답 (201 Created):**
```json
{
  "id": "990e8400-e29b-41d4-a716-446655440001",
  "session_id": "880e8400-e29b-41d4-a716-446655440099",
  "measurement_method": "depth",
  "camera_distance_m": 1.85,
  "shoulder_width_cm": 44.2,
  "chest_circumference_cm": 96.5,
  "waist_circumference_cm": 80.3,
  "hip_circumference_cm": 95.8,
  "height_cm": 175.5,
  "arm_length_cm": 60.2,
  "inseam_cm": 78.5,
  "measurement_accuracy": 87.5,
  "confidence_score": 0.92,
  "depth_model_version": "v2-metric-small",
  "created_at": "2026-03-01T10:00:00Z"
}
```

---

### GET /api/v1/body-measurements/{id}

신체 측정 결과 상세 조회.

**경로 파라미터:**

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| id | UUID | 측정 ID |

**응답 (200 OK):** 측정 객체 반환 (POST 응답과 동일 형식)

**에러:**
- `404 NOT_FOUND`: 해당 ID의 측정 없음

---

### GET /api/v1/fitting-sessions/{session_id}/measurements

특정 피팅 세션의 신체 측정 이력 조회.

**경로 파라미터:**

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| session_id | UUID | 피팅 세션 ID |

**응답 (200 OK):**
```json
[
  {
    "id": "990e8400-e29b-41d4-a716-446655440001",
    "camera_distance_m": 1.85,
    "shoulder_width_cm": 44.2,
    "chest_circumference_cm": 96.5,
    "measurement_accuracy": 87.5,
    "confidence_score": 0.92,
    "created_at": "2026-03-01T10:00:00Z"
  }
]
```

---

## 15. 핏 평가 API (Fit Evaluations)

### POST /api/v1/fit-evaluations

핏 평가 결과를 저장한다.

**요청:**
```json
{
  "measurement_id": "990e8400-e29b-41d4-a716-446655440001",
  "variant_id": "660e8400-e29b-41d4-a716-446655440010",
  "fit_type": "regular",
  "suitability_pct": 87.5,
  "accuracy_pct": 92.3,
  "shoulder_diff_cm": 2.8,
  "chest_diff_cm": 3.5,
  "waist_diff_cm": -0.3,
  "hip_diff_cm": 4.2,
  "evaluation_details": {
    "shoulder": {"body_cm": 44.2, "garment_cm": 47.0, "fit": "regular"},
    "chest": {"body_cm": 96.5, "garment_cm": 100.0, "fit": "regular"},
    "waist": {"body_cm": 80.3, "garment_cm": 80.0, "fit": "slim"},
    "hip": {"body_cm": 95.8, "garment_cm": 100.0, "fit": "regular"}
  }
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| measurement_id | UUID | O | 신체 측정 ID |
| variant_id | UUID | O | 의류 변형 ID |
| fit_type | string | O | 핏 타입 (`slim`, `regular`, `oversize`) |
| suitability_pct | float | O | 종합 적합도 (%) |
| accuracy_pct | float | O | 측정 신뢰도(표시용, %, 상한 99) |
| shoulder_diff_cm | float | X | 어깨 차이 (cm) |
| chest_diff_cm | float | X | 가슴 차이 (cm) |
| waist_diff_cm | float | X | 허리 차이 (cm) |
| hip_diff_cm | float | X | 힙 차이 (cm) |
| evaluation_details | object | X | 항목별 상세 평가 (JSON) |

**응답 (201 Created):** 생성된 평가 객체 반환 (id, created_at 포함)

---

### POST /api/v1/garments/{garment_id}/evaluate-fit

특정 의류에 대해 즉석 핏 평가를 수행한다. 신체 측정 결과를 입력받아 모든 사이즈x핏 조합의 적합도를 반환한다.

- **인증**: JWT Bearer 또는 `X-API-Key`
- 본 엔드포인트는 **저장 없이 계산 결과만 반환**한다.

**경로 파라미터:**

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| garment_id | UUID | 의류 ID |

**요청:**
```json
{
  "shoulder_width_cm": 44.2,
  "chest_circumference_cm": 96.5,
  "waist_circumference_cm": 80.3,
  "hip_circumference_cm": 95.8
}
```

**응답 (200 OK):**
```json
{
  "garment_id": "550e8400-e29b-41d4-a716-446655440001",
  "recommendations": [
    {
      "variant_id": "660e8400-e29b-41d4-a716-446655440010",
      "size": "M",
      "fit_type": "regular",
      "suitability_pct": 92.3,
      "is_recommended": true
    },
    {
      "variant_id": "660e8400-e29b-41d4-a716-446655440011",
      "size": "L",
      "fit_type": "slim",
      "suitability_pct": 85.1,
      "is_recommended": false
    }
  ]
}
```

---

## 16. SDK 설정 API (SDK Configs)

### POST /api/v1/sdk/configs (vendor|manager|admin)

SDK 클라이언트 설정 생성. vendor/manager/admin 권한 필요.

**요청:**
```json
{
  "brand_id": "aa0e8400-e29b-41d4-a716-446655440001",
  "client_name": "모던웨어 쇼핑몰",
  "permissions": ["fit_evaluation", "body_measurement", "garment_catalog"],
  "rate_limit": 500,
  "allowed_origins": ["https://modernwear.co.kr", "https://www.modernwear.co.kr"]
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| brand_id | UUID | 조건부 | manager/admin은 필수. vendor는 자신의 `brand_id`가 자동 적용되며 요청 값은 무시된다 |
| client_name | string | O | 클라이언트 이름 |
| permissions | string[] | X | 허용 권한 (기본: ["fit_evaluation", "body_measurement"]) |
| rate_limit | integer | X | 분당 API 호출 제한 (기본: 1000) |
| allowed_origins | string[] | X | 허용 오리진 (기본: ["*"]) |

**응답 (201 Created):**
```json
{
  "id": "cc0e8400-e29b-41d4-a716-446655440001",
  "brand_id": "aa0e8400-e29b-41d4-a716-446655440001",
  "api_key": "af_live_abc123...",
  "api_key_prefix": "af_live_abc123",
  "client_name": "모던웨어 쇼핑몰",
  "permissions": ["fit_evaluation", "body_measurement", "garment_catalog"],
  "rate_limit": 500,
  "allowed_origins": ["https://modernwear.co.kr", "https://www.modernwear.co.kr"],
  "is_active": true,
  "created_at": "2026-03-01T09:00:00Z"
}
```

> `api_key`는 **생성 시점에만 1회** 응답으로 제공한다. 서버는 원문을 저장하지 않고 해시만 저장한다.

---

### GET /api/v1/sdk/configs (vendor|manager|admin)

SDK 설정 목록 조회. vendor/manager/admin 권한 필요.

**응답 (200 OK):**
```json
[
  {
    "id": "cc0e8400-e29b-41d4-a716-446655440001",
    "brand_id": "aa0e8400-e29b-41d4-a716-446655440001",
    "client_name": "모던웨어 쇼핑몰",
    "api_key_prefix": "af_live_abc123",
    "rate_limit": 500,
    "is_active": true,
    "created_at": "2026-03-01T09:00:00Z"
  }
]
```

---

### PUT /api/v1/sdk/configs/{id} (vendor|manager|admin)

SDK 설정 수정. vendor/manager/admin 권한 필요.

**응답 (200 OK):** 수정된 설정 객체 반환

---

### DELETE /api/v1/sdk/configs/{id} (vendor|manager|admin)

SDK 설정 비활성화 (is_active = false). vendor/manager/admin 권한 필요.

**응답 (204 No Content):** 본문 없음

---

### POST /api/v1/sdk/configs/{id}/regenerate-key (vendor|manager|admin)

API 키를 재발급한다. 기존 키는 즉시 무효화된다.

- **권한**: vendor (본인 브랜드), manager, admin

**응답 (200 OK):**
```json
{
  "api_key": "af_live_새로운키..."
}
```

> `api_key` 원문은 이때만 1회 제공된다.

---

### POST /api/v1/sdk/validate

SDK API 키 유효성 검증. JWT는 필요 없으며 `X-API-Key` 기반으로 검증한다.

**요청:**

```
X-API-Key: af_live_abc123...
Origin: https://modernwear.co.kr
```

**응답 (200 OK):**
```json
{
  "valid": true,
  "brand_id": "aa0e8400-e29b-41d4-a716-446655440001",
  "client_name": "모던웨어 쇼핑몰",
  "permissions": ["fit_evaluation", "body_measurement", "garment_catalog"],
  "rate_limit": 500
}
```

**에러:**
- `401 UNAUTHORIZED`: 유효하지 않은 API 키
- `403 FORBIDDEN`: 허용되지 않은 오리진

---

## 부록. API 사용 예시

### 상품 등록 플로우 (업체 → 3D 에셋 생성)

```bash
# 1. 로그인 (관리자)
TOKEN=$(curl -s -X POST /api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@autofit.com","password":"admin123!"}' \
  | jq -r '.access_token')

# 2. 브랜드 등록
BRAND_ID=$(curl -s -X POST /api/v1/brands \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"모던웨어","website_url":"https://modernwear.co.kr","contact_email":"biz@modernwear.co.kr"}' \
  | jq -r '.id')

# 3. 상품 등록 (brand_id 필수)
GARMENT_ID=$(curl -s -X POST /api/v1/garments \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"brand_id\":\"$BRAND_ID\",\"name\":\"기본 티셔츠\",\"category\":\"top\"}" \
  | jq -r '.id')

# 4. 상품 이미지 업로드 (다각도)
curl -s -X POST /api/v1/garments/$GARMENT_ID/images \
  -H "Authorization: Bearer $TOKEN" \
  -F "files[]=@front.jpg" \
  -F "files[]=@back.jpg" \
  -F "image_type=front"

# 5. 3D 에셋 생성 요청
curl -s -X POST /api/v1/garments/$GARMENT_ID/generate-3d \
  -H "Authorization: Bearer $TOKEN"

# 6. 에셋 생성 상태 확인 (폴링)
curl -s /api/v1/garments/$GARMENT_ID/asset-status \
  -H "Authorization: Bearer $TOKEN"

# 7. 사이즈 변형 + 실측 치수 등록
curl -s -X POST /api/v1/garments/$GARMENT_ID/variants \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"color":"white","size":"M","shoulder_width_cm":44.0,"chest_cm":96.0,"total_length_cm":68.0,"sleeve_length_cm":22.0}'
```

---

### 전체 피팅 플로우

```bash
# 1. 로그인
TOKEN=$(curl -s -X POST /api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"pass123!"}' \
  | jq -r '.access_token')

# 2. 의류 목록 조회
curl -s /api/v1/garments?category=top \
  -H "Authorization: Bearer $TOKEN"

# 3. 의류 상세 + 변형 확인
curl -s /api/v1/garments/550e8400.../variants \
  -H "Authorization: Bearer $TOKEN"

# 4. 바디 프리셋 조회
curl -s /api/v1/body-presets?gender=male \
  -H "Authorization: Bearer $TOKEN"

# 5. 피팅 세션 시작
SESSION_ID=$(curl -s -X POST /api/v1/fitting-sessions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"garment_id":"...","variant_id":"...","body_preset_id":"..."}' \
  | jq -r '.id')

# 6. 피팅 세션 종료 (소요 시간 기록)
curl -s -X PUT /api/v1/fitting-sessions/$SESSION_ID \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"duration_seconds":45,"screenshot_url":"/assets/screenshots/..."}'
```

---

### 신체 측정 + 핏 평가 플로우

```bash
# 1. 로그인
TOKEN=$(curl -s -X POST /api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"pass123!"}' \
  | jq -r '.access_token')

# 2. 피팅 세션 시작 (depth 거리 포함)
SESSION_ID=$(curl -s -X POST /api/v1/fitting-sessions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"garment_id":"...","variant_id":"...","depth_distance_m":1.85}' \
  | jq -r '.id')

# 3. 신체 측정 결과 저장
MEASUREMENT_ID=$(curl -s -X POST /api/v1/body-measurements \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$SESSION_ID\",\"camera_distance_m\":1.85,\"shoulder_width_cm\":44.2,\"chest_circumference_cm\":96.5,\"waist_circumference_cm\":80.3,\"hip_circumference_cm\":95.8,\"height_cm\":175.5,\"measurement_accuracy\":87.5,\"confidence_score\":0.92}" \
  | jq -r '.id')

# 4. 핏 평가 수행 및 저장
curl -s -X POST /api/v1/fit-evaluations \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"measurement_id\":\"$MEASUREMENT_ID\",\"variant_id\":\"...\",\"fit_type\":\"regular\",\"suitability_pct\":87.5,\"accuracy_pct\":92.3,\"shoulder_diff_cm\":2.8,\"chest_diff_cm\":3.5}"

# 5. 의류별 즉석 핏 평가 (전 사이즈 비교)
curl -s -X POST /api/v1/garments/550e8400.../evaluate-fit \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"shoulder_width_cm":44.2,"chest_circumference_cm":96.5,"waist_circumference_cm":80.3,"hip_circumference_cm":95.8}'
```

# Depth-Anything 절대 깊이 적용 가능성 검토 (2026-03-03)

대상 모델: `depth-anything/Depth-Anything-V2-Metric-Outdoor-Large-hf`

## 1) 사실 기반 요약

- 모델 카드는 Python `transformers` 사용 예시를 기본 경로로 제시한다.
- Outdoor Large 모델 크기는 `335.3M` params(F32 표기)로 고용량이다.
- Inference Provider 기본 배포가 없는 상태다.
- Indoor/Outdoor 별 metric 모델이 분리되어 제공된다.

참고: https://huggingface.co/depth-anything/Depth-Anything-V2-Metric-Outdoor-Large-hf

## 2) 브라우저 실시간 적용 판단

## 결론 (현재 시점)

- **Large(335.3M) 모델의 브라우저 실시간 직접 적용은 No-Go(고위험)**.
- 이유:
  1. 모델 용량/연산량이 크고 F32 기반이라 브라우저 메모리/지연 부담이 큼
  2. 제공 사용 예시가 Python 서버 경로 중심
  3. 본 프로젝트는 720p/실시간 UX가 핵심이라 지연 상승 시 사용자 경험 급락

## 조건부 가능 경로

- 브라우저 실시간 목표를 유지하려면 아래 선행 조건이 필요:
  - Small/Base 계열로 다운스케일
  - ONNX/WebGPU 추론 경로 및 정량화(FP16/INT8) 검증
  - 해상도 축소 입력(예: 384~512) + depth 맵 업샘플 전략

## 3) 정확도 리스크

- 현재 후보는 `Outdoor` metric 모델이며, 실내 노트북 웹캠 환경과 도메인 차이가 존재.
- 따라서 절대 깊이 수치 자체를 곧바로 cm ground truth로 쓰기보다, 초기 단계에서는 아래 용도로 제한하는 것이 안전:
  - 단면 보정(depth ratio 보정)
  - 전/후 프레임 상대적 깊이 변화 감시
  - 신뢰도 보조 지표

## 4) 권장 통합 전략 (현 프로젝트 기준)

1. **Track W 기본 유지**: `scale_cm_per_px` 기반 2D 측정(키 입력) 계속 사용
2. **Depth 보조 경로 추가**: 어깨/허리/배/엉덩이 둘레의 depth ratio를 동적으로 조정
3. **fallback 체계 유지**:
   - A: user_input (현재 기본)
   - B: world_landmark
   - C: pinhole_fallback
   - D: depth_assisted (조건 충족 시 보조)
4. **운영 정책**:
   - depth 미준비/지연 초과 시 기존 2D 경로로 즉시 복귀
   - depth 결과는 `confidence` 낮을 때만 참고값으로 사용

## 5) 구현 단계 제안

## Phase D0 (1~2일): 서버 PoC

- Python 백엔드에서 단일 이미지 depth 추론 endpoint 생성
- 기존 샘플셋으로 depth 추론 latency/메모리 측정
- 부위별 GT 대비 개선폭(둘레 MAE) 확인

## Phase D1 (2~4일): 브라우저 실시간 타당성

- Small/Base 모델 기반 브라우저 추론 PoC
- 측정 항목:
  - 평균 FPS
  - p95 latency(ms)
  - 메모리 사용량
  - 부위별 MAE 개선률

## Phase D2 (채택 시): 본선 통합

- `contracts.py`에 depth 보조 메타(`depth_source`, `depth_confidence`, `depth_latency_ms`) 확장
- `service.py` 둘레 계산 시 depth 보정 경로 추가
- `app.js` 실시간 품질 저하 감지 시 depth 경로 자동 비활성화

## 6) Go/No-Go 게이트

- Go 조건:
  - 실시간 추론 성능: 평균 15fps 이상(또는 본 측정 루프 p95 120ms 이내)
  - 둘레 MAE 개선: 기존 대비 15% 이상 개선
  - 측정 실패율 증가 없음(기존 대비 +2%p 이내)
- No-Go 조건:
  - 성능 기준 미달
  - MAE 개선 미미 또는 악화
  - 브라우저 안정성 문제(메모리 누수/프리징) 발생

## 7) 최종 판단

- 지금 즉시 Large 모델을 브라우저 실시간 본선 경로로 채택하기는 부적합.
- 현재는 **2D 키 기반 측정을 본선 유지**하고, Depth-Anything은 **서버 PoC -> 경량 브라우저 PoC -> 조건부 통합** 순으로 진행하는 것이 안전하다.

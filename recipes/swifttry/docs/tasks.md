# Tasks — SwiftTry

## Setup
- [x] Copy _template to `recipes/swifttry`
- [x] Update `recipe.yaml` with upstream info and pinned SHA
- [x] Fill out `docs/plan.md`
- [x] Fill out `docs/context.md`
- [x] Set `.claude/last_recipe.txt` to swifttry

## Implementation
- [x] Create `requirements_opt2_modern.txt` (Colab 기본 유지, 없는 것만 설치)
- [x] Create `requirements_opt1_legacy.txt` (upstream-pinned fallback)
- [x] Write `install.sh` with opt2 default + verification
- [x] Write `run.sh` with env-var-driven data paths
- [x] Create `patches/fix_diffusers_compat.py` — 5 breaking import fixes for diffusers 0.36
- [x] Write `notebook_manifest.yaml` with all required cells
- [x] Enhance `generate_notebook.py` to support `cells` list format + --recipe/--out flags
- [x] Generate `outputs/notebooks/swifttry.ipynb`
- [x] Add demo section G (auto-download 1 sample from HF TikTokDress)

## Colab Compat Fixes
- [x] Remove numpy<2.0 pin (torch 2.9 ABI requires numpy 2.x)
- [x] Remove scipy/scikit-learn/tqdm/Pillow version pins (use Colab defaults)
- [x] Fix torchsde==0.2.5 → >=0.2.6 (pip metadata bug)
- [x] Remove diffusers pin → use Colab 0.36.0 + patch
- [x] Remove CLIP GitHub zip → use open-clip-torch + ftfy

## Visual Artifact Fixes
- [x] H-3: repaint blur 축소 — `sed -i` 로 inference.py의 `kernal_size = h // 50` → `kernal_size = 3`
- [x] H-2: 얼굴 링 아티팩트 수정 — `face_exclude` dilation(15) + clothing_mask 보호
- [x] H-2 v2: SegFormer→DWPose 키포인트 기반 SAM2 프롬프팅 (실패 — SAM2 구조적 한계)
- [x] H-2 v3: SAM2 완전 제거 → SegFormer 퍼-프레임 시맨틱 세그멘테이션 교체

## Garment Shrink Fix
- [x] H-2: 마스크 과보상 제거 — consensus mask, binary_closing 삭제, dilation 12→5
- [x] H-3: kernal_size sed 패치 삭제 (업스트림 기본값 h//50 유지)
- [x] H-2: STICK_WIDTH 파라미터 추가 (4/8/12/16 Colab form)
- [x] H-2: stickwidth 변경 시 DWPose 프레임 자동 재생성
- [x] context.md: 과보상 제거 + stickwidth 파라미터화 기록

## Garment Shrink Fix v2
- [x] H-3: REPAINT_KERNEL 파라미터 추가 (1/3/5/10 Colab form) + sed 패치 복원
- [x] H-2: consensus 마스크 공간 제한 — median→connected components→largest bbox
- [x] context.md: stickwidth 무효 기록, REPAINT_KERNEL/consensus bbox 결정 기록
- [x] H-3: REPAINT_KERNEL 기본값 3→1 (하드엣지 — 가상옷 크기 최대 보존)
- [x] H-2: 얼굴/목 영역 제외 — face label(11) dilation(H*0.07) 차감
- [x] context.md: 목 제외 + REPAINT_KERNEL=1 결정 기록

## Mask Mismatch Fix (model input vs repaint)
- [x] SwiftTry 소스 분석 — prepare_mask_and_masked_image() binarize vs repaint() 연속값 경로 확인
- [x] H-2.5: 마스크 품질 진단 셀 — mp4 round-trip gray 오염, 면적 차이, 히스토그램, 시각화
- [x] H-3: REPAINT_BINARIZE + MASK_RESIZE_NEAREST 옵션 추가 (Python patching, git checkout 멱등성)
- [x] H-3: sed 방식 → Python re.sub/replace 방식으로 교체 (복잡한 패치 지원)
- [x] context.md: 마스크 경로 불일치 근본 원인 분석 + Fix 결정 기록
- [ ] Colab 테스트: H-2.5 진단 → 가설 검증 (예/아니오)
- [ ] Colab 테스트: Fix 적용 후 가상옷 수축 개선 확인

## Mask Precision PRs

### PR-1: Debug Dump + Metrics
- [x] H-2: DEBUG_DUMP 파라미터 추가
- [x] H-2: dump_mask(), dump_overlay(), compute_metrics() 헬퍼 함수
- [x] H-2: 파이프라인 각 단계에 dump 호출 삽입
- [x] H-2: metrics.json 저장 (leakage, face_intrusion, hole_rate, temporal_iou, flicker_score)
- [ ] Colab 테스트: DEBUG_DUMP=True → metrics.json 확인

### PR-2: Person Bbox AND + Pose Hull AND
- [x] H-2: DWPose 내부 API로 person bbox/keypoints 추출 (Step 1)
- [x] H-2: make_person_bbox_mask(), make_upper_body_hull_mask() 헬퍼
- [x] H-2: Step 1.5 — person mask 계산
- [x] H-2: per-frame 루프에 PERSON_BBOX_AND / POSE_HULL_AND 적용
- [ ] Colab 테스트: leakage_outside_person 지표 개선 확인

### PR-3: Hood Merge + Face/Hair/Neck Exclude
- [x] H-2: HOOD_MERGE, SCARF_MERGE, HAIR_EXCLUDE, FACE_EXCLUDE_MODE 파라미터
- [x] H-2: SegFormer 배치에서 hat/scarf/hair/upper 마스크 수집
- [x] H-2: Step 2.1 — 조건부 hood/scarf 합성 (upper-clothes 인접 hat만)
- [x] H-2: DWPose face keypoints → 타원 근사 제외
- [x] H-2: hair exclude 추가
- [ ] Colab 테스트: face_intrusion 지표 개선 + hood 커버리지 확인

### PR-4: Temporal Smoothing + Morphology 파라미터화
- [x] H-2: TEMPORAL_WINDOW, MORPH_CLOSE_KERNEL, DILATION_ITER Colab form 파라미터
- [x] H-2: temporal window 가변, binary_closing 옵션, dilation 가변
- [x] metrics에 flicker_score 추가
- [ ] Colab 테스트: TEMPORAL_WINDOW 3→5 비교

### PR-5: 2-Mask 전략
- [x] H-2: DUAL_MASK, UNET_EXTRA_DILATION, COMP_DILATION, SEAM_BAND_PX 파라미터
- [x] H-2: Step 2.7 — unet_agnostic(broader) + comp_garment(tighter) 마스크 분리 생성
- [x] H-3: USE_COMP_MASK_REPAINT 파라미터 + repaint 경로 패치
- [ ] Colab 테스트: DUAL_MASK=True → 가상옷 수축 개선 확인

## Mask v2 — Edge-Aware Refinement + 근본 원인 수정

### Phase 1: Consensus 긴급 수정
- [x] H-2: CONSENSUS_PAD_X 파라미터 추가 (0.20→0.08 기본값)
- [x] H-2: CONSENSUS_THRESHOLD 파라미터 추가 (0.30→0.45 기본값)
- [ ] Colab 테스트: consensus bbox 범위 축소 확인

### Phase 2: Edge-Aware Dilation
- [x] H-2: EDGE_DILATION, EDGE_DILATION_MAX, EDGE_THRESHOLD 파라미터 추가
- [x] H-2: cv2.Canny edge barrier + iterative expansion 알고리즘 구현
- [x] H-2: uniform dilation fallback 유지 (EDGE_DILATION=False)
- [ ] Colab 테스트: 1-2cm 삐져나옴 개선 확인

### Phase 3: 반팔 팔 대칭성 보정 + 가먼트 소매 적응
- [x] H-2: ARM_SYMMETRY 파라미터 추가
- [x] H-2: person bbox 중앙 기준 좌우 면적 비교 + 수평 반전 union
- [x] H-2: GARMENT_ADAPTIVE_ARMS — 타겟 가먼트 SegFormer 추론으로 소매 길이 자동 판정
- [x] H-2: 긴팔 판정 시 arm(14/15) 전체 raw_masks 주입
- [x] H-2: SLEEVE_ARM_MERGE — upper-clothes 인접 arm 픽셀 조건부 포함
- [x] H-2: CONSENSUS_MODE="interior" — consensus 내부 전용 적용
- [ ] Colab 테스트: 긴팔 가먼트 + 반팔 영상 → 팔 전체 마스킹 확인
- [ ] Colab 테스트: 반팔 가먼트 → 반팔 영역만 마스킹 확인

## Mask v3 — DWPose-Guided Pipeline

### Step 1: DWPose hull 기본 활성화 + pre-filter
- [x] POSE_HULL_AND 제거 → HULL_MASK=True + HULL_EXPAND_PX=15 파라미터 추가
- [x] Step 1.5에서 HULL_MASK 사용 (expand_px=HULL_EXPAND_PX)
- [x] SegFormer 추론 후, consensus 전에 hull pre-filter 적용 (raw_masks × hull)

### Step 2: Consensus 버퍼를 DWPose hull로 교체
- [x] CONSENSUS_MODE="hull" 추가 (기본값으로 설정)
- [x] DWPose hull을 consensus 버퍼로 사용 (fallback: contour convex hull)
- [x] 기존 "interior"/"union"/"off" 모드 유지

### Step 3: Dilation 최소화
- [x] DILATION_ITER: 3→1
- [x] EDGE_DILATION: True→False (기본)

### Step 4: v2 실패 코드 정리
- [x] POSE_HULL_AND 모든 참조 제거 → HULL_MASK로 대체
- [x] post-dilation hull AND 제거 (pre-filter가 대체)
- [x] 듀얼 마스크 POSE_HULL_AND → HULL_MASK 참조 갱신

### Step 5: 파라미터 정리 + 문서
- [x] context.md: v3 전략 결정 + SAM2 재평가 기록
- [x] tasks.md: v3 섹션 추가
- [ ] Colab 테스트: HULL_MASK=True + CONSENSUS_MODE="hull" → 배 구멍 해결 확인
- [ ] Colab 테스트: hull pre-filter + DILATION_ITER=1 → 외곽 overflow 개선 확인
- [ ] Colab 테스트: GARMENT_ADAPTIVE_ARMS → 긴팔/반팔 적응 확인

## Mask v4 — v3 롤백 + SAM2 Image Predictor

### Part A: v3 롤백
- [x] HULL_MASK True→False, DILATION_ITER 1→3, CONSENSUS_MODE "hull"→"interior", EDGE_DILATION False→True
- [x] v3 코드 비활성화만 (삭제 X) — 수동 활성화 가능

### Part B: SAM2 Image Predictor
- [x] B-1: MASK_ENGINE + SAM2_MODEL Colab form 파라미터 추가
- [x] B-2: Cell C에 `!pip install -q sam2` 추가
- [x] B-3: SAM2 Step 2 분기 (if/elif) — SAM2ImagePredictor.from_pretrained + per-frame predict
- [x] B-4: sam2_mode 후처리 조건부 가드 (hull pre-filter, hood/scarf merge, hair exclude)
- [x] B-5: Garment-adaptive arms — SAM2 시 SegFormer 1-shot + wrist negative 제어
- [x] UI 문자열 업데이트 (셀 제목, 요약, 시각화 라벨)
- [x] docs 업데이트 (context.md, tasks.md)
- [x] YAML 검증 + 노트북 재생성 + smoke_test
- [ ] Colab 테스트: MASK_ENGINE="segformer" → v2 동작 확인
- [ ] Colab 테스트: MASK_ENGINE="sam2" → 마스크 의류 형태, 얼굴 제외 확인

### Phase 4: SAM3 실험 (미래)
- [ ] SAM3 안정화 확인 후 MASK_ENGINE에 "sam3" 옵션 추가
- [ ] SAM3 텍스트 프롬프트 경로 구현

### Documentation
- [x] context.md: SAM2/SAM3 리서치 결과 기록
- [x] context.md: edge-aware dilation, consensus 수정, arm symmetry 결정 기록
- [x] tasks.md: Edge-Aware Refinement 섹션 추가

## Performance v5 — H100 최적화 + SegFormer 폐기

### SegFormer 폐기
- [x] MASK_ENGINE 기본값 "segforter"→"sam2", segformer 옵션 제거
- [x] context.md: SegFormer 폐기 결정 기록

### DWPose 이중 호출 제거
- [x] draw_bodypose() 직접 호출 시도 → 실패 (시그니처 불일치: candidate/subset 구조)
- [x] detector(pil) 시각화 유지 + inference_detector()+pose_estimation() bbox/kps 추출
- [x] pose 프레임 저장 async I/O로 전환

### scipy→OpenCV 후처리
- [x] binary_dilation→cv2.dilate, binary_fill_holes→cv2.floodFill
- [x] binary_closing→cv2.morphologyEx, ndimage_label→cv2.connectedComponents
- [x] make_upper_body_hull_mask의 scipy import 제거
- [x] compute_metrics의 scipy import 제거
- [x] cv2_fill_holes 버그 수정: (0,0) 단일 flood → 4-corner flood (마스크 깜빡임 해결)
- [x] cv2_label connectivity 수정: 8-conn(cv2 기본) → 4-conn(scipy 기본 일치)

### 비동기 I/O
- [x] ThreadPoolExecutor(4 workers) 프레임 저장 async
- [x] Step 3 전 flush + masked frames async
- [x] 검증 전 pool shutdown

### H100 CUDA 최적화
- [x] cudnn.benchmark=True, allow_tf32=True
- [x] SAM2 model.half() + torch.autocast FP16
- [x] GPU 이름 감지 출력

### 타이밍 계측
- [x] Step 1 (DWPose), Step 2 (SAM2), Post-processing, Step 3 (Video) 각각 time.time()
- [x] 파이프라인 종료 시 타이밍 요약 출력

### SAM2 모드 조정
- [x] DILATION_ITER cap 제거: min(val, 1) → form 값 그대로 (기본 3)

### 추론 모델 캐싱 (H-3)
- [x] 1차 시도 → 실패: clip_length 미설정으로 1 clip(16f)만 처리
- [x] 1차 실패 후 subprocess 복원
- [x] inference.py upstream 분석: __main__이 clip_length=10000 전달 → tryon_video() 내부에서 clamp → 전체 프레임 처리. 슬라이딩 윈도우는 TryOnVideoPipeline.__call__() 내부 context_scheduler가 처리
- [x] 2차 구현: Pipeline Transplant 전략 — 모듈 reimport(패치 반영) + GPU pipeline 객체 이식
- [x] globals()에 _swifttry_controller 캐싱, 재실행 시 _cached_pipeline 이식으로 모델 로딩 스킵
- [x] clip_length=10000으로 전체 비디오 처리 (upstream __main__과 동일)
- [x] CWD 보존 (config 상대 경로 해석용 os.chdir + finally 복원)
- [ ] Colab 테스트: 첫 실행 모델 로딩 + 추론 정상 확인
- [ ] Colab 테스트: 재실행 시 "캐시된 파이프라인 발견" 메시지 + 로딩 스킵 확인

### 검증
- [ ] Colab: 타이밍 출력 확인
- [ ] Colab: SAM2 FP16 마스크 품질 확인
- [ ] Colab: OpenCV 후처리 마스크 품질 확인
- [ ] Colab: 모델 캐싱 재실행 테스트

## Validation
- [x] Run `compileall` — no syntax errors
- [x] Run `smoke_test.py` — passes
- [x] Verify notebook has all required cell groups (A–G)
- [x] Update context pack

---

> **Rule**: Check off each task immediately upon completion.
> Every decision made during implementation must be recorded in `context.md` → "Key Decisions".

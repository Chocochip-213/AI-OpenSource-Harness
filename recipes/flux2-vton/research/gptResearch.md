# FLUX.2 Klein 9B 기반 사이즈-컨트롤 가상 피팅(VTON) 추가 설계 리서치

## 문제 정의와 현재 제약이 만드는 구조적 한계

FLUX.2 Klein 9B는 텍스트→이미지뿐 아니라 “멀티 레퍼런스(다중 입력 이미지) 편집/생성” 능력을 갖는 것으로 공식 모델 카드에서 명시됩니다. 또한 9B rectified flow 기반에 Qwen3 계열(8B) 텍스트 임베더를 사용하고, 4-step로 step-distilled 되어 저지연 고품질을 목표로 설계되었다고 설명됩니다. citeturn3view0 다만 이 “멀티 레퍼런스 편집”은 **마스크 기반 인페인팅 인터페이스(= mask_image)를 당연히 제공하는 SD 계열 파이프라인과 동일한 형태**라고 보장되지는 않습니다.

엔지니어가 겪는 핵심 병목은 사용자 관찰(“VTON LoRA가 항상 perfectly fitted로 수렴”)과 맞물려, **사이즈(핏)라는 ‘기하/레이아웃’ 변수를 텍스트로만 안정적으로 지정할 수 없는 구조**입니다. 최근 사이즈 제어를 다룬 연구들은 공통적으로 “사이즈=마스크/레이아웃/경계 조건을 바꿔야 한다”로 귀결됩니다(아래 ‘문헌 기반 메커니즘’ 참고). citeturn11view1turn13view2turn19view0

또 하나의 실무 제약은, 적어도 공개된 diffusers 이슈 트래킹 상으로는 **Flux2KleinPipeline에 mask image를 넘기는 표준 inpaint 파이프라인이 아직 없다는 점**입니다(“mask image를 pass할 옵션이 없다”는 요청 이슈). citeturn4search2 즉, “마스크 크기를 바꿔 인페인팅으로 영역을 ‘덮는 면적’을 제어”하는 전통적인 SD 인페인팅식 접근은 **그대로는** 적용이 어렵고, ComfyUI에서의 우회(크롭-스티치, 마스크-가이드 재생성 등)가 필요해집니다. citeturn4search23turn23view1

마지막으로 “네거티브 프롬프트/프롬프트 가중치 문법으로 핏을 밀어붙이기”는, FLUX.2 계열에서 공식 가이드가 “negative prompts를 지원하지 않는다”는 입장을 밝히고 있어(특히 pro/max 가이드) 기댈 수 있는 레버가 제한됩니다. citeturn4search4 (일부 서드파티 튜토리얼은 negative prompt를 언급하지만, 실제 효과/지원 범위가 일관적이지 않은 사례가 보고되어 왔습니다. citeturn4search0)

## 왜 “사이즈 제어”는 프롬프트가 아니라 마스크·레이아웃 제어로 귀결되는가

사이즈(예: M/L/XL/2XL)는 결과 이미지에서 **옷의 길이(CL), 소매 길이(SL), 어깨 폭(SW), 허리/밑단 폭(WW)** 같은 치수의 변화로 나타납니다. SV-VTON은 diffusion 기반 VTON에서 “의복 워핑(결국 결과의 길이·헐렁함)은 입력 조건 중 ‘마스크 형태’에 의해 크게 결정된다”는 전제를 명시하고, 단일 ‘타이트/루즈’ 마스크로 학습된 모델이 **단일 핏으로 쏠리는 현상**을 문제로 제기합니다. citeturn10view0turn11view1 그리고 사이즈를 만들기 위해 (a) 마스크 자체를 팽창/연장시키거나, (b) 의복 이미지 비율(스케일)을 바꾸는 두 축을 실험적으로 분리해 영향을 분석합니다. citeturn11view3

SiCo는 더 직접적입니다. 이 시스템은 사용자가 선택한 사이즈와 “진짜 사이즈(true size)” 간의 차이를 계산해, **마스크를 좌/우/하 방향으로 dilation 반복**하여 더 큰(더 루즈) 핏을 만들고(윗변은 ‘떠 보임’ 방지를 위해 피함), 반대로 더 작은(타이트) 핏은 **밑단을 trim**하는 규칙 기반 마스크 생성기를 사용합니다. citeturn13view2 즉, 사이즈 제어를 “프롬프트 의미”가 아니라 **마스크 기하 조작**으로 구현합니다.

FitControler는 “fit-aware VTON”을 별도 문제로 정의하고, 목표 핏 라벨/프롬프트에 맞는 **body–garment layout(분할/레이아웃)을 먼저 재생성**한 뒤, 그 레이아웃을 멀티스케일로 주입해 VTON 모델이 레이아웃을 따라 렌더링하도록 설계합니다. citeturn19view0turn20view0 결론적으로 최신 연구들의 합의는 “핏은 레이아웃”이며, **레이아웃을 강제하는 제어 신호(마스크/세그/경계/포즈 등)** 없이는 “항상 적당히 맞는 옷”으로 붕괴하기 쉽다는 방향으로 모입니다. citeturn10view0turn13view2turn19view0

image_group{"layout":"carousel","aspect_ratio":"16:9","query":["DensePose body segmentation visualization","virtual try-on garment mask example","thin plate spline garment warping example","ControlNet canny edge guidance example"],"num_per_query":1}

## FLUX.2 Klein 9B 위에 “추가”로 얹을 수 있는 우선순위 높은 실무 해법

아래 항목들은 “FLUX.2 Klein 9B + VTON LoRA”를 베이스로 유지하면서, **사이즈 변별을 ‘입력 조건’ 쪽에서 강제**하는 접근들입니다. 각 항목은 “정말로 M vs L vs XL vs 2XL이 눈에 띄게 갈릴 것인가?”를 중심으로 평가합니다.

### 마스크-기반 사이즈 컨트롤을 ComfyUI 우회 인페인팅으로 구현

1) **방법/링크:** “SiCo식 마스크 팽창/절단 + (ComfyUI) 크롭-스티치형 마스크 인페인팅 우회” citeturn13view2turn4search23turn4search2  
2) **사이즈 제어 메커니즘:**  
SiCo처럼 사이즈 인덱스 차이(예: true=L, 선택=2XL)를 \(\Delta\)로 두고, \(\Delta>0\)이면 의복 영역 마스크를 좌/우/하 방향으로 반복 dilation하여 “헐렁함+기장 증가”를 만들고, \(\Delta<0\)이면 밑단을 잘라 기장을 줄이는 식으로 “타이트/쇼트”를 만듭니다. citeturn13view2 이 마스크로 인페인팅을 해야 하는데, Flux2KleinPipeline이 mask를 직접 받지 않으므로, 커뮤니티에서 쓰는 크롭-스티치 기반 워크플로(마스크 영역만 잘라 고해상도 편집 후 재합성) 같은 우회가 필요합니다. citeturn4search23turn4search2  
3) **FLUX.2 Klein 9B 호환성:** 애드온 가능(모델 교체 불필요). 단, “파이프라인 내부 mask 인자”가 없으므로 **ComfyUI/LanPaint 레벨의 우회가 사실상 필수**입니다. citeturn4search2turn4search23  
4) **구현 난이도:** 중~상(마스크 생성+세그/키포인트+ComfyUI 워크플로 통합). citeturn13view2turn4search23  
5) **정직한 평가:** “면적(coverage)·기장”은 가장 확실히 바뀝니다. M↔2XL 같은 큰 간격은 **가시적 변별 가능성이 높음**. 다만 LoRA가 “fitted bias”가 강하면, 마스크 밖으로 옷이 ‘줄어드는’ 대신 주변 신체/배경이 바뀌는 식으로 보상할 위험이 있어, (a) 마스크 경계/컨투어를 강하게 주거나, (b) 2단계(기본 착장→가장자리 재확장)로 가는 편이 안전합니다. SiCo가 실제로 마스크 조작을 통해 핏 선택을 구현하는 점은 강한 근거입니다. citeturn13view2

### 의복 레퍼런스 “물리 워핑/스케일”을 먼저 바꿔 모델이 ‘큰 옷’을 보게 만들기

1) **방법/링크:** “SV-VTON 인사이트 기반: (a) 마스크 크기 고정 + (b) 의복 이미지 비율(스케일) 조절” citeturn11view3turn10view0  
2) **사이즈 제어 메커니즘:**  
SV-VTON은 사이즈 변별의 두 축—(i) 마스크 크기 변화, (ii) 의복 이미지 비율 변화—를 분리해 실험합니다. citeturn11view3 이를 FLUX.2 파이프라인에 이식하면, **garment_image 자체를 TPS/flow/단순 스케일로 ‘더 크게/더 길게’ 워핑**(예: 밑단 연장, 품/어깨 폭 확대)한 뒤 레퍼런스로 넣어, 모델이 “이 옷은 원래 이렇게 크다”는 시각적 조건을 받게 합니다(프롬프트 숫자 대신 픽셀 기하로 전달). SV-VTON이 “garment proportion을 바꿔도 사이즈 스타일이 달라진다”를 ablation으로 보여줍니다. citeturn11view3  
3) **FLUX.2 Klein 9B 호환성:** 애드온 가능(가장 깔끔한 형태의 “전처리”). 단, 현재 VTON LoRA가 garment_image를 얼마나 강하게 따르는지(또는 ‘항상 fitted’로 정규화하는지)에 따라 효과가 달라질 수 있습니다. SV-VTON이 여러 diffusion VTON 백본에서 일반화 가능성을 주장한 건 긍정 신호입니다. citeturn10view0turn11view3  
4) **구현 난이도:** 중(세그/키포인트 + 워핑; TPS는 상대적으로 구현 용이, flow는 중~상). citeturn10view0  
5) **정직한 평가:** 마스크 기반만큼 강력하진 않지만, “M↔2XL”처럼 큰 차이는 **레퍼런스가 충분히 강하면** 눈에 띄게 나올 수 있습니다. 다만 LoRA가 “항상 딱 맞게” 정규화한다면, 스케일 차이가 ‘질감/패턴 보존’ 쪽으로만 쓰이고 기하 차이는 줄어들 수 있습니다(이 경우 마스크 제어와 결합이 필요).

### “레이아웃 힌트 이미지”를 멀티 레퍼런스로 주입해 경계를 유도

1) **방법/링크:** “멀티 레퍼런스 편집 + 레이아웃(실루엣/세그) 힌트 이미지 추가” citeturn3view0turn6search16turn9view0  
2) **사이즈 제어 메커니즘:**  
FLUX.2 Klein은 멀티 레퍼런스 편집을 지원한다고 명시되어 있으므로, 사람 이미지/의복 이미지 외에 “목표 핏 마스크(또는 경계선·실루엣)를 컬러로 그린 힌트 이미지”를 추가 레퍼런스로 넣어 **옷의 외곽선/커버리지**를 간접 유도합니다. citeturn3view0turn6search16 API 쪽에서는 base+추가 레퍼런스 형태(최대 4장까지)가 언급된 사례가 있어, 레퍼런스 슬롯이 늘어날수록 이 전략의 실용성이 올라갑니다. citeturn9view0  
3) **FLUX.2 Klein 9B 호환성:** 애드온 가능(모델 교체 불필요). 다만 “현재 엔지니어 스택이 3장 고정 입력”이라면, 파이프라인/워크플로 수준에서 입력 이미지 개수 확장이 필요합니다(가능 여부는 구현체에 좌우). citeturn3view0turn9view0  
4) **구현 난이도:** 중(레이아웃 힌트 생성은 쉬움, 레퍼런스 입력 확장이 관건).  
5) **정직한 평가:** “완전한 경계 강제”는 어렵지만, 옷이 항상 fitted로 수렴하는 현상을 완화하고 **사이즈별 외곽선 차이를 ‘학습된 시각 단서’로 제공**한다는 점에서 유망합니다. 다만 마스크 인페인팅처럼 결정적이지 않아 변동성이 남을 수 있습니다.

### 멀티-패스 편집으로 “기본 착장→확장/축소 보정”을 분리

1) **방법/링크:** “SiCo(마스크 기반) + SV-VTON(마스크/비율 분리) 인사이트를 멀티 패스로 재구성” citeturn13view2turn11view3  
2) **사이즈 제어 메커니즘:**  
1차 패스에서 VTON LoRA로 “질감/디테일”을 최대한 안정화한 뒤, 2차 패스에서 마스크를 목표 사이즈로 조정(dilation/trim)하여 **가장자리 영역만 재생성**(혹은 확장)하여 핏을 미세 조정합니다. SV-VTON이 “마스크가 결과에 강하게 작동한다”는 전제를 두고 있고, SiCo가 마스크 조작을 실제 핏 컨트롤로 사용한다는 점이 근거입니다. citeturn11view1turn13view2  
3) **FLUX.2 Klein 9B 호환성:** 애드온 가능. 다만 2차 패스는 역시 mask 입력 부재 문제로 ComfyUI 우회가 필요합니다. citeturn4search2turn4search23  
4) **구현 난이도:** 중~상(2단계 워크플로 + 경계 아티팩트 처리).  
5) **정직한 평가:** “항상 fitted” 편향을 깨는 데 가장 실전적으로 강합니다. M/L/XL/2XL을 만들 때도 “기본 품질”과 “핏 제어”를 분리하므로 실패 모드가 줄어듭니다.

## 문헌 기반 “사이즈/핏 컨트롤” 메커니즘 카드

여기서는 “이미 검증(논문/리포)”된 메커니즘을 정리하고, FLUX.2 Klein 9B에 **그대로 붙일 수 있는지(애드온)** 혹은 **아키텍처/훈련이 필요한지**를 냉정하게 구분합니다.

### SV‑VTON

1) **방법/링크:** SV‑VTON (Diffusion Model-Based Size Variable Virtual Try-On) citeturn10view0turn11view1  
2) **사이즈 제어 메커니즘(정확):**  
- 두 단계 마스크 생성: (a) 키포인트 기반 coarse mask 생성 후, (b) Edge Attention + U2‑Net으로 거친 경계를 매끈하게 정제. citeturn11view1  
- 사이즈 증분 파라미터에 따라 dilation/closing 반복 횟수로 **헐렁함**을 키우고, 키포인트 기반 길이 제약(팔/허리 등)으로 **기장**을 늘림. citeturn11view1  
- try-on 단계에서 “멀티 사이즈 마스크 + 비율 조정된 의복 이미지”를 함께 넣어 사이즈를 구현. citeturn11view1turn11view3  
3) **FLUX.2 Klein 9B 호환성:** 개념은 매우 잘 맞지만, 논문은 diffusion VTON에서 mask를 중요한 조건으로 사용합니다. citeturn10view0turn11view1 Flux2KleinPipeline에 mask 주입이 막혀 있으므로, **(A) ComfyUI 우회 인페인팅** 혹은 **(B) 레이아웃 힌트 멀티레퍼런스**로 이식하는 형태가 현실적입니다. citeturn4search2turn3view0  
4) **구현 난이도:**  
- 애드온 이식(우회 포함): 중~상  
- 논문 그대로(모델 학습 포함): 상  
5) **정직한 평가:** 논문 목적 자체가 “같은 사람·같은 옷에서 여러 사이즈를 안정적으로 만들기”이며, 마스크/비율 두 축이 효과를 가진다는 분석이 있어 가장 직접적인 청사진입니다. citeturn10view0turn11view3 다만 FLUX.2 쪽에서 마스크를 ‘강제 조건’으로 넣는 방법이 관건입니다.

### SiCo

1) **방법/링크:** SiCo (Size-Controllable VTO) citeturn12view0turn13view2  
2) **사이즈 제어 메커니즘(정확):**  
true size와 선택 size의 차이를 계산해, 더 큰 사이즈는 마스크를 좌/우/하 방향으로 반복 dilation(윗변 제외)하고, 더 작은 사이즈는 밑단을 특정 비율로 trim합니다. citeturn13view2  
3) **FLUX.2 Klein 9B 호환성:** 논문 구현은 Stable Diffusion 인페인팅+IP‑Adapter+ControlNet 조합이지만, “사이즈=마스크 규칙”은 모델 불문 애드온으로 이식 가능성이 큽니다. citeturn12view0turn13view2 단, 역시 Klein 파이프라인의 mask 입력 부재를 ComfyUI 우회로 풀어야 합니다. citeturn4search2turn4search23  
4) **구현 난이도:** 중(규칙 기반이라 학습 부담이 낮음).  
5) **정직한 평가:** 사이즈를 “규칙 기반 마스크 조작”으로 직접 구현하므로, 가장 빠르게 MVP를 만들 수 있습니다. 다만 “국제 표준 cm 단위 정확도”까지는 보장하지 않으며, 시각적 핏 차이를 제공하는 HCI(의사결정 지원) 성격이 강합니다. citeturn12view0turn13view2

### FitControler

1) **방법/링크:** FitControler (fit-aware VTON 플러그인) citeturn19view0turn20view0  
2) **사이즈 제어 메커니즘(정확):**  
- “fit-aware layout generator”가 fit 라벨에 맞는 body–garment 레이아웃(세그/레이아웃 이미지)을 먼저 예측하고 citeturn19view0  
- “multi-scale fit injector”가 그 레이아웃 특성을 기존 VTON 모델의 멀티스케일 특징에 주입하여, **레이아웃-드리븐**으로 착장 이미지를 생성하게 합니다. citeturn19view0turn20view0  
- 여러 VTON 모델(StableVITON, IDM-VTON, CatVTON 및 그 FLUX 변형 등)로의 통합 실험을 보고합니다. citeturn20view0turn20view1  
3) **FLUX.2 Klein 9B 호환성:** “개념적 호환성”은 높지만, 구현은 기존 diffusion VTON의 UNet/DiT 내부에 주입 모듈을 붙이는 형태라 **Flux2KleinPipeline을 거의 개조/재훈련 수준으로 다뤄야 할 가능성**이 큽니다. (논문은 FLUX.1 백본까지 커버했다고 명시하지만 FLUX.2 Klein에 대한 직접 검증은 별도입니다.) citeturn20view0  
4) **구현 난이도:** 상(학습+아키텍처 개입).  
5) **정직한 평가:** 제대로 붙이면 “fit 프롬프트(라벨)→레이아웃→렌더링”이 분리돼 가장 안정적인 컨트롤이 기대됩니다. 하지만 “FLUX.2 Klein 증류 4-step + VTON LoRA 스택” 위에 바로 얹기는 난도가 매우 높습니다.

### QuantFit‑VTON

1) **방법/링크:** QuantFit‑VTON (Measurement‑Conditioned Diffusion, IEEE Access 2026로 표기) citeturn22search0  
2) **사이즈 제어 메커니즘(정확):**  
VITON‑HD를 수치 신체/의복 측정값(키, 길이, 폭 등)으로 확장하고, “Measurement Encoder”로 숫자 조건을 임베딩해 diffusion 생성에 조건으로 넣는 구조로 설명됩니다. citeturn22search0  
3) **FLUX.2 Klein 9B 호환성:** 엔지니어가 시도한 “JSON 숫자 프롬프트”가 안 먹는 이유가 바로 “숫자용 조건 인코더가 없기 때문”인데, QuantFit‑VTON은 그 부분을 **아키텍처로 해결**하는 방향입니다. citeturn22search0 즉, **애드온만으로는 어렵고, 최소한 별도 컨디셔닝 모듈+파인튜닝**이 필요할 가능성이 큽니다.  
4) **구현 난이도:** 매우 상(데이터/훈련/조건 인코더).  
5) **정직한 평가:** “cm 단위 예측 가능/재현성”을 목표로 하는 방향이라 장기적으로 가장 정답에 가깝습니다. 다만 “FLUX.2 Klein 9B + 기존 VTON LoRA” 위에 즉시 덧대는 해법은 아닙니다.

### CAT‑DM

1) **방법/링크:** CAT‑DM (CVPR 2024) + 공개 코드 citeturn15search3turn15search11  
2) **사이즈 제어 메커니즘(정확):**  
논문은 “controllability”를 위해 ControlNet으로 추가 제어 조건(포즈/구조 등)을 주입하고, 동시에 샘플링을 가속하는 전략을 제안합니다. citeturn15search3  
3) **FLUX.2 Klein 9B 호환성:** 직접적인 “사이즈” 방법은 아니지만, **경계/포즈/구조 제어를 강하게 걸 수 있으면 핏 변별을 도울 수** 있습니다. 다만 CAT‑DM 자체는 별도 아키텍처/모델이므로, FLUX.2 Klein 애드온이라기보단 “하이브리드/대체 파이프라인” 영역입니다. citeturn15search3turn15search11  
4) **구현 난이도:** 상(별도 모델).  
5) **정직한 평가:** “핏=레이아웃” 관점에서는 유용한 부품이지만, 질문의 목표(FLUX.2 Klein 유지)에 대해선 직접 해답이 아닙니다.

### Better Fit

1) **방법/링크:** Better Fit: Adaptive mask training paradigm (arXiv 2024) citeturn14search0turn14search4  
2) **사이즈 제어 메커니즘(정확):**  
논문 요지는 “원래 옷/타깃 옷 종류가 다를 때도 잘 맞추려면 학습 마스크를 동적으로 조정(adaptive mask)하여 try-on 영역과 원복 의존성을 끊어야 한다”입니다. citeturn14search0turn14search4  
3) **FLUX.2 Klein 9B 호환성:** “학습 시 마스크 다양화” 아이디어는 SV‑VTON과도 결이 맞고, 결과적으로 “항상 fitted로 수렴” 같은 편향을 완화하는 방향입니다. citeturn14search0turn10view0 다만 이 역시 **훈련/재학습** 성격이 강합니다.  
4) **구현 난이도:** 상(훈련 필요).  
5) **정직한 평가:** 단기간 애드온보다는, “차세대 LoRA/파인튜닝”에서 마스크 다양화를 넣는 설계 근거로 유효합니다.

## 하이브리드 파이프라인: FLUX.2를 품질 백본으로 두면서 ‘제어 모델’을 옆에 붙이기

### FLUX.2‑dev ControlNet‑Union을 “레이아웃 생성기”로만 사용하고 Klein으로 렌더링

현재 공개된 FLUX.2 계열 ControlNet 중 확인 가능한 것은, entity["company","Alibaba-PAI","alibaba ai platform"]가 공개한 **FLUX.2‑dev 전용** “Fun Controlnet Union” 계열입니다. 이 모델 카드는 Canny/HED/Depth/Pose/MLSD/Scribble/Gray 등 다중 컨트롤을 지원하고, inpainting mode도 지원하며, controlnet_conditioning_scale을 0.65~0.80 범위에서 권장한다고 명시합니다. citeturn23view0 또한 이를 ComfyUI에서 쓰기 위한 커스텀 노드(entity["company","GitHub","code hosting platform"] 기반 리포)도 공개되어 있고, 해당 노드는 Flux.2‑dev 베이스 모델을 요구한다고 적혀 있습니다. citeturn23view1

이 사실이 의미하는 실무 옵션은 다음입니다.

1) **옵션:** Flux.2‑dev + ControlNet‑Union으로 “목표 핏 경계(예: 포즈+컨투어 기반)”를 강하게 따르는 **저해상 레이아웃/가이드 결과**를 먼저 만든 뒤,  
2) 그 결과를 (a) 레이아웃 힌트 이미지, (b) 워핑된 garment reference, (c) 사람 이미지와 함께 FLUX.2 Klein 9B + VTON LoRA에 멀티 레퍼런스로 넣어 **고품질 렌더링**을 유도합니다.  
3) 이렇게 하면 “Klein을 베이스로 유지”하면서도, 사이즈 차이를 만드는 데 필요한 “강한 구조 제어”를 옆 모델에서 확보할 수 있습니다. (다만 dev 모델을 함께 쓰므로 운영 복잡도가 커집니다.) citeturn23view0turn23view1turn3view0

**정직한 평가:** 이 하이브리드는 “정확한 경계 제어”는 강해질 수 있으나, 최종 Klein 렌더 단계에서 경계가 다시 무너질 위험이 있습니다(특히 VTON LoRA가 fitted로 끌어당길 때). 즉 “완전한 강제”는 아니고, **레이아웃 힌트를 강화하는 단계**로 보는 게 맞습니다.

## 권장 실행 로드맵과 “정말 M/L/XL/2XL이 갈리는가”에 대한 냉정한 전망

### 가장 빠른 실험 순서

1) **SiCo식 마스크 생성기부터 만들기**  
- true size 대비 선택 size 차이를 \(\Delta\)로 두고, \(\Delta>0\): 좌/우/하 dilation 반복, \(\Delta<0\): 밑단 trim. (SiCo 규칙을 그대로 MVP로 사용) citeturn13view2  
- 이때 “상의/하의/원피스” 등 카테고리별로 dilation 방향/가중치를 달리 주는 것이 중요합니다(상의는 어깨·품, 하의는 허벅지·밑위/기장). SiCo도 의복 메타데이터를 별도로 저장/활용한다고 밝힙니다. citeturn13view3  

2) **ComfyUI 우회 인페인팅 워크플로에 마스크를 연결**  
- Flux2KleinPipeline이 mask 인자를 받지 못한다는 제약이 명시되어 있으므로, citeturn4search2  
- 커뮤니티에서 쓰는 크롭-스티치 방식(마스크 영역 크롭→생성→스티치) 같은 우회를 기반으로 “마스크 크기 변화가 곧 coverage 변화”로 이어지는지 먼저 검증합니다. citeturn4search23  

3) **SV‑VTON의 ‘두 개의 노브’를 그대로 실험 설계로 채택**  
- 노브 A: 마스크 크기/형태(헐렁함·기장)  
- 노브 B: garment reference 비율(스케일/기장 워핑)  
SV‑VTON이 ablation에서 이 둘을 분리해 영향을 본다는 점은, 지금 스택에서도 “어떤 레버가 실제로 먹히는지”를 빠르게 진단하는 데 유용합니다. citeturn11view3turn11view1  

### “보이는 차이”를 객관화하는 평가 루프

SV‑VTON은 사이즈 증분을 평가하기 위해 CL/SL/SW/WW 네 치수의 증가량을 측정하고, 국제 표준 증분(예: 3cm, 1cm, 2cm, 3cm)을 기준으로 오차를 계산하는 평가 모듈을 제안합니다. citeturn11view3 이 아이디어는 FLUX.2 기반 시스템에도 그대로 이식 가능합니다. 즉, “프롬프트로 숫자를 넣는 것”이 아니라, **생성 결과에서 실제로 숫자가 나오도록** 닫힌 루프를 만드는 것입니다.

- 실무적으로는 (a) 사람이미지 스케일 보정(키포인트 간 거리로 픽셀→cm 근사), (b) 의복 영역 세그/마스크 기반 치수 측정, (c) 사이즈별 기대 증분에 맞게 마스크 dilation·기장 연장 계수를 자동 튜닝하는 식의 “캘리브레이션”이 가능합니다. (SV‑VTON도 픽셀 공간→물리 공간 매핑을 논합니다.) citeturn11view2turn11view3  

### 최종 전망

- **프롬프트만으로 M/L/XL/2XL을 안정적으로 갈라내는 것**은, 최신 사이즈 컨트롤 VTON 연구들이 공통적으로 “레이아웃/마스크/컨디션”을 조작하는 방향으로 해결하고 있다는 점에서 구조적으로 불리합니다. citeturn10view0turn13view2turn19view0  
- 반면, **마스크(coverage)와 의복 레퍼런스 스케일(garment proportion)을 입력 조건으로 강제**하면, 최소한 “기장/품”에서 확실한 시각적 차이를 만들 가능성이 높습니다(특히 M↔2XL처럼 큰 간격). 이는 SiCo의 규칙 기반 마스크 컨트롤과, SV‑VTON의 마스크/비율 기반 분석이 강한 근거입니다. citeturn13view2turn11view3  
- “cm 단위 정확/재현성”까지 요구하면, QuantFit‑VTON처럼 **측정값 전용 컨디셔닝 인코더 + 재훈련** 영역으로 넘어갈 공산이 큽니다. citeturn22search0  
- 장기적으로 가장 설득력 있는 아키텍처 방향은 FitControler류의 “fit-aware layout 생성 → layout-driven 렌더링” 분리이며, 이 라인을 FLUX.2 Klein 9B로 옮기려면 (1) 레이아웃 생성기는 외부 모듈로 두고, (2) Klein에는 ‘레이아웃 힌트 멀티레퍼런스+마스크 우회 인페인팅’을 병행하는 **혼합 설계**가 현실적입니다. citeturn19view0turn3view0turn4search2

(참고로, FLUX.2 Klein 9B는 모델 카드에서 비상업 라이선스로 표기되어 있어 배포/상용화 계획이 있다면 라이선스 검토가 필요합니다. citeturn3view0)
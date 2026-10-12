# T12 v2 — PROTOCOL LOCK (`T12v2-lock-1`, 2026-10-12)

이 프로토콜은 **실 ETF 데이터로 T12 를 한 번도 실행하기 전에** 고정했다. 설정 원본은 `configs/t12_annual_expanding_v2.json` 이다. 이후 바뀌는 내용은 `PROTOCOL_CHANGELOG.md` 에 run ID 와 함께 남긴다.
상위 계약은 `R2H_T12_20ETF_Diagnostic_Master_Spec_v2.md` (v2 Part A 가 Part B 보다 우선)이다.

## L1. 시간축 · fold

- 수익률은 `r_t = 100·Δlog Close` 다 (T11 `percent_log_returns`). 공통 거래일만 쓰며 2019-01-03 ~ 2026-10-02 이다. 261240 의 2019-03-14·15 는 NaN 으로 둔다.
- 검정연도는 `y ∈ {2020..2026}` 다. 학습 이력은 `H_y` = date < y-01-01 인 유효(비결측) 수익률, 검정 구간은 `E_y` = y 달력연도의 수익률이다.
- 내부 분할은 `H_y` 의 시간순 앞 `round(0.7·n)` 을 train, 나머지를 validation 으로 둔다. 27 grid 를 validation MAE 로 선택하되 동률이면 앞 후보를 고른다. 선택 뒤 `H_y` 전체로 다시 적합한다. 경계 정책은 T11 `fit_etf` 와 같다 (validation proxy/lag = CARRY, RAW, X_AND_Y scaling).
- `min_inner_train_n = 150`, `min_inner_val_n = 50` 이다. 미달하면 `INSUFFICIENT_HISTORY` 로 두며, 미래 연도로 메우지 않는다.
- fold 상태: 2020 `PILOT_SHORT_HISTORY`, 2021–2025 `PRIMARY`, 2026 `PARTIAL_NON_BLIND`.
- 검정연도 안에서는 재적합·재선택·임계값 재보정을 하지 않는다.

## L2. 학습 이력 전략 (H 축)

학습에 쓰는 표본만 바뀐다. **특징 문맥**(검정 첫날의 lag 입력)은 모든 전략에서 실제 직전 거래일의 관측이다. 구현은 `combined_observations = H_y 전체` 로 교체한 뒤 `forecast_test_variance(CARRY)` 를 호출한다. expanding 에서는 이 교체가 원래 값과 같다.

| 전략 | 학습 표본 | 2020 | 2021 | 2022+ |
|---|---|---|---|---|
| `expanding` (주) | `H_y` 전체 | 2019 | 2019–20 | 2019–(y−1) |
| `trailing_2y` | [y−2, y−1] 두 달력연도 | `SKIP_INSUFFICIENT_HISTORY` | `IDENTICAL_TO_EXPANDING` | 실제 대조 |
| `frozen_2019` | 2019 만 (2020 fold 모형 재사용) | `IDENTICAL_TO_EXPANDING` | 실제 대조 | 실제 대조 |

`IDENTICAL_TO_EXPANDING` 칸은 따로 다시 계산하지 않고 상태만 적는다. 이 칸을 "이력 효과 없음" 으로 세지 않는다.

## L3. 분산 정책 · 잔차

- **A**: OBSERVED_PROXY, proxy/lag CARRY. t 일 예측은 t−1 까지의 관측만 쓴다.
- **B**: RECURSIVE_PREDICTION, CARRY. 재귀는 검정연도 첫날에 시작하고, 직전 문맥은 사전 연도 관측 proxy 다.
- **base**: `r_t / σ_{t−1}(60)` (min_periods 40, T11 과 같다). 모형이 없으므로 `history_strategy = none` 이다.
- 비양수 예측분산이 나온 날은 그날 잔차만 NaN 으로 둔다 (T11 D3, RAW). 건수는 `nonpos_var` 에 적는다.
- **사전 연도 재표준화 잔차**(warm 문맥·보정 풀): `model_y` 를 `H_y` 전체에 OBSERVED_PROXY·RESET 으로 적용한 in-sample 값이다 (`PREYEAR_RESTANDARDIZED`). B 의 사전 연도 문맥은 A 의 값을 쓴다 (T11 `residuals("B")` 관례). base 는 사전 연도의 인과적 기준선 잔차다.

## L4. 이동창 CUSUM · 경계

- 통계량은 T11 `rolling_cusum` 그대로다 (유효 < 0.9w 이면 NaN). w ∈ {20,30,60,120,252}, 주 분석은 w=60 이다.
- **CARRY**: 사전 연도 마지막 w−1 개 재표준화 잔차를 앞에 붙인다. 검정연도의 모든 날에 통계량이 생기며, 앞 w−1 일은 `CROSS_BOUNDARY_WARM` 이다.
- **PURE_OOS_WINDOW**: 창 전체가 검정연도 안에 있는 날(연중 순번 ≥ w−1)이다. **엄격한 OOS 요약의 주 표는 이 마스크만** 쓴다.
- **YEAR_CONTAINED**: 검정연도 관측만으로 계산한다. 정의상 PURE_OOS_WINDOW 날의 CARRY 값과 같다 (단위 테스트로 확인한다). 그래서 두 경계 모드의 차이는 앞 w−1 일에서만 생긴다.
- **구조적 불가**: 모든 연도의 거래일이 252보다 적으므로 (242–248) w=252 의 PURE/YEAR_CONTAINED 는 모든 칸이 `NO_FULL_WINDOW` 다. w=252 는 CARRY 로만 볼 수 있다.
- 에피소드는 경보일 사이 공백 ≤ 5 거래일이면 하나로 묶는다. 연도 귀속은 경보일 기준이다.

## L5. 임계값 (모두 검정연도 시작 전 정보)

| 방법 | 풀/생성 | 귀무 | 상태 표시 |
|---|---|---|---|
| `iid_insample` (T11 호환, 주) | 사전 연도 재표준화 잔차 iid 재표집 5,000 | iid, 구조변화 없음 | `IN_SAMPLE_RESIDUAL_CALIBRATION` (base: `HISTORICAL_CAUSAL_RESIDUALS`) |
| `iid_prequential` | 2020..y−1 의 **OOS** 잔차 (같은 정책·expanding) iid 5,000 | iid | `PREQUENTIAL_OOS`. 2020 은 `NOT_ESTIMABLE` |
| `normal_mc` | N(0,1) 20,000 | iid 정규 | `REFERENCE_NORMAL` |
| `block_insample` | in-sample 풀, 순환 블록 부트스트랩 (L=10) 2,000 | **다른 귀무** — 풀의 단기 의존을 보존 | `DIFFERENT_NULL_SENSITIVITY` |
| 점근 1.3397 | — | 대표본 점근 | `REFERENCE_ASYMPTOTIC` (이동창에서는 참고 열) |

- 이동창 임계값은 길이 w 창 하나의 **점별** 95% 분위다. 연간 첫 경보 5%·ARL₀ 를 뜻하지 않는다. 연간 확률은 합성 실험으로만 잰다.
- **연간 사후 검정**의 임계값은 점근 1.3397 이고, 같은 풀에서 n = 그해 유효 잔차 수로 만든 유한표본 95% (iid_insample, iid_prequential, normal_mc, block) 를 함께 적는다. 이동창 `c_w` 는 쓰지 않는다.
- 귀무 기대 에피소드 수 (`expected_null_episodes`) 는 같은 풀에서 길이 n_test 의 iid 표본 200회를 뽑아 PURE 마스크로 센 평균이다.
- 난수 seed 는 `sha256(study_id|ticker|year|policy|history|window|calibration|purpose)` 의 앞 8바이트로 만든다 (Python `hash()` 는 쓰지 않는다).

## L6. 진단 축 정의

- **V**: `RV_y = √252·sd(r | 연도 y)` (ddof=1, %p.a.) 와 `rv_prev`, `ratio`, `delta`, `log_ratio`, `rv_3y_historical` (직전 최대 3개 달력연도를 묶은 표본), `rv_prior_quantile` (= RV_y 이하인 사전 연도 일별 60일 연환산 이동 변동성 관측의 비율) 를 낸다. 모두 `known_at = 연도 마지막 관측일 장 마감 후` 이다.
- **M**: 지표는 `QLIKE = mean(log v̂ + r²/v̂)`, `MAE/RMSE(r² − v̂)` (단위 %²), `mean e²`, `var e`, `mean e`, `coverage`, `nonpos_var`, `val_mae` 다. 정책 간 비교는 **세 정책이 모두 유효한 날의 교집합**에서 하고, 정책별 자기 coverage 는 따로 적는다. base 의 v̂ 는 `σ_{t−1}(60)²` 이다.
- **N**: 잔차 e 의 평균·분산·왜도·초과첨도·분위수(1,5,50,95,99%)·|e|>3 빈도, `ACF(e,1)`, `ACF(e²; 1,5,10,20)`, `Ljung–Box(e,10)`, `Ljung–Box(e²,10)`, `ARCH-LM(5)` (n·R², χ²(5)) 를 낸다. **BH 범위**는 (검정 종류 × 정책 × history_strategy) 마다 20 ETF × 7 연도 = 140 검정이다. 연중 상·하반기 e² 비율은 `EXPLORATORY` 다.
- **C**: 연간 T·임계값·기각 (방법별), 이동창 peak T, 경보일, 에피소드, 첫 경보일, 귀무 기대 에피소드다.
- **H**: L2 의 대조를 쓴다. 같은 날짜(전략 간 유효 교집합)의 QLIKE, 연간 T, 기각, w60 PURE 에피소드 (자기 iid_insample 임계값) 를 비교한다.

## L7. 사전 고정 플래그 규칙 (실 데이터를 보기 전 고정)

| 축 | 플래그 | 규칙 |
|---|---|---|
| V | `RV_UP` / `RV_DOWN` | `rv_ratio ≥ 1.25` / `≤ 0.8` |
| V | `RV_HIGH_VS_HISTORY` | `rv_prior_quantile ≥ 0.9` |
| M | `VAR_UNDERPREDICTED` / `VAR_OVERPREDICTED` | 교집합 기준 `mean e² ≥ 1.5` / `≤ 0.6667` |
| M | `QLIKE_WORSE_THAN_BASE` | 같은 날짜에서 정책 QLIKE > base QLIKE (SVR 정책만) |
| M | `LOW_COVERAGE` | 자기 coverage < 0.9 |
| N | `E2_DEPENDENCE` / `ARCH_EFFECT` | `LB(e²)` / `ARCH-LM` 의 BH q < 0.05 |
| N | `HEAVY_TAIL` | 초과첨도 > 3 |
| C | `ANNUAL_REJECT_ASYM` | 연간 T ≥ 1.3397 |
| C | `VERDICT_FLIPS_CALIBRATION` | 연간 기각이 점근 / iid_insample / iid_prequential 사이에서 다름 (추정 가능한 것만) |
| C | `VERDICT_FLIPS_WINDOW` | PURE 에피소드 유무가 w ∈ {20,30,60,120} 사이에서 다름 (iid_insample) |
| C | `VERDICT_FLIPS_BOUNDARY` | w60 에서 CARRY 와 PURE 의 에피소드 유무가 다름 |
| C | `ALARMS_EXCEED_NULL` | w60 PURE 에피소드 ≥ 2 × 귀무 기대 (iid_insample) |
| H | `H_VERDICT_DIFFERS` | 연간 점근 기각이 expanding 과 다른 전략이 하나라도 있음 |
| H | `H_QLIKE_GAP` | 같은 날짜에서 \|QLIKE_전략 − QLIKE_expanding\| > 0.1 |

**종합 상태** (`multi_factor_status`) 는 ETF·연도·정책마다 정한다 (history = expanding).
- fold 를 추정할 수 없으면 `NOT_ESTIMABLE`.
- 연간 점근 기각이거나 w60 PURE 에피소드가 있으면, 그 칸을 "설명할 신호" 로 본다. V/M/N/H 중 플래그가 선 축이 2개 이상이면 `MULTIFACTOR`, 1개면 `DESCRIPTIVE_EVIDENCE` (축 이름만 쓰고 원인이라고 하지 않는다), 0개면 `UNRESOLVED` 다.
- 신호가 없으면 `NO_SIGNAL_DESCRIPTIVE` 다.
- C 축 뒤집힘(보정·창·경계 중 하나라도)이 있으면 별도 열 `sensitivity_status = SENSITIVITY_CONFIRMED` 로 둔다. 이것은 계산상 사실이지 원인이 아니다.
- `SYNTHETIC_CAUSAL_KNOWN_ONLY` 는 합성 결과표에만 붙인다.

## L8. 합성 검증 (G2/G5)

- **검출기 수준** (잔차를 직접 생성, 1,000회): 귀무 정규, 높은 분산 정규(×3 스케일), t5 꼬리, GARCH(1,1) 군집, 단일 이상치, 평균만 이동, 분산 ×1.5/2/3 연중 변화, 연도 경계 분산 ×2, 같은 연간 RV·다른 연중 구조, 일정한 분산 예측 편향(×0.5), 표류하는 편향을 둔다. 연간 사후 검정의 Size/Power 와 w60 PURE 이동창의 연간 경보 확률·지연을 재며, 보정 방법별로 낸다. Wilson 95% CI 를 붙인다.
- **파이프라인 수준** (수익률 생성 → 연초 SVR 적합 → A 잔차 → 검정, 200회): GARCH 귀무, 분산 ×2 연중 변화를 둔다. 반복 수가 적다는 점을 적는다.

## L9. 병렬 · 재현

- 병렬 단위는 ticker 다. `ProcessPoolExecutor(mp_context=spawn)` 를 쓰고, worker 마다 BLAS/OMP 스레드는 1개다. ETF 안에서는 연도를 순차로 처리한다.
- 출력은 `outputs/t12/work/<run_id>/<ticker>/` 에 원자적으로 쓴다 (tmp→rename). 병합은 (ticker, year, policy, history_strategy, window, boundary_mode, calibration_method) 순으로 안정 정렬한다. CSV 는 UTF-8·LF·`%.10g` 로 쓴다.
- 비교 모드는 sequential, parallel_2, parallel_4, parallel_4 재실행 이다. 판정은 행 수, 결과표 sha256, 수치 최대 차이로 한다. 바이트가 일치하지 않으면 원인과 허용 오차를 적으며, PASS 로 쓰지 않는다.

## L10. 금지

- P1/P4/C3·임의 사건을 정답으로 쓰지 않는다.
- 실제 데이터에서 TP/FP 를 말하지 않는다. 관측 경보는 `alarm_frequency` 이고 `not_ground_truth_false_positive` 다.
- RV 를 원인으로 서술하지 않는다.
- 2026 을 블라인드 검증처럼 서술하지 않는다.
- oracle(검정연도로 재학습) 결과를 주 결과에 넣지 않는다 (이번 run 에서는 만들지 않는다).

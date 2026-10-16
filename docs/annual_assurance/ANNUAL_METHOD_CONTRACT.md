# ANNUAL_METHOD_CONTRACT — T12 Annual Expanding SVR–GARCH–CUSUM 방법 계약 (A-1)

작성: A (Scientific Methodology & Independent Assurance), 2026-10-16. 브랜치 `research/annual-a-method`, base `8414678`.

이 문서는 T12 가 **실제로 무엇을 계산하는지** 고정한다. 각 항목에 코드 위치(`파일:줄`, 줄 번호는 base `8414678` 기준)와 문서 근거를 단다.
문서 약칭은 다음과 같다.

| 약칭 | 문서 |
|---|---|
| `LOCK Ln` | `research/t12_annual_expanding_v2/PROTOCOL_LOCK.md` 의 절 (줄 번호는 `LOCK:줄`) |
| `CHG C-nn` | `research/t12_annual_expanding_v2/PROTOCOL_CHANGELOG.md` |
| `SPEC A§n` / `SPEC B§n` | `R2H_T12_20ETF_Diagnostic_Master_Spec_v2.md` Part A (v2 강화) / Part B (v1 확정 명세) |
| `CFG:줄` | `configs/t12_annual_expanding_v2.json` |
| `METH` | `research/t12_annual_expanding_v2/report/methods_part.md` |

코드 경로 약칭: `ae/` = `src/r2h/annual_expanding/`, `p20/` = `src/r2h/paper2020/`, `etf/` = `src/r2h/svrgarch_etf/`.

프로토콜과 코드가 다른 곳은 **충돌** 로 적었다. 이 문서에서는 고치지 않는다. 수정 요청은 `REQUESTS_TO_B.md` 에 있다.
"확인" 은 A 가 결과표나 코드로 직접 대조했다는 뜻이다. 대조 스크립트는 `docs/annual_assurance/scripts/`, 테스트는 `tests/assurance/` 에 있다.

---

## 1. 자산 (Universe)

ETF 는 정확히 20종이다. 순서는 `research/svr_garch_cusum_etf/reference_close_sha256.csv` 의 행 순서를 따른다.

| # | ticker | 이름 | category |
|---|---|---|---|
| 1 | 069500 | KODEX 200 | broad_market |
| 2 | 102110 | TIGER 200 | broad_market |
| 3 | 229200 | KODEX 코스닥150 | broad_market |
| 4 | 122630 | KODEX 레버리지 | leveraged_inverse |
| 5 | 114800 | KODEX 인버스 | leveraged_inverse |
| 6 | 091230 | TIGER 반도체 | sector |
| 7 | 091170 | KODEX 은행 | sector |
| 8 | 091180 | KODEX 자동차 | sector |
| 9 | 305540 | TIGER 2차전지테마 | theme |
| 10 | 143860 | TIGER 헬스케어 | sector |
| 11 | 117680 | KODEX 철강 | sector |
| 12 | 161510 | PLUS 고배당주 | strategy |
| 13 | 219480 | KODEX 미국S&P500선물(H) | broad_market |
| 14 | 133690 | TIGER 미국나스닥100 | broad_market |
| 15 | 192090 | TIGER 차이나CSI300 | broad_market |
| 16 | 148070 | KIWOOM 국고채10년 | rates |
| 17 | 153130 | KODEX 단기채권 | money_market |
| 18 | 132030 | KODEX 골드선물(H) | commodity |
| 19 | 261220 | KODEX WTI원유선물(H) | commodity |
| 20 | 261240 | KODEX 미국달러선물 | currency |

- 코드
  - `ae/pipeline.py:170-172` 는 universe 를 `reference()` 의 ticker 열로 정한다. 개수가 `expected_n_tickers=20` (`CFG:8`) 이 아니거나 수익률 열 순서가 다르면 멈춘다.
  - `ae/pipeline.py:167-168` 은 `data_version` 이 `5f20e3e0073b521a` (`CFG:7`) 가 아니면 멈춘다.
- 문서: `SPEC A§1` (정확히 20 ETF, 일부만 보고 금지), `METH II.1`.
- 노출 중복
  - 069500·102110 은 같은 KOSPI200 을 추종한다. 122630·114800 은 같은 지수의 레버리지·인버스다.
  - 근거: `etf/data.py:28` `KOSPI200_GROUP`, `SPEC B§8`.
  - 상관 구조의 정량은 감사 문서 Q7 에 있다.

## 2. 기간 · 일별 수익률

| 항목 | 정의 | 코드 | 문서 |
|---|---|---|---|
| 원자료 | `data/raw/<ticker>.csv` 의 `Date, Close`. `Date ≤ 2026-10-02` | `etf/data.py:25,81-83` | `SPEC B§2`, `G0_AUDIT §3` |
| 무결성 | `Date,Close` 원문 줄의 sha256 을 기준 해시와 대조한다. 다르면 `DataVersionDiffers` | `etf/data.py:35-38,84,91-95` | `ANNUAL_STATE_PACKET §3` |
| 공통 거래일 | 20종 종가가 모두 있는 날만 남긴다 (`DataFrame.dropna()`) | `etf/data.py:96` | `LOCK L1` (`LOCK:8`) |
| 수익률 | `r_t = 100·(ln C_t − ln C_{t−1})`. 첫 행은 버린다 | `etf/data.py:103-108` | `LOCK:8`, `CFG:10`, `SPEC B§3` |
| 기간 | 수익률 2019-01-03 ~ 2026-10-02, 1,902개 (종가 1,903행) | 결과로 확인 (§3 표) | `G0_AUDIT §3` |
| DQ 결측 | 261240 의 2019-03-14·15 수익률은 NaN 이다 | `etf/data.py:27,109-111` | `LOCK:8` |
| 학습·검정에서의 결측 | `returns.dropna()` 후 **유효값만** 학습한다. NaN 이 빠진 자리는 앞뒤 관측이 붙는다 | `ae/folds.py:75`, `ae/worker.py:140-142` | — |

- **함정 (충돌 아님, 운영 위험)**
  - `load_close_panel(raw_dir=None)` 은 `ETF_RAW_DIR` 가 없으면 FinanceDataReader 네트워크 조회로 간다 (`etf/data.py:75-81`).
  - `ae/pipeline.py:166` 은 `raw_dir` 를 그대로 넘긴다. 기본값을 쓰는 CLI 는 `scripts/run_t12_annual_expanding.py:23` (`data/raw`) 이다.
  - 노트북은 `raw_dir='data/raw'` 를 명시해야 한다 (`ANNUAL_STATE_PACKET §3`, D-C04).
- 공통 거래일 규칙의 함의: 어느 한 ETF 라도 거래가 없던 날은 20종 모두에서 빠진다. 그다음 날 수익률은 2거래일치가 된다. 이 규칙은 T11 과 같다.

## 3. 연도별 fold (실측 대조)

**정의**
- 검정연도는 `y ∈ {2020..2026}` 다 (`CFG:12`).
- 학습 이력 `H_y` 는 `date < y-01-01` 인 유효 수익률이다. 검정 구간 `E_y` 는 `y-01-01 ≤ date < (y+1)-01-01` 이다.
- 코드: `ae/folds.py:41-51` (`training_mask`), `ae/folds.py:77` (test), `ae/worker.py:166-168,234-236`.
- 문서: `LOCK L1` (`LOCK:9`), `SPEC B§2`.

**누수 가드**
- `ae/worker.py:237-238` 는 학습 이력의 마지막 날이 검정 첫날보다 앞서지 않으면 `AssertionError` 를 낸다.
- 결과 열 `leak_check_train_end_lt_test_start` 는 `ae/worker.py:222-224` 에서 만든다.

**fold 표.** `results/fold_manifest.csv` 의 `history_strategy=expanding` 140행을 값별로 묶었다.
A 가 원자료에서 날짜를 독립적으로 다시 계산했고 140/140 일치했다 (`tests/assurance/test_fold_contract_real.py`).

| y | 상태 | train_start | train_end | n_history | inner train / val | test_start | test_end | n_test |
|---|---|---|---|---|---|---|---|---|
| 2020 | PILOT_SHORT_HISTORY | 2019-01-03 | 2019-12-30 | 245 (261240: 243) | 172/73 (261240: 170/73) | 2020-01-02 | 2020-12-30 | 248 |
| 2021 | PRIMARY | 2019-01-03 | 2020-12-30 | 493 (491) | 345/148 (344/147) | 2021-01-04 | 2021-12-30 | 248 |
| 2022 | PRIMARY | 2019-01-03 | 2021-12-30 | 741 (739) | 519/222 (517/222) | 2022-01-03 | 2022-12-29 | 246 |
| 2023 | PRIMARY | 2019-01-03 | 2022-12-29 | 987 (985) | 691/296 (690/295) | 2023-01-02 | 2023-12-28 | 245 |
| 2024 | PRIMARY | 2019-01-03 | 2023-12-28 | 1232 (1230) | 862/370 (861/369) | 2024-01-02 | 2024-12-30 | 244 |
| 2025 | PRIMARY | 2019-01-03 | 2024-12-30 | 1476 (1474) | 1033/443 (1032/442) | 2025-01-02 | 2025-12-30 | 242 |
| 2026 | PARTIAL_NON_BLIND | 2019-01-03 | 2025-12-30 | 1718 (1716) | 1203/515 (1201/515) | 2026-01-02 | 2026-10-02 | 184 |

- `METH II.2` 는 "2019 한 해(245일)도 172/73" 이라고만 적었다. 261240 은 243일, 170/73 이다. 사소한 기술 누락이며 노트북에 같이 적어야 한다.

## 4. 내부 train / validation 경계

| 항목 | 정의 | 코드 | 문서 |
|---|---|---|---|
| 분할 | `n_train = round(0.7·n)`, 나머지는 validation (시간순) | `ae/folds.py:68-70`, `CFG:16` | `LOCK:10`, `SPEC B§4` |
| 반올림 | Python `round` 는 은행가 반올림이다. 2020 의 `0.7·245 = 171.5 → 172` | `ae/folds.py:69` | 문서에 반올림 규칙 명시 없음 (결과는 위 표와 일치) |
| 최소 표본 | train ≥ 150, val ≥ 50. 미달하면 `INSUFFICIENT_HISTORY` 이고 미래로 메우지 않는다 | `ae/folds.py:84-85`, `CFG:17-18` | `LOCK:11`, `SPEC B§4` |
| 실측 | 140 fold 모두 충족한다 (최소는 2020 의 170/73) | §3 표 | — |
| 미달 처리 | 그해 진단 행을 쓰지 않는다 (`continue`) | `ae/worker.py:231-232` | 이번 run 에서는 발생하지 않음 |

- **스케일러 경계**
  - validation 예측은 inner train 으로 학습한 파이프라인(X 와 y 의 `StandardScaler` 포함)을 쓴다 (`p20/svr_garch.py:238-247,356-367`).
  - validation proxy 는 train 끝에서 CARRY 로 이어진다. lag 도 CARRY 다 (`p20/svr_garch.py:290-307`, `ae/fit.py:62-64`).
  - 문서: `SPEC B§4` (inner train 만으로 변환 학습, validation 은 고정 적용), `LOCK:10`.

## 5. expanding 적합 · SVR 입력 · 27 grid · 선택 규칙

**SVR 입력 (Eq. 9)**
- proxy 는 `σ̃²_t = mean(r²_{t−m+1..t})`, m = 5 다. 앞부분 m 개 미만 구간은 확장 평균을 쓴다 (`p20/volatility_proxy.py:47-84`).
- 특징은 `x_t = (r²_{t−1}, σ̃²_{t−1})` (p = q = 1), 목표는 `σ̃²_t` 다 (`p20/volatility_proxy.py:139-152`).
- 첫 `max(p,q)=1` 행은 lag 가 없어 빠진다.

**모형**
- RBF-SVR 이다. `gamma_sklearn = 1/(2·γ²)` (`p20/svr_garch.py:208-213,225-235`).
- 스케일링은 X·y 모두 `StandardScaler` (X_AND_Y) 다 (`ae/fit.py:58`, `p20/svr_garch.py:243-247`).

**grid**
- `C ∈ {1,10,100}` × `γ² ∈ {0.1,0.5,1}` × `ε ∈ {0.1,0.5,1}` 을 `itertools.product` 순서로 쓴다. 모두 27개다 (`etf/model.py:38-41`).
- 문서: `CFG:21`, `LOCK:10`, `METH II.2`.

**선택**
- validation MAE `mean|σ̂² − σ̃²|` 가 최소인 후보를 고른다. 비양수 예측도 그대로 둔다 (RAW).
- 동률은 `np.isclose(rtol=0, atol=0)`, 즉 정확히 같은 값일 때만이다. 이때 grid 순서상 앞 후보를 고른다 (`p20/svr_garch.py:363-382`, `ae/fit.py:65-67`).

**재적합**
- 선택한 하이퍼파라미터로 `H_y` 전체(train+val, RESET proxy)에 다시 적합한다 (`p20/svr_garch.py:384-400`).
- 문서: `LOCK:10`, `SPEC B§4`.

**연도 고정**
- 검정연도 안에서는 재적합·재선택·재보정을 하지 않는다. 적합 호출은 연도 루프마다 `fit_annual` 한 번뿐이다 (`ae/worker.py:240`).
- 문서: `LOCK:13`.

**T11 과의 차이**
- T12 는 `fit_etf` (T11 70:30 전체 분할) 를 호출하지 않는다 (`ae/fit.py:1-5`, `SPEC B§4`, `G0_AUDIT §5`).
- 경계·스케일링·tie 정책은 `etf/model.py:79-92` 와 같다.

**이력 전략 (H 축)**

| 전략 | 학습 표본 | 코드 | 문서 |
|---|---|---|---|
| expanding (주) | `H_y` 전체 | `ae/folds.py:44-46` | `LOCK L2` |
| trailing_2y | `[y−2-01-01, y-01-01)` | `ae/folds.py:47-48`, 상태 `ae/folds.py:58-61` | `LOCK L2` |
| frozen_2019 | 2019 만 학습한 2020 fold 모형을 재사용 | `ae/folds.py:49-50`, `ae/worker.py:241-242,508-511` | `LOCK L2`, `CHG C-06` |

- 특징 문맥(lag 입력)은 모든 전략에서 실제 직전 관측(`ctx`, `H_y` 전체)이다 (`ae/fit.py:85-92`, `ae/worker.py:540`).
- 문서: `LOCK:17`, `CHG C-06`.

## 6. 분산 갱신 (m, p, q) · 정책 A / B / base

`M, P, Q = 5, 1, 1` (`etf/model.py:42`, `CFG:22`).

| 정책 | 검정연도 t 일 예측 σ̂²_{t\|t−1} | 코드 | 문서 |
|---|---|---|---|
| **A** (OBSERVED_PROXY, CARRY) | `ĝ(r²_{t−1}, σ̃²_{t−1})`. 둘 다 **관측값**이다. proxy 는 사전 연도 끝에서 CARRY 로 이어진다 | `ae/fit.py:95-119`, `p20/svr_garch.py:426-447` | `LOCK:29`, `SPEC B§4` |
| **B** (RECURSIVE_PREDICTION, CARRY) | `ĝ(r²_{t−1}, σ̂²_{t−1})`. 관측 `r²_{t−1}` 과 **자기 직전 예측** `σ̂²_{t−1}` 을 쓴다. 첫날의 분산 lag 는 사전 연도 마지막 관측 proxy 다 | `p20/svr_garch.py:449-474`, 문맥 `ae/fit.py:85-92` | `LOCK:30` |
| **base** | `σ²_{t−1}(60)` = `r_{t−60..t−1}` 의 표본분산 (ddof=1, min_periods 40, `shift(1)`). 모형이 없다 (`history_strategy=none`) | `ae/fit.py:151-154`, `ae/worker.py:144-145,268` | `LOCK:31`, `SPEC B§4` |

- **잔차**: `e_t = r_t / √σ̂²_t` 다. σ̂² ≤ 0 이거나 유한하지 않으면 그날만 NaN 으로 둔다 (`ae/fit.py:142-148`).
  - 비양수 건수는 `nonpos_var` 에 기록한다 (`ae/worker.py:295`). 문서: `LOCK:32`.
- **사전 연도 재표준화 잔차** (warm 문맥과 in-sample 보정 풀)
  - `model_y` 를 `H_y` 전체에 OBSERVED_PROXY·RESET 으로 적용한 값이다. 첫 관측은 lag 가 없어 NaN 이다 (`ae/fit.py:122-139`, `ae/worker.py:271-273`).
  - B 의 풀·문맥은 A 의 값을 쓴다 (`ae/worker.py:273`, `CHG C-05`). base 의 풀은 사전 연도의 인과적 기준선 잔차다.
  - 문서: `LOCK:33`.
- **인과성**: t 일 예측은 t−1 까지의 관측만 쓴다.
  - 기존 테스트: `tests/leakage/test_t12_no_future_information.py::test_within_year_prefix_invariance...`
  - A 의 실데이터 재확인: `tests/assurance/test_boundary_leakage_real.py`

## 7. CUSUM-of-squares 통계량 · 정규화

n 개 유효 잔차 `e_1..e_n` 에 대해 다음을 계산한다.

```
S_k   = Σ_{s≤k} e_s²  −  (k/n) · Σ_{s≤n} e_s²                 (k = 1..n)
τ̂²   = (1/n) Σ e_s⁴  −  ((1/n) Σ e_s²)²                       (분모 n, n−1 아님)
T     = max_k |S_k| / ( √n · τ̂ )
k̂    = argmax_k |S_k|  (동률이면 첫 위치)  — 위치일 뿐이다. 기각하지 않았으면 변화점이 아니다
```

- **연간 사후 검정**: `p20/cusum.py:84-98` (경로·τ̂²), `p20/cusum.py:144` (T), `p20/cusum.py:101-113` (argmax).
  - 연간 래퍼는 `ae/calibration.py:62-72` 이다. NaN 을 빼고 유효 잔차 < 30 이면 NaN 을 낸다. τ̂² ≤ 0 이어도 NaN 이다 (`RETURN_NAN`).
  - 잔차는 **그해 OOS 잔차만** 쓴다 (`ae/worker.py:326`). k̂ 날짜는 원래 날짜 위치로 되돌린다 (`ae/calibration.py:71`, `ae/worker.py:354`). 라벨은 `argmax_location_only` 다.
  - 문서: `SPEC B§7`, `LOCK L6-C`, `METH II.4`.
- **이동창**: 같은 식을 창 `[t−w+1, t]` 에 적용한다. NaN 은 건너뛴 것과 같게 처리한다 (유효 개수 누적 k). 유효 < ⌈0.9w⌉ 이면 NaN 이다.
  - 코드: `etf/rolling.py:20-49`. 문서: `LOCK:37`.
- **정규화 해석**: τ̂ 는 그 표본(또는 창)의 e² 표본 표준편차다. 그래서 T 는 **척도 불변**이다. e 를 상수배해도 T 는 같다.
  - 따라서 "분산 수준이 일정하게 높음(편향)" 은 T 를 올리지 않는다. T 는 **연중 e² 수준의 변화** 에만 반응한다.
  - 합성 결과 `variance_forecast_bias_constant` 의 Size 0.045 가 이것을 보여 준다.
- **독립 재계산**: A 가 위 식을 numpy 로 직접 구현했다. 재실행 `a_seq_1` 의 일별 잔차로 420행의 `annual_T`·`n_test_residuals`·`khat_argmax_date` 를 대조했다 (`docs/annual_assurance/scripts/a2_posthoc_recompute.py`, 감사 Q3).

## 8. 임계값

### 8.1 연간 사후 검정 (연말 1회)

| 방법 | 정의 | 코드 | 상태 표시 |
|---|---|---|---|
| asymptotic | 상수 **1.3397** | `ae/worker.py:331-333`, `CFG:35` | `REFERENCE_ASYMPTOTIC` |
| iid_insample | 사전 연도 재표준화 잔차(§6)를 iid 로 5,000회 재표집한다. 길이 n = 그해 유효 잔차 수. T 의 95% 분위 | `ae/worker.py:337-338`, `ae/calibration.py:23-24,40-41` | `IN_SAMPLE_RESIDUAL_CALIBRATION` (B: `_POOL_POLICY_A`, base: `HISTORICAL_CAUSAL_RESIDUALS`) |
| iid_prequential | 2020..y−1 의 같은 정책 **OOS** 잔차를 iid 로 5,000회 재표집한다. 2020 은 추정할 수 없다 | `ae/worker.py:322,493` | `PREQUENTIAL_OOS` / `NOT_ESTIMABLE` |
| normal_mc | N(0,1) 20,000회, 길이 n | `ae/worker.py:334-336,76-85` | `REFERENCE_NORMAL` |
| block_insample | in-sample 풀에서 순환 블록 (L=10) 으로 2,000회 | `ae/calibration.py:27-33` | `DIFFERENT_NULL_SENSITIVITY` |

- 풀의 유효값이 50 미만이면 `NaN` 이다. 이때 상태는 `NOT_ESTIMABLE` 이다 (`ae/worker.py:101-106,357`).
- 기각 규칙은 `T ≥ c` 다 (`ae/worker.py:352`). 이동창의 `c_w` 를 연간 검정에 쓰지 않는다. 문서: `LOCK:55`, `SPEC B§6`.
- **1.3397 의 근거 (확인)**
  - 이 통계량의 H0 극한분포는 sup|Brownian bridge| (Kolmogorov) 다.
  - 그 정확한 95% 분위는 **1.3581** 이다 (`scipy.stats.kstwobign.ppf(0.95)`). 극한에서 `P(sup|B°| > 1.3397) = 0.0552` 다.
  - 따라서 1.3397 은 원문(Lee·Kim·Lee 2020) 이 표기한 값이며, **정확한 점근 5% 값이 아니다**.
  - 유한표본(n≈245)에서는 이산 최대값이 연속 sup 보다 작다. 그래서 1.3397 은 iid 정규에서 보수적이다 (감사 Q4: size ≈ 0.035). `annual_posthoc` 의 normal_mc 95% 는 n = 184–248 에서 1.298–1.320 이다.
  - 이 사실은 노트북에 "원문 표기 임계값, 점근 5% 정확값 아님" 으로 적어야 한다.

### 8.2 이동창 (일별)

- 같은 다섯 방법을 쓴다. 다만 표본 길이가 **w** 이고, 결과는 길이 w 창 하나의 **점별 95% 분위** 다 (`ae/worker.py:371-383`).
  - 문서: `LOCK:53`, `SPEC A§2.4`, `SPEC B§6`.
- 점별 95% 는 "연중 첫 경보 확률 5%" 나 ARL₀ 를 뜻하지 않는다.
  - 합성 iid N(0,1) 검출기 수준에서 w60 PURE 창의 연중 ≥1 에피소드 확률은 **0.682** 다 (`results/null_dgp_validation.csv`).
- 귀무 기대 에피소드 (`expected_null_episodes`, `null_prob_any_episode`)
  - 같은 풀에서 길이 `n_days` 표본을 200회 뽑는다. PURE 창으로 에피소드를 세고 평균과 ≥1 확률을 낸다 (`ae/worker.py:385-396`, `ae/calibration.py:53-59`).
  - 단위는 **연간 원카운트** 다 (T11 의 연율 환산과 다르다. `T11_T12_COMPARISON_CONTRACT.md`).
- **충돌 K-1 (경미)**
  - `LOCK:57` 은 귀무 표본 길이를 `n_test` 로 정의한다. 코드는 공통 index 날짜 수 `n_days` 를 쓴다 (`ae/worker.py:387,390`).
  - 이번 자료에서는 검정연도에 DQ 결측이 없어 두 값이 같다. 다만 비양수 분산일(NaN 잔차)은 `n_days` 에 포함된다.
- **충돌 K-2 (seed 규칙)**
  - `LOCK:58` 은 모든 난수 seed 를 `sha256(study_id|ticker|year|policy|history|window|calibration|purpose)` 로 정한다.
  - 코드에서 normal_mc 와 asymptotic 귀무 표본은 `rng_for(study_id, "normal_reference", n, reps, purpose)` 이다 (`ae/worker.py:75-90`). ticker·year·policy 가 키에 없다.
  - 그 결과 같은 n 이면 모든 ETF 가 **같은 정규 표본** 을 공유한다. 정규 임계값의 MC 오차가 ETF 사이에 완전 상관된다.
  - 코드 주석은 근거로 `C-11` 을 인용한다 (`ae/worker.py:77`). 그러나 `PROTOCOL_CHANGELOG.md` 에는 C-10 까지만 있다. **문서 누락**이다.

### 8.3 seed

- `derive_seed(*key)` 는 `sha256("|".join(key))` 의 앞 8바이트를 big-endian 으로 읽는다 (`ae/config.py:32-35`).
- Python `hash()` 를 쓰지 않으므로 프로세스·순서와 무관하다. 문서: `LOCK:58`.
- 기본 seed `CFG:9` (20261012) 는 키 기반 seed 에 들어가지 않는다. study_id 문자열이 대신 들어간다.

## 9. 경계 모드 · 마스크 · 에피소드

| 항목 | 정의 | 코드 | 문서 |
|---|---|---|---|
| CARRY | 사전 연도 마지막 w−1 개 재표준화 잔차(공통 index, NaN 포함) + 검정연도 → 검정연도 날짜의 통계량 | `ae/calibration.py:75-80`, `ae/worker.py:364` | `LOCK:38` |
| PURE_OOS_WINDOW | 연중 순번 ≥ w−1 (창 전체가 검정연도 안) | `ae/worker.py:366` | `LOCK:39`, `SPEC A§2.4` |
| YEAR_CONTAINED | 검정연도 관측만으로 계산한다. PURE 날의 CARRY 값과 같은지 런타임에 `atol=0` 으로 assert 한다. 결과표의 YEAR_CONTAINED 행은 CARRY 통계량을 PURE 마스크로 요약한 것이다 | `ae/worker.py:365-370,398` | `LOCK:40` |
| w=252 | 모든 연도의 거래일이 252 미만(184–248)이라 PURE 창이 없다 → `NO_FULL_WINDOW` | `ae/worker.py:414-415` | `LOCK:41` |
| 에피소드 | 경보일 사이 공백 ≤ 5 거래일이면 하나로 묶는다. 경보 = mask 안에서 `T_t ≥ c` | `etf/rolling.py:93-105`, `ae/calibration.py:83-96` | `LOCK:42` |
| 연도 귀속 | 경보일 기준이다. 마스크는 그해 날짜만 포함하므로 연도를 넘는 에피소드는 연도별로 잘린다 | `ae/worker.py:398` | `LOCK:42` |

- **충돌 K-3 (명세 대 lock/코드)**
  - `SPEC B§5` (`SPEC:288`) 는 연도 경계를 넘는 에피소드를 `CROSS_YEAR_EPISODE` 로 표시하고, 귀속 규칙을 함께 기록하라고 요구한다.
  - lock 은 "경보일 기준 귀속" 만 정했다. 코드에는 `CROSS_YEAR_EPISODE` 표시가 없다.
  - 그래서 12월 말에서 1월 초로 이어지는 경보는 두 해에 **각각 1 에피소드**로 세어진다. CARRY 모드에서 중복이 생길 수 있다.
- **충돌 K-4 (명세 대 코드)**
  - `SPEC B§5` (`SPEC:287`) 는 "2019 학습 기간이 252 미만이면 `w=252` 임계값·워밍업 적합성은 `INSUFFICIENT_CALIBRATION`" 이라고 요구한다.
  - 2019 의 유효 잔차는 244–245개(< 252)인데, 2020 w=252 행의 `calibration_status` 는 `IN_SAMPLE_RESIDUAL_CALIBRATION` 이다 (결과표로 확인).
  - w=252 는 CARRY 로만 존재한다. 2020 CARRY w=252 의 첫 6일(base 21일)은 유효 < 0.9w 라서 NaN 이다 (`n_valid_stat_days` 242/227).

## 10. 2020 파일럿 · 2026 부분·비블라인드

| 항목 | 내용 | 코드 | 문서 |
|---|---|---|---|
| 2020 상태 | `PILOT_SHORT_HISTORY`: 학습 245일(2019 한 해), inner 172/73 | `ae/folds.py:32-38`, `CFG:14` | `LOCK:12`, `SPEC A§1`, `SPEC B§2` |
| 2020 제약 1 | `iid_prequential` 은 `NOT_ESTIMABLE` 이다 (사전 OOS 풀이 없음) | `ae/worker.py:68-69` | `LOCK L5` |
| 2020 제약 2 | trailing_2y 는 `SKIP_INSUFFICIENT_HISTORY`, frozen_2019 는 `IDENTICAL_TO_EXPANDING` 이다. H 대조가 없다 | `ae/folds.py:54-65` | `LOCK L2` |
| 2020 제약 3 | w=252 보정 풀이 252 미만이다 (K-4) | — | `SPEC B§5` |
| 2026 상태 | `PARTIAL_NON_BLIND`: 2026-01-02 ~ 10-02, 184 거래일. T11·EDA 가 이미 본 구간이다 | `ae/folds.py:36-37`, `CFG:15` | `LOCK:12`, `SPEC B§2,§8`, `LOCK L10` |
| 2026 제약 | n=184 라 다른 해(242–248)와 통계량 분포·검정력이 다르다. 연간 기각률을 다른 해와 직접 비교할 수 없다 | 정규 95% 1.298 (n=184) vs 1.311 (n=245), `annual_posthoc` | `SPEC B§7` |
| 표시 | 모든 행의 `year_status` 와 `interpretation_status` 에 상태가 들어간다 | `ae/worker.py:198-200,418-419` | U5 |
| 주 해석 기간 | 2021–2025 (`core_completed_years`) | `CFG:13` | `SPEC A§1` |

## 11. 진단 축 · 종합 상태 (요약 계약)

- V: `ae/diagnostics.py:17-30`, `ae/worker.py:175-203`. RV 는 사후값이고 `known_at` 열에 `ex-post` 가 붙는다. 문서: `LOCK L6`, `SPEC A§2.1`.
- M: `ae/diagnostics.py:34-59`, `ae/worker.py:275-300`. 세 정책 교집합 날짜에서 계산한다. 문서: `CHG C-07`.
- N
  - 코드: `ae/diagnostics.py:63-142`.
  - BH 는 `(policy, history_strategy)` 묶음 × 검정 종류마다 140개 범위다 (`ae/pipeline.py:108-114`). 문서: `LOCK L6`.
  - 관찰: Ljung–Box·ARCH-LM 은 NaN 을 지운 뒤 붙인 배열에 적용한다. 결측일의 시간 간격은 무시한다 (`ae/diagnostics.py:108-110`).
- C: §7–9.
- H: `ae/worker.py:495-622`. 같은 날짜·유효 교집합에서 비교한다.
- 종합 상태
  - 코드: `ae/profile.py:127-143`.
  - "신호" 는 연간 점근 기각 **또는** w60 PURE iid_insample 에피소드 ≥ 1 이다.
  - 귀무에서도 w60 PURE 에피소드 확률이 높아(검출기 수준 0.68) 신호 게이트가 쉽게 켜진다. 감사 Q6 에서 다룬다.
  - 이 규칙은 사전 고정이므로 충돌은 아니다. 해석 위험으로 분류한다.

## 12. 충돌 · 문서 누락 요약

| ID | 종류 | 내용 | 영향 | 요청 |
|---|---|---|---|---|
| K-1 | lock 대 코드 (경미) | 귀무 표본 길이 `n_test` vs `n_days` | 이번 자료에서는 수치상 없음 | RQ-3 |
| K-2 | lock 대 코드 + 문서 누락 | normal_mc seed 가 ticker·year·policy 를 키에 넣지 않는다. 근거 `C-11` 이 CHANGELOG 에 없다 | 정규 임계값 MC 오차가 ETF 간 공통이다 (판정 영향 없음, 기록 결함) | RQ-1 |
| K-3 | 명세 대 lock·코드 | `CROSS_YEAR_EPISODE` 표시 없음 | CARRY 연말-연초 에피소드가 두 해에 각각 1건으로 세어질 수 있다 | RQ-4 |
| K-4 | 명세 대 코드 | 2020 w=252 `INSUFFICIENT_CALIBRATION` 표시 없음 | w=252 는 보조 분석이라 주 결과 영향 없음 | RQ-4 |
| D-1 | 문서 | `METH II.2` 가 261240 (243일, 170/73) 을 언급하지 않는다 | 서술 정확도 | RQ-5 |
| D-2 | 문서 | 1.3397 을 "점근" 이라고 부른다. 정확한 점근 5% 는 1.3581 이다 | 해석. 1.3397 은 원문 표기값 | RQ-2 |

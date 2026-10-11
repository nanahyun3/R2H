# R2H 계약 v0.1 (제안) — 관측 · feature · 탐지 출력 · 정답 · 평가 · 백테스트

> **지위: PROPOSED.** 2조·4조 공통작업 문서와 교수 확인으로 버전을 확정하기 전까지 SSOT 가 아니다.
> 팀 Notion 의 "R2H Experiment Contract v0.1" 초안(10/09)과 같은 객체 구성을 코드로 옮긴 것이다. 코드의 단일 버전 문자열: `r2h.CONTRACT_VERSION`.

## 1. 관측 (observation) — `r2h.data.validate_observations`

| 열 | 필수 | 타입 / 규칙 |
|---|---|---|
| `ticker` | ✓ | 문자열 (선행 0 보존: `"069500"`) |
| `date` | ✓ | timezone-naive datetime, 거래소 현지 **거래일 라벨** |
| `adj_close` | ✓ | > 0, 유한. 분배·분할 조정 정책은 `source` 에 기록 |
| `volume` | ✓ | ≥ 0, 유한 |
| `open` `high` `low` `close` | | > 0, 유한 |
| `observed_at` | | timezone-aware. 마감 시각이 다른 자산(해외·선물)의 **실제 이용 가능 시각** |
| `source` | | 수집처·버전·조정 정책 |

- `(ticker, date)` 중복 금지, ticker 안 날짜 오름차순. 위반은 보고하고 조용히 고치지 않는다.
- 데이터 버전 = sorted `ticker:sha256` 의 sha256 (`r2h.data.data_version`). 원시 파일은 저장소에 넣지 않는다.
- 휴장일·결측: 행을 만들어 채우지 않는다. wide 변환 시 공통 거래일만 쓸지(`common_only`)는 실험 config 에 명시한다.

## 2. Feature — `r2h.features`

행 t 의 값은 t 이하 관측만 사용한다 (t 종가 후 이용 가능). 당일 제외 통계는 함수 안에서 `shift(1)` 로 명시.

| 함수 | 정의 | warm-up / 0 분모 |
|---|---|---|
| `log_returns` | ln C_t − ln C_{t−1} | 첫 행 NaN · 가격 ≤ 0 이면 오류 |
| `rolling_volatility(w, exclude_current)` | std(ddof=1) over [t−w+1, t] 또는 [t−w, t−1] | min_periods 미만 NaN |
| `moving_average(w)` | 단순평균 [t−w+1, t] | 〃 |
| `volume_ratio(w)` | V_t / mean(V_{t−w..t−1}) | 직전 평균 0 → NaN |
| `vol_scaled_return(w)` | r_t / σ_{t−1}(w) | σ = 0 → NaN (Inf 금지) |
| `rolling_corr(x, y, w)` | pairwise-complete Pearson/창 내부 Spearman, `n_eff`, `const` | n_eff < min_periods 또는 분산 0 → NaN |
| `sign_regimes(rho, RegimeRule(band, k))` | ±band 밖 같은 부호 k 일 연속이면 확정 | `confirmed_at` = candidate + (k−1) 거래일 |

## 3. 탐지 출력 — `r2h.detection.SIGNAL_COLUMNS`

| 열 | 의미 |
|---|---|
| `ticker` `signal_at` | 신호 시점 (일봉이면 그 거래일 종가 후) |
| `score` | 방법 고유 점수 (CUSUM 통계량 ≠ BOCPD 확률 — 직접 비교 금지). warm-up 은 NaN |
| `is_alarm` | bool 이진 경보 — 방법 간 비교는 이 열과 사건 매칭에서만 |
| `method_id` `model_version` `params_hash` | 방법·버전·파라미터 (정렬 JSON sha256 앞 16자) |
| `mode` | `online` (t 까지 관측만) / `posthoc` (표본 전체 사용 사후 검정) |
| `data_version` | 입력 데이터 버전 |
| `available_until` | 이 행 계산에 쓴 마지막 관측 시점. **online 은 ≤ `signal_at` 강제** |

필요하면 열을 덧붙일 수 있다 (예: `direction`, `run_length`). 필수 열은 지우거나 의미를 바꾸지 않는다.

## 4. 사건 정답 — `r2h.evaluation.GROUND_TRUTH_COLUMNS` (오프라인 전용)

`label_version, event_id, ticker, event_start, event_end, direction(+1/−1), threshold_definition, created_from_window`.
한 평가에 label_version 하나. 탐지기 출력으로 정답을 만들지 않는다. **어떤 정의를 쓸지는 미결 (D-01).**
4조 합성 데이터의 change point 와 금융 가격 급등 라벨은 의미가 다르다 — 섞어서 집계하지 않는다.

## 5. 평가 — `r2h.evaluation`

1. 시간순 분할 (`chronological_split`, `walk_forward` + embargo). 경계값은 config (D-03).
2. cooldown 적용 → 사건 창 [start − pre_tolerance, start + max_delay] 매칭 → TP / DUPLICATE / FP / SUPPRESSED.
3. 지표: 탐지율(사건 기준), FP / ticker-year, 지연 평균·중앙값(탐지 사건만) + 미탐 수, `recall_at_fp_cap`.
4. 사후 검정(`posthoc`) 출력은 온라인 매칭에 넣을 수 없다.
5. 근접의 우연 수준: `circular_shift_test_fast` + `bh_qvalues` (Track A 방법).

## 6. 백테스트 — `r2h.backtest` (SCHEMA_ONLY)

`signal_adapter → entry_rule → exit_rule → cost_model → performance_metrics`. 체결 규칙: `signal_at ≤ decision_at < fill_at`
(같은 봉 체결 금지). `TRADE_COLUMNS` = experiment_id, order_id, ticker, signal_at, decision_at, fill_at, side, qty, fill_price, fee, slippage.
성과 수치는 아직 없다.

## 7. 2조 ↔ 4조 교환

두 팀의 탐지기는 `시계열 → {signal_at, score, is_alarm}` 로 교환한다. 4조 PELT 는 사후 구간 분할이므로 `mode="posthoc"`.
BOCPD 의 hazard/prior 는 `params()` 에, run-length 사후확률은 `score` 에 둔다.

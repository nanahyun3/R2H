# 원본 대비 수치 parity (2026-10-11 로컬 검사)

이식한 함수를 원본 함수와 같은 입력으로 실행해 비교했다. 입력은 Track A 의 실제 ETF 패널(20종, 1,902 거래일, `dq_trim_canonical`)이며,
그 데이터는 이 저장소에 없다 — 그래서 이 검사는 CI 가 아니라 로컬 감사로만 재현 가능하다. 환경: Python 3.12.3, numpy 2.4.6, pandas 3.0.3, scipy 1.18.0.

| 비교 | 범위 | 결과 |
|---|---|---|
| `features.rolling_corr` vs Track A `rolling_corr` | 069500 대비 19쌍 × 창 30/60/120 × Pearson/Spearman, min_periods 0.9w | max\|Δρ\| = **0** (양 method), NaN·n_eff·const 불일치 0 |
| `features.sign_regimes` vs Track A | 위 Pearson ρ 전부 × 규칙 (0.1,10)(0,5)(0.2,10)(0.1,20) | 사건 표 **동일** (candidate/confirmed/zero_cross/부호/lag) |
| `features.log_returns` vs Track A `log_returns(logdiff)` | 20종 Close 패널 | max\|Δ\| = **0** |
| `features.vol_scaled_return(r, 60, min_periods=40)` vs Track A P1 점수 `r / r.rolling(60, min_periods=40).std().shift(1)` | 20종 | max\|Δ\| = **0**, NaN 패턴 동일 |
| `evaluation.circular_shift_test_fast`, `bh_qvalues` vs Track A | 무작위 200 사례 (n, 사건 위치, lag, seed) | 출력 dict·배열 **동일** |
| `detection.paper2020_cusum` | 원본과 sha256 동일 | 동일 파일 |

주의: `vol_scaled_return` 의 기본 `min_periods` 는 `window` 다. Track A P1 과 같은 값을 원하면 `min_periods=40` 을 넘긴다.

## 수치 안정성 점검 — rolling 표준편차

`rolling_volatility` 는 pandas 의 rolling std 를 그대로 쓴다 (Track A P1 과 비트 동일). 같은 20종 패널에서 2-pass(창별 `nanstd`) 계산과의
최대 상대차는 **4.8e-14**, 정확히 상수인 60일 창은 0개였다. 다만 0.1 크기 수익률 뒤 1e-12 크기 값만 남은 병적인 합성 입력에서는
pandas 버전에 따라 σ 의 상대오차가 1e-6 이상 나는 것을 property test 가 찾았다 (numpy 2.0 / pandas 2.2.2 하한 환경).
property test 는 σ > 1e-4 × 누적 최대 |r| 인 창만 비교하도록 제한하고, 이 한계를 `features/price.py` docstring 에 적었다.

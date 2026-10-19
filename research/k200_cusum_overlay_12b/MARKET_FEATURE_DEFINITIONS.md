# 시장변수 정의 (12B)

| 변수 | 정의 | 단위 | 비고 |
|---|---|---|---|
| close | 원자료 Close | 원 | `data/raw/069500.csv` (sha256 0d713905…) |
| daily_log_return_pct | 100·ln(C_t/C_{t−1}) | % | 12번 `return_log_pct` 와 동일 |
| daily_simple_return_pct | 100·(C_t/C_{t−1} − 1) | % | |
| abs_return · squared_return | \|r\| · r² | % · %² | |
| daily_realized_variance_proxy | r² | %² | 일간 실현분산 대용치 (분산, 표준편차 아님) |
| cumulative_log_return | 100·ln(C_t/C_base), base = 2019-12-30 | % | 누적 (일간 수익률과 구별) |
| indexed_close | 100·C_t/C_base | 지수 | |
| rolling_vol_w (w=5,20,60,120,252) | SD(r_{t−w+1..t}, ddof=1) | %/일 | 2019-01-03 부터의 전체 수익률로 계산 후 절단 — 12번 rv5–rv120 과 일치해야 함 (G3) |
| annualized_vol_w | √252 · rolling_vol_w | %/년 | 관측 변동성 |
| predicted_vol_B1 | √v̂ (v̂ > 0) | %/일 | SVR–GARCH 정책 A 조건부 r² 예측의 제곱근 — 평균 제거 표본 SD 와 다른 추정량 |
| predicted_vol_annualized_B1 | √(252·v̂) | %/년 | v̂ ≤ 0 → NA (`NONPOSITIVE_FORECAST`) |

구별: 일간 vs 누적 수익률 · 분산 vs 표준편차 · 일간 vs 연환산 · 관측 vs 예측 · 수준 vs 변화율(d5·d20) · 장기 고변동 vs 단일 충격 창 잔존(창 이탈일).
11번 대조: 11번 급변 구간은 q20 기준 20일 변동성 순위로 정의(`events_11.csv`)되어 이 표의 수준 국면과 정의가 다르다 — 각각 유지.

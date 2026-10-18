# 11번 그림 목록 (PNG 320dpi + SVG, 34종)

`src/r2h/etf_shock/figures.py` 가 `pipeline.run()` 결과로 그린다. 노트북과 `scripts/run_t20_pipeline.py` 두 경로가 바이트 동일하다. 번호 k = 1..6 은 069500 · 229200 · 148070 · 153130 · 133690 · 261220.

| 그림 | 내용 |
|---|---|
| E1_k_{ticker}_timeline | 2019–2026 4층: 누적수익률 · σ20/σ60 + 급변 경계 · A q20/q60 상태 · CUSUM T/crit (정책 A, w=20·60), q20 구간 음영 |
| E2_k_{ticker}_scale | 구간 시작일 × 지속 (점 크기 = 최대 σ/경계), 주분석 q20 구간 배율 막대 (단일 충격형/누적형, 창 이탈 종료) |
| E3_k_{interval_id} | 지속 상위 3구간 확대: 일간 수익률(분산 기여 색) · σ 와 경계(진입·창 이탈 종료 표시) · 시작 전날 기준 누적수익률 · CUSUM T/crit (12셀 최대 포함) |
| X1_six_etf_stack | 6종 q20 급변 상태 + 10번 C1 |
| X2_kospi200_participation | 069500 주분석 구간마다 다른 5종의 같은 날 급변 일수 |
| X3_cusum_inside_outside | 급변일 vs 나머지 날의 CUSUM T/crit (중앙값·최댓값) |
| X4_all_intervals | 6종 주분석 q20 구간 69개의 지속 × 스케일 |

## 발표용 인포그래픽 (`infographics/`, PNG 300dpi + SVG, `scripts/t20_infographics.py`)

| 그림 | 메시지 |
|---|---|
| IG1_kospi200_anatomy | KOSPI200 5년 7구간 — 누적수익률 · σ20 과 경계(초과 면적 빨강) · CUSUM 띠, 지속 상위 3구간 바텀업 카드 (20일 창 분산 기여 막대) |
| IG2_six_etf_time_rings | 6종 시간 링 — 호 = 급변 구간 (두께 = 최대 σ/경계), 안쪽 흰 링 = 10번 C1, 흰 눈금 = CUSUM 경보일 (급변일과 겹침 0) |
| IG3_shock_constellation | 69구간 지속 × 스케일 별자리 + 지속 히스토그램 (20일 봉우리, 창 이탈 종료 24개) |

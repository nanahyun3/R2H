# W4 주장–근거 표

| # | 주장 | 결과 파일 | 계산 위치 | 노트북·그림 |
|---|---|---|---|---|
| C1 | 판정 VALID_ZERO_INTERVALS, 주분석 1,225일 판정 가능 100%, FINAL 0일, 구간 0개 | `results/w4_final.json · shock_intervals.csv` | `pipeline.verdict · intervals` | 09 §11, F24 |
| C2 | 민감도 4종 모두 17/17 AB 0일·구간 0 | `results/sensitivity_summary.csv` | `pipeline.sensitivity` | 09 §15, F25 |
| C3 | 주분석 최대 참여 A 12/6 · B 7/7 · AB 3/2 (q20/q60) | `results/global_by_period.csv` | `pipeline.global_by_period` | 09 §9, F16–F18 |
| C4 | GLOBAL_A 17/17 은 2020-03-16~04-06 (q20, 파일럿) 16일, 그날 B 3–6 | `results/global_daily_counts.csv` | `core.global_states` | 09 §9·§10, F21 |
| C5 | A∩B: A ETF-일의 12.6% (q20)·22.1% (q60) | `results/figure_captions.json F19` | `figures.f19_intersection` | 09 §8, F19 |
| C6 | B↑ 1,022 · B↓ 1,260 (q20 주분석 ETF-일) | `results/figure_captions.json F09` | `figures.f09_B_map` | 09 §6, F09 |
| C7 | KOSPI200 Core Pair |L| 중앙 0.894 %p, B↑ 87 · B↓ 71 | `results/figure_captions.json F10` | `core.pair_ratio_state` | 09 §7, F10 |
| C8 | 레버리지·인버스 정규화 비율 중앙 1.004·1.025, A 일치 ≥ 98.9% | `results/kospi200_aux_diagnostics.csv` | `pipeline.kospi_aux_table` | 09 §7, F05 |
| C9 | 한 그룹 제외 16/16 A·B·AB 모두 0일, 유일 병목 0일 | `results/bottleneck_groups.csv` | `pipeline.bottleneck` | 09 §12, F26 |
| C10 | W2 정의 재계산 80/80 일치, σ 대 √(252·mean r²) Spearman 중앙 0.992/0.997 | `evidence/w2_reconstruction_check.csv · results/comparison_w2_w3.csv` | `pipeline.w2_reference · compare_w2_w3` | 09 §14 |
| C11 | 사건 최대 A: 2024-08 10 · 2025-04 12 · 2022 9 (q20), 세 사건 FINAL 0 | `results/event_case_studies.csv` | `pipeline.event_cases` | 09 §13, F28–F30 |
| C12 | W3 에피소드 20건 동안 W4 AB 최대 3, FINAL 0 | `results/comparison_w2_w3.csv (w3_ 블록)` | `pipeline.compare_w2_w3` | 09 §14, F31 |
| C13 | Peer 20/20 매핑, PEER_UNAVAILABLE 0, 참조 42종, 늦은 상장 제외 10 | `results/peer_mapping.csv` | `scripts/t18_freeze_peer_mapping.py` | 09 §3, F06 |
| C14 | 영변동성 0건, Peer 부족 130 (전부 2019 132030) | `results/zero_volatility_audit.csv` | `core.peer_log_ratio` | 09 §15, F33 |
| C15 | 20·60일 그룹-일 Jaccard A 0.30 · AB 0.17 | `results/figure_captions.json F20` | `figures.f20_horizons` | 09 §10, F20 |

노트북 09 의 마지막 CLAIMS 셀이 해석 문단 수치 33개를 결과 파일과 다시 대조한다 (33/33).

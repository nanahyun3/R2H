# W4 그림 목록 (F01–F34)

모두 실제 계산 결과로 그렸다. PNG 320dpi 와 SVG 를 함께 둔다. 캡션 수치는 `results/figure_captions.json` 에 있다.

| 그림 | 묶음 | 내용 | 캡션 수치 (요약) |
|---|---|---|---|
| `F01_sigma20_grid` | A | 20종 20일 연환산 σ 시계열 + A 눈금 | `{"069500": {"A_days": 95, "max": 43.42, "median": 17.47}, "091170": {"A_days": 110, "max": 43.46, "median": 22.68}, "091180": {"A_days": 53, "max": 64.86, "m…` |
| `F02_sigma60_grid` | A | 20종 60일 연환산 σ 시계열 + A 눈금 | `{"069500": {"A_days": 90, "max": 29.5, "median": 18.17}, "091170": {"A_days": 74, "max": 34.95, "median": 23.76}, "091180": {"A_days": 0, "max": 48.16, "medi…` |
| `F03_level_vs_rank` | A | 절대 σ 수준(10–90분위·최대)과 주분석 A 비율 | `{"max_A_q20": ["153130", 0.2195918367], "zero_A_q60": ["091180", "143860", "261220"]}` |
| `F04_A_heatmap` | A | 20일·60일 A 상태 지도 | `{"q20_max_date": "2020-03-16", "q20_max_etf_A_same_day": 20, "q60_max_date": "2020-04-07", "q60_max_etf_A_same_day": 19}` |
| `F05_leverage_normalization` | A | 레버리지·인버스 배율 정규화 전후 | `{"ratio_114800": 1.0254, "ratio_122630": 1.0044}` |
| `F06_peer_network` | B | Peer Mapping 네트워크 (Tier·등급) | `{"late_excluded": 10, "n_peers": 42, "tier1_edges": 31, "tier2_edges": 24}` |
| `F07_peer_ratio_grid` | B | ETF별 Peer 로그비율 L 과 B↑/B↓ | `{"069500": {"B_DOWN": 30, "B_UP": 31}, "091170": {"B_DOWN": 50, "B_UP": 84}, "091180": {"B_DOWN": 77, "B_UP": 46}, "091230": {"B_DOWN": 119, "B_UP": 88}, "10…` |
| `F08_peer_ratio_rank_heat` | B | L 의 과거 분위 U_B 지도 | `{}` |
| `F09_B_direction_map` | B | B 양방향 사건 지도 | `{"q20": {"down": 1260, "up": 1022}, "q60": {"down": 1544, "up": 1364}}` |
| `F10_kospi200_four` | B | KOSPI200 4종 배율 보정 σ·Core Pair 비율·그룹 상태 | `{"core_B_DOWN": 71, "core_B_UP": 87, "core_L_abs_median_pctpt": 0.894, "group_AB_days": 8}` |
| `F11_domestic_peer` | B | 국내 업종·전략 ETF 자기 σ 대 Peer 중앙값 | `{"091170": {"AB": 20, "B_DOWN": 50, "B_UP": 84}, "091180": {"AB": 7, "B_DOWN": 77, "B_UP": 46}, "091230": {"AB": 26, "B_DOWN": 119, "B_UP": 88}, "117680": {"…` |
| `F12_overseas_bond_cmd_fx_peer` | B | 해외 주식·채권·원자재·통화 Peer 진단 | `{"132030": {"AB": 0, "B_DOWN": 47, "B_UP": 43}, "133690": {"AB": 4, "B_DOWN": 26, "B_UP": 106}, "148070": {"AB": 39, "B_DOWN": 82, "B_UP": 84}, "153130": {"A…` |
| `F13_group_A_timeline` | C | 17 그룹 A 타임라인 | `{"q20_max_all": 17, "q20_max_primary": 12, "q60_max_all": 16, "q60_max_primary": 6}` |
| `F14_group_B_timeline` | C | 17 그룹 B 타임라인 | `{"q20_max_all": 8, "q20_max_primary": 7, "q60_max_all": 10, "q60_max_primary": 7}` |
| `F15_group_AB_timeline` | C | 17 그룹 AB 타임라인 | `{"q20_max_all": 6, "q20_max_primary": 3, "q60_max_all": 5, "q60_max_primary": 2}` |
| `F16_count_A` | C | A 참여 그룹 수 | `{"pilot_max": {"20": 17, "60": 16}, "q20_max": 12, "q20_max_date": "2025-04-11", "q60_max": 6, "q60_max_date": "2022-11-21"}` |
| `F17_count_B` | C | B 참여 그룹 수 | `{"pilot_max": {"20": 8, "60": 10}, "q20_max": 7, "q20_max_date": "2021-04-09", "q60_max": 7, "q60_max_date": "2024-08-06"}` |
| `F18_count_AB` | C | AB 참여 그룹 수 | `{"pilot_max": {"20": 6, "60": 5}, "q20_max": 3, "q20_max_date": "2022-10-04", "q60_max": 2, "q60_max_date": "2024-04-11"}` |
| `F19_A_B_intersection` | C | A·B·AB 교집합 (ETF-일) | `{"q20": {"AB_share_of_A": 0.1261, "AB_total": 307, "A_total": 2434, "B_total": 2282}, "q60": {"AB_share_of_A": 0.2215, "AB_total": 457, "A_total": 2063, "B_t…` |
| `F20_horizon_20_vs_60` | C | 20일 대 60일 그룹 수 교차표·Jaccard | `{"A": 0.4742, "AB": 0.2596, "B": 0.3363, "jaccard_group_day_A": 0.3033, "jaccard_group_day_AB": 0.1747}` |
| `F21_global_A_17of17` | D | GLOBAL_A 17/17 충족일 | `{"q20_days17": 0, "q20_min_gap": 5, "q20_pilot_days17": 16, "q60_days17": 0, "q60_min_gap": 11, "q60_pilot_days17": 0}` |
| `F22_global_B_17of17` | D | GLOBAL_B 17/17 충족일 | `{"q20_days17": 0, "q20_min_gap": 10, "q20_pilot_days17": 0, "q60_days17": 0, "q60_min_gap": 10, "q60_pilot_days17": 0}` |
| `F23_global_AB_17of17` | D | GLOBAL_AB 17/17 충족일 | `{"q20_days17": 0, "q20_min_gap": 14, "q20_pilot_days17": 0, "q60_days17": 0, "q60_min_gap": 15, "q60_pilot_days17": 0}` |
| `F24_final_shock_timeline` | D | FINAL_SHOCK 전체 시계열·판정 가능일 | `{"n_intervals": 0, "primary_days": 1225, "primary_evaluable_days": 1225, "primary_evaluable_share": 1.0, "primary_final_true_days": 0, "verdict": "VALID_ZERO…` |
| `F25_interval_durations` | D | 급변 구간 지속기간 (0개) + 그룹별 AB 최장 지속 (진단) | `{"intervals_all_variants": [0, 0, 0, 0, 0], "max_group_run": {"20": 26, "60": 61}}` |
| `F26_bottleneck` | D | 17/17 병목 (그룹별 충족률·한 그룹 제외 진단) | `{"q20": {"loo_AB_max": 0, "loo_A_max": 0, "loo_B_max": 0, "sole_blocker_AB_max": 0}, "q60": {"loo_AB_max": 0, "loo_A_max": 0, "loo_B_max": 0, "sole_blocker_A…` |
| `F27_participation_distribution` | D | 0–17 참여 그룹 수 분포 | `{"q20_AB_max": 3, "q20_A_max": 12, "q20_B_max": 7, "q60_AB_max": 2, "q60_A_max": 6, "q60_B_max": 7}` |
| `F28_event_E2024_08` | E | 2024-08 사건: 가격·σ·U_A·B·그룹 수 vs W2·FINAL | `{"q20": {"final_days": 0, "max_n_A": 10, "max_n_AB": 3, "max_n_A_date": "2024-08-07", "max_n_B": 5}, "q60": {"final_days": 0, "max_n_A": 4, "max_n_AB": 2, "m…` |
| `F29_event_E2025_04` | E | 2025-04 사건 | `{"q20": {"final_days": 0, "max_n_A": 12, "max_n_AB": 1, "max_n_A_date": "2025-04-11", "max_n_B": 4}, "q60": {"final_days": 0, "max_n_A": 4, "max_n_AB": 1, "m…` |
| `F30_event_E2022_bond` | E | 2022 채권 사건 | `{"q20": {"final_days": 0, "max_n_A": 9, "max_n_AB": 3, "max_n_A_date": "2022-10-11", "max_n_B": 4}, "q60": {"final_days": 0, "max_n_A": 6, "max_n_AB": 1, "ma…` |
| `F31_w3_comparison` | E | W3 CUSUM 에피소드 대 W4 그룹 수 | `{"w3_episodes": 20, "w4_final_days_during_w3": 0, "w4_max_n_AB_during_w3": 3}` |
| `F32_definition_cases` | E | A만·B↑만·B↓만·AB 실제 사례 | `{"A 만 (자기 과거 고변동성, Peer 와 같이 움직임)": {"days": 222, "longest_run": ["2022-10-06", "2022-11-22"], "ticker": "148070"}, "AB (둘 다)": {"days": 83, "longest_run": […` |
| `F33_eligibility` | E | L 상태(결측·영분산·Peer 부족)와 연도별 판정 가능일 | `{"peer_insufficient_total": 130, "zero_den_total": 0, "zero_num_total": 0}` |
| `F34_summary_limits` | E | k 이상 동시 충족 일수 곡선·결론·한계 | `{"verdict": "VALID_ZERO_INTERVALS"}` |

묶음: A 개별 ETF 변동성 · B Peer 상대 · C 그룹 상태 · D 최종 구간 · E 기존 연구 대조.
진단 그림(F25 오른쪽, F26 의 한 그룹 제외)은 라벨이 아니다.

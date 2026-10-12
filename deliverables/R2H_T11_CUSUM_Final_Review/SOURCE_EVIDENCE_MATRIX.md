# SOURCE_EVIDENCE_MATRIX — 보고서 주장·수치 ↔ 원천

생성: `scripts/05_build_docx.py` (본문에서 사용한 claim 키를 자동 기록). 기준 커밋 `a346faf`. 값의 원본은 `claims.json`.

상태: VERIFIED = 이 작업에서 재계산/재실행 · REPORTED = 기존 결과에서만 확인 · EXTENSION = 이번 추가 실험 (extension/)

| claim 키 | 값 | 상태 | 원천 (파일 · 열 · 함수) | 비고 | 보고서 위치 |
|---|---|---|---|---|---|
| `E1_garch_unstandardized_n571_paper` | 85.7 | VERIFIED | extension/E1_residual_size.csv (garch_unstandardized, n=571, paper_1.3397) | EXTENSION · % · MC SE 0.4%p · R=10000 | 6.2 잔차 수준 크기 (E1) |
| `E1_iid_normal_n571_paper` | 4.5 | VERIFIED | extension/E1_residual_size.csv (iid_normal, n=571, paper_1.3397) | EXTENSION · % · MC SE 0.2%p · R=10000 | 6.2 잔차 수준 크기 (E1) |
| `E1_iid_normal_n60_paper` | 2.7 | VERIFIED | extension/E1_residual_size.csv (iid_normal, n=60, paper_1.3397) | EXTENSION · % · MC SE 0.2%p · R=10000 | 6.2 잔차 수준 크기 (E1) |
| `E1_iid_t5_n571_paper` | 3.4 | VERIFIED | extension/E1_residual_size.csv (iid_t5, n=571, paper_1.3397) | EXTENSION · % · MC SE 0.2%p · R=10000 | 6.2 잔차 수준 크기 (E1) |
| `E2_R` | 500 | VERIFIED | E2_pipeline_size_power_reps.csv | EXTENSION | 6.3 파이프라인 전체의 크기와 검정력 (E2) |
| `E2_break_A_rej13397` | 19.0 | VERIFIED | extension/E2_pipeline_size_power_summary.csv (break, A, posthoc_reject@paper_1.3397) | EXTENSION · % · MC SE 1.8 · R=500 | 요약 (Executive Summary); 6.3 파이프라인 전체의 크기와 검정력 (E2); 7.6 검정의 사용 가능 범위; 10. 결론 |
| `E2_break_A_w60_detect_share_by_end` | 27.0 | VERIFIED | extension/E2_pipeline_size_power_summary.csv (break, A, w60_detect_share_by_end) | EXTENSION · % · MC SE 2.0 · R=500 | 6.3 파이프라인 전체의 크기와 검정력 (E2) |
| `E2_break_A_w60_detect_within_20d` | 2.0 | VERIFIED | extension/E2_pipeline_size_power_summary.csv (break, A, w60_detect_within_20d) | EXTENSION · % · MC SE 0.6 · R=500 | 6.3 파이프라인 전체의 크기와 검정력 (E2) |
| `E2_break_A_w60_detect_within_60d` | 6.4 | VERIFIED | extension/E2_pipeline_size_power_summary.csv (break, A, w60_detect_within_60d) | EXTENSION · % · MC SE 1.1 · R=500 | 6.3 파이프라인 전체의 크기와 검정력 (E2); 7.3 경보 수와 탐지기의 질 (원칙 C) |
| `E2_break_A_w60_first_alarm_delay_median_days` | 138.0 | VERIFIED | extension/E2_pipeline_size_power_summary.csv (break, A, w60_first_alarm_delay_median_days) | EXTENSION · 거래일 · R=500 | 6.3 파이프라인 전체의 크기와 검정력 (E2) |
| `E2_break_A_w60_prebreak_episodes_per_year` | 0.09 | VERIFIED | extension/E2_pipeline_size_power_summary.csv (break, A, w60_prebreak_episodes_per_year) | EXTENSION · 연간 에피소드 · MC SE 0.02 · R=500 | 6.3 파이프라인 전체의 크기와 검정력 (E2) |
| `E2_break_B_rej13397` | 73.0 | VERIFIED | extension/E2_pipeline_size_power_summary.csv (break, B, posthoc_reject@paper_1.3397) | EXTENSION · % · MC SE 2.0 · R=500 | 6.3 파이프라인 전체의 크기와 검정력 (E2) |
| `E2_break_B_w60_detect_share_by_end` | 87.4 | VERIFIED | extension/E2_pipeline_size_power_summary.csv (break, B, w60_detect_share_by_end) | EXTENSION · % · MC SE 1.5 · R=500 | 6.3 파이프라인 전체의 크기와 검정력 (E2) |
| `E2_break_B_w60_detect_within_20d` | 28.2 | VERIFIED | extension/E2_pipeline_size_power_summary.csv (break, B, w60_detect_within_20d) | EXTENSION · % · MC SE 2.0 · R=500 | 6.3 파이프라인 전체의 크기와 검정력 (E2) |
| `E2_break_B_w60_detect_within_60d` | 51.2 | VERIFIED | extension/E2_pipeline_size_power_summary.csv (break, B, w60_detect_within_60d) | EXTENSION · % · MC SE 2.2 · R=500 | 6.3 파이프라인 전체의 크기와 검정력 (E2) |
| `E2_break_B_w60_first_alarm_delay_median_days` | 41.0 | VERIFIED | extension/E2_pipeline_size_power_summary.csv (break, B, w60_first_alarm_delay_median_days) | EXTENSION · 거래일 · R=500 | 6.3 파이프라인 전체의 크기와 검정력 (E2) |
| `E2_break_B_w60_prebreak_episodes_per_year` | 2.34 | VERIFIED | extension/E2_pipeline_size_power_summary.csv (break, B, w60_prebreak_episodes_per_year) | EXTENSION · 연간 에피소드 · MC SE 0.07 · R=500 | 6.3 파이프라인 전체의 크기와 검정력 (E2) |
| `E2_break_base_rej13397` | 28.8 | VERIFIED | extension/E2_pipeline_size_power_summary.csv (break, base, posthoc_reject@paper_1.3397) | EXTENSION · % · MC SE 2.0 · R=500 | 6.3 파이프라인 전체의 크기와 검정력 (E2) |
| `E2_break_base_w60_detect_share_by_end` | 99.6 | VERIFIED | extension/E2_pipeline_size_power_summary.csv (break, base, w60_detect_share_by_end) | EXTENSION · % · MC SE 0.3 · R=500 | 6.3 파이프라인 전체의 크기와 검정력 (E2) |
| `E2_break_base_w60_detect_within_20d` | 61.8 | VERIFIED | extension/E2_pipeline_size_power_summary.csv (break, base, w60_detect_within_20d) | EXTENSION · % · MC SE 2.2 · R=500 | 6.3 파이프라인 전체의 크기와 검정력 (E2) |
| `E2_break_base_w60_detect_within_60d` | 84.6 | VERIFIED | extension/E2_pipeline_size_power_summary.csv (break, base, w60_detect_within_60d) | EXTENSION · % · MC SE 1.6 · R=500 | 6.3 파이프라인 전체의 크기와 검정력 (E2) |
| `E2_break_base_w60_first_alarm_delay_median_days` | 12.0 | VERIFIED | extension/E2_pipeline_size_power_summary.csv (break, base, w60_first_alarm_delay_median_days) | EXTENSION · 거래일 · R=500 | 6.3 파이프라인 전체의 크기와 검정력 (E2) |
| `E2_break_base_w60_prebreak_episodes_per_year` | 4.34 | VERIFIED | extension/E2_pipeline_size_power_summary.csv (break, base, w60_prebreak_episodes_per_year) | EXTENSION · 연간 에피소드 · MC SE 0.08 · R=500 | 6.3 파이프라인 전체의 크기와 검정력 (E2) |
| `E2_eps_floor_share` | 98.8 | VERIFIED | E2 reps eps == 0.1 | EXTENSION · 합성 자료에서도 ε grid 하한 선택 비율 % | 6.3 파이프라인 전체의 크기와 검정력 (E2); 8. 연구 한계 |
| `E2_null_A_rej13397` | 2.4 | VERIFIED | extension/E2_pipeline_size_power_summary.csv (null, A, posthoc_reject@paper_1.3397) | EXTENSION · % · MC SE 0.7 · R=500 | 요약 (Executive Summary); 6.3 파이프라인 전체의 크기와 검정력 (E2); 10. 결론 |
| `E2_null_A_rej13581` | 2.4 | VERIFIED | extension/E2_pipeline_size_power_summary.csv (null, A, posthoc_reject@kolmogorov_1.3581) | EXTENSION · % · MC SE 0.7 · R=500 | 6.3 파이프라인 전체의 크기와 검정력 (E2) |
| `E2_null_A_w60_test_any_alarm_share` | 12.8 | VERIFIED | extension/E2_pipeline_size_power_summary.csv (null, A, w60_test_any_alarm_share) | EXTENSION · % · R=500 | 6.3 파이프라인 전체의 크기와 검정력 (E2) |
| `E2_null_A_w60_test_episodes_per_year` | 0.1 | VERIFIED | extension/E2_pipeline_size_power_summary.csv (null, A, w60_test_episodes_per_year) | EXTENSION · 연간 에피소드 · MC SE 0.01 · R=500 | 6.3 파이프라인 전체의 크기와 검정력 (E2); 7.3 경보 수와 탐지기의 질 (원칙 C) |
| `E2_null_B_rej13397` | 34.0 | VERIFIED | extension/E2_pipeline_size_power_summary.csv (null, B, posthoc_reject@paper_1.3397) | EXTENSION · % · MC SE 2.1 · R=500 | 요약 (Executive Summary); 6.3 파이프라인 전체의 크기와 검정력 (E2); 7.4 정책 차이와 우월성 (원칙 D); 7.6 검정의 사용 가능 범위; 10. 결론 |
| `E2_null_B_rej13581` | 32.4 | VERIFIED | extension/E2_pipeline_size_power_summary.csv (null, B, posthoc_reject@kolmogorov_1.3581) | EXTENSION · % · MC SE 2.1 · R=500 | 6.3 파이프라인 전체의 크기와 검정력 (E2) |
| `E2_null_B_w60_test_any_alarm_share` | 98.2 | VERIFIED | extension/E2_pipeline_size_power_summary.csv (null, B, w60_test_any_alarm_share) | EXTENSION · % · R=500 | 6.3 파이프라인 전체의 크기와 검정력 (E2) |
| `E2_null_B_w60_test_episodes_per_year` | 2.41 | VERIFIED | extension/E2_pipeline_size_power_summary.csv (null, B, w60_test_episodes_per_year) | EXTENSION · 연간 에피소드 · MC SE 0.06 · R=500 | 6.3 파이프라인 전체의 크기와 검정력 (E2); 6.6 정책 B 이동창 (E5) |
| `E2_null_base_rej13397` | 24.6 | VERIFIED | extension/E2_pipeline_size_power_summary.csv (null, base, posthoc_reject@paper_1.3397) | EXTENSION · % · MC SE 1.9 · R=500 | 요약 (Executive Summary); 6.3 파이프라인 전체의 크기와 검정력 (E2); 10. 결론 |
| `E2_null_base_rej13581` | 23.2 | VERIFIED | extension/E2_pipeline_size_power_summary.csv (null, base, posthoc_reject@kolmogorov_1.3581) | EXTENSION · % · MC SE 1.9 · R=500 | 6.3 파이프라인 전체의 크기와 검정력 (E2) |
| `E2_null_base_w60_test_any_alarm_share` | 100.0 | VERIFIED | extension/E2_pipeline_size_power_summary.csv (null, base, w60_test_any_alarm_share) | EXTENSION · % · R=500 | 6.3 파이프라인 전체의 크기와 검정력 (E2) |
| `E2_null_base_w60_test_episodes_per_year` | 4.1 | VERIFIED | extension/E2_pipeline_size_power_summary.csv (null, base, w60_test_episodes_per_year) | EXTENSION · 연간 에피소드 · MC SE 0.05 · R=500 | 6.3 파이프라인 전체의 크기와 검정력 (E2); 7.3 경보 수와 탐지기의 질 (원칙 C) |
| `E3_c571_iid_median` | 1.31 | VERIFIED | E3_stationary_bootstrap.csv | EXTENSION | 6.5 귀무 생성 방법의 민감도 (E3) |
| `E3_c571_sb_153130` | 2.19 | VERIFIED | E3 153130 | EXTENSION | 6.5 귀무 생성 방법의 민감도 (E3) |
| `E3_c571_sb_median` | 1.04 | VERIFIED | E3_stationary_bootstrap.csv | EXTENSION | 6.5 귀무 생성 방법의 민감도 (E3) |
| `E3_rate_iid` | 0.47 | VERIFIED | E3 rate_test_w60_iid 평균 | EXTENSION | 6.5 귀무 생성 방법의 민감도 (E3) |
| `E3_rate_sb` | 1.62 | VERIFIED | E3 rate_test_w60_sb20 평균 | EXTENSION | 6.5 귀무 생성 방법의 민감도 (E3) |
| `E3_reject_both` | 2 | VERIFIED | E3_stationary_bootstrap.csv | EXTENSION | 요약 (Executive Summary); 6.5 귀무 생성 방법의 민감도 (E3) |
| `E3_reject_iid` | 069500, 091230, 153130, 261220 | VERIFIED | E3_stationary_bootstrap.csv reject_iid | EXTENSION | 6.5 귀무 생성 방법의 민감도 (E3) |
| `E3_reject_sb` | 069500, 091230, 143860, 132030 | VERIFIED | E3_stationary_bootstrap.csv reject_sb20 | EXTENSION | 6.5 귀무 생성 방법의 민감도 (E3) |
| `E4_identical` | 18/18 | VERIFIED | extension/E4_time_integrity.json *_identical_before_t0 | EXTENSION | 6.7 시점 무결성과 정보 누수 (E4) |
| `E4_t0` | 2025-08-22 | VERIFIED | E4_time_integrity.json | EXTENSION | 6.7 시점 무결성과 정보 누수 (E4) |
| `E5_rate_A` | 0.47 | VERIFIED | E5_policyB_rolling_w60.csv | EXTENSION | 6.6 정책 B 이동창 (E5) |
| `E5_rate_B` | 2.41 | VERIFIED | E5_policyB_rolling_w60.csv | EXTENSION | 6.6 정책 B 이동창 (E5) |
| `E5_zero_A` | 10 | VERIFIED | E5_policyB_rolling_w60.csv | EXTENSION | 6.6 정책 B 이동창 (E5) |
| `E5_zero_B` | 0 | VERIFIED | E5_policyB_rolling_w60.csv | EXTENSION | 6.6 정책 B 이동창 (E5) |
| `E6_base_test_lrv` | 1.49 | VERIFIED | E6_residual_dependence_etf.csv 중앙값 | EXTENSION | 6.4 잔차 제곱의 의존성 (E6) |
| `E6_base_test_lt1` | 0 | VERIFIED | E6_residual_dependence_etf.csv lrv < 1 개수 | EXTENSION | 6.4 잔차 제곱의 의존성 (E6) |
| `E6_sim_A_lrv` | 0.66 | VERIFIED | E6_residual_dependence_sim.csv 중앙값 | EXTENSION | 요약 (Executive Summary); 6.4 잔차 제곱의 의존성 (E6) |
| `E6_sim_B_lrv` | 1.02 | VERIFIED | E6_residual_dependence_sim.csv 중앙값 | EXTENSION | 6.4 잔차 제곱의 의존성 (E6) |
| `E6_svrA_fit_lrv` | 0.68 | VERIFIED | E6_residual_dependence_etf.csv 중앙값 | EXTENSION | 6.4 잔차 제곱의 의존성 (E6) |
| `E6_svrA_fit_lt1` | 19 | VERIFIED | E6_residual_dependence_etf.csv lrv < 1 개수 | EXTENSION | 6.4 잔차 제곱의 의존성 (E6) |
| `E6_svrA_test_acf` | -0.17 | VERIFIED | E6 acf lag1–5 합 중앙값 | EXTENSION | 6.4 잔차 제곱의 의존성 (E6) |
| `E6_svrA_test_lrv` | 0.91 | VERIFIED | E6_residual_dependence_etf.csv 중앙값 | EXTENSION | 요약 (Executive Summary); 6.4 잔차 제곱의 의존성 (E6) |
| `E6_svrA_test_lt1` | 18 | VERIFIED | E6_residual_dependence_etf.csv lrv < 1 개수 | EXTENSION | 6.4 잔차 제곱의 의존성 (E6) |
| `E6_svrB_test_lrv` | 1.19 | VERIFIED | E6_residual_dependence_etf.csv 중앙값 | EXTENSION | 6.4 잔차 제곱의 의존성 (E6) |
| `ab_T_B_gt_A` | 17 | VERIFIED | policy_pairs.csv T_B > T_A | 20종 중 | 5.2 정책 A와 B의 대응 비교 |
| `ab_both_reject` | 2 | VERIFIED | policy_pairs.csv |  | 5.2 정책 A와 B의 대응 비교 |
| `ab_cvB_lt_cvA` | 20 | VERIFIED | policy_pairs.csv cv_var_B < cv_var_A | 검정 구간 σ̂² 변동계수 — B 가 덜 변동하는 ETF 수 | 5.2 정책 A와 B의 대응 비교; 7.6 검정의 사용 가능 범위 |
| `ab_cv_A_median` | 1.064 | VERIFIED | policy_pairs.csv cv_var_A 중앙값 |  | 5.2 정책 A와 B의 대응 비교 |
| `ab_cv_B_median` | 0.765 | VERIFIED | policy_pairs.csv cv_var_B 중앙값 |  | 5.2 정책 A와 B의 대응 비교 |
| `ab_disagree` | 7 | VERIFIED | policy_pairs.csv rej_A != rej_B |  | 5.2 정책 A와 B의 대응 비교 |
| `ab_khat_same` | 5 | VERIFIED | policy_pairs.csv khat_gap_days == 0 |  | 5.2 정책 A와 B의 대응 비교 |
| `c_normal_n571` | 1.3298 | VERIFIED | 01_recompute: iid N(0,1) MC 20,000회, n=571, seed [20261012,571,9] |  | 4.4 점근분포와 임계값 — 적용 가능성 감사; 5.1 전체 검정 구간 사후 검정 |
| `crit_max_abs_diff` | 4.990471596855173e-06 | VERIFIED | critical_recomputed.csv | CSV 반올림 6자리 대비 | 5.4 관측창별 경보 빈도와 분모 |
| `crit_normal_w20` | 1.182 | VERIFIED | results/critical_values.csv c_normal |  | 4.4 점근분포와 임계값 — 적용 가능성 감사 |
| `data_version` | 5f20e3e0073b521a | REPORTED | results/run_manifest.json |  | 표지; 3.1 데이터 카드; D. Git 및 데이터 식별자 |
| `first_last` | 2019-01-03 ~ 2026-10-02 | VERIFIED | t11_state.npz dates |  | 3.1 데이터 카드 |
| `fs_A_khat_2026_01` | 8 | VERIFIED | fullsample_recomputed.csv 정책 A k̂ 2026-01 |  | 5.1 전체 검정 구간 사후 검정 |
| `fs_T_median_A` | 0.859 | VERIFIED | fullsample_recomputed.csv T 중앙값 |  | 5.1 전체 검정 구간 사후 검정 |
| `fs_T_median_B` | 1.323 | VERIFIED | fullsample_recomputed.csv T 중앙값 |  | 5.1 전체 검정 구간 사후 검정 |
| `fs_T_median_base` | 0.812 | VERIFIED | fullsample_recomputed.csv T 중앙값 |  | 5.1 전체 검정 구간 사후 검정 |
| `fs_khat_match` | 60 | VERIFIED | fullsample_recomputed.csv khat == khat_committed | 60행 중 | 5.1 전체 검정 구간 사후 검정 |
| `fs_max_abs_diff` | 4.857376488587306e-06 | VERIFIED | analysis/fullsample_recomputed.csv abs_diff (vs results/fullsample_tests.csv T) |  | 요약 (Executive Summary); 5.1 전체 검정 구간 사후 검정 |
| `fs_reject_A` | 2 | VERIFIED | fullsample_recomputed.csv reject_1.3397 |  | 요약 (Executive Summary); 5.1 전체 검정 구간 사후 검정; 7.1 조건부분산 설명 이후의 구조변화 (RQ1); 7.6 검정의 사용 가능 범위; 10. 결론 |
| `fs_reject_A_boot` | 4 | VERIFIED | fullsample_recomputed.csv reject_boot_n | EXTENSION 성격의 재판정 — ETF 별 iid 부트스트랩 임계값 (n_test 길이) | 5.1 전체 검정 구간 사후 검정 |
| `fs_reject_A_kolm` | 1 | VERIFIED | fullsample_recomputed.csv reject_kolmogorov |  | 5.1 전체 검정 구간 사후 검정; 10. 결론 |
| `fs_reject_A_normal` | 2 | VERIFIED | fullsample_recomputed.csv reject_normal_n571 |  | 5.1 전체 검정 구간 사후 검정 |
| `fs_reject_B` | 9 | VERIFIED | fullsample_recomputed.csv reject_1.3397 |  | 요약 (Executive Summary); 5.1 전체 검정 구간 사후 검정; 7.6 검정의 사용 가능 범위; 10. 결론 |
| `fs_reject_B_boot` | 11 | VERIFIED | fullsample_recomputed.csv reject_boot_n | EXTENSION 성격의 재판정 — ETF 별 iid 부트스트랩 임계값 (n_test 길이) | 5.1 전체 검정 구간 사후 검정 |
| `fs_reject_B_kolm` | 8 | VERIFIED | fullsample_recomputed.csv reject_kolmogorov |  | 5.1 전체 검정 구간 사후 검정 |
| `fs_reject_B_normal` | 9 | VERIFIED | fullsample_recomputed.csv reject_normal_n571 |  | 5.1 전체 검정 구간 사후 검정 |
| `fs_reject_base` | 1 | VERIFIED | fullsample_recomputed.csv reject_1.3397 |  | 요약 (Executive Summary); 5.1 전체 검정 구간 사후 검정; 10. 결론 |
| `fs_reject_base_boot` | 1 | VERIFIED | fullsample_recomputed.csv reject_boot_n | EXTENSION 성격의 재판정 — ETF 별 iid 부트스트랩 임계값 (n_test 길이) | 5.1 전체 검정 구간 사후 검정 |
| `fs_reject_base_kolm` | 1 | VERIFIED | fullsample_recomputed.csv reject_kolmogorov |  | 5.1 전체 검정 구간 사후 검정 |
| `fs_reject_base_normal` | 1 | VERIFIED | fullsample_recomputed.csv reject_normal_n571 |  | 5.1 전체 검정 구간 사후 검정 |
| `fs_reject_match` | 60 | VERIFIED | fullsample_recomputed.csv | 60행 중 | 5.1 전체 검정 구간 사후 검정 |
| `fs_rejected_A` | 069500, 091230 | VERIFIED | fullsample_recomputed.csv |  | 5.1 전체 검정 구간 사후 검정 |
| `fs_rejected_B` | 069500, 122630, 114800, 091230, 161510, 133690, 153130, 132030, 261220 | VERIFIED | fullsample_recomputed.csv |  | 5.1 전체 검정 구간 사후 검정 |
| `fs_rejected_base` | 153130 | VERIFIED | fullsample_recomputed.csv |  | 5.1 전체 검정 구간 사후 검정 |
| `grid_eps_floor` | 20 | VERIFIED | results/fit_summary.csv epsilon == 0.1 (grid 하한) | 20종 중 | 3.2 실험 설계와 파라미터 |
| `k200_TA_069500` | 1.403 | VERIFIED | fullsample_recomputed.csv |  | 요약 (Executive Summary); 5.3 동일 기초지수 ETF의 일관성; 7.6 검정의 사용 가능 범위 |
| `k200_TA_102110` | 0.646 | VERIFIED | fullsample_recomputed.csv |  | 요약 (Executive Summary); 5.3 동일 기초지수 ETF의 일관성; 7.6 검정의 사용 가능 범위 |
| `k200_corr_eA` | 0.9891 | VERIFIED | kospi200_group.csv |  | 5.3 동일 기초지수 ETF의 일관성 |
| `k200_corr_r` | 0.9994 | VERIFIED | kospi200_group.csv |  | 요약 (Executive Summary); 5.3 동일 기초지수 ETF의 일관성; 6.8 다중 ETF와 다중 창의 의존 |
| `k200_params_069500` | C=1, γ²=0.5, ε=0.1 | REPORTED | results/fit_summary.csv |  | 5.3 동일 기초지수 ETF의 일관성 |
| `k200_params_102110` | C=100, γ²=1, ε=0.1 | REPORTED | results/fit_summary.csv |  | 5.3 동일 기초지수 ETF의 일관성 |
| `k200_roll60_corr` | 0.868 | VERIFIED | rolling_cusum(res svrA, 60) 069500 vs 102110 |  | 5.3 동일 기초지수 ETF의 일관성 |
| `k200_sigma_ratio_p05` | 0.682 | VERIFIED | sqrt(varA 069500 / varA 102110) 검정 구간 5% 분위 |  | 5.3 동일 기초지수 ETF의 일관성 |
| `k200_sigma_ratio_p95` | 1.062 | VERIFIED | 같은 비의 95% 분위 |  | 5.3 동일 기초지수 ETF의 일관성 |
| `kolmogorov_q95` | 1.3581 | VERIFIED | 01_recompute.kolmogorov_quantile (해석적 급수) |  | 4.4 점근분포와 임계값 — 적용 가능성 감사 |
| `n_returns` | 1902 | VERIFIED | t11_state.npz dates |  | 3.1 데이터 카드 |
| `n_test` | 571 | VERIFIED | results/fit_summary.csv |  | 3.1 데이터 카드 |
| `n_train` | 932 | VERIFIED | results/fit_summary.csv |  | 3.1 데이터 카드 |
| `n_val` | 399 | VERIFIED | results/fit_summary.csv |  | 3.1 데이터 카드 |
| `null_max_diff` | 0.0013286750788643609 | VERIFIED | zone_rates.csv null_recomputed vs committed |  | 5.4 관측창별 경보 빈도와 분모 |
| `paper_cv` | 1.3397 | REPORTED | src/r2h/paper2020/cusum.py PAPER_CRITICAL_VALUE_5_PERCENT |  | 4.4 점근분포와 임계값 — 적용 가능성 감사 |
| `paper_cv_implied_level` | 0.0552 | VERIFIED | 01_recompute.kolmogorov_cdf(1.3397) | 1.3397 을 Kolmogorov 분포로 읽으면 이 상측 확률 — 원문 값의 유도 근거는 확인하지 못함 | 4.4 점근분포와 임계값 — 적용 가능성 감사 |
| `rate_base_w120_all` | 2.73 | VERIFIED | zone_rates.csv 20종 평균 (전 기간 분모) |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_base_w120_fit` | 2.81 | VERIFIED | zone_rates.csv 20종 평균 (적합 구간, in-sample) |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_base_w120_null` | 0.97 | VERIFIED | results/null_alarm_rate.csv 20종 평균 (iid 재표집) |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_base_w120_test` | 3.62 | VERIFIED | zone_rates.csv 20종 평균 (순수 검정 구간) |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_base_w120_test_gt_null` | 19 | VERIFIED | zone_rates.csv |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_base_w120_test_zero` | 0 | VERIFIED | zone_rates.csv episodes_test == 0 |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_base_w20_all` | 6.26 | VERIFIED | zone_rates.csv 20종 평균 (전 기간 분모) |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_base_w20_fit` | 6.33 | VERIFIED | zone_rates.csv 20종 평균 (적합 구간, in-sample) |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_base_w20_null` | 4.04 | VERIFIED | results/null_alarm_rate.csv 20종 평균 (iid 재표집) |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_base_w20_test` | 6.76 | VERIFIED | zone_rates.csv 20종 평균 (순수 검정 구간) |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_base_w20_test_gt_null` | 19 | VERIFIED | zone_rates.csv |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_base_w20_test_zero` | 0 | VERIFIED | zone_rates.csv episodes_test == 0 |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_base_w252_all` | 1.28 | VERIFIED | zone_rates.csv 20종 평균 (전 기간 분모) |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_base_w252_fit` | 1.4 | VERIFIED | zone_rates.csv 20종 평균 (적합 구간, in-sample) |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_base_w252_null` | 0.57 | VERIFIED | results/null_alarm_rate.csv 20종 평균 (iid 재표집) |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_base_w252_test` | 2.09 | VERIFIED | zone_rates.csv 20종 평균 (순수 검정 구간) |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_base_w252_test_gt_null` | 20 | VERIFIED | zone_rates.csv |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_base_w252_test_zero` | 0 | VERIFIED | zone_rates.csv episodes_test == 0 |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_base_w30_all` | 5.31 | VERIFIED | zone_rates.csv 20종 평균 (전 기간 분모) |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_base_w30_fit` | 5.44 | VERIFIED | zone_rates.csv 20종 평균 (적합 구간, in-sample) |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_base_w30_null` | 2.93 | VERIFIED | results/null_alarm_rate.csv 20종 평균 (iid 재표집) |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_base_w30_test` | 5.86 | VERIFIED | zone_rates.csv 20종 평균 (순수 검정 구간) |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_base_w30_test_gt_null` | 20 | VERIFIED | zone_rates.csv |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_base_w30_test_zero` | 0 | VERIFIED | zone_rates.csv episodes_test == 0 |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_base_w60_all` | 3.82 | VERIFIED | zone_rates.csv 20종 평균 (전 기간 분모) |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_base_w60_fit` | 3.84 | VERIFIED | zone_rates.csv 20종 평균 (적합 구간, in-sample) |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_base_w60_null` | 1.7 | VERIFIED | results/null_alarm_rate.csv 20종 평균 (iid 재표집) |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_base_w60_test` | 4.48 | VERIFIED | zone_rates.csv 20종 평균 (순수 검정 구간) |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_base_w60_test_gt_null` | 19 | VERIFIED | zone_rates.csv |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_base_w60_test_zero` | 0 | VERIFIED | zone_rates.csv episodes_test == 0 |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_denominator` | 전 기간 1902 거래일 / 252 = 7.548년 | VERIFIED | pipeline.py obs_rate = size / (len(idx)/252) |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_svrA_w120_all` | 0.25 | VERIFIED | zone_rates.csv 20종 평균 (전 기간 분모) |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_svrA_w120_fit` | 0.22 | VERIFIED | zone_rates.csv 20종 평균 (적합 구간, in-sample) |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_svrA_w120_null` | 0.99 | VERIFIED | results/null_alarm_rate.csv 20종 평균 (iid 재표집) |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_svrA_w120_test` | 0.39 | VERIFIED | zone_rates.csv 20종 평균 (순수 검정 구간) |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_svrA_w120_test_gt_null` | 3 | VERIFIED | zone_rates.csv |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_svrA_w120_test_zero` | 13 | VERIFIED | zone_rates.csv episodes_test == 0 |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_svrA_w20_all` | 2.23 | VERIFIED | zone_rates.csv 20종 평균 (전 기간 분모) |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_svrA_w20_fit` | 2.1 | VERIFIED | zone_rates.csv 20종 평균 (적합 구간, in-sample) |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_svrA_w20_null` | 4.05 | VERIFIED | results/null_alarm_rate.csv 20종 평균 (iid 재표집) |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_svrA_w20_test` | 2.63 | VERIFIED | zone_rates.csv 20종 평균 (순수 검정 구간) |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_svrA_w20_test_gt_null` | 3 | VERIFIED | zone_rates.csv |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_svrA_w20_test_zero` | 0 | VERIFIED | zone_rates.csv episodes_test == 0 |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_svrA_w252_all` | 0.21 | VERIFIED | zone_rates.csv 20종 평균 (전 기간 분모) |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_svrA_w252_fit` | 0.21 | VERIFIED | zone_rates.csv 20종 평균 (적합 구간, in-sample) |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_svrA_w252_null` | 0.56 | VERIFIED | results/null_alarm_rate.csv 20종 평균 (iid 재표집) |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_svrA_w252_test` | 0.47 | VERIFIED | zone_rates.csv 20종 평균 (순수 검정 구간) |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_svrA_w252_test_gt_null` | 6 | VERIFIED | zone_rates.csv |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_svrA_w252_test_zero` | 14 | VERIFIED | zone_rates.csv episodes_test == 0 |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_svrA_w30_all` | 0.87 | VERIFIED | zone_rates.csv 20종 평균 (전 기간 분모) |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_svrA_w30_fit` | 0.75 | VERIFIED | zone_rates.csv 20종 평균 (적합 구간, in-sample) |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_svrA_w30_null` | 3.02 | VERIFIED | results/null_alarm_rate.csv 20종 평균 (iid 재표집) |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_svrA_w30_test` | 1.26 | VERIFIED | zone_rates.csv 20종 평균 (순수 검정 구간) |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_svrA_w30_test_gt_null` | 0 | VERIFIED | zone_rates.csv |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_svrA_w30_test_zero` | 1 | VERIFIED | zone_rates.csv episodes_test == 0 |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_svrA_w60_all` | 0.39 | VERIFIED | zone_rates.csv 20종 평균 (전 기간 분모) |  | 요약 (Executive Summary); 5.4 관측창별 경보 빈도와 분모 |
| `rate_svrA_w60_fit` | 0.35 | VERIFIED | zone_rates.csv 20종 평균 (적합 구간, in-sample) |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_svrA_w60_null` | 1.71 | VERIFIED | results/null_alarm_rate.csv 20종 평균 (iid 재표집) |  | 요약 (Executive Summary); 5.4 관측창별 경보 빈도와 분모 |
| `rate_svrA_w60_test` | 0.47 | VERIFIED | zone_rates.csv 20종 평균 (순수 검정 구간) |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_svrA_w60_test_gt_null` | 2 | VERIFIED | zone_rates.csv |  | 5.4 관측창별 경보 빈도와 분모 |
| `rate_svrA_w60_test_zero` | 10 | VERIFIED | zone_rates.csv episodes_test == 0 |  | 5.4 관측창별 경보 빈도와 분모 |
| `split_date` | 2024-05-29 | VERIFIED | results/fit_summary.csv |  | 3.1 데이터 카드 |
| `trackb_in_ci` | {"clip": "1/45", "raise": "9/45", "recursive": "10/45"} | REPORTED | outputs/cache/031157d…ORIGINAL_VS_REPRODUCED.csv n=500 *_paper_in_ci | 원 감사 패키지의 Wilson 95% CI 판정을 그대로 집계 (반복은 재실행하지 않음) | 6.9 |
| `vol_069500_fit` | 19.6 | VERIFIED | t11_state.npz r__069500 적합 구간 std×√252 | %/년 | 3.1 데이터 카드 |
| `vol_069500_test` | 42.4 | VERIFIED | t11_state.npz r__069500 검정 구간 std×√252 | %/년 | 3.1 데이터 카드 |
| `vol_ratio_median` | 1.29 | VERIFIED | 검정/적합 연율화 변동성 비 중앙값 (20종) |  | 3.1 데이터 카드 |
| `vol_test_gt_fit` | 16 | VERIFIED | t11_state.npz 검정 구간 변동성 > 적합 구간인 ETF 수 |  | 3.1 데이터 카드 |
| `yearly_base_2020` | 85 | VERIFIED | analysis/yearly_reject_share.csv (%, 1.3397) |  | 5.5 연도 블록과 종목별 시계열 진단 |
| `yearly_base_2026` | 55 | VERIFIED | analysis/yearly_reject_share.csv (%, 1.3397) |  | 5.5 연도 블록과 종목별 시계열 진단 |
| `yearly_max_abs_diff` | 4.92921035655236e-06 | VERIFIED | yearly_blocks() vs results/yearly_blocks.csv |  | 5.5 연도 블록과 종목별 시계열 진단 |
| `yearly_svrA_2020` | 5 | VERIFIED | analysis/yearly_reject_share.csv (%, 1.3397) |  | 5.5 연도 블록과 종목별 시계열 진단 |
| `yearly_svrA_2022` | 5 | VERIFIED | analysis/yearly_reject_share.csv (%, 1.3397) |  | 5.5 연도 블록과 종목별 시계열 진단 |

## 표·그림의 원천

| 보고서 요소 | 원천 |
|---|---|
| 표 8 · 표 18 (부록 C) | `analysis/fullsample_recomputed.csv` ← `01_recompute.py` (캐시 잔차 + `cusum_squares_test`) |
| 표 9 (KOSPI200) | `analysis/kospi200_group.csv` |
| 표 10 (경보 빈도) | `analysis/zone_rates.csv` ← `rolling_cusum`, `episodes`, `null_alarm_episodes_per_year` |
| 표 11 (E1) | `extension/E1_residual_size.csv` |
| 표 12 (E2) · 그림 11 | `extension/E2_pipeline_size_power_summary.csv`, `_reps.csv` |
| 표 13 (Track B) | `outputs/cache/031157d__…EMPIRICAL_ORIGINAL_VS_REPRODUCED.csv` → `analysis/trackb_empirical.csv` (REPORTED) |
| 그림 4 | `analysis/fullsample_recomputed.csv` |
| 그림 6 | `results/critical_values.csv` |
| 그림 7 | `analysis/zone_rates.csv` |
| 그림 5·10 · 그림 2 | `outputs/cache/t11_state.npz` (varA, varB, res), `results/fit_summary.csv`, `results/critical_values.csv` |
| 그림 12 | `extension/E6_*`, `extension/E3_stationary_bootstrap.csv` |
| 그림 8·9 (재사용) | `docs/figures/svrgarch/04_rolling_heatmaps.png`, `10_yearly_blocks.png` (커밋 a346faf) |

사용한 claim 184개 / 전체 255개.

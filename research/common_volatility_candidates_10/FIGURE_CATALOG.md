# 10번 그림 목록 (G01–G16, PNG 320dpi + SVG)

모든 그림은 `src/r2h/common_vol/figures.py` 가 `pipeline.run()` 결과로 그린다. 노트북과 `scripts/run_t19_pipeline.py` 두 경로의 결과가 바이트 동일하다.

| 그림 | 노트북 장 | 내용 |
|---|---|---|
| G01_group_A_state_maps | §4 | 17 그룹 × 주분석 일별 A 상태 (q20·q60) 와 같은 날 참여 수 N_A, k 선 |
| G02_count_and_candidate_intervals | §8 | N_A 시계열 위 C1–C3 (q20)·C4 (q60) 구간 음영 |
| G03_k_survival_curves | §5 | k=1–17 의 N_A≥k 일수·구간 수 (구간 수 비단조) |
| G04_rule_ribbons | §7 | 12개 규칙의 일별 1/0 리본 (포함관계) |
| G05_candidate_gantt | §8 | 주 후보 구간 12개 간트 (동시 최대 / ever / 매일) |
| G06_k_and_q_effects | §9 | k 고정 q 비교 막대, 주 후보 구간 특성 점그림 |
| G07_rule_jaccard | §11 | 규칙 간 날짜 Jaccard |
| G08_split_and_vanish | §10 | q20 k 6→9→10→12 의 소멸·축소·분할 |
| G09_event_E1_2022_bond | §12 | 2022 사례 (N_A, 그룹 상태 q20·q60, 규칙 리본, B·AB) |
| G10_event_E2_2024_08 | §13 | 2024-08 사례 |
| G11_event_E3_2025_04 | §14 | 2025-04 사례 |
| G12_group_participation | §15 | 주 후보별 그룹 참여 비율 vs 평소 비율 |
| G13_simultaneous_vs_ever | §9 | 구간별 매일·동시 최대·ever 그룹 수 |
| G14_B_AB_inside_outside | §16 | 후보일 안팎 N_B·N_AB (보조) |
| G15_yearly_candidate_days | §19 | 연도별 후보일 (주분석) |
| G16_pilot2020_and_2026 | §17 | 2020 파일럿·2026 부분 연도 (주분석 제외) |

## v2 (`10-lock-2`)

| 그림 | 장 | 내용 |
|---|---|---|
| G17_null_kstar | D1 | 관측 vs 원형 이동 귀무 일수, 기간 최대 우연 확률, k*_fw |
| G18_asset_class_balance | D2 | 주식 × 비주식 동시 급변 2차원 분포, 시간축 비율 |
| G19_hysteresis_balance_intervals | D3 | C1·H1·C2·H2·WB 구간 리본 (2022-10·2024-08·2025-04 확대) |
| G20_intensity_index | D4 | 연속 강도 지수 자산군 누적, N_A 비교 |
| G21_q20_q60_lead_lag | D5 | 20일 → 60일 시차 상관 |
| G22_c1_bottomup | D6 | C1 구간 그룹 진입 순서·종료 원인 (창 이탈) |
| infographics/IG10_1_definitions_vs_chance | 발표 | 정의 비교 + 우연 기준선 (Pretendard 밝은 판) |
| infographics/IG10_2_c1_three_intervals | 발표 | 같은 C1, 다른 자산 — 세 구간 해부 |

## PART R (모델 입력)

| 그림 | 내용 |
|---|---|
| G23_etf_interval_swimlane | ETF 20종 A20 급변 구간 2021–2026, C1 테두리, 구간·일수 |
| G24_model_input_examples | D2 사건 정렬 창 예시 2개 (KOSPI200 2024-08 단일 충격 · 국고채 2022-09 누적) — 13 × 60 z 점수 |
| G25_dataset_balance | D1 양성 비율·분할별 창 수 |
| infographics/IG10_3_labels_to_model_input | 20종 급변 지도 + 창 하나 + 데이터셋 3종 + 분할·누수 방지 |

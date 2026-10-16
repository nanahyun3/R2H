# R2H T12 — ETF 20종 연간 expanding SVR–GARCH CUSUM 다축 진단 연구보고서

**프로토콜** `T12v2-lock-1` (실 데이터 실행 전 커밋 `cb9e9ca`) · **코드 기준** `nanahyun3/R2H` `1012@a346faf` → 작업 브랜치 `1012_Annual_SVR–GARCH-CUSUM` · **데이터** `5f20e3e0073b521a` (20/20 해시 일치) · **작성** 2026-10-12

> 이 보고서는 통계적 구조변화 검정이 **어떻게 작동했고 어디까지 구별할 수 있는지**를 진단한다. 급등 예측, 국면 판정, 투자 성과에 대해서는 아무것도 주장하지 않는다. 실제 금융 데이터의 경보는 경보 빈도일 뿐이다. 참·거짓 양성의 정답은 합성 데이터에서만 알 수 있다.

## I. 연구 요약

**질문.** 각 ETF 에서 학습 기준이 해마다 누적·변경될 때 특정 해의 CUSUM 통계량은 왜 달라지는가? 그 차이를 연간 변동성 상승(V), 분산모형의 OOS 설명력 저하(M), 귀무 가정·보정의 민감도(N·C), 학습 이력의 차이(H) 중 어디까지 구별할 수 있는가?

**설계.** ETF 20종 전부를 같은 방식으로 분석했다.

- 2020 년 검정에는 2019 년만, 2021 년에는 2019–2020 을, …, 2026 년에는 2019–2025 를 학습에 썼다. 매년 연초에 ETF 별 SVR 분산모형을 다시 고르고 적합한 뒤, 그해에는 고정했다.
- 그해의 일별 예측분산, 표준화 잔차, w ∈ {20,30,60,120,252} 이동창 CUSUM 을 계산했다. 연말에는 그해 OOS 잔차만으로 사후 CUSUM 을 한 번 검정했다.
- 분산 정책은 A(관측 proxy)·B(재귀 예측)·기준선(60일 표준편차) 세 가지다. 임계값 보정은 다섯 가지, 연도 경계 처리는 두 가지, 학습 이력은 세 가지를 비교했다.
- 그 결과 140개 ETF×연도 fold 에서 21,000개 이동창 진단 행이 나왔다.
- 실데이터를 보기 전에 판정 규칙을 고정했다. 합성 DGP 로 Size·Power 를 쟀다. 순차·2·4 worker 병렬 실행이 서로 같은 결과를 내는지도 검증했다.

**무엇을 알아냈나 (완결 연도 2021–2025, ETF×연도 100칸).**

1. **정책 A 는 사실상 기각하지 않았다.** 연간 사후 점근 기각은 {{agg|name=core_reject_asym_A|value|.0f}}/100 이다. w60 순수 OOS 경보 에피소드는 {{agg|name=core_w60_obs_A|value|.0f}}건으로, iid 귀무 기대 {{agg|name=core_w60_null_A|value|.1f}}건의 {{agg|name=core_w60_ratio_A|value|.2f}} 배에 그쳤다. 합성 검증에서도 같은 현상이 나왔다. 수익률을 생성해 SVR 적합까지 거친 파이프라인에서는, 연중 분산 ×2 변화의 연간 검정력이 {{syn|dgp_name=pipeline_garch_variance_break_x2,test=annual_posthoc,calibration=asymptotic_1.3397|rate|.3f}} 였다. 잔차를 직접 생성해 같은 검정에 넣으면 {{syn|dgp_name=variance_break_x2,test=annual_posthoc,calibration=asymptotic_1.3397|rate|.3f}} 였다. 관측 proxy 를 입력으로 쓰는 적응형 표준화가 분산 수준의 변화를 잔차에서 상당 부분 **흡수**한다는 뜻이다. 따라서 A 의 낮은 T 는 "변화가 없었다" 는 증거가 아니다.
2. **연간 변동성과 연간 T 사이에는 양의 순위 연관이 없었다.** RV 비(RV_y/RV_{y−1})와 연간 T 의 Spearman ρ 는 A {{agg|name=spearman_T_rvratio_A_core|value|+.2f}}, B {{agg|name=spearman_T_rvratio_B_core|value|+.2f}}, 기준선 {{agg|name=spearman_T_rvratio_base_core|value|+.2f}} 이다. 2026 년은 RV 중앙값이 {{agg|name=rv_median_2026|value|.1f}}%, 최대가 {{agg|name=rv_max_2026|value|.1f}}% 로 높았지만, A 의 연간 기각은 0건이었다. CUSUM-of-squares 는 잔차 척도에 불변이다. 그래서 1년 내내 고르게 높은 변동성이나 1년 내내 고르게 과소한 분산 예측은 T 를 올리지 않는다. 합성 음성 대조에서 이 점을 확인했다: 높은 분산·변화 없음 Size {{syn|dgp_name=stable_high_variance_no_change,test=annual_posthoc,calibration=asymptotic_1.3397|rate|.3f}}, 일정한 예측 편향 Size {{syn|dgp_name=variance_forecast_bias_constant,test=annual_posthoc,calibration=asymptotic_1.3397|rate|.3f}}. 같은 연간 RV 를 가진 연중 분산 변화 DGP 에서는 기각률이 {{syn|dgp_name=equal_yearly_rv_within_year_break,test=annual_posthoc,calibration=asymptotic_1.3397|rate|.3f}} 였다.
3. **T 가 커진 칸은 분산 정책의 성질과 함께 나타났다.**
   - **B**: 2021 년 이후 연간 T ≥ 1.6 인 {{agg|name=b_T_ge_1p6_2021plus|value|.0f}}칸 중 {{agg|name=b_spikes_2021plus|value|.0f}}칸에서 평균 e² 가 0.8 미만이었다. 재귀 예측이 분산을 과대 추정하는 쪽으로 표류했다는 M 축 신호다.
   - **기준선**: 변동성 군집을 그대로 남긴다. w60 에피소드가 귀무 기대의 {{agg|name=core_w60_ratio_base|value|.2f}} 배였다 (N 축). 합성 GARCH 군집 귀무에서도 연간 Size 가 {{syn|dgp_name=stable_garch_clustering,test=annual_posthoc,calibration=asymptotic_1.3397|rate|.3f}} 로 부풀었다.
4. **학습 이력(H) 효과는 예측 손실에서는 일관됐지만 판정에서는 정책에 따라 달랐다.** 2019 모형을 고정하면(frozen_2019) A 의 QLIKE 가 expanding 보다 나빠진 비율이 {{agg|name=h_frozen_2019_A_frac_worse|value|.0%}} 였다. 차이의 중앙값은 2021 {{agg|name=h_frozen_A_dq_median_2021|value|+.3f}} 에서 2026 {{agg|name=h_frozen_A_dq_median_2026|value|+.3f}} 로 커졌다. 그러나 연간 판정이 바뀐 대조는 A {{agg|name=h_verdict_diff_A|value|.0f}}/{{agg|name=h_contrasts_A|value|.0f}}, B {{agg|name=h_verdict_diff_B|value|.0f}}/{{agg|name=h_contrasts_B|value|.0f}} 였다. 같은 기초지수를 추종하는 069500·102110 의 연간 T 차이는 최대 A {{agg|name=kospi_pair_max_absdiff_T_A|value|.3f}}, B {{agg|name=kospi_pair_max_absdiff_T_B|value|.3f}} 였다.

**무엇을 알 수 없나.** 한 해의 한 가격 경로에서는 V·M·N 이 동시에 움직인다. 신호가 있는 칸 대부분이 `MULTIFACTOR` 였고, 단일 원인 귀속은 하지 않았다. 실제 시장에서 구조변화가 있었는지는 이 자료로 판정할 수 없다. 2020 은 파일럿(2019 한 해 학습)이고, 2026 은 10/2 까지의 부분·비블라인드 구간이다.

<!-- pagebreak -->

<!-- INCLUDE:methods_part.md -->

<!-- pagebreak -->

## III. ETF 20종 독립 진단 프로필

각 ETF 마다 그림 1장, 연도별 다축 표, 그 ETF 의 수치로 쓴 해석 문단을 둔다.

- 해석 문단은 사전 고정 플래그와 결과표에 근거한다. 플래그는 원인이 아니라 함께 관측된 신호다.
- 순위나 우열로 정리하지 않는다.
- 표의 QLIKE 는 세 정책이 모두 유효한 같은 날짜에서 계산했다.

<!-- AUTO:etf_profiles -->

## IV. 연도·자산군 공통 패턴

![그림 2 · ETF×연도 사후 실현 연환산 변동성](figures/F02_rv_heatmap.png)

![그림 3 · 연간 사후 CUSUM T (정책별)](figures/F03_posthoc_T_heatmap.png)

<!-- AUTO:year_table -->

표의 기각 수는 ETF 20개에서 **동시에 관측된 통계적 신호의 개수**다. 20개의 독립 증거로 세면 안 된다. KOSPI200 계열 4종(069500·102110·122630·114800)은 노출이 겹치고, 섹터 ETF 도 시장 요인을 공유한다.

- **2020 (파일럿)**: 정책 A {{sy|year=2020,policy=A|n_reject_asym|.0f}}종, B {{sy|year=2020,policy=B|n_reject_asym|.0f}}종, 기준선 {{sy|year=2020,policy=base|n_reject_asym|.0f}}종이 기각했다. 연중 급변이 큰 해였고, 학습 이력은 2019 한 해뿐이었다. 2019 의 낮은 변동성으로 학습한 모형이 2020 의 분산을 크게 과소예측했다 (A 평균 e² 중앙값 {{sy|year=2020,policy=A|median_mean_e2|.2f}}). 즉 학습량 부족과 연중 급변이 섞여 있어 둘을 분리할 수 없다.
- **2021–2025**: A 는 해마다 연간 점근 기각 0건이었다. 기준선은 해마다 귀무 기대보다 많은 w60 에피소드를 보였다. B 는 그 사이에 있었다.
- **2026 (부분·비블라인드)**: RV 중앙값이 {{sy|year=2026,policy=A|median_rv|.1f}}% 로 가장 높았고, 기준선은 {{sy|year=2026,policy=base|n_reject_asym|.0f}}종이 기각했다. A 는 {{sy|year=2026,policy=A|n_reject_asym|.0f}}종이었다. 같은 날짜, 같은 수익률인데 결과가 이렇게 다르다. 따라서 이 차이는 시장보다 **표준화 방식**과 연관된 것으로 보인다.
- **자산군**:
  - 채권(148070)·단기채(153130)·달러선물(261240)은 RV 수준 자체가 낮다. 153130 은 호가 단위 때문에 수익률이 0 인 날이 많아 잔차 분포가 왜곡됐다 (DQ 제약).
  - 원유(261220)는 B 에서 재귀 표류가 반복됐다.
  - 해외지수 ETF(219480·133690·192090)는 기초자산 거래시간이 KRX 거래시간과 어긋난다는 한계를 같이 고려해야 한다.
  - 자산군별 표본이 1–5종에 불과하므로 자산군 간 유의성은 주장하지 않는다.

![그림 8 · 연간 RV 변화와 CUSUM T 의 사후 기술 연관](figures/F08_rv_vs_T.png)

![그림 10 · M 축(QLIKE 차, 평균 e²)과 N 축(Ljung–Box e² q)](figures/F10_M_N_heatmaps.png)

![그림 12 · 다축 evidence profile 종합 상태](figures/F12_profile_status.png)

종합 상태(정책 A, 140칸)는 MULTIFACTOR {{agg|name=status_A_MULTIFACTOR|value|.0f}}, DESCRIPTIVE_EVIDENCE {{agg|name=status_A_DESCRIPTIVE_EVIDENCE|value|.0f}}, UNRESOLVED {{agg|name=status_A_UNRESOLVED|value|.0f}}, NO_SIGNAL {{agg|name=status_A_NO_SIGNAL_DESCRIPTIVE|value|.0f}} 이다.

- A 의 신호 칸 {{agg|name=signal_cells_A|value|.0f}}개에서 축별 플래그 비율은 V {{agg|name=signal_share_V_A|value|.0%}}, M {{agg|name=signal_share_M_A|value|.0%}}, N {{agg|name=signal_share_N_A|value|.0%}}, H {{agg|name=signal_share_H_A|value|.0%}} 였다. 대부분 2020 파일럿 칸이다.
- 기준선의 신호 칸 {{agg|name=signal_cells_base|value|.0f}}개에서는 N 이 {{agg|name=signal_share_N_base|value|.0%}} 로 가장 흔했다.
- 보정·창·경계 중 하나라도 바꾸면 판정이 뒤집힌 칸(`SENSITIVITY_CONFIRMED`)은 A {{agg|name=sensitivity_A|value|.0f}}/140, B {{agg|name=sensitivity_B|value|.0f}}/140, 기준선 {{agg|name=sensitivity_base|value|.0f}}/140 이다. A 에서 많은 것은 w=20 짧은 창에서만 경보가 생기는 경우가 잦기 때문이다.

<!-- pagebreak -->

## V. 판별 사례 연구 (탐색적 선택)

사례는 결과표를 본 뒤 **대비가 분명한 칸**으로 골랐다 (`EXPLORATORY`). 선택 기준은 사례마다 적는다. 각 사례가 보여주는 것은 "어느 축이 함께 움직였고 어느 축이 움직이지 않았는가" 이다. 원인은 아니다.

### V.1 V↑ 인데 A 신호 없음 — 219480 2022 (기준: 2021–25 중 RV 비가 가장 큰 축에 속하면서 A 비기각)

RV 가 {{vol|ticker=219480,year=2021|rv_ann_pct|.1f}}% 에서 {{vol|ticker=219480,year=2022|rv_ann_pct|.1f}}% 로 {{vol|ticker=219480,year=2022|rv_ratio|.2f}} 배가 됐다. 그러나 A 의 연간 T 는 {{ph|ticker=219480,year=2022,policy=A,calibration_method=asymptotic|annual_T|.2f}}, w60 에피소드는 {{cu|ticker=219480,year=2022,policy=A,window=60,boundary_mode=YEAR_CONTAINED,calibration_method=iid_insample|rolling_episodes|.0f}} 건이었다. 평균 e² 는 {{fc|ticker=219480,year=2022,policy=A|mean_sq_standardized_residual|.2f}} 이고 비양수 예측분산이 {{fc|ticker=219480,year=2022,policy=A|nonpos_var|.0f}}일 있었다. 분산 수준은 과소예측됐다. 하지만 그 과소예측이 연중 고르게 나타났다면, 척도에 불변인 CUSUM-of-squares 의 T 는 올라가지 않는다 (합성 `variance_forecast_bias_constant` 와 같은 모양). 기준선 T 는 {{ph|ticker=219480,year=2022,policy=base,calibration_method=asymptotic|annual_T|.2f}} 였다. **구별된 것**: "RV 상승" 과 "연중 분산 구조의 변화" 는 같은 것이 아니다. **구별되지 않은 것**: 이 해에 기초자산의 연중 구조가 실제로 바뀌었는지.

### V.2 V·M·N 동시 — 069500 2020 (기준: 파일럿 연도 대표, 세 정책 모두 기각)

RV 는 {{vol|ticker=069500,year=2020|rv_ann_pct|.1f}}% 로 2019 대비 {{vol|ticker=069500,year=2020|rv_ratio|.2f}} 배였다. A 의 평균 e² 는 {{fc|ticker=069500,year=2020,policy=A|mean_sq_standardized_residual|.2f}} 였고, 잔차 초과첨도는 {{res|ticker=069500,year=2020,policy=A|excess_kurtosis|.1f}}, Ljung–Box(e²) q 는 {{res|ticker=069500,year=2020,policy=A|ljungbox_e2_q|.3f}} 였다. 연간 T 는 A {{ph|ticker=069500,year=2020,policy=A,calibration_method=asymptotic|annual_T|.2f}}, B {{ph|ticker=069500,year=2020,policy=B,calibration_method=asymptotic|annual_T|.2f}}, 기준선 {{ph|ticker=069500,year=2020,policy=base,calibration_method=asymptotic|annual_T|.2f}} 로 모두 기각이다. argmax 위치는 {{ph|ticker=069500,year=2020,policy=A,calibration_method=asymptotic|khat_argmax_date|s}} 이고, e² 의 하반기/상반기 비는 {{res|ticker=069500,year=2020,policy=A|e2_ratio_h2_over_h1_exploratory|.2f}} (탐색적)이다. 연중 급변, 1년 학습 모형의 과소예측, 잔차 의존이 한꺼번에 나타났다. 상태는 `MULTIFACTOR` 로 남긴다.

### V.3 B 재귀 표류 — 305540 2022 (기준: B 의 2021+ 최대 T)

같은 연초 모형인데도 B 의 연간 T 는 {{ph|ticker=305540,year=2022,policy=B,calibration_method=asymptotic|annual_T|.2f}}, A 는 {{ph|ticker=305540,year=2022,policy=A,calibration_method=asymptotic|annual_T|.2f}} 였다. B 의 평균 e² 는 {{fc|ticker=305540,year=2022,policy=B|mean_sq_standardized_residual|.2f}} 로 분산을 과대 예측했다. e² 의 하반기/상반기 비가 {{res|ticker=305540,year=2022,policy=B|e2_ratio_h2_over_h1_exploratory|.3f}} 로 극단적이어서, 연중 e² 수준에 강한 추세가 있었다. 이 칸의 큰 T 는 시장 신호와 재귀 예측 경로의 표류(M) 를 구별할 수 없고, 후자를 강하게 시사한다. 학습 이력만 frozen_2019 로 바꾸면 B 의 T 는 {{ab|ticker=305540,year=2022,policy=B,history_strategy=frozen_2019|annual_T|.2f}} 로 내려갔다. B 판정이 학습 이력에 민감하다는 뜻이다.

### V.4 학습 이력만 바꿨을 때의 판정 반전 — KOSPI200 계열 2021 (기준: H_VERDICT_DIFFERS 가 A 에서 집중된 해)

2021 년 069500 에서 2019 모형을 고정하면 A 의 연간 T 가 {{ab|ticker=069500,year=2021,policy=A,history_strategy=frozen_2019|annual_T|.2f}} (expanding 대비 {{ab|ticker=069500,year=2021,policy=A,history_strategy=frozen_2019|d_annual_T_vs_expanding|+.2f}}) 로 1.3397 을 넘었다. 102110 ({{ab|ticker=102110,year=2021,policy=A,history_strategy=frozen_2019|annual_T|.2f}}), 114800 ({{ab|ticker=114800,year=2021,policy=A,history_strategy=frozen_2019|annual_T|.2f}}), 122630 ({{ab|ticker=122630,year=2021,policy=A,history_strategy=frozen_2019|annual_T|.2f}}) 도 같았다. 같은 날짜와 같은 수익률에서 학습 표본(2019 vs 2019–20)만 다르다. 따라서 이 차이는 학습 이력 선택과 **연관**된다. 다만 네 ETF 는 같은 지수에 대한 노출이라 독립 증거 4건이 아니다. 2019 단독 학습은 2020 을 겪지 않았다는 점에서 표본 크기와 국면 경험이 섞여 있다.

### V.5 표준화 방식만 다른 대비 — 069500 2026 (기준: 2026 기준선 기각 중 KOSPI 대표)

RV {{vol|ticker=069500,year=2026|rv_ann_pct|.1f}}% (부분·비블라인드). 기준선 T {{ph|ticker=069500,year=2026,policy=base,calibration_method=asymptotic|annual_T|.2f}} 는 기각, A T {{ph|ticker=069500,year=2026,policy=A,calibration_method=asymptotic|annual_T|.2f}} 는 비기각이다. 기준선 잔차의 Ljung–Box(e²) q 는 {{res|ticker=069500,year=2026,policy=base|ljungbox_e2_q|.3f}}, A 는 {{res|ticker=069500,year=2026,policy=A|ljungbox_e2_q|.3f}} 다. 같은 가격 경로에서 판정을 가른 것은 잔차에 남은 의존(N) 과 표준화의 적응성이다. 어느 쪽이 "참" 인지는 이 자료로 정할 수 없다.

### V.6 자료 품질 제약 — 153130 2024 (기준: A 잔차 초과첨도 최대)

단기채 ETF 는 RV 가 {{vol|ticker=153130,year=2024|rv_ann_pct|.2f}}% 수준이다. 로컬 일별 캐시를 감사한 결과, 수익률이 정확히 0 인 날이 해에 따라 7–33% 였다. A 잔차 초과첨도는 {{res|ticker=153130,year=2024,policy=A|excess_kurtosis|.1f}}, 평균 e² 는 {{fc|ticker=153130,year=2024,policy=A|mean_sq_standardized_residual|.2f}} 다. 이산적인 가격 변화가 분산 예측과 τ̂ 추정을 지배하므로, 이 ETF 의 CUSUM 결과는 구조변화 진단보다 **자료 품질 진단**으로 읽어야 한다.

<!-- pagebreak -->

## VI. 검정 타당성 — 합성 DGP · 보정 · 병렬 재현

![그림 9 · 합성 DGP 의 경험적 Size/Power (Wilson 95% CI)](figures/F09_synthetic_size_power.png)

<!-- AUTO:synthetic_table -->

**검출기 수준** (잔차를 직접 생성, 1,000회):

- iid 정규 귀무에서 연간 점근 검정 Size 는 {{syn|dgp_name=stable_low_variance_no_change,test=annual_posthoc,calibration=asymptotic_1.3397|rate|.3f}}, iid 부트스트랩은 {{syn|dgp_name=stable_low_variance_no_change,test=annual_posthoc,calibration=iid_history_bootstrap|rate|.3f}} 로 명목 수준 근처다.
- GARCH 군집 귀무에서는 Size 가 {{syn|dgp_name=stable_garch_clustering,test=annual_posthoc,calibration=iid_history_bootstrap|rate|.3f}} 로 부풀었다. 잔차에 군집이 남으면 iid 보정은 무효가 된다.
- 단일 이상치 하나는 τ̂ 를 키워 기각률을 {{syn|dgp_name=one_outlier_without_persistent_break,test=annual_posthoc,calibration=asymptotic_1.3397|rate|.3f}} 로 떨어뜨렸다. 이상치가 검정을 가린다.
- 연도 경계에서 바로 시작된 분산 변화는 연간 사후 검정이 잡지 못한다 ({{syn|dgp_name=break_at_year_boundary,test=annual_posthoc,calibration=asymptotic_1.3397|rate|.3f}}). 그해 안에서는 분산이 일정하기 때문이다. 반면 CARRY warm 구간의 경보 확률은 {{syn|dgp_name=break_at_year_boundary,test=rolling_w60_CARRY_warm_days_any_episode,calibration=iid_history_bootstrap_pointwise95|rate|.3f}} 였다.
- 점별 95% 임계값을 쓰면, 변화가 없어도 w60 PURE 창에서 연중 1회 이상 경보가 날 확률이 {{syn|dgp_name=stable_low_variance_no_change,test=rolling_w60_PURE_any_episode_in_year,calibration=iid_history_bootstrap_pointwise95|rate|.3f}} 다. 실데이터 A 의 귀무 기대 확률 평균도 {{agg|name=null_prob_any_w60_A_core_mean|value|.2f}} 였다. 이동창 경보 한 번은 "5% 사건" 이 아니다.

**파이프라인 수준** (수익률 생성 → 연초 SVR 적합 → A 잔차, 200회):

- GARCH 귀무 Size 는 {{syn|dgp_name=pipeline_garch_H0,test=annual_posthoc,calibration=asymptotic_1.3397|rate|.3f}}, iid 정규 귀무는 {{syn|dgp_name=pipeline_iid_normal_H0,test=annual_posthoc,calibration=asymptotic_1.3397|rate|.3f}} 다. 검정이 보수적이다.
- 연중 분산 ×2 변화의 Power 는 {{syn|dgp_name=pipeline_garch_variance_break_x2,test=annual_posthoc,calibration=asymptotic_1.3397|rate|.3f}} 로 낮았다.
- 즉 실데이터 A 에서 기각이 없었다는 결과는 "변화가 없었다" 와 "검정력이 없었다" 를 구별하지 못한다. 반복 수가 적고 GARCH 파라미터를 한 조만 썼다는 한계가 있다.

![그림 6 · 같은 잔차 경로, 다른 보정 방식](figures/F06_calibration_methods.png)

**보정 방식 비교.**

- block 부트스트랩(다른 귀무)의 A 연간 임계값은 iid 보다 낮게 나왔다. 사전 연도 in-sample 잔차의 e² 가 짧은 시차에서 음의 자기상관을 보였고, 이는 적응형 표준화의 과보정과 일치한다. 블록 풀이 약 500개뿐이라 이 임계값 자체의 추정 잡음도 크다 (iid 정규 풀로 실험했을 때 풀에 따라 1.16–1.38 로 흔들렸다).
- prequential(OOS 풀) 보정은 2020 에서 추정할 수 없었다 (`NOT_ESTIMABLE`).
- w=252 는 모든 해에서 순수 OOS 창이 없다.

![그림 4 · 연도 경계 연결 예시](figures/F04_boundary_069500.png)

![그림 5 · w60 에피소드 관측 vs 귀무 기대](figures/F05_episodes_vs_null.png)

![그림 7 · 정책 간 불일치와 동일 노출 ETF](figures/F07_policy_pairs.png)

![그림 11 · 학습 이력 대조](figures/F11_history_ablation.png)

**병렬 재현.** 같은 설정을 순차, 2-worker, 4-worker, 4-worker 재실행으로 돌렸다. 9개 결과표의 sha256 과 수치를 비교한 결과는 아래와 같다. 하이퍼파라미터 선택에서 ε 가 격자 경계(0.1)에 걸린 fold 가 {{agg|name=eps_at_grid_edge_share|value|.1%}} 였다. 격자 경계 민감도는 아직 검사하지 않았다.

<!-- AUTO:parallel_table -->

<!-- pagebreak -->

## VII. 결론과 남은 질문

**최종 판정 질문에 대한 답.** "학습 기준이 누적·변경될 때 왜 특정 해의 CUSUM 통계량이 달라졌는가?"

1. **연간 변동성 상승(V) 은 T 의 변화를 설명하지 못했다.** 완결 연도에서 RV 비와 T 의 순위 연관은 세 정책 모두 0 근처이거나 음수였다. 2026 의 극단적 RV 에서도 A 의 T 는 낮았다. 척도 불변성 때문에 연중 고른 변동성 상승은 T 를 올리지 않는다. 이것은 합성 음성 대조로 **검정된** 성질이다 (`SYNTHETIC_CAUSAL_KNOWN_ONLY`). 실데이터에서는 기술적 일치로만 말한다.
2. **분산모형의 OOS 설명력(M) 은 두 갈래로 작동했다.**
   - 평균 수준의 과소예측(A 의 평균 e² 중앙값 {{agg|name=core_median_mean_e2_A|value|.2f}}) 은 T 를 올리지 않았다.
   - 반면 연중 예측 경로의 **표류**(B 재귀) 는 큰 T 와 거의 항상 함께 나타났다.
   - 둘째는 B 정책 고유의 성질로 구별된다 (같은 날짜, 같은 연초 모형, 다른 입력 정책). 다만 표류가 시장 변화로 촉발됐는지는 구별하지 못했다.
3. **귀무 가정·보정(N·C) 은 판정을 크게 좌우했다.** 기준선 잔차의 군집은 iid 귀무 대비 과다 경보와 함께 관측됐다 (합성 GARCH 귀무 Size {{syn|dgp_name=stable_garch_clustering,test=annual_posthoc,calibration=asymptotic_1.3397|rate|.3f}}). A 의 적응형 표준화는 반대로 과소 경보와 낮은 검정력을 보였다. 그래서 같은 가격 경로라도 "기각 여부" 는 거의 표준화·보정 설계로 결정됐다. 이것은 **설계 민감도**로 확인됐다 (`SENSITIVITY_CONFIRMED`). 시장에 관한 결론은 아니다.
4. **학습 이력(H) 은 예측 손실과는 일관되게 연관됐지만, A 의 판정과는 약하게만 연관됐다.** frozen_2019 의 손실 악화는 해가 갈수록 커졌다. 판정 반전은 A 에서 드물었고 2021 KOSPI 계열에 몰려 있었다. B 에서는 흔했다. 학습량과 경험한 국면이 섞여 있으므로 인과 효과는 추정하지 않는다.
5. **구별할 수 없는 것**:
   - 한 칸 안에서 V·M·N 이 함께 움직일 때 기여도를 나누는 일 (반사실 가격 경로가 없다)
   - 실제 시장 구조변화의 유무 (정답 없음)
   - A 의 무기각이 "변화 없음" 인지 "검정력 부족" 인지 (파이프라인 Power 가 낮다)
   - 2026 의 비블라인드성

**후속 연구와의 연결.**

- 이 결과는 상태 S·관측 O·belief P 를 정의하는 후속 연구에 **관측 O 의 성질**을 알려 준다: 적응형 표준화 잔차의 CUSUM 은 분산 수준 변화에 둔감하다.
- 다만 Active Inference·DP 의 성능에 관해서는 아무것도 주장하지 않는다.
- 다음 실험 후보 (사전 등록 필요):
  - 귀무를 GARCH 로 둔 모형 기반 보정
  - SVR 격자 경계(ε<0.1) 민감도
  - 이상치에 강건한 τ̂
  - 표준화 없이 r² 의 CUSUM 과 병행 비교

## 부록 · 산출물과 재현

| 산출물 | 위치 (R2H 저장소 기준) | 공개 |
|---|---|---|
| 프로토콜·변경 이력 | `research/t12_annual_expanding_v2/PROTOCOL_LOCK.md`, `PROTOCOL_CHANGELOG.md` | 커밋 |
| 결과표 (ETF×연도 집계, 9종 + 요약·집계) | `research/t12_annual_expanding_v2/results/` | 커밋 |
| 그림 원본 + figure_manifest (출처 표·필터·sha256) | `research/t12_annual_expanding_v2/figures/` | 커밋 |
| 소스-주장 매트릭스 | `SOURCE_EVIDENCE_MATRIX.csv` (이 보고서의 모든 수치 토큰) | 커밋 |
| 재현 감사·이슈 로그 | `REPRODUCIBILITY_AUDIT.md`, `ISSUE_LOG.md` | 커밋 |
| 일별 수익률·잔차·예측분산 | `outputs/t12/work/<run>/<ticker>/daily.csv.gz` | **로컬 전용** (시세 역산 가능) |
| DOCX / PDF | `outputs/t12/report/` | **로컬 전용** (`.gitignore` 의 `*.docx`, `*.pdf`) |

재현 명령:

- `uv sync --locked --extra dev --extra research --extra notebook`
- `uv run python scripts/run_t12_annual_expanding.py --run-id seq_golden --workers 1`
- `uv run python scripts/run_t12_synthetic_validation.py --workers 4`
- `uv run python scripts/t12_figures.py --results … --work … --figs …`

**완료 판정 (혼합 금지):**

- `CODE_TESTED` = 통과
- `COMPUTATION_REPRODUCED` = VI 절 병렬 표 참조
- `STATISTICAL_VALIDITY_TESTED` = 합성 DGP 범위 안에서만
- `ECONOMIC_USEFULNESS_UNTESTED`

**참고문헌.** Lee, S., Kim, C. K., & Lee, S. (2020). Hybrid CUSUM change point test for time series with time-varying volatilities based on support vector regression. *Entropy*, 22(5), 578. https://doi.org/10.3390/e22050578 — 원문 충실도는 Track B 감사에서 `METHOD_FIDELITY_UNRESOLVED`.

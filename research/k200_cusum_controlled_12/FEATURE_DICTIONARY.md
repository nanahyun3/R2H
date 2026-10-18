# 피처 사전 (daily_cusum_features)

| 열 | dtype | 뜻 |
|---|---|---|
| `ticker` | str | 069500 |
| `date` | datetime64[us] | 평가일 |
| `experiment_id` | str | 등록부 ID |
| `policy_id` | str | SVR 파이프라인 |
| `detector_type` | str | rolling_cos · raw_rolling_cos · page_up · page_down · page_two · *_sn |
| `window_w` | str | 이동창 길이 (Page 는 NA) |
| `reset_rule` | str | 초기화 일정 이름 또는 cp:규칙:q:불응기 |
| `calendar_year` | int32 | 달력연도 |
| `feature_available_at` | datetime64[us] | 관측 가능 시점 (t 종가) |
| `information_cutoff` | str | close_t |
| `model_fit_id` | int64 | SVR 적합 번호 (재적합 경계 식별) |
| `return_log_pct` | float64 | 100·Δlog(Close) |
| `residual_std` | float64 | 표준화 잔차 e = r/√v̂ |
| `predicted_variance` | float64 | SVR 정책 A 예측분산 v̂ (t−1 종가 정보) |
| `cusum_raw_T` | float64 | 원시 통계량 (이동 CoS T 또는 Page 자유 상태 S, 경보 후 재설정 없음) |
| `cusum_upper_state` | float64 | Page 상방 자유 상태 |
| `cusum_lower_state` | float64 | Page 하방 자유 상태 |
| `cusum_critical_value_a05` | float64 | N1 귀무 연 블록 α=0.05 임계 (양방향 Page 는 두 h 중 큰 값) |
| `cusum_T_over_critical_a05` | float64 | T / 임계 |
| `cusum_tail_probability` | float64 | 귀무 일별 분포 꼬리확률 (서술용 raw p) |
| `cusum_adjusted_pvalue` | float64 | 귀무 연 블록 최대 대비 p (블록 다중성 보정) |
| `confirmatory_p` | float64 | 귀무 적합 파이프라인에서만 adjusted p, 아니면 NA |
| `cusum_alarm_a05` | bool | α=0.05 경보 (Page 는 경보 후 재설정 경로) |
| `cusum_alarm_a20` | bool | α=0.20 경보 |
| `cusum_statistic_valid` | bool | 통계량 계산 가능 |
| `cusum_null_valid` | bool | 관측 잔차가 N1 귀무 적합 검사 통과 (raw CoS 는 해당 없음=True) |
| `cusum_calibration_id` | str | garch_t_N1 또는 E11 대체 보정 이름 |
| `significance_status` | str | SIGNIFICANT / NOT_SIGNIFICANT / NULL_MODEL_INVALID / WINDOW_NOT_AVAILABLE / INSUFFICIENT_HISTORY |
| `pvalue_status` | str | OK / P_VALUE_NOT_CALCULATED / WINDOW_NOT_AVAILABLE / INSUFFICIENT_HISTORY |
| `days_since_reset` | int64 | 마지막 CUSUM 초기화 후 경과일 |
| `reset_count` | int64 | 누적 외부 초기화 횟수 |
| `page_state_code` | int64 | 0 일반 · 1 자연 0 복귀 · 2 외부 초기화 · −1 해당 없음 |
| `source_hash` | str | 원자료 sha256 앞 16자 |

AE 후보 wide 표의 열과 결정은 `results/feature_catalog.csv`. 정의 규칙은 `RESEARCH_CONTRACT.md` §5·§9.

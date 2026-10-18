# 피처 사전

저장 위치 `outputs/t21/feature_store_n1/` (Git 제외). 데이터셋 9종: daily_cusum_features(원장) · daily_market_features · daily_svr_predictions · daily_change_point_features · daily_change_point_triggers · daily_reset_events · daily_feature_eligibility · experiment_metrics · synthetic_validation · autoencoder_feature_catalog (+ ae_candidate_wide).

## daily_cusum_features

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
| `return_abs` | float64 | |r| |
| `return_sq` | float64 | r^2 |
| `realized_variance` | float64 | r_t^2 (일 실현분산 대리) |
| `realized_volatility` | float64 | 직전 20일 표준편차 (t 포함) |
| `observed_variance_proxy` | float64 | 직전 5일 r^2 평균 (정책 A 입력 프록시와 같은 m=5) |
| `predicted_volatility` | float64 | sqrt(v̂) |
| `residual` | float64 | r_t (정책 A 는 평균을 모형화하지 않음) |
| `standardized_residual` | float64 | e |
| `standardized_residual_sq` | float64 | e^2 |
| `cusum_critical_value` | float64 | = cusum_critical_value_a05 |
| `cusum_T_over_critical` | float64 | = a05 비 |
| `cusum_normalized_T` | float64 | T / 임계 (α=0.05) |
| `cusum_test_pvalue` | float64 | = confirmatory_p |
| `cusum_alarm_flag` | bool | = cusum_alarm_a05 |
| `cusum_signed_direction` | float64 | 이동 CoS: 창 후반−전반 평균 e^2 부호 · Page 양방향: 우세 쪽 · 단측: 고정 |
| `segment_id` | int64 | 초기화 구간 번호 |
| `reset_applied_at` | datetime64[us] | 구간 시작일 (초기화 없으면 NaT, 사유 SERIES_START) |
| `reset_reason` | str | 초기화 일정 이름 또는 SERIES_START |
| `change_trigger_type` | str | cp_<규칙> 또는 NOT_APPLICABLE:<사유> |
| `change_detected_at` | datetime64[ns] | 변화점 확정일 t (효과일 t+1 의 전날) |
| `change_score` | float64 | 확정일 강도 점수 |
| `change_score_percentile` | float64 | 확정일 강도의 과거 백분위 |
| `model_fit_at` | datetime64[ns] | SVR 적합일 (구간 첫날, 이전 날까지 정보) |
| `model_training_start` | datetime64[ns] | 학습 시작일 |
| `model_training_end` | datetime64[ns] | 학습 끝일 |
| `svr_refit_at` | datetime64[ns] | = model_fit_at |
| `days_since_refit` | int64 | 적합 후 경과 평가일 (−1 = 해당 없음) |
| `refit_reason` | str | INITIAL_FIT / SCHEDULED / SCHEDULED_ANNUAL / CHANGE_POINT_TRIGGER(_ADAPTIVE) / NOT_APPLICABLE |
| `svr_C` | float64 | 선택 C |
| `svr_gamma2` | float64 | 선택 γ² |
| `svr_eps` | float64 | 선택 ε |
| `history_truncated` | object | 학습창이 가용 이력보다 길어 전체 사용 |
| `computation_status` | str | OK / WINDOW_NOT_AVAILABLE / INSUFFICIENT_HISTORY |
| `model_validity_status` | str | NULL_MODEL_INVALID 또는 NULL_VALID_OR_NOT_APPLICABLE |
| `feature_eligibility` | str | ELIGIBLE_REALTIME_CONTINUOUS / NOT_ELIGIBLE_MISSING |
| `missing_reason` | str | 결측 사유 (유효하면 빈 값) |
| `numerical_precision` | str | float64_cpu_numpy |

해당 없는 필드는 NA/NaT + `missing_reason`·`change_trigger_type`·`refit_reason` 의 NOT_APPLICABLE 사유. AE 후보 결정은 `results/feature_catalog.csv`, §3.1 필드 포함 검사는 `results/feature_field_coverage.csv` (57/57).

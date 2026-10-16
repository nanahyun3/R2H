# W2 다중 기간 변동성 국면 → CNN 후보 구간 인계 계약

파일 `research/multihorizon_w2/results/07/cnn_candidate_intervals_w2.csv` 의 생성 노트북은 `notebooks/07_가격반응_ETF상대움직임_CNN인계.ipynb` §9 이고, 프로토콜은 `W2-lock-1` 이다.

**이 파일은 정답 라벨이 아니다.**
- 05 의 규칙으로 만든 **탐색 후보**다. 규칙은 다음과 같다.
  - 분산 수준·직전 대비 변화의 확장형 mid-rank 과거 분위 상·하위 10%
  - 7개 기간(q=3…120) 가운데 3개 이상이 같은 날 반응
  - 그런 날의 연속 구간
- 가격 급등, 실제 구조변화, 매매 신호의 정답으로 쓰지 않는다. 라벨 열은 만들지 않았다.

## 1. 범위

- 1,711 행 = 20종 ETF × 4채널의 공통 구간 전부. 순위로 걸러내지 않았다.
  - 2021–2025: 1,168
  - 2020 파일럿: 268
  - 2026 부분·비블라인드: 275
- W1 의 `research/window_study_w1/results/04_real/cnn_candidate_intervals.csv` (CUSUM 첫 경보 142행)와는 다른 규칙으로 만들었다. 두 표를 합쳐 중복 학습하지 않는다.

## 2. 필드 사전 (사용자 §10 필수 22개 → 실제 열)

| 필수 정보 | 실제 열 | 뜻 | 시점·금지 해석 |
|---|---|---|---|
| candidate_id | `candidate_id` | `W2-{ticker}-{채널 앞 3자}-{시작일}` | 유일 |
| ticker | `ticker` | ETF 코드 | |
| exposure_group | `exposure_group` | W1 노출 그룹. KOSPI200 4종은 한 그룹 | **학습·평가 분할 단위**. 같은 그룹을 양쪽에 두지 않는다 |
| episode_state | `episode_state` | `HIGH_LEVEL` / `LOW_LEVEL` / `EXPANSION` / `CONTRACTION` | 방향(상승·하락)과 무관한 분산 상태 |
| episode_start | `episode_start` | 3개 이상 q 가 처음 동시에 켜진 날 | 사후 구간 시작이다. 구조변화 참시점이 아니다 |
| episode_end | `episode_end` | 3개 이상 동시 반응의 마지막 날 | 사후 요약 |
| available_at | `available_at` | `episode_start` 종가 이후 | 이보다 이른 시점의 입력으로 쓰지 않는다 |
| episode_confirmed_at | `episode_confirmed_at` | `episode_end` 다음 거래일 (`RIGHT_CENSORED` = 자료 끝까지 지속) | 구간 길이는 이날 이후에만 안다 |
| estimated_change_at | `estimated_change_at` | 항상 `NOT_ESTIMATED` | 변화점 추정기를 쓰지 않았다 |
| active_q | `active_q` | 구간 중 한 번이라도 켜진 q 목록 | |
| max_overlap_count | `max_overlap_count` | 최대 동시 반응 q 수 (3–7) | 확률·신뢰도가 아니다 |
| duration_trading_days | `duration_trading_days` | 지속 거래일 | |
| realized_variance_features | `rv_max_U_V`, `rv_max_U_D`, `rv_max_D`, `rv_min_D`, `rv_n_horizon_groups`, `rv_short_mid_long`, `rv_daily_shock_in_interval` | 구간 안 최대 분위·로그분산비, 단·중·장기 참여(예 `110`), q=1 일간 충격 여부 | 구간 전체의 사후 요약. 실시간 입력이면 `available_at` 이후 값만 써야 한다 |
| relative_variance_features | `rel_max_n_group_during`, `rel_max_n_etf_during`, `rel_overlaps_cross_group_interval`, `rel_U_V20_minus_cross_median_at_start` | 같은 기간 후보 노출 그룹·ETF 수, 06 교차 공통 구간과의 겹침, 시작일 U_V⁽²⁰⁾ − 20종 중앙값 | 앞 셋은 사후 요약 |
| price_response_features | `px_pre_C_h20`, `px_pre_rel_h20`, `px_during_C`, `px_during_rel_simple`, `px_during_rel_exposure_adj`, `px_post_R_h20_POSTHOC`, `px_post_available_at_h20` | 사전 20일·구간 중·사후 20일 누적 로그수익률(%)과 같은 날 상대값 | **`px_post_*` 는 사후 결과다.** 입력 특징으로 쓰면 미래 누수다. 2026 끝 구간 47 행은 `NOT_AVAILABLE_DATA_END` |
| cusum_w | `cusum_w` | 구간 안 CUSUM 경보 창 (`NONE` = 계산 가능했으나 경보 없음, `NOT_AVAILABLE` = 하루도 계산 불가) | `NOT_AVAILABLE` 을 무경보로 바꾸지 않는다. `cusum_coverage` 와 함께 읽는다 |
| cusum_statistic | `cusum_statistic`, `cusum_statistic_w` | 구간 안 첫 경보일의 T_w 와 그 w (가장 짧은 경보 창) | W1 적격 창 0/4. 탐색 보조 신호일 뿐이다 |
| cusum_alarm_at | `cusum_alarm_at` | 구간 안 첫 CUSUM 경보일 | 같은 수익률에서 파생됐으므로 독립 확인이 아니다 |
| cusum_threshold_type | `cusum_threshold_type`, `cusum_policy_sample` | `pipeline_garch_annual_max`, 정책 A · 공통일 | |
| is_exploratory_candidate | `is_exploratory_candidate` | 항상 True | |
| source_commit | `source_commit` | 기준 `7205e91` · 계약 `1fbdb1d` · 릴리스 커밋은 `W2_RELEASE_MANIFEST.json` | |
| protocol_version | `protocol_version` | `W2-lock-1` | |

추가 열 `cusum_coverage` 와 `year_status` (주 해석 / 파일럿 / 2026 부분)가 있다.

## 3. 사용 규칙

1. **분할.**
   - `exposure_group` 단위로 학습·검증·평가를 나눈다. KOSPI200 4종의 구간은 후보일 Jaccard 0.75–0.99 로 사실상 같은 사건이다.
   - 날짜도 블록으로 나눈다. 같은 날짜의 다른 그룹 후보도 공통 충격(06: 2024-08, 2025-04)을 공유하기 때문이다.
2. **입력 창.** CNN 입력 길이 `L_CNN` 은 q·h·w 와 별개다. 아직 정하지 않았다. 입력 창의 끝은 `available_at` 이후가 될 수 없다.
3. **정답.** CNN 을 '급등 시작 탐지기' 로 평가하려면, 아래 다섯 가지를 이 파일과 **다른 절차**로 먼저 사전 등록해야 한다. 이 후보를 정답으로 쓰면 순환 평가다.
   - (1) 독립 가격 급등 시작 라벨과 허용 시차
   - (2) 음성 사례
   - (3) 온라인 정보 차단
   - (4) 자산·기간 블라인드 분리
   - (5) 오경보 비용·누락·지연 지표
4. **레버리지·인버스.** 같은 노출이라도 변동성 국면에서 가격 반응이 체계적으로 다르다. 07 §7 에서 레버리지의 '2×기초' 대비 20일 차이 중앙값은 −0.54 → −1.21%p 였다. 기초지수 사건 라벨을 레버리지 상품에 그대로 복사하지 않는다.
5. **배포.** 행 단위 구간 요약만 담았다. 일별 가격·수익률·잔차는 Git 제외 폴더(`outputs/t14/`)에 있다.

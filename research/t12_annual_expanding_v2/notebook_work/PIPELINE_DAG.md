# PIPELINE_DAG — T12 Annual Expanding 실행 그래프 (B-1)

기준 코드: 브랜치 `research/annual-b-notebook` @ base `8414678`. 아래의 `파일:줄` 은 이 커밋 기준이다.
경로는 저장소 루트(`$W`) 기준 상대경로다.

## 0. 한눈에 보기

```
data/raw/<ticker>.csv (20종, 원본 R2H/data/raw 심링크, 읽기 전용)
 │  svrgarch_etf/data.py:70 load_close_panel(raw_dir)  ── 종가 sha256 ↔ research/svr_garch_cusum_etf/reference_close_sha256.csv
 │                                                        data_version (data.py:63) == cfg.expected_data_version (pipeline.py:167)
 ▼
close panel (공통 거래일 1,903행) ─ svrgarch_etf/data.py:103 percent_log_returns → r_t = 100·Δlog Close (DQ 셀 NaN)
 │
 │  pipeline.py:153 run()  [THREAD_ENV=1 :164–165 · meta{data_version, git_sha(:65), code_sha(:55)} :179]
 ▼
ticker 별 job (pipeline.py:180) ── workers<=1: 순차 루프 :182–185 / workers>1: ProcessPoolExecutor(spawn) :186–196
 │
 ▼  worker.py:122 run_ticker(ticker, r, cfg, work, meta) — 연도 y = 2020..2026 순차 (:165)
 │   ├─ V  worker.py:175–203  annual_rv / prior_quantile (diagnostics.py:17, :24)
 │   ├─ fold  worker.py:206–229  folds.py:73 build_fold (3 전략, folds.py:13) · year_status folds.py:32
 │   ├─ 적합  worker.py:240  fit.py:150 fit_annual → paper2020/svr_garch.py:311 select_and_refit (27 grid, val MAE)
 │   ├─ 정책별 분산  worker.py:265–269
 │   │     A = fit.py:198 forecast_year(OBSERVED_PROXY) · B = forecast_year(RECURSIVE_PREDICTION)
 │   │     base = fit.py:254 baseline_variance (σ_{t−1}(60)², min 40)
 │   │     → 잔차 e = fit.py:245 standardize (비양수 v̂ → NaN)
 │   │     사전 연도 재표준화 풀 fit.py:225 insample_variance (worker.py:271–273)
 │   ├─ M  worker.py:276–300  diagnostics.py:34 forecast_metrics (교집합 + 자기 coverage)
 │   ├─ N  worker.py:303–314  diagnostics.py:107 residual_stats (LB, ARCH-LM …)
 │   ├─ C  worker.py:317–493
 │   │     연간 사후 CUSUM  calibration.py:319 posthoc → paper2020/cusum.py:116 cusum_squares_test
 │   │     임계값  asymptotic = cfg 1.3397 (worker.py:331–333) · normal_mc (worker.py:76–90, lru_cache)
 │   │            iid/block = worker.py:93 _draws → calibration.py:280/:284 · 분위 calibration.py:297
 │   │     이동창  calibration.py:332 rolling_with_context (CARRY) · svrgarch_etf/rolling.py:39 rolling_cusum
 │   │            PURE/YEAR_CONTAINED 동치 assert worker.py:366–370
 │   │            경보 요약 calibration.py:340 summarize_alarms · 귀무 기대 calibration.py:310 null_episode_rate
 │   ├─ H  worker.py:496–622  (trailing_2y, frozen_2019 재적합/재사용 → 같은 날짜 대조)
 │   └─ 쓰기  worker.py:624–639  <work>/<ticker>/{8 표}.csv + daily.csv.gz + DONE.json (tmp→rename 원자적)
 ▼
pipeline.py:200 merge()  ── 표별 concat + pipeline.py:81 _sort (SORT_KEYS :40, 문자열 mergesort)
 │   ├─ BH q 값  pipeline.py:108–115 (diagnostics.py:145 bh_qvalues; 범위 = (검정 × 정책 × history) × 140)
 │   └─ diagnostic_profile  pipeline.py:116 → profile.py:179 build_profile (L7 사전 고정 규칙)
 ▼
<work>/merged/{8 표, diagnostic_profile}.csv  (pipeline.py:203–207, worker.py:48 frame_bytes: UTF-8·LF·%.10g)
<work>/merged/integrity.csv                    (pipeline.py:120 integrity → :208–209; PK 유일성·기대 행 수)
<work>/merged/run_manifest.json                (pipeline.py:213–243; outputs_sha256, aggregate_hash :210)
 │
 │  (선택) CLI --publish  scripts/run_t12_annual_expanding.py:350–358 → research/t12_annual_expanding_v2/results/
 ▼
scripts/t12_figures.py  (--results R --work W --figs F)
 │   ├─ derived_tables :470  → R/summary_by_year_policy.csv  (:510, %.6g)
 │   ├─ aggregates     :513  → R/aggregates.csv              (:572, %.6g)
 │   ├─ 그림 F01–F12 :149–415 + ETF_<ticker> :418  (daily.csv.gz 필요: F04, ETF_*)
 │   └─ figure_manifest.csv  :602 (원천 표 sha256 앞 16자 + png sha256)
 ▼
research/t12_annual_expanding_v2/report/  build_report.py (토큰 {{alias|키|열|형식}} → 결과표 값; ALIAS :22–35)
                                           check_tokens.py (토큰 해석 오류 검사)
```

합성 검증은 실데이터 DAG 와 **독립된 가지**다:

```
scripts/run_t12_synthetic_validation.py (--workers 4 기본, --out 기본 = REPO_ROOT/outputs/t12/synthetic)
 ├─ detector_job :43  → synthetic.py:118 DETECTOR_DGPS × detector_reps(1000) → synthetic.py:167 evaluate
 ├─ pipeline_job :57  → synthetic.py:215 PIPELINE_DGPS × pipeline_reps(200) → synthetic.py:222 pipeline_rep
 ├─ summarize :62 (Wilson CI synthetic.py:157)
 └─ :136–145  <out>/null_dgp_validation.csv · replicates.json · synthetic_manifest.json
    :147–151  --publish 면 results/ 로 복사
```

## 1. 산출물 → 생산자 표

| 산출물 (results/) | 생산 함수 | 파일:줄 | 입력 |
|---|---|---|---|
| `fold_manifest.csv` … `annual_history_ablation.csv` (8 표) | `run_ticker` → `merge` | worker.py:122, pipeline.py:100 | r_t, cfg, meta |
| `diagnostic_profile.csv` | `build_profile` | profile.py:179 (호출 pipeline.py:116) | 병합된 8 표 + cfg.flag_rules |
| `integrity.csv` | `integrity` | pipeline.py:120 (쓰기 :209) | 병합 표 + 기대 행 수 |
| `run_manifest.json` | `run` | pipeline.py:213–243 | 위 전부 + 환경 |
| `summary_by_year_policy.csv` | `derived_tables` | scripts/t12_figures.py:470 (쓰기 :510) | results/ 의 표 |
| `aggregates.csv` | `aggregates` | scripts/t12_figures.py:513 (쓰기 :572) | results/ 의 표 |
| `null_dgp_validation.csv`, `synthetic_manifest.json` | `__main__` | scripts/run_t12_synthetic_validation.py:136–151 | cfg 만 (실데이터 없음) |
| `figures/*.png`, `figures/figure_manifest.csv` | `fig_*` | scripts/t12_figures.py:149–467, :602 | results/ + work/<ticker>/daily.csv.gz |

주의: `t12_figures.py` 는 `--results` 로 받은 폴더에 `summary_by_year_policy.csv`·`aggregates.csv` 를 **덮어쓴다**.
노트북은 커밋된 `research/.../results/` 를 넘기지 않고 `outputs/` 아래 복사본을 넘긴 뒤, 재생성된 두 파일이
커밋본과 바이트 동일한지 확인한다 (두 파일에는 git_sha 가 없으므로 바이트 비교가 유효하다).

## 2. 실행 메타데이터와 결과표의 관계 (B-2 의 근거)

- `git_sha()` (pipeline.py:65–78): `git rev-parse HEAD` + `git status --porcelain -- src configs scripts` 가 비어 있지 않으면 `+dirty`.
  **실행 시작 시 1회** 계산된다 (pipeline.py:179). untracked 파일도 porcelain 에 나오므로 dirty 를 만든다.
- 이 값은 `fold_manifest.git_sha` 열(worker.py:227)과 `run_manifest.git_sha` 로 들어간다. 다른 결과표에는 들어가지 않는다.
- `code_sha()` (pipeline.py:55–62): `src/r2h/{annual_expanding,paper2020,svrgarch_etf}/*.py` 내용 해시. 커밋 여부와 무관.
- **발견**: pipeline.py:198 의 `d["code_sha"] != meta["code_sha"]` 검사는 동어반복이다. worker 는 부모가 넘긴
  `meta["code_sha"]` 를 그대로 돌려주므로 (worker.py:635), 자식 프로세스가 다른 코드를 import 해도 이 검사는 통과한다.
  독립 가드가 아니다. (수정은 결과에 영향이 없으나 src 변경이므로 하지 않았다 — C 판단 사항.)
- 병렬 경로(pipeline.py:187)는 `PYTHONPATH` 를 환경에서 잠시 뺀다. spawn 자식은 부모의 `sys.path` 를 넘겨받으므로
  (multiprocessing spawn preparation data) 부모가 `$W/src` 를 잡았다면 자식도 같은 src 를 import 한다. 다만 위 동어반복 때문에
  이것을 결과로 검증할 장치는 없다.
- `THREAD_ENV` (pipeline.py:52, :164–165) 는 numpy import **이후** 설정되므로 이미 로드된 BLAS 에는 늦을 수 있다.
  CLI (scripts/run_t12_annual_expanding.py:8–9) 는 numpy import **전에** 설정한다. 노트북은 첫 셀에서 numpy 전에 설정한다.

## 3. 결과 결정성에 영향을 주는 요소

| 요소 | 위치 | 처리 |
|---|---|---|
| 난수 | config.py:294 derive_seed = sha256(study_id\|키…) 앞 8바이트, config.py:300 rng_for | 실행 순서·프로세스·PYTHONHASHSEED 무관 |
| 정규 참조 표본 캐시 | worker.py:75–90 (`lru_cache`, seed = (n, reps, 용도)) | 캐시 유무가 값에 영향 없음 (키 seed). 순차 run 에서는 ticker 간 캐시 공유, 병렬은 프로세스별 — 값 동일해야 함 |
| 정렬 | pipeline.py:81 `_sort` (문자열 mergesort) | 완료 순서 무관 |
| CSV 정밀도 | worker.py:39 `FLOAT_FMT="%.10g"` | 결과표의 "전체 정밀도" = 유효숫자 10자리 문자열 |
| BLAS 스레드 | THREAD_ENV | 1 로 고정 |
| 데이터 경로 | data.py:75 `raw_dir or ETF_RAW_DIR or None` → None 이면 FinanceDataReader (네트워크) | 항상 raw_dir 명시 (D-C04) |

## 4. 합성 검증을 노트북에서 재실행할지 (판단)

- 비용 (원 증거 `R2H/outputs/t12/logs/synthetic_*.log`): workers=4 에서 136.7 s · 137.6 s · 142.3 s, 3회 모두
  `null_dgp_validation.csv` sha256 `43de7bca9b42…` 동일. 순차(workers=1)는 측정된 적이 없다 (CPU 시간으로 약 4 배 ≈ 9 분 추정).
- 실데이터 파이프라인과 데이터·코드 경로가 겹치지 않는다 (실 시세 없음, cfg 만 입력).
- 결정: 노트북은 **저장된 합성 결과 + sha256 검증 + 재실행 명령**을 기본으로 하고, 플래그 `RUN_SYNTHETIC=True`
  일 때만 CLI 를 subprocess 로 `--out $W/outputs/t12/synthetic_b_nb --workers 4` 로 다시 돌려 sha256 을 대조한다.
  근거: (1) canonical 실행은 순차(D-C05)인데 합성의 결정성 증거는 workers=4 에만 있다 — 노트북 안에서 순차로 돌리면
  검증되지 않은 조건이 하나 더 생긴다. (2) 실데이터 순차 실행만으로 노트북이 이미 약 10–11 분이다.
  (3) 합성 결과는 실데이터 결과표와 독립이라 저장본의 해시 검증으로 무결성을 확인할 수 있다.
  측정값은 `REPRO_ENV.md` 와 노트북 해당 셀에 적는다.
- B 측정 (2026-10-16, 이 워크트리): `run_t12_synthetic_validation.py --workers 4 --out outputs/t12/synthetic_b_1` → wall 146.9 s,
  sha256 `43de7bca9b42…` = 저장본 (4회째 일치). 노트북은 `T12_RUN_SYNTHETIC=1` 일 때만 같은 명령을 subprocess 로 재실행한다.

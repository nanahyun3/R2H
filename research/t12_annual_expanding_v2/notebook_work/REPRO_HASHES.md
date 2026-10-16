# REPRO_HASHES — seq/par 불일치 독립 확인 · Byte vs Semantic 판정표 (B-2)

도구: `scripts/t12_semantic_fingerprint.py` (정의는 파일 머리말). 테스트: `tests/integration/test_t12_semantic_fingerprint.py`.
1차 증거(읽기 전용): `R2H/outputs/t12/work/{seq_golden,par2,par4,par4_rerun}/merged/`, `R2H/outputs/t12/logs/`.
B 의 비교 산출물(커밋 안 함, `outputs/`): `outputs/t12/fingerprint/*.csv|json`.

## 1. 기준 지문 — seq_golden (= 커밋된 `research/t12_annual_expanding_v2/results/`, 바이트 동일 11/11)

| 표 | 행 | Byte sha256 (앞 16) | Semantic sha256 (앞 16) | Verdict sha256 (앞 16) | 제외 열 |
|---|---:|---|---|---|---|
| fold_manifest | 420 | 9f42f0fb1f130aa9 | cc40b7c4241a38d3 | 3082facd6ef37e1d | git_sha |
| fit_summary | 360 | eb32f1fb31c145f9 | 0ac2a7bbb88daa9b | 58b2ced6e487508f | |
| annual_vol_diagnostics | 140 | 41696cf0629a23ae | 385b4a4fcb5cafc2 | 1f759bb2b9bdaee9 | |
| annual_forecast_diagnostics | 420 | d7017b72dedfa67d | 88758955b710dbae | 4aca0ec1a1ea3b12 | |
| annual_residual_diagnostics | 420 | 1b343557207fb441 | 72b8d05d44f8e93f | 7c405e6c4dd8ac6b | |
| annual_posthoc | 2100 | 5d8910821e20de5f | 65811b59ade194ea | 222e3fabaed9c655 | |
| annual_cusum_diagnostics | 21000 | 28638eae402fabc0 | 09dc1ea899e8319f | 2a94b09fdaf41f1a | |
| annual_history_ablation | 840 | c9582f01d276cfc2 | 009b63e20b1c52d8 | 1ea5a7f5f0616ee0 | |
| diagnostic_profile | 420 | 5d8ae44434bc8d14 | d17159d245e6d453 | 55dca34297ed6b42 | |
| integrity | 9 | 5b22ef661bfa43d9 | 08407f35ceceb766 | bcb522720121a3e8 | |

- **집계 Semantic** = `a5dca934bee19e3d843d2914c465a330cdd9d8abcd5051c3ef212de47472f883`
- **집계 Verdict** = `48c8de250f72e22bc3d880e37ee762ecdec9fa2e98cd4258143cdf5c570e710f`
- 집계 Byte (10 표) = `f0de6ceedb831d78933b17f0aa62aca440d66d8c3133139a25cd2ab7de5c2f71` (파이프라인의 `aggregate_hash` 와는 정의가 다름 — 그쪽은 integrity 제외 9 표)
- 이 두 상수는 노트북 5절과 테스트에 하드코딩돼 있다.

### Semantic Fingerprint 의 제외 열 (코드에서 확정)

- **제외**: `git_sha` 하나 (결과표 중 실행 환경에서 오는 유일한 열; pipeline.py:65 → :179 → worker.py:227). 목록에 `run_id`, `n_workers`, `runtime_*` 도
  두었지만 현재 결과표에는 없다.
- **유지** (입력에서 결정됨 — 빼면 실제 변화가 숨는다): `data_version`, `config_hash`, `history_hash`, `model_hash`, `protocol_version`,
  `known_at`, `available_at`, `calibration_cutoff`, `evidence_refs`.
- `run_manifest.json` 은 지문에서 빼고 의미 필드(`study_id, protocol_version, tickers, config_hash, data_version, close_hash_ok,
  input_sha_per_ticker, code_sha, t11_reference_sha, integrity_pass`)만 따로 비교한다.
- 판정 열(Verdict): `annual_reject*`, `*_status`, `*_flags`, `rolling_episodes`, `rolling_alarm_days`, `n_rolling_episodes_w60_pure`,
  `w60_pure_episodes_iid_insample`, `first_alarm_date`, `signal_present`, `flagged_axes`, `h_contrast_state`, `status`, `leak_check_*`.

## 2. 판정표 — seq_golden 대비

| run | workers | git_sha (결과표) | code_sha | 소요 | Byte (10 표) | Byte 다른 표 · 열 | Semantic | Verdict | manifest 의미 필드 | 판정 |
|---|---:|---|---|---:|---|---|---|---|---|---|
| seq_golden | 1 | `ccd60d4…` | eb612bf6c11f | 628 s | REF | — | REF | REF | REF | 기준 |
| par2 | 2 | `ccd60d4…+dirty` | eb612bf6c11f | 278 s | FAIL (9/10 동일) | fold_manifest · `git_sha` | PASS | PASS | PASS | **Byte FAIL / Semantic PASS** (원인 = provenance `git_sha`) |
| par4 | 4 | `ccd60d4…+dirty` | eb612bf6c11f | 176 s | FAIL (9/10 동일) | fold_manifest · `git_sha` | PASS | PASS | PASS | **Byte FAIL / Semantic PASS** |
| par4_rerun | 4 | `ccd60d4…+dirty` | eb612bf6c11f | 173 s | FAIL (9/10 동일) | fold_manifest · `git_sha` | PASS | PASS | PASS | **Byte FAIL / Semantic PASS** |
| committed results/ | — | `ccd60d4…` | — | — | PASS (11/11 파일) | — | PASS | PASS | PASS | seq_golden 바이트 복사본 |
| **b_seq_1** (B, 이 워크트리) | 1 | `8414678…` (clean) | eb612bf6c11f | 609 s (wall 10:11) | FAIL (9/10 동일) | fold_manifest · `git_sha` | **PASS** | **PASS** | PASS | **Byte FAIL / Semantic PASS** — 순차 결정성 2회째 증거 (U1) |
| **b_par4_1** (B) | 4 | `410a7f9…` (clean) | eb612bf6c11f | 185 s (wall 3:06) | FAIL (9/10 동일) | fold_manifest · `git_sha` | **PASS** | **PASS** | PASS | **Byte FAIL / Semantic PASS** |

- Semantic 이 FAIL 인 표가 없으므로 수치 최대 차이·판정 변화 수는 0 이다 (비교 도구는 Semantic FAIL 일 때만 열별 차이를 계산한다;
  위 run 들은 git_sha 외 열이 문자 단위로 같다 — `cut -d, -f1-15 fold_manifest.csv` 가 바이트 동일, 나머지 9 표는 파일 바이트 동일).
- b_seq_1 은 사전 예측(STATUS.md, 실행 전 기록)과 정확히 일치했다: 바이트가 다른 파일은 `fold_manifest.csv`(git_sha 열)와 `run_manifest.json` 뿐.

## 3. 원인 확인 — 진단 순서

지시서 §6 B-2 원문 (C `DIRECTIVE_EXCERPTS.md`) 의 진단 순서 1–7 에 맞춰 대조했다. 전제 조건(같은 입력 CSV·fold·seed·버전·모형·통계량)은
먼저 확인했다: data_version `5f20e3e0073b521a`·입력 해시 20/20 동일, config_hash `0a9fbaa9c5776ebc`, code_sha `eb612bf6c11f15f8`,
환경(python 3.12.3 · numpy 2.5.4 · pandas 3.0.6 · sklearn 1.9.1 · uv.lock 동일 · THREAD_ENV=1) 은 네 run 모두 같다.

| # (원문) | 진단 항목 | 방법 | 결과 (seq_golden vs par2·par4·par4_rerun) |
|---|---|---|---|
| 1 | CSV 행·열 정렬 및 인덱스 | 행 수·열 목록 비교, `integrity.csv` (PK 유일성·기대 행 수), 지문 도구의 키 정렬·중복 검사 | 10 표 모두 행 수·열 이름·열 순서 동일, 키 중복 0, integrity 9/9 PASS. 정렬 차이 없음 (9 표는 파일 바이트 동일) |
| 2 | float 직렬화·파일 메타데이터 | 표별 sha256, `%.10g`·LF 형식 확인 | 9/10 바이트 동일. `fold_manifest.csv` 만 다르며 앞 15열은 바이트 동일 (`cut -d, -f1-15`) → 직렬화 차이 아님. 다른 것은 provenance 열 `git_sha` 하나 (`ccd60d4…` vs `ccd60d4…+dirty`, 420행) |
| 3 | 결과의 전체 정밀도 차이 | Semantic Fingerprint (`float.hex()`, 반올림 없음, git_sha 제외) | 10 표 Semantic PASS → 저장 정밀도 범위 안에서 수치 차이 0 (최대 절대 차이 0) |
| 4 | RNG·작업 순서·작업별 seed | 코드 확인: seed = sha256 키 (config.py:294), 병합 안정 정렬 (pipeline.py:81) | 순서·프로세스 무관 설계. 결과로도 차이 없음 (3). C-11: 정규 참조 표본은 `(n, reps, 용도)` 키로 ETF 간 공유 — 순서와 무관 |
| 5 | NumPy/BLAS thread 및 최적화 구현 | `run_manifest.environment.thread_env`, numpy 빌드 (scipy-openblas 0.3.34) | 네 run 모두 THREAD_ENV=1, 같은 venv. 차이 원인 아님 |
| 6 | 병렬 작업에서 공유된 mutable state | 코드 확인: worker 는 ticker 별 독립 폴더에 원자적 쓰기, `lru_cache` 는 키 seed 값의 메모 (worker.py:75–90, 읽기 전용 배열) | 공유 가변 상태 없음. 순차(캐시 공유)와 병렬(프로세스별 캐시)이 Semantic 동일 |
| 7 | 실제 모델 파라미터·통계량·기각 여부 변화 | Verdict Fingerprint (기각·에피소드·상태·플래그 열), `fit_summary` 파라미터·`model_hash` | 10 표 Verdict PASS, `fit_summary` Semantic PASS → 파라미터·통계량·기각 여부 변화 없음 |

**원인 판정**: 1–7 어디에서도 결과 차이가 없다. 유일한 바이트 차이는 provenance 열 `git_sha` 의 `+dirty` 이고, 그 발생 시점은 아래와 같다.

**`+dirty` 발생 근거**

- 구현 (pipeline.py:65–78): `git status --porcelain -- src configs scripts` 가 비어 있지 않으면 `+dirty`. 실행 시작 시 1회 (pipeline.py:179).
- **재현 실험 (B 워크트리, 2026-10-16)** — `git_sha()` 를 직접 호출:
  `scripts/` 에 untracked 파일을 만들면 → `8414678…+dirty`; 지우면 → `8414678…`;
  `scripts/__pycache__/*.pyc` 만 있으면 → clean (`.gitignore` `__pycache__/`); `src/configs/scripts` 밖(`research/`)의 untracked → clean.
- 원본 트리의 파일 집합 (git 명령은 B 워크트리에서만 실행, 원본은 파일 읽기만): `R2H/{src,configs,scripts}` 의 추적 파일은
  모두 `ccd60d4` blob 과 **바이트 동일** (수정 0). `ccd60d4` 에 없는 파일은 정확히 **2개**: `scripts/t12_figures.py`, `scripts/t12_compare_runs.py`
  (둘 다 canonical base `8414678` 에 같은 blob 으로 보존됨).
- 시각 (`stat` birth/mtime, KST):

| 시각 | 사건 |
|---|---|
| 11:20:36 | `ccd60d4` 커밋 |
| ≈11:20:42.6 | seq_golden 시작 (log 종료 11:31:12.19 − wall 10:29.54) → `git_sha` 계산, 이때 untracked 없음 → clean |
| **11:23:48.87** | `scripts/t12_figures.py` 생성 (untracked) ← **첫 dirty 원인** |
| 11:25:19.30 | `scripts/t12_compare_runs.py` 생성 (untracked) |
| 11:31:12 | seq_golden 종료 |
| ≈11:31:12 | par2 시작 (종료 11:35:51.59 − wall 4:39.40) → `+dirty` |
| 11:35:34 | `scripts/__pycache__/` 생성 — gitignore 대상, 무관 |
| ≈11:35:51.6 / ≈11:38:49.0 | par4 / par4_rerun 시작 → `+dirty` |

**판정**: C 의 원인 판정(D-C02)을 **확정**하되 한 가지를 **정정**한다. 원인은 "untracked `scripts/t12_compare_runs.py`" 하나가 아니다.
`scripts/` 아래 untracked 파일 **2개**이고, 먼저 생긴 것은 `t12_figures.py` (11:23:48) 다. par 세 run 은 둘 다 있는 상태에서 시작했으므로,
둘 중 어느 하나만으로도 `+dirty` 가 된다. 결론(provenance 열 `git_sha` 만 다름, 결과 동일)은 같다. 기록 판정은 그대로
**Byte FAIL / Semantic PASS** 다 (L9 — PASS 로 고쳐 쓰지 않는다).

## 4. 병렬 (b_par4_1)

- `scripts/run_t12_annual_expanding.py --run-id b_par4_1 --workers 4 --raw-dir $W/data/raw`, 이 워크트리 src, 작업트리 clean (HEAD `410a7f9`).
- seq_golden 대비 Semantic·Verdict PASS. b_seq_1 대비로도 바이트가 다른 파일은 `fold_manifest.csv`(git_sha: `8414678…` vs `410a7f9…`, 두 run 사이에
  B 가 커밋했기 때문) 와 `run_manifest.json` 뿐이다. 둘 다 clean 이므로 `+dirty` 는 붙지 않았다 — §3 원인과 일치.
- 결론: 이번 조건(같은 venv·스레드 1·로컬 데이터)에서 병렬(4)과 순차(1)의 결과표는 provenance 열을 빼면 같다. 병렬을 비활성화할 이유는 찾지 못했다.
  다만 canonical 실행은 D-C05 대로 순차다. 병렬 자식의 import 경로는 결과로 검증되지 않는다 (§5 첫 항목).

## 5. 기타 발견

- pipeline.py:198 의 `code_sha` 일치 검사는 **무효다 (결과 무영향)**. worker 가 부모 `meta["code_sha"]` 를 그대로 돌려주는 동어반복이라
  (worker.py:635) 병렬 자식이 다른 src 를 import 해도 잡지 못한다. 이번 미션에서는 src 를 고치지 않는다 (D-C08).
- 합성 검증 `null_dgp_validation.csv`: 원 증거 3회(synthetic, synthetic_r1, synthetic_r2; workers=4) 모두 sha256 `43de7bca9b42…` 동일,
  커밋본과 동일.

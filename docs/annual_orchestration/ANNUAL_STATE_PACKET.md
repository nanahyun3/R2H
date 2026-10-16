# ANNUAL_STATE_PACKET — T12 Annual Expanding 재현 완결 (C 작성, 2026-10-16)

소유: **C** (오케스트레이터). A·B 는 읽기만 한다. 갱신은 C 가 이 파일과 `TICKETS.md`·`DECISION_LOG.md` 에 남긴다.

## 1. 기준점 (실측 2026-10-16)

| 항목 | 값 |
|---|---|
| 원본 작업트리 | `SA/1012_Annual_SVR–GARCH-CUSUM/R2H` — 브랜치 `1012_Annual_SVR–GARCH-CUSUM` @ `ccd60d4` (origin 은 `7c3eafa`, 로컬이 17커밋 앞섬, push 안 됨). **이 트리는 이번 미션에서 건드리지 않는다** (1차 증거 보존) |
| 원격 | `https://github.com/nanahyun3/R2H.git` · 마지막 fetch 2026-10-12 (이후 원격 상태 미확인, fetch 하지 않음) |
| T12 Protocol Lock | `cb9e9ca` (`T12v2-lock-1`) · 구현 `ccd60d4` |
| **canonical base** | **`8414678`** = `ccd60d4` + 10/12 untracked 산출물(results·figures·report·`scripts/t12_compare_runs.py`·`scripts/t12_figures.py`) 바이트 그대로 보존 커밋. `report/__pycache__` 제외 |
| T11 기준 | `SA/1012/R2H` `1012_SVR-GARCH-CUSUM` @ `be38b8e` — **읽기 전용** (10/16 untracked 파일 1개 있음, 다른 주체 작업 가능성) |
| daum_tf09 격리 | `SA/.git/info/exclude` 에 `1012_Annual_SVR–GARCH-CUSUM/` 추가 → `git -C SA status` 에서 사라짐 (감사 B-4 해소) |
| 메모 | 예전 메모의 독립 클론 `R2H_annual/` 은 존재하지 않는다. 이번 지시서가 `SA/` 경로를 명시하므로 지시서가 우선 |

## 2. 작업공간 (모두 `8414678` 에서 출발)

| 레인 | 경로 (`W=SA/1012_Annual_SVR–GARCH-CUSUM/.worktrees`) | 브랜치 | 쓰기 허용 |
|---|---|---|---|
| A | `$W/a` | `research/annual-a-method` | `docs/annual_assurance/**`, `tests/assurance/**`, 자기 `outputs/` |
| B | `$W/b` | `research/annual-b-notebook` | `research/t12_annual_expanding_v2/**`, `notebooks/T12_*.ipynb`, `scripts/t12_*.py`, (필요 시 티켓 승인 후) `src/r2h/annual_expanding/**`, 자기 `outputs/` |
| C | `$W/c` | `research/annual-c-integration` | `docs/annual_orchestration/**`, 통합 머지 |

- 인터프리터: **`$R/.venv/bin/python`** (`R=SA/1012_Annual_SVR–GARCH-CUSUM/R2H`; Python 3.12.3 · numpy 2.5.4 · pandas 3.0.6 · scikit-learn 1.9.1). hongik `.venv` 와 버전이 다르므로 섞지 않는다.
- **반드시 `PYTHONPATH=<자기 워크트리>/src`**. `.venv` 의 `r2h` 는 원본 트리 `src` 의 editable 설치라서, 빠뜨리면 원본 코드가 돌고 `REPO_ROOT`(=`__file__` 기준)도 원본 트리가 되어 원본 `outputs/t12/work` 를 덮어쓸 수 있다. 시작 게이트: `python -c "import r2h;print(r2h.__file__)"` 가 자기 워크트리여야 한다 (3개 모두 통과 확인).
- `data/raw` 는 각 워크트리에서 원본 `R2H/data/raw` 로의 심링크다 (gitignore + info/exclude). 수정 금지.
- run_id 접두사: A `a_*`, B `b_*`, C `c_*`. 기존 `seq_golden`·`par2`·`par4`·`par4_rerun`·`pilot_g3` 재사용 금지.

## 3. 원자료

- `data/raw/*.csv` 20종 + `MANIFEST.csv` + listing 스냅샷. 수정 시각은 모두 2026-10-03 20:58–21:06. sha256 목록: `evidence/raw_data_sha256.txt`.
- `load_close_panel('data/raw')` 재계산 결과: `data_version = 5f20e3e0073b521a`, 20/20 `close_hash_ok`, 공통 거래일 1,903행. **10/12 실행과 같다.**
- ⚠ **함정 (C 실측)**: `load_close_panel(raw_dir=None)` 은 `ETF_RAW_DIR` 가 없으면 **FinanceDataReader 네트워크 조회**로 간다. 2026-10-16 조회본은 **153130 종가가 기준 스냅샷과 달라** `DataVersionDiffers` 로 멈췄다 (데이터 제공자가 과거 값을 수정함). 노트북·스크립트는 반드시 로컬 `data/raw` 를 명시적으로 넘기고, 네트워크 경로를 쓰지 않는다. CLI `scripts/run_t12_annual_expanding.py` 는 기본값이 `data/raw` 라서 안전하다.

## 4. 기존 실행·결과 상태

| run | workers | aggregate_hash | git_sha (결과표 안) | code_sha | 소요 |
|---|---|---|---|---|---|
| `seq_golden` | 1 | `0fa201c09638…` | `ccd60d44…` | `eb612bf6c11f` | 628 s |
| `par2` | 2 | `e11aa29efa9e…` | `ccd60d44…+dirty` | `eb612bf6c11f` | 278 s |
| `par4` | 4 | `e11aa29efa9e…` | `ccd60d44…+dirty` | `eb612bf6c11f` | 176 s |
| `par4_rerun` | 4 | `e11aa29efa9e…` | `ccd60d44…+dirty` | `eb612bf6c11f` | 173 s |

- 결과표 9종 중 **`fold_manifest.csv` 하나만** sha256 이 다르다. 나머지 8종은 네 run 이 바이트 동일하다.
- `fold_manifest.csv` 도 앞 15열은 바이트 동일하다. 다른 것은 마지막 `git_sha` 열뿐이다: seq `ccd60d4…` vs par `ccd60d4…+dirty`.
- **원인 (C 판정, B 가 B-2 에서 독립 확인할 것)**: `pipeline.git_sha()` 는 `git status --porcelain -- src configs scripts` 가 비어 있지 않으면 `+dirty` 를 붙인다. `scripts/t12_compare_runs.py` 가 11:25 에 untracked 로 생겼다. seq_golden 은 그보다 앞서(≈11:20:43, 매니페스트 11:31 − 628 s) 시작했다. par 세 run 은 그 뒤에 실행됐다. 네 run 의 `code_sha` 가 같으므로 코드 드리프트는 아니다.
- 판정 기록: **Byte Hash FAIL / Semantic PASS (원인 = provenance 열 `git_sha`)**. L9 에 따라 PASS 로 고쳐 쓰지 않는다.
- 순차 실행의 결정성은 **seq 1회뿐이라 아직 직접 증명되지 않았다**. canonical 노트북의 순차 실행이 두 번째 seq 증거가 된다.
- 기존 테스트: canonical base 에서 `pytest tests` → **126 passed** (14 s).
- `research/t12_annual_expanding_v2/results/` = `seq_golden/merged` 복사본 + 집계(`aggregates.csv`, `summary_by_year_policy.csv`, `integrity.csv`, `null_dgp_validation.csv`, `synthetic_manifest.json`). 해시: `evidence/t12_results_sha256.txt`, 원본 `outputs/t12/**` 해시: `evidence/outputs_t12_sha256.txt`.
- 보고서 `report/REPORT_TEMPLATE.md` 는 `{{agg|…}}`·`{{syn|…}}` 토큰 템플릿이고, 렌더된 보고서는 없다.
- `experiments.md` 에 T12 카드가 없다 (C 가 만든다).

## 5. 해시 정의 (이번 미션 고정)

- **Byte Hash**: 저장된 파일 그대로의 sha256.
- **Semantic Result Fingerprint**: 각 결과표를 키(`ticker, year, policy, history_strategy, window, boundary_mode, calibration_method` 중 존재하는 것)로 안정 정렬하고, **provenance 열(`git_sha`, 그리고 run_id·runtime 등 실행 메타데이터 열 — 목록은 B 가 코드에서 확정해 명시)** 만 제외한 뒤, 나머지 열의 이름·dtype·값을 전체 정밀도로 직렬화한 sha256. 반올림하지 않는다.
- 판정: Semantic 이 같고 Byte 가 다르면 "Byte FAIL / Semantic PASS + 원인". 수치 차이가 있으면 최대 차이와 그 차이가 **기각 판정(reject 열·에피소드 수·status)** 을 바꾸는지 함께 적는다. 판정이 바뀌면 무조건 FAIL.
- `git_sha` 는 노트북 실행·새 커밋·워크트리에서 바뀔 수밖에 없다. 그러므로 canonical 노트북 결과와 seq_golden 의 비교 기준은 Semantic Fingerprint 다.

## 6. 미재현·미확정 문제

| # | 문제 | 담당 |
|---|---|---|
| U1 | 순차 실행 2회째 결정성 미증명 | B |
| U2 | Semantic Fingerprint 구현·제외 열 목록 확정 | B (A 감사) |
| U3 | 렌더된 보고서 없음. 노트북이 결과표·그림·결론을 재생성해야 함 | B |
| U4 | 원논문 수치 재현은 T09 에서 `METHOD_FIDELITY_UNRESOLVED` — T12 해석 제약으로 기술 | A |
| U5 | 2026 `PARTIAL_NON_BLIND` (10/2 까지), 2020 `PILOT_SHORT_HISTORY` | A·B 모든 표·그림에 명시 |
| U6 | 이동창 임계값은 점별 95% 다. 연간 첫 경보 5% 가 아니다 (L5) | A |
| U7 | 네트워크 데이터 경로가 기본값인 함수 존재 (§3) | B 노트북에서 차단 |

## 7. 의존관계 · 완료 기준

```
P0 (C, 완료) ─┬─ A-1 계약 → A-2 감사 → A-3 비교계약 ─┐
              └─ B-1 DAG → B-2 해시 → B-3 환경 → B-4 노트북 ─┴→ A-4 독립 리뷰 → C 통합·최종 실행 → 커밋
```

- **G1 (B-2 끝)**: Byte/Semantic 판정표가 있고, 새 순차 실행(`b_seq_*`)이 seq_golden 과 Semantic 일치.
- **G2 (A-1·A-3 끝)**: 계약의 모든 항목에 코드 `파일:줄` 과 문서 근거가 있다.
- **G3 (B-4 끝)**: 새 커널에서 `jupyter nbconvert --execute` 로 처음부터 끝까지 성공하고, 산출 결과표의 Semantic Fingerprint 가 seq_golden 과 같다. 노트북 규칙 테스트(`tests/integration/test_notebook_rules.py`)와 `pytest tests` 가 통과한다.
- **G4 (A-4)**: A 판정이 승인 또는 조건부 승인이고, 조건이 모두 해소됐다.
- **최종**: C 가 통합 브랜치에서 노트북을 다시 실행해 G3 를 재확인한 뒤 커밋한다. **push 는 사용자 승인 전에는 하지 않는다.**

## 8. 범위 밖

Gold Label, 20거래일 온라인 baseline, 뉴스·LLM, BOCPD, 매매 백테스트, 신규 탐지 성능 최적화. 결과를 본 뒤 임계값·학습기간·검정을 바꾸는 일도 범위 밖이다 (바꾸는 경우 `Sensitivity` 로 분리).

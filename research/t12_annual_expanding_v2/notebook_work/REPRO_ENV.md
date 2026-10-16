# REPRO_ENV — T12 재현 환경 (B-3)

측정일 2026-10-16 · 워크트리 `.worktrees/b` (브랜치 `research/annual-b-notebook`).
`$R` = `SA/1012_Annual_SVR–GARCH-CUSUM/R2H` (원본 트리, 읽기 전용), `$W` = 이 저장소 루트.

## 1. 인터프리터 · 패키지 (importlib.metadata 로 측정)

| 항목 | 값 | 비고 |
|---|---|---|
| 인터프리터 | `$R/.venv/bin/python` | hongik `.venv` 와 섞지 않는다 (버전이 다름) |
| Python | 3.12.3 | |
| numpy | 2.5.4 (scipy-openblas 0.3.34, DYNAMIC_ARCH) | **assert** (노트북 0절) |
| pandas | 3.0.6 | **assert** |
| scikit-learn | 1.9.1 | **assert** |
| scipy | 1.18.1 | 기록 |
| matplotlib | 3.11.2 | 기록 |
| nbclient / ipykernel / jupyter_client | 0.11.0 / 7.4.0 / 8.10.0 | `nbconvert` 없음 → `jupyter execute` 사용 |
| pytest | 9.1.1 | |
| FinanceDataReader | **설치 안 됨** | 네트워크 경로는 이 venv 에서 ImportError 로도 막힌다 |
| uv.lock sha256 | `283c21139b79…` (run_manifest `environment.uv_lock_sha256`) | 의존성 변경 없음 |

seq_golden·par2·par4·par4_rerun 의 `run_manifest.environment` 는 위 핵심 4개와 같다. 노트북은 핵심 4개가 다르면 멈춘다
(다른 BLAS/라이브러리 버전은 `lstsq`·SVR 결과를 비트 단위로 바꿀 수 있다).

측정 명령:

```bash
env -u VIRTUAL_ENV -u LD_LIBRARY_PATH PYTHONPATH=$W/src $R/.venv/bin/python -c \
  "import importlib.metadata as m; print({p: m.version(p) for p in ['numpy','pandas','scipy','scikit-learn','matplotlib','nbclient','ipykernel']})"
```

## 2. 모듈 경로 (가장 위험한 함정)

- `$R/.venv` 의 `r2h` 는 `_editable_impl_r2h.pth` (내용: `$R/src`) 로 **원본 트리 src** 를 가리킨다.
  `PYTHONPATH` 없이 돌리면 원본 코드가 돌고 `REPO_ROOT`(config.py:278, `__file__` 기준) 도 원본 트리가 된다 → 원본 `outputs/t12/work` 를 덮어쓸 수 있다.
- 이 셸(Claude Code hongik 설정)은 `PATH`·`VIRTUAL_ENV`·`LD_LIBRARY_PATH`·`PYTHONPATH` 에 **hongik** 값을 주입한다.
  모든 명령을 `env -u VIRTUAL_ENV -u LD_LIBRARY_PATH PYTHONPATH=$W/src $R/.venv/bin/…` 로 감싼다. 맨 `jupyter`·`pytest` 를 쓰지 않는다.
- 시작 게이트: `PYTHONPATH=$W/src $R/.venv/bin/python -c "import r2h; print(r2h.__file__)"` → `$W/src/r2h/__init__.py` (확인함).
- 노트북은 환경변수에 기대지 않는다: 첫 셀이 저장소 루트를 찾아 `sys.path.insert(0, ROOT/src)` 하고
  `r2h.__file__ ∈ ROOT/src`, `config.REPO_ROOT == ROOT` 를 assert 한다.
- 커널: `$R/.venv/share/jupyter/kernels/python3` (argv `python` → jupyter_client 가 `sys.executable` 로 바꿈 = `$R/.venv/bin/python`).
  사용자 커널 스펙에 `python3` 이름의 덮어쓰기는 없다 (`jupyter kernelspec list` 확인).
- 병렬 경로(pipeline.py:187)는 자식 프로세스 환경에서 `PYTHONPATH` 를 뺀다. spawn 자식은 부모 `sys.path` 를 넘겨받으므로 부모가
  `$W/src` 를 잡았으면 같은 src 를 쓰지만, pipeline.py:198 의 code_sha 검사는 부모 값을 되돌려 받는 동어반복이라 이를 검증하지 못한다.

## 3. 스레드 · seed · 캐시

- `THREAD_ENV` = `OMP_NUM_THREADS, OPENBLAS_NUM_THREADS, MKL_NUM_THREADS, NUMEXPR_NUM_THREADS` = `1`.
  CLI (`scripts/run_t12_annual_expanding.py:8–9`) 와 노트북 첫 셀은 **numpy import 전에** 설정한다. `pipeline.run` (:164) 은 import 후에
  다시 설정하는데, 이미 초기화된 OpenBLAS 에는 늦을 수 있다. 그래서 라이브러리로 부를 때는 반드시 import 전에 설정한다.
- seed: `config.derive_seed(*key)` = `int.from_bytes(sha256("|".join(key))[:8], "big")` (config.py:294). 키 = `study_id`, ticker, year,
  policy, history, window, purpose, method. Python `hash()`·`PYTHONHASHSEED`·실행 순서·worker 수와 무관하다. `cfg.seed` (20261012) 는 T12 실데이터 경로에서 쓰이지 않는다.
- 캐시: `worker.py:75–90` 의 `lru_cache` (정규 참조 표본·임계값·귀무 에피소드)는 키 seed 로 만든 값을 메모할 뿐이다. 캐시 적중 여부는 값을 바꾸지 않는다
  (순차 run = ticker 간 공유, 병렬 = 프로세스별 — 두 경우 결과표가 Semantic 동일함을 REPRO_HASHES 에서 확인).
  디스크 캐시: `outputs/cache/raw/` 는 네트워크 경로에서만 쓰인다 (로컬 raw_dir 경로에서는 쓰지 않음).
  `outputs/t12/work/<run_id>/` 는 run 마다 새로 만든다. 노트북은 기존 run_id 폴더가 있으면 멈춘다 (덮어쓰기·재사용 금지가 기본).

## 4. 데이터

- 경로: `$W/data/raw` → `$R/data/raw` 심링크 (20 CSV + `MANIFEST.csv` + `listing_snapshot_20261003T2058.csv`). 수정 금지.
- 파일 해시: `notebook_work/raw_data_sha256.txt` (B 가 2026-10-16 측정, C `evidence/raw_data_sha256.txt` 와 **동일**).
- 내용 해시: 로더가 종가를 `research/svr_garch_cusum_etf/reference_close_sha256.csv` 와 대조 → `data_version = 5f20e3e0073b521a`
  (= `cfg.expected_data_version`), 20/20 `hash_ok`.
- 검증 명령:

```bash
cd $W && sha256sum -c research/t12_annual_expanding_v2/notebook_work/raw_data_sha256.txt
env -u VIRTUAL_ENV -u LD_LIBRARY_PATH PYTHONPATH=$W/src $R/.venv/bin/python -c \
  "from r2h.svrgarch_etf.data import load_close_panel as L; p=L('data/raw'); print(p.data_version, all(p.hash_ok.values()), p.source)"
```

## 5. 오프라인 실행

- 항상 `raw_dir` 를 명시한다. 노트북은 `os.environ["ETF_RAW_DIR"] = ROOT/data/raw` 도 설정한다 (data.py:75 의 네트워크 분기 차단).
- CLI 의 `--raw-dir` 기본값은 `ETF_RAW_DIR` 또는 `REPO_ROOT/data/raw` 라서 안전하다. 그래도 명령에 `--raw-dir $W/data/raw` 를 명시한다.
- 네트워크가 필요한 단계는 없다. FinanceDataReader 는 이 venv 에 없다.

## 6. 실패 시 규칙 — 중간 결과 미발표

- `integrity_pass == False`, `data_version` 불일치, 노트북의 Semantic/Verdict assert 실패 중 하나라도 있으면 그 run 의 산출물은
  **발표·커밋·`--publish` 하지 않는다**. `outputs/` 에 남겨 원인 조사에만 쓴다.
- 중간에 끊긴 run 폴더(`DONE.json` 이 없는 ticker 또는 `merged/` 없음)는 재사용하지 않는다. 새 run_id 로 다시 돌린다.
- 결과가 다르면 PASS 로 고쳐 쓰지 않는다 (L9). 표 이름·열·최대 차이·판정 변화 수를 그대로 적는다.

## 7. 단일 실행 명령

```bash
W=<이 저장소 루트>; R=<R2H 원본 트리>
cd $W
# (1) 재현 노트북 — 순차 전체 실행 + seq_golden Semantic assert + 표·그림 (약 11–12 분)
env -u VIRTUAL_ENV -u LD_LIBRARY_PATH PATH=$R/.venv/bin:/usr/bin:/bin PYTHONPATH=$W/src \
  $R/.venv/bin/jupyter execute --inplace --timeout=3600 notebooks/T12_Annual_Expanding_Reproduction.ipynb
# (2) 테스트 (노트북 규칙 포함)
env -u VIRTUAL_ENV -u LD_LIBRARY_PATH PYTHONPATH=$W/src $R/.venv/bin/python -m pytest -q tests
# (참고) CLI 순차 실행 + 지문 비교
env -u VIRTUAL_ENV -u LD_LIBRARY_PATH PYTHONPATH=$W/src $R/.venv/bin/python scripts/run_t12_annual_expanding.py \
  --run-id b_seq_N --workers 1 --raw-dir $W/data/raw
env -u VIRTUAL_ENV -u LD_LIBRARY_PATH PYTHONPATH=$W/src $R/.venv/bin/python scripts/t12_semantic_fingerprint.py \
  --ref research/t12_annual_expanding_v2/results --runs outputs/t12/work/b_seq_N/merged
```

- 노트북 원본은 `scripts/t12_build_reproduction_notebook.py` 로 생성한다 (손 편집 금지 — 생성기를 고친 뒤 다시 생성·실행).
- 실행 전에 `git status --porcelain -- src configs scripts` 가 비어 있게 커밋한다. 그렇지 않으면 provenance `git_sha` 에 `+dirty` 가 붙는다
  (결과 지문에는 영향 없음).

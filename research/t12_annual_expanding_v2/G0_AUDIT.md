# T12 v2 — G0 읽기 전용 감사 (2026-10-12)

이 문서는 구현을 시작하기 전에 확인한 현황이다. 이 단계에서는 원격 push, 삭제, 원본 수정을 하지 않았다.

## 1. 저장소 · 브랜치

| 항목 | 값 |
|---|---|
| 작업 경로 | `SA/1012_Annual_SVR–GARCH-CUSUM/R2H` (독립 clone. `SA/1012/R2H` 의 worktree 가 아니다) |
| 원격 | `https://github.com/nanahyun3/R2H.git` |
| 원격 `1012` | `a346faf78ff47b2695fab438f7397d7958b8d655` (명세 작성 시 SHA 와 같다) |
| 원격 `1012_Annual_SVR–GARCH-CUSUM` | `7c3eafa9be82768319b96df5e4ffd7a9d6042c64` (= `main` = Initial commit) |
| 로컬 작업 브랜치 | `1012_Annual_SVR–GARCH-CUSUM`, 시작점 `origin/1012` (`a346faf`). `7c3eafa` 가 `a346faf` 의 조상이라 이후 push 는 fast-forward 다 |
| 시작 시 dirty tree | 없음 (`git status --porcelain` 0줄) |
| 명세와 다른 점 | 명세가 권장한 브랜치 이름은 `research/t12-annual-expanding` 이다. 사용자가 브랜치를 `1012_Annual_SVR–GARCH-CUSUM` 으로 지정했으므로 이 이름을 쓴다 (`PROTOCOL_CHANGELOG.md` C-01) |

## 2. T11 산출물 무결성

`research/svr_garch_cusum_etf/results/run_manifest.json` 의 `outputs` sha256 과 실제 파일 9개를 비교한 결과, **9/9 일치**했다.

| 파일 (T11 원본, 수정 금지) | sha256 앞 16자 |
|---|---|
| `src/r2h/paper2020/cusum.py` | `bb686701639743ab` |
| `src/r2h/paper2020/svr_garch.py` | `7ac250f2825cfd09` |
| `src/r2h/paper2020/volatility_proxy.py` | `14437996130fc80f` |
| `src/r2h/paper2020/__init__.py` | `9c1a26d4cfb8b8df` |
| `src/r2h/svrgarch_etf/data.py` | `39029374aa4c61d8` |
| `src/r2h/svrgarch_etf/model.py` | `a4f0c08c5960a443` |
| `src/r2h/svrgarch_etf/rolling.py` | `71fa9970f822d180` |
| `src/r2h/svrgarch_etf/pipeline.py` | `eaceab3d379838d5` |
| `notebooks/R2H_T11_svr_garch_cusum_etf.ipynb` | `5a138c4dff1926a8` |


기존 테스트 98개가 모두 통과했다 (`pytest -q`, 5.6 s).

## 3. 데이터

- 원천: `SA/ETF_EDA_SCAFFOLD/data/raw/*.csv` 를 **복사**해 `R2H/data/raw/` 에 두었다. 이 경로는 R2H `.gitignore` 의 `data/raw/` 에 걸려 git 에 올라가지 않는다. 원천 디렉터리는 읽기만 했다.
- 20개 파일의 sha256 이 `reference_close_sha256.csv` 의 `raw_file_sha256` 과 **20/20 일치**했다. `load_close_panel` 의 종가 해시도 20/20 일치했고, `data_version = 5f20e3e0073b521a` 로 T11 manifest 와 같다.
- 공통 거래일 수익률은 1,902개(2019-01-03 ~ 2026-10-02)다. 연도별 개수: 2019 245 · 2020 248 · 2021 248 · 2022 246 · 2023 245 · 2024 244 · 2025 242 · 2026 184 (부분 연도).
- 데이터 품질(DQ) 처리: 261240 의 2019-03-14·15 수익률은 NaN 이다 (T11 규칙).
- 라이선스: FinanceDataReader 로 수집한 KRX ETF 종가다 (`MANIFEST.csv`: "FDR Close 는 분배 소급조정으로 추정"). 재배포 조건은 확인하지 못했다. 그래서 **일별 시세·수익률·잔차·예측분산은 공개 저장소에 올리지 않는다** (`outputs/` 는 gitignore 대상이다). 커밋하는 것은 연·ETF 단위 집계통계뿐이다.

## 4. 실행 환경

| 항목 | 값 |
|---|---|
| OS | WSL2 Linux 6.18 · Python 3.12.3 |
| CPU / RAM | 논리 코어 24 · RAM 15 GB (가용 약 11 GB) |
| R2H 환경 | `uv sync --locked --extra dev --extra research --extra notebook` → 독립 `R2H/.venv`. numpy 2.5.4 · pandas 3.0.6 · scikit-learn 1.9.1 · scipy 1.18.1 (T11 manifest 와 같다) |
| 없는 것 | statsmodels. 그래서 Ljung–Box·ARCH-LM 은 numpy/scipy 로 직접 구현하고, 상위 `.venv` 의 statsmodels 0.14.6 과 한 번만 대조한다 (CI 대상 아님) |
| 문서 도구 | python-docx 1.2.0 · pymupdf 1.28.2 (상위 `.venv`) · `google-chrome` headless (HTML→PDF) · NanumGothic. 새로 내려받은 프로그램은 없다 |
| 비용 측정 | T11 `fit_etf` 1회 0.65 s (27 grid). 연간 적합 비용은 작다. 비용이 큰 부분은 Monte Carlo 다 |

## 5. 재사용할 수 있는 코드

| 재사용 (수정 없이 import) | T12 에서의 쓰임 |
|---|---|
| `paper2020.select_and_refit`, `forecast_test_variance`, `moving_square_proxy`, `cusum_squares_test` | 연초 적합, A/B 분산 예측, 연간 사후 검정 |
| `svrgarch_etf.data.load_close_panel`, `percent_log_returns` | 해시 검증 패널, 100·Δlog, DQ |
| `svrgarch_etf.model.GRID`, `M,P,Q`, `baseline_residuals` | 27 grid, 기준선 |
| `svrgarch_etf.rolling.rolling_cusum`, `iid_stats`, `episodes`, `window_khat` | 이동창 통계량, 귀무 MC, 에피소드 |
| **재사용 금지** | `fit_etf` (T11 70:30 전체 분할), `yearly_blocks` (고정 모형) — 명세 §4 와 §7 |

## 6. 위험과 잔여 사항

1. `SA/` 는 `Siegfriex/daum_tf09` 의 worktree 이고, 이 폴더(`SA/1012_Annual_SVR–GARCH-CUSUM/`)는 그 안에 untracked 로 있다. 원시 데이터는 R2H 의 gitignore 경로로 옮겼다. 그래도 `SA/` 에서 `git add .` 를 하면 이 폴더의 명세 문서와 R2H gitlink 가 잡힐 수 있다. `SA/.git/info/exclude` 는 다른 에이전트의 영역이므로 이 작업에서 수정하지 않는다. **사용자 확인이 필요하다.**
2. w=252: 모든 연도의 거래일 수(242~248)가 252보다 적다. 그래서 순수 OOS 창(창 전체가 검정연도 안)은 **구조적으로 존재하지 않는다**. 이 값은 측정 결과가 아니라 설계상 불가능이다.
3. 이력(H) 대조는 초기 연도에서 퇴화한다. 2020 에서는 trailing2y 를 할 수 없고 (SKIP), frozen2019 는 expanding 과 같다. 2021 에서는 trailing2y 가 expanding 과 같다. 이런 칸은 "이력 효과 없음" 이 아니라 `IDENTICAL_TO_EXPANDING` 으로 표시한다.
4. 2026 은 10/2 까지의 부분 연도이고 T11·EDA 에서 이미 본 구간이다 (`PARTIAL_NON_BLIND`).

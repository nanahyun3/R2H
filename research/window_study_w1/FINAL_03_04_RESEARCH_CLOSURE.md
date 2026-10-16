# W1 검정창 연구 종결 보고 — 03 대표 4종 · 04 전체 20종

작성 2026-10-16 · 연구 ID `t13_window_study_w1` · 사전 계약 [`research/03_04_연구계약.md`](../03_04_연구계약.md) · 설정 `configs/t13_window_study_v1.json` (SHA256 `8489eada913a3e62…`) · 출발점 T12 `39566e2b` / run `b_nb_20261016T181251`

## 1. 한 문장 결론

사전 고정한 W1 규칙에서 **검정창 20·30·60·120 거래일 가운데 적격 창은 0/4 이다. 따라서 결론은 '최적창 없음' 이다.**

적격을 막은 것은 주로 **검출력**이다.
- 검출기 수준에서 알려진 지속 분산 ×2 상승·×0.5 하락의 60거래일 검출률은 0.029–0.096 이다. Wilson 하한은 최대 0.079 로, 기준 0.15 에 미달했다.
- 적합 포함 정책 A 의 검출률 하한은 0.011–0.058 이다.
- 귀무 크기는 대부분 통과했다. 예외는 적합 포함 A 의 w=60 하나로, Wilson 상한 0.114 가 예산 0.10 을 넘었다.
- 04 의 20종 적용은 이 판정을 바꾸지 않는다 (계약 §4).

## 2. 인수 사실 (Codex → Claude)

| 항목 | 인수 시 상태 | 확인·조치 |
|---|---|---|
| 코드 `src/r2h/window_study/` (simulation·empirical·figures) | untracked, ruff 오류 0 | 계산 모듈 2개는 `ruff format` 만 적용 (AST 동일 확인). figures 는 표현만 수정 |
| 03 실행 (10:23–10:26Z, 190 s) | `PASS` 로 기록 | **R2H `.venv` 가 아닌 user-site 패키지** (numpy 2.5.0 · pandas 3.0.3 · sklearn 1.9.0) 로 실행됐다. 원인은 커널 명세 argv `"python"` 의 PATH 해석 |
| 04 실행 | `FAIL` (7 s, 03/04 대표 4종 동등성 assert) | 실행된 04 는 생성기 수정(19:25) **이전**(19:23) 생성본이었다. 현재 생성기의 디스크 대 디스크 비교는 PASS |
| 테스트 | `152 passed, 4 failed` | 4건 모두 노트북 03·04 규칙 위반이었다 (주석 없음, 폰트 셀 없음 — 옛 생성기 출력). 재생성 후 **156 passed** |
| ruff | 18건 보고 | W1 범위 0건. 저장소 전체 145건 중 133건은 T12 종결 코드(39566e2)의 기존 부채이며 손대지 않았다 (§7) |
| `1.2167e-09` | 출처 불명 | `daily_cache_qa.max_abs_pure_T_diff_from_T12_cache` 의 20종 최대 (219480). PURE 유효일 전체에서 재계산 T 와 T12 cache T 의 최대 절대차다. cache 의 `%.10g` 직렬화 반올림 크기와 일치한다 |
| Codex 상태 보존 | 없음 | `outputs/t13/codex_snapshot_20261016T_codex/` (44 파일 SHA256SUMS, Git 제외) |

## 3. 실행 이력 (모두 `scripts/run_t13_notebooks.py`, 새 커널 순차 03→04)

| 실행 | 환경 | 03 | 04 | 결과 CSV |
|---|---|---|---|---|
| Codex 10:23Z | user-site (numpy 2.5.0) | PASS 190 s | FAIL 7 s | 스냅샷 보존 |
| Claude #1 11:42Z | R2H `.venv` (2.5.4 / 3.0.6 / 1.9.1), PYTHONNOUSERSITE | PASS 206 s | PASS 9 s | 데이터 CSV 17/17 이 Codex 와 **바이트 동일** |
| Claude #2 11:49Z | 같음 | PASS 209 s | PASS 9 s | #1 과 바이트 동일 (그림 수정 반영) |
| Claude #3 11:53Z | 같음 | PASS 207 s | PASS 9 s | #1 과 바이트 동일 (04-2 y축 여유) |
| Claude #4 (최종 저장본) | 같음 | PASS 194 s | PASS 9 s | #1 과 바이트 동일 (03 그림 03-2 해석 문장 정정만) |

- 사전 기대([`evidence/RERUN_EXPECTATION.md`](evidence/RERUN_EXPECTATION.md))는 "적합 포함 합성은 sklearn 버전 차이로 다를 수 있다" 였다. 실측은 바이트 동일이었다.
- 따라서 W1 수치는 user-site 환경과 `.venv` 환경에서 같다. 그러나 공식 재현 환경은 `.venv` 하나로 고정한다. 노트북 첫 셀이 버전을 assert 한다.

## 4. 주장 → 근거 연결

| # | 주장 | 근거 CSV | 생성 코드 | 설정 | 입력 | 그림·셀 |
|---|---|---|---|---|---|---|
| C1 | 적격 창 0/4, 최적창 없음 | `최적창_판정과_보류사유.csv` | `simulation.select_windows` | 계약 §4 · config `primary_any_alarm_budget=0.10`, `min_h1_wilson_lower=0.15` | 합성 (seed 20261016) | 03 표·마지막 assert 셀 |
| C2 | 검출기 귀무 연간 경보 Wilson 상한 ≤ 0.0765 (세 귀무·네 창) | `03_synthetic/detector/detector_summary.csv` | `detector_experiment` | 귀무별 보정 500·평가 1,000 | 합성 | 그림 03-1 |
| C3 | 필수 대립 60일 검출률 0.029–0.096, 하한 최대 0.079 | 같음 | 같음 | 대립별 1,000, k=122 | 합성 | 그림 03-2 |
| C4 | 적합 포함 A: 귀무 상한 0.071/0.083/**0.114**/0.096, 대립 하한 0.011/0.035/0.042/0.058 (w=20/30/60/120) | `03_synthetic/pipeline/pipeline_summary.csv` | `pipeline_experiment` (T12 `fit_annual` 27 grid) | 보정·귀무·대립 각 200 | 합성 | 그림 03-3 |
| C5 | 연간 보정 임계값(검출기) 1.688/1.848/2.133/2.536 > 원문 1.3397 | `detector_thresholds.csv` | `detector_experiment` | q=0.95 연중 최대, 세 귀무 최대 | 합성 | 03 표 1 |
| C6 | 03 과 04 의 대표 4종 결과 동일 (validity 420행, alarm 1,344행) | `03_real/*.csv`, `04_real/*.csv` | `empirical.empirical_experiment` (같은 함수) | 같은 임계값 입력 | T12 daily cache | 04 동등성 셀 |
| C7 | w=252 는 모든 ETF·연도·정책에서 PURE 불가 (`NO_FULL_WINDOW`) | `04_real/validity.csv` | `_empirical_rows` | 연도 242–248 거래일 | T12 daily cache | 03·04 assert |
| C8 | 2021–2025 정책 A '경보 있는 ETF·연도' 관측 비율 0.02/0.09/0.15/0.09, 같은 임계값의 합성 GARCH 귀무 기대 0.035/0.045/0.070/0.055 | `04_real/alarm_metrics.csv` + `pipeline_summary.csv` | 04 비교 셀 | 공통 PURE · 연간 임계값 | T12 daily cache | 04 표 2-비교, 그림 04-3 |
| C9 | KOSPI200 동일 노출 4종은 2024·w60 에서 4/4 가 함께 경보 → C8 의 w60 관측 15건 중 4건이 한 노출의 동시 경보 | `04_real/alarm_metrics.csv` | 04 노출 중복 셀 | 사전 고정 노출 그룹 | 같음 | 04 표 |
| C10 | CNN 후보 142행 = 고유 ETF·연도 53, 고유 ETF·첫경보일 131. 2020 이 60행 | `04_real/cnn_candidate_intervals.csv` | `_empirical_rows` | 연간 임계값·공통일·첫 에피소드 | 같음 | 04 후보 셀 |
| C11 | 재계산 T 와 T12 cache 의 최대 절대차 1.2167e-09 | `04_real/daily_cache_qa.csv` | `_empirical_rows` (`allclose` 1e-8 게이트) | — | T12 daily cache | 03·04 assert |

## 5. 결과의 세 수준

**계산으로 확인한 사실**
- C1–C11 은 모두 결정적 실행 5회(Codex 1 + Claude 4)에서 같은 바이트로 재생성됐다 (§3).
- W1 판정은 사전 규칙에서 기계적으로 나온다. 실제 ETF 결과는 판정 함수의 입력이 아니다 (`select_windows` 는 합성 요약표만 받는다).
- 원문 1.3397·T12 점별 임계값과 W1 연간 임계값은 다른 보정 단위다. 같은 2021–2025 정책 A·공통일에서 경보 있는 ETF·연도가 w=20 기준 69 대 2 로 크게 다르다.

**가정 아래에서만 가능한 통계적 해석**
- 합성 GARCH(ω=.05, α=.10, β=.85)·t5·정규 귀무가 ETF 잔차를 대표한다면, 연간 임계값은 귀무 연간 경보를 0.10 아래로 막는다.
- 같은 가정에서, 60거래일 안에 2배 분산 변화를 잡을 확률은 0.1 안팎이다. 즉 이 통계량·평가일 설계는 크기는 맞추지만 짧은 지평의 검출력이 낮다.
- 그 기전으로 세 가지를 생각할 수 있다. 이 연구에서는 분리하지 않았다.
  - τ̂ 정규화의 흡수 (T12 감사 Q7)
  - 늦은 공통 시작일 t≥119
  - GARCH 귀무가 임계값을 지배하는 것
- 실측 경보 비율(C8)이 귀무 기대의 0.6–2.1 배다. 이것이 '귀무 부적합 · 실제 분산 변화 · 노출 중복' 중 어느 것 때문인지는 구별되지 않는다. C9 는 노출 중복이 숫자를 키운다는 직접 증거다.

**현재 자료로는 판단할 수 없는 주장**
- ETF 경보가 실제 구조변화라는 주장.
- 어느 창·자산군이 '더 좋은 탐지기' 라는 주장.
- 실제 ETF 의 참양성·거짓양성·정밀도·재현율.
- 가격 급등 탐지 성능.
- 2026 독립 검증.
- 03→04 를 독립 외부 검증이라고 부르는 것. 20종 모두 같은 기간을 같은 연구 과정에서 본 자료다.
- 2020(파일럿)과 2026(부분·비블라인드)의 차이를 시장 구조로 귀속하는 것.

## 6. 방법론 감사 (지시서 §5)

| 질문 | 판정 | 근거 |
|---|---|---|
| 03 ETF 와 비교군의 역할 | OK | 069500·229200·148070 + 잠정 102110. 102110 은 069500 과 같은 KOSPI200 노출이라 독립 노출로 세지 않는다고 본문에 명시 |
| 비교 거래일 수 | OK | 합성 126 공통일. 실측 2021–2025 정책 A 공통일 117–129 (그림 04-1, 219480 2022 만 117) |
| 창별 통계량·임계값 | OK | `rolling_cusum` 원본 재사용. 임계값 표 2종 (검출기 4개, 적합 포함 12개) |
| 점별 대 연간 최대 보정 | OK | 두 임계값을 열 `threshold_type` 으로 분리. 본문·그림에서 섞지 않음 |
| 귀무 연간 경보 확률 | OK | Wilson 95% 와 독립 평가 난수열 (`_rng(…, "eval", …)`) |
| 검출력·지연 | OK | 60일 지평 첫 경보. 지연은 검출 조건부, 미검출은 검열 |
| 검출기 대 적합 포함 구분 | OK | 결과 폴더·그림·판정 열 분리 |
| Wilson 과 사전 기준 | OK | 상한 ≤ 0.10, 하한 ≥ 0.15, n ≥ 30, 지연 기준. 코드 `select_windows` 가 계약 §4 와 일치 (코드 검토) |
| 적격 부재의 의미 | OK (서술) | '최적창 없음' 이며, 실측 경보가 적은 창을 사후에 우승시키지 않음 |
| 04 가 03 조건 승계 | OK | `03_to_04_transfer.json` 7개 파일 SHA·설정 SHA·환경 assert 를 04 가 검증 |
| 대표 4종 03=04 | OK | C6 |
| 검정 불능 구간 | OK | C7. 평가 불가를 무경보로 바꾸지 않음 |
| 자산군·노출 중복 | OK (제한) | ETF 등가중과 노출 그룹 등가중을 함께 제시. 미국 주식 2종과 T12 감사 9개 상관 군집은 계약상 추가 민감도이며 이번에 계산하지 않음 |
| 경보 다발을 검정력으로 표현 | OK | '관측 경보 부담', '참양성/오탐률 아님' 을 표·그림 각주에 명시 |
| 사후 판정 변경 | 없음 | 계약·config 는 Codex 동결본과 바이트 동일 (스냅샷 SHA). W1 판정은 실행 5회 동일 |
| 후보 구간 대 정답 | OK | 인계 계약 + C10 의 중복 구조 공개 |

**한계 (계약 위반 아님)**
- 적합 포함 실험은 반복 200회와 단일 GARCH DGP 뿐이다.
- 검출기 GARCH(ω=.05, α=.10, β=.85)와 파이프라인 GARCH(ω=.02, α=.08, β=.90)는 모수가 다르다. 둘 다 T12 원본 DGP 를 그대로 쓴 것이다.
- 적합 포함 B 의 w=120 대립에는 `NOT_ESTIMABLE` 반복이 1회 있다. B 는 선정 대상이 아니다.

## 7. 게이트 판정

| 게이트 | 판정 | 근거 |
|---|---|---|
| G0 Source | PASS | 원자료 22개·00–02 노트북 3개·T12 run manifest 를 `verify_frozen` 이 매 실행 대조. 00–02 SHA 불변 (`675474b0…`, `42ee6f85…`, `e951390f…`) |
| G1 Tests | PASS WITH LIMITATIONS | `pytest tests` 156 passed (0 failed, 0 skipped). W1 파일 ruff check·format 0건. **저장소 전체 `ruff check .` 은 W1 밖의 기존 133건 (실측, `ruff check . --statistics`) 때문에 실패한다.** CI 의 ruff 단계는 이 브랜치에서도 실패할 것이다 (W1 이 추가한 오류는 0건) |
| G2 Notebook | PASS | 03·04 새 커널 순차 실행 Claude 4회 PASS (최종본 실행 번호 1–10 연속, 오류·stderr·글리프 누락 0). 노트북 규칙 테스트 통과 |
| G3 Reproducibility | PASS WITH LIMITATIONS | 데이터 CSV 17/17 이 5회 실행에서 바이트 동일. 제한: 03·04 는 형제 작업트리 `R2H_T12_Final` 의 Git 제외 일별 cache (`outputs/t12/work/b_nb_20261016T181251/*/daily.csv.gz`, 20종 SHA 는 `daily_cache_qa.csv`) 가 필요하다. 새 clone 에서는 T12 01 노트북을 같은 run_id 로 다시 실행하거나 `T12_FROZEN_ROOT` 를 지정해야 한다 |
| G4 Scientific Audit | PASS WITH LIMITATIONS | §6. 통계적 결론은 '최적창 없음' 이며 합성 귀무 조건부 |
| G5 Figures | PASS | 7장 PNG 320dpi + SVG. 한글 글꼴 NanumGothic(+DejaVu 대체), 특수문자 글리프 cmap 확인, 범례·각주 겹침 육안 검수, 그림 번호·자료·표본 수·2020/2026 표시 |
| G6 Evidence | PASS | `evidence/` (실행 로그·실행 기록·사전 기대), `03_to_04_transfer.json`, `04_release_manifest.json`, 그림 색인 SHA, `evidence/W1_RELEASE_SHA256.txt` |
| G7 GitHub | 최종 보고에 기록 | 브랜치 `1016_CUSUM_Window_4ETF_20ETF` 를 `origin` (nanahyun3/R2H) 에 일반 push (force 금지) 하고 `git ls-remote origin refs/heads/1016_CUSUM_Window_4ETF_20ETF` 의 SHA 를 로컬 HEAD 와 대조한다. 이 문서는 그 커밋 안에 있으므로 SHA 는 여기에 적지 않는다 |

## 8. 재현

```bash
R=/home/sieg/projects-wsl/hongik_univ_26_2/SA/1012_Annual_SVR–GARCH-CUSUM/R2H   # R2H .venv 위치
cd SA/1016/R2H_CUSUM_Window_Study
$R/.venv/bin/python scripts/t13_build_notebooks.py --write     # 노트북 생성 (출력 비움)
env -u VIRTUAL_ENV $R/.venv/bin/python scripts/run_t13_notebooks.py   # 03→04 새 커널 실행, 약 3분 40초
PYTHONPATH=$PWD/src $R/.venv/bin/python -m pytest -q tests      # 156 passed
```

- 환경은 Python 3.12.3 · numpy 2.5.4 · pandas 3.0.6 · scikit-learn 1.9.1 이다 (노트북 첫 셀 assert).
- `data` 는 원본 R2H `data/raw` 로의 로컬 심링크다 (Git 제외). T12 일별 cache 는 `T12_FROZEN_ROOT` (기본값: 옆 작업트리 `R2H_T12_Final`) 에서 읽는다.
- 원자료와 일별 잔차는 가격을 역산할 수 있어 배포하지 않는다.

## 9. 남은 후속 연구 (별도 세션에서 설계)

- **다중 기간 가격 상승 검정** (1·3·7·14 거래일): 분산 CUSUM 이 아닌 평균·방향 통계량이 필요하다. 독립 가격 상승 라벨과 허용 시차를 먼저 사전 등록한다.
- **분산 변화**: 정규화 τ̂ 흡수를 피하는 통계량(예: 비정규화 대비, 장기분산 보정)과 이른 공통 시작일 설계로 짧은 지평 검출력을 다시 잰다. 이번 규칙과는 버전을 분리한다.
- **공통 구간 연구**: 노출 군집(KOSPI200 4종, 미국 주식 2종, T12 감사 9개 군집) 단위의 동시 경보와 원형 이동 귀무 (계약 §5).
- **CNN 인계**: 후보 메타데이터만 넘긴다. 정답 라벨은 독립 절차로 만든다 ([`CUSUM_CNN_후보구간_인계계약.md`](CUSUM_CNN_후보구간_인계계약.md)).

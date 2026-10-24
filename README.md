# R2H
주가 급등 국면 포착 에이전트 (2026.9~2027.6, 홍익대학교 졸업 프로젝트)

---

## KODEX 200 급변 구간 데이터셋 — 수집 · 클리닝 · 정제

KODEX 200 ETF(069500) 일봉을 수집해 클리닝하고, **급변 구간**(20일 변동성이 60일 변동성을 넘는 구간)을 사건 단위로 잘라
오토인코더 학습용 데이터셋 3종으로 정제했다. 이 브랜치는 그 결과 데이터와, 같은 결과를 다시 만들어 내는 실행 노트북을 담는다.

| 항목 | 값 |
|---|---|
| 종목 | KODEX 200 (`069500`) |
| 출처 | FinanceDataReader 0.9.202 단일 출처 (다른 출처와 병합하지 않음) |
| 수집 기간 | 2017-01-02 ~ 2026-10-23 · **2,403 거래일** (2017–2018 은 변동성 계산용 워밍업 487일, 분석 1,916일) |
| 수집 시각 | 2026-10-24 15:32 KST |
| 급변 사건 | 전체 80개 → 표본 **64개 · 891 거래일** (2019 이후 시작, 시작·끝 모두 관측된 사건) |
| 정상 비교 구간 | 사건마다 같은 길이의 비급변 구간 — 57/64 매칭 · 599 거래일 |
| 데이터셋 | Dataset 1 (5 피처) · Dataset 2 (7 피처) · Dataset 3 (5 피처) |
| 학습 분할 · 표준화 | **적용하지 않음** — 모델 설계와 함께 정한다 |

---

## 1. 폴더 구조

```
README.md
data/raw/
  069500_fdr_raw.parquet      수집 원본 스냅샷 (재실행 입력, SHA-256 264b1629…b642)
  069500_fdr_raw.json         수집 메타 — 요청 파라미터 · 수집 시각 · 라이브러리 버전 · 시도 기록 · SHA-256
outputs/
  01_dataset_1_daily.ipynb    수집 · 클리닝 · 급변 구간 · 정상 구간 · Dataset 1   (실행 결과 · 그림 포함)
  02_dataset_2_historical.ipynb   Dataset 2 — 변동성 · SVR–GARCH 예측분산 · CUSUM · Page
  03_dataset_3_changes.ipynb  Dataset 3 — 변화량 피처
  *.csv                       결과 데이터 10개 (아래 2절)
  quality/                    클리닝 보고서 · 검증 결과 (아래 4절)
```

---

## 2. 결과 데이터 (`outputs/*.csv`)

| 파일 | 행 | 내용 |
|---|---|---|
| `069500_fdr_raw.csv` | 2,403 | 수집 원본 그대로 + 메타 컬럼 (`source, collected_at, source_version, price_adjustment_policy`) |
| `069500_daily_clean.csv` | 2,403 | 클리닝 결과. `ticker, date, open, high, low, close, volume, change_source, is_warmup` |
| `069500_regime_events.csv` | 80 | 급변 사건 표 — `event_id, start_date, end_date, cross_down_date, duration_days, event_status, in_main_sample` 등 |
| `normal_reference_windows.csv` | 64 | 사건별 정상 비교 구간 — `ref_id, matched_event_id, start_date, end_date, duration_days, matched, seed` |
| `dataset_1_event_rows.csv` | 891 | Dataset 1 — 사건 날짜별 피처 원값 |
| `dataset_1_normal_reference.csv` | 599 | Dataset 1 — 정상 구간 날짜별 피처 원값 |
| `dataset_2_event_rows.csv` | 891 | Dataset 2 — 사건 날짜별 피처 원값 + 메타 |
| `dataset_2_normal_reference.csv` | 599 | Dataset 2 — 정상 구간 |
| `dataset_3_event_rows.csv` | 891 | Dataset 3 — 사건 날짜별 피처 원값 + `missing_reason` |
| `dataset_3_normal_reference.csv` | 599 | Dataset 3 — 정상 구간 |

- 행 수는 헤더 제외. 사건 행 식별 컬럼 `event_id, ticker, date, day_index` · 정상 구간 행 `ref_id, matched_event_id, ticker, date, day_index`
- `event_id = 069500_<시작 YYYYMMDD>_<끝 YYYYMMDD>` — 같은 원천·정의면 항상 같은 ID
- 세 데이터셋은 `event_id · date · day_index` 가 완전히 같다 → 같은 사건을 다른 피처 묶음으로 본 것
- 단위: 비율은 소수 (0.01 = 1%). `predicted_variance` 는 %² (r = 100·ln 수익률 기준)

### 데이터셋 3종

| 데이터셋 | 무엇을 담나 | 학습 피처 | 상태 |
|---|---|---|---|
| **Dataset 1** 당일·직전일 | 가격·거래량 원값 | `close`, `return_1d`, `gap_1d`, `daily_range`, `volume` | **TRAIN_READY** |
| **Dataset 2** 과거 조건부 | 과거 정보만으로 계산한 변동성·통계량 | `volatility_10d`, `volatility_120d`, `predicted_variance`, `raw_cusum_60d`, `svr_cusum_60d`, `svr_cusum_120d`, `x1_page_down` | **PARTIAL** (8개 중 `page_down` 기각) |
| **Dataset 3** 변화량 | 가격 수준 없이 변화량만 | `return_1d`, `gap_1d`, `daily_range`, `range_change_1d`, `volume_change_1d` | **TRAIN_READY** |

피처 정의

| 피처 | 식 | 정보 시점 |
|---|---|---|
| `return_1d` | close_t / close_{t−1} − 1 | t 종가 |
| `gap_1d` | open_t / close_{t−1} − 1 (사건 첫날도 실제 직전 거래일 종가) | t 시가 |
| `daily_range` | (high_t − low_t) / close_t | t 종가 |
| `range_change_1d` | daily_range_t − daily_range_{t−1} | t 종가 |
| `volume_change_1d` | volume_t / volume_{t−1} − 1 (직전 거래량 0 이면 결측 + 사유) | t 종가 |
| `volatility_10d` · `_120d` | 최근 10 · 120개 로그수익률 표준편차(ddof=1) × √252 | t 종가 |
| `predicted_variance` | SVR–GARCH 예측분산 σ̂²_t — 매년 첫 거래일에 그 이전 수익률만으로 재적합 (2018–2026, 9회) | **t−1 종가** |
| `raw_cusum_60d` | 원 수익률의 60일 이동 CUSUM-of-squares | t 종가 |
| `svr_cusum_60d` · `_120d` | 표준화 잔차 e 의 60 · 120일 이동 CUSUM-of-squares | t 종가 |
| `page_down` | 분산 감소(λ = 0.5) 로그우도비 누적 (원값만 보존 — 학습 피처에서 기각) | t 종가 |
| `x1_page_down` | e 를 과거 [t−252, t−61] 잔차 척도로 나눈 뒤 같은 Page 누적 | t 종가 |

Dataset 2 메타 컬럼 `model_fit_id, days_since_refit, forecast_ceiling, cos60_mixed_fit, cos120_mixed_fit` 은 학습 입력이 아니라 해석용이다.
SVR–GARCH 는 Lee·Kim·Lee (2020) 방식을 따른다. 상세 수식은 노트북 02 의 7절.

---

## 3. 클리닝

원칙: **검사만 하고, 근거 없는 수정은 하지 않는다.** 결과 — 2,403행 → 2,403행, **값 수정 0건**.

| 검사 | 결과 |
|---|---|
| 숫자 변환 불가 값 · 결측 | 모든 컬럼 0 |
| 중복 거래일 (동일 · 값 충돌) | 0 · 0 |
| 가격 관계 (low ≤ open, close ≤ high) 위반 | 0 |
| 0 이하 가격 · 음수 거래량 · 거래량 0 | 0 · 0 · 0 |
| 조정 기준 일관성 (O/H/L/C 가 같은 조정 기준인가) | 같음 — 연도별 종가가 [저가, 고가] 밖인 비율 0%, 시가/지수 시가와 종가/지수 종가 비율이 같은 추세 (`quality/adjustment_basis_by_year.csv`) |
| 극단 관측 (로그수익률 전체 표준화 \|z\| > 5) | 14건 — 제거하지 않고 목록만 기록 (최대 2026-07-31 +0.217) |
| 휴장일 행 생성 | 하지 않음 |

- 자료형: 가격·거래량을 float64 로 통일 (원본은 정수 — 값은 같음), `ticker` 는 앞자리 0 보존을 위해 문자열
- 보조 출처(pykrx)는 조회 결과가 0행이라 대조하지 못했다. 두 출처를 섞지 않는다
- 상세: `outputs/quality/cleaning_report.json`

### 급변 구간 정의

- `lr_t = ln(close_t / close_{t−1})`, `vol20 · vol60` = 정확히 20 · 60개 수익률의 표준편차(ddof=1) × √252
- 급변 상태 `S_t = vol20_t > vol60_t` (같으면 급변 아님, 두 변동성이 모두 있는 날만 판정)
- 시작일 = 상태가 False → True 로 바뀐 날 · 끝 = 다시 False 가 되기 직전 날
- `event_status`: complete 79 · left_censored 1 · right_censored 0
- 표본 = complete 이고 2019-01-01 이후 시작 → **64개**. 길이 1–63일 (중앙값 7), 1–3일 사건 25개 (39%)
- 정상 비교 구간: 사건마다 같은 길이의, 모든 날이 비급변인 연속 구간을 시드 `20261024` 로 무작위 선택. 사건·다른 정상 구간과 겹치지 않음. 긴 사건(20–63일) 7개는 맞는 구간이 없어 미매칭

---

## 4. 검증

### 노트북 안 자동 검사 (`outputs/quality/`)

| 파일 | 내용 |
|---|---|
| `dataset_1_validation.json` | 15개 항목 FAIL 0 (분할 관련 1개는 N/A) — 원천 재계산 차 0, 미래 값 변경 시 과거 피처 불변, 정상 구간이 사건과 겹치지 않음 등 |
| `dataset_2_validation.json` | SVR 학습 끝 < 예측 시작 (9회 모두), 미래 수익률을 바꿔도 이전 예측분산·CUSUM·Page 불변, CUSUM·Page 손계산 대조 통과. FAIL 은 `feature_count` (7/8) 하나 |
| `dataset_3_validation.json` | 가격 수준 컬럼 없음, 원천 재계산 차 0, Dataset 1 공통 피처와 값 일치 |
| `cross_dataset_validation.json` | 세 데이터셋 사건 64개 · ID · 날짜 동일 |
| `dataset_2_similarity_gate.csv` | Dataset 2 피처를 독립 참조 구현과 비교한 상관 (2021–2025, 1,225일). 0.9 이상 등록 — `page_down` 0.813 으로 기각 |
| `svr_fit_log.csv` | SVR 연간 재적합 9회의 학습 기간 · 선택 (C, γ², ε) · 검증 MAE |

### 독립 재구현 대조

노트북 코드를 쓰지 않고 원천 OHLCV 에서 정의만 보고 따로 구현해 모든 저장값과 배열을 대조했다. 대조용 스크립트는 이 브랜치에 포함하지 않았고 결과만 싣는다 (5절 재현 범위 밖).

| 확인한 것 | 결과 |
|---|---|
| 재계산 41개 항목 | 값이 다른 항목 **0** (자료형 차이 1건 — 정수 → 실수, 값 동일) |
| 급변 상태 · 사건 표 | 2,403일 · 80개 사건 전부 일치 |
| Dataset 1 · 3 배열 | float32 상대 오차 ≤ 5.9×10⁻⁸ · 마스크 · 패딩 · 사건 순서 일치 |
| Dataset 2 피처 (SVR 재적합 9회 포함) | 최대 차이 ≤ 3.3×10⁻¹³ · 9개 연도의 하이퍼파라미터 동일 |
| **미래 정보 누출** | 컷오프 이후 가격을 **삭제**한 자료로 Dataset 2 를 다시 계산 — 2020-03-31 · 2022-06-30 · 2025-06-30 세 곳 모두 이전 값 차이 ≤ 3.3×10⁻¹³ → 누출 없음 |

**수치 민감성**: 로그수익률을 `log(c_t/c_{t−1})` 로 구하느냐 `log c_t − log c_{t−1}` 로 구하느냐(부동소수점 차이 10⁻¹⁶)만으로
SVR 예측분산이 최대 0.0035 (%², 사건일 평균의 약 0.3%) 달라진다. 하이퍼파라미터 선택은 같다. Dataset 2 로 학습한 결과는
이 정도 입력 흔들림에 결론이 바뀌지 않는지 확인해야 한다.

---

## 5. 재현

### 바로 확인

```bash
sha256sum outputs/*.csv
```

| 파일 | SHA-256 |
|---|---|
| `069500_fdr_raw.csv` | `bd24b93c9c0324a56879b5a49dede920b2df9ea48e60ace60b049aa115806486` |
| `069500_daily_clean.csv` | `acf52fcd3b7a640b431747de0be252f937ec24cac8ed26c102f71870f617ec00` |
| `069500_regime_events.csv` | `8256650ea477b3014303f7444cfcf03635bf9c86d9f645bcef265cd9d7860b8c` |
| `normal_reference_windows.csv` | `97e0c339b5815b4b5fd25d58ed6cb38abffc030a069c0ad9ef51e79bec043335` |
| `dataset_1_event_rows.csv` | `9ec6140ce48316414899d0b1eb9fe512241bb9adf630628ab0e9be2b2b270950` |
| `dataset_1_normal_reference.csv` | `6b2dddcbaefc24d32a3e6b0e531f6cbd0df7d607f0ae2646246f47d786014e95` |
| `dataset_2_event_rows.csv` | `fdbae8a6d78d2f24bf0a12cbd4af48b98ffdd8eb54fec1d7748da9d63a3ff0fd` |
| `dataset_2_normal_reference.csv` | `636cfee45030f1d70d744b4a8dd9f704d62493fb67bd466ee9d4806fc0c7d288` |
| `dataset_3_event_rows.csv` | `f691f95437a516441bdd97acb278a93ae8217b7d984393104d127b1a7a984eb3` |
| `dataset_3_normal_reference.csv` | `9e16102e54526dbce97d869cf992a8c115160f26903cb86f2c54cb3c2a2d746a` |

### 노트북으로 다시 만들기

```bash
pip install numpy==2.4.6 pandas==3.0.3 pyarrow==24.0.0 scikit-learn==1.9.0 \
            finance-datareader==0.9.202 pykrx==1.0.51 matplotlib==3.11.0 \
            nbconvert nbclient nbformat ipykernel
cd outputs
for nb in 01_dataset_1_daily 02_dataset_2_historical 03_dataset_3_changes; do
  jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=1200 $nb.ipynb
done
```

- 그림의 한글 글꼴은 NanumSquare · Noto Sans CJK KR 순으로 찾고, 없으면 DejaVu Sans 로 대체된다 (데이터 결과에는 영향 없음)
- 순서 01 → 02 → 03 고정. 노트북은 `outputs/` 의 상위 폴더를 루트로 보고 `data/` 아래에 결과를 쓴다
- 01 은 `data/raw/069500_fdr_raw.parquet` 스냅샷이 있으면 API 를 부르지 않고 그대로 쓴다 (스냅샷 SHA-256 을 메타와 대조). 스냅샷을 지우면 FDR 에서 새로 받는데, 제공처의 소급 조정으로 값이 달라질 수 있다
- 02 의 유사성 게이트는 비공개 참조 파일과 비교한다. 파일이 없으면 노트북에 적어 둔 최초 실행의 게이트 결과(`RECORDED_GATE`)를 그대로 적용하므로 등록 · 기각 판정과 학습 배열이 같다. 파일이 있으면 환경 변수 `D2_REFERENCE_FEATURES` 로 경로를 주며, 이때는 직접 계산한 판정이 기록값과 같은지 assert 한다
- 재실행이 만드는 것: `data/clean`, `data/events`, `data/processed/dataset_N` (위 CSV 와 parquet), `data/training/dataset_N` (학습 배열 `features.npz` · `normal_reference_features.npz`, `feature_columns.json`, `scaler.json`, `split_manifest.json`, `dataset_manifest.json`), `reports/figures`, `data/raw/069500_fdr_raw.csv` · `069500_pykrx_check.json` — 모두 `.gitignore` 대상

**공개 전 재현 확인 (2026-10-24)**: 이 브랜치와 같은 구조의 빈 폴더에서 새 커널로 01 → 02 → 03 을 실행했다 (12초 · 15초 · 5초).
참조 파일이 **있는** 조건과 **없는** 조건 모두에서

- 생성된 CSV 20개가 위 결과와 **바이트 단위로 같고**
- 학습 배열 6개(`features.npz` · `normal_reference_features.npz` × 3)의 모든 배열이 같으며
- `dataset_manifest.json` 의 출력 내용 해시가 같았다

KS200 지수와의 조정 기준 비교는 최초 수집 실행에서만 한다 (재실행은 API 를 부르지 않음). 그 결과는 `quality/adjustment_basis_by_year.csv` 에 있다.

실행 환경: Python 3.12.3 · numpy 2.4.6 · pandas 3.0.3 · scikit-learn 1.9.0 · FinanceDataReader 0.9.202 · matplotlib 3.11.0

### 학습 배열 형식 (재실행 후 `data/training/dataset_N/features.npz`)

| 키 | 모양 | 내용 |
|---|---|---|
| `X` | (64, 63, F) float32 | `X[사건, 날, 피처]` 원값 — 결측·패딩 위치는 0 |
| `obs_mask` | (64, 63) bool | 실제 거래일 위치 (패딩 아님) |
| `missing_mask` | (64, 63, F) bool | 피처 결측 위치 |
| `lengths` · `event_ids` | (64,) | 사건 길이 · ID (event_id 정렬 순서, 세 데이터셋 동일) |

F = 5 · 7 · 5. 정상 구간 배열은 (57, 61, F). 실제 값 위치 = `obs_mask[..., None] & ~missing_mask`.

---

## 6. 학습 전에 알아 둘 데이터 성질

검증 실패는 아니지만, 모델이 지름길을 배우거나 평가가 부풀 수 있는 지점이다.

| # | 성질 | 수치 | 권고 |
|---|---|---|---|
| P1 | 사건 길이가 경계 정보를 드러냄 | 길이 1–63일, 관측 마스크 길이 = 사건 길이 | 길이만 넣은 대조 모델 · 복원 오차를 길이 구간별로 보고 |
| P2 | 정상 구간 대부분이 급변 사건 옆 | 57개 중 40개가 사건과 5거래일 이내 | 사건과 k일 이상 떨어진 정상 구간만으로 민감도 분석 |
| P3 | Dataset 1 의 가격 수준 · 거래량 원값 | 왜도 close 2.38 · volume 2.59 · daily_range 3.60 | 학습 분할에서만 표준화 · Dataset 3 (가격 수준 없음)과 비교 |
| P4 | 예측 고정일 (같은 예측분산 반복) | 2019 이후 33일 · 사건 행 891 중 29 (`forecast_ceiling`) | 포함 / 제외 결과 비교 |
| P5 | 유사성 게이트는 척도를 보지 않음 | `x1_page_down` 상관 0.975 지만 평균은 참조 값의 0.569 배 | 참조 값과 수치를 섞어 쓰지 않음 |

### 분할 제안 (적용하지 않음)

사건 시작 연도 기준 2019–2023 학습 / 2024 검증 / 2025 시험 / 2026 관찰. 연도 경계에 걸친 사건 2개는 시작 연도로 통째 배정.

| 분할 | 사건 | 사건 일수 | 4일 이상 사건 | 정상 구간 (매칭) |
|---|---|---|---|---|
| 학습 | 41 | 552 | 25 | 37 |
| 검증 | 13 | 110 | 7 | 13 |
| 시험 | 7 | 122 | 4 | 5 |
| 관찰 | 3 | 107 | 3 | 2 |

시험 사건이 7개뿐이므로 결과는 사건 단위 부트스트랩 구간과 함께 낸다. 2019–2025 는 이미 탐색 분석에 쓰인 기간이라 2026-10-24 이후 자료만 맹검 평가로 볼 수 있다.

## 7. 한계

- 단일 출처다. 2026 년 극단 관측(07-31 +0.217 등)을 제2 출처로 확인하지 못했다
- `page_down` 기각 원인(예측분산 척도 vs SVR 학습 이력 시작 차이)은 분리하지 않았다
- SVR ε 가 9회 모두 후보 하한 0.1 로 선택됐다 — 후보 범위 민감도는 평가하지 않았다
- 2021 적합의 검증 MAE 1.87 은 다른 해(0.14–0.52)보다 크다 (2020 급변이 검증 블록에 들어감)

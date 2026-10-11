# 1012 인계 — 2조 ↔ 4조 공통작업 추적

워크스트림 ID 는 팀 Notion 마스터 DB 의 W 번호를 따른다 (담당자 배정은 Notion 에서 관리, 이 공개 저장소에는 적지 않는다).

## 일정과 이 저장소에서의 산출물

| 기한 | 항목 | 이 브랜치 상태 | 다음 작업 (issue 로 추적 권장) |
|---|---|---|---|
| 10/12 | 교수·4조 합동 미팅 | 미팅 결과는 이 저장소에 아직 없음 (가상 기입 금지) | D-01 ~ D-03 결정 반영 → 계약 v0.2 |
| 10/19 | 1차 중간발표 | 연구 근거 요약 `research/` · 계약 v0.1 | 발표용 수치는 `research/REPRODUCTION_STATUS.md` 의 MATCH 항목만 인용 |
| 10/26 | 공통 코드 확정 (2조·4조) — 평가 틀·결과 스키마 | `evaluation/` · `detection/schema.py` 제안판 | 4조 BOCPD 를 `Detector` 로 감싸 합성 예제에서 교차 실행 |
| 11/2 | 시장 지표 코드 4조 전달 (수익률·MA·변동성·거래량) | `features/price.py` (테스트·누수 검사 포함) | 4조 입력 형식 확인 후 필요한 feature 추가 |
| 11/9 | 교차검증 보고 · DB증권 중간점검 | — | 승인된 Ground Truth 로 walk-forward 평가 |

## 연구 근거를 한 번에 보려면

[`notebooks/R2H_1012_research_synthesis.ipynb`](../../notebooks/R2H_1012_research_synthesis.ipynb) — EDA·Track A·Track B 결과 해석과 그림 10장 (SA_ETF 공개 결과표를 SHA·sha256 로 고정해 읽음), R2H 계약 합성 시연.

T11 (SVR–GARCH CUSUM × ETF 20종, 70/30 · 이동창 20/30/60/120/252 · Track A·EDA 대비): [`notebooks/R2H_T11_svr_garch_cusum_etf.ipynb`](../../notebooks/R2H_T11_svr_garch_cusum_etf.ipynb) · [`research/svr_garch_cusum_etf/README.md`](../../research/svr_garch_cusum_etf/README.md) — W04 판단 근거.

## 재사용 방법 (요약)

- 새 탐지기: `Detector` 프로토콜 구현 → `build_signal_frame(...)` 로 출력 → `match_alarms` / `event_metrics`.
- 사후 방법(PELT, 사후 CUSUM): `mode="posthoc"` — 온라인 지표에 넣으면 오류가 난다 (의도된 동작).
- 상관 사건 · 가격 사건 비교: `features.correlation` + `evaluation.null_tests` (Track A 방법). 같은 날 큰 수익률의 기계적 중복을 먼저 제거할 것.

## 보존해야 할 정의 차이 (Track A → 후속 비교)

1. 수익률 = logdiff, DQ 변형 ID 를 명시 (`dq_trim_canonical`: 261240 2019-03-14·15 두 셀만 NaN).
2. 실시간 비교에는 `confirmed_at` / `available_until` 만. `candidate_at` 은 사후에야 알 수 있다.
3. KOSPI200 exposure group (069500·102110·122630·114800) 은 사건 1건으로 센다.
4. 사후·look-ahead 라벨 (P4 누적, 전체표본 분위수) 은 평가 전용.

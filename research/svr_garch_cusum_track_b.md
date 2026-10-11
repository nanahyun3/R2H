# Track B — Lee, Kim & Lee (2020) Hybrid SVR–GARCH CUSUM 재현 감사

- 논문: Lee, S., Kim, C. K., & Lee, S. (2020). *Hybrid CUSUM Change Point Test for Time Series with Time-Varying Volatilities Based on
  Support Vector Regression.* Entropy 22(5), 578. [doi:10.3390/e22050578](https://doi.org/10.3390/e22050578) (PDF 는 저장소에 넣지 않음)
- 원본: SA_ETF [`research/track-b-paper2020@031157d`](https://github.com/Siegfriex/SA_ETF/tree/research/track-b-paper2020/research/track_b_paper2020) (로컬 패키지를 정리해 공개, 반복별 원시 결과·원시 시계열 제외). R2H 에는 CUSUM-of-squares 검정 모듈만 바이트 동일로 이식 (`src/r2h/detection/paper2020_cusum.py`)
- 상태: **METHOD_FIDELITY_UNRESOLVED** — 감사는 종결, 원문 수치는 재현되지 않음

## 재실행 확인 (2026-10-11)

| 항목 | 결과 |
|---|---|
| pytest | 84 passed (golden·수학 17 + 계약 8 + 경계·누출·DGP 59) |
| 실증 3종 (S&P500 2012–2016, KOSPI 2012–2019, KRW/USD 2012–2016; 원문 Investing.com → Yahoo 대체 **SOURCE_SUBSTITUTED**) | `empirical_summary.json` 바이트 동일 |
| Monte Carlo chunk 재생성 (n=500, 9 chunk · 400 반복) | 통계량·기각·변화점 위치 원본과 완전 일치 (seed 파생 결정적) |
| 원문 값이 재현 Wilson 95% CI 안에 든 셀 (n=500, 45행) | clip 1/45 · raise 9/45 · recursive 10/45 (jsonl 에서 독립 재계산) |

## 원문 대비

| series | 원문 T / 날짜 | 재현 (관측 proxy 정책 A) | 재현 (재귀 예측 정책 B) |
|---|---|---|---|
| S&P 500 | 2.4751 / 2015-08-18 | 0.7540 비기각 | 1.0963 비기각 (날짜는 2015-08-18 일치) |
| KOSPI | 1.5081 / 2018-01-22 | 0.7910 비기각 | 1.1071 비기각 |
| KRW/USD | 4.2754 / 2014-09-26 | 0.7939 비기각 | 1.0238 비기각 |

임계값 c = 1.3397 (5%). 원문 통계량 3개는 모두 기각, 재현은 두 정책 모두 비기각.

## 해석 (원 감사 보고서 기재 — 이번 감사에서 재계산하지 않은 수치는 † 표시)

- 원문이 명시하지 않은 **테스트 구간 분산 lag 정책**(관측 proxy A vs 재귀 예측 B)이 결과를 크게 바꾼다 (같은 경로 McNemar: size p=7.6e-6†, power p=3.6e-152†).
  그러나 **어느 정책도 원문 Tables 를 재현하지 못한다** — 남은 차이의 원인은 미해결.
- 정책 A = ASSUMPTION(문자적 연장), B = SENSITIVITY. 원문 수치에 가까운 쪽을 사후에 고르지 않았다.
- 코드 결함 1건 발견·수정† (Table 6 TGARCH→AGARCH ω=1 의 post β 0.4 → 원문 0.3). 원문 자체 이상: Table 6 두 행이 Table 4 와 동일.

## R2H 에서의 사용 제한

`PosthocCUSUMSquares` 는 표본 전체를 보는 **사후 검정**이다 (`mode="posthoc"`). 온라인 경보가 아니며, ETF 에 적용한 결과를
"원문 방법의 결과" 라고 부르지 않는다. 쓸 때는 정책 A·B 를 병기하는 민감도 분석으로만 쓴다. SVR–GARCH 적합 단계는 이식하지 않았다.

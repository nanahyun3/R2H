# T11 · SVR–GARCH CUSUM 을 ETF 20종에 적용 — 설계 · 결과 · 재현

> **지위**: Lee·Kim·Lee (2020) Hybrid SVR–GARCH CUSUM 의 **ETF 적용 민감도 분석**이다. 원 논문 수치는 재현되지 않았으므로
> (Track B, METHOD_FIDELITY_UNRESOLVED) 이 결과를 "원문 방법의 결과" 라고 부르지 않는다. 실제 매매·탐지 성능 수치가 아니다.

| 바로 가기 | |
|---|---|
| 노트북 (그림 16장·해석) | [`notebooks/R2H_T11_svr_garch_cusum_etf.ipynb`](../../notebooks/R2H_T11_svr_garch_cusum_etf.ipynb) · [nbviewer](https://nbviewer.org/github/nanahyun3/R2H/blob/1012/notebooks/R2H_T11_svr_garch_cusum_etf.ipynb) |
| 오토런 | [`scripts/run_svr_garch_cusum_etf.py`](../../scripts/run_svr_garch_cusum_etf.py) → [`src/r2h/svrgarch_etf/pipeline.py`](../../src/r2h/svrgarch_etf/pipeline.py) |
| 결과표 (정본) | [`results/`](results) — `run_manifest.json` 에 출력 해시 |
| 그림 | [`docs/figures/svrgarch/`](../../docs/figures/svrgarch) |

## 1. 사전 고정 결정 (첫 실행 전)

| # | 결정 |
|---|---|
| 분할 | 시간순 **앞 70% 적합** (그 안 70% 학습 / 30% 검증, grid 27점, 검증 MAE 선택) / **뒤 30% 검정**. 원문(전체 50/50 → 적합구간 내부 70/30)과 다른 T11 프로토콜 |
| 잔차 | 정책 A (관측 proxy 입력, 1차) · 정책 B (재귀 입력, 민감도) · 기준선 r/σ₆₀ (모형 없음, Track A P1 점수) |
| 비양수 σ̂² | 그날 잔차만 NaN (실제 0건) |
| 이동창 | w ∈ {20, 30, 60, 120, 252(연)} · 창 안 유효 관측 ≥ 0.9w · 경보 사이 공백 ≤ 5일이면 한 에피소드 |
| 임계값 | 1차 = ETF 별 부트스트랩 95% (적합 구간 잔차 iid 재표집 5,000회) · 참고 = iid N(0,1) MC 20,000회 · 점근 1.3397 |
| 비교 사건 | P1 (r/σ≥3) · **P4 h5/h10/h20 = "누적수익률 절대값 경계"** (Track A 의 유일한 누적 정의, 양방향) · EDA 공통충격일 · C3 상관 부호전환 (확정일) · 고변동 국면 진입 (expanding 75% 분위, 과거만) |
| 1차 가족 | 정책 A · w=60 · 검정 구간 · {P1, 공통충격} · ±10일 — KOSPI200 그룹 4종은 1건(069500), 검정 불가 행은 p=1 → **34 검정**. BH 는 이 안에서만, 나머지는 탐색 |
| 검정 구간 경계 | 창 전체가 검정 구간 안에 들어간 날(분할일 + w − 1)부터. 창이 걸친 경보는 `boundary` |
| 시점 | 경보일 t (실시간) / 창 안 k̂ (사후) 구분 · C3 확정일 · P4 사후 확정일 |
| seed | 20261012 (MC·부트스트랩·원형 이동 B=2,000) |

## 2. 데이터 카드

| 항목 | 내용 |
|---|---|
| 대상 | 국내 상장 ETF 20종 (목록·이름: [`reference_close_sha256.csv`](reference_close_sha256.csv)) |
| 기간 | 2019-01-02 ~ 2026-10-02 종가 → 공통 거래일 1,902 수익률 (100·Δlog). 261240 은 DQ 2일 제외 |
| 출처 | [FinanceDataReader](https://github.com/FinanceData/FinanceDataReader) 0.9.202 (KRX ETF 일봉). 원시 시세는 저장소에 넣지 않는다 |
| 버전 확인 | `Date,Close` 원문의 sha256 (종가 해시) 20종을 기준과 대조 → 다르면 `DataVersionDiffers` 로 멈춤 (FDR 은 분배를 소급 조정하므로 나중에 받으면 달라질 수 있다) |
| 비교 사건 | SA_ETF [`codex/r2h-track-a@a3f9e9b`](https://github.com/Siegfriex/SA_ETF/tree/codex/r2h-track-a) 의 `price_event_candidates.csv`·`correlation_event_candidates.csv` (sha256 고정, 실행 시 검증) |
| 커밋한 파생물 | 적합 요약 · 사후 검정 · 임계값 · 경보 에피소드 · 귀무 경보율 · 근접 지표 · 흐름 겹침 · 연도 블록 · 이동창 통계량 (일별 수익률·잔차는 수익률 복원이 가능하므로 커밋하지 않음 — `outputs/cache/t11_state.npz`) |

## 3. 방법 (수식)

$$\tilde\sigma^2_t=\tfrac15\sum_{j=0}^{4}y^2_{t-j},\qquad \hat\sigma^2_t=\hat g\big(y^2_{t-1},\tilde\sigma^2_{t-1}\big)\ (\varepsilon\text{-SVR, RBF}),\qquad \hat\varepsilon_t=y_t/\hat\sigma_t$$

$$T_t(w)=\max_{1\le k\le n}\frac{\big|\sum_{s\le k}\hat\varepsilon_s^2-\tfrac kn\sum_{s\le n}\hat\varepsilon_s^2\big|}{\sqrt n\,\hat\tau},\quad \hat\tau^2=\overline{\hat\varepsilon^4}-\big(\overline{\hat\varepsilon^2}\big)^2,\quad \text{창}=[t-w+1,t],\ \text{경보}\Leftrightarrow T_t(w)\ge c_w$$

근접 귀무: 경보 에피소드 시작일 집합 C 와 사건 집합 P 에 대해 $T=\#\{c:\exists p,|p-c|\le L\}$, P 를 원형 이동 B=2,000 회 → $p=(1+\#\{T^*\ge T\})/(B+1)$.

## 4. 결과 요약 (결과표에서 계산한 값)

| 질문 | 결과 |
|---|---|
| 사후 검정 (검정 구간 30%) 기각 | 정책 A **2/20** · 정책 B **9/20** · 기준선 **1/20**. k̂ 는 정책 A 에서 2026-01 에 8종 (알려진 고변동 국면의 시작) |
| 이동창 경보율 vs iid 기준값 (w=60, 연간 에피소드, ETF 평균) | 정책 A **0.39 vs 1.71** (초과 0/20) · 기준선 **3.82 vs 1.70** (20/20 초과). 기준값은 iid 재표집이라 변동성 군집 아래의 오탐 보정은 아님 |
| 창 길이 | 창이 길수록 경보↓·임계값↑. w=20 유한표본 95% 임계값 1.14–1.18 < 점근 1.3397 |
| 사건 근접 (23,442 검정, 탐색) | p<0.05 비율 **5.9%**. P1 사건일 제거 시 기준선 8.9%→4.6%, 정책 A 6.6%→2.6%. 2026 제외 검정 구간 6.2% · 3.5%. P1 은 기준선과 같은 점수라 기준선 근접은 일부 기계적 |
| 1차 가족 (34 검정) | p<0.05 2개 (261220 P1 · 132030 공통충격), **최소 q = 0.57** → 우연 이상 증거 없음 |
| 흐름 겹침 (w=60) | 정책 A 경보 59개: P1 59% · P4 53% · 공통충격 46% · 고변동 49% · C3 10% — 충격 자체에 반응 · 기준선 577개: 069500 동시 경보 46% (시장 변동성 국면) |
| 채권↔KOSPI | 148070 정책 A 경보 w=60·120 0건 · 기준선 vs C3 p=0.23 · 153130 정책 A 근접(P1 p=0.007, C3 p=0.037)은 **in-sample 적합 구간에서만**, 검정 구간 경보 0건 |
| 연도 블록 | 기준선 기각: 2020 85% · 2026 55% (EDA 고변동 해와 일치) · 정책 A 는 2020·2022 5% 외 0% |

**적용 가능성**: 정책 A SVR–GARCH CUSUM 은 변동성 변화를 흡수해 급등 탐지기로 쓸 수 없다. 기준선 변동성 CUSUM 은 변동성 국면 요약에는 맞지만
방향이 없고, 급등 사건과의 겹침은 기계적 성분을 빼면 우연 수준이다. Track A 의 상관 전환(C3)·누적 경계(P4)와도 우연 이상 겹치지 않는다
— 셋은 서로 다른 것을 잰다. W04 의 다음 단계는 평균·방향 CUSUM 을 승인된 정답(D-01)으로 평가하는 것이다.

## 5. 재현

```bash
uv sync --extra dev --extra notebook --extra research
# 원시 시세: 이미 받은 파일이 있으면 ETF_RAW_DIR=<dir>, 없으면 FinanceDataReader 로 자동 수집 (종가 해시 검증)
uv run python scripts/run_svr_garch_cusum_etf.py            # 약 3분, results/ 갱신
uv run jupyter execute notebooks/R2H_T11_svr_garch_cusum_etf.ipynb
```

검증 기록 (2026-10-12, 로컬): 독립 검토(누수 없음 확인, 1차 가족 크기·KOSPI 그룹·검정 구간 경계·D3·salt 정정) 반영 후 오토런 독립 2회 결과표 9종 **바이트 동일** · 노트북 2회 실행 출력 27개·그림 16장 동일 ·
정책 A 전구간 경로가 원문 CARRY 검정 경로와 일치 (코드 assert) · 단위 테스트 10개 · 노트북 규칙 테스트 (모든 코드 줄 한국어 주석, 한글 폰트, 글리프 누락 0).
CI 는 원시 시세가 필요한 이 노트북을 실행하지 않는다 (단위 테스트·규칙 검사만).

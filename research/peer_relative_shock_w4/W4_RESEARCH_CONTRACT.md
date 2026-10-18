# W4 연구계약 — ETF 20종 Peer 상대 변동성 급변 구간 (W4-lock-1)

- 연구 ID: `t18_peer_relative_shock_w4` · 노트북 `09_ETF20종_Peer상대변동성_급변구간정의.ipynb`
- 기준 커밋: `534a122` (`1017_2_MultiAsset_Joint_CUSUM_W3`, 원격 HEAD 와 일치 확인 2026-10-18)
- 작업 브랜치: `research/w4_peer_relative_shock_regimes` (로컬 전용, push·병합은 사용자 승인 후)
- 설정 파일: `configs/t18_peer_shock_w4_v1.json` · Peer 매핑: `PEER_MAPPING_CONTRACT.md` + `results/peer_mapping.csv`
- 이 계약은 **ETF 변동성·분위·비율을 한 번도 계산하지 않은 상태에서** 커밋한다. 이후 임계값·Peer·17/17 규칙은 바꾸지 않는다.

## 1. 무엇을 — 그리고 하지 않는 것

**한다**: 관측 수익률과 연환산 변동성으로 기술적 급변 상태 라벨 A·B·AB 를 ETF·그룹·전체 단위로 계산하고, 17/17 공동 충족일을 연속 구간으로 묶는다.

**하지 않는다**: 통계적 구조변화 입증, 미래 급등 정답, 매매 신호, W1·W3 CUSUM 검정 적격성의 계승, W3 결과 재해석, 05–08 동결 산출물 수정, PDF·DOCX 제작.

## 2. 입력

| 항목 | 내용 |
|---|---|
| 평가 ETF | `exposure_groups.csv` 의 20종 (17 노출 그룹). 각 ETF 는 한 번만 평가 |
| 원자료 | `data/raw/*.csv` (FDR 0.9.202, 2019-01-02 ~ 2026-10-02, 1,903행). sha256 은 `data/raw/MANIFEST.csv` 와 대조 |
| Peer 참조 | `data/external/peer/*.csv` (같은 FDR 버전·같은 기간, Git 제외). sha256 은 `evidence/source_hashes.json` |
| 거래일 | 평가 20종의 공통 KRX 거래일 (1,903일). Peer 는 이 달력에 맞춘다. 없는 날은 결측 |
| 가격 | `Close` (FDR 분배 소급조정 추정 — 기존 EDA C-0012 DEC-3 과 동일). 결측 가격을 전일값으로 채우지 않는다 |

## 3. 변수 정의

- 수익률: `r(i,t) = 100·log(C(i,t)/C(i,t−1))` (일간 %)
- 연환산 변동성: `σ(i,t,q) = √252 · std(r(i,t−q+1..t), ddof=1)`, q ∈ {20, 60} (연환산 %). 창 안에 결측이 하나라도 있으면 결측.
  W2 는 `mean(r²)` (평균 0 가정·ddof 0)였다. W4 는 표본표준편차(평균 차감·ddof 1)다. 두 값을 비교할 때 이 차이를 분리해 보고한다.
- 배율 정규화: `σ_adj = σ / |m|`, m: 122630 = +2, 114800 = −1, 나머지 1. 일간 목표 배율 기준일 뿐 장기 배율을 보장하지 않는다.
- 과거 분위: 확장형 엄밀 과거 mid-rank (`r2h.multihorizon.core.midrank_past`, W2 와 동일). 당일 값은 기준집합에 넣지 않는다. 유효 과거 관측 252개 미만이면 `INSUFFICIENT_HISTORY` (NA).

## 4. A — 자기 과거 대비 고변동성

`U_A(i,t,q) = midrank_past(σ(i,·,q))`, `A = 1[U_A ≥ 0.90]`. 기준 부족·결측은 NA (0 이 아님). 0.90 은 라벨 정의를 위한 사전 선택값이며 유의수준이 아니다.

## 5. B — Peer 대비 양방향 상대 변동성 괴리

- `L(i,t,q) = log(σ_adj(i,t,q) / median_j∈P(i) σ_adj(j,t,q))`. 자기 자신 제외. P(i) 는 동결된 Peer 매핑.
- 그날 유효한 Peer 수가 Tier 1 은 1개 이상, Tier 2 는 2개 이상이어야 한다. 아니면 `PEER_INSUFFICIENT_ON_DATE` (NA). 유효 Peer 수와 구성을 기록한다.
- 분자 σ_adj = 0 → `ZERO_VOL_NUMERATOR`, Peer 중앙값 = 0 → `ZERO_VOL_DENOMINATOR`. epsilon 을 쓰지 않고 NA. 별도 영변동성 표를 만든다.
- `U_B = midrank_past(L)`, `B_UP = 1[U_B ≥ 0.95]`, `B_DOWN = 1[U_B ≤ 0.05]`, `B = B_UP ∨ B_DOWN`.
- B_DOWN 은 저변동성이 아니라 평소 상대 관계의 하방 이탈이다 (Peer 가 더 크게 움직였을 수 있다).

## 6. 그룹 상태 (17개)

- `KOSPI200_동일노출`: Core Pair 069500·102110.
  - `GROUP_A = A(069500) ∧ A(102110)`.
  - `GROUP_B`: `L_K200 = log(σ(069500)/σ(102110))` 의 확장형 과거 mid-rank 가 ≥ 0.95 또는 ≤ 0.05.
  - 122630·114800 은 배율 정규화 후 Core Pair 중앙값과 비교한 보조 진단만 하고 거부권이 없다.
- 나머지 16개 단일 ETF 그룹: 해당 ETF 의 A·B.
- `GROUP_AB = GROUP_A ∧ GROUP_B`.
- 논리는 3값(1·0·NA)이다. AND: 하나라도 0 이면 0, 모두 1 이면 1, 그 외 NA.

## 7. 전체 상태와 최종 라벨

- `GLOBAL_X(q,t) = AND_{g=1..17} GROUP_X(g,t,q)`, X ∈ {A, B, AB}. 17/17 만 1. 16/17 은 1 이 아니다.
  한 그룹이라도 NA 이고 0 인 그룹이 없으면 GLOBAL 은 NA (판정 불가).
- `FINAL_SHOCK(t) = GLOBAL_AB(20,t) ∨ GLOBAL_AB(60,t)` (3값 OR: 하나라도 1 이면 1, 모두 0 이면 0, 그 외 NA).
- 보조 라벨: `GLOBAL_A_ANY_HORIZON`, `GLOBAL_B_ANY_HORIZON`, `GLOBAL_AB_20_ONLY`, `GLOBAL_AB_60_ONLY`, `GLOBAL_AB_BOTH_HORIZONS`. 주 라벨을 대체하지 않는다.
- 진단(라벨 아님): 날짜·q 별 A·B·AB 충족 그룹 수(0–17), 평가 가능 그룹 수, 15/17·16/17 일수.

## 8. 구간

- FINAL_SHOCK = 1 인 연속 거래일을 한 구간으로. 하루도 구간. 갭 병합·진입/종료 완충 없음. 종료 다음 날 재진입 허용.
- NA 는 연속성을 끊는 미확인 경계. 정상 복귀로 해석하지 않는다.
- 자료 첫날·마지막 날에 닿은 구간은 `LEFT_CENSORED`·`RIGHT_CENSORED`.
- 종료 사유: 다음 날 상태가 0 이면 `GLOBAL_CONDITION_EXITED` (그날 AB 충족 그룹이 0 이면 추가로 `ALL_GROUPS_NORMALIZED`), NA 이면 `NOT_EVALUABLE`.

## 9. 기간 구분

2019 = 기준 전용, 2020 = 파일럿, 2021–2025 = 주 분석, 2026 = 부분·비블라인드 탐색 (성공 근거로 쓰지 않는다).

## 10. 최종 판정 범주 (셋 중 하나)

| 범주 | 조건 |
|---|---|
| `LABELS_GENERATED` | 주 분석기간에 FINAL_SHOCK = 1 인 날이 1일 이상 |
| `VALID_ZERO_INTERVALS` | 주 분석기간에 FINAL_SHOCK 가 판정 가능(0 또는 1)한 날이 주 분석기간 거래일의 50% 이상이고, 1 인 날이 0일 |
| `INSUFFICIENT_PEER_COVERAGE` | 판정 가능일이 50% 미만 (Peer 부족·결측) |

50% 는 판정 가능성의 최소 기준으로 사전에 정한 값이다. 실제 판정 가능 비율도 함께 보고한다.

## 11. 민감도 (주 정의를 대체하지 않음)

최근 504거래일 고정 길이 기준 · A ≥ 0.95 · B 2.5%/97.5% · KOSPI200 4종 (Core Pair + 배율 정규화 레버리지·인버스) 그룹 규칙 · 임계값 인근 안정성 (U 가 임계값 ±0.01 안에 있는 그룹-일 비율).

## 12. 기존 연구 대조

- W2: `research/multihorizon_w2/results/06/cross_daily_counts.csv` (HIGH_LEVEL·EXPANSION 일별 그룹 수)와 `cross_intervals_group.csv`. 사건 창은 설정의 `events` (2022 채권 · 2024-08 · 2025-04).
- W3: `research/joint_cusum_w3/results/08/` 의 개별 CUSUM 요약·순차 경보 에피소드·공동 에피소드. W4 라벨은 W3 의 정답이 아니며, W3 비유의로 W4 라벨을 부정하지 않는다.

## 13. 금지

17/17 사후 완화 · 결과 보고 임계값 조정 · Peer 사후 선택 · 무관 자산을 Peer 로 명명 · NA 를 0 으로 대체 · W2 후보를 참 구조변화로 명명 · W3 비유의를 시장 안정 증거로 해석 · W4 라벨을 급등 예측 성공으로 주장 · 05–08 동결 결과 수정 · 사용자 승인 없는 push·병합.

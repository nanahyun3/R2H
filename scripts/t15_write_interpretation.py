# ruff: noqa: E501
"""노트북 08 해석 문단과 CLAIMS 목록 작성 (MC 완료 후, 실행 결과 수치를 그대로 옮김).

해석의 모든 수치는 CLAIMS 에 같은 값으로 들어가며, 노트북 20장이 실행 결과와 대조한다.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research/joint_cusum_w3"

INTERP = {
    "ch04": r"""
**해석 (04).**
- **개별 경보.** W3 own-valid 보정 임계값 기준으로 5년 동안 개별 경보일을 셌다 (6종 × 3정책 × 4창 합산).
  - 153130 32일, 261220 9일, 133690 4일이다. **069500·229200·148070 은 0일**이다.
  - W1 동결 임계값으로 세면 186일이다. 이 값은 참고용이다.
- **임계값이 높아진 이유.** 평가연도별 DCC-t 귀무에서 연간 SVR 재적합까지 포함해 모의하면, 정상 시장에서도 CUSUM 연간 최대가 크게 나온다. 그래서 W3 임계값은 W1 값보다 높다.
- **경보 정의.** "경보" 는 ETF-연도마다 귀무 5% 가 넘는 일이 생기도록 정의했다. 경보가 0이라는 사실은 관측 CUSUM 이 그해 귀무 연간 최대의 95% 분위를 넘지 않았다는 뜻일 뿐이다.
- **계산 가능일.** 창이 길수록 연초 계산 불능이 커진다. w=20 은 1,130일 중 95일이 불능이고, w=120 은 630일만 계산되고 595일이 불능이다. 이 불능일은 무경보로 세지 않았다.
- **한계.** CUSUM 은 SVR 예측분산으로 표준화한 잔차의 통계량이다. 그래서 예측분산이 변동성 상승을 빠르게 흡수하면 반응이 작아진다 (T12·W1 과 같은 구조).
""",
    "ch05": r"""
**해석 (05).**
- **단기 분위 후보는 귀무에서도 하루 약 10% 켜진다.** holdout 귀무에서 q=3·7·14 확대 후보일 비율은 0.100–0.102 였다. 정의상 분위 상위 10% 이기 때문이다.
  - 따라서 "단기 신호가 먼저 반응했다" 는 사실만으로는 변화를 탐지했다고 할 수 없다. 13장에서 귀무 기준선과 비교한다.
- **W3 임계 개별 CUSUM 경보.** 5년 동안 10개 에피소드뿐이다 (w=20 3, w=60 3, w=120 4).
  - 모든 에피소드 직전 60일 안에 q=3 확대 후보가 있었고, 경보까지의 지연 중앙값은 10.5 거래일이다.
  - 다만 후보가 하루 10% 확률로 켜지므로, 이 선행성은 귀무에서도 거의 늘 성립한다.
- **2024-08 사례.**
  - q=3 확대 후보가 069500·229200 은 08-02, 133690 은 07-26, 148070 은 07-25 에 처음 켜졌다.
  - W3 임계 CUSUM 경보는 153130 의 w=120 (07-29) 하나뿐이다.
- **2025-04 사례.**
  - q=3 후보는 069500 03-28, 261220 04-01, 133690 04-07, 229200 04-09 다.
  - 여섯 ETF 모두 W3 임계 CUSUM 경보가 **없었다**.
- **단기 창 적격성.** w=3·7·14 CUSUM 은 귀무 크기(ETF-연도당 0.050–0.051, Wilson 상한 ≤ 0.064)는 통과했다.
  - 그러나 V1 검출률이 0.009·0.011·0.016 에 그쳐 **18칸 모두 NOT_ELIGIBLE** 이다.
  - 참고 창 20·30·60·120 도 검출률 0.016–0.046 으로 모두 NOT_ELIGIBLE 이다. W1 의 0/4 와 같은 방향이지만, 다른 귀무에서 얻은 결과이므로 W1 판정을 다시 내린 것이 아니다.
- **G7 Q12 (단기 신호 대 중장기 CUSUM 의 검출 지연).**
  - 단기 분위 후보는 자주, 빨리 켜지지만 변화에 특이적이지 않다.
  - 중장기 CUSUM 은 거의 켜지지 않는다.
  - 둘 사이의 "지연" 은 어느 한쪽의 탐지 성능이 아니다.
""",
    "ch07_09": r"""
**해석 (07–09).**
- **S1 (KOSPI200·KOSDAQ150).**
  - 관측 M_S1 = 4.471, DCC-t p = 0.853 이다. CCC-t 는 0.845, H0-A 는 원형 이동 0.627 · 블록 0.602 다.
  - 069500 이 귀무 적합도 N3 에서 탈락해 판정은 `NULL_MODEL_INVALID` 다. r² 자기상관이 5개 연도 모형 중 4개에서 envelope 위였다.
  - 사전 규칙에 따라 **확증 사슬은 S1 에서 멈춘다**. 공개 진행표에 "S2 에서 멈춘다" 고 적었던 예측은 이 결과로 정정한다. 규칙은 바꾸지 않았다.
  - 적합도를 무시하더라도 p 는 기준 0.02 에서 멀다.
- **공동 극단이 없었다.**
  - S1 의 일별 J_all 최대값은 4.471 이고, c_E = −log 0.01 = 4.605 에 못 미친다. 2021–2025 에 두 ETF 가 ±2일 안에서 동시에 각자 귀무 꼬리 1% 에 들어간 날이 하루도 없었다는 뜻이다.
  - 그래서 E₁ 이 비어 S2·S3 조건부 참여는 `NOT_ESTIMABLE` 이다. 이는 "국채·단기채가 참여하지 않았다" 는 증거가 **아니다**.
- **S4·S5.**
  - C_S4 = 0.669 (p = 0.855), C_S5 = 0.893 (p = 0.953) 이다.
  - 구성원 적합도 탈락과 사슬 중단으로 확증 지위가 없다.
- **조건부 귀무 유효성.**
  - V1·V2 처럼 앞 단계만 실제로 변할 때, 신규 ETF 검정의 기각률은 0.007–0.027 이었다.
  - Wilson 하한이 모두 0.02 이하라 조건부 귀무는 성립했다. 따라서 무효 판정의 원인은 조건부 귀무가 아니라 주변 적합도다.
- **G7 답.**
  - Q1 공동 반응: KOSPI–KOSDAQ 공동 CUSUM 극단은 관측되지 않았다.
  - Q2·Q3 이례성: H0-A·H0-B 모두 비이례적이다 (p ≥ 0.60). 단 H0-B 는 확증 불가다.
  - Q4 국채10년의 추가 정보: 추정 불가.
  - Q5 단기채: 귀무 부적합.
  - Q6 나스닥·Q7 원유: 비유의이며 확증 불가.
""",
    "ch10": r"""
**해석 (10).**
- **판정 분포.** 57개 중 56개가 `NULL_MODEL_INVALID` 이다. 069500·148070·153130·261220 중 하나라도 들어가 있거나, 069500+148070 쌍이 N4 에서 탈락했기 때문이다.
- **유효한 부분집합.** H0-B 가 유효한 부분집합은 **229200+133690 하나**다.
  - p = 0.270, CCC-t 0.255, minP 조정 0.270 으로 `NOT_SIGNIFICANT` 다.
- **원시 p.** 무효를 무시하고 본 DCC-t 원시 p 의 최소값도 0.040 이다 (069500+153130+261220). Holm 의 가장 엄격한 기준 0.02/57 = 3.5e-4 보다 백 배 이상 크다.
- **MC 해상도.** 가족 해상도 B × 기준 = 17.5 로 규칙(≥ 10)을 충족했다. 그래서 `INSUFFICIENT_MONTE_CARLO` 판정은 없고, 연장 규칙도 쓰지 않았다.
- **원시 점수.** 원시 공동 점수 최대는 153130+261220 의 5.689 다. 원시 점수가 높다는 것과 유의하다는 것은 다르다.
- **G7 Q8 (주 경로 밖 부분집합의 공통성).** 귀무를 넘는 공통성은 확인되지 않았다.
""",
    "ch11_12": r"""
**해석 (11–12).**
- **귀무 적합도: 탈락은 모두 "관측이 귀무보다 크다" 쪽이다.**
  - 069500: r² 자기상관 0.386–0.423 (2021–2024 모형). 귀무 상한은 ≤ 0.359 다. 실제 변동성 군집이 GARCH(1,1)-t 모의보다 강하다.
  - 261220: 초과 첨도 28.0–33.0 (5/5 모형). 주변 ν 는 4.4–7.5 인데 결합 다변량 t 의 ν 는 약 8 이라 모의 꼬리가 얇아진다. 단일 자유도 DCC-t 설계의 한계다. **다른 결합 분포를 사후에 시도하지 않는다.**
  - 153130: 정확 0 비율 0.185–0.270, LB(z) p < 0.01 이 5/5 다. 연속분포 귀무로 재현되지 않는다.
  - 148070: 2024 모형의 지속성이 경계값이다 (N1).
  - 229200·133690 은 모두 통과했다.
- **H0-A (보조).**
  - S1 은 0.627 (원형 이동) · 0.602 (블록) 이다.
  - 부분집합의 H0-A 최소값은 0.028 · 0.024 로, 0.02/57 보다 훨씬 크다. 그래서 `SIGNIFICANT_H0A_ONLY` 도 없다.
  - 변환은 방법마다 10,000개가 모두 서로 달랐다.
- **CCC-t (민감도).** DCC 와 거의 같다 (S1 0.845 대 0.853). 동적 상관을 넣어도 결론은 바뀌지 않는다.
- **초기조건 민감도.** burn-in 500 대 2000 의 M_S1 98% 분위가 7.790 대 7.789 로 안정적이었다.
""",
    "ch13": r"""
**해석 (13) — 이 연구의 결론을 정하는 장.**
- **크기는 맞다.** holdout 1,000 회의 실제 기각률은 다음과 같다.
  - S1 0.024 [0.016, 0.036], S2 0.022, S3 0.017, S5 0.014, 부분집합 Holm 가족 FWER 0.020 [0.013, 0.031] 이다.
  - S4 만 0.030 [0.021, 0.043] 으로 약간 반보수적이다. 6개 중 하나이며, 규칙은 바꾸지 않는다.
- **검출력은 사실상 없다.**
  - V1 은 KOSPI200·KOSDAQ150 분산 ×2 를 연말까지 지속시킨 시나리오다. 여기서 S1 경로 수준 기각률은 **0.043** 으로, 크기와 거의 같다.
  - 모든 대립 시나리오에서 유의일 검출은 **0/300** 이다. 예외는 V7 의 S1 거짓 검출 2/300 = 0.007 뿐이다.
  - 영향 ETF 의 참여율은 0.565, 비영향 ETF 의 과잉 참여는 0.532 로 거의 같다. 주입한 변화가 잔차 CUSUM 에서 보이지 않는다.
- **개별 신호도 변화를 구별하지 못한다.** V1 과 귀무 기준선의 60일 첫 발화 비율을 비교했다 (계약 외 사후 기준선).
  - q=3 확대 후보 1.000 대 0.992
  - q=14 확대 후보 0.860 대 0.743
  - CUSUM Q ≥ c_E (w=20) 0.233 대 0.228
  - W3 임계 CUSUM (w=60) 0.045 대 0.013
- **원인 해석.**
  - SVR–GARCH 예측분산이 분산 상승을 빠르게 흡수한다. 그래서 표준화 잔차의 CUSUM 은 지속 분산 변화에 거의 반응하지 않는다.
  - 여기에 정책 3 × 창 4 × 날짜 × 시차 ±2 를 최대값으로 탐색하는 보정 부담이 더해진다.
  - T12 (정책 A 검정력 0.085) 와 W1 (60일 검출 0.03–0.10) 의 낮은 검출력을 W3 공동 검정이 그대로 물려받았다.
- **G7 Q11 (알려진 합성 변화에 대한 검출력).** 충분하지 않다.
  - 그러므로 실제 ETF 에서 유의 구간이 없었다는 사실로 "추가 공동 불안정성이 없었다" 고 결론내릴 수 없다.
""",
    "ch15": r"""
**해석 (15).**
- **탐색 구간.** J_max ≥ c0 = −log 0.01 인 탐색 구간은 57개 집합 전체에서 **10개뿐이고 모두 2종 쌍**이다.
  - S1 (069500+229200) 의 구간은 0개다.
  - 유의일 기준을 넘은 날은 **0일**이다.
- **구간 수준 p.** 최소값은 0.066 이다 (153130+261220, 2025-04-04~04-08, 누적 초과 3.18).
- **판정.** 8개는 귀무 부적합 집합의 구간이다. 유효 집합 229200+133690 의 2개 구간(2021-08-24, 2021-09-13)은 `EXPLORATORY` 다.
- **결론.** 유의한 공동 구간은 없다. 따라서 구간 경계·지속에 관한 유의성 주장도 없다.
""",
    "ch16": r"""
**해석 (16).**
- **방향 분포.** 10개 탐색 구간의 방향은 혼합 3 · 판정 불가 3 · 공동 확대 2 · 공동 축소 2 였다.
- **G7 Q13 (공동 반응의 방향).**
  - 공동 반응의 방향은 한쪽으로 모이지 않는다.
  - 표본이 10개이고 귀무 보정이 없는 기술 통계이므로, 방향에 대한 주장은 하지 않는다.
- **H5 (구간 전후 60일 상관 변화).**
  - 쌍 8개의 평균 변화는 +0.105 다.
  - 보정되지 않은 탐색 결과다. 의존구조 자체의 변화를 검정한 것이 아니다.
""",
    "ch17": r"""
**해석 (17, `EXPLORATORY_REUSED_DATA`).**
- **단독 반응 사건 (94개, 날짜 블록 41개).** 사후 5일 누적수익률 중앙값은 0.024% [−0.356, 0.065] 로 0 근처다.
- **2종 이상 공동 반응 사건 (사후 10일 계산 가능 18개, 날짜 블록 6개).**
  - 사후 10일 중앙값은 0.461% [0.083, 1.272] 다.
  - 같은 조건의 대조일은 5개뿐이라 구간이 [−6.1, 6.2] 로 넓어 비교할 수 없다.
- **H0-B 유의 구간.** 없으므로 그 그룹은 비어 있다.
- **G7 Q14 (사후 가격반응: 개별 국면 대 공동 국면).** 표본이 작고 겹쳐 있어 차이를 말할 수 없다.
- **미래 확증 설계.**
  - 관측 차이를 효과크기로 두고, α = 0.01·검정력 0.8 을 맞추려면 그룹당 497 (5일) · 765 (10일) 사건이 필요하다.
  - 현재 자료로는 확증할 수 없다. 예약한 α = 0.01 은 쓰지 않았다.
  - W2 의 −0.84%p 결과를 검증된 가설로 쓰지 않는다.
""",
    "ch18": r"""
**해석 (18).** 통계 설계와 임계값을 확정한 뒤 사례를 해석했다.

- **2024-08.**
  - 어느 집합에도 탐색 공동 구간(J ≥ c0)이 없다.
  - 창 안에서 S1 J_all 최대값은 4.446 (2024-08-30) 이다.
  - 069500 의 개별 Q 는 그 창에서 5.93 까지 올랐지만, 229200 이 4.45 에 그쳐 "둘 다 1% 꼬리" 조건을 채우지 못했다.
  - 다중 기간 확대 후보는 6종 모두 07-25~08-07 에 켜졌다 (W2 의 관찰과 일치). 그러나 잔차 CUSUM 의 공동 극단으로는 이어지지 않았다.
- **2025-04.**
  - 공동 구간은 153130+261220 두 개다: 04-04~04-08 (공동 확대), 04-10~04-11 (혼합).
  - 두 구간 모두 귀무 부적합 집합에 속한다.
  - S1 J_all 은 창 안 최대 3.027 로 낮았다.
- **결론.** 사례 날짜는 실시간 조기 탐지 성공으로 읽지 않는다.
""",
    "ch19": r"""
### 가설·조합별 판정

| 대상 | 판정 | 근거 |
|---|---|---|
| H1 개별 잔차 분산 불안정성 | 기술. W3 임계 경보 45 ETF-정책-창-일 (153130·261220·133690 에서만) | 04장 |
| H2 (H0-A) 시간 정렬 | 비유의. S1 0.627·0.602, 부분집합 최소 0.024 > 3.5e-4 | 11–12장 |
| **H3 (H0-B) S1** | **`NULL_MODEL_INVALID`** (069500 N3). 원시 p 0.853 | 07장 |
| H4 S2·S3 | `NOT_ESTIMABLE` (E₁ 비어 있음 — 참여 부재의 증거 아님) | 08장 |
| H4 S4·S5 | `NULL_MODEL_INVALID` · 사슬 중단 (원시 p 0.855·0.953) | 09장 |
| 부분집합 57 | 56 `NULL_MODEL_INVALID` · 1 (229200+133690) `NOT_SIGNIFICANT` p=0.270 | 10장 |
| 공동 구간 | 유의 구간 0개. 탐색 구간 10개 (모두 쌍) | 15장 |
| H5 의존구조 변화 | 탐색 기술만 (평균 상관 변화 +0.105) | 16장 |
| H6 가격 | `EXPLORATORY_REUSED_DATA`. 확증 필요 표본 497–765 /그룹 | 17장 |
| 검출력 | V1 경로 기각 0.043 ≈ 크기 · 유의일 검출 0/300 → 사실상 없음 | 13장 |
| 단기 창 3·7·14 | `NOT_ELIGIBLE` (크기 통과, 검출 실패) | 05장 |

### 최종 판정

- **`LOW_POWER_INCONCLUSIVE` (주).**
  - 설계한 공동 분산 변화조차 검정 크기 수준으로만 잡혔다.
  - 그러므로 유의 구간이 없다는 사실은 "추가 공동 불안정성이 없다" 는 뜻이 아니다.
- **`NULL_MODEL_INVALID` (주 경로 전 단계, 부분집합 56/57).**
  - DCC-t 귀무는 069500 의 변동성 군집, 261220 의 꼬리, 153130 의 이산성, 148070 의 지속성을 재현하지 못했다.
- **`NO_SIGNIFICANT_COMMON_INTERVAL`.**
  - 유효한 유일 조합 229200+133690 이 비유의다.
  - 원시 p 를 보아도 최소 0.040 으로 기준에서 멀다.
- **쓸 수 없는 판정.** `COMMON_SYNCHRONIZATION_EXPLAINED_BY_NULL` 은 검출력이 없어서 쓸 수 없다.
- **쓰지 않은 판정.** `INSUFFICIENT_MONTE_CARLO`·`BLOCKED_BY_COMPUTE` 는 해당 사항이 없다 (해상도 충족, 13.1시간).

### 비지지 가설·한계

- **비지지 가설.** "KOSPI·KOSDAQ 의 CUSUM 이 정상 동조성을 넘어 함께 반응한다" 는 가설은 지지되지 않았다. 다만 이 검정은 그런 반응을 잡을 힘이 없었다.
- **표준화 효과.** 잔차 CUSUM 은 SVR 예측분산이 변동성을 흡수한 뒤의 통계량이다. 그래서 가격 변동성의 공동 급등을 직접 재는 도구가 아니다.
  - 다음 연구는 표준화 전 수익률 또는 예측 오차(QLIKE) 수준의 공동 통계량으로 검출력을 먼저 확인해야 한다.
- **귀무모형.** 결합 자유도가 하나뿐인 DCC-t 는 이 6종의 꼬리와 이산성을 재현하지 못한다. 대안 결합(t-copula 등)은 이번 연구에서 사후로 시도하지 않았다.
- **자료.** 2021–2025 는 W1·W2 에서 이미 본 자료다. 독립 외부 검증이 아니다.
""",
}

CLAIMS = [
    {"id": "w3_alarm_total", "expr": "int(INDIV.alarm_days_w3.sum())", "want": 45},
    {"id": "w3_alarm_153130", "expr": "int(INDIV[INDIV.ticker=='153130'].alarm_days_w3.sum())", "want": 32},
    {"id": "w3_alarm_261220", "expr": "int(INDIV[INDIV.ticker=='261220'].alarm_days_w3.sum())", "want": 9},
    {"id": "w3_alarm_133690", "expr": "int(INDIV[INDIV.ticker=='133690'].alarm_days_w3.sum())", "want": 4},
    {
        "id": "w3_alarm_kospi_kosdaq_bond",
        "expr": "int(INDIV[INDIV.ticker.isin(['069500','229200','148070'])].alarm_days_w3.sum())",
        "want": 0,
    },
    {"id": "w1_ref_alarm_total", "expr": "int(INDIV.alarm_days_w1_ref.sum())", "want": 186},
    {"id": "valid_w20", "expr": "int(INDIV[INDIV.w==20].valid_days.iloc[0])", "want": 1130},
    {"id": "na_w20", "expr": "int(INDIV[INDIV.w==20].not_available_days.iloc[0])", "want": 95},
    {"id": "valid_w120", "expr": "int(INDIV[INDIV.w==120].valid_days.iloc[0])", "want": 630},
    {"id": "na_w120", "expr": "int(INDIV[INDIV.w==120].not_available_days.iloc[0])", "want": 595},
    {"id": "seq_episodes", "expr": "len(SEQ)", "want": 10},
    {
        "id": "seq_by_w",
        "expr": "{str(k): int(v) for k, v in SEQ.groupby('w').size().items()}",
        "want": {"20": 3, "60": 3, "120": 4},
    },
    {"id": "seq_q3_preceded", "expr": "float(SEQ.lag_from_q3_EXP.notna().mean())", "want": 1.0, "atol": 1e-9},
    {"id": "seq_q3_lag_median", "expr": "float(SEQ.lag_from_q3_EXP.median())", "want": 10.5, "atol": 1e-9},
    {
        "id": "elig_short_none",
        "expr": "int((ELIG[ELIG.w.isin([3,7,14])].verdict=='ELIGIBLE').sum())",
        "want": 0,
    },
    {"id": "elig_all_none", "expr": "int((ELIG.verdict=='ELIGIBLE').sum())", "want": 0},
    {
        "id": "elig_short_size_hi",
        "expr": "round(float(ELIG[ELIG.w.isin([3,7,14])].null_wilson_high.max()),3)",
        "want": 0.064,
        "atol": 1e-9,
    },
    {
        "id": "elig_v1_w3",
        "expr": "round(float(ELIG[ELIG.w==3].v1_detected_60_pooled_affected.mean()),3)",
        "want": 0.009,
        "atol": 1e-9,
    },
    {
        "id": "elig_v1_w7",
        "expr": "round(float(ELIG[ELIG.w==7].v1_detected_60_pooled_affected.mean()),3)",
        "want": 0.011,
        "atol": 1e-9,
    },
    {
        "id": "elig_v1_w14",
        "expr": "round(float(ELIG[ELIG.w==14].v1_detected_60_pooled_affected.mean()),3)",
        "want": 0.016,
        "atol": 1e-9,
    },
    {
        "id": "case24_069500_q3",
        "expr": "CASE_T['2024-08 (2024-07-25~09-30)'].set_index('ticker').loc['069500','first_EXP_q3']",
        "want": "2024-08-02",
    },
    {
        "id": "case24_148070_q3",
        "expr": "CASE_T['2024-08 (2024-07-25~09-30)'].set_index('ticker').loc['148070','first_EXP_q3']",
        "want": "2024-07-25",
    },
    {
        "id": "case24_153130_w120",
        "expr": "CASE_T['2024-08 (2024-07-25~09-30)'].set_index('ticker').loc['153130','first_CUSUM_w120']",
        "want": "2024-07-29",
    },
    {
        "id": "case25_no_cusum",
        "expr": "int((CASE_T['2025-04 (2025-03-25~05-30)'][['first_CUSUM_w20','first_CUSUM_w30','first_CUSUM_w60','first_CUSUM_w120']]!='NONE').sum().sum())",
        "want": 0,
    },
    {
        "id": "s1_obs",
        "expr": "round(float(STAGE.set_index('stage').loc['S1','obs']),3)",
        "want": 4.471,
        "atol": 1e-9,
    },
    {
        "id": "s1_p",
        "expr": "round(float(STAGE.set_index('stage').loc['S1','p_dcc']),3)",
        "want": 0.853,
        "atol": 1e-9,
    },
    {
        "id": "s1_p_ccc",
        "expr": "round(float(STAGE.set_index('stage').loc['S1','p_ccc']),3)",
        "want": 0.845,
        "atol": 1e-9,
    },
    {
        "id": "s1_h0a_shift",
        "expr": "round(float(STAGE.set_index('stage').loc['S1','p_h0a_circular_shift_within_year']),3)",
        "want": 0.627,
        "atol": 1e-9,
    },
    {
        "id": "s1_h0a_block",
        "expr": "round(float(STAGE.set_index('stage').loc['S1','p_h0a_circular_block_bootstrap_within_year']),3)",
        "want": 0.602,
        "atol": 1e-9,
    },
    {
        "id": "stage_status",
        "expr": "STAGE.status.tolist()",
        "want": [
            "NULL_MODEL_INVALID",
            "NOT_ESTIMABLE",
            "NOT_ESTIMABLE",
            "NULL_MODEL_INVALID",
            "NULL_MODEL_INVALID",
        ],
    },
    {"id": "chain_stop_s1", "expr": "STAGE.confirmatory_status.iloc[0]", "want": "NULL_MODEL_INVALID"},
    {
        "id": "s4_obs",
        "expr": "round(float(STAGE.set_index('stage').loc['S4','obs']),3)",
        "want": 0.669,
        "atol": 1e-9,
    },
    {
        "id": "s4_p",
        "expr": "round(float(STAGE.set_index('stage').loc['S4','p_dcc']),3)",
        "want": 0.855,
        "atol": 1e-9,
    },
    {
        "id": "s5_obs",
        "expr": "round(float(STAGE.set_index('stage').loc['S5','obs']),3)",
        "want": 0.893,
        "atol": 1e-9,
    },
    {
        "id": "s5_p",
        "expr": "round(float(STAGE.set_index('stage').loc['S5','p_dcc']),3)",
        "want": 0.953,
        "atol": 1e-9,
    },
    {"id": "cond_rate_min", "expr": "round(float(COND.rate.min()),3)", "want": 0.007, "atol": 1e-9},
    {"id": "cond_rate_max", "expr": "round(float(COND.rate.max()),3)", "want": 0.027, "atol": 1e-9},
    {"id": "cond_all_valid", "expr": "bool(COND.conditional_null_valid.all())", "want": True},
    {"id": "sub_invalid", "expr": "int((SUB.status=='NULL_MODEL_INVALID').sum())", "want": 56},
    {"id": "sub_valid_only", "expr": "SUB[SUB.h0b_valid].subset.tolist()", "want": ["229200+133690"]},
    {
        "id": "sub_valid_p",
        "expr": "round(float(SUB[SUB.h0b_valid].p_dcc.iloc[0]),3)",
        "want": 0.270,
        "atol": 1e-9,
    },
    {
        "id": "sub_valid_p_ccc",
        "expr": "round(float(SUB[SUB.h0b_valid].p_ccc.iloc[0]),3)",
        "want": 0.255,
        "atol": 1e-9,
    },
    {"id": "sub_min_p", "expr": "round(float(SUB.p_dcc.min()),3)", "want": 0.040, "atol": 1e-9},
    {
        "id": "sub_min_p_subset",
        "expr": "SUB.loc[SUB.p_dcc.idxmin(),'subset']",
        "want": "069500+153130+261220",
    },
    {"id": "sub_max_M", "expr": "round(float(SUB.M_obs.max()),3)", "want": 5.689, "atol": 1e-9},
    {
        "id": "sub_h0a_shift_min",
        "expr": "round(float(SUB.p_h0a_circular_shift_within_year.min()),3)",
        "want": 0.028,
        "atol": 1e-9,
    },
    {
        "id": "sub_h0a_block_min",
        "expr": "round(float(SUB.p_h0a_circular_block_bootstrap_within_year.min()),3)",
        "want": 0.024,
        "atol": 1e-9,
    },
    {
        "id": "acf_069500_years_above",
        "expr": "int(((VDET.statistic=='acf_r2')&(VDET.ticker=='069500')&(VDET.side=='위')).sum())",
        "want": 4,
    },
    {
        "id": "acf_069500_min",
        "expr": "round(float(VDET[(VDET.statistic=='acf_r2')&(VDET.ticker=='069500')&(VDET.side=='위')].obs.min()),3)",
        "want": 0.386,
        "atol": 1e-9,
    },
    {
        "id": "acf_069500_max",
        "expr": "round(float(VDET[(VDET.statistic=='acf_r2')&(VDET.ticker=='069500')&(VDET.side=='위')].obs.max()),3)",
        "want": 0.423,
        "atol": 1e-9,
    },
    {
        "id": "kurt_261220_years_above",
        "expr": "int(((VDET.statistic=='kurt')&(VDET.ticker=='261220')&(VDET.side=='위')).sum())",
        "want": 5,
    },
    {"id": "n3_pass", "expr": "VAL['n3'][VAL['n3'].N3_pass].ticker.tolist()", "want": ["229200", "133690"]},
    {
        "id": "rob_q98",
        "expr": "[round(float(v),3) for v in ROB[(ROB.statistic=='M_S1')&(ROB['quantile']==0.98)][['burn500','burn2000']].iloc[0]]",
        "want": [7.79, 7.789],
    },
    {"id": "h0a_unique", "expr": "H0AD.unique_transforms.tolist()", "want": [10000, 10000]},
    {"id": "size_s1", "expr": "round(float(SIZE.iloc[0]['size']),3)", "want": 0.024, "atol": 1e-9},
    {"id": "size_s4", "expr": "round(float(SIZE.iloc[3]['size']),3)", "want": 0.030, "atol": 1e-9},
    {"id": "size_fam", "expr": "round(float(SIZE.iloc[5]['size']),3)", "want": 0.020, "atol": 1e-9},
    {
        "id": "v1_path_s1",
        "expr": "round(float(POWER['path'].set_index('scenario').loc['V1','path_S1_reject']),3)",
        "want": 0.043,
        "atol": 1e-9,
    },
    {
        "id": "det_all_zero_but_v7",
        "expr": "int(POWER['detection'][POWER['detection'].scenario!='V7'].detected_60.gt(0).sum())",
        "want": 0,
    },
    {
        "id": "v7_s1_false",
        "expr": "round(float(POWER['detection'].set_index(['scenario','family']).loc[('V7','S1'),'detected_60']),3)",
        "want": 0.007,
        "atol": 1e-9,
    },
    {
        "id": "v1_recall",
        "expr": "round(float(POWER['path'].set_index('scenario').loc['V1','participation_recall']),3)",
        "want": 0.565,
        "atol": 1e-9,
    },
    {
        "id": "v1_over",
        "expr": "round(float(POWER['path'].set_index('scenario').loc['V1','over_participation']),3)",
        "want": 0.532,
        "atol": 1e-9,
    },
    {
        "id": "v1_q3",
        "expr": "[round(float(x),3) for x in V1D.set_index('signal').loc['q3_EXP',['detected_60','null_detected_60']]]",
        "want": [1.0, 0.992],
    },
    {
        "id": "v1_q14",
        "expr": "[round(float(x),3) for x in V1D.set_index('signal').loc['q14_EXP',['detected_60','null_detected_60']]]",
        "want": [0.86, 0.743],
    },
    {
        "id": "v1_Q_w20",
        "expr": "[round(float(x),3) for x in V1D.set_index('signal').loc['cusum_Q_A_w20',['detected_60','null_detected_60']]]",
        "want": [0.233, 0.228],
    },
    {
        "id": "v1_w3_w60",
        "expr": "[round(float(x),3) for x in V1D.set_index('signal').loc['cusum_w3crit_A_w60',['detected_60','null_detected_60']]]",
        "want": [0.045, 0.013],
    },
    {"id": "ep_count", "expr": "len(EP)", "want": 10},
    {"id": "ep_all_pairs", "expr": "sorted(EP['size'].unique().tolist())", "want": [2]},
    {"id": "ep_s1_none", "expr": "int((EP.subset=='069500+229200').sum())", "want": 0},
    {"id": "ep_sig_days", "expr": "int(EP.n_days_ge_day_critical.sum())", "want": 0},
    {"id": "ep_min_p", "expr": "round(float(EP.retrospective_p_value.min()),3)", "want": 0.066, "atol": 1e-9},
    {
        "id": "ep_status",
        "expr": "EP.day_level_status.value_counts().to_dict()",
        "want": {"NULL_MODEL_INVALID": 8, "EXPLORATORY": 2},
    },
    {
        "id": "ep_direction",
        "expr": "EP.direction.value_counts().sort_index().to_dict()",
        "want": {"COMMON_CONTRACTION": 2, "COMMON_EXPANSION": 2, "MIXED": 3, "UNDETERMINED": 3},
    },
    {"id": "corr_pairs", "expr": "len(CORR)", "want": 8},
    {"id": "corr_mean", "expr": "round(float(CORR.delta.mean()),3)", "want": 0.105, "atol": 1e-9},
    {
        "id": "price_single_h5",
        "expr": "[round(float(x),3) for x in PRICE['summary'].set_index(['group','h']).loc[('single_etf_only',5),['n_events','median_ret','ci95_low','ci95_high']]]",
        "want": [94.0, 0.024, -0.356, 0.065],
    },
    {
        "id": "price_multi_h10",
        "expr": "[round(float(x),3) for x in PRICE['summary'].set_index(['group','h']).loc[('two_or_more_etf',10),['n_events','median_ret','ci95_low','ci95_high']]]",
        "want": [18.0, 0.461, 0.083, 1.272],
    },
    {
        "id": "price_req",
        "expr": "REQ.set_index('h')['n_per_group_required_alpha_0.01_power_0.8'].loc[[5,10]].astype(int).tolist()",
        "want": [497, 765],
    },
    {"id": "w1_integrity", "expr": "bool(W1CHK.match.all())", "want": True},
    {"id": "t12_repro", "expr": "bool(REPRO.max_abs_de.max() < 1e-8)", "want": True},
]

CLAIMS.append(
    {
        "id": "price_multi_h10_blocks",
        "expr": "int(PRICE['summary'].set_index(['group','h']).loc[('two_or_more_etf',10),'n_date_blocks'])",
        "want": 6,
    }
)


def main() -> None:
    (OUT / "notebook_interpretation.json").write_text(
        json.dumps({k: v.strip() for k, v in INTERP.items()}, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    (OUT / "notebook_claims.json").write_text(
        json.dumps(CLAIMS, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print("해석", len(INTERP), "문단 · CLAIMS", len(CLAIMS), "개")


if __name__ == "__main__":
    main()

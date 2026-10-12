"""최종 연구보고서 DOCX 생성 — 숫자는 ``claims.json`` (재계산·EXTENSION) 과 ``analysis/``·``extension/`` 표에서만 읽는다.

사용한 claim 키와 위치를 기록해 ``SOURCE_EVIDENCE_MATRIX.md`` 를 함께 쓴다.
실행 (R2H 루트): ``python deliverables/R2H_T11_CUSUM_Final_Review/scripts/05_build_docx.py``
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from docx_kit import (  # noqa: E402
    BULLET_SIZE,
    bullets,
    caption,
    equation,
    figure,
    header_footer,
    new_document,
    note,
    page_break,
    para,
    set_core,
    table,
    toc,
)

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
FIG = HERE / "figures"
OLDFIG = REPO / "docs" / "figures" / "svrgarch"
AN = HERE / "analysis"
EXT = HERE / "extension"
OUT_DOCX = HERE / "R2H_T11_SVR_GARCH_CUSUM_최종연구보고서.docx"
SHA = "a346faf78ff47b2695fab438f7397d7958b8d655"
VERSION = "v1.0 (2026-10-12)"
CLAIMS = json.loads((HERE / "claims.json").read_text())
USED: dict[str, list[str]] = {}
_SECTION = ["표지"]


def v(key: str) -> str:
    """claim 값을 문자열로 — 사용 위치를 기록한다."""
    if key not in CLAIMS:
        raise KeyError(key)
    USED.setdefault(key, [])
    if _SECTION[0] not in USED[key]:
        USED[key].append(_SECTION[0])
    val = CLAIMS[key]["value"]
    if isinstance(val, float):
        if abs(val) < 1e-3 and val != 0:
            return "10⁻⁵ 미만"
        txt = f"{val:.6g}"
        return txt if len(txt) <= 7 else f"{val:.4g}"
    return str(val)


def H1(doc, text):
    _SECTION[0] = text
    doc.add_heading(text, level=1)


def H2(doc, text):
    _SECTION[0] = text
    doc.add_heading(text, level=2)


def H3(doc, text):
    doc.add_heading(text, level=3)


SMALL = [None]


def P(doc, text, **kw):
    kw.setdefault("size", SMALL[0])
    return para(doc, text, align="justify", **kw)


FIGN = [0]
TABN = [0]
FIG_ORDER = ["fig01_pipeline.png", "fig11_vol_overview.png", "fig10_cusum_toy.png", "fig02_fullsample_T.png", "fig06_kospi200_pair.png",
             "fig03_critical_values.png", "fig04_alarm_rates.png", "04_rolling_heatmaps.png", "10_yearly_blocks.png",
             "fig07_timeline_069500.png", "fig05_size_power.png", "fig08_dependence_and_null.png", "fig09_state_concept.png"]


def F(name: str) -> int:
    """그림 이름 → 보고서 그림 번호 (본문 참조용)."""
    return FIG_ORDER.index(name) + 1


def fig(doc, name, title, src, width=16.0, folder=FIG):
    FIGN[0] += 1
    assert F(name) == FIGN[0], (name, FIGN[0])
    figure(doc, folder / name, f"그림 {FIGN[0]}. {title}", src, width)
    return FIGN[0]


def tab(doc, title, header, rows, **kw):
    TABN[0] += 1
    table(doc, f"표 {TABN[0]}. {title}", header, rows, **kw)
    return TABN[0]


def build() -> None:
    doc = new_document()
    set_core(doc, "SVR–GARCH CUSUM의 ETF 적용과 통계적 구조변화 검정의 재평가", "R2H T11 최종 연구보고서",
             "R2H 시스템분석 프로젝트 팀", "SVR-GARCH, CUSUM-of-squares, ETF, structural change, size, power")
    names = pd.read_csv(REPO / "research" / "svr_garch_cusum_etf" / "reference_close_sha256.csv", dtype=str)
    fs = pd.read_csv(AN / "fullsample_recomputed.csv", dtype={"ticker": str})
    fitsum = pd.read_csv(REPO / "research" / "svr_garch_cusum_etf" / "results" / "fit_summary.csv", dtype={"ticker": str})

    # ───────────────────────── 표지
    for _ in range(3):
        para(doc, "")
    para(doc, "R2H / 시스템분석 프로젝트 · T11 최종 재평가", size=11, color="555555", align="center")
    para(doc, "")
    para(doc, "SVR–GARCH CUSUM의 ETF 적용과\n통계적 구조변화 검정의 재평가", size=22, bold=True, color="1F3864", align="center")
    para(doc, "조건부분산 모형 의존성, 검정 안정성 및 잠재 시장 상태 정의를 중심으로", size=12.5, color="333333", align="center")
    for _ in range(5):
        para(doc, "")
    rows = [
        ["작성일", "2026-10-12"],
        ["작성", "R2H 시스템분석 프로젝트 팀 (분석·문서 작성: Claude Code 보조)"],
        ["보고서 버전", VERSION],
        ["대상 저장소", f"github.com/nanahyun3/R2H · 브랜치 1012 · 기준 커밋 {SHA[:7]}"],
        ["데이터 버전", f"ETF 20종 종가 해시 20/20 일치 · data_version {v('data_version')}"],
        ["검증 상태", "결과표 재계산 VERIFIED (2개 환경 바이트 동일) · 합성 자료 EXTENSION 6건 · 원 논문 수치 미재현 (UNRESOLVED)"],
    ]
    tab(doc, "보고서 정보", ["항목", "내용"], rows, widths=[3.2, 13.0], size=8.5)
    page_break(doc)

    # ───────────────────────── 목차
    para(doc, "목차", size=15, bold=True, color="1F3864")
    toc(doc)
    page_break(doc)

    # ───────────────────────── 요약
    H1(doc, "요약 (Executive Summary)")
    SMALL[0] = 9.2
    BULLET_SIZE[0] = 9.2
    P(doc, "**배경.** R2H 프로젝트는 ETF 급등 국면 포착을 상위 목표로 한다. T11 연구는 Lee·Kim·Lee (2020)의 SVR–GARCH CUSUM-of-squares "
      "검정을 국내 상장 ETF 20종에 적용하고, 그 결과를 연구자가 정의한 가격·상관 사건(P1·P4·C3·공통충격)과 비교했다. 그러나 이 사건들은 "
      "임계값·누적 기간·지속성 기준을 연구자가 정한 것이고, 일부는 기준선 잔차와 같은 수익률·변동성 계산을 공유한다. 따라서 시장 상태의 독립적 "
      "정답으로 쓸 수 없다. 이 보고서는 사건 기반 평가를 성능 판단 근거에서 제외하고, 검정 자체의 통계적 성질을 다시 평가한다.")
    P(doc, "**연구 질문.** 조건부분산을 SVR–GARCH로 설명한 뒤에도 표준화 잔차에 구조변화가 남는가? 그 판단은 분산 입력 정책, 관측창, "
      "임계값 귀무모형, 자산 특성에 얼마나 민감한가? (RQ1–RQ6, 2장)")
    P(doc, "**수행한 작업.** 다음 세 가지를 수행했다.")
    bullets(doc, [
        f"커밋된 결과표 9종을 캐시 잔차에서 독립 재계산했다. 차이는 모두 {v('fs_max_abs_diff')}으로 CSV 반올림 수준이다.",
        "같은 커밋으로 오토런을 서로 다른 두 환경에서 다시 실행해 결과표가 바이트 단위로 같음을 확인했다.",
        "합성 자료로 확장 실험 6건(E1–E6)을 수행했다: 경험적 크기·검정력, 귀무모형 민감도, 시점 무결성, 잔차 의존성.",
    ])
    P(doc, "**핵심 결과.**")
    bullets(doc, [
        f"검정 구간(571일) 사후 검정의 기각 수는 정책 A {v('fs_reject_A')}/20, 정책 B {v('fs_reject_B')}/20, 기준선 {v('fs_reject_base')}/20이다 (임계값 1.3397). [VERIFIED]",
        f"합성 GARCH 귀무에서 같은 파이프라인의 경험적 크기는 정책 A {v('E2_null_A_rej13397')}%, 정책 B {v('E2_null_B_rej13397')}%, "
        f"기준선 {v('E2_null_base_rej13397')}%였다 (명목 5%). 정책 B와 기준선의 기각은 구조변화의 증거로 읽을 수 없다. [VERIFIED·EXTENSION]",
        f"검정 구간 중간에 무조건분산을 3배로 바꾼 대립에서도 정책 A의 검정력은 {v('E2_break_A_rej13397')}%에 그쳤다. 정책 A가 기각하지 않은 "
        f"{20 - int(v('fs_reject_A'))}종을 '구조변화 없음'으로 해석할 수 없다. [VERIFIED·EXTENSION]",
        f"정책 A 잔차 제곱은 음의 자기상관을 보인다 (장기분산/τ̂² 중앙값: 검정 구간 {v('E6_svrA_test_lrv')}, 합성 귀무 {v('E6_sim_A_lrv')}). "
        f"이 때문에 τ̂ 정규화가 통계량을 눌러 검정이 보수적이 된다. 이동창 경보가 iid 귀무 기대보다 적은 것(w=60: {v('rate_svrA_w60_all')} vs {v('rate_svrA_w60_null')}회/년)은 "
        "낮은 오탐률의 증거가 아니라 이 기전과 맞는다. [INFERRED]",
        f"같은 KOSPI200 지수를 추종하는 KODEX 200과 TIGER 200은 검정 구간 수익률 상관이 {v('k200_corr_r')}인데도 정책 A 통계량이 "
        f"{v('k200_TA_069500')} (기각) 대 {v('k200_TA_102110')} (비기각)으로 갈린다. 차이는 SVR 초모수 선택(C=1 대 C=100)에서 나온다. [VERIFIED]",
        f"임계값의 귀무를 iid에서 stationary bootstrap으로 바꾸면 정책 A로 기각되는 ETF가 절반 바뀐다 (겹침 {v('E3_reject_both')}/4). [VERIFIED·EXTENSION]",
    ])
    P(doc, "**결론.** 검증된 사실은 계산의 결정성과 재현성, 시점 무결성, 그리고 이 설정에서 검정이 보이는 크기·검정력의 수치다. "
      "정책 A는 크기는 지키지만 검정력이 낮고, 정책 B와 기준선은 검정력이 높아 보이지만 크기가 크게 부풀려져 있다. 따라서 이번 자료로는 "
      "'SVR–GARCH 표준화 뒤 ETF 잔차에 구조변화가 남는가'에 확정적으로 답할 수 없다 (RQ1 UNRESOLVED). 원 논문 수치도 재현되지 않았다 "
      "(METHOD_FIDELITY_UNRESOLVED). 투자 유용성은 측정하지 않았다.")
    P(doc, "**후속 연구.** 다음 단계는 탐지기 개선이 아니다. 관측 O, 잠재 상태 S, 사후 믿음 P(S|O)를 조작적으로 정의하고 그 식별 가능성을 "
      "먼저 검증하는 것이다 (9장). CUSUM 통계량은 상태 자체가 아니라 관측 후보 가운데 하나로만 다룬다.")
    SMALL[0] = None
    BULLET_SIZE[0] = None
    page_break(doc)

    # ───────────────────────── 1
    H1(doc, "1. 연구 배경과 문제 재정의")
    H2(doc, "1.1 상위 목표와 통계적 검정 대상의 차이")
    P(doc, "R2H의 상위 과업은 ETF 가격의 급등 국면을 포착하는 것이다. 이는 수익률의 방향과 크기에 관한 경제적 과업이다. 반면 CUSUM-of-squares "
      "검정의 대상은 표준화 잔차 제곱의 평균, 곧 잔차 분산이 표본 안에서 일정한가 하는 통계적 가설이다. 분산 구조변화는 상승·하락 방향을 "
      "구분하지 않는다. 같은 크기의 하락 충격에도 같은 통계량이 나온다. 따라서 검정의 기각을 곧바로 급등 신호로 옮기는 것은 범주 오류다 "
      "(7.5절). 이 보고서는 두 대상을 분리해 검정의 성질만 평가한다.")
    H2(doc, "1.2 기존 사건 기반 평가를 제외하는 이유")
    P(doc, "기존 T11은 경보와 P1(급등·급락 후보, r/σ≥3), P4(누적수익률 절대값 경계), C3(KOSPI200 대비 상관 부호전환), 공통충격일의 시간적 "
      "근접성을 원형 이동 귀무로 검정했다. 이 보고서는 그 결과를 성능 판단에 쓰지 않는다. 이유는 셋이다.")
    bullets(doc, [
        "**정답이 아니다.** 사건은 연구자가 고른 임계값·기간·지속성 규칙의 산물이다. 시장 상태 변화의 독립적 측정이라는 근거가 없다.",
        "**계산을 공유한다.** P1의 점수 r/σ₆₀은 기준선 잔차와 같은 식이다. 기준선 경보와 P1의 근접에는 기계적 일치가 섞인다 (기존 T11도 P1 사건일 제거 시 p<0.05 비율이 8.9%→4.6%로 줄었다고 기록, REPORTED).",
        "**비대칭 해석의 위험.** 임의 사건과 겹치지 않았다고 검정이 무효라고 할 수 없다. 겹쳤다고 유효하다고 할 수도 없다.",
    ])
    P(doc, "기존 결과 파일(overlap_metrics.csv, episode_flows.csv 등)은 삭제하거나 수정하지 않았다. 새로운 임의 사건 집합으로 대체하지도 않았다. "
      "검정력 평가는 생성 과정과 변화 시점을 명시한 합성 시계열로만 했다 (6.3절). 합성 자료의 변화점은 통계적 정답일 뿐 시장의 경제적 상태 정답이 아니다.")
    H2(doc, "1.3 이 보고서의 범위")
    P(doc, "그림 1은 분석 대상과 네 가지 사용 형태를 구분한다. ① 원 논문의 전체 구간 사후 검정, ② T11이 제안한 이동창 반복 검정, ③ 실제 온라인 "
      "경보 시스템, ④ 투자 의사결정·수익률 예측이다. 이 보고서가 수치로 평가하는 것은 ①과 ②의 통계적 성질뿐이다. ③의 오탐·지연 보장과 "
      "④의 성과는 평가하지 않았다. 사후 변화점 추정일 k̂를 그 당시의 실시간 검출일로 해석하지 않는다.")
    fig(doc, "fig01_pipeline.png", "SVR–GARCH CUSUM-of-squares 파이프라인과 네 가지 사용 형태",
        "출처: 이 보고서 작성 (scripts/04_figures.py fig01). 조건: T11 프로토콜 (m=5, p=q=1, 앞 70% 적합). 주의: ③·④는 이 보고서의 검증 범위 밖이다.")

    # ───────────────────────── 2
    H1(doc, "2. 연구 목적과 검증 질문")
    P(doc, "목적은 탐지기의 성공·실패 판정이 아니다. 검정의 통계적 성질, 식별 가능성, 모형 의존성, 그리고 연구적 한계를 규명하는 것이다. 이를 위해 질문을 여섯 개로 다시 세웠다.")
    tab(doc, "연구 질문과 이 보고서의 답변 위치", ["RQ", "질문", "주로 답하는 절"], [
        ["RQ1", "SVR–GARCH 조건부분산으로 표준화한 잔차 제곱에 통계적 구조변화가 남는가", "5.1, 6.3, 7.1"],
        ["RQ2", "분산 입력 정책 A(관측 proxy)와 B(재귀 예측)에 따라 통계량·기각이 어떻게 달라지는가", "5.2, 6.3, 6.6"],
        ["RQ3", "20·30·60·120·252일 이동창에서 통계량·경보 빈도가 어떻게 변하는가", "5.4"],
        ["RQ4", "iid bootstrap 임계값의 이론적·경험적 한계, 의존성·이분산이 귀무분포에 주는 영향", "4.4, 6.2–6.5"],
        ["RQ5", "같은 지수를 추종하는 ETF 간 일관성, 자산군에 따른 차이", "5.3, 6.8"],
        ["RQ6", "검출된 잔차 구조변화의 의미, 시장 상태 전환으로 해석하기 위한 추가 가정", "7, 9"],
    ], widths=[1.2, 11.4, 3.6], size=8.3)
    P(doc, "주장마다 다음 상태 표기를 붙인다. 모든 주요 수치와 그 원천 파일·열·함수는 별도 파일 SOURCE_EVIDENCE_MATRIX.md에 연결했다.")
    tab(doc, "판정 상태 표기", ["표기", "의미"], [
        ["VERIFIED", "이 작업에서 코드 재실행 또는 원시 결과표 재계산으로 확인"],
        ["REPORTED", "기존 결과표·보고서에서만 확인 (이 작업에서 재계산하지 않음)"],
        ["INFERRED", "검증된 자료를 근거로 한 해석"],
        ["HYPOTHESIS", "후속 검증이 필요한 가설"],
        ["UNRESOLVED", "자료 부족 또는 방법론적 미해결"],
        ["EXTENSION", "T11 원본 결과와 분리된 이번 추가 실험 (extension/ 디렉터리)"],
    ], widths=[3.0, 13.2], size=8.3)

    # ───────────────────────── 3
    H1(doc, "3. 데이터와 실험 설계")
    H2(doc, "3.1 데이터 카드")
    cats = {"broad_market": "시장 지수", "leveraged_inverse": "레버리지·인버스", "sector": "업종", "theme": "테마",
            "strategy": "전략", "rates": "채권(장기)", "money_market": "단기채", "commodity": "원자재", "currency": "통화"}
    tab(doc, "분석 대상 ETF 20종", ["코드", "종목", "분류", "코드", "종목", "분류"],
        [[names.ticker[i], names.name[i], cats[names.category[i]], names.ticker[i + 10], names.name[i + 10], cats[names.category[i + 10]]]
         for i in range(10)],
        widths=[1.4, 4.0, 2.6, 1.4, 4.2, 2.6], size=7.8,
        src="출처: research/svr_garch_cusum_etf/reference_close_sha256.csv. KOSPI200 그룹(동일 기초지수) = 069500·102110·122630(2배)·114800(−1배).")
    tab(doc, "데이터 사양", ["항목", "내용"], [
        ["출처", "FinanceDataReader 0.9.202 (KRX ETF 일봉). 원시 시세는 저장소에 넣지 않음 (SA/ETF_EDA_SCAFFOLD/data/raw, ETF_RAW_DIR)"],
        ["기간·관측 수", f"종가 2019-01-02~2026-10-02 → 공통 거래일 수익률 {v('n_returns')}개 ({v('first_last')})"],
        ["변환", "y_t = 100·Δlog(종가). 261240은 데이터 품질 문제 2일(2019-03-14·15)을 NaN 처리"],
        ["버전 확인", f"Date,Close 원문 sha256 20/20을 기준표와 대조, 다르면 실행 중단 · data_version {v('data_version')}"],
        ["분할", f"시간순 앞 70% 적합 (학습 {v('n_train')} / 검증 {v('n_val')}) · 뒤 30% 검정 {v('n_test')}일, 분할일 {v('split_date')}"],
    ], widths=[3.0, 13.2], size=8.3)
    P(doc, f"그림 {F('fig11_vol_overview.png')}는 각 ETF의 변동성을 두 구간으로 나눠 비교한다. 20종 중 {v('vol_test_gt_fit')}종은 검정 구간(2024-05 이후)의 변동성이 "
      f"적합 구간보다 높고, 검정/적합 비의 중앙값은 {v('vol_ratio_median')}다. 예를 들어 KODEX 200은 연율화 {v('vol_069500_fit')}%에서 {v('vol_069500_test')}%로 올랐다. "
      "즉 검정 구간 자체가 높은 변동성 국면을 포함한다. 채권·단기채·달러 ETF는 변동성이 낮고 거의 변하지 않았다.")
    fig(doc, "fig11_vol_overview.png", "ETF 20종의 연율화 변동성 — 적합 구간 대 검정 구간",
        "출처: outputs/cache/t11_state.npz 수익률 (scripts/04_figures.py fig11). 단위: %/년, 로그 축. 주의: 단순 표준편차로, 변동성 군집을 고려한 값이 아니다.", width=13.0)
    H2(doc, "3.2 실험 설계와 파라미터")
    tab(doc, "T11 사전 고정 설계 (첫 실행 전 결정, 이 보고서에서 변경하지 않음)", ["요소", "설정", "원문 대비"], [
        ["변동성 proxy", "σ̃²_t = (y²_t + … + y²_{t−4})/5 (m=5)", "원문 정의 이식 (Track B 모듈 바이트 동일)"],
        ["SVR", "ε-SVR, RBF, 입력 (y²_{t−1}, σ̃²_{t−1}), 입력·출력 표준화", "원문 Step 1–5 이식"],
        ["초모수 grid", "C∈{1,10,100} × γ²∈{0.1,0.5,1} × ε∈{0.1,0.5,1} = 27점, 검증 MAE 최소", f"원문 대비 grid 범위는 T11 선택. ε는 20종 모두 하한 0.1 선택 ({v('grid_eps_floor')}/20)"],
        ["분할", "전체 70% 적합 / 30% 검정, 적합 내부 70/30", "원문은 50/50 → 적합 내부 70/30. T11 프로토콜"],
        ["검정 구간 분산 입력", "정책 A: 관측 proxy (1차) · 정책 B: 재귀 예측 σ̂² (민감도)", "원문 미명시 (Track B UNRESOLVED)"],
        ["기준선", "ε_t = r_t/σ_{t−1}(60), 모형 없음 (min_periods 40)", "T11 추가"],
        ["임계값", "원문 1.3397 · ETF 별 iid 부트스트랩 95% (적합 잔차 5,000회) · iid N(0,1) MC 95% (20,000회)", "1.3397은 원문 표기값"],
        ["이동창", "w∈{20,30,60,120,252}, 유효 관측 ≥0.9w, 경보 사이 공백 ≤5일이면 한 에피소드", "T11 추가"],
        ["seed", "20261012 (파생 seed는 [seed, w, salt] 형식)", "—"],
    ], widths=[3.0, 8.0, 5.2], size=7.8,
        src="출처: research/svr_garch_cusum_etf/README.md §1, src/r2h/svrgarch_etf/model.py·rolling.py, results/run_manifest.json.")
    H2(doc, "3.3 이 보고서의 실행 구분")
    tab(doc, "실행 구분과 산출물 위치", ["구분", "내용", "산출물"], [
        ["재계산 (VERIFIED)", "캐시 잔차(t11_state.npz)에서 사후 검정·임계값·이동창·귀무 경보율·연도 블록을 다시 계산해 결과표와 대조. 구간별 분모 분리", "analysis/*.csv, recompute_claims.json"],
        ["재실행 (VERIFIED)", "같은 커밋의 오토런을 루트 .venv와 uv 잠금 환경에서 각각 실행, 결과표 9종 바이트 비교, 단위 테스트", "analysis/repro_logs/"],
        ["EXTENSION E1–E6", "잔차 수준 크기, 파이프라인 크기·검정력, stationary bootstrap 귀무, 시점 무결성, 정책 B 이동창, 잔차 제곱 의존성", "extension/*.csv·json"],
        ["NOT_REEXECUTED", "Track B 원 논문 Monte Carlo 전체(n=1000/2000, raise·recursive 1,000회)와 실증 3종 재실행", "기존 감사 결과 인용 (REPORTED)"],
    ], widths=[3.2, 9.0, 4.0], size=7.8)
    P(doc, "확장 실험은 실행 전에 실험 기록(experiments.md T11 카드 E1–E6)에 데이터 생성 과정, 반복 수, seed, 변화 강도를 먼저 적었다. "
      "E6은 E1–E5 결과를 본 뒤 기전 확인을 위해 추가했으며, 그 사실을 기록에 남겼다.")

    # ───────────────────────── 4
    H1(doc, "4. SVR–GARCH CUSUM의 이론적 구조")
    H2(doc, "4.1 조건부분산 추정")
    P(doc, "수익률 y_t의 조건부분산을 GARCH(1,1)의 비모수 대응으로 추정한다. 관측 불가능한 과거 분산 대신 이동 제곱 평균 proxy를 쓴다.")
    equation(doc, r"\tilde{\sigma}_t^2=\frac{1}{m}\sum_{j=0}^{m-1}y_{t-j}^2,\quad m=5", 1)
    equation(doc, r"\hat{\sigma}_t^2=\hat{g}\left(y_{t-1}^2,\tilde{\sigma}_{t-1}^2\right)", 2)
    P(doc, "ĝ는 적합 구간에서 학습한 ε-SVR(RBF 커널) 회귀함수다. 입력은 전날 수익률 제곱과 전날 proxy이고, 목표는 당일 proxy σ̃²_t이다. "
      "정책 A는 검정 구간에서도 식 (2)의 둘째 입력에 관측 proxy를 넣는다. 정책 B는 그 자리에 직전 예측값 σ̂²_{t−1}을 재귀로 넣는다. "
      "원 논문은 검정 구간의 입력을 명시하지 않았다 (Track B 감사, UNRESOLVED).")
    H2(doc, "4.2 표준화 잔차")
    equation(doc, r"\hat{\varepsilon}_t=\frac{y_t}{\hat{\sigma}_t}", 3)
    P(doc, "조건부분산 모형이 맞다면 ε̂_t는 근사적으로 평균 0, 분산 1인 독립 혁신이다. 검정은 이 표준화된 잔차의 제곱 수준이 표본 안에서 "
      "변했는지를 묻는다. 따라서 결과는 표준화에 쓴 σ̂_t에 직접 의존한다 (모형 의존성, 5.2–5.3절).")
    H2(doc, "4.3 CUSUM-of-squares 검정통계량과 가설")
    equation(doc, r"T_n=\mathrm{max}_{1\le k\le n}\frac{\left|\sum_{t=1}^{k}\hat{\varepsilon}_t^2-\frac{k}{n}\sum_{t=1}^{n}\hat{\varepsilon}_t^2\right|}{\sqrt{n}\,\hat{\tau}}", 4)
    equation(doc, r"\hat{\tau}^2=\frac{1}{n}\sum_{t=1}^{n}\hat{\varepsilon}_t^4-\left(\frac{1}{n}\sum_{t=1}^{n}\hat{\varepsilon}_t^2\right)^2,\qquad \hat{k}=\mathrm{argmax}_{k}\left|\sum_{t=1}^{k}\hat{\varepsilon}_t^2-\frac{k}{n}\sum_{t=1}^{n}\hat{\varepsilon}_t^2\right|", 5)
    P(doc, "**변수.** n은 검정 표본 길이(이 보고서의 사후 검정에서 571), k는 후보 분할 위치, τ̂²은 ε̂² 의 표본분산(분모 n)이다.")
    P(doc, "**가설.** 귀무가설 H₀은 '검정 구간 전체에서 ε²_t의 기대값이 일정하다(잔차 분산 불변)'이다. 대립가설 H₁은 '어떤 k*에서 그 기대값이 바뀐다'이다.")
    P(doc, "**통계량이 커지는 이유.** 분자는 첫 k개 제곱합에서 전체 평균에 비례한 몫을 뺀 중심화 누적합이다. 분산이 일정하면 이 경로는 0 근처를 "
      "오가며 끝점 k=n에서 정확히 0이 된다. 분산이 k*에서 바뀌면 경로가 k* 전까지 한 방향으로 쌓여 큰 절대값에 이른다. "
      "k̂는 그 최대점이며, 표본 전체를 본 뒤에야 정해지는 사후 추정치다.")
    fig(doc, "fig10_cusum_toy.png", "CUSUM-of-squares 검정의 작동 원리 (교육용 합성 예시)",
        "출처: scripts/04_figures.py fig10 (seed [20261012,10]). 회색 = 분산 불변, 파랑 = 251번째부터 표준편차 1.6배. 가운데 패널의 검은 실선은 ±1.3397, 파란 점선은 실제 변화 시점이다. "
        "주의: 실제 ETF 자료가 아닌 설명용 예시다.")
    H2(doc, "4.4 점근분포와 임계값 — 적용 가능성 감사")
    P(doc, f"ε̂²가 독립이고 4차 적률이 유한하면 H₀ 아래에서 T_n은 표준 브라운 다리 B°의 sup|B°(s)| (Kolmogorov 분포)로 수렴한다는 것이 CUSUM-of-squares의 "
      f"표준 결과다 [INFERRED: 일반 결과, 이 작업에서 원 논문 정리의 조건을 재검토하지 않음]. 이 분포의 95% 분위는 {v('kolmogorov_q95')}이다 [VERIFIED: 급수 직접 계산]. "
      f"코드와 Track B가 쓰는 원문 임계값은 {v('paper_cv')}이다 [REPORTED]. 이를 Kolmogorov 분포로 읽으면 상측 확률은 {v('paper_cv_implied_level')}다. "
      "원문 값의 유도 근거는 확인하지 못했다 [UNRESOLVED]. 이 보고서는 두 값을 모두 병기한다. 판정이 갈리는 경우는 5.1절에 적었다.")
    P(doc, "점근 근사의 적용에는 세 가지 감사 사항이 있다.")
    bullets(doc, [
        f"**유한표본.** iid N(0,1)에서 n=571의 MC 95% 분위는 {v('c_normal_n571')}이고, w=20의 분위는 {v('crit_normal_w20')}다. 짧은 창에 점근값을 쓰면 크게 보수적이다 (6.2절). [VERIFIED]",
        "**의존성.** τ̂²는 ε̂²가 독립일 때의 분산이다. ε̂²에 자기상관이 남으면 분자의 장기분산과 τ̂²가 어긋나 크기가 틀어진다. 양의 자기상관이면 과대기각, 음의 자기상관이면 과소기각이다 (6.4절). [INFERRED·E6로 확인]",
        "**추정 효과.** ε̂_t는 추정된 ĝ로 만든 잔차다. 적합 구간의 ĝ를 고정하고 검정 구간에 적용하므로, 검정 구간의 잔차는 ĝ 추정 오차를 공통으로 지닌다. 그 효과는 합성 자료 실험으로만 평가했다 (6.3절). [EXTENSION]",
    ])
    H2(doc, "4.5 이동창 반복 검정")
    equation(doc, r"T_t(w)=T_{n}\left(\hat{\varepsilon}_{t-w+1},\ldots,\hat{\varepsilon}_t\right),\qquad \text{alarm}_t=\mathbf{1}\left\{T_t(w)\ge c_w\right\}", 6)
    P(doc, "T11은 식 (4)를 길이 w의 창 [t−w+1, t]에 반복 적용했다. 시점 t의 통계량은 t까지의 관측만 쓰므로 실시간으로 계산할 수 있다. "
      "그러나 같은 날을 공유하는 창들이 강하게 겹치므로, 각 창의 5% 임계값을 매일 적용하면 연간 경보 수는 5%×252와 무관하게 결정된다. "
      "이 반복 검정의 귀무 오탐 빈도는 별도로 보정해야 한다. T11은 적합 구간 잔차를 iid로 재표집한 경로에서 연간 에피소드 기대값을 구했다 (5.4절). "
      "'실시간 계산 가능'은 '온라인 검출 성능 검증'과 같지 않다.")

    # ───────────────────────── 5
    H1(doc, "5. ETF 20종 적용 결과")
    H2(doc, "5.1 전체 검정 구간 사후 검정")
    P(doc, f"캐시 잔차에서 검정 구간 통계량을 다시 계산했다. 결과표와의 차이는 최대 {v('fs_max_abs_diff')}이고, k̂ 일치 {v('fs_khat_match')}/60, "
      f"기각 판정 일치 {v('fs_reject_match')}/60이다 [VERIFIED]. 표 {TABN[0] + 1}은 임계값 정의별 기각 수다.")
    tab(doc, "사후 검정 기각 수 (20종 중, 검정 구간 n=571)", ["잔차", "원문 1.3397", "Kolmogorov 1.3581", f"iid N(0,1) MC ({v('c_normal_n571')})", "ETF 별 iid 부트스트랩 (EXTENSION)", "T 중앙값"], [
        ["정책 A", v("fs_reject_A"), v("fs_reject_A_kolm"), v("fs_reject_A_normal"), v("fs_reject_A_boot"), v("fs_T_median_A")],
        ["정책 B", v("fs_reject_B"), v("fs_reject_B_kolm"), v("fs_reject_B_normal"), v("fs_reject_B_boot"), v("fs_T_median_B")],
        ["기준선", v("fs_reject_base"), v("fs_reject_base_kolm"), v("fs_reject_base_normal"), v("fs_reject_base_boot"), v("fs_T_median_base")],
    ], widths=[2.0, 2.2, 2.6, 2.8, 4.2, 2.2], size=8.2, align=["l", "c", "c", "c", "c", "c"],
        src="출처: analysis/fullsample_recomputed.csv (01_recompute.py). 부트스트랩 임계값은 그 ETF의 적합 구간 잔차(정책 B는 정책 A 잔차)를 n_test 길이로 iid 재표집 5,000회 한 95% 분위.")
    P(doc, f"정책 A의 기각은 {v('fs_rejected_A')}, 정책 B는 {v('fs_rejected_B')}, 기준선은 {v('fs_rejected_base')}다. 091230은 1.3397로는 기각, "
      f"1.3581로는 비기각이다. 정책 A의 k̂는 20종 중 {v('fs_A_khat_2026_01')}종이 2026년 1월에 있다. 이는 사후 추정 위치이며 그 시점에 실시간으로 "
      "검출되었다는 뜻이 아니다. 정책 B의 기각 수가 많다는 사실만으로 정책 B가 더 정확하다고 판단하지 않는다. 그 이유는 6.3절의 크기 실험에 있다.")
    fig(doc, "fig02_fullsample_T.png", "ETF 20종 사후 검정통계량 (정책 A·B·기준선)",
        "출처: analysis/fullsample_recomputed.csv. 조건: 검정 구간 2024-05-29~2026-10-02 (n=571). 채운 마커는 1.3397 이상이며, 색이 아니라 채움으로 기각을 구분한다. "
        "주의: 세 잔차는 서로 다른 표준화이므로 같은 ETF 안에서의 크기 비교는 '통계량 차이'일 뿐 정확도 비교가 아니다.", width=14.5)
    H2(doc, "5.2 정책 A와 B의 대응 비교")
    P(doc, f"같은 ETF에서 정책 B의 통계량이 A보다 큰 경우가 {v('ab_T_B_gt_A')}/20이다. 기각 판정이 엇갈린 ETF는 {v('ab_disagree')}종, "
      f"둘 다 기각한 ETF는 {v('ab_both_reject')}종, k̂가 같은 날인 ETF는 {v('ab_khat_same')}종이다 [VERIFIED]. 검정 구간 σ̂²의 변동계수는 "
      f"20종 모두에서 정책 B가 A보다 작다 ({v('ab_cvB_lt_cvA')}/20, 중앙값 B {v('ab_cv_B_median')} 대 A {v('ab_cv_A_median')}) [VERIFIED]. "
      "재귀 입력은 관측 충격을 늦게 반영해 분산 경로가 평활되고, 그만큼 실제 변동성 변화가 잔차 제곱에 남는다. 정책 B의 큰 통계량은 "
      f"이 덜 된 표준화와 맞는 현상이다 [INFERRED]. 그림 {F('fig07_timeline_069500.png')}의 가운데 패널에서 069500의 두 경로를 비교할 수 있다.")
    pair = pd.read_csv(AN / "policy_pairs.csv", dtype={"ticker": str})
    H2(doc, "5.3 동일 기초지수 ETF의 일관성")
    g = pd.read_csv(AN / "kospi200_group.csv", dtype={"ticker": str})
    tab(doc, "KOSPI200 그룹 4종의 적합 초모수와 검정 결과", ["코드", "종목", "C / γ² / ε", "T_A", "T_B", "T_기준선", "k̂ (A)", "수익률 상관 (vs 069500)", "정책 A 잔차 상관"],
        [[r.ticker, r["name"], f"{r.C:g} / {r.gamma2:g} / {r.epsilon:g}", f"{r.T_A:.3f}", f"{r.T_B:.3f}", f"{r.T_base:.3f}", r.khat_A,
          f"{r.corr_r_vs_069500_test:.4f}", f"{r.corr_eA_vs_069500_test:.4f}"] for _, r in g.iterrows()],
        widths=[1.3, 2.4, 2.1, 1.2, 1.2, 1.4, 2.0, 2.3, 2.3], size=7.6, align=["l", "l", "c", "r", "r", "r", "c", "r", "r"],
        src="출처: analysis/kospi200_group.csv (상관은 검정 구간). 122630(2배)·114800(−1배)은 수익률 규모가 달라 상관만 비교 대상이다.")
    P(doc, f"KODEX 200(069500)과 TIGER 200(102110)은 검정 구간 수익률 상관이 {v('k200_corr_r')}로 사실상 같은 시계열이다. 정책 A 잔차 상관도 "
      f"{v('k200_corr_eA')}다. 그런데 사후 통계량은 {v('k200_TA_069500')} (기각) 대 {v('k200_TA_102110')} (비기각)이다. 두 ETF의 SVR 초모수는 "
      f"{v('k200_params_069500')} 대 {v('k200_params_102110')}로, 검증 MAE 차이가 작은 grid 선택에서 갈렸다. 검정 구간에서 두 ETF의 σ̂ 비는 "
      f"5% 분위 {v('k200_sigma_ratio_p05')}, 95% 분위 {v('k200_sigma_ratio_p95')}다. TIGER 200의 ĝ는 2026년 고변동기에 σ̂를 더 크게 추정해 잔차 "
      f"제곱을 더 많이 눌렀다 (그림 {F('fig06_kospi200_pair.png')}). 이동창(w=60) 통계량의 상관도 "
      f"{v('k200_roll60_corr')}에 그친다 [VERIFIED]. 사실상 같은 자료에서 기각 여부가 바뀐다는 것은, 결과가 시장 자료보다 ĝ의 선택에 크게 의존함을 보여 준다 [INFERRED].")
    fig(doc, "fig06_kospi200_pair.png", "KODEX 200 대 TIGER 200 — 검정 구간 σ̂_t와 정규화 CUSUM 경로",
        "출처: outputs/cache/t11_state.npz (varA, res svrA), results/fit_summary.csv. 조건: 정책 A, 검정 구간. 주의: 경로의 절대값 최대가 T_n이며, "
        "최대 위치(k̂)는 사후 추정이다.")
    H2(doc, "5.4 관측창별 경보 빈도와 분모")
    P(doc, f"기존 요약값(w=60, 정책 A 0.39 대 귀무 1.71, 기준선 3.82 대 1.70)의 분모는 {v('rate_denominator')}이다 [VERIFIED: pipeline.py obs_rate]. "
      f"이 값은 정책 A의 in-sample 적합 구간과 out-of-sample 검정 구간의 경보를 함께 센다. 표 {TABN[0] + 1}은 두 구간을 분리했다. 검정 구간은 창 전체가 "
      "검정 구간에 들어간 날(분할일+w−1)부터 센다. 창이 두 구간에 걸친 경보(boundary)는 두 구간 어디에도 넣지 않았다.")
    rows = []
    for rt, lab in (("svrA", "정책 A"), ("base", "기준선")):
        for w in (20, 30, 60, 120, 252):
            p = f"rate_{rt}_w{w}"
            rows.append([lab, w, v(f"{p}_all"), v(f"{p}_fit"), v(f"{p}_test"), v(f"{p}_null"), v(f"{p}_test_gt_null"), v(f"{p}_test_zero")])
    tab(doc, "연간 경보 에피소드 (20종 평균, 회/년)", ["잔차", "w", "전 기간", "적합 구간 (in-sample)", "검정 구간 (OOS)", "iid 귀무 기대", "검정>귀무 ETF 수", "검정 경보 0건 ETF 수"],
        rows, widths=[1.6, 1.0, 1.6, 2.4, 2.2, 2.0, 2.6, 2.6], size=7.8, align=["l", "c", "r", "r", "r", "r", "c", "c"],
        src="출처: analysis/zone_rates.csv (01_recompute.py). 임계값은 ETF 별 iid 부트스트랩 95%. 귀무 기대는 results/null_alarm_rate.csv (100회 모의, 재계산 차이 최대 "
            f"{v('null_max_diff')}회/년 — CSV 임계값 반올림으로 경계 사례가 바뀐 것).")
    P(doc, f"정책 A의 w=60 경보는 적합 구간 {v('rate_svrA_w60_fit')}, 검정 구간 {v('rate_svrA_w60_test')}회/년이다. 검정 구간에서 경보가 0건인 ETF가 "
      f"{v('rate_svrA_w60_test_zero')}종이다. 기준선은 검정 구간 {v('rate_base_w60_test')}회/년으로, 20종 중 {v('rate_base_w60_test_gt_null')}종이 귀무 기대를 넘는다. "
      f"창이 길수록 임계값이 점근값에 다가가고 경보는 줄어든다 (그림 {F('fig03_critical_values.png')}, 그림 {F('fig04_alarm_rates.png')}).")
    P(doc, "**해석상 주의.** 정책 A의 경보가 iid 귀무 기대보다 적다는 사실은 낮은 실제 오탐률을 뜻하지 않는다. iid 재표집 귀무는 잔차 제곱의 "
      "시계열 의존성을 지운다. 6.4절에서 보듯 정책 A 잔차 제곱의 음의 자기상관은 통계량을 체계적으로 누른다. 기준선이 귀무 기대를 넘는 것도 "
      "구조변화의 증거가 아니다. 기준선 잔차 제곱의 양의 자기상관(변동성 군집)과 맞는 현상이다 [INFERRED].")
    fig(doc, "fig03_critical_values.png", "관측창 길이별 5% 임계값", "출처: results/critical_values.csv (재계산 차이 최대 "
        f"{v('crit_max_abs_diff')}). 조건: 부트스트랩 5,000회, MC 20,000회, seed 20261012. 주의: 부트스트랩 값은 적합 구간 잔차의 주변분포만 보존한다.", width=13.5)
    fig(doc, "fig04_alarm_rates.png", "관측창별 경보 빈도 — 적합·검정 구간 분리와 iid 귀무 기대",
        "출처: analysis/zone_rates.csv. 단위: 연간 경보 에피소드 (경보 사이 공백 ≤5일 → 한 에피소드). 주의: 귀무 기대는 iid 재표집으로 계산해 시계열 의존성을 반영하지 않는다.")
    fig(doc, "04_rolling_heatmaps.png", "이동창 통계량/임계값 지도 (기존 T11 그림 재사용)",
        "출처: docs/figures/svrgarch/04_rolling_heatmaps.png (T11 노트북, 커밋 a346faf). 색이 진할수록 T_t(w)/c_w가 크며 1 이상이 경보다. 청록 세로선은 적합/검정 분할. "
        "주의: 분할선 왼쪽의 정책 A 값은 in-sample이다.", folder=OLDFIG)
    H2(doc, "5.5 연도 블록과 종목별 시계열 진단")
    P(doc, f"달력연도별 사후 검정(1.3397)에서 기준선은 2020년 {v('yearly_base_2020')}%, 2026년 {v('yearly_base_2026')}%의 ETF가 기각된다. "
      f"정책 A는 2020년 {v('yearly_svrA_2020')}%, 2022년 {v('yearly_svrA_2022')}%이고 나머지 해는 0%다 [VERIFIED, 재계산 차이 최대 {v('yearly_max_abs_diff')}]. "
      "2019–2023년 블록은 정책 A의 적합 구간이므로 in-sample이다. 기준선의 2019년은 60일 초기화 때문에 비어 있다.")
    fig(doc, "10_yearly_blocks.png", "연도 블록 사후 통계량 (기존 T11 그림 재사용)",
        "출처: docs/figures/svrgarch/10_yearly_blocks.png, results/yearly_blocks.csv. 굵은 숫자는 1.3397 이상이다. 주의: 연도 안 표본 길이가 약 245일로 서로 다르며, 정책 A 2019–2024년 5월은 in-sample이다.", folder=OLDFIG)
    fig(doc, "fig07_timeline_069500.png", "적합·검정 구간을 분리한 시계열 진단 (069500 KODEX 200)",
        "출처: t11_state.npz, results/critical_values.csv. 위: 일간 수익률, 가운데: 세 가지 조건부 표준편차, 아래: w=60 통계량/ETF 별 임계값. "
        "주의: 회색 구간의 정책 A 값은 ĝ를 그 구간으로 학습한 in-sample 값이다.")

    # ───────────────────────── 6
    H1(doc, "6. 통계적 타당성과 강건성")
    H2(doc, "6.1 계산 재현성")
    P(doc, f"기준 커밋 {SHA[:7]}에서 오토런(scripts/run_svr_garch_cusum_etf.py)을 두 번 실행했다. 첫째는 루트 .venv (numpy 2.4.6, pandas 3.0.3, "
      "scikit-learn 1.9.0), 둘째는 저장소의 uv.lock 환경 (numpy 2.5.4, pandas 3.0.6, scikit-learn 1.9.1)이다. 두 실행 모두 결과표 9종이 "
      "커밋된 파일과 바이트 단위로 같았다. run_manifest.json은 실행 시간과 패키지 버전 필드만 달랐다. 캐시 상태 파일(t11_state.npz)도 바이트가 같았다. "
      "uv 잠금 환경의 단위 테스트는 98개 모두 통과했다. 루트 .venv에서는 hypothesis 미설치로 테스트를 수집하지 못했다 (환경 문제, 기록 보존) [VERIFIED].")
    P(doc, "이것은 '같은 코드와 같은 자료로 같은 숫자가 나온다'는 결정성의 확인이다. 원 논문 수치의 재현 성공과는 별개다 (6.9절).")
    H2(doc, "6.2 잔차 수준 크기 (E1)")
    e1 = pd.read_csv(EXT / "E1_residual_size.csv")
    piv = e1.pivot_table(index=["dgp", "n"], columns="critical", values="reject_rate").reset_index()
    lab = {"iid_normal": "iid N(0,1)", "iid_t5": "iid t₅ (분산 1)", "garch_unstandardized": "GARCH(1,1) 미표준화"}
    tab(doc, "CUSUM-of-squares 통계량의 경험적 크기 (%, R=10,000, EXTENSION E1)", ["자료 생성 과정", "n", "1.3397", "1.3581", "N(0,1) MC 95%"],
        [[lab[r.dgp], int(r.n), f"{100 * r['paper_1.3397']:.1f}", f"{100 * r['kolmogorov_1.3581']:.1f}", f"{100 * r['normal_mc95']:.1f}"] for _, r in piv.iterrows()],
        widths=[5.0, 1.5, 2.4, 2.4, 3.2], size=8.2, align=["l", "c", "r", "r", "r"],
        src="출처: extension/E1_residual_size.csv. seed [20261012,1,n,·]. MC 표준오차 ≤0.4%p. GARCH: ω=0.05, α=0.08, β=0.90, 정규 혁신, burn-in 500.")
    P(doc, f"iid 정규 잔차에서 n=571의 크기는 명목 5%에 가깝다 ({v('E1_iid_normal_n571_paper')}%, 1.3397). 두꺼운 꼬리(t₅)는 τ̂를 키워 크기를 "
      f"{v('E1_iid_t5_n571_paper')}%로 낮춘다. n=60에서 점근값을 쓰면 크기가 {v('E1_iid_normal_n60_paper')}%로 줄어든다. 조건부 이분산을 지우지 않은 GARCH "
      f"수익률에서는 크기가 {v('E1_garch_unstandardized_n571_paper')}%로 무너진다. 변동성 군집을 그대로 두면 이 검정은 거의 항상 기각한다. "
      "이것이 조건부분산 표준화가 필요한 이유이자, 표준화의 질이 결과를 좌우하는 이유다 [VERIFIED·EXTENSION].")
    H2(doc, "6.3 파이프라인 전체의 크기와 검정력 (E2)")
    P(doc, f"T11 파이프라인(fit_etf: grid 선택, 정책 A·B, 기준선)을 합성 GARCH(1,1) 경로에 그대로 적용했다. n=1,902, 70/30 분할은 실제와 같다. "
      f"귀무는 구조변화가 없는 경로, 대립은 검정 구간 286번째 날부터 ω를 3배로 바꾼 경로(무조건분산 3배)다. 시나리오마다 R={v('E2_R')}회를 반복했다. "
      f"합성 자료에서도 ε grid 하한 0.1이 {v('E2_eps_floor_share')}%의 반복에서 선택되었다.")
    tab(doc, "합성 GARCH에서의 파이프라인 크기·검정력 (EXTENSION E2, R=500/시나리오)", ["측정", "정책 A", "정책 B", "기준선"], [
        ["사후 검정 크기 (귀무, 1.3397, %)", v("E2_null_A_rej13397"), v("E2_null_B_rej13397"), v("E2_null_base_rej13397")],
        ["사후 검정 크기 (귀무, 1.3581, %)", v("E2_null_A_rej13581"), v("E2_null_B_rej13581"), v("E2_null_base_rej13581")],
        ["사후 검정 검정력 (ω×3, 1.3397, %)", v("E2_break_A_rej13397"), v("E2_break_B_rej13397"), v("E2_break_base_rej13397")],
        ["w=60 귀무 연간 경보 에피소드 (검정 구간)", v("E2_null_A_w60_test_episodes_per_year"), v("E2_null_B_w60_test_episodes_per_year"), v("E2_null_base_w60_test_episodes_per_year")],
        ["w=60 귀무에서 검정 구간 경보가 1건 이상인 반복 (%)", v("E2_null_A_w60_test_any_alarm_share"), v("E2_null_B_w60_test_any_alarm_share"), v("E2_null_base_w60_test_any_alarm_share")],
        ["w=60 변화 전 연간 경보 에피소드 (대립)", v("E2_break_A_w60_prebreak_episodes_per_year"), v("E2_break_B_w60_prebreak_episodes_per_year"), v("E2_break_base_w60_prebreak_episodes_per_year")],
        ["w=60 변화 후 20일 안 첫 경보 (%)", v("E2_break_A_w60_detect_within_20d"), v("E2_break_B_w60_detect_within_20d"), v("E2_break_base_w60_detect_within_20d")],
        ["w=60 변화 후 60일 안 첫 경보 (%)", v("E2_break_A_w60_detect_within_60d"), v("E2_break_B_w60_detect_within_60d"), v("E2_break_base_w60_detect_within_60d")],
        ["w=60 검정 구간 끝까지 첫 경보 (%)", v("E2_break_A_w60_detect_share_by_end"), v("E2_break_B_w60_detect_share_by_end"), v("E2_break_base_w60_detect_share_by_end")],
        ["w=60 첫 경보 지연 중앙값 (거래일, 경보 있는 반복)", v("E2_break_A_w60_first_alarm_delay_median_days"), v("E2_break_B_w60_first_alarm_delay_median_days"), v("E2_break_base_w60_first_alarm_delay_median_days")],
    ], widths=[7.6, 2.8, 2.8, 2.8], size=8.0, align=["l", "r", "r", "r"],
        src="출처: extension/E2_pipeline_size_power_summary.csv·_reps.csv. MC 표준오차: 비율 p에 대해 √(p(1−p)/500) ≤ 2.2%p. seed [20261012,2,rep,시나리오]. "
            "이동창 임계값은 반복마다 적합 구간 잔차 iid 부트스트랩 2,000회 95%.")
    P(doc, "세 잔차 가운데 크기와 검정력을 함께 만족하는 것은 없다 [VERIFIED·EXTENSION].")
    bullets(doc, [
        f"**정책 A**는 크기를 지킨다 ({v('E2_null_A_rej13397')}%). 그러나 분산 3배 변화에 대한 검정력이 {v('E2_break_A_rej13397')}%다. 이동창에서는 "
        f"변화 후 60일 안에 {v('E2_break_A_w60_detect_within_60d')}%만 경보를 낸다. 관측 proxy가 변화를 따라가 표준화 과정에서 흡수하기 때문이다 [INFERRED].",
        f"**정책 B**의 귀무 크기는 {v('E2_null_B_rej13397')}%다. 검정력 {v('E2_break_B_rej13397')}%의 상당 부분이 크기 왜곡과 겹친다. 실제 ETF의 9/20 기각은 "
        "정책 B의 귀무 거짓 기각률과 구별되지 않는다 [INFERRED].",
        f"**기준선**의 귀무 크기는 {v('E2_null_base_rej13397')}%, 검정력은 {v('E2_break_base_rej13397')}%다. 사후 검정으로는 귀무와 대립을 거의 구별하지 못한다. "
        f"이동창에서는 변화를 빨리 잡지만(중앙 지연 {v('E2_break_base_w60_first_alarm_delay_median_days')}일), 귀무에서도 연 {v('E2_null_base_w60_test_episodes_per_year')}회 경보를 낸다.",
    ])
    fig(doc, "fig05_size_power.png", "합성 GARCH(1,1)에서의 파이프라인 크기·검정력과 첫 경보 시점",
        "출처: extension/E2_*. 조건: ω=0.05, α=0.08, β=0.90, 정규 혁신, 대립은 검정 구간 286번째 날부터 ω×3. 오차막대는 ±1.96 MC SE이고, 정책 B·기준선은 빗금으로 구분한다. "
        "주의: 하나의 합성 자료 생성 과정에서 얻은 결과다. 실제 ETF의 생성 과정을 대표한다고 가정하지 않는다.")
    H2(doc, "6.4 잔차 제곱의 의존성 (E6)")
    P(doc, f"검정 분모 τ̂²는 독립을 가정한 분산이다. ε̂² 의 Bartlett 장기분산(대역폭 h=⌊4(n/100)^{{2/9}}⌋)과 τ̂²의 비를 계산했다. 실제 ETF에서 정책 A "
      f"잔차의 비는 적합 구간 중앙값 {v('E6_svrA_fit_lrv')} ({v('E6_svrA_fit_lt1')}/20이 1 미만), 검정 구간 {v('E6_svrA_test_lrv')} "
      f"({v('E6_svrA_test_lt1')}/20)다. lag 1–5 자기상관 합의 중앙값은 검정 구간 {v('E6_svrA_test_acf')}이다. 합성 GARCH 귀무에서도 정책 A의 비는 중앙값 "
      f"{v('E6_sim_A_lrv')}이고 100회 모두 1 미만이다. 반대로 기준선은 검정 구간 중앙값 {v('E6_base_test_lrv')} (1 미만 {v('E6_base_test_lt1')}/20)로 "
      f"양의 의존이 남는다. 정책 B는 실제 ETF 검정 구간에서 {v('E6_svrB_test_lrv')}다 [VERIFIED·EXTENSION].")
    P(doc, "**기전.** 정책 A의 σ̂²_t는 직전 5일 제곱 수익률 proxy를 입력으로 받는다. 큰 충격 다음 날들은 σ̂가 커져 ε̂²가 작아진다. 그래서 큰 ε̂² 뒤에 "
      "작은 ε̂²가 오는 음의 자기상관이 생긴다. 장기분산이 τ̂²보다 작으므로 식 (4)의 정규화가 과대해지고 검정이 보수적이 된다. 정책 A의 낮은 경보 "
      "빈도와 낮은 검정력이 이 기전과 맞는다 [INFERRED]. 정책 B의 크기 왜곡은 장기분산 비가 1 근처(합성 중앙값 "
      f"{v('E6_sim_B_lrv')})인데도 나타난다. 따라서 의존성보다는 재귀 예측이 실제 분산 수준을 따라가지 못해 생기는 잔차 분산 수준의 이동으로 보는 편이 맞다 [INFERRED].")
    H2(doc, "6.5 귀무 생성 방법의 민감도 (E3)")
    P(doc, f"T11의 1차 임계값은 적합 구간 잔차를 독립으로 재표집한다. 귀무를 '정상 의존 과정'으로 바꾸어 평균 블록 길이 20의 stationary bootstrap으로 "
      f"임계값을 다시 구했다. n=571 임계값의 중앙값은 iid {v('E3_c571_iid_median')}에서 {v('E3_c571_sb_median')}로 내려간다. 정책 A 기각은 iid 기준 "
      f"{v('E3_reject_iid')}, stationary bootstrap 기준 {v('E3_reject_sb')}로, 겹치는 것은 {v('E3_reject_both')}종뿐이다. 검정 구간 w=60 경보 빈도는 "
      f"평균 {v('E3_rate_iid')}에서 {v('E3_rate_sb')}회/년으로 늘어난다. 153130 (단기채)은 양의 의존이 강해 임계값이 {v('E3_c571_sb_153130')}로 올라간다 [VERIFIED·EXTENSION].")
    P(doc, "이것은 개선이 아니다. iid 재표집은 '잔차가 독립'이라는 귀무를, stationary bootstrap은 '적합 구간과 같은 의존 구조를 가진 정상 과정'이라는 "
      "다른 귀무를 검정한다. 블록 재표집은 적합 구간 잔차의 의존 구조를 귀무에 넣으므로, 적합 구간 자체에 구조변화가 있으면 그것까지 귀무로 흡수한다. "
      f"어느 귀무가 맞는지는 자료로 정할 수 없으며, 기각 집합이 귀무 정의에 따라 절반 바뀐다는 것 자체가 결과다 (그림 {F('fig08_dependence_and_null.png')} 오른쪽).")
    fig(doc, "fig08_dependence_and_null.png", "잔차 제곱의 의존성(왼쪽)과 귀무 생성 방법에 따른 임계값(오른쪽)",
        "출처: extension/E6_residual_dependence_*.csv, extension/E3_stationary_bootstrap.csv. 왼쪽: 빈 원 = 적합 구간, 채운 원 = 검정 구간, 가로선 = 중앙값, 상자 = 합성 GARCH 귀무 100회. "
        "주의: 오른쪽의 두 임계값은 서로 다른 귀무가설에 대한 값이다.")
    H2(doc, "6.6 정책 B 이동창 (E5)")
    P(doc, f"검정 구간 w=60에서 정책 A 대신 정책 B 잔차를 쓰고 같은 임계값을 적용하면, 연간 경보는 평균 {v('E5_rate_A')}에서 {v('E5_rate_B')}회로 늘어난다. "
      f"검정 구간 경보가 0건인 ETF는 {v('E5_zero_A')}종에서 {v('E5_zero_B')}종이 된다 [VERIFIED·EXTENSION]. E2의 귀무에서 정책 B가 연 "
      f"{v('E2_null_B_w60_test_episodes_per_year')}회 경보를 낸 것과 같은 크기라서, 늘어난 경보를 탐지력의 증거로 볼 수 없다 [INFERRED].")
    H2(doc, "6.7 시점 무결성과 정보 누수 (E4)")
    P(doc, f"069500의 검정 구간 안 시점 t₀={v('E4_t0')} 이후 수익률만 3배로 바꾸고 전체 파이프라인을 다시 실행했다. ĝ는 그대로였다. t₀ 이전의 정책 A·B 잔차, "
      f"기준선 잔차, 그리고 다섯 개 창의 이동창 통계량이 모두 비트 단위로 같았다 ({v('E4_identical')}) [VERIFIED·EXTENSION]. 검정 구간 안에서 미래 관측은 "
      "과거 판단에 들어가지 않는다.")
    P(doc, "대조 실험으로 적합 구간 일부를 교란하면 ĝ와 검정 구간 잔차가 모두 바뀌었다. 적합 구간 전체로 ĝ를 추정하는 설계상, 적합 구간 안의 정책 A "
      "잔차와 경보는 그 구간의 미래 정보를 쓴 in-sample 값이다 (파라미터 look-ahead). 이는 결함이 아니라 설계의 속성이다. 따라서 적합 구간의 "
      "경보 빈도를 out-of-sample 성능으로 쓰지 않는다 (5.4절).")
    H2(doc, "6.8 다중 ETF와 다중 창의 의존")
    P(doc, f"20종 ETF는 서로 독립인 표본 20개가 아니다. KOSPI200 그룹 4종은 사실상 같은 시계열이고 (069500–102110 상관 {v('k200_corr_r')}), 국내 주식 ETF들은 공통 시장 요인을 "
      "공유한다. 따라서 '20종 중 k종 기각'에 이항검정을 적용하지 않았다. 독립이라면 5% 수준에서 귀무에서도 약 1종이 기각될 것으로 기대되지만, "
      "실제 기대 분포는 ETF 간 의존 때문에 더 넓다. 다섯 개 관측창과 매일 반복 검정 역시 서로 강하게 겹친다. 이번 보고서는 이들을 하나의 "
      "다중검정 가족으로 보정하지 않았다. 대신 개별 결과를 탐색적 기술로만 제시했다.")
    H2(doc, "6.9 원 논문 충실도 (Track B)")
    emp = pd.read_csv(AN / "trackb_empirical.csv").iloc[:9]
    emp = emp[emp.nonpos_policy.eq("clip")]
    tab(doc, "원 논문 실증 통계량과 재현값 (Track B, 자료 출처 대체: Yahoo)", ["계열", "원문 T / 변화점", "재현 정책 A (T / 날짜)", "재현 정책 B (T / 날짜)"], [
        [s, f"{g.paper_T.iloc[0]} / {g.paper_date.iloc[0]}",
         f"{g[g.test_policy.str.startswith('A')].repl_T.iloc[0]} / {g[g.test_policy.str.startswith('A')].repl_date.iloc[0]}",
         f"{g[g.test_policy.str.startswith('B')].repl_T.iloc[0]} / {g[g.test_policy.str.startswith('B')].repl_date.iloc[0]}"]
        for s, g in emp.groupby("series", sort=False)
    ], widths=[2.5, 4.3, 4.6, 4.6], size=8.0,
        src="출처: SA_ETF research/track-b-paper2020@031157d reports/EMPIRICAL_ORIGINAL_VS_REPRODUCED.csv (outputs/cache 사본). REPORTED — 이 작업에서 실증을 재실행하지 않음.")
    mc = CLAIMS["trackb_in_ci"]["value"]
    USED.setdefault("trackb_in_ci", []).append("6.9")
    P(doc, "원문의 세 통계량은 모두 1.3397을 넘는다. 재현값은 두 정책 모두 넘지 않는다. 원문 Monte Carlo 표(n=500, 45셀)의 값이 재현 95% CI 안에 든 셀 수는 "
      f"clip {mc['clip']}, raise {mc['raise']}, recursive {mc['recursive']}다 [REPORTED]. 원 감사는 코드 재실행의 결정성은 확인했지만(같은 seed에서 같은 결과), "
      "원 논문 수치의 재현에는 실패했다. 두 판정은 별개다. 상태는 METHOD_FIDELITY_UNRESOLVED이다. 따라서 이 보고서의 ETF 결과를 '원 논문 방법의 결과'라고 부르지 않는다. "
      "원문 방법을 ETF에 이식한 'T11 프로토콜의 결과'로만 부른다.")

    # ───────────────────────── 7
    H1(doc, "7. 결과의 해석과 연구적 함의")
    H2(doc, "7.1 조건부분산 설명 이후의 구조변화 (RQ1)")
    P(doc, f"정책 A로 표준화한 잔차에서 기각은 {v('fs_reject_A')}/20이다. 그러나 정책 A의 검정력이 낮고 음의 의존 때문에 보수적이므로, 비기각 18종은 '구조변화 없음'의 "
      "증거가 아니다 (원칙 A). 정책 B와 기준선의 기각은 크기 왜곡과 구별되지 않는다. 이번 자료와 설계로는 RQ1에 확정적으로 답할 수 없다 [UNRESOLVED].")
    H2(doc, "7.2 표준화와 정보 손실 (원칙 B)")
    P(doc, "정책 A가 분산 변화를 흡수한다는 것은 E2에서 확인했다. 그러나 이것이 과적합·과도한 평활화의 결과인지, 조건부 이분산을 적절히 제거한 결과인지는 "
      "이번 실험으로 구별되지 않는다. 구별하려면 다음 두 가지가 필요하다. 하나는 표준화 강도를 단계적으로 바꾸는 실험(proxy 창 m, grid 범위)이다. "
      "다른 하나는 조건부 이분산과 구조변화를 함께 넣은 생성 과정이다 [HYPOTHESIS].")
    H2(doc, "7.3 경보 수와 탐지기의 질 (원칙 C)")
    P(doc, f"정책 A의 적은 경보는 좋은 탐지기의 증거가 아니다. 귀무에서도 적고(E2: 연 {v('E2_null_A_w60_test_episodes_per_year')}회), 변화가 있어도 적다(60일 안 {v('E2_break_A_w60_detect_within_60d')}%). 기준선의 많은 경보 역시 "
      f"귀무에서 연 {v('E2_null_base_w60_test_episodes_per_year')}회 수준으로 나온다. 경보 건수는 검정력과 오탐 보정 없이 비교하지 않는다.")
    H2(doc, "7.4 정책 차이와 우월성 (원칙 D)")
    P(doc, f"정책 B는 통계량이 더 크고 더 자주 기각한다. 그러나 귀무 크기가 {v('E2_null_B_rej13397')}%이므로 우월성의 근거가 될 수 없다. 반대로 정책 A가 '보수적이라서 안전하다'고 "
      "말하는 것도 낮은 검정력 앞에서는 의미가 없다. 두 정책은 원문이 명시하지 않은 같은 선택지의 두 해석이며, 결과가 이 선택에 크게 의존한다는 것 "
      "자체가 핵심 결과다.")
    H2(doc, "7.5 금융 급등 탐지와 분산 구조변화 검정 (원칙 E)")
    P(doc, "검정은 잔차 분산 수준의 변화를 본다. 방향도, 수익률 크기의 비대칭도 보지 않는다. 이 보고서는 수익률 예측이나 투자 성과를 측정하지 않았다. "
      "따라서 투자 유용성에 관해 어떤 결론도 내리지 않는다.")
    H2(doc, "7.6 검정의 사용 가능 범위")
    tab(doc, "연구 질문별 판정", ["RQ", "판정", "근거", "상태"], [
        ["RQ1", "확정 불가", f"정책 A {v('fs_reject_A')}/20 기각, 검정력 {v('E2_break_A_rej13397')}%·보수적, B·기준선은 크기 왜곡", "UNRESOLVED"],
        ["RQ2", "정책 선택이 결과를 지배", f"기각 {v('fs_reject_A')}→{v('fs_reject_B')}/20, B의 귀무 크기 {v('E2_null_B_rej13397')}%, σ̂² 변동계수 {v('ab_cvB_lt_cvA')}/20에서 B<A", "VERIFIED / INFERRED"],
        ["RQ3", "창이 길수록 임계값↑·경보↓, 짧은 창에서 점근값은 과보수", "임계값·경보 빈도표, E1 n=60", "VERIFIED"],
        ["RQ4", "iid 임계값은 잔차 의존을 무시, 귀무 선택에 따라 기각 집합이 절반 바뀜", "E1·E3·E6", "VERIFIED·EXTENSION"],
        ["RQ5", "동일 지수 ETF끼리도 기각이 갈림 (초모수 선택 의존)", f"069500 {v('k200_TA_069500')} 대 102110 {v('k200_TA_102110')}", "VERIFIED"],
        ["RQ6", "잔차 구조변화를 시장 상태로 해석하려면 상태의 조작적 정의와 관측모형이 필요", "9장", "HYPOTHESIS"],
    ], widths=[1.2, 5.0, 7.0, 3.0], size=7.8)

    # ───────────────────────── 8
    H1(doc, "8. 연구 한계")
    bullets(doc, [
        "**원 논문 미재현.** Track B는 원문 실증·Monte Carlo 수치를 재현하지 못했다 (METHOD_FIDELITY_UNRESOLVED). 검정 구간 분산 입력, 임계값 1.3397의 근거 등 원문 미명시 사항이 남아 있다.",
        "**합성 자료의 대표성.** E2·E6은 정규 혁신의 GARCH(1,1) 하나와 ω 변화 하나만 썼다. 두꺼운 꼬리, 레버리지 효과, 점진적 변화, 여러 번의 변화는 평가하지 않았다. 반복 수는 시나리오당 500회다.",
        "**표본과 자료.** ETF 20종, 7.5년, 검정 구간은 571일 하나다. 2026년 고변동기가 검정 구간 후반에 몰려 있다. FDR은 분배를 소급 조정하므로 나중에 받은 자료는 해시가 다를 수 있다.",
        "**실제 시장 상태의 정답 부재.** 기각의 경제적 의미를 판정할 독립 기준이 없다. 이것이 사건 기반 평가를 제외한 이유이며, 동시에 이번 보고서가 탐지 성능을 말할 수 없는 이유다.",
        "**탐색된 자료.** 이 자료는 EDA·Track A·T11에서 이미 여러 번 분석되었다. 확장 실험의 설계는 사전 등록했지만 E6은 결과를 본 뒤 추가했다. 이번 결과는 확증이 아니라 탐색적 진단이다.",
        f"**grid 경계.** ε는 실제 20종과 합성 자료 {v('E2_eps_floor_share')}%에서 grid 하한 0.1이 선택되었다. 더 넓은 grid에서 정책 A의 흡수 정도가 달라질 수 있다 (미실행).",
    ])

    # ───────────────────────── 9
    H1(doc, "9. 후속 연구 설계")
    P(doc, "이 장은 성과가 아니라 설계다. 이번 결과는 '통계량이 언제 크게 나오는가'와 '시장이 어떤 상태인가'가 다른 질문임을 보여 주었다. "
      "그러므로 다음 연구는 정책이나 탐지기 구현이 아니라, 잠재 상태를 조작적으로 정의하고 그것을 자료에서 식별할 수 있는지 검증하는 데서 시작한다.")
    H2(doc, "9.1 기본 개념의 정의")
    tab(doc, "후속 연구의 기본 기호", ["기호", "정의", "예시·주의"], [
        ["O_t", "시점 t에 관측 가능한 변수 벡터", "수익률, 실현 변동성, 거래량, 자산 간 상관, CUSUM 통계량(진단 후보 중 하나)"],
        ["S_t", "관측되지 않는 잠재 시장 상태 (이산 또는 연속)", "예: 저변동/고변동/위기. 상태의 수와 의미는 사전 정의가 필요"],
        ["P(S_t | S_{t−1})", "상태전이 모형", "지속성(체류 시간)과 전이 확률. 식별 대상"],
        ["P(O_t | S_t)", "관측모형", "상태별 관측 분포. CUSUM 통계량을 넣으려면 그 분포를 상태별로 모형화해야 함"],
        ["P(S_t | O_{1:t})", "시점 t까지의 관측으로 얻은 사후 믿음 (belief)", "필터링으로 계산. 사후 평활 P(S_t|O_{1:T})와 구분"],
    ], widths=[2.8, 5.6, 7.8], size=7.9)
    fig(doc, "fig09_state_concept.png", "관측 O → 잠재 상태 S → 사후 믿음 개념도 (후속 연구 설계)",
        "출처: 이 보고서 작성. 주의: 개념도이며 이번 작업에서 어떤 상태 모형도 추정하지 않았다.")
    H2(doc, "9.2 방법별 역할 구분")
    bullets(doc, [
        "**HMM / 상태공간 모형.** 잠재 상태와 상태전이를 통계적으로 모형화하는 1차 후보다. 상태 수 선택, 관측모형 설정, 모수 식별 가능성(라벨 교환, 약한 식별)을 먼저 검토한다.",
        "**동적계획법(DP).** 상태 또는 belief state가 정의된 뒤, 정책 선택과 가치 최적화를 다루는 후속 방법이다. 보상·비용 함수의 정의가 선행해야 하며, 이번 보고서의 결과는 그 입력이 될 수 없다.",
        "**Active Inference (Friston).** 생성모형, 선호 결과, 불확실성, 기대 자유에너지에 기반한 정책 추론 접근이다. DP와 같은 수학적 방법이 아니며, 이번 T11 결과는 그 우수성에 대해 아무것도 입증하지 않는다.",
    ])
    H2(doc, "9.3 단계적 연구 과제")
    tab(doc, "후속 연구의 단계와 합격 기준 (제안, 미실행)", ["단계", "과제", "합격 기준 (사전 고정 필요)"], [
        ["1", "상태의 조작적 정의: 관측 O_t 후보와 상태 S_t의 의미를 문서로 고정 (사건 집합을 정답으로 쓰지 않음)", "정의가 자료를 보기 전에 승인됨 (계약 D-01 갱신)"],
        ["2", "합성 자료 식별 실험: 알려진 HMM에서 상태 수·전이·관측모형을 복원할 수 있는가", "모수 복원 오차·상태 분류 정확도의 사전 기준"],
        ["3", "실제 ETF에 HMM/상태공간 적합, 상태 수 선택과 안정성 (기간·종목 교차)", "동일 지수 ETF 간 상태 경로 일치, 기간 분할 안정성"],
        ["4", "CUSUM 통계량을 관측 후보로 추가했을 때 belief의 변화 (정보 기여)", "추가 전후 예측 로그우도의 out-of-sample 비교"],
        ["5", "belief 위의 의사결정 (DP 또는 Active Inference) — 보상·선호의 정의 후", "별도 설계 문서와 승인"],
    ], widths=[1.2, 8.8, 6.2], size=7.9)

    # ───────────────────────── 10
    H1(doc, "10. 결론")
    P(doc, "**검증된 사실 (VERIFIED).**")
    bullets(doc, [
        "T11 결과표 9종은 같은 커밋·같은 자료로 서로 다른 두 환경에서 바이트 단위로 재현된다. 보고서의 결과표 수치는 캐시 잔차의 재계산과 반올림 수준에서 일치한다.",
        f"검정 구간 사후 검정 기각은 정책 A {v('fs_reject_A')}, 정책 B {v('fs_reject_B')}, 기준선 {v('fs_reject_base')}/20이다. 원문 1.3397 대신 Kolmogorov 1.3581을 쓰면 정책 A는 {v('fs_reject_A_kolm')}이다.",
        f"합성 GARCH에서 파이프라인 크기는 A {v('E2_null_A_rej13397')}%, B {v('E2_null_B_rej13397')}%, 기준선 {v('E2_null_base_rej13397')}%이고, 분산 3배 변화에 대한 정책 A의 검정력은 {v('E2_break_A_rej13397')}%다 (EXTENSION).",
        "검정 구간 안에서 미래 수익률은 과거 통계량에 영향을 주지 않는다. 적합 구간은 설계상 in-sample이다.",
        "동일 지수 ETF 두 종의 기각 여부가 SVR 초모수 선택에 따라 갈린다.",
    ])
    P(doc, "**해석 (INFERRED).** 정책 A의 낮은 경보·검정력은 잔차 제곱의 음의 의존과 proxy 입력의 흡수에서 오고, 정책 B·기준선의 많은 기각은 불완전한 "
      "표준화에서 오는 크기 왜곡과 구별되지 않는다.")
    P(doc, "**아직 검증할 수 없는 주장 (UNRESOLVED / HYPOTHESIS).** ETF 잔차에 실제 구조변화가 남는지, 원 논문 수치가 왜 재현되지 않는지, 표준화가 "
      "정보 손실인지, CUSUM 통계량이 시장 상태 추론에 정보를 더하는지, 그리고 어떤 투자 유용성이 있는지는 이번 자료로 판단할 수 없다.")
    P(doc, "**최종 판정.** SVR–GARCH CUSUM은 이번 ETF 적용에서 '구조변화 검정'으로서의 크기·검정력 균형을 확보하지 못했다. 결과는 분산 입력 정책, 임계값의 "
      "귀무 정의, SVR 초모수 선택에 크게 의존한다. 이 검정을 급등 탐지기나 시장 상태의 대리 지표로 쓰지 않는다. 후속 연구는 상태의 조작적 정의와 "
      "식별 가능성 검증부터 시작한다.")

    # ───────────────────────── 참고문헌
    H1(doc, "참고문헌")
    refs = [
        "Lee, S., Kim, C. K., & Lee, S. (2020). Hybrid CUSUM change point test for time series with time-varying volatilities based on support vector regression. Entropy, 22(5), 578. https://doi.org/10.3390/e22050578 — 원 논문 (Track B 감사에서 열람·대조).",
        "Siegfriex/SA_ETF. ETF Domain EDA (main d5c2f79), Track A (codex/r2h-track-a@a3f9e9b), Track B 재현 패키지 (research/track-b-paper2020@031157d). https://github.com/Siegfriex/SA_ETF — 원 연구 저장소.",
        f"nanahyun3/R2H, 브랜치 1012, 커밋 {SHA}. https://github.com/nanahyun3/R2H — T11 코드·결과표·노트북.",
        "FinanceData. FinanceDataReader 0.9.202. https://github.com/FinanceData/FinanceDataReader — 시세 자료 출처.",
        "Kolmogorov 분포의 급수 표현 1 − 2Σ(−1)^{k−1}exp(−2k²x²) — 표준 결과. 이 보고서에서 수치 계산만 수행 (문헌 원문 미열람).",
        "Politis, D. N., & Romano, J. P. (1994). The stationary bootstrap. Journal of the American Statistical Association, 89(428), 1303–1313. — E3 방법 출처 (이 작업에서 원문 미열람).",
        "Newey, W. K., & West, K. D. (1994). Automatic lag selection in covariance matrix estimation. Review of Economic Studies, 61(4), 631–653. — E6 대역폭 규칙 출처 (원문 미열람).",
        "Rabiner, L. R. (1989). A tutorial on hidden Markov models and selected applications in speech recognition. Proceedings of the IEEE, 77(2), 257–286. — 9장 HMM 개념 (원문 미열람).",
        "Friston, K., FitzGerald, T., Rigoli, F., Schwartenbeck, P., & Pezzulo, G. (2017). Active inference: A process theory. Neural Computation, 29(1), 1–49. — 9장 Active Inference 개념 (원문 미열람).",
    ]
    for i, r in enumerate(refs, 1):
        p = para(doc, f"[{i}] {r}", size=8.6)
        p.paragraph_format.left_indent = __import__("docx.shared", fromlist=["Cm"]).Cm(0.6)
        p.paragraph_format.first_line_indent = __import__("docx.shared", fromlist=["Cm"]).Cm(-0.6)
    note(doc, "'원문 미열람'으로 표시한 문헌은 방법의 출처를 밝히기 위한 것이며, 이 보고서는 그 문헌의 세부 정리나 수치를 인용하지 않는다.")

    # ───────────────────────── 부록
    page_break(doc)
    H1(doc, "부록")
    H2(doc, "A. 실험 파라미터와 실행 환경")
    tab(doc, "실행 환경", ["항목", "환경 1 (루트 .venv)", "환경 2 (uv.lock)"], [
        ["Python", "3.12.3", "3.12.3"],
        ["numpy / pandas", "2.4.6 / 3.0.3", "2.5.4 / 3.0.6"],
        ["scikit-learn / scipy", "1.9.0 / 1.18.0", "1.9.1 / 1.18.1"],
        ["OS", "WSL2 Ubuntu 24.04, 24 cores", "같은 머신"],
        ["결과표 9종", "커밋본과 바이트 동일", "커밋본과 바이트 동일"],
        ["단위 테스트", "미수집 (hypothesis 미설치)", "98 passed"],
    ], widths=[4.0, 6.1, 6.1], size=8.0, src="출처: analysis/repro_logs/. 보고서 제작은 python-docx 1.2.0, latex2mathml 3.81.1, Microsoft Word (PDF 내보내기)를 사용했다.")
    H2(doc, "B. 재현 명령")
    for line in [
        "# R2H 루트, 커밋 a346faf",
        "uv sync --frozen --extra dev --extra notebook --extra research",
        "ETF_RAW_DIR=<원시 시세 폴더> uv run python scripts/run_svr_garch_cusum_etf.py   # 결과표 + outputs/cache/t11_state.npz",
        "uv run pytest -q",
        "D=deliverables/R2H_T11_CUSUM_Final_Review/scripts",
        "PYTHONPATH=src python $D/01_recompute.py && PYTHONPATH=src python $D/02_extension.py",
        "python $D/03_claims.py && PYTHONPATH=src python $D/04_figures.py && python $D/05_build_docx.py",
        "powershell.exe -File $D/06_export_pdf.ps1  (Word로 필드 갱신 → DOCX 저장 → PDF)",
    ]:
        para(doc, line, size=8.0, color="1F1F1F").paragraph_format.space_after = __import__("docx.shared", fromlist=["Pt"]).Pt(0)
    H2(doc, "C. 전체 ETF 사후 검정표")
    rows = []
    for t in names.ticker:
        f = fitsum.set_index("ticker").loc[t]
        r = {p: fs[(fs.ticker == t) & (fs.policy == p)].iloc[0] for p in ("A", "B", "base")}
        mark = lambda x: f"{x['T']:.3f}{' *' if x['reject_1.3397'] else ''}"  # noqa: E731
        rows.append([t, names.set_index("ticker").loc[t, "name"], f"{f.C:g}/{f.paper_gamma_squared:g}/{f.epsilon:g}",
                     mark(r["A"]), r["A"].khat, mark(r["B"]), r["B"].khat, mark(r["base"]), f"{r['A'].c_boot_n:.3f}"])
    tab(doc, "ETF 20종 사후 검정 전체 (검정 구간 n=571, * = 1.3397 이상)", ["코드", "종목", "C/γ²/ε", "T_A", "k̂_A", "T_B", "k̂_B", "T_기준선", "c 부트(A)"], rows,
        widths=[1.3, 3.4, 1.8, 1.4, 1.9, 1.4, 1.9, 1.6, 1.5], size=7.2, align=["l", "l", "c", "r", "c", "r", "c", "r", "r"],
        src="출처: analysis/fullsample_recomputed.csv, results/fit_summary.csv.")
    H2(doc, "D. Git 및 데이터 식별자")
    tab(doc, "식별자", ["대상", "값"], [
        ["R2H 1012 기준 커밋", SHA],
        ["R2H main (변경 없음)", "7c3eafa9be82768319b96df5e4ffd7a9d6042c64"],
        ["SA_ETF 원 연구", "main d5c2f79 · codex/r2h-track-a a3f9e9b · research/track-b-paper2020 031157d"],
        ["data_version", v("data_version")],
        ["seed", "20261012"],
    ], widths=[4.2, 12.0], size=8.0)
    H2(doc, "E. 소스–주장 대응과 미해결 사항")
    para(doc, "주요 수치 전체의 원천 파일·열·함수와 상태는 SOURCE_EVIDENCE_MATRIX.md에 있다. 이 문서는 생성 스크립트가 본문에서 사용한 claim 키를 자동으로 "
      "기록해 만든다. 재현성 감사는 REPRODUCIBILITY_AUDIT.md, 기존 T11 해석 대비 변경과 미해결 과제는 CHANGELOG_AND_OPEN_ISSUES.md에 있다.")
    bullets(doc, [
        "원문 임계값 1.3397의 유도 근거 (Kolmogorov 95% 1.3581과 차이) — UNRESOLVED",
        "검정 구간 분산 입력 정책 (원문 미명시) — UNRESOLVED",
        "원 논문 실증·MC 수치 미재현 — METHOD_FIDELITY_UNRESOLVED",
        "SVR grid 경계(ε 하한) 민감도 — 미실행",
        "의존성을 반영한 귀무에서의 크기 보정 (장기분산 정규화 등) — HYPOTHESIS",
        "잠재 상태의 조작적 정의 — 9장 1단계, 팀 승인 필요",
    ])

    header_footer(doc, "R2H · SVR–GARCH CUSUM의 ETF 적용과 통계적 구조변화 검정의 재평가 · " + VERSION,
                  f"R2H 1012 @ {SHA[:7]} · 검증 상태: 재계산 VERIFIED / 원문 UNRESOLVED")
    doc.save(OUT_DOCX)

    # ───────────────────────── SOURCE_EVIDENCE_MATRIX.md
    lines = ["# SOURCE_EVIDENCE_MATRIX — 보고서 주장·수치 ↔ 원천", "",
             f"생성: `scripts/05_build_docx.py` (본문에서 사용한 claim 키를 자동 기록). 기준 커밋 `{SHA[:7]}`. 값의 원본은 `claims.json`.", "",
             "상태: VERIFIED = 이 작업에서 재계산/재실행 · REPORTED = 기존 결과에서만 확인 · EXTENSION = 이번 추가 실험 (extension/)", "",
             "| claim 키 | 값 | 상태 | 원천 (파일 · 열 · 함수) | 비고 | 보고서 위치 |", "|---|---|---|---|---|---|"]
    for k in sorted(USED):
        c = CLAIMS[k]
        val = json.dumps(c["value"], ensure_ascii=False) if not isinstance(c["value"], str) else c["value"]
        lines.append(f"| `{k}` | {val} | {c['status']} | {c['source']} | {c.get('note', '')} | {'; '.join(USED[k])} |")
    lines += ["", "## 표·그림의 원천", "",
              "| 보고서 요소 | 원천 |", "|---|---|",
              "| 표 8 · 표 18 (부록 C) | `analysis/fullsample_recomputed.csv` ← `01_recompute.py` (캐시 잔차 + `cusum_squares_test`) |",
              "| 표 9 (KOSPI200) | `analysis/kospi200_group.csv` |",
              "| 표 10 (경보 빈도) | `analysis/zone_rates.csv` ← `rolling_cusum`, `episodes`, `null_alarm_episodes_per_year` |",
              "| 표 11 (E1) | `extension/E1_residual_size.csv` |",
              f"| 표 12 (E2) · 그림 {F('fig05_size_power.png')} | `extension/E2_pipeline_size_power_summary.csv`, `_reps.csv` |",
              "| 표 13 (Track B) | `outputs/cache/031157d__…EMPIRICAL_ORIGINAL_VS_REPRODUCED.csv` → `analysis/trackb_empirical.csv` (REPORTED) |",
              f"| 그림 {F('fig02_fullsample_T.png')} | `analysis/fullsample_recomputed.csv` |",
              f"| 그림 {F('fig03_critical_values.png')} | `results/critical_values.csv` |",
              f"| 그림 {F('fig04_alarm_rates.png')} | `analysis/zone_rates.csv` |",
              f"| 그림 {F('fig06_kospi200_pair.png')}·{F('fig07_timeline_069500.png')} · 그림 {F('fig11_vol_overview.png')} | `outputs/cache/t11_state.npz` (varA, varB, res), `results/fit_summary.csv`, `results/critical_values.csv` |",
              f"| 그림 {F('fig08_dependence_and_null.png')} | `extension/E6_*`, `extension/E3_stationary_bootstrap.csv` |",
              f"| 그림 {F('04_rolling_heatmaps.png')}·{F('10_yearly_blocks.png')} (재사용) | `docs/figures/svrgarch/04_rolling_heatmaps.png`, `10_yearly_blocks.png` (커밋 a346faf) |",
              "", f"사용한 claim {len(USED)}개 / 전체 {len(CLAIMS)}개."]
    (HERE / "SOURCE_EVIDENCE_MATRIX.md").write_text("\n".join(lines) + "\n")
    print("figures", FIGN[0], "tables", TABN[0], "claims used", len(USED), "→", OUT_DOCX)


if __name__ == "__main__":
    build()

# ruff: noqa: E501
"""12B 최종 보고 노트북 생성기 — 계산을 다시 하지 않고 동결 결과·그림만 읽어 보고 순서로 제시한다.

연구 노트북(12B_KODEX200_CUSUM_시장변수_연환산변동성_정렬비교.ipynb)이 계산·게이트를 담당하고, 이 노트북은 결과 제시용이다.
코드 셀 검사·CLAIMS 는 t22_build_notebook.py 의 것을 그대로 쓴다 (같은 notebook_claims.json 을 다시 대조).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import nbformat

sys.path.insert(0, str(Path(__file__).resolve().parent))
import t22_build_notebook as B  # noqa: E402

ROOT = B.ROOT
NB = ROOT / "notebooks" / "12B_최종보고_KODEX200_CUSUM_시장정렬.ipynb"
md, code, table = B.md, B.code, B.table


def fig(name: str, width: int = 1000) -> nbformat.NotebookNode:
    return code(f"""
display(Image(data=preview(FIGDIR / "{name}.png", width={width})))  # 저장된 PNG(320dpi)의 축소 미리보기 (원본은 figures/)
""")


LOAD = r"""
# 계산은 하지 않는다: 연구 노트북·스크립트가 만든 동결 결과표·그림·릴리스 기록만 읽는다.
T = {p.name: pd.read_csv(p) for p in sorted(RES.glob("*.csv*"))}  # 결과표 전부 (gzip 포함)
CAP = json.loads((RES / "figure_captions.json").read_text(encoding="utf-8"))  # 그림 캡션 수치
MAN = json.loads((BASE / "RELEASE_MANIFEST.json").read_text(encoding="utf-8"))  # 릴리스 기록
X1C = json.loads((BASE / "evidence/x1_checks.json").read_text(encoding="utf-8"))  # X1 원장 재계산·fit 0 검사
G6 = pd.read_csv(BASE / "evidence/g6_figure_ledger_check.csv")  # 그림–원장 일치 기록
REC = json.loads((BASE / "evidence/execution_record.json").read_text(encoding="utf-8"))  # 연구 노트북 실행 기록
gates = pd.DataFrame([  # 게이트 요약표
    ("G0 12번 보호", f"{MAN['G0_protected_12_files']}개 중 변경 {len(MAN['G0_changed'])}"),  # 기존 연구 불변
    ("G1–G3·G7 정렬", f"{int(T['policy_market_alignment_audit.csv']['pass'].astype(str).eq('True').sum())}/{len(T['policy_market_alignment_audit.csv'])} 통과"),  # 날짜·전수·시장변수·결측
    ("G4 OFAT (구조 판정)", f"불일치 {int((~T['ofat_pair_comparison.csv'].ofat_consistent_structural.astype(bool)).sum())} / {len(T['ofat_pair_comparison.csv'])}쌍"),  # 한 변수 변경 확인
    ("G6 그림–원장", f"{int(G6['equal'].sum())}/{len(G6)} 일치"),  # 그린 값 = 원장 값
    ("X1 원장 재계산", f"{sum(v for k, v in X1C.items() if k.endswith('_equal'))}/{sum(1 for k in X1C if k.endswith('_equal'))} 일치"),  # 재적합 없이 동일
    ("G10 연구 노트북", f"{REC['status']} · {REC['seconds']}초"),  # 새 커널 실행
    ("재현성", str(MAN["reproducibility_notebook_vs_script"])),  # 노트북 경로 = 스크립트 경로
    ("단위 시험", MAN["tests"]),  # pytest 결과
], columns=["게이트", "결과"])  # 표 열 이름
display(gates)  # 표 출력
"""

LIVE_X1 = r"""
# 실시간 그림: X1·원래 Page 의 α=0.05 경보일과 연환산 20일 변동성을 한 축에 (결과표 x1_real_daily.csv 에서 직접 그린다)
x = T["x1_real_daily.csv"].assign(date=lambda d: pd.to_datetime(d["date"]))  # X1 일별 해부표
fig_, ax = plt.subplots(2, 1, figsize=(13, 5.5), sharex=True, gridspec_kw={"height_ratios": [1.2, 1]})  # 변동성·경보 두 패널
ax[0].plot(x["date"], x["annualized_vol_20"], color="#eb6834", lw=1, label="연환산 관측 20일")  # 관측 변동성
ax[0].plot(x["date"], np.sqrt(252 * x["predicted_variance_B1"]), color="#6250d6", lw=0.9, ls="--", label="SVR 예측 연환산 (B1)")  # 예측 변동성
ax[0].set_ylabel("%/년")  # 단위
ax[0].legend(fontsize=8, frameon=False)  # 범례
rows = [("E3_up_alarm_a05", "Page 상방"), ("X1_up_alarm_a05", "X1 상방"), ("X1w_up_alarm_a05_REFERENCE", "X1w 상방 (참조)"), ("E3_down_alarm_a05", "Page 하방"), ("X1_down_alarm_a05", "X1 하방"), ("X1_two_alarm_a05", "X1 양방향")]  # 경보 계열
for k, (c, lab) in enumerate(rows):  # 계열마다
    d = x.loc[x[c].astype(bool), "date"]  # 경보일
    ax[1].scatter(d, np.full(len(d), k), marker="|", s=250, color=f"C{k}")  # 세로 눈금으로 표시
ax[1].axvspan(x["date"].iloc[0], x.loc[x["m_hat_X1"].notna(), "date"].iloc[0], color="#d9d8d2", alpha=0.6, lw=0, label="X1 값 없음 (유효 120일 전)")  # X1 결측 구간
ax[1].set_yticks(range(len(rows)), [f"{lab} {int(x[c].astype(bool).sum())}회" for c, lab in rows], fontsize=9)  # 계열 이름·경보 수를 눈금 라벨로
ax[1].set_ylim(-0.7, len(rows) - 0.3)  # 위아래 여유
ax[1].legend(fontsize=8, frameon=False, loc="lower right")  # 범례
fig_.suptitle("X1 과 원래 Page 의 경보일 (α=0.05, 서술용 — N1 귀무 부적합)", x=0.01, ha="left", fontsize=12)  # 제목
plt.tight_layout()  # 여백 정리
buf = io.BytesIO()  # 그림 버퍼
fig_.savefig(buf, format="png", dpi=110)  # 노트북용 해상도
plt.close(fig_)  # 메모리 해제
display(Image(data=buf.getvalue()))  # 표시
"""

LIVE_CLUSTER = r"""
# 실시간 그림: 463 정책이 몇 개의 신호로 묶이는가 — 값 군집 크기 분포와 탐지기 구성 (agreement_clusters.csv)
cl = T["agreement_clusters.csv"]  # 정책별 값 군집
sz = cl.groupby("value_cluster").size().sort_values(ascending=False)  # 군집 크기
comp = cl.groupby(["value_cluster", "detector_type"]).size().unstack(fill_value=0).loc[sz.index[:15]]  # 상위 15 군집 구성
fig_, ax = plt.subplots(1, 2, figsize=(14, 5), gridspec_kw={"width_ratios": [1, 1.4]})  # 두 패널
ax[0].bar(range(len(sz)), sz.values, color="#3987e5")  # 군집 크기 막대
ax[0].set_yscale("log")  # 크기 차이가 커서 로그
ax[0].yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}"))  # 일반 숫자 눈금
ax[0].set_xlabel("값 군집 (큰 순)")  # 축 이름
ax[0].set_ylabel("정책 수")  # 축 이름
ax[0].set_title(f"값 군집 {len(sz)}개 · 단일 {int((sz == 1).sum())}개", loc="left")  # 제목
comp.plot.barh(stacked=True, ax=ax[1], width=0.8)  # 구성 누적 막대
ax[1].invert_yaxis()  # 큰 군집이 위로
ax[1].set_xlabel("정책 수")  # 축 이름
ax[1].set_title("상위 15 군집의 탐지기 구성", loc="left")  # 제목
ax[1].legend(fontsize=8, frameon=False)  # 범례
plt.tight_layout()  # 여백 정리
buf = io.BytesIO()  # 그림 버퍼
fig_.savefig(buf, format="png", dpi=110)  # 노트북용 해상도
plt.close(fig_)  # 메모리 해제
display(Image(data=buf.getvalue()))  # 표시
"""

CLAIMS = r"""
# 본문 수치를 결과 파일에서 다시 계산해 대조한다 (연구 노트북과 같은 notebook_claims.json).
CL = json.loads((BASE / "notebook_claims.json").read_text(encoding="utf-8"))  # (주장, 결과파일, 식, 기대값)
bad = {}  # 불일치 주장
for c in CL:  # 주장마다
    df = pd.read_csv(RES / c["file"])  # 근거 결과표
    got = eval(c["expr"], {"df": df, "np": np, "pd": pd})  # 결과표에서 다시 계산한 값
    got = round(float(got), c["round"]) if isinstance(got, (int, float, np.floating, np.integer, bool)) else got  # 반올림 규칙
    exp = round(float(c["expected"]), c["round"]) if isinstance(c["expected"], (int, float)) else c["expected"]  # 기대값
    if got != exp:  # 다르면
        bad[c["claim"]] = (got, exp)  # 기록
print(f"CLAIMS {len(CL) - len(bad)}/{len(CL)} 일치")  # 결과
assert not bad, bad  # 불일치면 실패
bad_p = [p for h, p in PROT if sha(ROOT / p) != h]  # 12번 보호 파일 재확인
assert not bad_p, bad_p  # 변경 금지
print("12번 보호", len(PROT), "개 불변 · 그림", len(list(FIGDIR.glob("*.png"))), "장 · 결과표", len(T), "개")  # 요약
"""


def book() -> nbformat.NotebookNode:
    cells = [
        md("""
# 12B 최종 보고 — KODEX 200 CUSUM 을 실제 시장 위에 겹쳐 보면

**R2H 12B (T22)** · 069500 KODEX 200 · 2020-01-02 ~ 2025-12-30 · 계약 `12B-lock-1` · 브랜치 `research/12b_k200_cusum_volatility_alignment`

12번의 463개 일별 CUSUM 정책(681,999행)을 종가·수익률·연환산변동성과 같은 날짜축에 전수 정렬하고, 한 변수씩 바꾼 정책을 시장 경로 위에 겹쳐 비교했다.
요청한 **X1 자기정규화 Page 의 실데이터 적용** 을 맨 앞에 둔다.

> 이 노트북은 결과 제시용이다. 계산·게이트는 연구 노트북 `12B_KODEX200_CUSUM_시장변수_연환산변동성_정렬비교.ipynb` 가 담당하고, 여기서는 그 동결 결과만 읽는다.
> 관측 귀무 모형이 맞지 않으므로(`NULL_MODEL_INVALID`) 모든 경보·임계값은 서술용 참조다.

### 한눈에 보기

| 질문 | 답 |
|---|---|
| X1 은 실데이터에서? | 2020-09-21 부터 값이 있어 COVID 를 못 본다. 2021–2025 상방 경보 0회, 하방 4회(COVID 뒤 정상화기). 2019 잔차로 시작한 X1w(보정 없는 참조)는 2020-03-18 — 원래 Page 보다 3거래일 빠르다 |
| 새 발견 | SVR 예측분산이 2020-02-25 ~ 08-21 의 32일 동안 1.127 에 **상수 고정** (커널 소실, 기계적 확인). 2020 경보와 동시 발생 (인과 미확인) |
| 급증 / 높은 수준 / 감소 | 이동 CoS / Page 상방(표류 섞임) / CoS·Page 하방·X1 하방 |
| 창 길이 · 초기화 | 창은 기억 길이를 바꾼다 (w20–w60 ρ 0.07). CoS 초기화는 관측 공백만 더한다 |
| 중복성 | 463 정책 → 값 군집 73개. 117개 CoS 군집, 107개 Page 하방 군집은 사실상 한 신호 |
| AE 인계 | CoS 4개 창 · 원수익률 CoS · Page 하방 · X1(검증 후) · 예측분산 + 상수 고정 표시 · 마스크. 경보·p값은 넘기지 않는다 |
"""),
        code(B.SETUP),
        md("## 1. 검증 상태"),
        code(LOAD),
        md("""
## 2. X1 자기정규화 Page — 실데이터 적용 (요청 사항)

X1 은 12번이 저장한 B1 잔차 e = r/√v^ 를 과거 [t−252, t−61] 의 평균 e² 로 한 번 더 나눈 값이다. **재적합이 필요 없고**, 다시 계산한 상태·경보가 원장과 비트 단위로 같다.

- **2020 이 빈다.** 기준에 유효일 120일이 필요해 값이 2020-09-21 부터 나온다.
- **상방 경보 0회 (2021–2025).** 사건 구간 중 상태/임계값 최대 0.46 (2024-08).
- **하방 4회 (2020-12-03 ~ 2021-07-01).** COVID 기간의 큰 e² 가 기준창에 남아 이후 잔차가 상대적으로 작아 보인 정상화기다.
- **X1w (탐색).** 2019 fit 0 의 표본내 잔차로 기준을 채우면 2020-03-18 에 처음 임계값을 넘는다 (원래 Page 상방 03-23). 임계값을 따로 보정하지 않아 참조로만 쓴다.
"""),
        code(LIVE_X1),
        fig("G02_X1_자기정규화Page_실데이터"),
        md("""
### 왜 2024-08-05 −9.63% 에도 울리지 않았나

그날 SVR 예측분산 v^ 가 이미 5.01 이라 잔차가 −4.30 에 그쳤다. CUSUM 은 원수익률이 아니라 **SVR 이 놓친 몫**만 본다. 2020 에는 반대로 v^ 가 1.127 에 묶여 있어 잔차가 원수익률에 가까웠다.
"""),
        fig("G03_X1_사건확대"),
        md("""
### X1 은 원래 Page 와 다른 정보인가

공통일 순위 상관이 −0.25 다. 원래 Page 상방은 잔차 척도가 1 보다 크면(평균 e² > 1.39) 상태가 계속 쌓이는 표류가 있어 변동성 **수준**과 상관 0.58 을 보이는데, X1 은 이를 지워 0.26 이 된다.
"""),
        fig("G05_09_부모자식_E3_page_up_vs_X1_page_up_sn"),
        fig("G05_10_부모자식_E3_page_down_vs_X1_page_down_sn"),
        table("T['x1_event_table.csv'].query('event_set==\"A_t20\"')[['interval_id','shock_type','period','E3_up_free_max_over_h','E3_up_path_max_over_h','X1_up_path_max_over_h','X1w_up_path_max_over_h','X1_down_path_max_over_h','E3_up_first_alarm_a05','X1w_up_first_alarm_a05']].round(2)", "사건별 상태/임계값 최대 — 자유 상태(free, 표류 포함)와 경보 경로(path) 분리"),
        md("""
## 3. 새 발견 — SVR 예측분산 상수 고정 (커널 소실)

같은 적합 안에서 예측분산이 소수점 9자리까지 같은 값으로 5일 이상 반복되는 날을 찾았다. B1 은 2020-02-25 부터 1.127 에 32일 묶였고, 그동안 관측 20일 분산은 2 에서 20 까지 올랐다.
입력이 2019 학습 범위를 벗어나 RBF 커널 기여가 0 이 되면 절편 상수만 남는다 — fit 0 에 아주 먼 입력을 넣으면 정확히 1.1272266 이 나온다. 같은 적합의 2020 최대 v^ 는 1.92 라 '상한' 이 아니다.
B1 의 2020 경보 43일 중 13일이 고정일 당일이다. 함께 일어났을 뿐이며, 고정일 v^ 를 바꿔 넣는 반사실 계산 전까지 원인으로 말하지 않는다.
"""),
        fig("G04_SVR_예측상수고정"),
        table("T['svr_forecast_ceiling_summary.csv'].round(3)", "정책·적합별 상수 고정 구간 (열 이름 forecast_ceiling 은 호환용, D-11)"),
        table("T['b1_alarm_constant_overlap.csv']", "B1 경보일과 상수 고정일의 겹침 (동시 발생 기술)"),
        md("""
## 4. 6년 시장 경로 위의 CUSUM

대표 12정책의 **과거 전용 백분위**(t 이전 252일 자기 분포 안 위치, 0–1)를 띠로 쌓았다. 회색 = 값 없음(NA), 붉은 음영 = 11번 급변 구간(CUSUM 과 독립 정의).
아래 띠는 변화점·연초 초기화·재학습·예측 상수 고정, 맨 아래는 과거 전용 연환산 국면이다.
"""),
        fig("G01_6년_시장_CUSUM_정렬지도", 1100),
        fig("G06_연도별_시장_CUSUM"),
        md("""
## 5. 한 변수만 바꾸면 — 부모–자식 중첩

- **창 길이**: 날짜별 순위가 크게 바뀐다 (공통일 ρ: w20 0.07 · w120 0.38 · w252 0.35). 긴 창은 충격이 창에서 빠질 때(d + w)까지 기억한다 — w252 경보 159일·NA 192일 추가.
- **변화점 초기화 (CoS)**: 공통 유효일에서 값이 부모와 같다 (ρ = 1.00). 달라지는 것은 초기화 직후 NA 뿐 — 관측 공백 추가다.
- **SVR 학습·재학습**: 잔차 척도를 바꿔 같은 날 값이 달라진다 (win252 ρ 0.67, refit21 0.89).
"""),
        fig("G05_02_부모자식_B1_vs_E2_w20"),
        fig("G05_04_부모자식_B1_vs_E2_w252"),
        fig("G07_창이탈_효과"),
        fig("G05_05_부모자식_B1_vs_E8_reset_only"),
        fig("G13_초기화_관측공백"),
        fig("G05_07_부모자식_B1_vs_E7_refit21"),
        fig("G14_SVR정책_비교"),
        table("T['ofat_pair_comparison.csv'].set_index('child').loc[['B0','E2_w20','E2_w120','E2_w252','E8_reset_only','E6_win252','E7_refit21','X1_page_up_sn','X1_page_down_sn','E3_raw_rolling_cos'],['parent','changed_variable','common_valid_days','parent_only_days','child_only_days','raw_spearman','pct_diff_mean_expanding','pct_diff_mean_contracting','alarm_days_parent','alarm_days_child','added_na_days']].round(3)", "대표 부모–자식 쌍 지표"),
        md("""
## 6. 연환산변동성 국면 · 사건 · 시차

국면은 계산 전에 고정한 과거 전용 정의다 (연환산 20일: 수준 4 × 변화 3). 흐린 칸은 유효일 20 미만이라 해석하지 않는다.
- **확대**: 이동 CoS 가 가장 크게 오른다 (원수익률 CoS +0.27, B1 +0.19).
- **높은 수준 유지**: Page 상방만 높다 (+0.25) — 표류가 섞인 반응이다. SVR 잔차 CoS 는 무반응 (B1 +0.001).
- **감소**: CoS(+0.13), Page 하방, X1 하방.
- **시차**: Page·X1 은 같은 날 반응이 가장 강하다 (Page 상방 +0.44, 하방 −0.46). CoS w60 의 k = −19 최대는 20일 앵커의 창 이탈 메아리다.
"""),
        fig("G08_국면별_정책반응"),
        fig("G09_사건정렬_반응"),
        fig("G15_단일vs누적_충격"),
        fig("G10_선행후행"),
        table("T['annualized_volatility_response.csv'].set_index('experiment_id').loc[['B1','E2_w20','E2_w252','E3_raw_rolling_cos','E3_page_up','E3_page_down','X1_page_up_sn','X1_page_down_sn','X1_page_two_sn'],['rho_vol20','rho_vol20_ex2020','rho_d5','contrast_EXPANDING_minus_STABLE','contrast_CONTRACTING_minus_STABLE','contrast_HIGHEXT_STABLE_minus_LOWMID_STABLE']].round(3)", "대표 정책의 국면 반응 (2020 제외 포함)"),
        md("""
## 7. 463개 정책은 몇 개의 신호인가

공통 유효일 원시 T 의 Spearman ρ ≥ 0.9 로 묶으면 값 군집 73개 (단일 29개). 가장 큰 117개 군집(B1·B0·변화점 초기화 CoS 대부분)과 107개 Page 하방 군집은 사실상 한 신호다.
CoS 창 w20·w30·w120·w252, 원수익률 CoS, SVR 학습창 정책, X1 3종은 서로 독립된 시간 규모다. 결측 패턴은 값과 따로 군집화했다.
"""),
        code(LIVE_CLUSTER),
        fig("G11_전체정책_히트맵", 1100),
        fig("G12_정책합의_중복성"),
        md("""
## 8. Autoencoder 에 넘길 피처

미래 20일 실현변동성 예측에서, 관측·예측 변동성만 쓴 기준보다 상대 MSE 가 얼마나 줄었는지 쟀다 (한 해씩 빼고 시험, 표본외지만 실시간 예측은 아님). 정책마다 유효일이 달라 공통 846일에서도 따로 비교했다.
- Page 하방 계열 +3.5% (시험연도 5개 중 4개 개선, 공통일 비교 5개 모두) · X1 양방향 +8.1% (공통일 +2.7%) · CoS w120·w252 +2.4%·+3.9%
- CoS w60 계열 −1.7% — 원시 변동성에 이미 담긴 정보다.

| 넘길 것 | 시간 규모 | 근거 |
|---|---|---|
| SVR 잔차 이동 CoS (창마다 1개) | 20 · 60 · 120 · 252일 | 창마다 다른 값 군집 |
| 원수익률 CoS | 60일 | SVR 비의존 기준, 확대 반응 최대 |
| Page 하방 (대표 1개) | 누적 | +3.5%, 변형 107개는 중복 |
| X1 하방 · 양방향 | 누적 | 탐색 — 2026 이후 자료로 검증 후 |
| SVR 예측분산 + 상수 고정 표시 | 1일 | 고정일 잔차 ≈ 원수익률 |
| 마스크 (초기화·재학습 경과일, 창 이탈일) | — | 공백·창 잔존·경계 식별 |

넘기지 않는 것: Page 상방 원시 상태(표류, 공통일 −8.6%), CoS 초기화 변형, 경보·p값, 사후 백분위.
"""),
        code("""
display(Image(data=preview(BASE / "figures_ae/AE01_인계_피처표.png", width=1400)))  # AE 인계 피처표 (12B_AE인계_피처표.ipynb 가 그린 PNG)
display(Image(data=preview(BASE / "figures_ae/AE02_보조열.png", width=1100)))  # 함께 넘기는 보조 열
"""),
        fig("G16_AE피처_증분정보"),
        fig("G17_연도별_안정성"),
        table("T['feature_incremental_information_common_days.csv'].query('~exclude_2020_train')[['feature','n_common','rel_mse_gain_pooled','years_positive','gain_2021','gain_2022','gain_2023','gain_2024','gain_2025']].sort_values('rel_mse_gain_pooled', ascending=False).round(4)", "공통 유효일 846일에서 대표 후보 비교"),
        md("""
## 9. 연구 질문 10개에 대한 답

1. **급증에 가장 강하게 반응** — 이동 CoS (원수익률 +0.27, SVR 잔차 +0.19). 같은 날 반응은 Page 상방·하방.
2. **높은 수준 유지** — Page 상방 (+0.25, 수준 ρ 0.58). 표류가 섞였고 X1 은 0.26. CoS 는 무반응.
3. **감소** — CoS (+0.13), Page 하방 (5일 변화율과 ρ −0.26), X1 하방.
4. **창 길이만 바꾸면** — 날짜별 순위가 바뀌고(w20–w60 ρ 0.07), 긴 창은 충격을 창 이탈일까지 기억한다.
5. **변화점 초기화** — CoS 에서는 관측 공백 추가가 대부분 (NA 중앙값 242일, 값 ρ ≈ 1). 무작위 초기화보다 나은 경우는 우연 수준.
6. **SVR 때문에 생긴 인위적 반응 날짜** — 예측분산 상수 고정 2020-02-25 ~ 08-21 · 2024-08-06 ~ 12, 재적합 경계 척도 단절 2020-04-02(refit63)·2022-01-03(B1), 2021 초 유예 재학습 경계.
7. **2020 제외** — 수준 상관 부호가 바뀐 정책 0개. 과거 전용 척도는 2020 대부분이 NA 라 근거가 약하다.
8. **원시 변동성 밖의 정보** — Page 하방, X1 하방·양방향, 긴 창(w120·w252).
9. **유사 정책군 / 독립 시간 규모** — 117개 CoS 군집, 107개 Page 하방 군집은 중복. 창 길이·공식·SVR 학습창·X1 은 독립.
10. **AE 인계** — 8절 표. 경보는 넘기지 않는다.

## 10. 한계와 다음 단계

- 사건 7개, 시험연도 5개, 예측 목표 구간이 겹친다. 과거 전용 척도는 2020 대부분이 NA. X1w 는 임계값 미보정.
- 다음 단계 제안: 고정일 v^ 를 바꿔 넣는 반사실 계산으로 2020 경보 중 상수 고정 몫을 분리 · X1 을 다른 ETF·2026 맹검으로 사전 등록 검증 · AE 입력을 8절 대표 정책으로 축소.

상호작용 탐색기: `research/k200_cusum_overlay_12b/interactive/12B_시장_CUSUM_탐색기.html` · 전체 그림 27장: `research/k200_cusum_overlay_12b/figures/`
"""),
        md("## 11. 수치 대조 · 보호 확인"),
        code(CLAIMS),
    ]
    nb = nbformat.v4.new_notebook()
    nb.cells = cells
    nb.metadata["kernelspec"] = {"display_name": "Python 3 (R2H .venv)", "language": "python", "name": "python3"}
    nb.metadata["language_info"] = {"name": "python"}
    return nb


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    nb = book()
    if a.write:
        nbformat.write(nb, NB)
        print("작성:", NB)
    else:
        print("검사만 (셀", len(nb.cells), "개)")


if __name__ == "__main__":
    main()

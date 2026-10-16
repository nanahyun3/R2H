# ruff: noqa: E501  — 그림 캡션과 긴 한국어 표기는 출판용 문구로 유지한다.
"""T12 원본 계산 결과를 읽어 출판용 한국어 그림 6종을 별도 버전으로 만든다.

숫자·검정 판정은 변경하지 않는다. 원본 그림 F01–F12와 구분하기 위해
P01–P06 이름을 쓰며 PNG(300 dpi)와 SVG를 같은 데이터에서 저장한다.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager

FONT = Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf")
COL = {"A": "#2a78d6", "B": "#eb6834", "base": "#1b8066"}
POL = {"A": "정책 A", "B": "정책 B", "base": "60일 기준선"}


def _setup() -> None:
    if not FONT.exists():
        raise FileNotFoundError(f"한글 폰트 없음: {FONT}")
    font_manager.fontManager.addfont(str(FONT))
    plt.rcParams.update({
        "font.family": [font_manager.FontProperties(fname=str(FONT)).get_name(), "DejaVu Sans"],
        "axes.unicode_minus": False,
        "figure.dpi": 110,
        "savefig.dpi": 160,
        "axes.edgecolor": "#c3c2b7",
        "axes.labelcolor": "#52514e",
        "xtick.color": "#52514e",
        "ytick.color": "#52514e",
        "axes.grid": True,
        "grid.color": "#e1e0d9",
        "grid.linewidth": 0.6,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "font.size": 9,
        "axes.titlesize": 10,
        "svg.fonttype": "none",
        "figure.facecolor": "white",
        "axes.facecolor": "#fcfcfb",
        "savefig.facecolor": "white",
    })


def _save(fig, out: Path, stem: str, sources: list[Path], caption: str, *, layout: bool = True) -> dict[str, str]:
    if layout:
        fig.tight_layout()
    png, svg = out / f"{stem}.png", out / f"{stem}.svg"
    fig.savefig(png, dpi=300, bbox_inches="tight")
    fig.savefig(svg, bbox_inches="tight")
    plt.close(fig)
    return {
        "그림": stem,
        "PNG": str(png),
        "SVG": str(svg),
        "PNG_SHA256": hashlib.sha256(png.read_bytes()).hexdigest(),
        "자료_SHA256": ";".join(f"{p.name}:{hashlib.sha256(p.read_bytes()).hexdigest()}" for p in sources),
        "캡션": caption,
    }


def make(results: Path, out: Path) -> pd.DataFrame:
    """검증된 01 결과표에서만 6개 발표 그림을 그린다."""
    _setup()
    out.mkdir(parents=True, exist_ok=True)
    sy_path = results / "summary_by_year_policy.csv"
    post_path = results / "annual_posthoc.csv"
    syn_path = results / "null_dgp_validation.csv"
    hist_path = results / "annual_history_ablation.csv"
    sy = pd.read_csv(sy_path)
    post = pd.read_csv(post_path, dtype={"ticker": str})
    syn = pd.read_csv(syn_path)
    core = sy[sy.year.between(2021, 2025)]
    records: list[dict[str, str]] = []

    # P01: 연도별 분모가 20인 기각 수를 정책별로 나란히 표시한다.
    fig, ax = plt.subplots(figsize=(10, 4.5))
    years = np.arange(2020, 2027)
    for i, policy in enumerate(("A", "B", "base")):
        v = sy[sy.policy.eq(policy)].set_index("year").loc[years, "n_reject_asym"]
        ax.bar(years + (i - 1) * .24, v, width=.23, color=COL[policy], label=POL[policy])
    ax.set(xticks=years, ylim=(0, 20), ylabel="기각 ETF 수 / 20", xlabel="검정연도", title="그림 P01 · 연간 사후 CUSUM 기각 수")
    ax.axvspan(2019.5, 2020.5, color="#eee", zorder=-1)
    ax.axvspan(2025.5, 2026.5, color="#eee", zorder=-1)
    ax.text(2020, 19, "파일럿", ha="center", fontsize=8)
    ax.text(2026, 19, "부분·비블라인드", ha="center", fontsize=8)
    ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(.5, -.16), frameon=False)
    records.append(_save(fig, out, "P01_연도별_기각수", [sy_path], "20 ETF × 2020–2026, 원문 표기 임계값 1.3397. 2021–2025 합계 A 0/100, B 12/100, 기준선 6/100. 회색은 파일럿·부분 연도이며 기각은 실제 변화의 정답이 아니다."))

    # P02: 관측 통계량을 표시하고 임계값 이상인 칸에 점을 찍는다.
    pp = post.query("calibration_method == 'asymptotic' and (history_strategy == 'expanding' or policy == 'base') and 2021 <= year <= 2025")
    tickers = sorted(pp.ticker.unique())
    fig, axs = plt.subplots(1, 3, figsize=(13, 6), sharey=False)
    for ax, policy in zip(axs, ("A", "B", "base"), strict=True):
        one = pp[pp.policy.eq(policy)]
        mat = one.pivot(index="ticker", columns="year", values="annual_T").loc[tickers, [2021, 2022, 2023, 2024, 2025]]
        im = ax.imshow(mat.to_numpy(), vmin=0, vmax=max(2.5, float(pp.annual_T.max())), cmap="Blues", aspect="auto")
        rejects = one.pivot(index="ticker", columns="year", values="annual_reject").loc[mat.index, mat.columns].to_numpy(dtype=bool)
        yy, xx = np.where(rejects)
        ax.scatter(xx, yy, marker="o", s=25, facecolors="none", edgecolors="#d45332", linewidths=1.2)
        ax.set(xticks=range(5), xticklabels=mat.columns, title=POL[policy], xlabel="검정연도")
        ax.set_yticks(range(len(tickers)))
        ax.set_yticklabels(tickers if ax is axs[0] else [])
    fig.suptitle("그림 P02 · 연간 검정통계량 T와 임계값 이상 표시 (핵심 기간)")
    fig.subplots_adjust(left=.09, right=.87, top=.84, bottom=.12, wspace=.12)
    color_ax = fig.add_axes([.90, .17, .017, .62])
    fig.colorbar(im, cax=color_ax, label="관측 T (무차원)")
    records.append(_save(fig, out, "P02_검정통계량_히트맵", [post_path], "20 ETF × 2021–2025 × 3정책. 빈 원은 T≥1.3397인 판정, 색은 관측 T다. ETF는 독립 표본이 아니며 통계량의 크기가 경제적 효과를 뜻하지 않는다.", layout=False))

    # P03: PURE_OOS 60거래일 창의 묶음과 iid 귀무 기대를 동일 단위로 비교한다.
    grouped = core.groupby("policy")[["w60_pure_episodes_total", "w60_null_expected_total"]].sum().loc[["A", "B", "base"]]
    fig, ax = plt.subplots(figsize=(8, 4.8))
    x = np.arange(3)
    ax.bar(x - .18, grouped.w60_pure_episodes_total, width=.35, color="#2766a8", label="관측 경보 묶음")
    ax.bar(x + .18, grouped.w60_null_expected_total, width=.35, color="#aaa", hatch="//", label="iid 귀무 기대")
    ax.set(xticks=x, xticklabels=[POL[p] for p in grouped.index], ylabel="에피소드 수 (100 ETF-연도 합)", title="그림 P03 · 60거래일 이동 검정의 경보 빈도")
    ax.legend(loc="upper left", frameon=False)
    records.append(_save(fig, out, "P03_경보묶음_귀무기대", [sy_path], "20 ETF × 2021–2025, 60거래일 PURE_OOS, iid in-sample 귀무·200회 재표집/셀. 관측 A/B/기준선 26/171/346, 귀무 기대 132.22/132.975/135.675. 경보 묶음은 참탐지·오탐률이 아니다."))

    # P04: 같은 T에 적용되는 임계값의 명칭과 수치를 분리한다.
    cc = post.query("calibration_method in ['asymptotic', 'iid_insample', 'normal_mc', 'block_insample']")
    med = cc.groupby(["policy", "calibration_method"]).annual_critical.median()
    methods = ("asymptotic", "normal_mc", "iid_insample", "block_insample")
    labels = ("원문 표기\n1.3397", "정규 모의", "iid 재표집", "블록 재표집\n(다른 귀무)")
    fig, ax = plt.subplots(figsize=(9, 4.8))
    for policy, marker in zip(("A", "B", "base"), ("o", "s", "^"), strict=True):
        ax.plot(range(4), [med.loc[(policy, m)] for m in methods], marker=marker, color=COL[policy], label=POL[policy])
    ax.axhline(1.3581, color="#555", linestyle="--", label="정확 점근 5% ≈1.3581 (참고)")
    ax.set(xticks=range(4), xticklabels=labels, ylabel="연간 임계값 중앙값 (무차원)", title="그림 P04 · 보정 방법에 따른 연간 임계값")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), frameon=False)
    records.append(_save(fig, out, "P04_임계값_민감도", [post_path], "20 ETF × 2020–2026 = 140 ETF-연도/정책의 임계값 중앙값. 원문 표기 1.3397은 정확 점근 5% 1.3581과 다르다. 블록 재표집은 귀무 자체가 다르며 이 그림으로 우열을 정하지 않는다."))

    # P05: 귀무 크기는 합성 데이터의 반복 시행 비율만 보여준다.
    selected = syn.query("dgp_name in ['stable_low_variance_no_change', 'stable_heavy_tail', 'stable_garch_clustering'] and level == 'detector' and test == 'annual_posthoc' and calibration in ['asymptotic_1.3397', 'iid_history_bootstrap', 'block_history_bootstrap(L=10, different null)']")
    dgps = ("stable_low_variance_no_change", "stable_heavy_tail", "stable_garch_clustering")
    fig, ax = plt.subplots(figsize=(9, 4.7))
    for i, (_cal, label, hatch) in enumerate((("asymptotic_1.3397", "원문 표기 1.3397", ""), ("iid_history_bootstrap", "iid 보정", "//"), ("block_history_bootstrap(L=10, different null)", "블록 귀무", "xx"))):
        rows = [selected.query("dgp_name == @d and calibration == @_cal").iloc[0] for d in dgps]
        vals = np.array([row.rate for row in rows])
        errs = np.array([[row.rate - row.rate_ci_low for row in rows], [row.rate_ci_high - row.rate for row in rows]])
        ax.bar(np.arange(3) + (i - 1) * .25, vals, yerr=errs, capsize=2, width=.23, label=label, hatch=hatch, edgecolor="#333")
    ax.axhline(.05, color="#b23a35", linestyle="--", label="명목 5%")
    ax.set(xticks=range(3), xticklabels=["독립 정규", "두꺼운 꼬리 t5", "분산 군집 GARCH"], ylabel="합성 귀무 기각 비율 (R=1,000)", title="그림 P05 · 귀무 생성방법에 따른 검정 크기")
    ax.legend(ncol=2, loc="upper left", frameon=False)
    records.append(_save(fig, out, "P05_합성귀무_크기", [syn_path], "구조변화 없는 합성 잔차, 조건당 R=1,000, 막대 오차선은 Wilson 95% 구간. iid/t5의 원문값 크기 0.036/0.035, 군집 귀무에서는 훨씬 크다. 합성 귀무 크기는 실제 ETF 변화의 참값이 아니다."))

    # P06: 검정 기간을 맞춘 학습 이력 대조의 판정 차이를 센다.
    # 기존 집계표의 정의를 사용하여 정책별 전체 대조 판정 차이를 표시한다.
    agg_path = results / "aggregates.csv"
    agg = pd.read_csv(agg_path).set_index("name").value
    fig, ax = plt.subplots(figsize=(6.8, 4.2))
    vals = [float(agg["h_verdict_diff_A"]), float(agg["h_verdict_diff_B"])]
    ax.bar([0, 1], vals, color=[COL["A"], COL["B"]], width=.5)
    ax.set(xticks=[0, 1], xticklabels=["정책 A", "정책 B"], ylabel="확장 이력 대비 판정 차이 / 220 대조", title="그림 P06 · 학습 이력 선택과 검정 판정")
    for i, v in enumerate(vals):
        ax.text(i, v + 1, f"{int(v)} / 220", ha="center")
    ax.set_ylim(0, max(vals) * 1.25)
    records.append(_save(fig, out, "P06_학습이력_판정차이", [hist_path, agg_path], "동일 검정연도·같은 날짜에서 expanding과 trailing 2y/frozen 2019 대조. 220개/정책 중 A 9, B 46개 판정 차이. 학습 이력 민감도이며 모형의 인과 효과나 탐지 정확도가 아니다."))

    index = pd.DataFrame(records)
    index.to_csv(out / "presentation_figure_index.csv", index=False, lineterminator="\n")
    return index

# ruff: noqa: E501
"""10번 발표용 인포그래픽 2장 (밝은 판, Pretendard) — IG10-1 정의 비교·우연 기준선 · IG10-2 C1 세 구간 해부.

사용: R2H .venv/bin/python scripts/t19_infographics_light.py
숫자는 모두 pipeline.run() + lock2.run() 결과에서 계산한다. 출력: research/common_volatility_candidates_10/infographics/
"""

from __future__ import annotations

import glob
import os
import sys
from pathlib import Path

for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[key] = "1"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

from r2h.common_vol import lock2 as L  # noqa: E402
from r2h.common_vol import pipeline as P  # noqa: E402

OUT = ROOT / "research/common_volatility_candidates_10/infographics"
FONT_DIR = Path.home() / ".local/share/fonts/pretendard"
BG, CARD, EDGE, INK, INK2, MUTED, GRID = "#f7f6f2", "#ffffff", "#e4e1d8", "#16171b", "#3d4048", "#7a7e87", "#e9e7e1"
RED, BLUE, GREEN, AMBER, PURPLE = "#e5484d", "#2563eb", "#0f9f6e", "#d97706", "#6e56cf"
CLS_COL = {"주식": BLUE, "채권": GREEN, "원자재": AMBER, "통화": PURPLE}
P0, P1 = pd.Timestamp("2021-01-04"), pd.Timestamp("2025-12-30")


def theme() -> None:
    files = sorted(glob.glob(str(FONT_DIR / "Pretendard-*.otf")))
    if len(files) < 4:
        raise FileNotFoundError(f"Pretendard 글꼴이 없습니다: {FONT_DIR}")
    for f in files:
        font_manager.fontManager.addfont(f)
    plt.rcParams.update({"font.family": "Pretendard", "axes.unicode_minus": True, "figure.facecolor": BG, "axes.facecolor": "none",
                         "savefig.facecolor": BG, "text.color": INK, "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED,
                         "axes.edgecolor": EDGE, "svg.hashsalt": "t19_infographics_light"})


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.png", dpi=300, metadata={"Software": None})
    fig.savefig(OUT / f"{name}.svg", metadata={"Date": None, "Creator": None})
    plt.close(fig)


def card(fig, x, y, w, h):
    fig.patches.append(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.003,rounding_size=0.010", transform=fig.transFigure,
                                      facecolor=CARD, edgecolor=EDGE, lw=0.9, zorder=-5))


def clean(ax, grid=True):
    for s in ("top", "right", "bottom"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(EDGE)
    ax.tick_params(length=0, labelsize=9.5)
    if grid:
        ax.grid(axis="y", color=GRID, lw=0.7)
    ax.set_axisbelow(True)


def label(ax, text, y=1.03):
    ax.text(0, y, text, transform=ax.transAxes, fontsize=10.5, weight=600, color=INK2, va="bottom")


def classes(R, X):
    st = R["states"]
    eg = st["eg"].drop_duplicates("exposure_group").set_index("exposure_group")
    m = {"broad_market": "주식", "sector": "주식", "theme": "주식", "strategy": "주식", "leveraged_inverse": "주식",
         "rates": "채권", "money_market": "채권", "commodity": "원자재", "currency": "통화"}
    return {g: m[eg.loc[g, "category"]] for g in st["groups"]}


def ig1(R, X):
    d = R["daily"]
    p = d[d["period"] == "PRIMARY"]
    dts = pd.DatetimeIndex(p["date"])
    iv = R["intervals"]
    ks = X["kstar"].set_index("q")
    nt = X["null"]
    c1 = iv[(iv["rule"] == "q20_k9") & (iv["period"] == "PRIMARY")]
    c4 = iv[(iv["rule"] == "q60_k6") & (iv["period"] == "PRIMARY")]
    pf = lambda q, k: float(nt[(nt["q"] == q) & (nt["k"] == k)]["p_fw_null"].iloc[0])  # noqa: E731
    ll = X["lead_lag"]
    lag = int(ll.loc[ll["corr"].idxmax(), "lag"])
    ext = X["c1_exit"]
    e24 = ext[ext["interval_id"] == c1.iloc[1]["interval_id"]]
    fig = plt.figure(figsize=(20, 11.25))
    fig.text(0.035, 0.937, "시장 공통 급변, 우연과 비교하면", fontsize=31, weight=800)
    fig.text(0.035, 0.900, "17개 노출 그룹 · 2021–2025 · N_A = 같은 날 급변인 그룹 수 · 귀무 = 그룹별 급변 시계열 독립 원형 이동 2,000회", fontsize=12.5, color=MUTED)
    tiles = [(f"{int(c1['duration_trading_days'].sum())}일", f"C1 {len(c1)}구간 (20일 ≥ 9)", INK),
             (f"k* = {int(ks.loc[20, 'k_star_fw'])}", "20일 우연 기준 문턱", RED),
             (f"{pf(60, 6):.0%}", "C4 의 우연 확률", AMBER),
             (f"{lag}일", "20일 → 60일 시차", PURPLE),
             (f"{int(e24['window_exit'].sum())}/{len(e24)}", "2024-08 종료 = 창 이탈", INK)]
    for k, (v, lab, c) in enumerate(tiles):
        x = 0.555 + k * 0.085
        fig.text(x, 0.928, v, fontsize=22, weight=800, color=c)
        fig.text(x, 0.903, lab, fontsize=9.4, color=MUTED)
    card(fig, 0.025, 0.07, 0.6, 0.81)
    ax1 = fig.add_axes([0.06, 0.53, 0.55, 0.30])
    ax2 = fig.add_axes([0.06, 0.13, 0.55, 0.30], sharex=ax1)
    for ax, q, rule_iv, kc, col, name in ((ax1, 20, c1, 9, BLUE, "C1"), (ax2, 60, c4, 6, AMBER, "C4")):
        for _, r in rule_iv.iterrows():
            ax.axvspan(pd.Timestamp(r["start"]), pd.Timestamp(r["end"]) + pd.Timedelta(days=1), color=col, alpha=0.18, lw=0)
        y = p[f"n_A_q{q}"].to_numpy(float)
        ax.fill_between(dts, y, step="post", color=col, alpha=0.25, lw=0)
        ax.plot(dts, y, drawstyle="steps-post", color=col, lw=0.9)
        kf, kd = int(ks.loc[q, "k_star_fw"]), int(ks.loc[q, "k_star_day"])
        ax.axhline(kf, color=RED, lw=1.4)
        ax.text(dts[-1], kf + 0.25, f"우연 기준 k*_fw = {kf} (5년 중 하루라도 우연히 넘을 확률 < 5%)", ha="right", fontsize=9.2, color=RED)
        ax.axhline(kd, color=MUTED, lw=1, ls=(0, (4, 3)))
        ax.text(dts[-1], kd + 0.25, f"일별 우연 1% 선 k*_day = {kd}", ha="right", fontsize=8.8, color=MUTED)
        ax.axhline(kc, color=col, lw=1, ls=(0, (2, 2)))
        ax.text(dts[2], kc + 0.25, f"{name} 문턱 k = {kc}", fontsize=9.2, color=col, weight=600)
        ax.set_ylim(0, 13.5)
        clean(ax)
        ax.set_ylabel("같은 날 급변 그룹 수", fontsize=9.5)
    label(ax1, f"20일 변동성 — 관측 최대 {int(ks.loc[20, 'obs_max'])} · C1 의 k=9 가 우연 기준과 정확히 일치")
    label(ax2, f"60일 변동성 — 관측 최대 {int(ks.loc[60, 'obs_max'])} < k*_fw {int(ks.loc[60, 'k_star_fw'])} · C4 는 우연과 구별되지 않는다")
    plt.setp(ax1.get_xticklabels(), visible=False)
    ax2.xaxis.set_major_locator(mdates.YearLocator())
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax2.tick_params(axis="x", labelsize=11, colors=INK2)
    ax2.set_xlim(P0, P1 + pd.Timedelta(days=1))
    # 오른쪽 위: 우연 곡선
    card(fig, 0.64, 0.47, 0.335, 0.41)
    ax3 = fig.add_axes([0.675, 0.53, 0.28, 0.28])
    for q, col in ((20, BLUE), (60, AMBER)):
        x = nt[(nt["q"] == q) & (nt["k"].between(4, 13))]
        ax3.plot(x["k"], x["p_fw_null"], color=col, marker="o", ms=5, lw=2, label=f"{q}일")
    ax3.axhline(0.05, color=RED, lw=1, ls=(0, (4, 3)))
    ax3.text(13, 0.07, "5%", color=RED, fontsize=9, ha="right")
    for c, (q, k, col) in {"C1": (20, 9, BLUE), "C2": (20, 10, BLUE), "C4": (60, 6, AMBER)}.items():
        ax3.annotate(f"{c} {pf(q, k):.4f}" if c == "C2" else f"{c} {pf(q, k):.3f}", (k, pf(q, k)), xytext=(8, 10 if c != "C2" else -16), textcoords="offset points", fontsize=9.5, color=col, weight=600)
    ax3.set_xticks(range(4, 14))
    ax3.set_xlabel("최소 동시 급변 그룹 수 k", fontsize=9.5)
    ax3.set_ylabel("우연 확률 (기간 최대)", fontsize=9.5)
    ax3.legend(fontsize=9, frameon=False)
    clean(ax3)
    label(ax3, "우연히 '5년 중 하루라도' N_A ≥ k 일 확률", y=1.06)
    # 오른쪽 아래: 정의별 판정
    card(fig, 0.64, 0.07, 0.335, 0.37)
    rows = [("C1 · 20일 ≥ 9", f"우연 {pf(20, 9):.3f}", "통과 — 문턱이 우연 기준과 같다", BLUE),
            ("C2 · 20일 ≥ 10", f"우연 {pf(20, 10):.4f}", "통과 — 단, 2024-08 을 3조각 (이력 H2 로 이음)", BLUE),
            ("C3 · 20일 ≥ 12", f"우연 {pf(20, 12):.4f}", "통과 — 2025-04 한 구간 (관측 최대 = k)", BLUE),
            ("C4 · 60일 ≥ 6", f"우연 {pf(60, 6):.3f}", "미통과 — 우연과 구별되지 않음", AMBER),
            ("WB · 자산군 균형", f"{len(X['wb_intervals'])}구간", "2024-08 이 사라짐 (비주식 0 · 주식만)", GREEN)]
    fig.text(0.655, 0.405, "정의별 판정", fontsize=14, weight=800)
    for i, (a, b, c, col) in enumerate(rows):
        y = 0.36 - i * 0.056
        fig.text(0.655, y, "●", fontsize=12, color=col)
        fig.text(0.67, y, a, fontsize=11, weight=700)
        fig.text(0.79, y, b, fontsize=10.5, color=INK2)
        fig.text(0.67, y - 0.022, c, fontsize=9.6, color=MUTED)
    fig.text(0.975, 0.025, "R2H · 10-lock-2 (10-lock-1 결과를 본 뒤 설계한 확장) · 그룹 A = 09 · 귀무 시드 20261019", fontsize=8.5, color=MUTED, ha="right")
    save(fig, "IG10_1_definitions_vs_chance")
    return {"kstar20": int(ks.loc[20, "k_star_fw"]), "p_c4": round(pf(60, 6), 4)}


def ig2(R, X):
    st, d = R["states"], R["daily"]
    cl = classes(R, X)
    iv = R["intervals"]
    c1 = iv[(iv["rule"] == "q20_k9") & (iv["period"] == "PRIMARY")].reset_index(drop=True)
    contrib = X["contrib"]
    ent, ext = X["c1_entry"], X["c1_exit"]
    pk = X["c1_intensity_peak"].set_index("interval_id")
    wb = X["wb_intervals"]
    fig = plt.figure(figsize=(20, 11.25))
    fig.text(0.035, 0.937, "같은 C1, 다른 자산 — 세 번의 시장 공통 급변", fontsize=31, weight=800)
    fig.text(0.035, 0.900, "C1 = 17개 노출 그룹 중 같은 날 9개 이상 급변 (20일) · 각 열 = 한 구간 · 위: 어느 자산군이 얼마나 (강도 기여) · 가운데: 그룹이 들어온 순서 · 아래: 끝난 이유", fontsize=12.5, color=MUTED)
    titles = {0: "2022 금리·달러 충격", 1: "2024-08 국내 주식 급락", 2: "2025-04 다자산 관세 충격"}
    A = st["mats"][20]["A"]
    for k, (_, r) in enumerate(c1.iterrows()):
        x0 = 0.03 + k * 0.325
        card(fig, x0, 0.06, 0.31, 0.82)
        s, e = int(r["i0"]), int(r["i1"])
        lo, hi = s - 25, e + 12
        dts = st["dates"][lo:hi + 1]
        fig.text(x0 + 0.015, 0.835, titles[k], fontsize=17, weight=800)
        fig.text(x0 + 0.015, 0.81, f"{r['start']} ~ {r['end']} · {r['duration_trading_days']}거래일 · 최대 {r['max_n_A']}/17", fontsize=11, color=INK2)
        ax = fig.add_axes([x0 + 0.035, 0.63, 0.26, 0.15])
        stack = []
        for c in ("주식", "채권", "원자재", "통화"):
            gs = [g for g in st["groups"] if cl[g] == c]
            stack.append(contrib.loc[lo:hi, gs].sum(axis=1).to_numpy())
        ax.stackplot(dts, *stack, colors=[CLS_COL[c] for c in ("주식", "채권", "원자재", "통화")], alpha=0.9, labels=list(CLS_COL))
        ax.axvspan(st["dates"][s], st["dates"][e] + pd.Timedelta(days=1), color=RED, alpha=0.08, lw=0)
        ax.set_xticks([])
        clean(ax)
        if k == 0:
            ax.legend(fontsize=8.5, frameon=False, loc="upper left", ncol=4)
        eqs = float(pk.loc[r["interval_id"], "equity_share"])
        fig.text(x0 + 0.015, 0.595, f"정점 {pk.loc[r['interval_id'], 'peak_date']} 강도 기여 중 주식 {eqs:.0%}", fontsize=10.5, weight=700, color=BLUE if eqs > 0.5 else GREEN)
        e_iv = ent[ent["interval_id"] == r["interval_id"]].sort_values("entry_date")
        gi = [st["groups"].index(g) for g in e_iv["group"]]
        axm = fig.add_axes([x0 + 0.105, 0.23, 0.19, 0.34])
        mat = A[lo:hi + 1][:, gi].T
        cols = [CLS_COL[cl[st["groups"][j]]] for j in gi]
        img = np.full(mat.shape + (3,), 0.95)
        for i, c in enumerate(cols):
            rgb = matplotlib.colors.to_rgb(c)
            img[i, mat[i] == 1] = rgb
        edges = mdates.date2num(list(dts) + [dts[-1] + pd.Timedelta(days=1)])
        axm.pcolormesh(edges, np.arange(len(gi) + 1), np.zeros((len(gi), len(dts))), cmap=ListedColormap(["#f1efe9"]), shading="flat")
        for i in range(len(gi)):
            on = np.flatnonzero(mat[i] == 1)
            for t in on:
                axm.add_patch(matplotlib.patches.Rectangle((edges[t], i), edges[t + 1] - edges[t], 0.86, color=cols[i], lw=0))
        axm.set_ylim(len(gi), 0)
        axm.set_yticks(np.arange(len(gi)) + 0.43)
        axm.set_yticklabels([st["label"][st["groups"][j]].split(" ", 1)[-1] for j in gi], fontsize=8.6)
        axm.axvline(edges[s - lo], color=RED, lw=1)
        axm.axvline(edges[e - lo + 1], color=RED, lw=1)
        x_iv = ext[ext["interval_id"] == r["interval_id"]]
        for _, z in x_iv.iterrows():
            i = gi.index(st["groups"].index(z["group"]))
            axm.scatter([edges[e - lo + 1]], [i + 0.43], marker="<" if z["window_exit"] else "x", s=40, color=RED if z["window_exit"] else INK, zorder=5)
        axm.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=0, interval=2))
        axm.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
        axm.tick_params(length=0, labelsize=8)
        for sp in axm.spines.values():
            sp.set_visible(False)
        nwx = int(x_iv["window_exit"].sum())
        top_days = sorted(set(x_iv.loc[x_iv["window_exit"], "top_day"].astype(str)))
        in_wb = any((pd.Timestamp(a) <= pd.Timestamp(r["end"])) and (pd.Timestamp(b) >= pd.Timestamp(r["start"])) for a, b in zip(wb["start"], wb["end"]))
        lines = [f"끝난 이유: 빠진 그룹 {len(x_iv)}개 중 창 이탈 {nwx}개" + (f" (큰 하루 {', '.join(top_days)})" if top_days else ""),
                 f"자산군 균형(WB) 에서도 급변: {'예' if in_wb else '아니오 — 주식만의 급변'}",
                 f"먼저 들어온 그룹: {', '.join(st['label'][g].split(' ', 1)[-1] for g in e_iv['group'].head(3))}"]
        for i, ln in enumerate(lines):
            fig.text(x0 + 0.015, 0.165 - i * 0.03, ln, fontsize=10, color=INK2 if i else INK, weight=600 if i == 0 else 400)
    fig.text(0.035, 0.03, "◀ = 그 그룹의 20일 창에서 가장 큰 하루가 정확히 20거래일 전 — 그 하루가 창에서 빠지자 급변이 끝났다 · × = 그 밖의 종료 · 빨간 세로선 = 구간 시작·종료 다음 날 · 색 = 자산군", fontsize=10, color=MUTED)
    fig.text(0.975, 0.03, "R2H · 10-lock-2", fontsize=8.5, color=MUTED, ha="right")
    save(fig, "IG10_2_c1_three_intervals")
    return {"n": len(c1)}


def main():
    theme()
    R = P.run(ROOT)
    X = L.run(ROOT, R)
    print(ig1(R, X), ig2(R, X))


if __name__ == "__main__":
    main()

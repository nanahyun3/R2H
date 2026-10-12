"""최종 보고서 그림 — 결과표·캐시 잔차·EXTENSION 결과에서만 그린다 (사건 집합 미사용).

출력: ``figures/figNN_*.png`` (200 dpi) + 같은 이름 ``.svg``. 유의/비유의는 색이 아니라 마커 채움·선 모양으로도 구분한다.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager as fm
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from r2h.paper2020.cusum import centered_square_path, tau_squared
from r2h.svrgarch_etf.rolling import ASYMPTOTIC_5PCT, WINDOWS, rolling_cusum

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
RES = REPO / "research" / "svr_garch_cusum_etf" / "results"
FIG = HERE / "figures"
FIG.mkdir(parents=True, exist_ok=True)
STATE = Path(os.environ.get("T11_STATE", REPO / "outputs" / "cache" / "t11_state.npz"))
KOLM = 1.3581

fm.fontManager.addfont("/usr/share/fonts/truetype/nanum/NanumGothic.ttf")
fm.fontManager.addfont("/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf")
plt.rcParams.update(
    {
        "font.family": ["NanumGothic", "DejaVu Sans"],
        "axes.unicode_minus": False,
        "mathtext.fontset": "dejavusans",
        "font.size": 9,
        "axes.titlesize": 10,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "savefig.dpi": 200,
        "savefig.bbox": "tight",
    }
)
C_A, C_B, C_BASE, C_NULL = "#1f4e79", "#c55a11", "#6b6b6b", "#2e7d32"


def save(fig, name: str) -> None:
    fig.savefig(FIG / f"{name}.png")
    fig.savefig(FIG / f"{name}.svg")
    plt.close(fig)


def load():
    z = np.load(STATE, allow_pickle=True)
    idx = pd.DatetimeIndex(pd.to_datetime(z["dates"]))
    ref = pd.read_csv(REPO / "research" / "svr_garch_cusum_etf" / "reference_close_sha256.csv", dtype=str)
    names = dict(zip(ref.ticker, ref.name, strict=True))
    fit = pd.read_csv(RES / "fit_summary.csv", dtype={"ticker": str})
    return z, idx, names, fit


def box(ax, xy, w, h, text, fc="#eef3f8", ec="#1f4e79", fs=8.5, bold=False):
    ax.add_patch(FancyBboxPatch(xy, w, h, boxstyle="round,pad=0.02,rounding_size=0.03", fc=fc, ec=ec, lw=1.1))
    ax.text(xy[0] + w / 2, xy[1] + h / 2, text, ha="center", va="center", fontsize=fs,
            fontweight="bold" if bold else "normal", linespacing=1.35)


def arrow(ax, a, b, style="-|>", ls="-"):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle=style, mutation_scale=11, lw=1.1, color="#333333", linestyle=ls))


def fig01_pipeline() -> None:
    fig, ax = plt.subplots(figsize=(9.2, 4.0))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4.4)
    ax.axis("off")
    box(ax, (0.1, 2.9), 1.8, 1.0, "ETF 종가\n(20종, 1,902 수익률)\n$y_t=100\\,\\Delta\\log P_t$")
    box(ax, (2.3, 2.9), 2.2, 1.0, "변동성 proxy (m=5)\n$\\tilde\\sigma_t^2=(y_t^2+\\cdots+y_{t-4}^2)/5$")
    box(ax, (4.9, 2.9), 2.4, 1.0, "ε-SVR (RBF)\n$\\hat\\sigma_t^2=\\hat g(y_{t-1}^2,\\tilde\\sigma_{t-1}^2)$\n앞 70% 적합 · grid 27")
    box(ax, (7.7, 2.9), 2.2, 1.0, "표준화 잔차\n$\\hat\\varepsilon_t=y_t/\\hat\\sigma_t$")
    arrow(ax, (1.9, 3.4), (2.3, 3.4))
    arrow(ax, (4.5, 3.4), (4.9, 3.4))
    arrow(ax, (7.3, 3.4), (7.7, 3.4))
    box(ax, (5.2, 1.45), 2.0, 0.9, "정책 A: 검정 구간 입력 =\n관측 proxy (1차)", fc="#f4f6f8", ec=C_A, fs=8)
    box(ax, (7.5, 1.45), 2.4, 0.9, "정책 B: 검정 구간 입력 =\n재귀 예측 $\\hat\\sigma^2$ (민감도)", fc="#fbf1ea", ec=C_B, fs=8)
    arrow(ax, (8.8, 2.9), (8.8, 2.35))
    arrow(ax, (8.0, 2.9), (6.4, 2.35))
    box(ax, (0.1, 0.15), 3.1, 1.05, "① 사후 검정 (원 논문)\n검정 구간 571일 전체에 한 번\n$T_n$ 과 $\\hat k$ — 사후 추정", fc="#ffffff", ec="#333333", fs=8)
    box(ax, (3.45, 0.15), 3.1, 1.05, "② 이동창 반복 검정 (T11 제안)\n$[t-w+1,t]$, $w\\in\\{20,30,60,120,252\\}$\n시점 t 까지 정보만 사용", fc="#ffffff", ec="#333333", fs=8)
    box(ax, (6.8, 0.15), 3.1, 1.05, "③ 온라인 경보 시스템 · ④ 투자 판단\n오탐·지연 보장 / 수익 성과는\n이 보고서에서 검증하지 않음", fc="#f2f2f2", ec="#999999", fs=8)
    arrow(ax, (6.2, 1.45), (1.65, 1.2))
    arrow(ax, (6.2, 1.45), (5.0, 1.2))
    arrow(ax, (6.55, 0.67), (6.8, 0.67), ls="--")
    ax.text(5.0, 4.25, "SVR–GARCH CUSUM-of-squares 파이프라인과 네 가지 사용 형태의 구분", ha="center", fontsize=10, fontweight="bold")
    save(fig, "fig01_pipeline")


def fig02_fullsample(names) -> None:
    fs = pd.read_csv(HERE / "analysis" / "fullsample_recomputed.csv", dtype={"ticker": str})
    order = fs[fs.policy == "A"].sort_values("T").ticker.tolist()
    fig, ax = plt.subplots(figsize=(7.6, 6.4))
    ys = {t: i for i, t in enumerate(order)}
    for pol, col, mk, dy in (("A", C_A, "o", 0.18), ("B", C_B, "s", 0.0), ("base", C_BASE, "^", -0.18)):
        s = fs[fs.policy == pol]
        for _, r in s.iterrows():
            rej = r["T"] >= ASYMPTOTIC_5PCT
            ax.plot(r["T"], ys[r.ticker] + dy, mk, ms=6.5, mec=col, mfc=col if rej else "white", mew=1.3)
        ax.plot([], [], mk, mec=col, mfc="white", ms=6.5, mew=1.3,
                label={"A": "정책 A (관측 proxy)", "B": "정책 B (재귀 예측)", "base": "기준선 r/σ₆₀ (모형 없음)"}[pol])
    ax.axvline(ASYMPTOTIC_5PCT, color="black", lw=1.0, ls="-")
    ax.axvline(KOLM, color="black", lw=1.0, ls=":")
    ax.text(ASYMPTOTIC_5PCT - 0.02, len(order) - 0.2, "원문 1.3397", ha="right", fontsize=7.5)
    ax.text(KOLM + 0.02, len(order) - 0.2, "Kolmogorov 1.3581", ha="left", fontsize=7.5)
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([f"{t} {names[t]}" for t in order], fontsize=7.5)
    ax.set_xlabel("검정 구간 사후 CUSUM-of-squares 통계량 $T_n$ (n=571, 무차원)")
    ax.set_xlim(0.2, 2.45)
    ax.legend(loc="lower right", fontsize=7.5, frameon=False, title="채운 마커 = 1.3397 이상 (기각)", title_fontsize=7.5)
    ax.set_title("ETF 20종 사후 검정통계량 — 정책 A·B·기준선")
    save(fig, "fig02_fullsample_T")


def fig03_critical() -> None:
    crit = pd.read_csv(RES / "critical_values.csv", dtype={"ticker": str})
    fig, ax = plt.subplots(figsize=(7.0, 3.6))
    ws = list(WINDOWS)
    for rt, col, mk, lab in (("svrA", C_A, "o", "ETF 별 부트스트랩 (정책 A 적합 잔차)"), ("base", C_BASE, "^", "ETF 별 부트스트랩 (기준선 적합 잔차)")):
        g = crit[crit.rtype == rt].groupby("window").c_bootstrap
        x = np.arange(len(ws)) + (-0.08 if rt == "svrA" else 0.08)
        ax.vlines(x, g.min().to_numpy(), g.max().to_numpy(), color=col, lw=2.2, alpha=0.6)
        ax.plot(x, g.median().to_numpy(), mk, color=col, ms=6, label=lab + " (선 = 20종 범위, 점 = 중앙)")
    cn = crit.groupby("window").c_normal.first().to_numpy()
    ax.plot(np.arange(len(ws)), cn, "D--", color=C_NULL, ms=5, mfc="white", label="iid N(0,1) MC 20,000회 95%")
    ax.axhline(ASYMPTOTIC_5PCT, color="black", lw=1.0, label="원문 점근 1.3397")
    ax.axhline(KOLM, color="black", lw=1.0, ls=":", label="Kolmogorov 이론값 1.3581")
    ax.set_xticks(range(len(ws)))
    ax.set_xticklabels([f"w={w}" for w in ws])
    ax.set_ylabel("95% 임계값 (무차원)")
    ax.set_ylim(1.05, 1.42)
    ax.legend(fontsize=7, frameon=False, loc="lower right")
    ax.set_title("관측창 길이별 5% 임계값 — 유한표본 값은 점근값보다 작다")
    save(fig, "fig03_critical_values")


def fig04_rates() -> None:
    zr = pd.read_csv(HERE / "analysis" / "zone_rates.csv", dtype={"ticker": str})
    fig, axes = plt.subplots(1, 2, figsize=(9.0, 3.6), sharey=True)
    ws = list(WINDOWS)
    x = np.arange(len(ws))
    for ax, rt, title in ((axes[0], "svrA", "SVR 정책 A 잔차"), (axes[1], "base", "기준선 r/σ₆₀ 잔차")):
        g = zr[zr.rtype == rt].groupby("window")
        ax.plot(x, g.null_episodes_per_year.mean().to_numpy(), "D--", color=C_NULL, mfc="white", label="귀무 기대 (적합 잔차 iid 재표집)")
        ax.plot(x - 0.06, g.rate_fit_per_yr.mean().to_numpy(), "o:", color="#7f7f7f", mfc="white",
                label="관측 — 적합 구간 (in-sample)")
        ax.plot(x + 0.06, g.rate_test_per_yr.mean().to_numpy(), "o-", color=C_A if rt == "svrA" else C_BASE,
                label="관측 — 순수 검정 구간 (out-of-sample)")
        ax.set_xticks(x)
        ax.set_xticklabels([f"w={w}" for w in ws])
        ax.set_title(title)
        ax.grid(axis="y", alpha=0.3)
    axes[0].set_ylabel("연간 경보 에피소드 (20종 평균, 회/년)")
    axes[1].legend(fontsize=7, frameon=False, loc="upper right")
    fig.suptitle("관측창별 경보 빈도와 iid 귀무 기대값 — 귀무 기대값은 시계열 의존성을 반영하지 않는다", fontsize=10)
    save(fig, "fig04_alarm_rates")


def fig05_size_power() -> None:
    s = pd.read_csv(HERE / "extension" / "E2_pipeline_size_power_summary.csv")
    s["scenario"] = s.scenario.fillna("null")
    reps = pd.read_csv(HERE / "extension" / "E2_pipeline_size_power_reps.csv")
    reps["scenario"] = reps.scenario.fillna("null")
    fig, axes = plt.subplots(1, 3, figsize=(10.2, 3.5))
    keys = (("A", "정책 A", C_A), ("B", "정책 B", C_B), ("base", "기준선", C_BASE))
    for ax, sc, title in ((axes[0], "null", "귀무 (구조변화 없음): 경험적 크기"), (axes[1], "break", "대립 ($\\omega\\times3$): 경험적 검정력")):
        for i, (k, lab, col) in enumerate(keys):
            r = s[(s.scenario == sc) & (s.residual == k) & (s.measure == "posthoc_reject@paper_1.3397")].iloc[0]
            ax.bar(i, 100 * r.value, color="white", edgecolor=col, hatch="///" if k != "A" else "", lw=1.4)
            ax.errorbar(i, 100 * r.value, yerr=196 * r.mc_se, color="black", capsize=3, lw=1)
            ax.text(i, 100 * r.value + 196 * r.mc_se + 1.5, f"{100 * r.value:.1f}%", ha="center", fontsize=8)
        ax.axhline(5, color="black", ls="--", lw=1, label="명목 5%")
        ax.legend(fontsize=7, frameon=False, loc="upper left")
        ax.set_xticks(range(3))
        ax.set_xticklabels([k[1] for k in keys])
        ax.set_ylim(0, 100)
        ax.set_title(title, fontsize=9)
    axes[0].set_ylabel("사후 검정 기각률 (%, 오차막대 = ±1.96 MC SE)")
    ax = axes[2]
    br = reps[reps.scenario == "break"]
    for k, lab, col in keys:
        d = br[f"first_alarm_delay_{k}"].to_numpy(float)
        xs = np.arange(0, 287)
        ax.step(xs, [100 * np.mean(d <= v) for v in xs], where="post", color=col,
                ls={"A": "-", "B": "--", "base": ":"}[k], lw=1.6, label=lab)
    ax.set_xlabel("변화 시점 이후 거래일")
    ax.set_ylabel("첫 경보까지 도달한 반복 비율 (%)")
    ax.set_title("w=60 이동창: 변화 후 첫 경보 (누적)", fontsize=9)
    ax.legend(fontsize=7.5, frameon=False)
    ax.set_ylim(0, 100)
    fig.suptitle("합성 GARCH(1,1) 에 T11 파이프라인 전체를 적용한 크기·검정력 (R=500/시나리오, seed 20261012)", fontsize=10)
    fig.tight_layout()
    save(fig, "fig05_size_power")


def fig06_kospi_pair(z, idx, names, fit) -> None:
    sp = int(idx.searchsorted(pd.Timestamp(fit.set_index("ticker").loc["069500", "split_date"])))
    d = idx[sp:]
    fig, axes = plt.subplots(2, 1, figsize=(8.6, 5.6), sharex=True)
    for t, col, ls in (("069500", C_A, "-"), ("102110", C_B, "--")):
        f = fit.set_index("ticker").loc[t]
        axes[0].plot(d, np.sqrt(z[f"varA__{t}"][sp:]), color=col, ls=ls, lw=1.0,
                     label=f"{t} {names[t]} — $\\hat g$: C={f.C:g}, $\\gamma^2$={f.paper_gamma_squared:g}, $\\epsilon$={f.epsilon:g}")
        e = z[f"res__{t}__svrA"][sp:]
        e = e[np.isfinite(e)]
        path = centered_square_path(e) / (np.sqrt(e.size) * np.sqrt(tau_squared(e)))
        T = np.abs(path).max()
        axes[1].plot(d[: path.size], path, color=col, ls=ls, lw=1.2, label=f"{t}: $T_n$={T:.3f}")
    axes[0].set_ylabel("정책 A $\\hat\\sigma_t$ (%)")
    axes[0].legend(fontsize=7.5, frameon=False, loc="upper left")
    axes[0].set_title("동일 기초지수(KOSPI200) ETF 두 종 — 검정 구간 수익률 상관 0.9994")
    for s in (1, -1):
        axes[1].axhline(s * ASYMPTOTIC_5PCT, color="black", lw=0.9)
    axes[1].axhline(0, color="#aaaaaa", lw=0.6)
    axes[1].set_ylabel("정규화 CUSUM 경로\n(절대값 최대 = $T_n$)")
    axes[1].set_ylim(-1.6, 1.6)
    axes[1].legend(fontsize=7.5, frameon=False, loc="upper left", title="검은 실선 = ±1.3397", title_fontsize=7)
    save(fig, "fig06_kospi200_pair")


def fig07_timeline(z, idx, names, fit) -> None:
    t = "069500"
    sp = int(idx.searchsorted(pd.Timestamp(fit.set_index("ticker").loc[t, "split_date"])))
    crit = pd.read_csv(RES / "critical_values.csv", dtype={"ticker": str})
    r = z[f"r__{t}"]
    fig, axes = plt.subplots(3, 1, figsize=(9.0, 7.0), sharex=True, gridspec_kw={"height_ratios": [1.1, 1.1, 1.2]})
    for ax in axes:
        ax.axvspan(idx[0], idx[sp], color="#f0f0f0", zorder=0)
        ax.axvline(idx[sp], color="black", lw=0.8)
    axes[0].plot(idx, r, color="#444444", lw=0.5)
    axes[0].set_ylabel("일간 수익률 (%)")
    axes[0].set_title(f"{t} {names[t]} — 회색 배경 = 적합 구간 (정책 A in-sample), 흰 배경 = 검정 구간 (out-of-sample)")
    sig_base = np.abs(r / z[f"res__{t}__base"])
    axes[1].plot(idx, np.sqrt(z[f"varA__{t}"]), color=C_A, lw=0.8, label="정책 A $\\hat\\sigma_t$")
    vb = np.sqrt(z[f"varB__{t}"])
    axes[1].plot(idx[sp:], vb[sp:], color=C_B, lw=1.2, ls="--", label="정책 B $\\hat\\sigma_t$ (검정 구간 재귀)")
    axes[1].plot(idx, sig_base, color=C_BASE, lw=0.8, ls=":", label="기준선 $\\sigma_{t-1}(60)$")
    axes[1].set_ylabel("조건부 표준편차 (%)")
    axes[1].legend(fontsize=7.5, frameon=False, loc="upper left", ncol=3)
    for rt, col, ls, lab in (("svrA", C_A, "-", "정책 A"), ("base", C_BASE, ":", "기준선")):
        stat = rolling_cusum(z[f"res__{t}__{rt}"], 60)
        c = float(crit[(crit.ticker == t) & (crit.rtype == rt) & (crit.window == 60)].c_bootstrap.iloc[0])
        axes[2].plot(idx, stat / c, color=col, ls=ls, lw=0.9, label=f"{lab} $T_t(60)/c_{{60}}$ (c={c:.3f})")
    axes[2].axhline(1.0, color="black", lw=0.9)
    axes[2].set_ylabel("$T_t(60)$ / 임계값\n(1 이상 = 경보)")
    axes[2].legend(fontsize=7.5, frameon=False, loc="upper left", ncol=2)
    save(fig, "fig07_timeline_069500")


def fig08_dependence() -> None:
    e6 = pd.read_csv(HERE / "extension" / "E6_residual_dependence_etf.csv", dtype={"ticker": str})
    sim = pd.read_csv(HERE / "extension" / "E6_residual_dependence_sim.csv")
    e3 = pd.read_csv(HERE / "extension" / "E3_stationary_bootstrap.csv", dtype={"ticker": str})
    fig, axes = plt.subplots(1, 2, figsize=(10.0, 3.8), gridspec_kw={"width_ratios": [1.15, 1]})
    ax = axes[0]
    groups = [("svrA", "fit", "A 적합"), ("svrA", "test", "A 검정"), ("svrB", "test", "B 검정"), ("base", "fit", "기준선 적합"), ("base", "test", "기준선 검정")]
    rng = np.random.default_rng(0)
    for i, (rt, zn, lab) in enumerate(groups):
        v = e6[(e6.rtype == rt) & (e6.zone == zn)].lrv_over_tau2.to_numpy()
        col = {"svrA": C_A, "svrB": C_B, "base": C_BASE}[rt]
        ax.plot(i + rng.uniform(-0.12, 0.12, v.size), v, "o", mfc="white" if zn == "fit" else col, mec=col, ms=5)
        ax.hlines(np.median(v), i - 0.25, i + 0.25, color="black", lw=1.5)
    for j, (k, col) in enumerate((("A", C_A), ("B", C_B), ("base", C_BASE))):
        v = sim[f"lrv_{k}_test"].to_numpy()
        x = len(groups) + 0.3 + j * 0.7
        ax.boxplot(v, positions=[x], widths=0.45, patch_artist=True, showfliers=False,
                   boxprops={"facecolor": "white", "edgecolor": col}, medianprops={"color": "black"})
    ax.set_xticks(list(range(len(groups))) + [len(groups) + 0.3 + j * 0.7 for j in range(3)])
    ax.set_xticklabels([g[2] for g in groups] + ["합성 A", "합성 B", "합성 기준선"], rotation=30, ha="right", fontsize=7.5)
    ax.axhline(1.0, color="black", ls="--", lw=1)
    ax.set_ylabel("$\\hat\\varepsilon_t^2$ 장기분산 / $\\hat\\tau^2$ (Bartlett)")
    ax.set_title("잔차 제곱의 의존성 — 1 미만이면 검정이 보수적", fontsize=9)
    ax = axes[1]
    o = e3.sort_values("T_A")
    y = np.arange(len(o))
    ax.plot(o.c571_iid, y, "|", color=C_NULL, ms=9, mew=2, label="iid 재표집 95%")
    ax.plot(o.c571_sb20, y, "x", color="#7b1fa2", ms=6, label="stationary bootstrap 95% (블록 20)")
    for yy, (_, r) in zip(y, o.iterrows(), strict=True):
        filled = r.reject_iid or r.reject_sb20
        ax.plot(r.T_A, yy, "o", color=C_A, mfc=C_A if filled else "white", ms=5)
    ax.plot([], [], "o", color=C_A, mfc="white", label="정책 A $T_n$ (채움 = 어느 한 임계값 이상)")
    ax.set_yticks(y)
    ax.set_yticklabels(o.ticker, fontsize=7)
    ax.set_xlabel("값 (무차원)")
    ax.set_xlim(0.2, 2.3)
    ax.legend(fontsize=7, frameon=False, loc="upper center", bbox_to_anchor=(0.45, -0.13), ncol=2)
    ax.set_title("귀무 생성 방법에 따른 n=571 임계값", fontsize=9)
    fig.tight_layout()
    save(fig, "fig08_dependence_and_null")


def fig09_state_concept() -> None:
    fig, ax = plt.subplots(figsize=(9.0, 3.9))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4.3)
    ax.axis("off")
    for i, lab in enumerate(("$S_{t-1}$", "$S_t$", "$S_{t+1}$")):
        x = 0.5 + i * 2.6
        box(ax, (x, 2.75), 1.4, 0.8, f"잠재 상태\n{lab}", fc="#fdf6e3", ec="#8a6d3b")
        box(ax, (x, 0.7), 1.4, 0.8, f"관측\n{lab.replace('S', 'O')}", fc="#eef3f8", ec=C_A)
        arrow(ax, (x + 0.7, 2.75), (x + 0.7, 1.5))
        if i < 2:
            arrow(ax, (x + 1.4, 3.15), (x + 2.6, 3.15))
    ax.text(2.6, 3.62, "$P(S_t\\mid S_{t-1})$ 상태전이", fontsize=8, ha="center")
    ax.text(1.3, 2.05, "$P(O_t\\mid S_t)$\n관측모형", fontsize=8, ha="left")
    box(ax, (7.45, 1.65), 2.45, 1.0, "belief $P(S_t\\mid O_{1:t})$\n필터링 (HMM·상태공간)", fc="#ffffff", ec="#333333", fs=8)
    ax.plot([0.5, 6.95], [0.55, 0.55], color="#333333", lw=1.0, ls="--")
    arrow(ax, (6.95, 0.55), (8.6, 1.65), ls="--")
    ax.text(3.7, 0.38, "$O_{1:t}$ 누적", fontsize=7.5, ha="center")
    ax.text(5.0, 0.02, "$O_t$ 후보: 수익률 · 변동성 · 거래량 · 자산 간 관계 · CUSUM 통계량(진단 후보 중 하나, 상태 자체가 아님)", ha="center", fontsize=8)
    ax.text(5.0, 4.1, "후속 연구 개념도 — 관측 O, 잠재 상태 S, 사후 믿음 (가설 단계, 이번 보고서에서 추정하지 않음)", ha="center", fontsize=10, fontweight="bold")
    save(fig, "fig09_state_concept")


def fig10_cusum_toy() -> None:
    """입문용: 분산이 한 번 바뀌는 합성 자료에서 CUSUM-of-squares 경로가 어떻게 커지는지 (교육용 예시, seed 고정)."""
    rng = np.random.default_rng([20261012, 10])
    n, k_true = 400, 250
    e = np.concatenate([rng.standard_normal(k_true), 1.6 * rng.standard_normal(n - k_true)])
    e0 = rng.standard_normal(n)
    fig, axes = plt.subplots(1, 3, figsize=(10.4, 3.3))
    for ee, col, lab in ((e0, C_BASE, "분산 변화 없음"), (e, C_A, f"{k_true + 1}번째부터 표준편차 ×1.6")):
        axes[0].plot(np.arange(1, n + 1), ee**2, color=col, lw=0.6, alpha=0.8, label=lab)
        path = centered_square_path(ee) / (np.sqrt(n) * np.sqrt(tau_squared(ee)))
        T = np.abs(path).max()
        k = int(np.argmax(np.abs(path))) + 1
        axes[1].plot(np.arange(1, n + 1), path, color=col, lw=1.4, label=f"{lab}: $T_n$={T:.2f}, $\\hat k$={k}")
        axes[2].plot(np.arange(1, n + 1), np.cumsum(ee**2), color=col, lw=1.4, label=lab)
    axes[2].plot([0, n], [0, np.sum(e**2)], color=C_A, ls=":", lw=1)
    axes[2].plot([0, n], [0, np.sum(e0**2)], color=C_BASE, ls=":", lw=1)
    for s_ in (1, -1):
        axes[1].axhline(s_ * ASYMPTOTIC_5PCT, color="black", lw=0.9)
    axes[1].axvline(k_true, color=C_A, ls="--", lw=0.8)
    axes[0].set_title("① 잔차 제곱 $\\hat\\varepsilon_t^2$", fontsize=9)
    axes[2].set_title("③ 원래 누적합 (점선 = 분산 일정 시 직선, ②는 그 차이)", fontsize=9)
    axes[1].set_title("② 정규화 중심 누적합 — 절대값 최대 = $T_n$", fontsize=9)
    axes[0].legend(fontsize=7, frameon=False)
    axes[1].set_ylim(-3.9, 2.6)
    axes[1].legend(fontsize=7, frameon=False, loc="upper center")
    for ax in axes:
        ax.set_xlabel("시점 t")
    fig.suptitle("CUSUM-of-squares 검정의 작동 원리 (교육용 합성 예시, n=400, 검은 실선 ±1.3397)", fontsize=10)
    fig.tight_layout()
    save(fig, "fig10_cusum_toy")


def fig11_vol_overview(z, idx, names, fit) -> None:
    """입문용: ETF 별 연율화 변동성 — 적합 구간 대 검정 구간 (검정 구간에 고변동기가 몰린 점을 보인다)."""
    rows = []
    for t in [str(x) for x in z["tickers"]]:
        sp = int(idx.searchsorted(pd.Timestamp(fit.set_index("ticker").loc[t, "split_date"])))
        r = z[f"r__{t}"]
        rows.append((t, np.nanstd(r[:sp]) * np.sqrt(252), np.nanstd(r[sp:]) * np.sqrt(252)))
    d = pd.DataFrame(rows, columns=["t", "fit", "test"]).sort_values("test")
    fig, ax = plt.subplots(figsize=(7.4, 5.6))
    y = np.arange(len(d))
    ax.hlines(y, d.fit, d.test, color="#bbbbbb", lw=2)
    ax.plot(d.fit, y, "o", mfc="white", mec=C_A, ms=6, label="적합 구간 2019-01~2024-05")
    ax.plot(d.test, y, "o", color=C_B, ms=6, label="검정 구간 2024-05~2026-10")
    ax.set_yticks(y)
    ax.set_yticklabels([f"{t} {names[t]}" for t in d.t], fontsize=7.5)
    ax.set_xlabel("연율화 변동성 (%, 일간 100·Δlog 표준편차 × √252)")
    ax.set_xscale("log")
    ticks = [0.2, 0.5, 1, 2, 5, 10, 20, 50, 100]
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{x:g}" for x in ticks])
    ax.legend(fontsize=7.5, frameon=False, loc="lower right")
    ax.set_title("ETF 20종의 변동성 — 적합 구간 대 검정 구간")
    save(fig, "fig11_vol_overview")


def main() -> None:
    z, idx, names, fit = load()
    fig01_pipeline()
    fig02_fullsample(names)
    fig03_critical()
    fig04_rates()
    fig05_size_power()
    fig06_kospi_pair(z, idx, names, fit)
    fig07_timeline(z, idx, names, fit)
    fig08_dependence()
    fig09_state_concept()
    fig10_cusum_toy()
    fig11_vol_overview(z, idx, names, fit)
    print(json.dumps(sorted(p.name for p in FIG.glob("*.png"))))


if __name__ == "__main__":
    main()

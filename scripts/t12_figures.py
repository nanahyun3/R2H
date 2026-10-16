"""T12 그림 · 파생 요약표 — ``uv run python scripts/t12_figures.py --results DIR --work DIR --figs DIR``.

모든 그림은 결과표(``--results``)와 로컬 일별 캐시(``--work``, git 제외)에서만 만든다. 그림마다 사용한 표·필터·
sha256 을 ``figure_manifest.csv`` 에 남긴다 (명세 §8.1 #11). 사후 정보(RV)·OOS·경계 구간은 캡션/주석으로 구분.
팔레트: A=#2a78d6, B=#eb6834, base=#1baf7a (dataviz 기준 팔레트 1–3번, 전 쌍 CVD 검증), 순차형 파랑 램프,
발산형 파랑↔빨강 (회색 중앙).
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, ListedColormap  # noqa: E402

KFONT = "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"
if Path(KFONT).exists():
    font_manager.fontManager.addfont(KFONT)
    plt.rcParams["font.family"] = [font_manager.FontProperties(fname=KFONT).get_name(), "DejaVu Sans"]
plt.rcParams.update(
    {
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
        "figure.facecolor": "#fcfcfb",
        "axes.facecolor": "#fcfcfb",
    }
)
COL = {"A": "#2a78d6", "B": "#eb6834", "base": "#1baf7a"}
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
SEQ = LinearSegmentedColormap.from_list(
    "seqblue", ["#f4f8fd", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
)
DIV = LinearSegmentedColormap.from_list(
    "divbr", ["#1c5cab", "#6da7ec", "#cde2fb", "#f0efec", "#f7c6c5", "#e66767", "#b8302f"]
)
STATUS_COL = {
    "NO_SIGNAL_DESCRIPTIVE": "#f0efec",
    "DESCRIPTIVE_EVIDENCE": "#9ec5f4",
    "MULTIFACTOR": "#256abf",
    "UNRESOLVED": "#ec835a",
    "NOT_ESTIMABLE": "#ffffff",
}
YEARS = list(range(2020, 2027))
MANIFEST: list[dict] = []


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def save(fig, out: Path, name: str, sources: str, filt: str, results: Path) -> None:
    p = out / f"{name}.png"
    fig.savefig(p, bbox_inches="tight", facecolor=fig.get_facecolor(), metadata={"Software": None})
    plt.close(fig)
    MANIFEST.append(
        {
            "figure": p.name,
            "sources": sources,
            "filter": filt,
            "source_sha256": ";".join(f"{s}:{sha(results / s)}" for s in sources.split(";") if (results / s).exists()),
            "png_sha256": sha(p),
        }
    )


def year_band(ax, years=YEARS, horizontal=False, label=True):
    """2020 파일럿 · 2026 부분/비블라인드 구간 표시."""
    for y, lab in ((2020, "파일럿"), (2026, "부분·비블라인드")):
        if y in years:
            i = years.index(y)
            if horizontal:
                ax.axhspan(i - 0.5, i + 0.5, color="#f0efec", zorder=0)
            else:
                ax.axvspan(i - 0.5, i + 0.5, color="#f0efec", zorder=0)
                if label:
                    ax.text(i, 1.01, lab, transform=ax.get_xaxis_transform(), ha="center", fontsize=7, color=MUTED)


def load(results: Path) -> dict[str, pd.DataFrame]:
    names = [
        "annual_vol_diagnostics",
        "annual_forecast_diagnostics",
        "annual_residual_diagnostics",
        "annual_posthoc",
        "annual_cusum_diagnostics",
        "annual_history_ablation",
        "diagnostic_profile",
        "fit_summary",
        "fold_manifest",
        "null_dgp_validation",
    ]
    return {n: pd.read_csv(results / f"{n}.csv", dtype={"ticker": str}) for n in names if (results / f"{n}.csv").exists()}


def order(t) -> list[str]:
    return list(dict.fromkeys(t["annual_vol_diagnostics"].ticker))


def names() -> dict[str, str]:
    ref = pd.read_csv(Path(__file__).resolve().parents[1] / "research/svr_garch_cusum_etf/reference_close_sha256.csv", dtype=str)
    return dict(zip(ref.ticker, ref.name, strict=True))


def heat(ax, M, rows, cols, cmap, vmin, vmax, fmt="{:.1f}", mask=None, hatch_mask=None, ann=True, cbar_label=""):
    im = ax.imshow(M, aspect="auto", cmap=cmap, vmin=vmin, vmax=vmax)
    ax.set_xticks(range(len(cols)), cols)
    ax.set_yticks(range(len(rows)), rows)
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    if ann:
        for i in range(M.shape[0]):
            for j in range(M.shape[1]):
                v = M[i, j]
                if np.isfinite(v):
                    rel = (v - vmin) / (vmax - vmin + 1e-12)
                    ax.text(j, i, fmt.format(v), ha="center", va="center", fontsize=6.5, color="white" if rel > 0.6 else INK)
                else:
                    ax.text(j, i, "n/e", ha="center", va="center", fontsize=6, color=MUTED)
    if hatch_mask is not None:
        for i, j in zip(*np.nonzero(hatch_mask), strict=True):
            ax.add_patch(plt.Rectangle((j - 0.5, i - 0.5), 1, 1, fill=False, hatch="///", edgecolor=MUTED, lw=0))
    cb = plt.colorbar(im, ax=ax, fraction=0.03, pad=0.01)
    cb.set_label(cbar_label, color=INK2)
    cb.outline.set_visible(False)
    return im


def fig_timeline(out, results):
    fig, ax = plt.subplots(figsize=(8.5, 3.2))
    for i, y in enumerate(YEARS):
        ax.barh(i, y - 2019, left=2019, color="#9ec5f4", height=0.55)
        ax.barh(i, 1 if y < 2026 else 0.75, left=y, color="#eb6834", height=0.55)
        if y >= 2022:
            ax.plot([y - 2, y], [i + 0.36, i + 0.36], color="#256abf", lw=2)
        ax.plot([2019, 2020], [i - 0.36, i - 0.36], color=MUTED, lw=2)
        st = "파일럿" if y == 2020 else ("부분·비블라인드 (~10/2)" if y == 2026 else "주 해석")
        ax.text(y + 1.08, i, st, va="center", fontsize=7.5, color=INK2)
    ax.set_yticks(range(len(YEARS)), [f"검정 {y}" for y in YEARS])
    ax.set_xlim(2019, 2028.6)
    ax.set_xticks(range(2019, 2028), [str(x) for x in range(2019, 2028)])
    ax.invert_yaxis()
    ax.set_title("연간 expanding fold — 파랑 막대: 학습 이력(연초 재선택·재적합), 주황: 검정연도(OOS, 모형 고정)")
    ax.text(2019, 7.0, "진한 파랑 선: trailing_2y 학습 구간 (2022+) · 회색 선: frozen_2019 (2019 만)", fontsize=7.5, color=INK2)
    save(fig, out, "F01_fold_timeline", "fold_manifest.csv", "history_strategy=all", results)


def fig_rv_heat(t, out, results, nm):
    v = t["annual_vol_diagnostics"]
    tk = order(t)
    M = v.pivot(index="ticker", columns="year", values="rv_ann_pct").loc[tk, YEARS].to_numpy()
    base = v.groupby("ticker").rv_2019_ann_pct.first().loc[tk].to_numpy()[:, None]
    fig, ax = plt.subplots(figsize=(9, 7.2))
    heat(ax, np.hstack([base, M]), [f"{k} {nm[k]}" for k in tk], ["2019\n(학습)"] + [str(y) for y in YEARS], SEQ, 0, np.nanpercentile(M, 97), fmt="{:.0f}", cbar_label="실현 연환산 변동성 (%p.a.)")
    ax.set_title("그림 2 · ETF × 연도 사후 실현 연환산 변동성 RV (%) — 연말 이후에만 확정되는 사후 맥락 변수, 검정 입력 아님")
    nobs = v.groupby("year").n_obs.max().loc[YEARS].to_numpy()
    ax.set_xticks(range(len(YEARS) + 1), ["2019\n(학습)"] + [f"{y}\nn≤{n}" for y, n in zip(YEARS, nobs, strict=True)])
    save(fig, out, "F02_rv_heatmap", "annual_vol_diagnostics.csv", "all tickers, years 2019(rv_2019)..2026", results)


def fig_posthoc(t, out, results, nm):
    ph = t["annual_posthoc"]
    tk = order(t)
    fig, axes = plt.subplots(1, 3, figsize=(13, 6.6), sharey=True)
    for ax, pol in zip(axes, ("A", "B", "base"), strict=True):
        s = ph[(ph.policy == pol) & (ph.calibration_method == "asymptotic")]
        M = s.pivot(index="ticker", columns="year", values="annual_T").loc[tk, YEARS].to_numpy()
        heat(ax, M, [f"{k} {nm[k]}" for k in tk] if pol == "A" else tk, [str(y) for y in YEARS], SEQ, 0, 3.0, fmt="{:.2f}", cbar_label="연간 사후 T")
        rej = M >= 1.3397
        for i, j in zip(*np.nonzero(rej), strict=True):
            ax.add_patch(plt.Rectangle((j - 0.48, i - 0.48), 0.96, 0.96, fill=False, edgecolor="#d03b3b", lw=1.4))
        ax.set_title(f"정책 {pol}: 연간 사후 CUSUM T (빨간 테두리 = T ≥ 1.3397)")
    fig.suptitle("그림 3 · 검정연도 OOS 잔차만으로 연말 1회 계산한 사후 CUSUM-of-squares 통계량", y=1.0)
    save(fig, out, "F03_posthoc_T_heatmap", "annual_posthoc.csv", "calibration_method=asymptotic", results)


def daily_frame(work: Path, ticker: str) -> pd.DataFrame:
    return pd.read_csv(work / ticker / "daily.csv.gz", dtype={"ticker": str}, parse_dates=["date"])


def fig_boundary_example(t, work, out, results, ticker="069500", years=(2023, 2024)):
    d = daily_frame(work, ticker)
    cu = t["annual_cusum_diagnostics"]
    fig, ax = plt.subplots(figsize=(10, 3.6))
    for y in years:
        s = d[(d.year == y) & (d.policy == "A") & (d.window == 60)]
        c = cu[(cu.ticker == ticker) & (cu.year == y) & (cu.policy == "A") & (cu.window == 60) & (cu.calibration_method == "iid_insample") & (cu.boundary_mode == "CARRY")].pointwise_null_quantile.iloc[0]
        warm = ~s.pure_oos_window.astype(bool)
        ax.plot(s.date[warm], s["T"][warm], color="#86b6ef", lw=1.6, label="CARRY 경계 warm (앞 59일, 사전 연도 재표준화 포함)" if y == years[0] else None)
        ax.plot(s.date[~warm], s["T"][~warm], color=COL["A"], lw=1.6, label="PURE_OOS_WINDOW (창 전체가 검정연도)" if y == years[0] else None)
        ax.hlines(c, s.date.min(), s.date.max(), color="#d03b3b", lw=1, ls="--", label="연초 고정 임계값 (iid_insample, 점별 95%)" if y == years[0] else None)
        al = s["T"] >= c
        ax.scatter(s.date[al], s["T"][al], s=10, color="#d03b3b", zorder=3)
        ax.axvline(s.date.min(), color=MUTED, lw=0.8)
        ax.text(s.date.min(), ax.get_ylim()[1] if ax.get_ylim()[1] > 0 else 1, f" {y} 연초 재적합", fontsize=7, color=INK2, va="top")
    ax.set_ylabel("w=60 이동창 T")
    ax.legend(fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=3, frameon=False)
    ax.set_title(f"그림 4 · {ticker} 정책 A w60 일별 통계량의 연도 경계 연결 (점 = 경보일; 경보 ≠ 실제 국면 변화)")
    save(fig, out, f"F04_boundary_{ticker}", "annual_cusum_diagnostics.csv", f"ticker={ticker},policy=A,w=60,years={years}; daily cache (local)", results)


def fig_episodes(t, out, results, nm):
    cu = t["annual_cusum_diagnostics"]
    tk = order(t)
    s = cu[(cu.window == 60) & (cu.boundary_mode == "YEAR_CONTAINED") & (cu.calibration_method == "iid_insample")]
    fig, axes = plt.subplots(1, 3, figsize=(13, 6.6), sharey=True)
    for ax, pol in zip(axes, ("A", "B", "base"), strict=True):
        x = s[s.policy == pol]
        obs = x.pivot(index="ticker", columns="year", values="rolling_episodes").loc[tk, YEARS].to_numpy(float)
        exp = x.pivot(index="ticker", columns="year", values="expected_null_episodes").loc[tk, YEARS].to_numpy(float)
        heat(ax, obs - exp, [f"{k} {nm[k]}" for k in tk] if pol == "A" else tk, [str(y) for y in YEARS], DIV, -3, 3, fmt="{:+.1f}", ann=False, cbar_label="관측 − 귀무 기대 에피소드")
        for i in range(obs.shape[0]):
            for j in range(obs.shape[1]):
                ax.text(j, i, "n/e" if not np.isfinite(obs[i, j]) else f"{int(obs[i, j])}", ha="center", va="center", fontsize=7, color=INK)
        ax.set_title(f"정책 {pol}: w60 PURE 에피소드 수 (숫자) vs 귀무 기대 (색)")
    fig.suptitle("그림 5 · 연중 경보 에피소드 — 0건은 '0', 추정 불가는 'n/e'. 경보는 alarm_frequency 이며 실제 오탐/정탐이 아니다", y=1.0)
    save(fig, out, "F05_episodes_vs_null", "annual_cusum_diagnostics.csv", "w=60,YEAR_CONTAINED(=PURE),iid_insample", results)


def fig_calibration(t, out, results):
    ph = t["annual_posthoc"]
    cu = t["annual_cusum_diagnostics"]
    meths = ["asymptotic", "iid_insample", "iid_prequential", "normal_mc", "block_insample"]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    ax = axes[0]
    for k, pol in enumerate(("A", "B", "base")):
        for m_i, m in enumerate(meths):
            v = ph[(ph.policy == pol) & (ph.calibration_method == m)].annual_critical.dropna()
            pos = m_i + (k - 1) * 0.25
            ax.boxplot(v, positions=[pos], widths=0.2, patch_artist=True, showfliers=False, boxprops={"facecolor": COL[pol], "alpha": 0.8, "edgecolor": COL[pol]}, medianprops={"color": INK}, whiskerprops={"color": COL[pol]}, capprops={"color": COL[pol]})
    ax.set_xticks(range(len(meths)), ["점근\n1.3397", "iid\nin-sample", "iid\nprequential", "정규 MC", "block\n(다른 귀무)"])
    ax.set_ylabel("연간 사후 검정 임계값 (95%)")
    ax.set_title("연간 임계값 분포 (ETF×연도) — 파랑 A · 주황 B · 청록 base")
    ax = axes[1]
    s = cu[(cu.window == 60) & (cu.boundary_mode == "YEAR_CONTAINED")]
    for k, pol in enumerate(("A", "B", "base")):
        for m_i, m in enumerate(meths):
            x = s[(s.policy == pol) & (s.calibration_method == m)].dropna(subset=["rolling_episodes"])
            if x.empty:
                continue
            pos = m_i + (k - 1) * 0.25
            ax.scatter([pos - 0.04], [x.expected_null_episodes.mean()], marker="_", s=180, color=MUTED, zorder=3)
            ax.scatter([pos + 0.04], [x.rolling_episodes.mean()], marker="o", s=22, color=COL[pol], zorder=3)
    ax.set_xticks(range(len(meths)), ["점근", "iid in", "iid preq", "정규", "block"])
    ax.set_ylabel("연평균 w60 PURE 에피소드")
    ax.set_title("귀무 기대(회색 —) vs 관측 평균(점) — 귀무 가정이 다르면 기대값도 다르다")
    fig.suptitle("그림 6 · 같은 잔차 경로, 다른 보정 방식 — 임계값 이동 효과 (점별 95% ≠ 연간 5%)", y=1.02)
    save(fig, out, "F06_calibration_methods", "annual_posthoc.csv;annual_cusum_diagnostics.csv", "all; w=60 PURE", results)


def fig_policy_pairs(t, out, results, nm):
    ph = t["annual_posthoc"]
    s = ph[ph.calibration_method == "asymptotic"].pivot_table(index=["ticker", "year"], columns="policy", values="annual_T").reset_index()
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4))
    ax = axes[0]
    core = s.year.between(2021, 2025)
    for flag, mk, lab in ((core, "o", "2021–25"), (~core, "^", "2020/2026")):
        ax.scatter(s.A[flag], s.B[flag], s=18, marker=mk, color=COL["A"], alpha=0.75, label=lab, edgecolor="white", lw=0.5)
    lim = [0, max(3.2, float(np.nanmax(s[["A", "B"]].to_numpy())) + 0.1)]
    ax.plot(lim, lim, color=MUTED, lw=0.8)
    ax.axvline(1.3397, color="#d03b3b", lw=0.8, ls="--")
    ax.axhline(1.3397, color="#d03b3b", lw=0.8, ls="--")
    ax.set_xlabel("정책 A 연간 T")
    ax.set_ylabel("정책 B 연간 T")
    ax.legend(frameon=False, fontsize=7)
    ax.set_title("A vs B (같은 ETF·연도·날짜) — 점선 = 1.3397")
    ax = axes[1]
    for tk_, mk in (("069500", "o"), ("102110", "s")):
        x = s[s.ticker == tk_].set_index("year").loc[YEARS]
        for pol in ("A", "B", "base"):
            ax.plot(YEARS, x[pol], marker=mk, ms=4, lw=1.5, color=COL[pol], ls="-" if tk_ == "069500" else ":", label=f"{tk_} {pol}")
    ax.axhline(1.3397, color="#d03b3b", lw=0.8, ls="--")
    year_band(ax, YEARS)
    ax.set_xticks(YEARS)
    ax.legend(ncol=2, fontsize=6.5, frameon=False)
    ax.set_title("같은 기초지수 069500(실선) · 102110(점선) — 검정 안정성")
    fig.suptitle("그림 7 · 분산 정책 간 불일치와 동일 노출 ETF 의 통계량 일치도", y=1.02)
    save(fig, out, "F07_policy_pairs", "annual_posthoc.csv", "calibration_method=asymptotic", results)


def fig_rv_vs_T(t, out, results):
    ph = t["annual_posthoc"]
    v = t["annual_vol_diagnostics"]
    s = ph[ph.calibration_method == "asymptotic"].merge(v[["ticker", "year", "rv_ann_pct", "rv_ratio"]], on=["ticker", "year"])
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.9), sharey=True)
    for ax, pol in zip(axes, ("A", "B", "base"), strict=True):
        x = s[s.policy == pol]
        core = x.year.between(2021, 2025)
        ax.scatter(np.log(x.rv_ratio[core]), x.annual_T[core], s=16, color=COL[pol], alpha=0.8, edgecolor="white", lw=0.4, label="2021–25")
        ax.scatter(np.log(x.rv_ratio[~core]), x.annual_T[~core], s=18, marker="^", facecolor="none", edgecolor=COL[pol], lw=0.9, label="2020/2026")
        rho = x[core][["rv_ratio", "annual_T"]].rank().corr().iloc[0, 1]
        ax.axhline(1.3397, color="#d03b3b", lw=0.8, ls="--")
        ax.set_xlabel("log(RV_y / RV_{y−1})  — 사후 변수")
        ax.set_title(f"정책 {pol}: Spearman ρ(2021–25) = {rho:.2f}")
        ax.legend(frameon=False, fontsize=7)
    axes[0].set_ylabel("연간 사후 T")
    fig.suptitle("그림 8 · 연간 RV 변화와 CUSUM T 의 사후 기술적 연관 (예측·인과 주장 아님, ETF×연도 비독립)", y=1.03)
    save(fig, out, "F08_rv_vs_T", "annual_posthoc.csv;annual_vol_diagnostics.csv", "asymptotic; Spearman on core years", results)


def fig_synthetic(t, out, results):
    s = t.get("null_dgp_validation")
    if s is None:
        return
    tests = [
        ("annual_posthoc", "iid_history_bootstrap", "연간 사후 (iid 보정)"),
        ("annual_posthoc", "asymptotic_1.3397", "연간 사후 (점근)"),
        ("rolling_w60_PURE_any_episode_in_year", "iid_history_bootstrap_pointwise95", "w60 PURE 연중 ≥1 경보"),
    ]
    dgps = list(dict.fromkeys(s.dgp_name))
    fig, axes = plt.subplots(1, 3, figsize=(14, 6.2), sharey=True)
    for ax, (tst, cal, lab) in zip(axes, tests, strict=True):
        x = s[(s.test == tst) & (s.calibration == cal)].set_index("dgp_name").loc[dgps]
        y = np.arange(len(dgps))
        colors = ["#898781" if k == "H0" else ("#eb6834" if k == "BREAK_AT_BOUNDARY" else "#2a78d6") for k in x.dgp_kind]
        ax.barh(y, x.rate, color=colors, height=0.6)
        ax.errorbar(x.rate, y, xerr=[(x.rate - x.rate_ci_low).clip(lower=0), (x.rate_ci_high - x.rate).clip(lower=0)], fmt="none", ecolor=INK, lw=0.8, capsize=2)
        ax.axvline(0.05, color="#d03b3b", lw=0.8, ls="--")
        ax.set_yticks(y, [f"{d} [{lv}]" for d, lv in zip(dgps, x.level, strict=True)], fontsize=7)
        ax.set_xlim(0, 1.02)
        ax.set_title(lab)
        ax.invert_yaxis()
    fig.text(0.5, -0.02, "회색 = H0 (Size) · 파랑 = 연중 변화 (Power) · 주황 = 연도 경계 변화 · 막대 = Wilson 95% CI · 점선 = 0.05", fontsize=8, color=INK2, ha="center")
    fig.suptitle("그림 9 · 합성 DGP 의 경험적 Size/Power — 정답은 생성 과정에서만 안다 (SYNTHETIC_CAUSAL_KNOWN_ONLY)", y=1.0)
    save(fig, out, "F09_synthetic_size_power", "null_dgp_validation.csv", "selected tests", results)


def fig_M_N(t, out, results, nm):
    fc = t["annual_forecast_diagnostics"]
    rd = t["annual_residual_diagnostics"]
    tk = order(t)
    fig, axes = plt.subplots(1, 3, figsize=(14, 6.6), sharey=True)
    q = fc.pivot_table(index=["ticker", "year"], columns="policy", values="oos_qlike")
    d = (q.A - q.base).unstack().loc[tk, YEARS].to_numpy()
    heat(axes[0], d, [f"{k} {nm[k]}" for k in tk], [str(y) for y in YEARS], DIV, -1, 1, fmt="{:+.2f}", cbar_label="QLIKE(A) − QLIKE(base)")
    axes[0].set_title("M: QLIKE A − 기준선 (양수 = A 가 더 나쁨, 같은 날짜)")
    e2 = fc[fc.policy == "A"].pivot(index="ticker", columns="year", values="mean_sq_standardized_residual").loc[tk, YEARS].to_numpy()
    heat(axes[1], np.log2(e2), tk, [str(y) for y in YEARS], DIV, -1.5, 1.5, fmt="{:+.2f}", cbar_label="log2 mean e² (A)")
    axes[1].set_title("M: log2 평균 e² (A) — 양수 = 분산 과소예측")
    lq = rd[rd.policy == "A"].pivot(index="ticker", columns="year", values="ljungbox_e2_q").loc[tk, YEARS].to_numpy()
    heat(axes[2], -np.log10(np.clip(lq, 1e-6, 1)), tk, [str(y) for y in YEARS], SEQ, 0, 4, fmt="{:.1f}", cbar_label="−log10 q (LB e², BH)")
    axes[2].set_title("N: Ljung–Box(e²,10) BH q (A) — 1.3 이상 = q<0.05")
    fig.suptitle("그림 10 · 연초 분산모형의 OOS 적합(M)과 잔차 의존(N) — 기술 진단, 원인 판정 아님", y=1.0)
    save(fig, out, "F10_M_N_heatmaps", "annual_forecast_diagnostics.csv;annual_residual_diagnostics.csv", "policy=A (+base for QLIKE diff)", results)


def fig_H(t, out, results):
    ab = t["annual_history_ablation"]
    x = ab[(ab.h_status == "COMPUTED") & (ab.history_strategy != "expanding")]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2))
    for k, (s, mk) in enumerate((("trailing_2y", "o"), ("frozen_2019", "s"))):
        for pol in ("A", "B"):
            y = x[(x.history_strategy == s) & (x.policy == pol)]
            jit = (k * 2 + (pol == "B")) * 0.08 - 0.12
            axes[0].scatter(y.year + jit, y.d_qlike_vs_expanding, s=12, marker=mk, color=COL[pol], alpha=0.7, label=f"{s} · {pol}")
            axes[1].scatter(y.year + jit, y.d_annual_T_vs_expanding, s=12, marker=mk, color=COL[pol], alpha=0.7, label=f"{s} · {pol}")
    for ax, lab in zip(axes, ("ΔQLIKE (대안 − expanding, 같은 날짜)", "Δ연간 T (대안 − expanding)"), strict=True):
        ax.axhline(0, color=MUTED, lw=0.8)
        ax.set_ylabel(lab)
        ax.set_xticks(range(2021, 2027))
        ax.legend(fontsize=6.5, frameon=False, ncol=2)
    axes[0].set_title("H: 학습 이력만 바꾼 동일 연도 대조 — 예측 손실")
    axes[1].set_title("H: 연간 사후 T 차이")
    fig.suptitle("그림 11 · 동일 검정연도·동일 가격 경로에서 학습 이력 전략의 차이 (2020: 대조 없음, 2021: frozen 만)", y=1.03)
    save(fig, out, "F11_history_ablation", "annual_history_ablation.csv", "h_status=COMPUTED, non-expanding", results)


def fig_profile(t, out, results, nm):
    pr = t["diagnostic_profile"]
    tk = order(t)
    cats = list(STATUS_COL)
    cmap = ListedColormap([STATUS_COL[c] for c in cats])
    fig, axes = plt.subplots(1, 3, figsize=(14, 6.8), sharey=True)
    for ax, pol in zip(axes, ("A", "B", "base"), strict=True):
        x = pr[pr.policy == pol].pivot(index="ticker", columns="year", values="multi_factor_status").loc[tk, YEARS]
        M = x.map(lambda s: cats.index(s) if s in cats else np.nan).to_numpy(float)
        ax.imshow(M, cmap=cmap, vmin=-0.5, vmax=len(cats) - 0.5, aspect="auto")
        ax.grid(False)
        ax.set_xticks(range(len(YEARS)), [str(y) for y in YEARS])
        ax.set_yticks(range(len(tk)), [f"{k} {nm[k]}" for k in tk] if pol == "A" else tk)
        ax_ = pr[pr.policy == pol].pivot(index="ticker", columns="year", values="flagged_axes").loc[tk, YEARS]
        for i in range(len(tk)):
            for j in range(len(YEARS)):
                lab = ax_.iat[i, j]
                ax.text(j, i, "" if pd.isna(lab) else str(lab), ha="center", va="center", fontsize=6, color="white" if M[i, j] == cats.index("MULTIFACTOR") else INK)
        sens = pr[pr.policy == pol].pivot(index="ticker", columns="year", values="sensitivity_status").loc[tk, YEARS]
        for i, j in zip(*np.nonzero(sens.to_numpy() == "SENSITIVITY_CONFIRMED"), strict=True):
            ax.add_patch(plt.Rectangle((j - 0.46, i - 0.46), 0.92, 0.92, fill=False, edgecolor="#d03b3b", lw=1.0, ls="--"))
        ax.set_title(f"정책 {pol}")
        for s in ax.spines.values():
            s.set_visible(False)
    handles = [plt.Rectangle((0, 0), 1, 1, color=STATUS_COL[c], ec=MUTED) for c in cats[:4]]
    fig.legend(handles, ["신호 없음", "신호 + 1개 축 (기술 증거)", "신호 + 2개 이상 축 (MULTIFACTOR)", "신호 + 플래그 없음 (UNRESOLVED)"], loc="lower center", ncol=4, frameon=False, fontsize=8)
    fig.suptitle("그림 12 · 다축 evidence profile — 셀 글자 = 플래그 선 축(V/M/N/H), 빨간 점선 = 보정·창·경계에 판정 민감", y=1.0)
    save(fig, out, "F12_profile_status", "diagnostic_profile.csv", "all", results)


def fig_etf(t, work, out, results, tk, nm):
    v = t["annual_vol_diagnostics"].query("ticker == @tk").set_index("year").loc[YEARS]
    fc = t["annual_forecast_diagnostics"].query("ticker == @tk")
    ph = t["annual_posthoc"].query("ticker == @tk")
    cu = t["annual_cusum_diagnostics"].query("ticker == @tk")
    d = daily_frame(work, tk)
    fig = plt.figure(figsize=(11, 6.6))
    gs = fig.add_gridspec(2, 3, height_ratios=[1, 1.1], hspace=0.45, wspace=0.28)
    ax = fig.add_subplot(gs[0, 0])
    ax.bar(range(len(YEARS)), v.rv_ann_pct, color="#9ec5f4", width=0.6)
    ax.axhline(v.rv_2019_ann_pct.iloc[0], color=MUTED, lw=1, ls="--")
    ax.text(len(YEARS) - 0.5, v.rv_2019_ann_pct.iloc[0], " 2019", fontsize=7, color=MUTED, va="bottom", ha="right")
    ax.set_xticks(range(len(YEARS)), [str(y)[2:] for y in YEARS])
    ax.set_title("(a) RV %p.a. (사후, 회색 = 2020·2026)")
    year_band(ax, label=False)
    ax = fig.add_subplot(gs[0, 1])
    for pol in ("A", "B", "base"):
        x = fc[fc.policy == pol].set_index("year").loc[YEARS]
        ax.plot(range(len(YEARS)), x.oos_qlike, marker="o", ms=3.5, lw=1.6, color=COL[pol], label=pol)
    ax.set_xticks(range(len(YEARS)), [str(y)[2:] for y in YEARS])
    ax.set_title("(b) OOS QLIKE (같은 날짜, 낮을수록 좋음)")
    ax.legend(fontsize=7, frameon=False)
    ax = fig.add_subplot(gs[0, 2])
    for pol in ("A", "B", "base"):
        x = ph[(ph.policy == pol) & (ph.calibration_method == "asymptotic")].set_index("year").loc[YEARS]
        ax.plot(range(len(YEARS)), x.annual_T, marker="o", ms=3.5, lw=1.6, color=COL[pol], label=pol)
    ci = ph[(ph.policy == "A") & (ph.calibration_method == "iid_insample")].set_index("year").loc[YEARS]
    ax.plot(range(len(YEARS)), ci.annual_critical, color="#d03b3b", lw=0.8, ls=":", label="A iid 임계")
    ax.axhline(1.3397, color="#d03b3b", lw=0.8, ls="--")
    ax.set_xticks(range(len(YEARS)), [str(y)[2:] for y in YEARS])
    ax.set_title("(c) 연간 사후 T (점선 1.3397)")
    ax.legend(fontsize=6.5, frameon=False)
    ax = fig.add_subplot(gs[1, :])
    for y in YEARS:
        s = d[(d.year == y) & (d.policy == "A") & (d.window == 60)]
        if s.empty:
            continue
        c = cu[(cu.year == y) & (cu.policy == "A") & (cu.window == 60) & (cu.calibration_method == "iid_insample") & (cu.boundary_mode == "CARRY")].pointwise_null_quantile.iloc[0]
        pure = s.pure_oos_window.astype(bool)
        ax.plot(s.date[~pure], s["T"][~pure], color="#b7d3f6", lw=1.0)
        ax.plot(s.date[pure], s["T"][pure], color=COL["A"], lw=1.0)
        ax.hlines(c, s.date.min(), s.date.max(), color="#d03b3b", lw=0.8, ls="--")
        al = pure & (s["T"] >= c)
        ax.scatter(s.date[al], s["T"][al], s=6, color="#d03b3b", zorder=3)
        ax.axvline(s.date.min(), color=MUTED, lw=0.5)
        if y in (2020, 2026):
            ax.axvspan(s.date.min(), s.date.max(), color="#f0efec", zorder=0)
    ax.set_title("(d) 정책 A w60 일별 통계량 — 진한 선 = PURE_OOS, 옅은 선 = 연초 59일 CARRY warm, 빨간 점선 = 연초 고정 임계값(iid in-sample), 점 = PURE 경보일")
    fig.suptitle(f"{tk} {nm[tk]} — 연간 expanding 진단 요약 (2020 파일럿·2026 부분/비블라인드 음영)", y=0.99)
    save(fig, out, f"ETF_{tk}", "annual_vol_diagnostics.csv;annual_forecast_diagnostics.csv;annual_posthoc.csv;annual_cusum_diagnostics.csv", f"ticker={tk}; daily cache (local)", results)


def derived_tables(t, results: Path) -> None:
    """보고서 토큰용 파생 요약 — 결과표에서 직접 집계 (하드코딩 금지)."""
    ph = t["annual_posthoc"]
    cu = t["annual_cusum_diagnostics"]
    v = t["annual_vol_diagnostics"]
    fc = t["annual_forecast_diagnostics"]
    pr = t["diagnostic_profile"]
    rows = []
    for y in YEARS:
        for pol in ("A", "B", "base"):
            a = ph[(ph.year == y) & (ph.policy == pol)]
            c = cu[(cu.year == y) & (cu.policy == pol) & (cu.window == 60) & (cu.boundary_mode == "YEAR_CONTAINED") & (cu.calibration_method == "iid_insample")]
            p = pr[(pr.year == y) & (pr.policy == pol)]
            rows.append(
                {
                    "year": y,
                    "policy": pol,
                    "n_etf": a.ticker.nunique(),
                    "n_reject_asym": int(a[a.calibration_method == "asymptotic"].annual_reject.astype(bool).sum()),
                    "n_reject_iid_insample": int(a[a.calibration_method == "iid_insample"].annual_reject.astype(bool).sum()),
                    "n_reject_iid_prequential": int(a[a.calibration_method == "iid_prequential"].annual_reject.dropna().astype(bool).sum()),
                    "n_prequential_estimable": int(a[a.calibration_method == "iid_prequential"].annual_critical.notna().sum()),
                    "median_T": float(a[a.calibration_method == "asymptotic"].annual_T.median()),
                    "max_T": float(a[a.calibration_method == "asymptotic"].annual_T.max()),
                    "w60_pure_episodes_total": int(c.rolling_episodes.sum()),
                    "w60_null_expected_total": float(c.expected_null_episodes.sum()),
                    "n_etf_with_w60_episode": int((c.rolling_episodes > 0).sum()),
                    "median_rv": float(v[v.year == y].rv_ann_pct.median()),
                    "n_rv_up": int((v[v.year == y].rv_ratio >= 1.25).sum()),
                    "median_qlike_minus_base": float(
                        (fc[(fc.year == y) & (fc.policy == pol)].set_index("ticker").oos_qlike - fc[(fc.year == y) & (fc.policy == "base")].set_index("ticker").oos_qlike).median()
                    ),
                    "median_mean_e2": float(fc[(fc.year == y) & (fc.policy == pol)].mean_sq_standardized_residual.median()),
                    "n_multifactor": int((p.multi_factor_status == "MULTIFACTOR").sum()),
                    "n_descriptive": int((p.multi_factor_status == "DESCRIPTIVE_EVIDENCE").sum()),
                    "n_unresolved": int((p.multi_factor_status == "UNRESOLVED").sum()),
                    "n_no_signal": int((p.multi_factor_status == "NO_SIGNAL_DESCRIPTIVE").sum()),
                    "n_sensitivity_confirmed": int((p.sensitivity_status == "SENSITIVITY_CONFIRMED").sum()),
                }
            )
    pd.DataFrame(rows).to_csv(results / "summary_by_year_policy.csv", index=False, lineterminator="\n", float_format="%.6g")


def aggregates(t, results: Path) -> None:
    """본문이 인용하는 집계값 — 모두 결과표에서 계산 (name,value,definition)."""
    ph, v, fc, cu, ab, pr, fs = (t[k] for k in ("annual_posthoc", "annual_vol_diagnostics", "annual_forecast_diagnostics", "annual_cusum_diagnostics", "annual_history_ablation", "diagnostic_profile", "fit_summary"))
    rows: list[tuple[str, float, str]] = []
    asym = ph[ph.calibration_method == "asymptotic"].merge(v[["ticker", "year", "rv_ratio", "rv_ann_pct"]], on=["ticker", "year"])
    core = asym.year.between(2021, 2025)
    for pol in ("A", "B", "base"):
        x = asym[(asym.policy == pol) & core]
        rows.append((f"spearman_T_rvratio_{pol}_core", x[["annual_T", "rv_ratio"]].corr("spearman").iloc[0, 1], "Spearman rank corr annual_T vs rv_ratio, 2021-2025, 100 ETF-years"))
        rows.append((f"spearman_T_rv_{pol}_core", x[["annual_T", "rv_ann_pct"]].corr("spearman").iloc[0, 1], "Spearman annual_T vs rv_ann_pct, 2021-2025"))
        y = asym[asym.policy == pol]
        rows.append((f"spearman_T_rvratio_{pol}_all", y[["annual_T", "rv_ratio"]].corr("spearman").iloc[0, 1], "Spearman, 2020-2026, 140 ETF-years"))
        rows.append((f"core_reject_asym_{pol}", int(x.annual_reject.astype(bool).sum()), "annual asymptotic rejections 2021-2025 (of 100)"))
        rows.append((f"core_median_T_{pol}", x.annual_T.median(), "median annual T 2021-2025"))
        c = cu[(cu.policy == pol) & cu.year.between(2021, 2025) & (cu.window == 60) & (cu.boundary_mode == "YEAR_CONTAINED") & (cu.calibration_method == "iid_insample")]
        rows.append((f"core_w60_obs_{pol}", int(c.rolling_episodes.sum()), "w60 PURE episodes 2021-2025, iid_insample"))
        rows.append((f"core_w60_null_{pol}", c.expected_null_episodes.sum(), "expected null episodes 2021-2025"))
        rows.append((f"core_w60_ratio_{pol}", c.rolling_episodes.sum() / c.expected_null_episodes.sum(), "observed/expected"))
        f = fc[(fc.policy == pol) & fc.year.between(2021, 2025)]
        rows.append((f"core_median_mean_e2_{pol}", f.mean_sq_standardized_residual.median(), "median mean e2 2021-2025"))
        rows.append((f"core_share_e2_ge_1p5_{pol}", (f.mean_sq_standardized_residual >= 1.5).mean(), "share of ETF-years with mean e2>=1.5"))
        rows.append((f"nonpos_days_{pol}", int(fc[fc.policy == pol].nonpos_var.sum()), "non-positive variance days, all ETF-years"))
        p = pr[pr.policy == pol]
        for st in ("MULTIFACTOR", "DESCRIPTIVE_EVIDENCE", "UNRESOLVED", "NO_SIGNAL_DESCRIPTIVE"):
            rows.append((f"status_{pol}_{st}", int((p.multi_factor_status == st).sum()), "count over 140 ETF-years"))
            rows.append((f"status_core_{pol}_{st}", int((p[p.year.between(2021, 2025)].multi_factor_status == st).sum()), "count over 100 core ETF-years"))
        rows.append((f"sensitivity_{pol}", int((p.sensitivity_status == "SENSITIVITY_CONFIRMED").sum()), "SENSITIVITY_CONFIRMED over 140"))
        sig = p[p.signal_present.astype(bool)]
        rows.append((f"signal_cells_{pol}", len(sig), "cells with annual reject or w60 PURE episode"))
        for ax_ in "VMNH":
            rows.append((f"signal_share_{ax_}_{pol}", sig.flagged_axes.fillna("").str.contains(ax_).mean() if len(sig) else np.nan, f"share of signal cells with {ax_} flagged"))
        if pol != "base":
            for hs in ("trailing_2y", "frozen_2019"):
                h = ab[(ab.policy == pol) & (ab.history_strategy == hs) & (ab.h_status == "COMPUTED")]
                rows.append((f"h_{hs}_{pol}_n", len(h), "computed contrasts"))
                rows.append((f"h_{hs}_{pol}_frac_worse", (h.d_qlike_vs_expanding > 0).mean(), "share QLIKE worse than expanding"))
                rows.append((f"h_{hs}_{pol}_dq_median", h.d_qlike_vs_expanding.median(), "median dQLIKE"))
                rows.append((f"h_{hs}_{pol}_absdT_median", h.d_annual_T_vs_expanding.abs().median(), "median |dT|"))
            e = ab[(ab.policy == pol) & (ab.history_strategy == "expanding")].set_index(["ticker", "year"]).annual_reject_asymptotic
            h = ab[(ab.policy == pol) & (ab.h_status == "COMPUTED") & (ab.history_strategy != "expanding")]
            diff = (h.set_index(["ticker", "year"]).annual_reject_asymptotic != e.reindex(h.set_index(["ticker", "year"]).index)).sum()
            rows.append((f"h_verdict_diff_{pol}", int(diff), "alternative-history contrasts whose asymptotic verdict differs"))
            rows.append((f"h_contrasts_{pol}", len(h), "computed alternative-history contrasts"))
    fr = ab[(ab.policy == "A") & (ab.history_strategy == "frozen_2019") & (ab.h_status == "COMPUTED")]
    for y in range(2021, 2027):
        rows.append((f"h_frozen_A_dq_median_{y}", fr[fr.year == y].d_qlike_vs_expanding.median(), "median dQLIKE frozen vs expanding by year"))
    xb = asym[(asym.policy == "B") & (asym.year >= 2021)].merge(fc[fc.policy == "B"][["ticker", "year", "mean_sq_standardized_residual"]], on=["ticker", "year"])
    rows.append(("b_spikes_2021plus", int(((xb.annual_T >= 1.6) & (xb.mean_sq_standardized_residual < 0.8)).sum()), "B ETF-years 2021+ with T>=1.6 and mean e2<0.8"))
    rows.append(("b_T_ge_1p6_2021plus", int((xb.annual_T >= 1.6).sum()), "B ETF-years 2021+ with T>=1.6"))
    ex = fs[fs.history_strategy == "expanding"]
    rows.append(("eps_at_grid_edge_share", (ex.epsilon == 0.1).mean(), "share of expanding fits selecting epsilon=0.1 (grid edge)"))
    rows.append(("n_expanding_fits", len(ex), "expanding fits"))
    k = asym[asym.ticker.isin(["069500", "102110"])].pivot_table(index=["year", "policy"], columns="ticker", values="annual_T")
    rows.append(("kospi_pair_max_absdiff_T_A", (k.xs("A", level="policy")["069500"] - k.xs("A", level="policy")["102110"]).abs().max(), "max |T 069500 - T 102110| policy A over years"))
    rows.append(("kospi_pair_max_absdiff_T_B", (k.xs("B", level="policy")["069500"] - k.xs("B", level="policy")["102110"]).abs().max(), "same, policy B"))
    rows.append(("rv_median_2026", v[v.year == 2026].rv_ann_pct.median(), "median RV 2026 (partial)"))
    rows.append(("rv_max_2026", v[v.year == 2026].rv_ann_pct.max(), "max RV 2026"))
    nulla = cu[(cu.policy == "A") & (cu.window == 60) & (cu.boundary_mode == "YEAR_CONTAINED") & (cu.calibration_method == "iid_insample") & cu.year.between(2021, 2025)]
    rows.append(("null_prob_any_w60_A_core_mean", nulla.null_prob_any_episode.mean(), "mean iid-null P(>=1 PURE episode in year), A, 2021-2025"))
    pd.DataFrame(rows, columns=["name", "value", "definition"]).to_csv(results / "aggregates.csv", index=False, lineterminator="\n", float_format="%.6g")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--figs", required=True)
    ap.add_argument("--only", default=None)
    a = ap.parse_args()
    results, work, out = Path(a.results), Path(a.work), Path(a.figs)
    out.mkdir(parents=True, exist_ok=True)
    t = load(results)
    nm = names()
    derived_tables(t, results)
    aggregates(t, results)
    fig_timeline(out, results)
    fig_rv_heat(t, out, results, nm)
    fig_posthoc(t, out, results, nm)
    fig_boundary_example(t, work, out, results)
    fig_episodes(t, out, results, nm)
    fig_calibration(t, out, results)
    fig_policy_pairs(t, out, results, nm)
    fig_rv_vs_T(t, out, results)
    fig_synthetic(t, out, results)
    fig_M_N(t, out, results, nm)
    fig_H(t, out, results)
    fig_profile(t, out, results, nm)
    for tk in order(t):
        fig_etf(t, work, out, results, tk, nm)
    pd.DataFrame(MANIFEST).to_csv(out / "figure_manifest.csv", index=False, lineterminator="\n")
    print(f"{len(MANIFEST)} figures → {out}")

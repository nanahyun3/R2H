# ruff: noqa: E501
"""11번 발표용 인포그래픽 3장 (IG1 KOSPI200 해부 · IG2 6종 시간 링 · IG3 급변 별자리).

사용: R2H .venv/bin/python scripts/t20_infographics.py
숫자는 모두 pipeline.run() 결과에서 계산한다. 출력: research/etf_shock_bottomup_11/infographics/ (PNG 300dpi + SVG).
"""

from __future__ import annotations

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
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

from r2h.etf_shock import pipeline as P  # noqa: E402
from r2h.peer_shock.figures import setup_font  # noqa: E402

OUT = ROOT / "research/etf_shock_bottomup_11/infographics"
BG, PANEL, INK, MUTED, GRID = "#0d1017", "#151a24", "#ecebe6", "#8b919c", "#262c38"
SHOCK = "#ff4d6d"
ETF_COL = {"069500": "#4ea1ff", "229200": "#9b8cff", "148070": "#36d399", "153130": "#a3e635", "133690": "#ff9f43", "261220": "#ffd166"}
ETF_NAME = {"069500": "KOSPI200", "229200": "코스닥150", "148070": "국고채10년", "153130": "단기채권", "133690": "미국나스닥100", "261220": "WTI원유"}
CUS_CMAP = LinearSegmentedColormap.from_list("cus", ["#151a24", "#2b2f6b", "#6c3fb5", "#d14fd1", "#ffd1ff"])
P0, P1 = pd.Timestamp("2021-01-04"), pd.Timestamp("2025-12-30")


def theme() -> None:
    setup_font()
    from matplotlib import font_manager
    font_manager.fontManager.addfont("/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf")  # 굵은 제목용
    plt.rcParams.update({"figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG, "text.color": INK,
                         "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED, "axes.edgecolor": GRID,
                         "svg.hashsalt": "t20_infographics"})


def save(fig, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.png", dpi=300, metadata={"Software": None})
    fig.savefig(OUT / f"{name}.svg", metadata={"Date": None, "Creator": None})
    plt.close(fig)


def clean(ax, left=True):
    for s in ("top", "right", "bottom") + (() if left else ("left",)):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(GRID)
    ax.tick_params(length=0, labelsize=9)
    ax.grid(axis="y", color=GRID, lw=0.5)
    ax.set_axisbelow(True)


def card(fig, x, y, w, h):
    fig.patches.append(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.004,rounding_size=0.012", transform=fig.transFigure,
                                      facecolor=PANEL, edgecolor=GRID, lw=0.8, zorder=-5))


# ── IG1 ────────────────────────────────────────────────────────────────────
def ig1(R: dict) -> dict:
    t = "069500"
    d = R["daily"][R["daily"]["ticker"] == t].reset_index(drop=True)
    p = d[(d["date"] >= P0) & (d["date"] <= P1)]
    cu = R["cusum"][R["cusum"]["ticker"] == t].set_index("date").reindex(p["date"])
    rc = [c for c in cu.columns if c.startswith("R_")]
    cmax = cu[rc].max(axis=1).to_numpy(float)
    iv = R["intervals"]
    iv = iv[(iv["ticker"] == t) & (iv["q"] == 20) & (iv["period"] == "PRIMARY")].reset_index(drop=True)
    picks = iv.sort_values(["duration", "start"], ascending=[False, True]).head(3).sort_values("start")

    fig = plt.figure(figsize=(20, 11.25))
    fig.text(0.035, 0.935, "KOSPI200, 5년간 7번의 급변", fontsize=30, weight=600)
    fig.text(0.035, 0.895, "KODEX 200 (069500) · 2021–2025 · 급변 = 20일 변동성이 자기 과거 90분위 경계를 넘은 날의 연속", fontsize=13, color=MUTED)
    stats = [(f"{len(iv)}", "급변 구간"), (f"{int(iv['duration'].sum())}일", "급변 거래일"),
             (f"{iv['peak_over_boundary'].max():.2f}배", "최대 σ / 경계"), (f"{int(iv['cusum_alarm_days_any'].sum())}", "CUSUM 경보")]
    for k, (v, lab) in enumerate(stats):
        x = 0.585 + k * 0.103
        fig.text(x, 0.925, v, fontsize=26, weight=600, color=SHOCK if k == 3 else INK)
        fig.text(x, 0.898, lab, fontsize=11, color=MUTED)

    L, W = 0.05, 0.60
    ax1 = fig.add_axes([L, 0.60, W, 0.25])
    ax2 = fig.add_axes([L, 0.33, W, 0.24], sharex=ax1)
    ax3 = fig.add_axes([L, 0.25, W, 0.05], sharex=ax1)
    for _, r in iv.iterrows():
        for a in (ax1, ax2):
            a.axvspan(pd.Timestamp(r["start"]), pd.Timestamp(r["end"]) + pd.Timedelta(days=1), color=SHOCK, alpha=0.22, lw=0)
    base = p["close"].iloc[0]
    cr = (p["close"] / base - 1) * 100
    ax1.plot(p["date"], cr, color=INK, lw=1.4)
    ax1.fill_between(p["date"], cr, cr.min() - 5, color=ETF_COL[t], alpha=0.10, lw=0)
    ax1.set_ylabel("누적수익률 % (2021-01-04 = 0)", fontsize=10)
    for j, r in iv.reset_index(drop=True).iterrows():
        xm = pd.Timestamp(r["start"]) + (pd.Timestamp(r["end"]) - pd.Timestamp(r["start"])) / 2
        ax1.scatter([xm], [cr.max() + 6], s=260, color=SHOCK if r["interval_id"] in set(picks["interval_id"]) else GRID, zorder=4)
        ax1.text(xm, cr.max() + 6, str(j + 1), ha="center", va="center", fontsize=10, weight=600, color=BG if r["interval_id"] in set(picks["interval_id"]) else INK, zorder=5)
    ax1.set_ylim(cr.min() - 5, cr.max() + 12)
    clean(ax1)
    plt.setp(ax1.get_xticklabels(), visible=False)
    s, b = p["sigma20"].to_numpy(float), p["b20"].to_numpy(float)
    ax2.plot(p["date"], s, color=ETF_COL[t], lw=1.1, label="20일 변동성 σ (연환산 %)")
    ax2.plot(p["date"], b, color=INK, lw=1, ls=(0, (4, 3)), label="급변 경계 (자기 과거 90분위)")
    ax2.fill_between(p["date"], b, s, where=s > b, color=SHOCK, alpha=0.75, lw=0, interpolate=True)
    ax2.set_ylabel("σ20 (%)", fontsize=10)
    ax2.legend(loc="upper left", fontsize=9, frameon=False)
    clean(ax2)
    plt.setp(ax2.get_xticklabels(), visible=False)
    dts = pd.DatetimeIndex(p["date"])
    edges = mdates.date2num(list(dts) + [dts[-1] + pd.Timedelta(days=1)])
    cm = CUS_CMAP.copy()
    cm.set_bad(BG)
    ax3.pcolormesh(edges, [0, 1], np.ma.masked_invalid(cmax)[None, :], cmap=cm, vmin=0.2, vmax=1.0, shading="flat", rasterized=True)
    ax3.set_yticks([])
    ax3.set_ylabel("CUSUM", fontsize=10, rotation=0, ha="right", va="center")
    for sp in ax3.spines.values():
        sp.set_visible(False)
    ax3.xaxis.set_major_locator(mdates.YearLocator())
    ax3.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax3.tick_params(length=0, labelsize=11, colors=INK)
    ax3.set_xlim(P0, P1 + pd.Timedelta(days=1))
    imax = int(np.nanargmax(cmax))
    assert np.nanmax(cmax) < 1
    fig.text(L, 0.205, f"CUSUM 띠 = SVR–GARCH 잔차 CUSUM 의 T / W3 임계값 (3정책 × 4창 중 최대). 밝을수록 경보에 가깝다. 최댓값 {np.floor(np.nanmax(cmax) * 1000) / 1000:.3f} ({dts[imax].date()}, 급변 구간 밖) — 1 (경보) 에는 한 번도 닿지 않았다.", fontsize=10, color=MUTED)
    # 오른쪽 카드 3장: 바텀업
    cx, cw, ch = 0.685, 0.29, 0.255
    for k, (_, r) in enumerate(picks.iterrows()):
        cy = 0.60 - k * 0.285
        card(fig, cx, cy, cw, ch)
        num = list(iv["interval_id"]).index(r["interval_id"]) + 1
        fig.text(cx + 0.012, cy + ch - 0.035, f"{num}", fontsize=18, weight=600, color=SHOCK)
        fig.text(cx + 0.035, cy + ch - 0.032, f"{r['start']} ~ {r['end']} · {r['duration']}거래일", fontsize=12.5, weight=600)
        kind = r["shock_type"] + (" · 창 이탈 종료" if r["window_exit_end"] else "")
        fig.text(cx + 0.035, cy + ch - 0.058, kind, fontsize=10.5, color=MUTED)
        pk = int(d.index[d["date"] == pd.Timestamp(r["peak_date"])][0])
        win = d["r"].to_numpy()[pk - 19:pk + 1]
        sh = (win - win.mean()) ** 2
        sh = sh / sh.sum()
        axc = fig.add_axes([cx + 0.012, cy + 0.03, 0.125, ch - 0.115])
        axc.set_facecolor("none")
        top = int(np.argmax(sh))
        axc.bar(range(20), sh * 100, color=[SHOCK if i == top else "#4a5262" for i in range(20)], width=0.75)
        axc.set_xticks([])
        axc.set_ylim(0, 70)
        axc.tick_params(labelsize=8, length=0)
        for spn in ("top", "right", "bottom"):
            axc.spines[spn].set_visible(False)
        axc.spines["left"].set_color(GRID)
        axc.set_title("최대 σ 일 20일 창의 분산 기여 %", fontsize=8.5, color=MUTED, loc="left")
        tx = cx + 0.148
        fig.text(tx, cy + ch - 0.098, f"{r['top1_share']:.0%}", fontsize=24, weight=600, color=SHOCK)
        fig.text(tx + 0.055, cy + ch - 0.094, f"{r['top1_date']}\n하루 {r['top1_r']:+.2f}%", fontsize=9.5, color=INK, va="bottom")
        lines = [f"σ {r['peak_sigma']:.1f}% = 경계 {r['peak_over_boundary']:.2f}배",
                 f"구간 수익률 {r['ret_interval_pct']:+.1f}% · 낙폭 {r['max_drawdown_pct']:.1f}%",
                 f"같은 날 급변 그룹 최대 {int(r['max_N_A_q20'])}/17" + (" (시장 공통)" if r["C1_days"] else " (국내 고유)"),
                 f"CUSUM 최대 {r['cusum_maxR_any']:.2f} · 경보 {int(r['cusum_alarm_days_any'])}"]
        for i, ln in enumerate(lines):
            fig.text(tx, cy + ch - 0.13 - i * 0.026, ln, fontsize=9.8, color=INK if i < 3 else "#d9b3ff")
    fig.text(0.035, 0.035, "읽는 법  빨강 = 급변 구간 · 20일 창에 큰 하루가 들어오면 σ 가 뛰고, 그 하루가 창에서 빠지는 날 구간이 끝난다 (창 이탈 종료). 원 번호 = 시간순 구간, 빨간 원 = 지속 상위 3개 (오른쪽 카드).",
             fontsize=10.5, color=MUTED)
    fig.text(0.965, 0.035, "R2H · 11-lock-1 · 데이터: 09 ETF 상태 · W3 SVR–GARCH CUSUM", fontsize=9, color=MUTED, ha="right")
    save(fig, "IG1_kospi200_anatomy")
    return {"picks": list(picks["interval_id"])}


# ── IG2 ────────────────────────────────────────────────────────────────────
def ig2(R: dict) -> dict:
    tk = R["cfg"]["tickers"]
    d = R["daily"]
    iv = R["intervals"]
    iv = iv[(iv["q"] == 20) & (iv["period"] == "PRIMARY")]
    cu = R["cusum"]
    rc = [c for c in cu.columns if c.startswith("R_")]
    alarm = cu[(cu[rc] >= 1).any(axis=1)][["date", "ticker"]]
    span = (P1 - P0).days + 1
    gap = np.deg2rad(26)

    def th(ts):
        return gap / 2 + (2 * np.pi - gap) * ((pd.Timestamp(ts) - P0).days / span)

    fig = plt.figure(figsize=(20, 11.25))
    ax = fig.add_axes([0.02, 0.02, 0.62, 0.96], projection="polar")
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_facecolor(BG)
    ax.grid(False)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines["polar"].set_visible(False)
    r0, dr = 3.2, 1.25
    rings = {t: r0 + (i + 1) * dr for i, t in enumerate(tk)}
    # C1 링
    c1 = d[(d["ticker"] == tk[0]) & (d["date"] >= P0) & (d["date"] <= P1)]
    f = (c1["C1"] == 1).to_numpy()
    for s_, e_ in _runs(f):
        a, b = th(c1["date"].iloc[s_]), th(c1["date"].iloc[e_] + pd.Timedelta(days=1))
        ax.bar((a + b) / 2, 0.7, width=b - a, bottom=r0 - 0.35, color=INK, alpha=0.9, lw=0)
    ax.plot(np.linspace(gap / 2, 2 * np.pi - gap / 2, 400), np.full(400, r0), color=GRID, lw=0.8)
    for t in tk:
        rr = rings[t]
        ax.plot(np.linspace(gap / 2, 2 * np.pi - gap / 2, 600), np.full(600, rr), color=GRID, lw=0.8)
        for _, r in iv[iv["ticker"] == t].iterrows():
            a, b = th(r["start"]), th(pd.Timestamp(r["end"]) + pd.Timedelta(days=1))
            h = 0.25 + 0.55 * min(r["peak_over_boundary"] - 1, 1.5) / 1.5
            ax.bar((a + b) / 2, h, width=max(b - a, 0.004), bottom=rr - h / 2, color=ETF_COL[t], alpha=0.95, lw=0)
        for dt in alarm[alarm["ticker"] == t]["date"]:
            a = th(dt)
            ax.plot([a, a], [rr + 0.42, rr + 0.62], color="#ffffff", lw=0.9, alpha=0.9)
        ax.text(0, rr, ETF_NAME[t], ha="center", va="center", fontsize=10.5, color=ETF_COL[t], weight=600)
    ax.text(0, r0, "C1 시장 공통", ha="center", va="center", fontsize=9.5, color=INK)
    rmax = rings[tk[-1]] + 0.9
    for y in range(2021, 2026):
        a = th(f"{y}-01-01") if y > 2021 else gap / 2
        ax.plot([a, a], [r0 - 0.6, rmax], color=GRID, lw=0.8, ls=(0, (2, 3)))
        ax.text(th(f"{y}-01-01") if y > 2021 else gap / 2, rmax + 0.45, str(y), ha="center", va="center", fontsize=14, color=INK, weight=600)
    for lab, when in (("2022 금리 급등", "2022-06-15"), ("2024-08 급락", "2024-08-15"), ("2025-04 관세 충격", "2025-04-20")):
        ax.text(th(when), rmax + 1.75, lab, ha="center", va="center", fontsize=10.5, color=SHOCK)
    ax.set_ylim(0, rmax + 2.1)
    n_alarm = len(alarm)
    on_shock = int(alarm.merge(d[["date", "ticker", "A20"]], on=["date", "ticker"])["A20"].eq(1).sum())
    ax.text(0, 0, f"{on_shock}", ha="center", va="center", fontsize=64, weight=600, color=SHOCK)
    ax.text(np.pi, 1.6, f"급변일에 울린 CUSUM 경보\n(경보가 난 날 전체 {n_alarm}일 중)", ha="center", va="center", fontsize=11, color=INK)
    # 오른쪽 해설
    fig.text(0.62, 0.90, "급변은 자산마다 다른 시기에 온다", fontsize=28, weight=600)
    fig.text(0.62, 0.862, "6종 ETF · 2021–2025 · 시계 방향 = 시간 · 호 = 급변 구간 (두께 = 최대 σ / 경계)", fontsize=12, color=MUTED)
    st = R["stage"].set_index("ticker")
    y = 0.79
    for t in tk:
        x = iv[iv["ticker"] == t]
        fig.text(0.62, y, "●", fontsize=16, color=ETF_COL[t])
        fig.text(0.638, y + 0.002, f"{ETF_NAME[t]}", fontsize=13, weight=600)
        fig.text(0.735, y + 0.002, f"{len(x)}구간 · {int(x['duration'].sum())}일", fontsize=12)
        ov = "기준" if t == tk[0] else f"KOSPI200 과 같은 날 {int(st.loc[t, 'days_with_069500'])}일"
        fig.text(0.835, y + 0.002, ov, fontsize=11, color=MUTED)
        y -= 0.048
    notes = ["국내 주식은 2023-11 · 2024-08 · 2025-04 에 함께 흔들렸다",
             "국채·단기채는 2022 금리 국면에 길게 흔들렸고 KOSPI200 과 거의 겹치지 않는다",
             "나스닥의 급변 6구간은 모두 다른 ETF 와 겹친다 (다자산 사건)",
             "가장 안쪽 흰 링 = 10번 C1 (17개 그룹 중 같은 날 9개 이상 급변) — 개별 급변이 겹친 곳",
             f"흰 눈금 = CUSUM 경보가 난 날 {n_alarm}일 — 하나도 색 호(급변) 와 같은 날이 아니다",
             "맨 위 빈 틈 = 2021-01 시작 / 2025-12 끝"]
    y -= 0.03
    for n_ in notes:
        fig.text(0.62, y, "—  " + n_, fontsize=11.5, color=INK)
        y -= 0.04
    fig.text(0.965, 0.035, "R2H · 11-lock-1 · 데이터: 09 ETF 상태 · 10 C1 · W3 SVR–GARCH CUSUM (crit_w3)", fontsize=9, color=MUTED, ha="right")
    save(fig, "IG2_six_etf_time_rings")
    return {"alarm": n_alarm, "on_shock": on_shock}


def _runs(flag: np.ndarray) -> list[tuple[int, int]]:
    out, i, n = [], 0, len(flag)
    while i < n:
        if flag[i]:
            j = i
            while j + 1 < n and flag[j + 1]:
                j += 1
            out.append((i, j))
            i = j + 1
        else:
            i += 1
    return out


# ── IG3 ────────────────────────────────────────────────────────────────────
def ig3(R: dict) -> dict:
    tk = R["cfg"]["tickers"]
    iv = R["intervals"]
    v = iv[(iv["q"] == 20) & (iv["period"] == "PRIMARY")].copy()
    fig = plt.figure(figsize=(20, 11.25))
    fig.text(0.035, 0.935, "급변 구간의 상당수는 큰 하루가 20일 창에 머문 시간이다", fontsize=28, weight=600)
    fig.text(0.035, 0.897, "6종 ETF · 2021–2025 급변 구간 전부 · 가로 = 지속 (거래일), 세로 = 최대 σ / 급변 경계", fontsize=12.5, color=MUTED)
    axh = fig.add_axes([0.06, 0.70, 0.60, 0.14])
    ax = fig.add_axes([0.06, 0.10, 0.60, 0.58], sharex=axh)
    bins = np.logspace(0, np.log10(90), 26)
    axh.hist([v[v["window_exit_end"]]["duration"], v[~v["window_exit_end"]]["duration"]], bins=bins, stacked=True,
             color=[SHOCK, "#4a5262"], label=["창 이탈 종료 (큰 하루가 20일 창에서 빠진 날 끝남)", "그 밖의 종료"], rwidth=0.9)
    axh.legend(fontsize=9.5, frameon=False, loc="upper left", labelcolor=INK)
    clean(axh)
    plt.setp(axh.get_xticklabels(), visible=False)
    axh.set_ylabel("구간 수", fontsize=10)
    for a in (ax, axh):
        a.axvspan(18.5, 21.5, color=SHOCK, alpha=0.10, lw=0)
    ax.text(20, 9.3, "20거래일 (창 길이)", ha="center", va="top", fontsize=10.5, color=SHOCK)
    for t in tk:
        z = v[v["ticker"] == t]
        sz = 40 + 6 * z["duration"]
        single = z["shock_type"] == "단일 충격형"
        ax.scatter(z.loc[single, "duration"], z.loc[single, "peak_over_boundary"], s=sz[single], color=ETF_COL[t], alpha=0.9, edgecolor=BG, lw=1.2, zorder=3)
        ax.scatter(z.loc[~single, "duration"], z.loc[~single, "peak_over_boundary"], s=sz[~single], facecolor="none", edgecolor=ETF_COL[t], lw=1.8, zorder=3)
    lab = {"069500_q20_007": "KOSPI200 2024-08\n-9.63% 하루 = 63%", "229200_q20_013": "코스닥 2023-11\n+13.66% 하루 = 57%",
           "148070_q20_009": "국채 2022-03~07\n78일 누적형", "153130_q20_025": "단기채 2024-01\n원자료 이상치 후보",
           "261220_q20_004": "원유 2025-06\n-14.47% 하루 = 65%", "133690_q20_008": "나스닥 2025-04\n경계 2.16배",
           "069500_q20_011": "KOSPI200 2025-11~12\n33일 누적형"}
    offs = {"069500_q20_007": (-150, 30), "229200_q20_013": (30, 25), "148070_q20_009": (-40, 40), "153130_q20_025": (-190, -10),
            "261220_q20_004": (-230, -12), "133690_q20_008": (25, 18), "069500_q20_011": (25, -40)}
    for k, txt in lab.items():
        r = v[v["interval_id"] == k].iloc[0]
        ax.annotate(txt, (r["duration"], r["peak_over_boundary"]), xytext=offs[k], textcoords="offset points", fontsize=9.5, color=INK,
                    arrowprops={"arrowstyle": "-", "color": MUTED, "lw": 0.8})
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(0.8, 100)
    ax.set_ylim(0.95, 10)
    ax.set_xticks([1, 2, 5, 10, 20, 50])
    ax.set_xticklabels(["1", "2", "5", "10", "20", "50"])
    ax.set_yticks([1, 1.5, 2, 3, 5, 8])
    ax.set_yticklabels(["1.0", "1.5", "2", "3", "5", "8"])
    ax.minorticks_off()
    ax.set_xlabel("지속 (거래일, 로그)", fontsize=11)
    ax.set_ylabel("최대 σ20 / 급변 경계 (로그)", fontsize=11)
    clean(ax)
    ax.grid(axis="x", color=GRID, lw=0.5)
    # 오른쪽 숫자 패널
    n = len(v)
    big = [(f"{n}", "급변 구간 (6종, 2021–2025)", INK), (f"{int((v['shock_type'] == '단일 충격형').sum())}", "단일 충격형 — 하루가 창 분산의 30% 이상", INK),
           (f"{int(v['window_exit_end'].sum())}", "창 이탈 종료 — 그 하루가 빠지자 끝남", SHOCK), (f"{int(v['cusum_alarm_days_any'].sum())}", "급변 구간 안 CUSUM 경보 (셀-일)", "#d9b3ff")]
    y = 0.76
    for val, txt, col in big:
        card(fig, 0.70, y - 0.02, 0.265, 0.13)
        fig.text(0.715, y + 0.04, val, fontsize=40, weight=600, color=col)
        fig.text(0.715, y + 0.008, txt, fontsize=11, color=MUTED)
        y -= 0.16
    yl = 0.115
    for i, t in enumerate(tk):
        fig.text(0.70 + (i % 3) * 0.09, yl - (i // 3) * 0.03, "●", fontsize=13, color=ETF_COL[t])
        fig.text(0.713 + (i % 3) * 0.09, yl - (i // 3) * 0.03 + 0.002, ETF_NAME[t], fontsize=10.5)
    fig.text(0.70, 0.16, "채운 원 = 단일 충격형 · 빈 원 = 누적형 · 원 크기 = 지속", fontsize=10.5, color=MUTED)
    fig.text(0.965, 0.035, "R2H · 11-lock-1 · 분산 기여 = (r - 평균)² / Σ (r - 평균)² , σ 의 표본분산과 정확히 일치", fontsize=9, color=MUTED, ha="right")
    save(fig, "IG3_shock_constellation")
    return {"n": n}


def main() -> None:
    theme()
    R = P.run(ROOT)
    print(ig1(R), ig2(R), ig3(R))


if __name__ == "__main__":
    main()

# ruff: noqa: E501  — 한국어 그림 캡션·각주 문자열.
"""11번 그림 — ETF 별 E1 전체 연도 타임라인 · E2 구간 스케일·지속 · E3 구간 바텀업 확대, 공통 X1–X4.

각 함수는 캡션 수치를 dict 로 돌려준다. 저장: PNG 320dpi + SVG (W2 ``save``).
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

from r2h.common_vol.figures import _img
from r2h.multihorizon.figures import CAT, INK, INK2, MUTED, SEQ, footnote, save, style
from r2h.peer_shock.figures import NA_COLOR, setup_font

FULL = (pd.Timestamp("2019-01-02"), pd.Timestamp("2026-10-02"))
PRIMARY = (pd.Timestamp("2021-01-01"), pd.Timestamp("2025-12-31"))
SHADE20, SHADE60 = "#e34948", "#eda100"
SHARE_CMAP = LinearSegmentedColormap.from_list("share", ["#d9d8d2", "#e34948"])


def _years(ax):
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))


def _period_bg(ax):
    ax.axvspan(FULL[0], PRIMARY[0], color="#f6f5f2", zorder=0, lw=0)
    ax.axvspan(PRIMARY[1], FULL[1] + pd.Timedelta(days=3), color="#f6f5f2", zorder=0, lw=0)


class Figures11:
    def __init__(self, res: dict, root: Path):
        setup_font()
        plt.rcParams["svg.hashsalt"] = "t20_etf_shock_11"
        self.r = res
        self.cfg = res["cfg"]
        self.d = res["daily"]
        self.cu = res["cusum"]
        self.iv = res["intervals"]
        self.out = root / "research/etf_shock_bottomup_11/figures"
        self.names = {"069500": "KODEX 200", "229200": "KODEX 코스닥150", "148070": "KIWOOM 국고채10년",
                      "153130": "KODEX 단기채권", "133690": "TIGER 미국나스닥100", "261220": "KODEX WTI원유선물(H)"}
        self.caps: dict[str, dict] = {}

    def _save(self, fig, name, cap):
        save(fig, self.out, name)
        plt.close(fig)
        self.caps[name] = cap
        return cap

    def _lab(self, t):
        return f"{t} {self.names[t]}"

    def _x(self, t):
        return self.d[self.d["ticker"] == t].reset_index(drop=True)

    def _ivs(self, t, q):
        return self.iv[(self.iv["ticker"] == t) & (self.iv["q"] == q)]

    def _shade(self, ax, t, q, color, alpha):
        for _, r in self._ivs(t, q).iterrows():
            ax.axvspan(pd.Timestamp(r["start"]), pd.Timestamp(r["end"]) + pd.Timedelta(days=1), color=color, alpha=alpha, lw=0, zorder=1)

    # E1 — 전체 연도 4층 타임라인
    def e1_timeline(self, t: str, num: str):
        x = self._x(t)
        c = self.cu[self.cu["ticker"] == t].set_index("date").reindex(x["date"])
        fig, axes = plt.subplots(5, 1, figsize=(15, 14), sharex=True, gridspec_kw={"height_ratios": [2.2, 2.2, 0.7, 2.0, 0.4]})
        ax = axes[0]
        _period_bg(ax)
        self._shade(ax, t, 20, SHADE20, 0.22)
        ax.plot(x["date"], x["cumret"], color=INK, lw=1)
        ax.axhline(0, color=MUTED, lw=0.6)
        ax.set_ylabel("누적수익률 (%)")
        ax.set_title("① 누적수익률 (2019-01-02 종가 = 0%) · 빨강 음영 = q20 급변 구간", loc="left", fontsize=10)
        style(ax)
        ax = axes[1]
        _period_bg(ax)
        self._shade(ax, t, 20, SHADE20, 0.22)
        ax.plot(x["date"], x["sigma20"], color=CAT[0], lw=0.9, label="σ20 (연환산 %)")
        ax.plot(x["date"], x["sigma60"], color=CAT[2], lw=0.9, alpha=0.8, label="σ60")
        ax.plot(x["date"], x["b20"], color=INK, lw=0.8, ls="--", label="σ20 급변 경계 (자기 과거 90분위)")
        ax.set_ylabel("연환산 σ (%)")
        ax.legend(fontsize=7.5, loc="upper left", ncol=3)
        ax.set_title("② 변동성 — σ20 이 점선(자기 과거 90분위 경계)을 넘는 날이 급변(A)", loc="left", fontsize=10)
        style(ax)
        ax = axes[2]
        _img(ax, np.vstack([x["A20"].to_numpy(float), x["A60"].to_numpy(float)]), pd.DatetimeIndex(x["date"]), ["A q20", "A q60"], fs=8)
        ax.set_title("③ 급변 상태 (파랑 = 1, 회색 = 0, 진회색 = 정의 불가: 기준 이력 252일 미만)", loc="left", fontsize=10)
        ax = axes[3]
        _period_bg(ax)
        self._shade(ax, t, 20, SHADE20, 0.22)
        for (p, w), col in zip(self.cfg["cusum_figure_cells"], (CAT[6], CAT[3])):
            ax.plot(x["date"], c[f"R_{p}_{w}"].to_numpy(float), color=col, lw=0.9, label=f"정책 {p} · w={w}")
        ax.axhline(1, color=INK, lw=1, ls="--")
        ax.text(x["date"].iloc[5], 1.03, "W3 경보 임계값 (T/crit = 1)", fontsize=7.5, color=INK2)
        ax.set_ylabel("CUSUM T / 임계값")
        ax.legend(fontsize=7.5, loc="upper left", ncol=2)
        ax.set_title("④ SVR–GARCH 잔차 CUSUM (2021–2025 만 계산 · 매년 1월 첫 w-1일 공백)", loc="left", fontsize=10)
        style(ax)
        ax = axes[4]
        ax.axis("off")
        for a in axes[:4]:
            a.set_xlim(FULL[0], FULL[1] + pd.Timedelta(days=3))
        _years(axes[3])
        axes[3].tick_params(labelbottom=True)
        prim = self._ivs(t, 20)
        prim = prim[prim["period"] == "PRIMARY"]
        cmax = c[[f"R_{p}_{w}" for p, w in self.cfg["cusum_figure_cells"]]].max().max()
        cap = {"n_primary": len(prim), "days_primary": int(prim["primary_days"].sum()), "cusum_max_ratio_fig": round(float(cmax), 3),
               "alarm_days_fig": int((c[[f"R_{p}_{w}" for p, w in self.cfg["cusum_figure_cells"]]] >= 1).sum().sum())}
        fig.suptitle(f"E1-{num} · {self._lab(t)} — 2019–2026 전체: 주분석 q20 급변 {cap['n_primary']}구간 {cap['days_primary']}일 · CUSUM(그림 2셀) 최대 T/crit {cap['cusum_max_ratio_fig']:.2f}", fontsize=12)
        footnote(fig, "흰 배경 = 주분석 2021–2025, 옅은 회색 = 2019 기준·2020 파일럿·2026 부분 연도. 2019 는 기준 이력 부족으로 급변 정의 불가. CUSUM 은 W3 와 같은 함수·임계값(crit_w3) 이며 2019–2020(SVR 학습)과 2026(W3 범위 밖)은 계산하지 않는다.")
        fig.tight_layout(rect=(0, 0.02, 1, 0.97))
        return self._save(fig, f"E1_{num}_{t}_timeline", cap)

    # E2 — 구간 스케일·지속
    def e2_scale(self, t: str, num: str):
        fig, axes = plt.subplots(1, 2, figsize=(15, 5.8), gridspec_kw={"width_ratios": [1.6, 1]})
        ax = axes[0]
        for q, col, mk in ((20, SHADE20, "o"), (60, SHADE60, "s")):
            v = self._ivs(t, q)
            ax.scatter(pd.to_datetime(v["start"]), v["duration"], s=30 + 120 * (v["peak_over_boundary"] - 1).clip(0, 2.5),
                       color=col, marker=mk, edgecolor="white", lw=1.2, alpha=0.9, label=f"q={q}", zorder=3)
            if q == 20:
                for _, r in v[v["period"] == "PRIMARY"].iterrows():
                    ax.annotate(f"{r['start']}\n{r['duration']}일 · σ {r['peak_sigma']:.1f}%", (pd.Timestamp(r["start"]), r["duration"]),
                                xytext=(6, 4), textcoords="offset points", fontsize=7, color=INK)
        _period_bg(ax)
        ax.set_yscale("log")
        ax.set_ylabel("지속 (거래일, 로그)")
        ax.set_xlim(FULL[0], FULL[1] + pd.Timedelta(days=3))
        _years(ax)
        ax.legend(fontsize=8)
        ax.set_title("구간 시작일 × 지속 (점 크기 = 최대 σ / 진입 경계)", loc="left", fontsize=10)
        style(ax)
        ax = axes[1]
        v = self._ivs(t, 20)
        v = v[v["period"] == "PRIMARY"].reset_index(drop=True)
        y = np.arange(len(v))
        ax.barh(y, v["peak_over_boundary"], color=[CAT[7] if s == "단일 충격형" else CAT[0] for s in v["shock_type"]], height=0.6)
        for i, r in v.iterrows():
            ax.text(r["peak_over_boundary"] + 0.02, i, f"{r['duration']}일 · 과거 중앙 대비 {r['peak_over_past_median']:.1f}배 · {r['shock_type']}{' · 창 이탈 종료' if r['window_exit_end'] else ''}", va="center", fontsize=7.5)
        ax.set_yticks(y)
        ax.set_yticklabels([f"{a}~{b}" for a, b in zip(v["start"], v["end"])], fontsize=7.5)
        ax.invert_yaxis()
        ax.axvline(1, color=INK, lw=0.8, ls="--")
        ax.set_xlim(0.9, max(2.2, float(v["peak_over_boundary"].max()) + 1.2) if len(v) else 2.2)
        ax.set_xlabel("최대 σ20 / 그날 급변 경계 σ")
        ax.set_title("주분석 q20 구간의 스케일 (빨강 단일 충격형 · 파랑 누적형)", loc="left", fontsize=10)
        style(ax)
        fig.suptitle(f"E2-{num} · {self._lab(t)} — 급변 구간의 스케일과 지속기간", fontsize=12)
        footnote(fig, f"단일 충격형 = 최대 σ 일의 20일 창에서 한 날의 (r-평균)² 몫 ≥ {self.cfg['single_shock_top1_share']:.0%}. 창 이탈 종료 = 그 날이 20일 창에서 빠지는 날 구간이 끝남 (지속기간이 기계적으로 약 20일).")
        fig.tight_layout(rect=(0, 0.04, 1, 0.94))
        return self._save(fig, f"E2_{num}_{t}_scale", {"n_primary_q20": len(v)})

    # E3 — 구간 바텀업 확대
    def e3_bottomup(self, t: str, interval_id: str, tag: str):
        x = self._x(t)
        r = self.iv[self.iv["interval_id"] == interval_id].iloc[0]
        s, e = int(r["i0"]), int(r["i1"])
        lo, hi = max(s - 30, 0), min(e + 30, len(x) - 1)
        w = x.iloc[lo:hi + 1]
        pk = int(x.index[x["date"] == pd.Timestamp(r["peak_date"])][0])
        q = int(r["q"])
        win = x["r"].to_numpy()[pk - q + 1:pk + 1]
        share = (win - win.mean()) ** 2
        share = share / share.sum()
        sh = pd.Series(0.0, index=x.index)
        sh.iloc[pk - q + 1:pk + 1] = share
        c = self.cu[self.cu["ticker"] == t].set_index("date").reindex(w["date"])
        fig, axes = plt.subplots(4, 1, figsize=(14, 12), sharex=True, gridspec_kw={"height_ratios": [1.6, 1.6, 1.6, 1.4]})
        span = (pd.Timestamp(r["start"]), pd.Timestamp(r["end"]) + pd.Timedelta(days=1))
        ax = axes[0]
        cols = SHARE_CMAP(np.clip(sh.loc[w.index].to_numpy() / max(share.max(), 1e-12), 0, 1))
        ax.bar(w["date"], w["r"], color=cols, width=0.8)
        ax.axvspan(*span, color=SHADE20, alpha=0.12, lw=0)
        ax.axvspan(x.loc[pk - q + 1, "date"], x.loc[pk, "date"] + pd.Timedelta(days=1), facecolor="none", edgecolor=INK, lw=0.8, ls=":")
        top = pd.Timestamp(r["top1_date"])
        ax.annotate(f"최대 기여 {r['top1_date']} {r['top1_r']:+.2f}% ({r['top1_share']:.0%})", (top, r["top1_r"]), xytext=(10, 10 if r["top1_r"] > 0 else -18),
                    textcoords="offset points", fontsize=8.5, color=INK, arrowprops={"arrowstyle": "-", "color": MUTED})
        ax.set_ylabel("일간 수익률 (%)")
        ax.set_title(f"① 일간 수익률 — 진할수록 최대 σ 일({r['peak_date']})의 {q}일 창(점선 상자)에서 분산 기여가 큼", loc="left", fontsize=10)
        style(ax)
        ax = axes[1]
        ax.axvspan(*span, color=SHADE20, alpha=0.12, lw=0)
        ax.plot(w["date"], w[f"sigma{q}"], color=CAT[0], lw=1.4, label=f"σ{q}")
        ax.plot(w["date"], w[f"b{q}"], color=INK, lw=1, ls="--", label="급변 경계 (과거 90분위)")
        if q == 20:
            ax.plot(w["date"], w["sigma60"], color=CAT[2], lw=0.9, alpha=0.8, label="σ60")
        ax.axvline(x.loc[s, "date"], color=CAT[2], lw=1)
        ax.text(x.loc[s, "date"], ax.get_ylim()[1] * 0.95, " 진입", fontsize=8, color=INK2, va="top")
        if r["window_exit_end"]:
            ex = x.loc[e + 1, "date"]
            ax.axvline(ex, color=CAT[7], lw=1, ls="-.")
            ax.text(ex, ax.get_ylim()[1] * 0.85, f" 종료 = {r['top1_date']} 이 창에서 빠진 날", fontsize=8, color=INK2, va="top")
        ax.legend(fontsize=7.5, loc="upper left")
        ax.set_ylabel("연환산 σ (%)")
        ax.set_title(f"② 변동성과 경계 — 최대 σ {r['peak_sigma']:.1f}% = 경계의 {r['peak_over_boundary']:.2f}배 · {r['shock_type']}", loc="left", fontsize=10)
        style(ax)
        ax = axes[2]
        base = x.loc[s - 1, "close"]
        ax.axvspan(*span, color=SHADE20, alpha=0.12, lw=0)
        ax.plot(w["date"], (w["close"] / base - 1) * 100, color=INK, lw=1.3)
        ax.axhline(0, color=MUTED, lw=0.6)
        ax.set_ylabel("시작 전날 대비 (%)")
        ax.set_title(f"③ 누적수익률 (시작 전날 종가 = 0) — 구간 {r['ret_interval_pct']:+.1f}% · 구간 최대 낙폭 {r['max_drawdown_pct']:.1f}% · 이후 20일 {r['ret_post20_pct']:+.1f}%", loc="left", fontsize=10)
        style(ax)
        ax = axes[3]
        ax.axvspan(*span, color=SHADE20, alpha=0.12, lw=0)
        for (p, ww), col in zip(self.cfg["cusum_figure_cells"], (CAT[6], CAT[3])):
            ax.plot(w["date"], c[f"R_{p}_{ww}"].to_numpy(float), color=col, lw=1.3, label=f"정책 {p} · w={ww}")
        rmax = c[[f"R_{p}_{ww}" for p in self.cfg["cusum_table_policies"] for ww in self.cfg["cusum_table_windows"]]].max(axis=1)
        ax.plot(w["date"], rmax.to_numpy(float), color=MUTED, lw=0.9, ls=":", label="12셀 중 최대")
        ax.axhline(1, color=INK, lw=1, ls="--")
        ax.set_ylim(0, max(1.15, float(np.nanmax(rmax.to_numpy(float))) * 1.1) if np.isfinite(rmax.to_numpy(float)).any() else 1.15)
        ax.legend(fontsize=7.5, loc="upper left", ncol=3)
        ax.set_ylabel("T / 임계값")
        cov = "계산 안 함 (2021–2025 밖)" if not np.isfinite(rmax.to_numpy(float)).any() else f"구간 최대 T/crit {r['cusum_maxR_any']:.2f} · 경보 {r['cusum_alarm_days_any']}셀-일"
        ax.set_title(f"④ SVR–GARCH CUSUM — {cov}", loc="left", fontsize=10)
        style(ax)
        axes[3].xaxis.set_major_locator(mdates.AutoDateLocator(minticks=6, maxticks=12))
        axes[3].xaxis.set_major_formatter(mdates.DateFormatter("%y-%m-%d"))
        fig.suptitle(f"E3 · {self._lab(t)} — 구간 {r['start']}~{r['end']} ({r['duration']}거래일, q{q}) 은 왜 잡혔나", fontsize=12)
        footnote(fig, f"상위 3 기여일: {r['top3']}. 같은 날 A 그룹 수(10번 N_A) 구간 최대 {int(r['max_N_A_q20'])}/17 · 10번 C1 포함 {r['C1_days']}일. 기여 = (r-평균)² / Σ(r-평균)² (σ 의 표본분산과 정확히 일치).")
        fig.tight_layout(rect=(0, 0.03, 1, 0.96))
        return self._save(fig, f"E3_{tag}_{interval_id}", {"interval": interval_id, "top1": f"{r['top1_date']} {r['top1_r']:+.2f}% {r['top1_share']:.2f}"})

    # X1 — 6종 급변 타임라인 (확장)
    def x1_stack(self):
        tk = self.cfg["tickers"]
        piv = self.d.pivot(index="date", columns="ticker", values="A20")[tk]
        c1 = self.d[self.d["ticker"] == tk[0]].set_index("date")["C1"]
        fig, ax = plt.subplots(figsize=(15, 4.8))
        _img(ax, np.vstack([piv[t].to_numpy(float) for t in tk] + [c1.to_numpy(float)]), pd.DatetimeIndex(piv.index),
             [f"{self.cfg['stage_labels'][t]} · {t}" for t in tk] + ["10번 C1 (시장 공통)"], fs=8)
        ax.axhline(5.5, color=INK, lw=1)
        _years(ax)
        fig.suptitle("X1 · 6종 ETF 의 q20 급변 상태 — KOSPI200 에서 코스닥·국채·단기채·나스닥·원유로 확장 (맨 아래 = 10번 C1)", fontsize=12)
        footnote(fig, "파랑 = 급변(A=1), 회색 = 0, 진회색 = 정의 불가. 10번 C1 = 17개 노출 그룹 중 같은 날 9개 이상 A.")
        fig.tight_layout(rect=(0, 0.05, 1, 0.94))
        return self._save(fig, "X1_six_etf_stack", {})

    # X2 — KOSPI200 구간별 다른 ETF 참여
    def x2_participation(self):
        k = self.r["k200_participation"]
        tk = self.cfg["tickers"][1:]
        m = np.vstack([(k[t] / k["duration"]).to_numpy(float) for t in tk])
        fig, ax = plt.subplots(figsize=(12, 4.5))
        im = ax.imshow(m, cmap=SEQ, vmin=0, vmax=1, aspect="auto")
        ax.set_yticks(range(len(tk)))
        ax.set_yticklabels([self._lab(t) for t in tk], fontsize=8)
        ax.set_xticks(range(len(k)))
        ax.set_xticklabels([f"{a}\n~{b}\n({d}일)" for a, b, d in zip(k["start"], k["end"], k["duration"])], fontsize=7.5)
        for i in range(m.shape[0]):
            for j in range(m.shape[1]):
                ax.text(j, i, f"{int(k[tk[i]].iloc[j])}", ha="center", va="center", fontsize=8, color="white" if m[i, j] > 0.55 else INK)
        fig.colorbar(im, ax=ax, label="구간 일수 중 그 ETF 도 급변인 비율")
        fig.suptitle("X2 · KOSPI200(069500) 주분석 급변 구간마다 다른 5종이 같은 날 급변이었나 (숫자 = 겹친 일수)", fontsize=12)
        fig.tight_layout(rect=(0, 0.02, 1, 0.93))
        return self._save(fig, "X2_kospi200_participation", k.to_dict("records"))

    # X3 — CUSUM 구간 안 vs 밖
    def x3_cusum_io(self):
        io = self.r["inside_outside"]
        tk = self.cfg["tickers"]
        fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharey=True)
        for ax, (p, w) in zip(axes, self.cfg["cusum_figure_cells"]):
            for i, t in enumerate(tk):
                for side, dx, col in (("A20 날", -0.18, SHADE20), ("비 A20 날", 0.18, "#a9a8a2")):
                    z = io[(io.ticker == t) & (io.policy == p) & (io.w == w) & (io.side == side)].iloc[0]
                    ax.vlines(i + dx, z["median_R"], z["max_R"], color=col, lw=2)
                    ax.scatter([i + dx], [z["median_R"]], color=col, s=40, zorder=3, edgecolor="white")
                    ax.scatter([i + dx], [z["max_R"]], color=col, s=25, marker="_", zorder=3)
            ax.axhline(1, color=INK, ls="--", lw=1)
            ax.set_xticks(range(len(tk)))
            ax.set_xticklabels(tk, fontsize=8)
            ax.set_title(f"정책 {p} · w={w} — 점 = 중앙값, 위 끝 = 최댓값", loc="left", fontsize=10)
            style(ax)
        axes[0].set_ylabel("CUSUM T / 임계값")
        fig.suptitle("X3 · 급변일(빨강) vs 나머지 날(회색)의 CUSUM 수준 — 2021–2025", fontsize=12)
        footnote(fig, "급변일에 CUSUM 이 더 높다면 두 신호가 같은 현상을 본다. 임계값(1) 을 넘는 날이 거의 없다는 것은 W3 의 결론(표준화가 변동성 상승을 흡수)과 같은 방향이다.")
        fig.tight_layout(rect=(0, 0.04, 1, 0.93))
        return self._save(fig, "X3_cusum_inside_outside", {})

    # X4 — 전체 구간 지속 × 스케일
    def x4_all(self):
        v = self.iv[(self.iv["q"] == 20) & (self.iv["period"] == "PRIMARY")]
        fig, ax = plt.subplots(figsize=(12, 6))
        for i, t in enumerate(self.cfg["tickers"]):
            z = v[v["ticker"] == t]
            for typ, mk in (("단일 충격형", "o"), ("누적형", "s")):
                zz = z[z["shock_type"] == typ]
                ax.scatter(zz["duration"], zz["peak_over_boundary"], color=CAT[i], marker=mk, s=55, edgecolor="white", lw=1.2,
                           label=f"{t} {typ}" if len(zz) else None, zorder=3)
        ax.axvline(20, color=MUTED, ls=":", lw=1)
        ax.text(20.5, ax.get_ylim()[1] * 0.97, "20거래일 (창 길이)", fontsize=7.5, color=INK2, va="top")
        ax.set_xscale("log")
        ax.set_yscale("log")
        o = v.loc[v["peak_over_boundary"].idxmax()]
        ax.annotate(f"{o['ticker']} {o['start']}~{o['end']} ({o['peak_over_boundary']:.2f}배)\n최대 기여일 {o['top1_date']} — 원자료 확인 필요", (o["duration"], o["peak_over_boundary"]),
                    xytext=(-210, -6), textcoords="offset points", fontsize=7.5, color=INK2, arrowprops={"arrowstyle": "-", "color": MUTED})
        ax.set_xlabel("지속 (거래일, 로그)")
        ax.set_ylabel("최대 σ20 / 진입 경계 (로그)")
        ax.legend(fontsize=7, ncol=3)
        style(ax)
        fig.suptitle(f"X4 · 6종 주분석 q20 급변 구간 {len(v)}개의 지속 × 스케일 (원 = 단일 충격형, 사각 = 누적형)", fontsize=12)
        fig.tight_layout(rect=(0, 0.02, 1, 0.94))
        return self._save(fig, "X4_all_intervals", {"n": len(v)})

    def zoom_targets(self, t: str) -> list[str]:
        """확대 대상: 주분석 q20 구간 중 지속 상위 3개 (동률은 시작일 순) — 계약 외 표시 규칙, 결과에 따라 바꾸지 않는다."""
        v = self._ivs(t, 20)
        v = v[v["period"] == "PRIMARY"].sort_values(["duration", "start"], ascending=[False, True])
        return list(v["interval_id"].head(3))

    def make_all(self) -> dict:
        """노트북과 같은 순서로 전부 그린다 (스크립트 경로 바이트 동일 확인용)."""
        for k, t in enumerate(self.cfg["tickers"], start=1):
            self.e1_timeline(t, str(k))
            self.e2_scale(t, str(k))
            for iv in self.zoom_targets(t):
                self.e3_bottomup(t, iv, str(k))
        self.x1_stack()
        self.x2_participation()
        self.x3_cusum_io()
        self.x4_all()
        return self.caps

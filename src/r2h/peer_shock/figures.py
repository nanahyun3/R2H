# ruff: noqa: E501  — 한국어 그림 캡션·각주 문자열.
"""W4 그림 F01–F34 — 실제 계산 결과만 그린다. 진단(16/17·한 그룹 제외 등)은 '진단 — 라벨 아님' 으로 표기한다.

저장: PNG 320dpi + SVG (W2 ``save`` 재사용, SVG id 결정성). 각 그림 함수는 캡션 수치를 dict 로 돌려준다.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager
from matplotlib.colors import ListedColormap

from r2h.multihorizon.figures import CAT, DIV, INK, INK2, MUTED, SEQ, footnote, save, style

FONT_FILE = Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf")
STATE_CMAP = ListedColormap(["#f0efec", "#2a78d6"])  # 0 = 옅은 회색, 1 = 파랑 (NA 는 별도 회색)
NA_COLOR = "#b9b8b0"
UP, DOWN = "#e34948", "#2a78d6"
PRIMARY = (pd.Timestamp("2021-01-01"), pd.Timestamp("2025-12-31"))


def setup_font() -> None:
    """나눔고딕 등록 — 없으면 □ 로 그리지 않고 실패한다."""
    if not FONT_FILE.exists():
        raise FileNotFoundError(FONT_FILE)
    font_manager.fontManager.addfont(str(FONT_FILE))
    plt.rcParams["font.family"] = font_manager.FontProperties(fname=str(FONT_FILE)).get_name()
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["svg.hashsalt"] = "t18_peer_shock_w4"
    plt.rcParams["figure.facecolor"] = "white"
    plt.rcParams["axes.facecolor"] = "white"


def _primary_band(ax: plt.Axes) -> None:
    """주 분석기간 밖(2019–2020, 2026)을 옅게 칠한다."""
    ax.axvspan(pd.Timestamp("2019-01-01"), PRIMARY[0], color="#f6f5f2", zorder=0)
    ax.axvspan(PRIMARY[1], pd.Timestamp("2026-10-05"), color="#f6f5f2", zorder=0)
    ax.set_xlim(pd.Timestamp("2019-01-02"), pd.Timestamp("2026-10-02"))  # 상태 지도와 같은 가로 범위


def _date_axis(ax: plt.Axes, fmt: str = "%y") -> None:
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter(fmt))


def _state_image(ax, mat: np.ndarray, dates: pd.DatetimeIndex, labels: list[str], cmap=STATE_CMAP, vmin=0, vmax=1):
    """행 = 항목, 열 = 날짜. NaN 은 NA 회색."""
    m = np.ma.masked_invalid(mat)
    cm = cmap.copy() if hasattr(cmap, "copy") else cmap
    cm.set_bad(NA_COLOR)
    x0, x1 = mdates.date2num(dates[0]), mdates.date2num(dates[-1])
    ax.imshow(m, aspect="auto", interpolation="nearest", cmap=cm, vmin=vmin, vmax=vmax,
              extent=[x0, x1, len(labels) - 0.5, -0.5])
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=6.5)
    ax.xaxis_date()
    _date_axis(ax)
    ax.tick_params(colors=INK2, labelsize=7)


def _pivot(df: pd.DataFrame, col: str, rows: list[str], key: str, dates) -> np.ndarray:
    p = df.pivot(index=key, columns="date", values=col).reindex(index=rows, columns=dates)
    return p.to_numpy(float)


class W4Figures:
    """pipeline.run() 결과로 그림을 만든다."""

    def __init__(self, res: dict, root: Path):
        setup_font()
        self.r = res
        self.cfg = res["cfg"]
        self.m = res["main"]
        self.dates = pd.DatetimeIndex(res["dates"])
        self.uni = res["uni"]
        self.name = dict(zip(self.uni["ticker"], self.uni["name"]))
        self.tickers = list(self.uni["ticker"])
        self.groups = list(res["groups"])
        self.out = root / "research/peer_relative_shock_w4/figures"
        self.etf = self.m["etf"]
        self.gs = self.m["groups"]
        self.gl = self.m["global"]
        self.fin = self.m["final"]
        self.caps: dict[str, dict] = {}
        self.root = root

    # ── 공통 ──────────────────────────────────────────────────────────────
    def _save(self, fig, name: str, cap: dict) -> dict:
        save(fig, self.out, name)
        plt.close(fig)
        self.caps[name] = cap
        return cap

    def _lab(self, t: str) -> str:
        return f"{t} {self.name.get(t, '')}"

    def _e(self, q: int) -> pd.DataFrame:
        return self.etf[self.etf["q"] == q]

    def _prim(self, df: pd.DataFrame) -> pd.DataFrame:
        d = pd.to_datetime(df["date"])
        return df[(d >= PRIMARY[0]) & (d <= PRIMARY[1])]

    # ── A. 개별 ETF 변동성 ──────────────────────────────────────────────────
    def f_sigma_grid(self, q: int, name: str) -> dict:
        e = self._e(q)
        fig, axes = plt.subplots(5, 4, figsize=(16, 14), sharex=True)
        cap = {}
        for ax, t in zip(axes.flat, self.tickers):
            d = e[e["ticker"] == t]
            _primary_band(ax)
            ax.plot(d["date"], d["sigma"], color=CAT[0], lw=0.7)
            a = d["A"] == 1
            ymin = np.nanmin(d["sigma"]) if d["sigma"].notna().any() else 0
            ax.scatter(d.loc[a, "date"], np.full(a.sum(), ymin), marker="|", s=18, color=CAT[1], lw=0.6)
            p = self._prim(d)
            ax.set_title(f"{self._lab(t)}\n주분석 중앙 {p['sigma'].median():.1f}% · 최대 {p['sigma'].max():.1f}%", fontsize=8, color=INK)
            style(ax)
            _date_axis(ax)
            cap[t] = {"median": round(float(p["sigma"].median()), 2), "max": round(float(p["sigma"].max()), 2),
                      "A_days": int((p["A"] == 1).sum())}
        fig.suptitle(f"F{'01' if q == 20 else '02'} · ETF 20종 {q}일 연환산 변동성 (%, √252·표본표준편차) — 주황 눈금 = A(자기 과거 90분위 이상)", fontsize=12, y=0.995)
        footnote(fig, "회색 띠 = 주 분석기간(2021–2025) 밖. A 는 엄밀 과거 확장형 mid-rank(최소 252개) 기준. 122630 은 정규화 전 원 변동성(약 2배).")
        fig.tight_layout(rect=(0, 0.02, 1, 0.98))
        return self._save(fig, name, cap)

    def f03_level_vs_rank(self) -> dict:
        vol = pd.read_csv(self.root / "research/peer_relative_shock_w4/results/etf_volatility_summary.csv", dtype={"ticker": str})
        st = pd.read_csv(self.root / "research/peer_relative_shock_w4/results/etf_state_summary.csv", dtype={"ticker": str})
        fig, axes = plt.subplots(1, 3, figsize=(16, 7.5), sharey=True, gridspec_kw={"width_ratios": [2.2, 1.2, 1.2]})
        order = vol[vol["q"] == 20].sort_values("sigma_median")["ticker"].tolist()
        y = np.arange(len(order))
        for k, q in enumerate((20, 60)):
            v = vol[vol["q"] == q].set_index("ticker").loc[order]
            off = -0.18 if q == 20 else 0.18
            axes[0].hlines(y + off, v["sigma_p10"], v["sigma_p90"], color=CAT[k], lw=2.2, label=f"q={q} 10–90분위")
            axes[0].scatter(v["sigma_median"], y + off, color=CAT[k], s=18, zorder=3)
            axes[0].scatter(v["sigma_max"], y + off, color=CAT[k], marker="x", s=18, zorder=3)
        axes[0].set_xscale("log")
        axes[0].xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}"))
        axes[0].set_xlabel("연환산 변동성 (%, 로그축) — 점 = 중앙값, × = 최대")
        axes[0].set_yticks(y)
        axes[0].set_yticklabels([self._lab(t) for t in order], fontsize=8)
        axes[0].legend(fontsize=8, loc="lower right")
        for ax, q in zip(axes[1:], (20, 60)):
            s = st[st["q"] == q].set_index("ticker").loc[order]
            ax.barh(y, s["A_rate_primary"] * 100, color=CAT[0], height=0.6)
            ax.axvline(10, color=MUTED, ls="--", lw=0.8)
            ax.set_xlabel(f"q={q} 주분석 A 비율 (%)\n점선 = 명목 10%")
            for yy, val in zip(y, s["A_rate_primary"] * 100):
                ax.text(val + 0.3, yy, f"{val:.1f}", va="center", fontsize=7, color=INK2)
        for ax in axes:
            style(ax)
        fig.suptitle("F03 · 절대 변동성 수준과 자기 과거 분위(A 비율)는 다른 순서를 만든다", fontsize=12)
        footnote(fig, "주 분석기간 2021–2025 (1,225일). A 비율이 10% 와 다른 이유: 확장형 기준분포에 2020 코로나 구간이 남아 있으면 이후 고변동성이 상위 10% 에 들기 어렵다.")
        fig.tight_layout(rect=(0, 0.03, 1, 0.96))
        s60 = st[st["q"] == 60].set_index("ticker")
        cap = {"zero_A_q60": sorted(s60.index[s60["A_rate_primary"] == 0].tolist()),
               "max_A_q20": st[st["q"] == 20].sort_values("A_rate_primary").iloc[-1][["ticker", "A_rate_primary"]].tolist()}
        return self._save(fig, "F03_level_vs_rank", cap)

    def f04_A_heatmap(self) -> dict:
        fig, axes = plt.subplots(2, 1, figsize=(15, 9), sharex=True)
        cap = {}
        for ax, q in zip(axes, (20, 60)):
            mat = _pivot(self._e(q), "A", self.tickers, "ticker", self.dates)
            _state_image(ax, mat, self.dates, [self._lab(t) for t in self.tickers])
            ax.set_title(f"q={q}: A 상태 (파랑 = 1, 옅은 회색 = 0, 진한 회색 = NA 기준 부족)", fontsize=10, loc="left")
            colsum = np.nansum(mat == 1, axis=0)
            cap[f"q{q}_max_etf_A_same_day"] = int(colsum.max())
            cap[f"q{q}_max_date"] = str(self.dates[int(colsum.argmax())].date())
        fig.suptitle("F04 · 20일·60일 A(자기 과거 대비 고변동성) 상태 지도", fontsize=12)
        footnote(fig, f"같은 날 A 인 ETF 최대: q20 {cap['q20_max_etf_A_same_day']}종 ({cap['q20_max_date']}), q60 {cap['q60_max_etf_A_same_day']}종 ({cap['q60_max_date']}). 앞쪽 NA 는 기준 252개를 채우기 전.")
        fig.tight_layout(rect=(0, 0.03, 1, 0.97))
        return self._save(fig, "F04_A_heatmap", cap)

    def f05_leverage_norm(self) -> dict:
        e = self._e(20)
        fig, axes = plt.subplots(2, 1, figsize=(14, 7.5), sharex=True)
        cols = {"069500": CAT[0], "102110": CAT[2], "122630": CAT[1], "114800": CAT[6]}
        for t, c in cols.items():
            d = e[e["ticker"] == t]
            axes[0].plot(d["date"], d["sigma"], color=c, lw=0.7, label=self._lab(t))
            axes[1].plot(d["date"], d["sigma_adj"], color=c, lw=0.7, label=self._lab(t))
        aux = pd.read_csv(self.root / "research/peer_relative_shock_w4/results/kospi200_aux_diagnostics.csv", dtype={"ticker": str})
        a20 = aux[aux["q"] == 20].set_index("ticker")
        axes[0].set_title("정규화 전 σ (q=20, %)", loc="left", fontsize=10)
        axes[1].set_title(f"정규화 후 σ/|m| — 122630 은 ÷2, 114800 은 ÷1. 4종 최대/최소 비 중앙 {a20['four_range_median'].iloc[0]:.3f}, 95분위 {a20['four_range_p95'].iloc[0]:.3f}", loc="left", fontsize=10)
        for ax in axes:
            _primary_band(ax)
            style(ax)
            ax.legend(fontsize=8, ncol=4)
            _date_axis(ax)
        fig.suptitle("F05 · 레버리지·인버스 배율 정규화 전후 (KOSPI200 동일 노출 4종)", fontsize=12)
        footnote(fig, f"주분석 정규화 비율(대 Core Pair 중앙값) 중앙: 122630 {a20.loc['122630','adj_ratio_to_core_median']:.3f}, 114800 {a20.loc['114800','adj_ratio_to_core_median']:.3f}. 일간 목표 배율 기준이며 장기 누적 배율을 보장하지 않는다.")
        fig.tight_layout(rect=(0, 0.03, 1, 0.96))
        return self._save(fig, "F05_leverage_normalization", {"ratio_122630": round(float(a20.loc["122630", "adj_ratio_to_core_median"]), 4),
                                                              "ratio_114800": round(float(a20.loc["114800", "adj_ratio_to_core_median"]), 4)})

    # ── B. Peer 상대 ─────────────────────────────────────────────────────────
    def f06_network(self) -> dict:
        m = self.r["mapping"]
        ad = m[m["adopted"]]
        ev = self.tickers
        peers = list(dict.fromkeys(ad["peer_ticker"]))
        fig, ax = plt.subplots(figsize=(13, 15))
        ye = {t: i for i, t in enumerate(ev)}
        yp = {p: i * (len(ev) - 1) / max(len(peers) - 1, 1) for i, p in enumerate(peers)}
        for _, x in ad.iterrows():
            c = CAT[0] if x["tier"] == 1 else CAT[1]
            ax.plot([0, 1], [ye[x["eval_ticker"]], yp[x["peer_ticker"]]], color=c, lw=0.8, alpha=0.7)
        for t in ev:
            st = ad[ad["eval_ticker"] == t]
            ax.text(-0.02, ye[t], f"{self._lab(t)} [{st['quality_grade'].iloc[0]}]", ha="right", va="center", fontsize=8)
        pname = dict(zip(ad["peer_ticker"], ad["peer_name"]))
        for p in peers:
            ax.text(1.02, yp[p], f"{p} {pname[p]}" + (" ★평가20" if p in ye else ""), ha="left", va="center", fontsize=7)
        ax.scatter([0] * len(ev), list(ye.values()), color=INK, s=12, zorder=3)
        ax.scatter([1] * len(peers), list(yp.values()), color=MUTED, s=10, zorder=3)
        ax.set_xlim(-0.9, 1.9)
        ax.invert_yaxis()
        ax.axis("off")
        ax.plot([], [], color=CAT[0], label="Tier 1 동일 기초지수")
        ax.plot([], [], color=CAT[1], label="Tier 2 유사 위험")
        ax.legend(loc="lower center", fontsize=9, ncol=2)
        n1, n2 = int((ad["tier"] == 1).sum()), int((ad["tier"] == 2).sum())
        excl = int((~m["eligible"]).sum())
        ax.set_title(f"F06 · Peer Mapping (동결 W4-lock-1) — 평가 20종 → 참조 {len(peers)}종, 연결 Tier1 {n1} · Tier2 {n2}, 늦은 상장 제외 {excl}", fontsize=11)
        footnote(fig, "등급 A = Tier1 2개 이상, B = Tier1 단일, C = Tier2. 선정에 가격 통계(상관·변동성)를 쓰지 않았다. 노출 그룹(17)과 Peer 집합은 다른 개념이다.")
        return self._save(fig, "F06_peer_network", {"n_peers": len(peers), "tier1_edges": n1, "tier2_edges": n2, "late_excluded": excl})

    def f07_ratio_grid(self) -> dict:
        e = self._e(20)
        fig, axes = plt.subplots(5, 4, figsize=(16, 14), sharex=True)
        cap = {}
        for ax, t in zip(axes.flat, self.tickers):
            d = e[e["ticker"] == t]
            _primary_band(ax)
            ax.plot(d["date"], d["L"], color=INK2, lw=0.6)
            ax.axhline(0, color=MUTED, lw=0.6)
            u, dn = d["B_UP"] == 1, d["B_DOWN"] == 1
            ax.scatter(d.loc[u, "date"], d.loc[u, "L"], s=3, color=UP)
            ax.scatter(d.loc[dn, "date"], d.loc[dn, "L"], s=3, color=DOWN)
            p = self._prim(d)
            ax.set_title(f"{self._lab(t)}\nB↑ {int((p['B_UP']==1).sum())}일 · B↓ {int((p['B_DOWN']==1).sum())}일", fontsize=8)
            style(ax)
            _date_axis(ax)
            cap[t] = {"B_UP": int((p["B_UP"] == 1).sum()), "B_DOWN": int((p["B_DOWN"] == 1).sum())}
        fig.suptitle("F07 · Peer 상대 로그 변동성 비율 L = log(σ_adj / Peer 중앙값) (q=20) — 빨강 B↑, 파랑 B↓", fontsize=12, y=0.995)
        footnote(fig, "069500·102110 의 그룹 B 는 Core Pair 비율로 따로 판정한다(F10). 이 그림의 069500·102110 은 Tier1 7종 중앙값 기준 개별 B 다. B↓ 는 저변동성이 아니라 평소 상대 관계의 하방 이탈.")
        fig.tight_layout(rect=(0, 0.02, 1, 0.98))
        return self._save(fig, "F07_peer_ratio_grid", cap)

    def f08_UB_heat(self) -> dict:
        fig, axes = plt.subplots(2, 1, figsize=(15, 9), sharex=True)
        for ax, q in zip(axes, (20, 60)):
            mat = _pivot(self._e(q), "U_B", self.tickers, "ticker", self.dates)
            _state_image(ax, mat, self.dates, [self._lab(t) for t in self.tickers], cmap=DIV, vmin=0, vmax=1)
            ax.set_title(f"q={q}: L 의 과거 분위 U_B (파랑 = 하위, 빨강 = 상위, 회색 = NA)", fontsize=10, loc="left")
        fig.suptitle("F08 · Peer 로그비율의 자기 과거 분위 — B 는 U_B ≤ 0.05 또는 ≥ 0.95", fontsize=12)
        footnote(fig, "분위는 엄밀 과거 확장형 mid-rank (최소 252개). 동일 지수 Peer 의 비율은 주로 추적 차이·호가·유동성 차이를 반영한다.")
        fig.tight_layout(rect=(0, 0.03, 1, 0.97))
        return self._save(fig, "F08_peer_ratio_rank_heat", {})

    def f09_B_map(self) -> dict:
        fig, axes = plt.subplots(2, 1, figsize=(15, 9), sharex=True)
        cap = {}
        cm = ListedColormap([DOWN, "#f0efec", UP])
        for ax, q in zip(axes, (20, 60)):
            e = self._e(q).copy()
            e["dir"] = np.where(e["B_UP"] == 1, 1.0, np.where(e["B_DOWN"] == 1, -1.0, np.where(e["B"].notna(), 0.0, np.nan)))
            mat = _pivot(e, "dir", self.tickers, "ticker", self.dates)
            _state_image(ax, mat, self.dates, [self._lab(t) for t in self.tickers], cmap=cm, vmin=-1, vmax=1)
            p = self._prim(e)
            nu, nd = int((p["B_UP"] == 1).sum()), int((p["B_DOWN"] == 1).sum())
            ax.set_title(f"q={q}: 빨강 B↑ {nu} ETF-일 · 파랑 B↓ {nd} ETF-일 (주분석)", fontsize=10, loc="left")
            cap[f"q{q}"] = {"up": nu, "down": nd}
        fig.suptitle("F09 · B 양방향 사건 지도 — 상대 변동성 괴리는 ETF 마다 다른 날에 흩어진다", fontsize=12)
        footnote(fig, "B↑ = Peer 대비 평소보다 상대적으로 큼, B↓ = 평소보다 상대적으로 작음(Peer 가 더 크게 움직였을 수 있음).")
        fig.tight_layout(rect=(0, 0.03, 1, 0.97))
        return self._save(fig, "F09_B_direction_map", cap)

    def f10_kospi(self) -> dict:
        e = self._e(20)
        core = self.m["core"][20].assign(date=self.dates)
        fig, axes = plt.subplots(4, 1, figsize=(14, 12), sharex=True, gridspec_kw={"height_ratios": [2, 1.4, 1.2, 0.8]})
        for t, c in {"069500": CAT[0], "102110": CAT[2], "122630": CAT[1], "114800": CAT[6]}.items():
            d = e[e["ticker"] == t]
            axes[0].plot(d["date"], d["sigma_adj"], color=c, lw=0.7, label=self._lab(t) + (" ÷2" if t == "122630" else ""))
        axes[0].legend(fontsize=8, ncol=4)
        axes[0].set_title("배율 정규화 σ_adj (q=20, %)", loc="left", fontsize=10)
        axes[1].plot(core["date"], core["L"] * 100, color=INK2, lw=0.6)
        axes[1].set_title("Core Pair 로그비율 100·log(σ069500/σ102110) — 단위 % 포인트", loc="left", fontsize=10)
        u, d_ = core["B_UP"] == 1, core["B_DOWN"] == 1
        axes[1].scatter(core.loc[u, "date"], core.loc[u, "L"] * 100, s=4, color=UP)
        axes[1].scatter(core.loc[d_, "date"], core.loc[d_, "L"] * 100, s=4, color=DOWN)
        axes[2].plot(core["date"], core["U_B"], color=INK2, lw=0.6)
        axes[2].axhline(0.95, color=UP, ls="--", lw=0.8)
        axes[2].axhline(0.05, color=DOWN, ls="--", lw=0.8)
        axes[2].set_title("U_B (Core Pair 비율의 과거 분위)", loc="left", fontsize=10)
        g = self.gs[(self.gs["q"] == 20) & (self.gs["group"] == self.cfg["kospi200_group"])]
        mat = np.vstack([g["GROUP_A"].to_numpy(), g["GROUP_B"].to_numpy(), g["GROUP_AB"].to_numpy()])
        _state_image(axes[3], mat, self.dates, ["그룹 A", "그룹 B", "그룹 AB"])
        for ax in axes[:3]:
            _primary_band(ax)
            style(ax)
            _date_axis(ax)
        pc = self._prim(core.assign(date=self.dates))
        cap = {"core_L_abs_median_pctpt": round(float(np.nanmedian(np.abs(pc["L"])) * 100), 3),
               "core_B_UP": int((pc["B_UP"] == 1).sum()), "core_B_DOWN": int((pc["B_DOWN"] == 1).sum()),
               "group_AB_days": int((self._prim(g)["GROUP_AB"] == 1).sum())}
        fig.suptitle(f"F10 · KOSPI200 동일 지수 4종 — 같은 지수여도 상대 변동성 괴리는 존재한다 (주분석 |L| 중앙 {cap['core_L_abs_median_pctpt']} %p)", fontsize=12)
        footnote(fig, f"주분석 Core Pair B↑ {cap['core_B_UP']}일 · B↓ {cap['core_B_DOWN']}일 · 그룹 AB {cap['group_AB_days']}일 (q=20). 레버리지·인버스는 보조 진단(거부권 없음).")
        fig.tight_layout(rect=(0, 0.03, 1, 0.96))
        return self._save(fig, "F10_kospi200_four", cap)

    def _own_vs_peer(self, tickers: list[str], name: str, title: str) -> dict:
        e = self._e(20)
        n = len(tickers)
        fig, axes = plt.subplots(n, 1, figsize=(14, 2.1 * n), sharex=True)
        cap = {}
        for ax, t in zip(axes, tickers):
            d = e[e["ticker"] == t]
            _primary_band(ax)
            ax.plot(d["date"], d["sigma_adj"], color=CAT[0], lw=0.7, label="자기 σ_adj")
            ax.plot(d["date"], d["peer_median_adj"], color=MUTED, lw=0.7, label="Peer 중앙값")
            ylim = ax.get_ylim()
            for col, c in (("B_UP", UP), ("B_DOWN", DOWN)):
                s = d[col] == 1
                ax.vlines(d.loc[s, "date"], ylim[0], ylim[1], color=c, alpha=0.08, lw=0.8)
            ax.set_ylim(ylim)
            peers = "·".join(self.r["peers"][t])
            p = self._prim(d)
            ax.set_title(f"{self._lab(t)}  vs  [{peers}]  — 주분석 B↑ {int((p['B_UP']==1).sum())} · B↓ {int((p['B_DOWN']==1).sum())} · AB {int((p['AB']==1).sum())}일", fontsize=8.5, loc="left")
            style(ax)
            _date_axis(ax)
            cap[t] = {"B_UP": int((p["B_UP"] == 1).sum()), "B_DOWN": int((p["B_DOWN"] == 1).sum()), "AB": int((p["AB"] == 1).sum())}
        axes[0].legend(fontsize=8, loc="upper right")
        fig.suptitle(title, fontsize=12)
        footnote(fig, "q=20 연환산 % · 세로 띠: 빨강 B↑, 파랑 B↓. Peer 품질 등급과 약점은 PEER_MAPPING_CONTRACT.md.")
        fig.tight_layout(rect=(0, 0.02, 1, 0.97))
        return self._save(fig, name, cap)

    # ── C. 그룹 ───────────────────────────────────────────────────────────────
    def f_group_timeline(self, k: str, num: str) -> dict:
        fig, axes = plt.subplots(2, 1, figsize=(15, 8), sharex=True)
        cap = {}
        for ax, q in zip(axes, (20, 60)):
            g = self.gs[self.gs["q"] == q]
            mat = _pivot(g, f"GROUP_{k}", self.groups, "group", self.dates)
            _state_image(ax, mat, self.dates, self.groups)
            col = np.nansum(mat == 1, axis=0)
            prim = (self.dates >= PRIMARY[0]) & (self.dates <= PRIMARY[1])
            ax.set_title(f"q={q}: GROUP_{k} — 같은 날 최대: 주분석 {int(col[prim].max())}/17 · 전체(2020 파일럿 포함) {int(col.max())}/17", fontsize=10, loc="left")
            cap[f"q{q}_max_primary"] = int(col[prim].max())
            cap[f"q{q}_max_all"] = int(col.max())
        lab = {"A": "자기 과거 고변동성", "B": "Peer 상대 괴리(양방향)", "AB": "A ∧ B"}[k]
        fig.suptitle(f"F{num} · 17개 노출 그룹 {k} 상태 타임라인 — {lab}", fontsize=12)
        footnote(fig, "KOSPI200_동일노출 = Core Pair 규칙(A 는 두 ETF 모두, B 는 069500/102110 비율). 나머지 16 그룹은 단일 ETF.")
        fig.tight_layout(rect=(0, 0.03, 1, 0.97))
        return self._save(fig, f"F{num}_group_{k}_timeline", cap)

    def f_count(self, k: str, num: str) -> dict:
        fig, ax = plt.subplots(figsize=(14, 4.8))
        _primary_band(ax)
        cap = {}
        for q, c in ((20, CAT[0]), (60, CAT[1])):
            g = self.gl[self.gl["q"] == q]
            ax.plot(g["date"], g[f"n_{k}"], color=c, lw=0.8, label=f"q={q}")
            pg = self._prim(g)
            i = pg[f"n_{k}"].idxmax()
            cap[f"q{q}_max"] = int(pg[f"n_{k}"].max())
            cap[f"q{q}_max_date"] = str(pd.Timestamp(pg.loc[i, "date"]).date())
            ax.annotate(f"q{q} 최대 {cap[f'q{q}_max']} ({cap[f'q{q}_max_date']})", (pg.loc[i, "date"], pg.loc[i, f"n_{k}"]),
                        xytext=(10, 8), textcoords="offset points", fontsize=8, color=c)
        ax.axhline(17, color=INK, ls="--", lw=1)
        ax.text(self.dates[5], 17.2, "17/17 — 급변 정의선", fontsize=8)
        ax.set_ylim(0, 18)
        ax.set_ylabel(f"{k} 충족 그룹 수 (0–17)")
        ax.legend(fontsize=8)
        style(ax)
        _date_axis(ax)
        fig.suptitle(f"F{num} · 17개 그룹 중 {k} 참여 개수", fontsize=12)
        pil = self.gl[pd.to_datetime(self.gl["date"]).dt.year == 2020]
        cap["pilot_max"] = {q: int(pil[pil["q"] == q][f"n_{k}"].max()) for q in (20, 60)}
        footnote(fig, f"주 분석기간(흰 배경) 기준 최대값 표기. 2020 파일럿 최대: q20 {cap['pilot_max'][20]} · q60 {cap['pilot_max'][60]} (성공 근거로 쓰지 않음). 15/17·16/17 등은 진단일 뿐 라벨이 아니다.")
        fig.tight_layout(rect=(0, 0.04, 1, 0.95))
        return self._save(fig, f"F{num}_count_{k}", cap)

    def f19_intersection(self) -> dict:
        fig, axes = plt.subplots(1, 2, figsize=(15, 7.5), sharey=True)
        cap = {}
        for ax, q in zip(axes, (20, 60)):
            p = self._prim(self._e(q))
            rows = []
            for t in self.tickers:
                d = p[p["ticker"] == t]
                a, b = d["A"] == 1, d["B"] == 1
                rows.append((int((a & ~b).sum()), int((a & b).sum()), int((~a & b).sum())))
            arr = np.array(rows)
            y = np.arange(len(self.tickers))
            ax.barh(y, arr[:, 0], color=CAT[0], label="A 만")
            ax.barh(y, arr[:, 1], left=arr[:, 0], color=CAT[6], label="A ∧ B (AB)")
            ax.barh(y, arr[:, 2], left=arr[:, 0] + arr[:, 1], color=CAT[1], label="B 만")
            ax.set_yticks(y)
            ax.set_yticklabels([self._lab(t) for t in self.tickers], fontsize=8)
            ax.set_xlabel(f"q={q} 주분석 일수")
            ax.legend(fontsize=8)
            style(ax)
            tot_a, tot_ab = int(arr[:, :2].sum()), int(arr[:, 1].sum())
            cap[f"q{q}"] = {"A_total": tot_a, "AB_total": tot_ab, "B_total": int(arr[:, 1:].sum()),
                            "AB_share_of_A": round(tot_ab / tot_a, 4) if tot_a else None}
            ax.set_title(f"q={q}: A 의 {100*cap[f'q{q}']['AB_share_of_A']:.1f}% 만 B 와 겹친다", fontsize=10, loc="left")
        fig.suptitle("F19 · A·B·AB 교집합 — 자기 과거 고변동성과 Peer 상대 괴리는 대체로 다른 날이다", fontsize=12)
        footnote(fig, "ETF-일 단위, 2021–2025. A 와 B 는 독립 지표가 아니며(같은 σ 를 씀) 동시 발생은 자산마다 다르다.")
        fig.tight_layout(rect=(0, 0.03, 1, 0.96))
        return self._save(fig, "F19_A_B_intersection", cap)

    def f20_horizons(self) -> dict:
        g20 = self._prim(self.gl[self.gl["q"] == 20]).set_index("date")
        g60 = self._prim(self.gl[self.gl["q"] == 60]).set_index("date")
        fig, axes = plt.subplots(1, 3, figsize=(16, 5.2))
        cap = {}
        for ax, k in zip(axes, ("A", "B", "AB")):
            x, y = g20[f"n_{k}"], g60[f"n_{k}"].reindex(g20.index)
            tab = pd.crosstab(x, y)
            ax.imshow(np.log1p(tab.to_numpy()), cmap="Blues", origin="lower", aspect="auto")
            ax.set_xticks(range(tab.shape[1]))
            ax.set_xticklabels(tab.columns, fontsize=7)
            ax.set_yticks(range(tab.shape[0]))
            ax.set_yticklabels(tab.index, fontsize=7)
            ax.set_xlabel(f"q=60 {k} 그룹 수")
            ax.set_ylabel(f"q=20 {k} 그룹 수")
            rho = x.corr(y, method="spearman")
            ax.set_title(f"{k}: 일별 그룹 수 Spearman ρ = {rho:.2f}", fontsize=10)
            cap[k] = round(float(rho), 4)
        # 그룹-일 단위 일치도
        gs = self._prim(self.gs)
        p20 = gs[gs["q"] == 20].set_index(["date", "group"])
        p60 = gs[gs["q"] == 60].set_index(["date", "group"])
        for k in ("A", "AB"):
            a, b = p20[f"GROUP_{k}"] == 1, p60[f"GROUP_{k}"].reindex(p20.index) == 1
            cap[f"jaccard_group_day_{k}"] = round(float((a & b).sum() / max((a | b).sum(), 1)), 4)
        fig.suptitle(f"F20 · 20일 대 60일 — 그룹-일 Jaccard A {cap['jaccard_group_day_A']:.2f}, AB {cap['jaccard_group_day_AB']:.2f}", fontsize=12)
        footnote(fig, "칸 색 = log(1+일수). 2021–2025. 두 기간은 같은 사건을 다른 시차·길이로 본다.")
        fig.tight_layout(rect=(0, 0.04, 1, 0.94))
        return self._save(fig, "F20_horizon_20_vs_60", cap)

    # ── D. 최종 ───────────────────────────────────────────────────────────────
    def f_global(self, k: str, num: str) -> dict:
        fig, axes = plt.subplots(2, 1, figsize=(14, 6.5), sharex=True, gridspec_kw={"height_ratios": [3, 1]})
        cap = {}
        for q, c in ((20, CAT[0]), (60, CAT[1])):
            g = self.gl[self.gl["q"] == q]
            axes[0].plot(g["date"], 17 - g[f"n_{k}"], color=c, lw=0.8, label=f"q={q}: 17/17 까지 모자란 그룹 수")
            pg = self._prim(g)
            cap[f"q{q}_days17"] = int((pg[f"GLOBAL_{k}"] == 1).sum())
            cap[f"q{q}_min_gap"] = int(17 - pg[f"n_{k}"].max())
            pil = g[pd.to_datetime(g["date"]).dt.year == 2020]
            cap[f"q{q}_pilot_days17"] = int((pil[f"GLOBAL_{k}"] == 1).sum())
        axes[0].axhline(0, color=INK, ls="--", lw=1)
        axes[0].set_ylim(-0.5, 17.5)
        axes[0].set_ylabel("17 - 충족 그룹 수")
        axes[0].legend(fontsize=8)
        mat = np.vstack([self.gl[self.gl["q"] == q][f"GLOBAL_{k}"].to_numpy() for q in (20, 60)])
        _state_image(axes[1], mat, self.dates, [f"GLOBAL_{k} q20", f"GLOBAL_{k} q60"])
        _primary_band(axes[0])
        style(axes[0])
        _date_axis(axes[0])
        fig.suptitle(f"F{num} · GLOBAL_{k} 17/17 충족일: q20 {cap['q20_days17']}일 · q60 {cap['q60_days17']}일 (주분석) — 최소 부족 q20 {cap['q20_min_gap']}·q60 {cap['q60_min_gap']} 그룹", fontsize=11.5)
        footnote(fig, f"아래 띠: 파랑 = 1(충족), 옅은 회색 = 0, 진한 회색 = NA. 0 선에 닿는 날이 17/17 이다. 2020 파일럿(성공 근거 아님) 17/17: q20 {cap['q20_pilot_days17']}일 · q60 {cap['q60_pilot_days17']}일.")
        fig.tight_layout(rect=(0, 0.04, 1, 0.94))
        return self._save(fig, f"F{num}_global_{k}_17of17", cap)

    def f24_final(self) -> dict:
        fig, axes = plt.subplots(3, 1, figsize=(14, 7.5), sharex=True, gridspec_kw={"height_ratios": [2.2, 0.6, 0.6]})
        for q, c in ((20, CAT[0]), (60, CAT[1])):
            g = self.gl[self.gl["q"] == q]
            axes[0].plot(g["date"], g["n_AB"], color=c, lw=0.8, label=f"AB 충족 그룹 수 q={q}")
        axes[0].axhline(17, color=INK, ls="--", lw=1)
        axes[0].set_ylim(0, 18)
        axes[0].legend(fontsize=8)
        _primary_band(axes[0])
        style(axes[0])
        _date_axis(axes[0])
        f = self.fin
        _state_image(axes[1], f[["FINAL_SHOCK"]].T.to_numpy(float), self.dates, ["FINAL_SHOCK"])
        avail = np.vstack([np.isfinite(f["FINAL_SHOCK"].to_numpy(float)).astype(float)])
        _state_image(axes[2], avail, self.dates, ["판정 가능"])
        n_iv = len(self.m["intervals"])
        v = self.m["verdict"]
        fig.suptitle(f"F24 · FINAL_SHOCK = GLOBAL_AB(20) ∨ GLOBAL_AB(60): 급변 구간 {n_iv}개 — 판정 {v['verdict']} (주분석 판정 가능 {v['primary_evaluable_share']*100:.1f}%)", fontsize=11.5)
        footnote(fig, f"주분석 1,225일 중 FINAL=1 은 {v['primary_final_true_days']}일. 존재하지 않는 구간을 그리지 않았다. AB 최대는 q20 3·q60 2 그룹.")
        fig.tight_layout(rect=(0, 0.04, 1, 0.94))
        return self._save(fig, "F24_final_shock_timeline", {"n_intervals": n_iv, **v})

    def f25_durations(self) -> dict:
        sens = self.r["sens"]
        fig, axes = plt.subplots(1, 2, figsize=(15, 6), gridspec_kw={"width_ratios": [1, 1.6]})
        axes[0].bar(sens["variant"], sens["n_intervals"], color=CAT[0])
        axes[0].set_ylim(0, 1)
        for i, v in enumerate(sens["n_intervals"]):
            axes[0].text(i, 0.03, f"{v}개", ha="center", fontsize=10)
        axes[0].set_title("급변 구간 수 (주 정의 + 민감도 4종)", fontsize=10, loc="left")
        axes[0].tick_params(axis="x", labelrotation=20)
        # 진단: 그룹별 GROUP_AB 최장 연속일 (라벨 아님)
        rows = []
        for q in (20, 60):
            g = self._prim(self.gs[self.gs["q"] == q])
            for grp, d in g.groupby("group", sort=False):
                v = d["GROUP_AB"].to_numpy()
                best = cur = 0
                for x in v:
                    cur = cur + 1 if x == 1 else 0
                    best = max(best, cur)
                rows.append((q, grp, best))
        r = pd.DataFrame(rows, columns=["q", "group", "max_run"])
        y = np.arange(len(self.groups))
        for k, q in enumerate((20, 60)):
            rr = r[r["q"] == q].set_index("group").reindex(self.groups)
            axes[1].barh(y + (-0.2 if q == 20 else 0.2), rr["max_run"], height=0.38, color=CAT[k], label=f"q={q}")
        axes[1].set_yticks(y)
        axes[1].set_yticklabels(self.groups, fontsize=8)
        axes[1].set_xlabel("그룹 개별 GROUP_AB 최장 연속 거래일 (2021–2025)")
        axes[1].set_title("진단 — 라벨 아님: 개별 그룹의 AB 지속", fontsize=10, loc="left")
        axes[1].legend(fontsize=8)
        for ax in axes:
            style(ax)
        fig.suptitle("F25 · 급변 구간별 지속기간 — 17/17 구간이 없으므로 지속기간 분포는 비어 있다", fontsize=12)
        footnote(fig, "오른쪽은 각 그룹이 혼자 AB 를 유지한 최장 기간이다. 공동 구간이 아니며 최종 라벨로 쓰지 않는다.")
        fig.tight_layout(rect=(0, 0.04, 1, 0.94))
        return self._save(fig, "F25_interval_durations", {"intervals_all_variants": sens["n_intervals"].tolist(),
                                                          "max_group_run": r.groupby("q")["max_run"].max().to_dict()})

    def f26_bottleneck(self) -> dict:
        bt = pd.read_csv(self.root / "research/peer_relative_shock_w4/results/bottleneck_groups.csv")
        fig, axes = plt.subplots(1, 2, figsize=(16, 7.5), sharey=True)
        y = np.arange(len(self.groups))
        cap = {}
        for ax, q in zip(axes, (20, 60)):
            b = bt[bt["q"] == q].set_index("group").reindex(self.groups)
            ax.barh(y - 0.2, (1 - b["A_false_share"] - b["A_na_share"]) * 100, height=0.38, color=CAT[0], label="A 충족 비율 %")
            ax.barh(y + 0.2, (1 - b["B_false_share"] - b["B_na_share"]) * 100, height=0.38, color=CAT[1], label="B 충족 비율 %")
            ax.set_yticks(y)
            ax.set_yticklabels(self.groups, fontsize=8)
            ax.set_xlabel(f"q={q} 주분석 그룹-일 비율 (%)")
            ax.legend(fontsize=8, loc="lower right")
            style(ax)
            cap[f"q{q}"] = {"loo_AB_max": int(b["loo_AB_16of16_days"].max()), "sole_blocker_AB_max": int(b["sole_blocker_AB_days"].max()),
                            "loo_A_max": int(b["loo_A_16of16_days"].max()), "loo_B_max": int(b["loo_B_16of16_days"].max())}
            ax.set_title(f"q={q}: 어느 한 그룹을 빼도 나머지 16/16 AB {cap[f'q{q}']['loo_AB_max']}일 · A {cap[f'q{q}']['loo_A_max']}일 · B {cap[f'q{q}']['loo_B_max']}일", fontsize=10, loc="left")
        fig.suptitle("F26 · 17/17 을 막는 병목 — 특정 한 그룹이 아니라 A·B 가 동시에 넓게 퍼지지 않는 구조", fontsize=12)
        footnote(fig, "한 그룹 제외(16/16)와 '유일 병목'은 진단이다. 라벨이 아니며 정의를 바꾸지 않는다.")
        fig.tight_layout(rect=(0, 0.04, 1, 0.94))
        return self._save(fig, "F26_bottleneck", cap)

    def f27_distribution(self) -> dict:
        dist = pd.read_csv(self.root / "research/peer_relative_shock_w4/results/participation_distribution.csv")
        fig, axes = plt.subplots(2, 3, figsize=(16, 7.5), sharex=True)
        cap = {}
        for i, q in enumerate((20, 60)):
            for j, k in enumerate(("A", "B", "AB")):
                d = dist[(dist["q"] == q) & (dist["state"] == k)]
                ax = axes[i, j]
                ax.bar(d["n_groups"], d["days_primary"], color=CAT[j])
                ax.set_yscale("symlog", linthresh=1)
                ax.axvline(17, color=INK, ls="--", lw=1)
                nz = d[d["days_primary"] > 0]["n_groups"].max()
                ax.set_title(f"q={q} {k}: 최대 {nz}/17, 17/17 {int(d[d['n_groups']==17]['days_primary'].iloc[0])}일", fontsize=10)
                ax.set_xticks(range(0, 18, 2))
                style(ax)
                cap[f"q{q}_{k}_max"] = int(nz)
        for ax in axes[1]:
            ax.set_xlabel("같은 날 충족 그룹 수")
        for ax in axes[:, 0]:
            ax.set_ylabel("주분석 일수 (symlog)")
        fig.suptitle("F27 · 0–17 참여 그룹 수 분포 (2021–2025, 1,225일)", fontsize=12)
        footnote(fig, "점선 = 17. 분포의 오른쪽 끝이 17 에 닿지 않는다.")
        fig.tight_layout(rect=(0, 0.04, 1, 0.95))
        return self._save(fig, "F27_participation_distribution", cap)

    # ── E. 기존 연구 대조 ─────────────────────────────────────────────────────
    def f_event(self, ev: str, num: str, title: str) -> dict:
        s, en = map(pd.Timestamp, self.cfg["events"][ev]["window"])
        idx = (self.dates >= s) & (self.dates <= en)
        dts = self.dates[idx]
        closes = self.r["closes"].loc[dts, self.tickers]
        e20 = self._e(20)
        e20 = e20[(e20["date"] >= s) & (e20["date"] <= en)]
        fig, axes = plt.subplots(6, 1, figsize=(14, 17), sharex=False,
                                 gridspec_kw={"height_ratios": [1.6, 1.6, 2.2, 2.2, 1.3, 0.6]})
        norm = closes / closes.iloc[0] * 100
        for k, t in enumerate(["069500", "229200", "133690", "148070", "132030", "261240"]):
            axes[0].plot(dts, norm[t], lw=0.9, color=CAT[k], label=self._lab(t))
        axes[0].set_title("가격 (창 첫날 = 100, 대표 6종)", loc="left", fontsize=10)
        axes[0].legend(fontsize=7, ncol=3)
        for t in self.tickers:
            d = e20[e20["ticker"] == t]
            axes[1].plot(d["date"], d["sigma_adj"], lw=0.6, color=MUTED)
        top = e20.groupby("ticker")["U_A"].max().sort_values().index[-3:]
        for k, t in enumerate(top):
            d = e20[e20["ticker"] == t]
            axes[1].plot(d["date"], d["sigma_adj"], lw=1.1, color=CAT[k], label=self._lab(t))
        axes[1].set_title("20일 연환산 σ_adj (%, 회색 = 20종, 색 = 창 내 U_A 최대 3종)", loc="left", fontsize=10)
        axes[1].legend(fontsize=7)
        mat_u = _pivot(e20, "U_A", self.tickers, "ticker", dts)
        _state_image(axes[2], mat_u, dts, [self._lab(t) for t in self.tickers], cmap=SEQ, vmin=0, vmax=1)
        axes[2].set_title("U_A 과거 분위 (진할수록 높음, A = 0.90 이상)", loc="left", fontsize=10)
        e20d = e20.copy()
        e20d["dir"] = np.where(e20d["B_UP"] == 1, 1.0, np.where(e20d["B_DOWN"] == 1, -1.0, np.where(e20d["B"].notna(), 0.0, np.nan)))
        _state_image(axes[3], _pivot(e20d, "dir", self.tickers, "ticker", dts), dts, [self._lab(t) for t in self.tickers],
                     cmap=ListedColormap([DOWN, "#f0efec", UP]), vmin=-1, vmax=1)
        axes[3].set_title("B 방향 (빨강 B↑, 파랑 B↓)", loc="left", fontsize=10)
        cd = pd.read_csv(self.root / "research/multihorizon_w2/results/06/cross_daily_counts.csv", parse_dates=["date"])
        for q, c in ((20, CAT[0]), (60, CAT[1])):
            g = self.gl[(self.gl["q"] == q) & (self.gl["date"] >= s) & (self.gl["date"] <= en)]
            axes[4].plot(g["date"], g["n_A"], color=c, lw=1.1, label=f"W4 A 그룹 수 q{q}")
            axes[4].plot(g["date"], g["n_AB"], color=c, lw=1.1, ls=":", label=f"W4 AB 그룹 수 q{q}")
        for ch, c in (("HIGH_LEVEL", CAT[5]), ("EXPANSION", CAT[4])):
            w = cd[(cd["channel"] == ch) & (cd["date"] >= s) & (cd["date"] <= en)]
            axes[4].plot(w["date"], w["n_group"], color=c, lw=1, ls="--", label=f"W2 {ch} 후보 그룹 수 (q 3–120 중 3개 이상 겹친 ETF 의 그룹)")
        axes[4].axhline(17, color=INK, lw=0.8, ls="--")
        axes[4].set_ylim(0, 18)
        axes[4].legend(fontsize=7, ncol=3)
        axes[4].set_title("그룹 참여 수: W4 (실선 A, 점선 AB) vs W2 교차 일별 그룹 수", loc="left", fontsize=10)
        f = self.fin[(self.fin["date"] >= s) & (self.fin["date"] <= en)]
        _state_image(axes[5], f[["FINAL_SHOCK"]].T.to_numpy(float), dts, ["FINAL"])
        for ax in axes[:2]:
            style(ax)
        for ax in (axes[0], axes[1], axes[4]):
            ax.set_xlim(dts[0], dts[-1])
            ax.xaxis.set_major_locator(mdates.MonthLocator())
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%y-%m"))
            style(ax)
        for ax in (axes[2], axes[3], axes[5]):
            ax.xaxis.set_major_locator(mdates.MonthLocator())
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%y-%m"))
        cases = pd.read_csv(self.root / "research/peer_relative_shock_w4/results/event_case_studies.csv")
        gc = cases[(cases["event"] == ev) & (cases["level"] == "global")].set_index("q")
        cap = {f"q{q}": {"max_n_A": int(gc.loc[q, "max_n_A"]), "max_n_B": int(gc.loc[q, "max_n_B"]), "max_n_AB": int(gc.loc[q, "max_n_AB"]),
                         "max_n_A_date": gc.loc[q, "max_n_A_date"], "final_days": int(gc.loc[q, "final_days"])} for q in (20, 60)}
        fig.suptitle(f"F{num} · {title} — W4 최대 A {cap['q20']['max_n_A']}/17 (q20, {cap['q20']['max_n_A_date']}), B {cap['q20']['max_n_B']}, AB {cap['q20']['max_n_AB']} · FINAL {cap['q20']['final_days']}일", fontsize=11.5)
        footnote(fig, f"창 {s.date()} ~ {en.date()}. W2 참조: {self.cfg['events'][ev]['w2_ref']}. W2 는 mean(r²) 기반·KOSPI200 은 구성원 하나라도(OR)·3그룹 이상 교차, W4 는 표본표준편차·Core Pair 둘 다(AND)·17/17·Peer 상대 괴리.")
        fig.tight_layout(rect=(0, 0.02, 1, 0.97))
        return self._save(fig, f"F{num}_event_{ev}", cap)

    def f31_w3(self) -> dict:
        w3 = self.root / "research/joint_cusum_w3/results/08"
        seq = pd.read_csv(w3 / "sequential_alarm_episodes.csv", dtype=str)
        je = pd.read_csv(w3 / "joint_episodes.csv", dtype=str)
        fig, axes = plt.subplots(2, 1, figsize=(14, 11), sharex=True, gridspec_kw={"height_ratios": [2.2, 2]})
        k = 0
        labels = []
        for _, x in seq.iterrows():
            axes[0].plot([pd.Timestamp(x["alarm_start"]), pd.Timestamp(x["alarm_end"]) + pd.Timedelta(days=2)], [k, k], color=CAT[6], lw=5)
            labels.append(f"개별 {x['ticker']} w{x['w']}")
            k += 1
        for _, x in je.iterrows():
            axes[0].plot([pd.Timestamp(x["episode_start_at"]), pd.Timestamp(x["episode_end_at"]) + pd.Timedelta(days=2)], [k, k], color=CAT[3], lw=5)
            labels.append(f"공동 {x['subset']}")
            k += 1
        axes[0].set_yticks(range(k))
        axes[0].set_yticklabels(labels, fontsize=6.5)
        axes[0].invert_yaxis()
        axes[0].set_title("W3 (노트북 08): 보라 = 개별 CUSUM 순차 경보 에피소드, 노랑 = 탐색적 공동 에피소드 (모두 NULL_MODEL_INVALID·비유의)", loc="left", fontsize=9.5)
        for q, c in ((20, CAT[0]), (60, CAT[1])):
            g = self.gl[self.gl["q"] == q]
            axes[1].plot(g["date"], g["n_A"], color=c, lw=0.7, label=f"W4 A 그룹 수 q{q}")
            axes[1].plot(g["date"], g["n_AB"], color=c, lw=0.7, ls=":", label=f"W4 AB 그룹 수 q{q}")
        axes[1].axhline(17, color=INK, ls="--", lw=0.8)
        axes[1].set_ylim(0, 18)
        axes[1].legend(fontsize=7, ncol=2)
        for ax in axes:
            _primary_band(ax)
            style(ax)
            _date_axis(ax)
        cmp_ = pd.read_csv(self.root / "research/peer_relative_shock_w4/results/comparison_w2_w3.csv")
        w3c = cmp_[cmp_["block"].str.startswith("w3_")]
        cap = {"w3_episodes": int(len(seq) + len(je)), "w4_max_n_AB_during_w3": int(w3c["w4_max_n_AB"].max()),
               "w4_final_days_during_w3": int(w3c["w4_final_days"].sum())}
        fig.suptitle(f"F31 · W3 CUSUM 경보·공동 에피소드 {cap['w3_episodes']}건 동안 W4 AB 그룹 수 최대 {cap['w4_max_n_AB_during_w3']} · FINAL {cap['w4_final_days_during_w3']}일", fontsize=11.5)
        footnote(fig, "W4 라벨은 W3 CUSUM 의 정답이 아니다. W3 비유의를 W4 부정 근거로 쓰지 않으며, W4 의 상태도 통계적 구조변화 증명이 아니다.")
        fig.tight_layout(rect=(0, 0.04, 1, 0.94))
        return self._save(fig, "F31_w3_comparison", cap)

    def f32_cases(self) -> dict:
        e = self._prim(self._e(20))
        cats = {"A 만 (자기 과거 고변동성, Peer 와 같이 움직임)": (e["A"] == 1) & (e["B"] == 0),
                "B↑ 만 (Peer 대비 상대 확대, 자기 과거 기준 평범)": (e["B_UP"] == 1) & (e["A"] == 0),
                "B↓ 만 (Peer 가 더 크게 움직임)": (e["B_DOWN"] == 1) & (e["A"] == 0),
                "AB (둘 다)": e["AB"] == 1}
        fig, axes = plt.subplots(4, 1, figsize=(14, 13))
        cap = {}
        allq = self._e(20)
        for ax, (lab, mask) in zip(axes, cats.items()):
            cnt = e[mask].groupby("ticker").size().sort_values()
            t = cnt.index[-1]
            dd = e[mask & (e["ticker"] == t)]["date"]
            # 해당 ETF 의 가장 긴 연속 구간 가운데 날을 중심으로 ±60 거래일
            pos = np.searchsorted(self.dates, pd.DatetimeIndex(dd))
            runs, start = [], pos[0]
            for a, b in zip(pos[:-1], pos[1:]):
                if b != a + 1:
                    runs.append((start, a))
                    start = b
            runs.append((start, pos[-1]))
            s0, s1 = max(runs, key=lambda r: r[1] - r[0])
            c = (s0 + s1) // 2
            lo, hi = max(c - 60, 0), min(c + 60, len(self.dates) - 1)
            d = allq[(allq["ticker"] == t) & (allq["date"] >= self.dates[lo]) & (allq["date"] <= self.dates[hi])]
            ax.plot(d["date"], d["sigma_adj"], color=CAT[0], lw=1, label=f"{self._lab(t)} σ_adj")
            ax.plot(d["date"], d["peer_median_adj"], color=MUTED, lw=1, label="Peer 중앙값")
            ax.axvspan(self.dates[s0], self.dates[s1], color=CAT[3], alpha=0.15, label=f"최장 연속 {s1 - s0 + 1}일")
            ax.set_title(f"{lab} — 가장 많은 ETF {t} ({int(cnt.iloc[-1])}일, 주분석 q=20)", loc="left", fontsize=10)
            ax.legend(fontsize=8)
            style(ax)
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%y-%m"))
            cap[lab] = {"ticker": t, "days": int(cnt.iloc[-1]), "longest_run": [str(self.dates[s0].date()), str(self.dates[s1].date())]}
        fig.suptitle("F32 · A·B·AB 정의가 실제로 가리키는 사례 차이", fontsize=12)
        footnote(fig, "사례 선택 규칙(사전 고정): 범주별 주분석 일수가 가장 많은 ETF, 그 ETF 의 최장 연속 구간 중심 ±60 거래일.")
        fig.tight_layout(rect=(0, 0.03, 1, 0.96))
        return self._save(fig, "F32_definition_cases", cap)

    def f33_eligibility(self) -> dict:
        z = pd.read_csv(self.root / "research/peer_relative_shock_w4/results/zero_volatility_audit.csv", dtype={"ticker": str})
        el = pd.read_csv(self.root / "research/peer_relative_shock_w4/results/eligibility_audit.csv")
        fig, axes = plt.subplots(1, 2, figsize=(16, 7.5), gridspec_kw={"width_ratios": [1.3, 1]})
        z20 = z[z["q"] == 20].set_index("ticker").loc[self.tickers]
        y = np.arange(len(self.tickers))
        left = np.zeros(len(y))
        for col, c in (("OK", CAT[0]), ("VOL_MISSING", NA_COLOR), ("ZERO_VOL_NUMERATOR", CAT[1]),
                       ("ZERO_VOL_DENOMINATOR", CAT[4]), ("PEER_INSUFFICIENT_ON_DATE", CAT[7])):
            axes[0].barh(y, z20[col], left=left, color=c, label=col)
            left += z20[col].to_numpy()
        axes[0].set_yticks(y)
        axes[0].set_yticklabels([self._lab(t) for t in self.tickers], fontsize=8)
        axes[0].set_xlabel("전체 1,903 거래일 중 L 상태 (q=20)")
        axes[0].legend(fontsize=7, loc="lower left", bbox_to_anchor=(0, 1.0), ncol=3, frameon=False)
        g = el[(el["group"] == "__FINAL__")]
        axes[1].bar(g["year"].astype(str), g["AB_evaluable"] / g["days"] * 100, color=CAT[0])
        for i, (a, d) in enumerate(zip(g["AB_evaluable"], g["days"])):
            axes[1].text(i, a / d * 100 + 1, f"{a}/{d}", ha="center", fontsize=8)
        axes[1].set_ylim(0, 110)
        axes[1].set_ylabel("FINAL 판정 가능 비율 (%)")
        axes[1].set_title("연도별 FINAL 판정 가능일", fontsize=10, loc="left")
        for ax in axes:
            style(ax)
        cap = {"zero_num_total": int(z["ZERO_VOL_NUMERATOR"].sum()), "zero_den_total": int(z["ZERO_VOL_DENOMINATOR"].sum()),
               "peer_insufficient_total": int(z["PEER_INSUFFICIENT_ON_DATE"].sum())}
        fig.suptitle(f"F33 · 데이터 적격성 — 영변동성 분자 {cap['zero_num_total']} · 분모 {cap['zero_den_total']} · Peer 부족 {cap['peer_insufficient_total']} (ETF-q-일)", fontsize=12)
        footnote(fig, "VOL_MISSING 은 대부분 첫 20일(창 미충족). Peer 부족 130 은 모두 2019 년 132030 (Peer 319640 관측 전). 2019 는 기준 축적 기간이라 판정 불가가 정상이다. Peer 부족으로 판정이 막힌 주분석일은 0.")
        fig.tight_layout(rect=(0, 0.04, 1, 0.94))
        return self._save(fig, "F33_eligibility", cap)

    def f34_summary(self) -> dict:
        gp = self._prim(self.gl)
        fig = plt.figure(figsize=(15, 8.5))
        ax = fig.add_axes((0.05, 0.12, 0.5, 0.75))
        ks = [1, 3, 5, 8, 12, 15, 16, 17]
        for k_, (st, c) in enumerate((("A", CAT[0]), ("B", CAT[1]), ("AB", CAT[6]))):
            vals = [int(((gp["q"] == 20) & (gp[f"n_{st}"] >= k)).sum() + 0) for k in ks]
            vals60 = [int(((gp["q"] == 60) & (gp[f"n_{st}"] >= k)).sum()) for k in ks]
            ax.plot(ks, vals, marker="o", color=c, label=f"{st} q20")
            ax.plot(ks, vals60, marker="s", ls="--", color=c, label=f"{st} q60")
        ax.set_yscale("symlog", linthresh=1)
        ax.set_xlabel("같은 날 충족 그룹 수 k 이상")
        ax.set_ylabel("주분석 일수 (1,225일 중, symlog)")
        ax.axvline(17, color=INK, ls="--", lw=1)
        ax.legend(fontsize=8, ncol=2)
        style(ax)
        v = self.m["verdict"]
        txt = (f"최종 판정: {v['verdict']}\n"
               f"· 주분석 1,225일, 판정 가능 {v['primary_evaluable_share']*100:.0f}% · 17 그룹 A·B 모두 평가 가능\n"
               f"· FINAL_SHOCK = 1: {v['primary_final_true_days']}일 → 급변 구간 0개\n"
               f"· 최대 참여: A 12/17 (q20, 2025-04) · B 7/17 · AB 3/17 (2024-08~09)\n"
               f"· 민감도 4종(504일 기준·A 0.95·B 2.5%·KOSPI 4종)도 모두 0일\n\n"
               "확정된 계산 사실\n· 이 정의(17/17 ∧ A ∧ 양방향 B)는 2019–2026 자료에서 한 번도 충족되지 않는다\n"
               "· A 만은 2020-03-16~04-06 (파일럿) q20 에서 17/17 을 16일 충족 — 그날 B 는 3–6/17\n\n"
               "검증되지 않은 해석\n· 0 이 '시장 급변이 없었다' 를 뜻하지 않는다 (B 는 상대 괴리라 공동 발생을 요구하기 어렵다)\n"
               "· 라벨이 없으므로 CNN 정답·예측 성능 주장 불가\n\n"
               "다음 연구 조건\n· 정의 변경은 새 계약(lock-2)으로만 · 독립 정답 정의 사전 등록")
        fig.text(0.6, 0.88, txt, fontsize=9.5, va="top", color=INK, linespacing=1.5)
        fig.suptitle("F34 · 통합 결과와 연구 한계 — k 이상 그룹 동시 충족 일수는 17 에 가까워질수록 0 으로 수렴", fontsize=12)
        footnote(fig, "15/17·16/17 등은 진단이다. 이 그림의 어떤 k 도 새 라벨이 아니다.")
        return self._save(fig, "F34_summary_limits", {"verdict": v["verdict"]})

    def make_all(self) -> dict:
        self.f_sigma_grid(20, "F01_sigma20_grid")
        self.f_sigma_grid(60, "F02_sigma60_grid")
        self.f03_level_vs_rank()
        self.f04_A_heatmap()
        self.f05_leverage_norm()
        self.f06_network()
        self.f07_ratio_grid()
        self.f08_UB_heat()
        self.f09_B_map()
        self.f10_kospi()
        self._own_vs_peer(["229200", "091230", "091170", "091180", "305540", "143860", "117680", "161510"],
                          "F11_domestic_peer", "F11 · 국내 업종·전략 ETF 의 자기 σ 와 Peer 중앙값 (q=20)")
        self._own_vs_peer(["133690", "219480", "192090", "148070", "153130", "132030", "261220", "261240"],
                          "F12_overseas_bond_cmd_fx_peer", "F12 · 해외 주식·채권·원자재·통화의 Peer 진단 (q=20)")
        for k, n in (("A", "13"), ("B", "14"), ("AB", "15")):
            self.f_group_timeline(k, n)
        for k, n in (("A", "16"), ("B", "17"), ("AB", "18")):
            self.f_count(k, n)
        self.f19_intersection()
        self.f20_horizons()
        for k, n in (("A", "21"), ("B", "22"), ("AB", "23")):
            self.f_global(k, n)
        self.f24_final()
        self.f25_durations()
        self.f26_bottleneck()
        self.f27_distribution()
        self.f_event("E2024_08", "28", "W2 2024-08 다자산 변동성 확대")
        self.f_event("E2025_04", "29", "W2 2025-04 다자산 변동성 확대")
        self.f_event("E2022_bond", "30", "W2 2022 채권 중심 고변동성")
        self.f31_w3()
        self.f32_cases()
        self.f33_eligibility()
        self.f34_summary()
        return self.caps


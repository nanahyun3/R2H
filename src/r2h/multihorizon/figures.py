# ruff: noqa: E501  — 한국어 그림 캡션·각주 문자열.
"""W2 그림 — 한글 라벨·단위·표본 수·연도 지위 표기. 글꼴 등록은 노트북 첫 셀이 한다.

팔레트: 범주 고정 순서(검증 통과 8색), 크기 = 단일 파랑 순차, 극성 = 파랑↔빨강 발산 + 회색 중간점.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

CAT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
CH_COLOR = {
    "HIGH_LEVEL": CAT[0],
    "EXPANSION": CAT[1],
    "LOW_LEVEL": CAT[2],
    "CONTRACTION": CAT[3],
    "DAILY_SHOCK": CAT[4],
}
CH_KO = {
    "HIGH_LEVEL": "고변동성 수준",
    "LOW_LEVEL": "저변동성 수준",
    "EXPANSION": "변동성 확대",
    "CONTRACTION": "변동성 축소",
    "DAILY_SHOCK": "일간 충격(q=1, 보조)",
}
CUSUM_COLOR = CAT[6]
YEAR_KO = {
    "PRIMARY": "주 해석(2021–25)",
    "PILOT": "2020 파일럿",
    "PARTIAL_NON_BLIND": "2026 부분·비블라인드",
    "REFERENCE_ONLY": "2019 기준",
}
SEQ = LinearSegmentedColormap.from_list(
    "seq_blue", ["#f0efec", "#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]
)
DIV = LinearSegmentedColormap.from_list("div_br", ["#104281", "#5598e7", "#f0efec", "#ec835a", "#b8302f"])
plt.rcParams["svg.hashsalt"] = "t14_multihorizon_w2"  # SVG 내부 id 를 결정적으로 고정
Q_COLORS = {
    3: "#86b6ef",
    7: "#6da7ec",
    14: "#5598e7",
    20: "#3987e5",
    30: "#256abf",
    60: "#184f95",
    120: "#0d366b",
}


def style(ax: plt.Axes) -> None:
    ax.grid(True, color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#c3c2b7")
    ax.tick_params(colors=INK2, labelsize=8)


def shade_years(ax: plt.Axes, start: str = "2020-01-01", end: str = "2026-12-31") -> None:
    """2020 파일럿·2026 부분 기간을 회색 띠로 구분."""
    ax.axvspan(pd.Timestamp("2020-01-01"), pd.Timestamp("2020-12-31"), color="#f0efec", zorder=0)
    ax.axvspan(pd.Timestamp("2026-01-01"), pd.Timestamp("2026-10-02"), color="#f0efec", zorder=0)


def footnote(fig: plt.Figure, text: str) -> None:
    fig.text(0.01, 0.005, text, fontsize=7, color=MUTED, ha="left", va="bottom", wrap=True)


def save(fig: plt.Figure, out: Path, name: str) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    paths = [out / f"{name}.png", out / f"{name}.svg"]
    fig.savefig(paths[0], dpi=320, bbox_inches="tight", metadata={"Software": None})
    fig.savefig(paths[1], bbox_inches="tight", metadata={"Date": None, "Creator": None})
    plt.close(fig)
    return paths


def three_panel(
    ticker: str,
    name: str,
    close: pd.Series,
    feat: pd.DataFrame,
    iv: pd.DataFrame,
    cus_alarm: pd.Series,
    out: Path,
    fig_no: str,
) -> list[Path]:
    """가격 · 일간 충격 · 기간별 실현 변동성 3단 패널 (고변동성 공통 구간 음영, CUSUM 경보 표시)."""
    fig, axes = plt.subplots(
        3, 1, figsize=(11, 7.6), sharex=True, gridspec_kw={"height_ratios": [1.2, 0.8, 1.4]}
    )
    hi = iv[iv.channel.eq("HIGH_LEVEL")]
    ex = iv[iv.channel.eq("EXPANSION")]
    for ax in axes:
        shade_years(ax)
        style(ax)
        for _, r in hi.iterrows():
            ax.axvspan(
                pd.Timestamp(r.interval_start),
                pd.Timestamp(r.interval_end),
                color=CH_COLOR["HIGH_LEVEL"],
                alpha=0.12,
                lw=0,
            )
    axes[0].plot(close.index, close.to_numpy(), color=INK, lw=1.0)
    axes[0].set_ylabel("종가 (원)", fontsize=9)
    al = cus_alarm[cus_alarm].index
    axes[0].scatter(
        al,
        close.reindex(al),
        s=9,
        color=CUSUM_COLOR,
        zorder=3,
        label="CUSUM 경보일 (정책 A·연간 임계값·공통일, 네 창 중 하나 이상)",
    )
    axes[0].legend(loc="upper left", fontsize=7, frameon=False)
    q1 = feat[feat.q.eq(1)].set_index("date")
    axes[1].bar(q1.index, q1.RV.to_numpy(), width=1.0, color="#86b6ef", lw=0)
    shock = q1.index[q1.U_V.to_numpy() >= 0.9]
    axes[1].scatter(
        shock,
        q1.RV.reindex(shock),
        s=5,
        color=CH_COLOR["DAILY_SHOCK"],
        zorder=3,
        label="일간 충격 신호 (과거 분위 ≥ 0.90)",
    )
    axes[1].set_ylabel("|r| (%/일)", fontsize=9)
    axes[1].legend(loc="upper left", fontsize=7, frameon=False)
    for q in (3, 20, 120):
        s = feat[feat.q.eq(q)].set_index("date").RV
        axes[2].plot(
            s.index, s.to_numpy(), color=Q_COLORS[q], lw=1.0 if q != 120 else 1.6, label=f"q={q} 거래일"
        )
    for _, r in ex.iterrows():
        axes[2].axvspan(
            pd.Timestamp(r.interval_start),
            pd.Timestamp(r.interval_end),
            ymin=0,
            ymax=0.05,
            color=CH_COLOR["EXPANSION"],
            lw=0,
        )
    axes[2].set_ylabel("실현 변동성 RV (%/일)", fontsize=9)
    axes[2].legend(loc="upper left", fontsize=7, frameon=False, ncol=3)
    axes[2].xaxis.set_major_locator(mdates.YearLocator())
    axes[2].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.suptitle(
        f"그림 {fig_no}. {name} ({ticker}) — 가격·일간 충격·기간별 실현 변동성",
        fontsize=12,
        x=0.01,
        ha="left",
    )
    footnote(
        fig,
        "파란 음영 = 고변동성 수준 공통 구간 (주 7개 q 중 ≥3 동시, 과거 분위 ≥0.90). 아래 주황 띠 = 변동성 확대 공통 구간. "
        "회색 띠 = 2020 파일럿·2026 부분(~10-02). 자료: FDR 종가(2019-01-02~2026-10-02), T12 cache, W1 임계값.",
    )
    fig.tight_layout(rect=(0, 0.03, 1, 0.97))
    return save(fig, out, f"fig{fig_no.replace('-', '_')}_{ticker}_three_panel")


def quantile_heatmaps(
    items: list[tuple[str, str, pd.DataFrame]], value: str, out: Path, fig_no: str, title: str
) -> list[Path]:
    """ETF 별 (q × 거래일) 과거 분위 히트맵. value='U_V' (순차) 또는 'U_D' (발산, 0.5 중심)."""
    fig, axes = plt.subplots(len(items), 1, figsize=(11, 1.7 * len(items) + 0.9), sharex=True)
    cmap = SEQ if value == "U_V" else DIV
    for ax, (ticker, name, feat) in zip(np.atleast_1d(axes), items, strict=True):
        qs = [1, 3, 7, 14, 20, 30, 60, 120] if value == "U_V" else [3, 7, 14, 20, 30, 60, 120]
        wide = feat.pivot(index="date", columns="q", values=value)[qs]
        dates = mdates.date2num(wide.index.to_pydatetime())
        im = ax.pcolormesh(
            np.append(dates, dates[-1] + 1),
            np.arange(len(qs) + 1),
            wide.T.to_numpy(),
            cmap=cmap,
            vmin=0,
            vmax=1,
            shading="flat",
            rasterized=True,
        )
        ax.set_yticks(np.arange(len(qs)) + 0.5, [str(q) for q in qs], fontsize=7)
        ax.set_ylabel(f"{name}\n({ticker})\nq", fontsize=8)
        ax.xaxis_date()
        ax.tick_params(colors=INK2, labelsize=8)
        for y in ("2020-12-31", "2025-12-31"):
            ax.axvline(pd.Timestamp(y), color=INK, lw=0.6, ls=(0, (2, 2)))
    cb = fig.colorbar(im, ax=axes, fraction=0.02, pad=0.01)
    cb.set_label(
        "과거 확장형 mid-rank 분위 (0–1)" + (" · 0.5=중앙, 파랑=축소, 빨강=확대" if value == "U_D" else ""),
        fontsize=8,
    )
    np.atleast_1d(axes)[0].set_title(f"그림 {fig_no}. {title}", fontsize=12, loc="left")
    footnote(
        fig,
        "회색(결측) = 과거 유효 비교값 252개 미만(NOT_ESTIMABLE) 또는 영분산. 점선 = 2020 파일럿 끝 / 2026 부분 시작. 기준분포는 평가일 이전 값만 사용.",
    )
    return save(fig, out, f"fig{fig_no.replace('-', '_')}_{value}_heatmap")


def episode_timeline(
    ticker: str,
    name: str,
    ep: pd.DataFrame,
    iv: pd.DataFrame,
    cus_alarm_w: dict[int, pd.Series],
    out: Path,
    fig_no: str,
    channels: tuple[str, ...] = ("HIGH_LEVEL", "EXPANSION"),
) -> list[Path]:
    """기간별 에피소드(행 = 채널×q) · 공통 구간 · CUSUM 창별 경보 시간축."""
    qs = [3, 7, 14, 20, 30, 60, 120]
    fig, ax = plt.subplots(figsize=(11, 6.4))
    style(ax)
    shade_years(ax)
    y, labels = 0, []
    for w in (120, 60, 30, 20):
        s = cus_alarm_w[w]
        d = s.index[s.to_numpy()]
        ax.scatter(d, np.full(d.size, y), marker="|", s=40, color=CUSUM_COLOR, lw=0.8)
        labels.append(f"CUSUM w={w}")
        y += 1
    for ch in channels:
        y += 0.5
        sub = iv[iv.channel.eq(ch)]
        for _, r in sub.iterrows():
            ax.barh(
                y,
                (pd.Timestamp(r.interval_end) - pd.Timestamp(r.interval_start)).days + 1,
                left=pd.Timestamp(r.interval_start),
                height=0.8,
                color=CH_COLOR[ch],
                edgecolor=INK,
                lw=0.4,
            )
        labels.append(f"{CH_KO[ch]} 공통 구간")
        y += 1
        for q in qs:
            e = ep[ep.channel.eq(ch) & ep.q.eq(q)]
            for _, r in e.iterrows():
                ax.barh(
                    y,
                    (pd.Timestamp(r.episode_end) - pd.Timestamp(r.episode_start)).days + 1,
                    left=pd.Timestamp(r.episode_start),
                    height=0.6,
                    color=CH_COLOR[ch],
                    alpha=0.55,
                    lw=0,
                )
            labels.append(f"{CH_KO[ch]} q={q}")
            y += 1
    pos = []
    k = 0
    for _ in (120, 60, 30, 20):
        pos.append(k)
        k += 1
    for _ in channels:
        k += 0.5
        pos.extend(k + np.arange(len(qs) + 1))
        k += len(qs) + 1
    ax.set_yticks(pos, labels, fontsize=7)
    ax.invert_yaxis()
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_title(
        f"그림 {fig_no}. {name} ({ticker}) — 기간별 에피소드·공통 구간·CUSUM 경보 시간축",
        fontsize=12,
        loc="left",
    )
    footnote(
        fig,
        "에피소드 = 연속 신호 거래일(비신호일 병합 없음). 공통 구간 = 같은 날 ≥3개 q 동시 반응한 연속일. CUSUM = 정책 A·W1 연간 임계값·공통일 "
        "(연초 t<119 와 연도 경계 구간은 NOT_AVAILABLE 로 표시 없음). 회색 띠 = 2020·2026.",
    )
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    return save(fig, out, f"fig{fig_no.replace('-', '_')}_{ticker}_timeline")


def case_zoom(cases: list[dict], out: Path, fig_no: str) -> list[Path]:
    """상위 공통 구간 사례: 구간 ±60 거래일의 종가(지수화)·RV(q)·중첩 수."""
    n = len(cases)
    fig, axes = plt.subplots(
        2, n, figsize=(3.6 * n, 5.6), sharex="col", gridspec_kw={"height_ratios": [1, 1]}
    )
    axes = np.atleast_2d(axes)
    for j, c in enumerate(cases):
        a0, a1 = axes[0, j], axes[1, j]
        for ax in (a0, a1):
            style(ax)
            ax.axvspan(c["start"], c["end"], color=CH_COLOR[c["channel"]], alpha=0.15, lw=0)
            if c["confirmed"] is not None:
                ax.axvline(c["confirmed"], color=INK2, lw=0.7, ls=(0, (2, 2)))
        px = c["close"]
        a0.plot(px.index, 100 * px / px.iloc[0], color=INK, lw=1.0)
        if len(c["alarms"]):
            a0.scatter(
                c["alarms"], 100 * px.reindex(c["alarms"]) / px.iloc[0], s=10, color=CUSUM_COLOR, zorder=3
            )
        a0.set_title(
            f"{c['name']} ({c['ticker']})\n{CH_KO[c['channel']]} · 순위 {c['rank']} · {YEAR_KO[c['year_status']]}",
            fontsize=8.5,
            loc="left",
        )
        for q, s in c["rv"].items():
            a1.plot(s.index, s.to_numpy(), color=Q_COLORS[q], lw=0.9, label=f"q={q}")
        a1.set_xlabel(f"최대 동시 {c['max_overlap']}/7 · {c['duration']}거래일", fontsize=8)
        a1.tick_params(axis="x", labelrotation=30)
        a1.xaxis.set_major_formatter(mdates.DateFormatter("%y-%m"))
    axes[0, 0].set_ylabel("종가 지수 (창 시작=100)", fontsize=8)
    axes[1, 0].set_ylabel("RV (%/일)", fontsize=8)
    axes[1, 0].legend(fontsize=6.5, frameon=False, ncol=2, loc="upper left")
    fig.suptitle(
        f"그림 {fig_no}. 대표 ETF 상위 공통 구간 사례 (구간 ±60 거래일)", fontsize=12, x=0.01, ha="left"
    )
    footnote(
        fig,
        "음영 = 공통 구간(시작~마지막 동시 반응일). 점선 = 종료 확인일(episode_confirmed_at). 보라 점 = CUSUM 경보일. "
        "순위 = (최대 동시 q 수, 지속일) 사전식, ETF×채널 범위, 공동 순위 min.",
    )
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    return save(fig, out, f"fig{fig_no.replace('-', '_')}_case_zoom")


def rv_cusum_relation(
    sp: pd.DataFrame,
    contrast: pd.DataFrame,
    ev: pd.DataFrame,
    out: Path,
    fig_no: str,
    core_years: tuple = (2021, 2022, 2023, 2024, 2025),
) -> list[Path]:
    """(가) ETF 중앙 Spearman ρ(U_V(q), T_w) 행렬 (나) 경보일/비경보일 U_V(q=w) 중앙값 (다) 경보 기준 사건 궤적."""
    fig = plt.figure(figsize=(14, 4.8))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.1, 1.35, 1.3])
    a, b, c = fig.add_subplot(gs[0]), fig.add_subplot(gs[1]), fig.add_subplot(gs[2])
    m = sp[sp.variable.eq("U_V")].groupby(["q", "w"]).spearman.median().unstack()
    im = a.imshow(m.to_numpy(), cmap=DIV, vmin=-1, vmax=1, aspect="auto")
    a.set_xticks(range(m.shape[1]), [f"w={w}" for w in m.columns], fontsize=8)
    a.set_yticks(range(m.shape[0]), [f"q={q}" for q in m.index], fontsize=8)
    for i in range(m.shape[0]):
        for j in range(m.shape[1]):
            a.text(j, i, f"{m.iat[i, j]:.2f}", ha="center", va="center", fontsize=7, color=INK)
    a.set_title("(가) ρ(U_V(q), T_w) — 20종 ETF 중앙값", fontsize=9, loc="left")
    fig.colorbar(im, ax=a, fraction=0.04)
    sub = contrast[contrast.q.eq(contrast.w)]
    ws = sorted(sub.w.unique())
    x = np.arange(len(ws))
    nlab = []
    for k, (state, col, lab) in enumerate(
        (("ALARM", CUSUM_COLOR, "경보일"), ("NO_ALARM", "#c3c2b7", "비경보일"))
    ):
        s = sub[sub.state.eq(state)].set_index("w").median_U_V.reindex(ws)
        b.bar(x + (k - 0.5) * 0.38, s.to_numpy(), width=0.36, color=col, label=lab)
        for xi, v in zip(x, s.to_numpy(), strict=True):
            b.text(xi + (k - 0.5) * 0.38, v + 0.015, f"{v:.2f}", ha="center", fontsize=7, color=INK2)
    for w in ws:
        na = int(sub[sub.state.eq("ALARM") & sub.w.eq(w)].n_days.iloc[0])
        nn = int(sub[sub.state.eq("NO_ALARM") & sub.w.eq(w)].n_days.iloc[0])
        nlab.append(f"w=q={w}\n경보 {na}\n비경보 {nn:,}")
    b.set_xticks(x, nlab, fontsize=6.5)
    b.set_xlabel("경보·비경보 아래 수 = 날짜 수 (ETF·날짜 합산)", fontsize=7, color=MUTED)
    b.set_ylim(0, 1.12)
    b.set_ylabel("U_V(q) 중앙값", fontsize=8)
    b.legend(fontsize=7, frameon=False, loc="upper left")
    b.set_title("(나) 경보일 대 비경보일 실현분산 분위", fontsize=9, loc="left")
    style(b)
    ev = ev[ev.year.isin(core_years)]
    for w, col in zip((20, 30, 60, 120), CAT[:4], strict=True):
        e = ev[ev.w.eq(w)].groupby("rel_day").U_V.mean()
        c.plot(
            e.index,
            e.to_numpy(),
            color=col,
            lw=1.2,
            label=f"w=q={w} (사건 {ev[ev.w.eq(w)].groupby(['ticker', 'alarm_at']).ngroups})",
        )
    c.axvline(0, color=INK2, lw=0.7, ls=(0, (2, 2)))
    c.axhline(0.5, color=MUTED, lw=0.6)
    c.set_xlabel("CUSUM 첫 경보일 기준 거래일", fontsize=8)
    c.set_ylabel("평균 U_V(q=w)", fontsize=8)
    c.legend(fontsize=7, frameon=False)
    c.set_title("(다) CUSUM 에피소드 첫 경보 전후 분위 궤적", fontsize=9, loc="left")
    style(c)
    fig.suptitle(
        f"그림 {fig_no}. 실현분산 특징과 W1 CUSUM 통계량의 관계 (정책 A, 2021–2025, 공통일)",
        fontsize=12,
        x=0.01,
        ha="left",
    )
    footnote(
        fig,
        "세 값 모두 같은 ETF 수익률에서 파생 — 관계의 강도는 CUSUM 의 독립 정확도 검증이 아니다. (나) 는 ETF·날짜를 합친 기술 통계(날짜 의존 무시). "
        "W1 검정창 비적격(0/4) 판정은 유지.",
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    return save(fig, out, f"fig{fig_no.replace('-', '_')}_rv_cusum")


def build_case(
    row: pd.Series, close: pd.Series, feat: pd.DataFrame, alarm_any: pd.Series, pad: int = 60
) -> dict:
    """공통 구간 한 행에서 사례 그림 입력(구간 ±pad 거래일)을 만든다."""
    idx = close.index
    s = idx.get_loc(pd.Timestamp(row.interval_start))
    e = idx.get_loc(pd.Timestamp(row.interval_end))
    win = idx[max(0, s - pad) : min(len(idx), e + pad + 1)]
    rv = {q: feat[feat.q.eq(q)].set_index("date").RV.reindex(win) for q in (3, 20, 120)}
    al = alarm_any.reindex(win).fillna(False)
    conf = None if row.episode_confirmed_at == "RIGHT_CENSORED" else pd.Timestamp(row.episode_confirmed_at)
    return {
        "ticker": row.ticker,
        "name": row["name"],
        "channel": row.channel,
        "rank": int(row.rank_in_etf_channel),
        "year_status": row.year_status,
        "start": pd.Timestamp(row.interval_start),
        "end": pd.Timestamp(row.interval_end),
        "confirmed": conf,
        "close": close.reindex(win),
        "alarms": win[al.to_numpy(bool)],
        "rv": rv,
        "max_overlap": int(row.max_overlap_count),
        "duration": int(row.duration_trading_days),
    }


def etf_day_heatmap(overlap: pd.DataFrame, expo: pd.DataFrame, out: Path, fig_no: str) -> list[Path]:
    """ETF × 거래일 동시 반응 q 수 (0–7) 히트맵 — 확대·고변동성 두 채널, 행은 자산유형·노출 그룹 순."""
    order = expo.sort_values(["category", "exposure_group", "ticker"])
    fig, axes = plt.subplots(2, 1, figsize=(11, 9.2), sharex=True)
    for ax, ch in zip(axes, ("EXPANSION", "HIGH_LEVEL"), strict=True):
        w = (
            overlap[overlap.channel.eq(ch)]
            .pivot(index="ticker", columns="date", values="overlap_count")
            .reindex(order.ticker)
        )
        w = w.loc[:, w.columns >= pd.Timestamp("2020-01-01")]
        dates = mdates.date2num(pd.DatetimeIndex(w.columns).to_pydatetime())
        im = ax.pcolormesh(
            np.append(dates, dates[-1] + 1),
            np.arange(len(w) + 1),
            w.to_numpy(),
            cmap=SEQ,
            vmin=0,
            vmax=7,
            shading="flat",
            rasterized=True,
        )
        ax.set_yticks(
            np.arange(len(w)) + 0.5,
            [f"{n} ({t})" for t, n in zip(order.ticker, order.name, strict=True)],
            fontsize=6.5,
        )
        ax.invert_yaxis()
        ax.xaxis_date()
        ax.set_title(f"{CH_KO[ch]} — 같은 날 반응한 주 q 수 (≥3 = 후보일)", fontsize=10, loc="left")
        for y in ("2020-12-31", "2025-12-31"):
            ax.axvline(pd.Timestamp(y), color=INK, lw=0.6, ls=(0, (2, 2)))
        ax.tick_params(colors=INK2, labelsize=8)
    cb = fig.colorbar(im, ax=axes, fraction=0.02, pad=0.01)
    cb.set_label("동시 반응 q 수 (0–7)", fontsize=8)
    fig.suptitle(
        f"그림 {fig_no}. ETF × 거래일 변동성 국면 히트맵 (20종, 2020–2026)", fontsize=12, x=0.01, ha="left"
    )
    footnote(
        fig,
        "행 순서 = 자산유형 → 노출 그룹. 점선 = 2020 파일럿 끝 / 2026 부분 시작. 05 의 일별 중첩 수(확장형 mid-rank 분위 10%, q=3–120).",
    )
    return save(fig, out, f"fig{fig_no.replace('-', '_')}_etf_day_heatmap")


def group_count_timeline(
    daily: pd.DataFrame, cross: pd.DataFrame, out: Path, fig_no: str, n_groups: int
) -> list[Path]:
    """채널별 동시 후보 노출 그룹 수·ETF 수 시계열과 그룹 기준 교차 공통 구간 (≥3 그룹)."""
    fig, axes = plt.subplots(4, 1, figsize=(11, 8.4), sharex=True)
    for ax, ch in zip(axes, ("HIGH_LEVEL", "EXPANSION", "LOW_LEVEL", "CONTRACTION"), strict=True):
        style(ax)
        shade_years(ax)
        d = daily[daily.channel.eq(ch)].set_index("date")
        d = d[d.index >= pd.Timestamp("2020-01-01")]
        ax.plot(d.index, d.n_etf.to_numpy(), color="#c3c2b7", lw=0.8, label="후보 ETF 수 (20종 기준)")
        ax.plot(
            d.index,
            d.n_group.to_numpy(),
            color=CH_COLOR[ch],
            lw=1.0,
            label=f"후보 노출 그룹 수 ({n_groups}개 기준)",
        )
        ax.axhline(3, color=INK2, lw=0.6, ls=(0, (2, 2)))
        for r in cross[cross.channel.eq(ch)].itertuples(index=False):
            ax.axvspan(
                pd.Timestamp(r.interval_start),
                pd.Timestamp(r.interval_end) + pd.Timedelta(days=1),
                ymin=0.94,
                ymax=1.0,
                color=CH_COLOR[ch],
                lw=0,
            )
        ax.set_ylabel(CH_KO[ch], fontsize=8)
        ax.set_ylim(0, 24.5)
        ax.set_yticks([0, 5, 10, 15, 20])
        ax.legend(loc="upper right", bbox_to_anchor=(1.0, 0.9), fontsize=7, frameon=False, ncol=2)
    axes[-1].xaxis.set_major_locator(mdates.YearLocator())
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.suptitle(
        f"그림 {fig_no}. 노출 군집별 공통 구간 시간축 — 같은 날 후보인 노출 그룹 수",
        fontsize=12,
        x=0.01,
        ha="left",
    )
    footnote(
        fig,
        "노출 그룹: KOSPI200 동일노출 4종을 1개로, 나머지 16종은 각각 1개 (17개). 점선 = 교차 공통 기준 3. 위쪽 띠 = 그룹 기준 교차 공통 구간. "
        "회색 띠 = 2020·2026. 군집 동시성의 유의성은 보정하지 않았다(탐색적).",
    )
    fig.tight_layout(rect=(0, 0.03, 1, 0.96))
    return save(fig, out, f"fig{fig_no.replace('-', '_')}_group_timeline")


def kospi200_case(
    overlap: pd.DataFrame,
    jac: pd.DataFrame,
    names: dict,
    members: list[str],
    windows: list[tuple[str, str]],
    out: Path,
    fig_no: str,
    channel: str = "EXPANSION",
) -> list[Path]:
    """KOSPI200 동일 노출 4종: 사건 창의 일별 동시 반응 q 수와 2021–2025 후보일 Jaccard 행렬."""
    fig = plt.figure(figsize=(12, 4.6))
    gs = fig.add_gridspec(1, len(windows) + 1, width_ratios=[1.4] * len(windows) + [1])
    for k, (a, b) in enumerate(windows):
        ax = fig.add_subplot(gs[k])
        style(ax)
        for j, t in enumerate(members):
            s = (
                overlap[overlap.ticker.eq(t) & overlap.channel.eq(channel)]
                .set_index("date")
                .overlap_count.loc[a:b]
            )
            ax.step(
                s.index,
                s.to_numpy() + (j - 1.5) * 0.08,
                where="mid",
                color=CAT[j],
                lw=1.1,
                label=f"{names[t]} ({t})",
            )
        ax.axhline(3, color=INK2, lw=0.6, ls=(0, (2, 2)))
        ax.set_ylim(-0.4, 7.6)
        ax.set_title(f"{a} ~ {b}", fontsize=9, loc="left")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%y-%m-%d"))
        ax.tick_params(axis="x", labelrotation=30)
        if k == 0:
            ax.set_ylabel(f"{CH_KO[channel]} 동시 반응 q 수", fontsize=8)
            ax.legend(fontsize=6.5, frameon=False, loc="upper right")
    ax = fig.add_subplot(gs[-1])
    m = pd.DataFrame(np.eye(len(members)), index=members, columns=members)
    sub = jac[jac.channel.eq(channel)]
    for r in sub.itertuples(index=False):
        m.loc[r.ticker_a, r.ticker_b] = m.loc[r.ticker_b, r.ticker_a] = r.jaccard
    ax.imshow(m.to_numpy(), cmap=SEQ, vmin=0, vmax=1)
    ax.set_xticks(range(len(members)), members, fontsize=7, rotation=30)
    ax.set_yticks(range(len(members)), members, fontsize=7)
    for i in range(len(members)):
        for j in range(len(members)):
            ax.text(
                j,
                i,
                f"{m.iat[i, j]:.2f}",
                ha="center",
                va="center",
                fontsize=7,
                color="#f0efec" if m.iat[i, j] > 0.6 else INK,
            )
    ax.set_title("2021–2025 후보일 Jaccard", fontsize=9, loc="left")
    fig.suptitle(
        f"그림 {fig_no}. KOSPI200 동일 노출 4종 — {CH_KO[channel]} 신호의 동시성",
        fontsize=12,
        x=0.01,
        ha="left",
    )
    footnote(
        fig,
        "선은 겹침을 피하려 세로로 0.08 씩 어긋나게 그렸다. 114800(인버스, −1배)·122630(레버리지, 2배)도 분산 채널에서는 방향과 무관하게 같은 날 반응한다. "
        "동일 지수 상품의 동시 반응은 독립 반복이 아니다.",
    )
    fig.tight_layout(rect=(0, 0.05, 1, 0.94))
    return save(fig, out, f"fig{fig_no.replace('-', '_')}_kospi200_case")


def yearly_bars(yearly: pd.DataFrame, out: Path, fig_no: str) -> list[Path]:
    """연도별 후보일 비율: ETF 등가중 대 노출 그룹 등가중, 채널별 작은 그림."""
    fig, axes = plt.subplots(1, 4, figsize=(12, 3.8), sharey=True)
    for ax, ch in zip(axes, ("HIGH_LEVEL", "EXPANSION", "LOW_LEVEL", "CONTRACTION"), strict=True):
        style(ax)
        d = yearly[yearly.channel.eq(ch) & yearly.year.ge(2020)].sort_values("year")
        x = np.arange(len(d))
        ax.bar(x - 0.2, d.etf_equal_share.to_numpy(), width=0.38, color="#c3c2b7", label="ETF 등가중 (20종)")
        ax.bar(
            x + 0.2,
            d.group_equal_share.to_numpy(),
            width=0.38,
            color=CH_COLOR[ch],
            label="노출 그룹 등가중 (17개)",
        )
        ax.set_xticks(x, [f"{y}{'*' if y in (2020, 2026) else ''}" for y in d.year], fontsize=7)
        ax.set_title(CH_KO[ch], fontsize=9, loc="left")
        ax.legend(fontsize=6.5, frameon=False, loc="upper left")
    axes[0].set_ylabel("후보일 비율 (그 해 거래일 중)", fontsize=8)
    fig.suptitle(
        f"그림 {fig_no}. 연도별 공통 국면 분포 — 종목 기준과 노출 그룹 기준", fontsize=12, x=0.01, ha="left"
    )
    footnote(
        fig,
        "* 2020 = 파일럿, 2026 = 1–10/2 부분·비블라인드. 그룹 등가중: 그룹 안 1종 이상이 후보일이면 그 그룹의 후보일. 2019 는 기준분포 축적 기간이라 제외.",
    )
    fig.tight_layout(rect=(0, 0.05, 1, 0.93))
    return save(fig, out, f"fig{fig_no.replace('-', '_')}_yearly")


def rank_basis_compare(cross_e: pd.DataFrame, out: Path, fig_no: str, top: int = 12) -> list[Path]:
    """ETF 수 기준 상위 교차 구간에서 최대 ETF 수와 최대 노출 그룹 수를 나란히 — 동일 지수 중복이 순위를 얼마나 부풀리는가."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.2))
    for ax, ch in zip(axes, ("HIGH_LEVEL", "EXPANSION"), strict=True):
        style(ax)
        d = (
            cross_e[cross_e.channel.eq(ch)]
            .sort_values(["rank_in_channel", "interval_start"])
            .head(top)
            .iloc[::-1]
        )
        y = np.arange(len(d))
        for yi, (a, b) in enumerate(zip(d.max_n_group, d.max_n_etf, strict=True)):
            ax.plot([a, b], [yi, yi], color="#c3c2b7", lw=1.5, zorder=1)
        ax.scatter(d.max_n_etf, y, s=36, color="#898781", zorder=2, label="최대 후보 ETF 수")
        ax.scatter(d.max_n_group, y, s=36, color=CH_COLOR[ch], zorder=3, label="최대 후보 노출 그룹 수")
        lab = [
            f"{s} ~ {e} ({n}일){' · 2026' if ys == 'PARTIAL_NON_BLIND' else (' · 2020' if ys == 'PILOT' else '')}"
            for s, e, n, ys in zip(
                d.interval_start, d.interval_end, d.duration_trading_days, d.year_status, strict=True
            )
        ]
        ax.set_yticks(y, lab, fontsize=7)
        ax.set_xlim(0, 21)
        ax.set_xlabel("수", fontsize=8)
        ax.set_title(f"{CH_KO[ch]} — ETF 수 기준 상위 {top} 교차 구간", fontsize=9, loc="left")
        ax.legend(fontsize=7, frameon=False, loc="lower right")
    fig.suptitle(
        f"그림 {fig_no}. 종목 기준과 노출 그룹 기준의 차이 — 같은 구간의 최대 ETF 수 대 최대 노출 그룹 수",
        fontsize=12,
        x=0.01,
        ha="left",
    )
    footnote(
        fig,
        "순위 = (최대 후보 ETF 수, 지속일) 사전식. 두 점 사이 거리 = KOSPI200 동일 노출 4종이 함께 후보여서 생긴 중복 집계(최대 3).",
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    return save(fig, out, f"fig{fig_no.replace('-', '_')}_rank_basis")


CH4 = ("HIGH_LEVEL", "EXPANSION", "LOW_LEVEL", "CONTRACTION")


def reaction_boxes(react: pd.DataFrame, uncond: dict, out: Path, fig_no: str) -> list[Path]:
    """공통 구간의 사전 20일 · 구간 중 · 사후 20일 누적 로그수익률 분포 (2021–2025 시작 구간)."""
    d = react[react.year_status.eq("PRIMARY")]
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.4), sharey=False)
    for ax, (col, title) in zip(
        axes,
        (
            ("pre_C_h20", "사전 20일 (시작 전날까지)"),
            ("during_C", "구간 중 (시작 전날 종가 → 끝 종가)"),
            ("post_R_h20", "사후 20일 (끝 다음날부터, 사후 결과)"),
        ),
        strict=True,
    ):
        style(ax)
        data = [d[d.channel.eq(ch)][col].dropna().to_numpy() for ch in CH4]
        bp = ax.boxplot(
            data, widths=0.55, showfliers=False, patch_artist=True, medianprops={"color": INK, "lw": 1.2}
        )
        for patch, ch in zip(bp["boxes"], CH4, strict=True):
            patch.set_facecolor(CH_COLOR[ch])
            patch.set_alpha(0.55)
            patch.set_edgecolor(INK2)
        ax.axhline(0, color=MUTED, lw=0.6)
        if col != "during_C":
            ax.axhline(uncond[20], color=INK2, lw=0.8, ls=(0, (3, 2)))
        ax.set_xticks(
            range(1, 5), [f"{CH_KO[c]}\nn={len(x)}" for c, x in zip(CH4, data, strict=True)], fontsize=7
        )
        ax.set_title(title, fontsize=9, loc="left")
    axes[0].set_ylabel("누적 로그수익률 (%)", fontsize=8)
    fig.suptitle(
        f"그림 {fig_no}. 변동성 국면 공통 구간의 가격 반응 (2021–2025 시작 구간, 20종 합산)",
        fontsize=12,
        x=0.01,
        ha="left",
    )
    footnote(
        fig,
        f"점선 = 2021–25 전 ETF·전 거래일 20일 누적수익률 중앙값 {uncond[20]:.2f}%. 상자 = 사분위, 수염 = 1.5 IQR, 이상치 생략. 구간들은 ETF·날짜가 겹쳐 독립 표본이 아니다 — 기술 통계. 사후 20일은 끝+20 거래일 종가 이후에만 알 수 있다.",
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.93))
    return save(fig, out, f"fig{fig_no.replace('-', '_')}_reaction_boxes")


def path_figure(path_mean: pd.DataFrame, out: Path, fig_no: str) -> list[Path]:
    """구간 시작 전후 ±60 거래일 누적 로그수익률 평균 경로 (절대·나머지 19종 대비)."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4), sharex=True)
    for ax, (col, title) in zip(
        axes,
        (("path", "누적 로그수익률 (시작 전날 종가 = 0)"), ("path_rel", "같은 날 나머지 19종 중앙값 대비")),
        strict=True,
    ):
        style(ax)
        for ch in CH4:
            s = path_mean.loc[ch][(col, "mean")]
            n = int(path_mean.loc[ch][(col, "count")].iloc[0])
            ax.plot(s.index, s.to_numpy(), color=CH_COLOR[ch], lw=1.4, label=f"{CH_KO[ch]} (구간 {n})")
        ax.axvline(0, color=INK2, lw=0.7, ls=(0, (2, 2)))
        ax.axhline(0, color=MUTED, lw=0.6)
        ax.set_title(title, fontsize=9, loc="left")
        ax.set_xlabel("공통 구간 시작일 기준 거래일", fontsize=8)
    axes[0].set_ylabel("평균 (%)", fontsize=8)
    axes[0].legend(fontsize=7, frameon=False, loc="upper left")
    fig.suptitle(
        f"그림 {fig_no}. 변동성 국면 전후 가격 궤적 (2021–2025 시작 구간 평균)",
        fontsize=12,
        x=0.01,
        ha="left",
    )
    footnote(
        fig,
        "시작일 이후 구간은 사후에 알 수 있는 경로다. 구간 길이가 달라 +k 일 경로에는 구간 안·밖 날짜가 섞인다. 평균은 소수 극단 구간에 민감하다 (중앙값은 결과표).",
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.93))
    return save(fig, out, f"fig{fig_no.replace('-', '_')}_paths")


def tracking_figure(
    rel: pd.DataFrame, hi_iv: pd.DataFrame, names: dict, out: Path, fig_no: str
) -> list[Path]:
    """KOSPI200 동일 노출: 명목 배수 조정 후 069500 대비 20일 누적 차이 (C_i − m_i·C_069500) 시계열."""
    fig, ax = plt.subplots(figsize=(11, 4.4))
    style(ax)
    shade_years(ax)
    for r in hi_iv.itertuples(index=False):
        ax.axvspan(
            pd.Timestamp(r.interval_start),
            pd.Timestamp(r.interval_end),
            color=CH_COLOR["HIGH_LEVEL"],
            alpha=0.12,
            lw=0,
        )
    for t, col, m in (("102110", CAT[1], "+1"), ("122630", CAT[2], "+2"), ("114800", CAT[3], "−1")):
        s = rel[rel.ticker.eq(t) & rel.h.eq(20)].set_index("date").rel_same_exposure
        s = s[s.index >= pd.Timestamp("2020-01-01")]
        ax.plot(s.index, s.to_numpy(), color=col, lw=0.9, label=f"{names[t]} ({t}) − ({m})×KODEX 200")
    ax.axhline(0, color=MUTED, lw=0.6)
    ax.set_ylabel("20일 누적 로그수익률 차이 (%p)", fontsize=8)
    ax.legend(fontsize=7, frameon=False, loc="lower left")
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_title(
        f"그림 {fig_no}. 동일 지수 ETF 의 추적 차이 — KOSPI200 노출 4종 (명목 배수 조정, h=20)",
        fontsize=12,
        loc="left",
    )
    footnote(
        fig,
        "파란 음영 = KODEX 200 고변동성 공통 구간. 배수는 상품 명목값(추정 아님). 일일 재조정 상품의 h 일 로그수익률은 m×기초와 같지 않다 — 차이는 '변동성 손실'·보수·괴리를 함께 담는다. 회색 띠 = 2020·2026.",
    )
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    return save(fig, out, f"fig{fig_no.replace('-', '_')}_tracking")


def regime_relative_figure(tab: pd.DataFrame, out: Path, fig_no: str) -> list[Path]:
    """채널별 후보일 대 비후보일: 과거 20일 상대 움직임 4종의 중앙값."""
    measures = [
        ("median_rel_simple", "단순 차이\n(나머지 19종 중앙값 대비, %p)"),
        ("median_rel_std", "표준화 차이\n(Z_A 기준)"),
        ("median_rel_exposure_adj", "노출 조정 차이\n(÷명목 배수, %p)"),
        ("median_rel_cross_asset", "다른 자산유형 대비\n(%p)"),
    ]
    fig, axes = plt.subplots(1, 4, figsize=(12, 3.9))
    for ax, (col, title) in zip(axes, measures, strict=True):
        style(ax)
        x = np.arange(len(CH4))
        for k, (flag, alpha, lab) in enumerate(((False, 0.35, "비후보일"), (True, 1.0, "후보일 (≥3 q)"))):
            v = [
                float(tab[(tab.channel == ch) & (tab.overlap_candidate_day == flag)][col].iloc[0])
                for ch in CH4
            ]
            ax.bar(
                x + (k - 0.5) * 0.38, v, width=0.36, color=[CH_COLOR[c] for c in CH4], alpha=alpha, label=lab
            )
        ax.axhline(0, color=MUTED, lw=0.6)
        ax.set_xticks(x, [CH_KO[c].replace(" ", "\n", 1) for c in CH4], fontsize=6.5)
        ax.set_title(title, fontsize=8.5, loc="left")
    axes[0].legend(fontsize=7, frameon=False, loc="upper left")
    fig.suptitle(
        f"그림 {fig_no}. 변동성 국면별 같은 날짜 ETF 상대 움직임 (과거 20일, 2021–2025, ETF·날짜 합산 중앙값)",
        fontsize=12,
        x=0.01,
        ha="left",
    )
    footnote(
        fig,
        "진한 막대 = 그 채널의 후보일, 옅은 막대 = 비후보일. 경제적 노출이 다른 ETF 간 단순 차이는 우열·위험조정 성과가 아니다.",
    )
    fig.tight_layout(rect=(0, 0.05, 1, 0.92))
    return save(fig, out, f"fig{fig_no.replace('-', '_')}_regime_relative")


def cusum_price_figure(summary: pd.DataFrame, lags: pd.Series, out: Path, fig_no: str) -> list[Path]:
    """(가) CUSUM 첫 경보일 대 비경보일의 과거 20일 수익률 중앙값 (나) 공통 구간 시작 → 구간 안 첫 경보 시차."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2), gridspec_kw={"width_ratios": [1.2, 1]})
    a, b = axes
    style(a)
    ws = [20, 30, 60, 120]
    x = np.arange(len(ws))
    for k, (grp, col, lab) in enumerate(
        (("first_alarm", CUSUM_COLOR, "에피소드 첫 경보일"), ("no_alarm", "#c3c2b7", "비경보 공통일"))
    ):
        s = summary[summary.group.eq(grp)].set_index("w").reindex(ws)
        a.bar(x + (k - 0.5) * 0.38, s.median_C20.to_numpy(), width=0.36, color=col, label=lab)
        for xi, (v, n) in enumerate(zip(s.median_C20, s.n, strict=True)):
            a.text(
                xi + (k - 0.5) * 0.38,
                v + 0.15 if v >= 0 else v - 0.6,
                f"{v:.2f}\nn={int(n):,}",
                ha="center",
                fontsize=6.5,
                color=INK2,
            )
    a.axhline(0, color=MUTED, lw=0.6)
    a.set_ylim(top=float(summary.median_C20.max()) * 1.25)
    a.set_xticks(x, [f"w={w}" for w in ws], fontsize=8)
    a.set_ylabel("과거 20일 누적 로그수익률 중앙값 (%)", fontsize=8)
    a.legend(fontsize=7, frameon=False, loc="upper right")
    a.set_title("(가) 경보 시점의 직전 가격 움직임 (2021–2025)", fontsize=9, loc="left")
    style(b)
    if len(lags):
        b.hist(
            lags.to_numpy(),
            bins=np.arange(-0.5, lags.max() + 1.5, 1),
            color=CUSUM_COLOR,
            alpha=0.8,
            rwidth=0.85,
        )
    b.set_xlabel("공통 구간 시작 → 구간 안 첫 CUSUM 경보 (거래일)", fontsize=8)
    b.set_ylabel("구간 수", fontsize=8)
    b.set_title(f"(나) 시차 분포 (경보가 겹친 2021–25 구간 {len(lags)}개)", fontsize=9, loc="left")
    fig.suptitle(
        f"그림 {fig_no}. CUSUM 경보와 가격 움직임의 시간적 관계 (정책 A·W1 연간 임계값·공통일)",
        fontsize=12,
        x=0.01,
        ha="left",
    )
    footnote(
        fig,
        "w=20 은 첫 경보 2건뿐이라 해석하지 않는다. 시차는 사후 구간 시작일 기준이며, 구간 시작일 자체가 실시간 경보 시점이 아니다.",
    )
    fig.tight_layout(rect=(0, 0.05, 1, 0.92))
    return save(fig, out, f"fig{fig_no.replace('-', '_')}_cusum_price")

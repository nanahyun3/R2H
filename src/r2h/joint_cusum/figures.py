# ruff: noqa: E501  — 한국어 그림 캡션·각주 문자열.
"""W3 그림 08-1 ~ 08-9. 한글 라벨·단위·정책·창·판정 상태·계산 불능 구분. 글꼴 등록은 노트북 첫 셀이 한다.

팔레트는 W2 와 같은 범주 고정 순서(검증 통과 8색)를 ETF 고정 색으로 쓴다. 유의성 판정은 원시 점수와 다른 패널에 둔다.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from r2h.multihorizon.figures import CAT, GRID, INK, INK2, MUTED, footnote, style

plt.rcParams["svg.hashsalt"] = "t15_joint_cusum_w3"  # SVG 내부 id 를 결정적으로 고정
TICKER_COLOR = {
    "069500": CAT[0],
    "229200": CAT[1],
    "148070": CAT[2],
    "153130": CAT[3],
    "133690": CAT[6],
    "261220": CAT[7],
}
W_COLOR = {20: "#86b6ef", 30: "#3987e5", 60: "#1c5cab", 120: "#0d366b"}
STATUS_KO = {
    "SIGNIFICANT_H0B": "H0-B 유의",
    "SIGNIFICANT_H0A_ONLY": "H0-A 만 유의",
    "EXPLORATORY": "탐색",
    "NOT_SIGNIFICANT": "비유의",
    "NOT_ESTIMABLE": "추정 불가",
    "NULL_MODEL_INVALID": "귀무 부적합",
    "INSUFFICIENT_MONTE_CARLO": "MC 정밀도 부족",
    "BLOCKED_BY_COMPUTE": "계산 차단",
}
STATUS_COLOR = {
    "SIGNIFICANT_H0B": "#b8302f",
    "SIGNIFICANT_H0A_ONLY": "#eda100",
    "NOT_SIGNIFICANT": "#898781",
    "NULL_MODEL_INVALID": "#6250d6",
    "NOT_ESTIMABLE": "#c3c2b7",
    "INSUFFICIENT_MONTE_CARLO": "#e87ba4",
    "EXPLORATORY": "#2a78d6",
}


def save(fig: plt.Figure, out: Path, name: str) -> list[Path]:
    """PNG 320dpi + SVG (메타데이터 날짜 제거 → 결정적)."""
    out.mkdir(parents=True, exist_ok=True)
    paths = [out / f"{name}.png", out / f"{name}.svg"]
    fig.savefig(paths[0], dpi=320, bbox_inches="tight", metadata={"Software": None})
    fig.savefig(paths[1], bbox_inches="tight", metadata={"Date": None, "Creator": None})
    plt.close(fig)
    return paths


def _date_axis(ax: plt.Axes) -> None:
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))


def _na_spans(ax: plt.Axes, dates: pd.DatetimeIndex, valid: np.ndarray) -> None:
    """CUSUM 계산 불능(NOT_AVAILABLE) 구간을 옅은 회색 띠로 — 무경보와 구분."""
    from r2h.joint_cusum.scores import run_lengths

    for a, b in run_lengths(~valid):
        ax.axvspan(dates[a], dates[b], color="#f0efec", zorder=0, lw=0)


def fig_individual(
    obs, names: dict, pipe_crit: dict, tickers: list[str], out: Path, fig_no: str
) -> list[Path]:
    """그림 08-1: ETF 별 가격(시작=100)·|r|·정책 A CUSUM T_w (4개 창, W1 동결 임계값 점선). 패널별 척도."""
    dates = obs.dates
    fig, axes = plt.subplots(
        3 * len(tickers), 1, figsize=(11, 2.15 * 3 * len(tickers)), sharex=True, gridspec_kw={"hspace": 0.12}
    )
    r = obs.R.loc[dates]
    for k, tk in enumerate(tickers):
        i = obs.tickers.index(tk)
        a0, a1, a2 = axes[3 * k], axes[3 * k + 1], axes[3 * k + 2]
        px = 100 * np.exp(np.cumsum(r[tk].to_numpy()) / 100)
        a0.plot(dates, px, color=TICKER_COLOR[tk], lw=1.0)
        a0.set_ylabel("가격\n(2021 초=100)", fontsize=7)
        a0.set_title(f"{names[tk]} ({tk})", fontsize=9, loc="left", color=INK)
        a1.plot(dates, np.abs(r[tk].to_numpy()), color=TICKER_COLOR[tk], lw=0.6)
        a1.set_ylabel("|r| (%/일)", fontsize=7)
        valid = np.isfinite(obs.out.T[i, 0, 2])
        _na_spans(a2, dates, valid)
        for w_i, w in enumerate((20, 30, 60, 120)):
            a2.plot(dates, obs.out.T[i, 0, w_i], color=W_COLOR[w], lw=0.7, label=f"w={w}")
            a2.axhline(pipe_crit["A", w], color=W_COLOR[w], lw=0.6, ls=":")
        a2.set_ylabel("CUSUM T\n(정책 A)", fontsize=7)
        if k == 0:
            a2.legend(fontsize=6.5, ncol=4, frameon=False, loc="upper left")
        for ax in (a0, a1, a2):
            style(ax)
    _date_axis(axes[-1])
    axes[0].figure.suptitle(
        f"그림 {fig_no}. ETF 별 가격·일간 변동·개별 CUSUM (2021–2025, 공통 날짜축)",
        x=0.01,
        ha="left",
        fontsize=12,
    )
    footnote(
        fig,
        "회색 띠 = CUSUM w=60 계산 불능(연초 59일, NOT_AVAILABLE — 무경보 아님). 점선 = W1 동결 임계값(pipeline_garch_annual_max, 기술용 — W1 적격 창 0/4 유지). 패널마다 세로 척도가 다르다.",
    )
    return save(fig, out, f"fig08_1_{tickers[0]}_individual")


def fig_sequence(
    case_tables: dict[str, pd.DataFrame], lag_df: pd.DataFrame, names: dict, out: Path, fig_no: str
) -> list[Path]:
    """그림 08-2: 사례 창의 ETF 별 첫 단기 후보·첫 CUSUM 경보 날짜 (가·나) + 단기 후보→CUSUM 경보 지연 분포 (다)."""
    fig = plt.figure(figsize=(12, 7.2))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 0.85], hspace=0.45, wspace=0.18)
    sigs = [
        ("first_daily_shock_q1", "q=1 충격", "x", MUTED),
        ("first_EXP_q3", "q=3 확대", "o", "#86b6ef"),
        ("first_EXP_q7", "q=7 확대", "o", "#3987e5"),
        ("first_EXP_q14", "q=14 확대", "o", "#0d366b"),
        ("first_CUSUM_w20", "CUSUM w=20", "s", "#ec835a"),
        ("first_CUSUM_w60", "CUSUM w=60", "s", "#b8302f"),
        ("first_CUSUM_w120", "CUSUM w=120", "s", "#6b1615"),
    ]
    for c_i, (title, tab) in enumerate(case_tables.items()):
        ax = fig.add_subplot(gs[0, c_i])
        ticks = list(tab.ticker)
        for y, (_, row) in enumerate(tab.iterrows()):
            for k, (col, lab, mk, colr) in enumerate(sigs):
                v = row[col]
                if v != "NONE":
                    ax.scatter(
                        pd.Timestamp(v),
                        y + (k - 3) * 0.09,
                        marker=mk,
                        s=26,
                        color=colr,
                        label=lab if y == 0 else None,
                        zorder=3,
                        edgecolor="white",
                        lw=0.4,
                    )
        ax.set_yticks(range(len(ticks)), [f"{names[t]}\n({t})" for t in ticks], fontsize=7)
        ax.invert_yaxis()
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
        ax.set_title(f"({'가나'[c_i]}) {title}", fontsize=9, loc="left")
        style(ax)
        if c_i == 1:
            ax.legend(fontsize=6.5, frameon=False, loc="upper left", bbox_to_anchor=(1.0, 1.0))
    ax = fig.add_subplot(gs[1, :])
    cols = ["lag_from_q3_EXP", "lag_from_q7_EXP", "lag_from_q14_EXP"]
    data, labels, pos = [], [], []
    for w_i, w in enumerate((20, 30, 60, 120)):
        for c_i, c in enumerate(cols):
            v = lag_df.loc[lag_df.w.eq(w), c].dropna().to_numpy()
            data.append(v if v.size else np.array([np.nan]))
            pos.append(w_i * 4 + c_i)
            labels.append(f"w={w}\n{c.split('_')[2]}")
    bp = ax.boxplot(
        [d[np.isfinite(d)] if np.isfinite(d).any() else [np.nan] for d in data],
        positions=pos,
        widths=0.7,
        patch_artist=True,
        showfliers=False,
    )
    for b, c_i in zip(bp["boxes"], [p % 4 for p in pos], strict=True):
        b.set_facecolor(["#86b6ef", "#3987e5", "#0d366b"][c_i])
        b.set_alpha(0.75)
    for med in bp["medians"]:
        med.set_color(INK)
    ax.set_xticks(pos, labels, fontsize=6.5)
    ax.set_ylabel("지연 (거래일)", fontsize=8)
    ax.set_title(
        "(다) CUSUM 경보 시작 전 60일 안의 가장 가까운 단기 확대 후보 → 경보까지 관측 지연 (6종·3정책)",
        fontsize=9,
        loc="left",
    )
    style(ax)
    fig.suptitle(
        f"그림 {fig_no}. 다중 기간 순차 탐지 — 단기 분위 후보(q)와 개별 CUSUM 경보(w)의 시점",
        x=0.01,
        ha="left",
        fontsize=12,
    )
    footnote(
        fig,
        "q 후보 = W2 규칙(엄밀 과거 확장형 분위 ≥ 0.90) — 탐색 후보이며 보정된 경보가 아니다. CUSUM 경보 = W1 동결 임계값(정책 A·B·base 중 최초). 사후 선택한 사례 창의 날짜는 실시간 조기 탐지 성공이 아니다.",
    )
    return save(fig, out, "fig08_2_sequential_detection")


def fig_bottom_up(
    stage: pd.DataFrame, null_C: dict[str, np.ndarray], part: pd.DataFrame, out: Path, fig_no: str
) -> list[Path]:
    """그림 08-3: (가) 단계 통계량 관측값 vs DCC 귀무 분포 (판정 색) · (나) ETF × 단계 조건부 참여 강도."""
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.6), gridspec_kw={"width_ratios": [1.15, 1.0]})
    ax = axes[0]
    for k, row in stage.reset_index(drop=True).iterrows():
        nul = null_C[row.stage]
        nul = nul[np.isfinite(nul)]
        if nul.size:
            q = np.quantile(nul, [0.5, 0.98])
            ax.plot([k, k], [nul.min(), q[1]], color=GRID, lw=6, solid_capstyle="butt", zorder=1)
            ax.scatter(k, q[0], marker="_", s=200, color=MUTED, zorder=2)
            ax.scatter(k, q[1], marker="_", s=200, color=INK2, zorder=2)
        if np.isfinite(row.obs):
            st = row.status
            ax.scatter(k, row.obs, s=60, color=STATUS_COLOR.get(st, INK), zorder=3, edgecolor="white")
            ax.annotate(
                STATUS_KO.get(st, st),
                (k, row.obs),
                textcoords="offset points",
                xytext=(6, 4),
                fontsize=7,
                color=INK2,
            )
        else:
            ax.annotate("추정 불가", (k, 0), fontsize=7, color=MUTED)
    ax.set_xticks(
        range(len(stage)),
        [f"{s}\n{m.split('+')[-1]}" for s, m in zip(stage.stage, stage.members, strict=True)],
        fontsize=7.5,
    )
    ax.set_ylabel("단계 통계량 (S1: max J_all · S2–S5: 신규 ETF 평균 시차 Q)", fontsize=7.5)
    ax.set_title(
        "(가) 관측값(점) 과 DCC-t 귀무 분포 (회색 막대: 최소~98% 분위, 짧은 선: 중앙·98%)",
        fontsize=8.5,
        loc="left",
    )
    style(ax)
    ax = axes[1]
    piv = part.pivot(index="ticker", columns="stage", values="mean_Qlag_on_E")
    im = ax.imshow(piv.to_numpy(float), cmap="Blues", aspect="auto", vmin=0)
    for (yy, xx), v in np.ndenumerate(piv.to_numpy(float)):
        ax.text(
            xx,
            yy,
            "—" if not np.isfinite(v) else f"{v:.2f}",
            ha="center",
            va="center",
            fontsize=7,
            color=INK if (not np.isfinite(v) or v < 2.5) else "white",
        )
    ax.set_xticks(range(piv.shape[1]), piv.columns, fontsize=8)
    ax.set_yticks(range(piv.shape[0]), piv.index, fontsize=8)
    ax.set_title(
        "(나) 직전 단계 공동일 E 에서 각 ETF 의 평균 시차 Q (최대 정책·창)", fontsize=8.5, loc="left"
    )
    fig.colorbar(im, ax=ax, fraction=0.04, label="평균 Q (귀무 기대 ≈ 1–2)")
    fig.suptitle(
        f"그림 {fig_no}. 바텀업 확장 S1→S5 — 단계 판정과 ETF 별 조건부 참여", x=0.01, ha="left", fontsize=12
    )
    footnote(
        fig,
        "단계 판정은 고정 순서(각 α=0.02). 귀무 부적합·추정 불가 단계 이후는 확증 사슬이 멈춘다. (나) 의 값은 기술 통계이며 유의성 표시가 아니다. '—' = E 가 비었거나 아직 편입 전.",
    )
    return save(fig, out, "fig08_3_bottom_up")


def fig_subsets(sub: pd.DataFrame, out: Path, fig_no: str) -> list[Path]:
    """그림 08-4: 57개 부분집합 — (가) 원시 공동 점수 M_S · (나) DCC 귀무 p (판정 상태, Holm 기준) — 두 패널 분리."""
    s = sub.sort_values(["size", "M_obs"], ascending=[True, False]).reset_index(drop=True)
    fig, axes = plt.subplots(2, 1, figsize=(13, 7.4), sharex=True, gridspec_kw={"hspace": 0.12})
    x = np.arange(len(s))
    sizes = s["size"].to_numpy()
    ax = axes[0]
    ax.bar(x, s.M_obs, color=[CAT[int(z) - 2] for z in sizes], width=0.75)
    ax.set_ylabel("M_S = max J_all (원시 점수)", fontsize=8)
    for z in sorted(set(sizes)):
        ax.bar([], [], color=CAT[int(z) - 2], label=f"{z}종")
    ax.legend(fontsize=7, ncol=5, frameon=False, loc="upper right")
    ax.set_title("(가) 원시 공동 점수 — 유의성 아님", fontsize=9, loc="left")
    style(ax)
    ax = axes[1]
    p = s.p_dcc.astype(float).to_numpy()
    for k, row in s.iterrows():
        st = row.status
        hollow = st == "NULL_MODEL_INVALID"
        ax.scatter(
            k,
            -np.log10(p[k]) if np.isfinite(p[k]) else 0,
            s=26,
            facecolor="none" if hollow else STATUS_COLOR.get(st, INK),
            edgecolor=STATUS_COLOR.get(st, INK),
            lw=0.9,
            zorder=3,
        )
    ax.axhline(-np.log10(0.02 / 57), color="#b8302f", ls=":", lw=0.8)
    ax.axhline(-np.log10(0.02), color=MUTED, ls=":", lw=0.8)
    ax.text(
        len(s) - 0.5,
        -np.log10(0.02 / 57),
        "Holm 첫 단계 0.02/57",
        fontsize=6.5,
        ha="right",
        va="bottom",
        color="#b8302f",
    )
    ax.text(len(s) - 0.5, -np.log10(0.02), "0.02", fontsize=6.5, ha="right", va="bottom", color=MUTED)
    for st in s.status.unique():
        ax.scatter(
            [],
            [],
            s=26,
            facecolor="none" if st == "NULL_MODEL_INVALID" else STATUS_COLOR.get(st, INK),
            edgecolor=STATUS_COLOR.get(st, INK),
            label=STATUS_KO.get(st, st),
        )
    ax.legend(fontsize=7, ncol=4, frameon=False, loc="upper right")
    ax.set_ylabel("−log10 p (DCC-t, MC)", fontsize=8)
    ax.set_xticks(x, [z.replace("+", "\n") for z in s.subset], fontsize=4.6)
    ax.set_title(
        "(나) DCC-t 귀무 MC p 와 판정 상태 (빈 원 = 귀무 부적합 → 확증 불가)", fontsize=9, loc="left"
    )
    style(ax)
    fig.suptitle(f"그림 {fig_no}. 전체 57개 부분집합의 공동 점수와 판정", x=0.01, ha="left", fontsize=12)
    footnote(
        fig,
        "p 하한은 1/(B+1). 같은 사건이 여러 부분집합에 나타나도 독립 증거가 아니다. 153130 포함 부분집합은 귀무 적합도 결과에 따라 확증에서 빠질 수 있다.",
    )
    return save(fig, out, "fig08_4_subsets57")


def fig_nulls(
    obs_vals: dict[str, float], nulls: dict[str, dict[str, np.ndarray]], out: Path, fig_no: str
) -> list[Path]:
    """그림 08-5: 통계량별 귀무 분포 비교 — H0-A 원형 이동 · H0-A 블록 · DCC-t (주) · CCC-t (민감도)."""
    keys = list(obs_vals)
    fig, axes = plt.subplots(1, len(keys), figsize=(4.2 * len(keys), 3.8), squeeze=False)
    colors = {
        "H0-A 원형 이동": "#eda100",
        "H0-A 블록": "#e87ba4",
        "H0-B DCC-t (주)": "#2a78d6",
        "H0-B CCC-t (민감도)": "#1baf7a",
    }
    for ax, k in zip(axes[0], keys, strict=True):
        allv = np.concatenate([v[np.isfinite(v)] for v in nulls[k].values()] + [np.array([obs_vals[k]])])
        bins = np.linspace(np.nanmin(allv), np.nanmax(allv), 60)
        for lab, v in nulls[k].items():
            v = v[np.isfinite(v)]
            ax.hist(
                v,
                bins=bins,
                density=True,
                histtype="step",
                lw=1.2,
                color=colors[lab],
                label=f"{lab} (n={v.size:,})",
            )
        if np.isfinite(obs_vals[k]):
            ax.axvline(obs_vals[k], color="#b8302f", lw=1.4)
            ax.text(obs_vals[k], ax.get_ylim()[1] * 0.92, " 관측", color="#b8302f", fontsize=7.5)
        ax.set_title(k, fontsize=9, loc="left")
        ax.set_xlabel("통계량 값", fontsize=8)
        style(ax)
    axes[0][0].set_ylabel("밀도", fontsize=8)
    axes[0][-1].legend(fontsize=6.5, frameon=False, loc="upper right")
    fig.suptitle(
        f"그림 {fig_no}. 시간 정렬 귀무(H0-A)와 시장 동조성 보존 귀무(H0-B)의 분포 비교",
        x=0.01,
        ha="left",
        fontsize=12,
    )
    footnote(
        fig,
        "H0-A 는 관측 Q 경로를 ETF·연도별로 재배열(재적합 없음) — 보조. H0-B 는 반복마다 연간 SVR 재적합을 포함한 전체 파이프라인(D15). 추정 불가 반복(E 비어 있음)은 히스토그램에서 빠진다.",
    )
    return save(fig, out, "fig08_5_null_comparison")


def fig_power(det: pd.DataFrame, delays: pd.DataFrame, out: Path, fig_no: str) -> list[Path]:
    """그림 08-6: (가) 시나리오×목표 가족 검출률 (5·10·20·60일, Wilson 95%) · (나) V1 영향 ETF 의 신호별 검출 지연."""
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8), gridspec_kw={"width_ratios": [1.25, 1.0]})
    ax = axes[0]
    d = det.reset_index(drop=True)
    hz = [5, 10, 20, 60]
    for k, row in d.iterrows():
        vals = [row[f"detected_within_{h}"] for h in hz]
        ax.plot(
            hz, vals, marker="o", ms=3, lw=1, color=CAT[k % len(CAT)], label=f"{row.scenario} → {row.family}"
        )
        ax.errorbar(
            60,
            row.detected_60,
            yerr=[
                [row.detected_60 - row.detected_60_wilson_low],
                [row.detected_60_wilson_high - row.detected_60],
            ],
            color=CAT[k % len(CAT)],
            lw=0.8,
            capsize=2,
        )
    ax.set_xscale("log")
    ax.set_xticks(hz, [str(h) for h in hz])
    ax.set_xlabel("변화 후 거래일", fontsize=8)
    ax.set_ylabel("유의일 검출률 (분모 = 전체 반복)", fontsize=8)
    ax.set_ylim(-0.02, 1.02)
    ax.legend(fontsize=6, frameon=False, ncol=2, loc="upper left")
    ax.set_title(
        "(가) 대립·음성 대조 시나리오의 검출률 (V7 = 정상 공통 충격 → 거짓 검출)", fontsize=8.5, loc="left"
    )
    style(ax)
    ax = axes[1]
    v1 = delays[delays.scenario.eq("V1")]
    order = [
        "q3_EXP",
        "q7_EXP",
        "q14_EXP",
        "short_A_w3",
        "short_A_w7",
        "short_A_w14",
        "cusum_Q_A_w20",
        "cusum_Q_A_w30",
        "cusum_Q_A_w60",
        "cusum_Q_A_w120",
        "cusum_w1crit_A_w60",
    ]
    rows = v1.set_index("signal").reindex(order)
    y = np.arange(len(order))
    ax.barh(y, rows.detected_60, color="#cde2fb", label="60일 내 검출 비율")
    for k, (_, row) in enumerate(rows.iterrows()):
        if np.isfinite(row.median_delay):
            ax.text(
                min(row.detected_60, 1) + 0.02,
                k,
                f"중앙 지연 {row.median_delay:.0f}일",
                va="center",
                fontsize=6.5,
                color=INK2,
            )
    ax.set_yticks(
        y,
        [
            "q=3 확대",
            "q=7 확대",
            "q=14 확대",
            "CUSUM w=3 (적격성 연구)",
            "CUSUM w=7 (적격성 연구)",
            "CUSUM w=14 (적격성 연구)",
            "Q≥c_E w=20",
            "Q≥c_E w=30",
            "Q≥c_E w=60",
            "Q≥c_E w=120",
            "W1 임계 w=60",
        ],
        fontsize=7,
    )
    ax.invert_yaxis()
    ax.set_xlim(0, 1.35)
    ax.set_xlabel("비율", fontsize=8)
    ax.set_title(
        "(나) V1 (KOSPI200·KOSDAQ150 분산 ×2) 영향 ETF 의 신호별 검출 (정책 A)", fontsize=8.5, loc="left"
    )
    style(ax)
    fig.suptitle(f"그림 {fig_no}. 합성 공동 변화의 검출력·지연과 음성 대조", x=0.01, ha="left", fontsize=12)
    footnote(
        fig,
        "모든 반복에서 연간 SVR 재적합 포함. 검출률 분모는 전체 반복(검출된 반복만 쓰지 않는다). 단기 q 후보는 분위 기반 탐색 후보, Q≥c_E 는 개별 꼬리 1% — 가족 보정 경보가 아니다.",
    )
    return save(fig, out, "fig08_6_power")


def fig_episode_zoom(
    obs,
    windows: list[tuple[str, str, str]],
    sig_days: dict[str, np.ndarray],
    names: dict,
    out: Path,
    fig_no: str,
) -> list[Path]:
    """그림 08-7: 주요 공동 구간·사례 창 확대 — ETF 별 max Q (정책·창 최대) · 유의일 음영 · 방향 표기."""
    dates = obs.dates
    fig, axes = plt.subplots(len(windows), 1, figsize=(11.5, 3.0 * len(windows)), squeeze=False)
    qmax = np.where(np.isfinite(obs.Q), obs.Q, -np.inf).max(axis=(1, 2))
    qmax[~np.isfinite(qmax)] = np.nan
    for ax, (title, a, b) in zip(axes[:, 0], windows, strict=True):
        m = (dates >= pd.Timestamp(a)) & (dates <= pd.Timestamp(b))
        for i, tk in enumerate(obs.tickers):
            ax.plot(dates[m], qmax[i, m], color=TICKER_COLOR[tk], lw=1.1, label=f"{names[tk]} ({tk})")
        flag = sig_days.get(title)
        if flag is not None:
            from r2h.joint_cusum.scores import run_lengths

            idx = np.flatnonzero(m)
            for s, e in run_lengths(flag[m]):
                ax.axvspan(dates[idx[s]], dates[idx[e]], color="#f6d3c8", zorder=0, lw=0)
        ax.axhline(-np.log(0.01), color=MUTED, ls=":", lw=0.8)
        ax.set_title(title, fontsize=9, loc="left")
        ax.set_ylabel("max Q (−log 꼬리확률)", fontsize=7.5)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        style(ax)
    axes[0, 0].legend(fontsize=6.5, ncol=3, frameon=False, loc="upper left")
    fig.suptitle(
        f"그림 {fig_no}. 주요 공동 구간 확대 — 참여 ETF 의 개별 꼬리점수와 판정",
        x=0.01,
        ha="left",
        fontsize=12,
    )
    footnote(
        fig,
        "점선 = c_E = −log 0.01 (개별 꼬리 1%). 음영 = 그 창 제목의 집합이 유의일 기준을 넘은 날 (없으면 음영 없음). 방향 표기는 기술 통계(유의성 없음).",
    )
    return save(fig, out, "fig08_7_episode_zoom")


def fig_price(summary: pd.DataFrame, out: Path, fig_no: str) -> list[Path]:
    """그림 08-8: 그룹·지평별 사후 누적수익률 중앙값과 20일 블록 bootstrap 95% 구간 (탐색)."""
    groups = [
        g
        for g in [
            "single_etf_only",
            "control_for_single_etf_only",
            "two_or_more_etf",
            "control_for_two_or_more_etf",
            "h0b_significant",
            "control_for_h0b_significant",
        ]
        if g in set(summary.group)
    ]
    ko = {
        "single_etf_only": "단독 반응",
        "two_or_more_etf": "2종 이상 공동",
        "h0b_significant": "H0-B 유의 구간",
    }
    hz = sorted(summary.h.unique())
    fig, axes = plt.subplots(1, len(hz), figsize=(4.3 * len(hz), 4.0), sharey=True, squeeze=False)
    for ax, h in zip(axes[0], hz, strict=True):
        s = summary[summary.h.eq(h)].set_index("group").reindex(groups)
        y = np.arange(len(groups))
        for k, (g, row) in enumerate(s.iterrows()):
            if not np.isfinite(row.median_ret):
                continue
            ctrl = g.startswith("control_for_")
            ax.errorbar(
                row.median_ret,
                k,
                xerr=[[row.median_ret - row.ci95_low], [row.ci95_high - row.median_ret]],
                fmt="o" if not ctrl else "s",
                color=MUTED if ctrl else "#2a78d6",
                ms=5,
                capsize=2,
                lw=1,
            )
            ax.text(row.ci95_high, k, f"  n={int(row.n_events)}", va="center", fontsize=6.5, color=INK2)
        ax.axvline(0, color=INK2, lw=0.6)
        ax.set_yticks(
            y,
            [
                ("대조: " + ko[g.replace("control_for_", "")]) if g.startswith("control_for_") else ko[g]
                for g in groups
            ],
            fontsize=7.5,
        )
        ax.invert_yaxis()
        ax.set_title(f"사후 {h}거래일", fontsize=9, loc="left")
        ax.set_xlabel("누적 로그수익률 중앙값 (%)", fontsize=8)
        style(ax)
    fig.suptitle(
        f"그림 {fig_no}. 단독·공동·H0-B 판정별 사후 가격 반응과 대조일 (EXPLORATORY_REUSED_DATA)",
        x=0.01,
        ha="left",
        fontsize=12,
    )
    footnote(
        fig,
        "기준일 = 공동 신호 이용 가능일 종가 다음 날. 대조일 = 같은 ETF·연도·사전 U_V(q=20) 십분위, ±20일 안 후보 없음. 구간 = 20일 날짜 블록 bootstrap 95%. 2021–25 는 이미 탐색한 자료 — 독립 확증 아님(α=0.01 예약).",
    )
    return save(fig, out, "fig08_8_price_response")


def fig_validity(n3: pd.DataFrame, n4: pd.DataFrame, out: Path, fig_no: str) -> list[Path]:
    """그림 08-9: 귀무 적합도 — ETF 별 N3 통계 (관측 vs 보정 반복 0.5–99.5%) · 쌍별 N4 탈락 수."""
    stats = [
        ("kurt", "초과 첨도"),
        ("acf_r2", "r² 자기상관 (1–5)"),
        ("var", "분산"),
        ("zero_share", "정확 0 비율"),
    ]
    fig, axes = plt.subplots(
        1, len(stats) + 1, figsize=(16, 3.8), gridspec_kw={"width_ratios": [1] * len(stats) + [1.2]}
    )
    y = np.arange(len(n3))
    for ax, (s, lab) in zip(axes[:-1], stats, strict=True):
        for k, row in n3.iterrows():
            ax.plot([row[f"{s}_lo"], row[f"{s}_hi"]], [k, k], color=GRID, lw=5, solid_capstyle="butt")
            ax.scatter(
                row[f"{s}_obs"],
                k,
                color="#1baf7a" if row[f"{s}_ok"] else "#b8302f",
                s=28,
                zorder=3,
                edgecolor="white",
            )
        ax.set_yticks(y, n3.ticker, fontsize=7.5)
        ax.invert_yaxis()
        ax.set_title(lab, fontsize=9, loc="left")
        if s in ("var",):
            ax.set_xscale("log")
        style(ax)
    ax = axes[-1]
    ax.barh(
        np.arange(len(n4)), n4.N4_fail_count, color=["#b8302f" if not ok else "#c3c2b7" for ok in n4.N4_pass]
    )
    ax.set_yticks(np.arange(len(n4)), n4.pair, fontsize=6)
    ax.invert_yaxis()
    ax.axvline(1.5, color=INK2, ls=":", lw=0.8)
    ax.set_title("N4 쌍별 탈락 수 (≥2 부적합)", fontsize=9, loc="left")
    style(ax)
    fig.suptitle(
        f"그림 {fig_no}. DCC-t 귀무의 적합도 게이트 (N3 ETF 별 · N4 쌍별)", x=0.01, ha="left", fontsize=12
    )
    footnote(
        fig,
        "회색 막대 = 보정 반복 2,000개의 0.5–99.5% 범위, 점 = 관측(2019-01-03~2025-12-30). 빨강 = 범위 밖. 정확 0 비율은 관측 ≤ 2% 면 호가 단위 효과로 통과(계약 §6.3).",
    )
    return save(fig, out, "fig08_9_null_validity")

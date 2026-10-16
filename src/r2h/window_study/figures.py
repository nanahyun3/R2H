# ruff: noqa: E501, B007  — 한국어 그림 캡션과 pandas.query의 지역변수 참조.
"""W1 결과의 한국어 출판 그림. 숫자 파일은 수정하지 않고 표현만 생성한다."""

from __future__ import annotations

import hashlib
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from r2h.svrgarch_etf.rolling import rolling_cusum
from r2h.window_study.empirical import _table_for_ticker

DPI = 320
YEAR_NOTE = "2020 = 파일럿(학습 2019 한 해) · 2026 = 10/2 까지 부분·비블라인드"
CATEGORY_KO = {
    "broad_market": "시장지수",
    "commodity": "원자재",
    "currency": "통화",
    "leveraged_inverse": "레버리지·인버스",
    "money_market": "단기자금",
    "rates": "국채",
    "sector": "업종",
    "strategy": "전략",
    "theme": "테마",
}


def font() -> str:
    """실재하는 한국어 글꼴을 지정하고(기호는 DejaVu 대체) 마이너스 깨짐을 피한다."""
    from matplotlib import font_manager

    nanum = Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf")
    if nanum.is_file():
        font_manager.fontManager.addfont(str(nanum))
        name = font_manager.FontProperties(fname=str(nanum)).get_name()
        plt.rcParams.update(
            {"font.family": [name, "DejaVu Sans"], "axes.unicode_minus": False, "svg.fonttype": "none"}
        )
        return name
    families = {f.name for f in font_manager.fontManager.ttflist}
    for name in ("Noto Sans CJK KR", "NanumSquare", "Noto Serif CJK KR"):
        if name in families:
            plt.rcParams.update(
                {"font.family": [name, "DejaVu Sans"], "axes.unicode_minus": False, "svg.fonttype": "none"}
            )
            return name
    raise RuntimeError("한글 글꼴이 없어 그림을 생성할 수 없습니다")


def _save(fig: plt.Figure, out: Path, stem: str, caption: str, source: str, note: str) -> dict:
    """본문 아래 주석(note)을 축 라벨과 겹치지 않게 그림 하단 여백에 둔 뒤 PNG·SVG 로 저장한다."""
    out.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.text(0.01, 0.01, note, fontsize=8.5, ha="left", va="bottom", color="#333333", wrap=True)
    png, svg = out / f"{stem}.png", out / f"{stem}.svg"
    fig.savefig(png, dpi=DPI, bbox_inches="tight")
    fig.savefig(svg, bbox_inches="tight")
    plt.close(fig)
    return {
        "그림": stem,
        "PNG": str(png),
        "SVG": str(svg),
        "캡션": caption,
        "자료": source,
        "PNG_SHA256": hashlib.sha256(png.read_bytes()).hexdigest(),
        "SVG_SHA256": hashlib.sha256(svg.read_bytes()).hexdigest(),
    }


def synthetic_figures(
    det: pd.DataFrame, pipe: pd.DataFrame, selection: pd.DataFrame, out: Path
) -> pd.DataFrame:
    """03: H0 크기, H1 검출률, 적합 포함 귀무·대립을 Wilson 95% 구간과 사전 기준선으로 표시한다."""
    font()
    rows = []
    windows = sorted(det.w.unique())
    fig, ax = plt.subplots(figsize=(8.4, 5.2))
    for dgp, label, marker in (
        ("stable_low_variance_no_change", "정규 독립", "o"),
        ("stable_heavy_tail", "t5 독립 (단위분산)", "s"),
        ("stable_garch_clustering", "GARCH 군집", "^"),
    ):
        d = det.query("stage == 'H0' and dgp == @dgp").sort_values("w")
        ax.plot(d.w, d.any_alarm, marker=marker, label=label)
        ax.fill_between(
            d.w.to_numpy(), d.any_alarm_ci_low.to_numpy(), d.any_alarm_ci_high.to_numpy(), alpha=0.12
        )
    ax.axhline(0.10, color="black", linestyle="--", label="사전 연간 경보 예산 0.10 (Wilson 상한 기준)")
    ax.set(
        xlabel="검정창 w (거래일)",
        ylabel="연중 1회 이상 경보 확률 (귀무)",
        xticks=windows,
        ylim=(-0.005, 0.13),
        title="그림 03-1. 검출기 수준 귀무의 연간 경보 확률",
    )
    ax.legend(fontsize=8.5, loc="upper center", ncol=2, framealpha=0.95)
    rows.append(
        _save(
            fig,
            out,
            "fig03_01_귀무_연간경보",
            "세 귀무·245거래일 모의, 공통 126일(t≥119) 평가. 연간 경보는 점별 5% 가 아니다.",
            "detector_summary.csv",
            "귀무·창마다 평가 R=1,000 (보정 R=500 과 별도 난수열) · 음영 = 95% Wilson 구간 · 임계값 = 세 귀무 연중 최대 T 95% 분위의 최대",
        )
    )

    fig, ax = plt.subplots(figsize=(8.4, 5.2))
    for dgp, label, marker, required in (
        ("garch_up_x2", "지속 분산 2배 상승 (필수)", "o", True),
        ("garch_down_x0.5", "지속 분산 절반 하락 (필수)", "s", True),
        ("garch_transient_up_x2_40d", "40일 일시 2배 (민감도)", "^", False),
        ("garch_gradual_up_1to2", "점진적 1→2배 (민감도)", "D", False),
    ):
        d = det.query("stage == 'H1' and dgp == @dgp").sort_values("w")
        (line,) = ax.plot(d.w, d.detected_60d, marker=marker, label=label, linestyle="-" if required else ":")
        if required:
            ax.fill_between(
                d.w.to_numpy(),
                d.detected_ci_low.to_numpy(),
                d.detected_ci_high.to_numpy(),
                alpha=0.15,
                color=line.get_color(),
            )
    ax.axhline(0.15, color="black", linestyle="--", label="사전 검출률 하한 기준 0.15 (Wilson 하한)")
    ax.set(
        xlabel="검정창 w (거래일)",
        ylabel="변화 후 60거래일 내 경보 확률 (대립)",
        xticks=windows,
        ylim=(0, 0.2),
        title="그림 03-2. 알려진 분산 변화의 60일 검출률 — 모든 창이 기준 미달",
    )
    ax.legend(fontsize=8.5, loc="upper left", framealpha=0.95)
    rows.append(
        _save(
            fig,
            out,
            "fig03_02_합성_검출률",
            "합성 GARCH 변화 4종, 변화 시점 k=122. 지속 상승·하락만 필수 조건이며 일시·점진은 민감도다.",
            "detector_summary.csv",
            "대립·창마다 R=1,000 · 음영 = 필수 대립의 95% Wilson 구간 · 판정은 Wilson 하한 ≥0.15 · 합성 검출률이며 실제 ETF 검출력이 아님",
        )
    )

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.9), sharex=True)
    for pol, label, marker in (
        ("A", "정책 A (주 선정)", "o"),
        ("B", "정책 B (민감도)", "s"),
        ("base", "σ60 기준선 (민감도)", "^"),
    ):
        for ax, stage, col, lo, hi in (
            (axes[0], "H0", "any_alarm", "any_alarm_ci_low", "any_alarm_ci_high"),
            (axes[1], "H1", "detected_60d", "detected_ci_low", "detected_ci_high"),
        ):
            d = pipe.query("stage == @stage and policy == @pol").sort_values("w")
            (line,) = ax.plot(d.w, d[col], marker=marker, label=label)
            if pol == "A":
                ax.fill_between(
                    d.w.to_numpy(), d[lo].to_numpy(), d[hi].to_numpy(), alpha=0.15, color=line.get_color()
                )
    axes[0].axhline(0.10, color="black", linestyle="--", label="예산 0.10 (상한 기준)")
    axes[1].axhline(0.15, color="black", linestyle="--", label="하한 기준 0.15")
    axes[0].set(
        xlabel="검정창 w (거래일)",
        ylabel="연중 1회 이상 경보 확률",
        xticks=windows,
        ylim=(0, 0.25),
        title="(a) GARCH 귀무 (R=200)",
    )
    axes[1].set(
        xlabel="검정창 w (거래일)",
        ylabel="변화 후 60거래일 내 경보 확률",
        ylim=(0, 0.25),
        title="(b) 분산 ×2 대립 (R=200)",
    )
    for ax in axes:
        ax.legend(fontsize=8, loc="upper left", framealpha=0.95)
    fig.suptitle("그림 03-3. SVR 적합 포함 파이프라인의 정책별 귀무·대립")
    rows.append(
        _save(
            fig,
            out,
            "fig03_03_적합포함_귀무",
            "모의마다 과거 490일로 T12 27-grid SVR 재적합 후 A/B/base 잔차. 정책·창별 임계값은 별도 보정 200회.",
            "pipeline_summary.csv",
            "음영 = 정책 A 의 95% Wilson 구간 (선정은 A 만) · w=60 은 귀무 상한이 예산 초과 · 단일 GARCH 생성모형 조건부 결과",
        )
    )
    return pd.DataFrame(rows)


def real_path_figure(
    source_root: Path,
    run_id: str,
    ticker: str,
    year: int,
    policy: str,
    thresholds: pd.DataFrame,
    out: Path,
    name: str = "KODEX 200",
) -> pd.DataFrame:
    """03: 동일 ETF·연도의 네 창 실제 T 경로와 정책별 연간 보정 임계값."""
    font()
    daily = _table_for_ticker(source_root, run_id, ticker)
    g = daily.query("year == @year and policy == @policy and window == 0").sort_values("date")
    e, dates = g.e.to_numpy(float), pd.DatetimeIndex(g.date)
    t = thresholds.set_index(["policy", "w"]).critical_annual_max
    fig, axes = plt.subplots(4, 1, figsize=(11.5, 9.5), sharex=True)
    colors = ("#2865A0", "#D87826", "#27916E", "#8D63A6")
    for ax, w, color in zip(axes, (20, 30, 60, 120), colors, strict=True):
        stat = rolling_cusum(e, w)
        mask = (np.arange(len(e)) >= 119) & np.isfinite(stat)
        ax.plot(dates[mask], stat[mask], color=color, linewidth=1.2, label=f"관측 T (w={w} 거래일)")
        ax.axhline(t[policy, w], color="black", linestyle="--", label=f"연간 보정 임계값 {t[policy, w]:.3f}")
        hit = mask & (stat >= t[policy, w])
        if hit.any():
            ax.scatter(dates[hit], stat[hit], color="red", s=14, zorder=3, label="경보일 (T ≥ 임계값)")
        ax.set_ylabel("CUSUM T")
        ax.set_ylim(0, max(float(np.nanmax(stat[mask])), t[policy, w]) * 1.25)
        ax.legend(loc="upper left", fontsize=8, ncol=3, framealpha=0.95)
    axes[0].set_title(
        f"그림 03-4. {ticker} {name}, {year}년, 정책 {policy}: 공통 PURE 날짜(t≥119)의 관측 CUSUM 경로"
    )
    axes[-1].set_xlabel("검정연도 날짜 (거래일만)")
    return pd.DataFrame(
        [
            _save(
                fig,
                out,
                "fig03_04_대표ETF_경로",
                f"{year}년 {ticker} {name} 정책 {policy}, 공통 PURE 일자. 실선 관측 통계량 / 점선 합성 GARCH 연간 임계값.",
                "T12 daily.csv.gz (b_nb_20261016T181251) + pipeline_thresholds.csv",
                "T = 표준화 잔차 제곱 CUSUM 의 창내 최대 이탈 / (√n × τ), τ = 잔차 제곱의 표본 표준편차 · 경보 = T ≥ 임계값 (실제 변화 정답 없음) · 임계값은 합성 GARCH 귀무 보정, 시장 적합 보장 없음",
            )
        ]
    )


def empirical_figures(
    valid: pd.DataFrame,
    alarms: pd.DataFrame,
    meta: pd.DataFrame,
    out: Path,
    null_any_alarm: dict[int, float] | None = None,
) -> pd.DataFrame:
    """04: 20종의 공통 유효일, 자산군별·연도별 관측 경보 부담을 분리한다."""
    font()
    rows = []
    label = meta.set_index("ticker").apply(lambda r: f"{r.name} {r['name']}", axis=1)
    v = valid.query("year >= 2021 and year <= 2025 and policy == 'A' and w == 120")
    grid = v.pivot(index="ticker", columns="year", values="n_common_valid").reindex(meta.ticker)
    fig, ax = plt.subplots(figsize=(9.5, 9))
    img = ax.imshow(grid.to_numpy(float), cmap="YlGnBu", vmin=110, vmax=130, aspect="auto")
    for i in range(grid.shape[0]):
        for j in range(grid.shape[1]):
            val = grid.iat[i, j]
            ax.text(
                j,
                i,
                f"{val:.0f}",
                ha="center",
                va="center",
                fontsize=7.5,
                color="white" if val > 124 else "black",
            )
    ax.set(
        xticks=np.arange(len(grid.columns)),
        xticklabels=grid.columns,
        yticks=np.arange(len(grid.index)),
        yticklabels=[label[t] for t in grid.index],
        xlabel="검정연도",
        title="그림 04-1. 20종 × 2021–2025 공통 PURE 평가 가능일 (정책 A)",
    )
    fig.colorbar(img, ax=ax, label="네 창 공통 유효 거래일 수")
    rows.append(
        _save(
            fig,
            out,
            "fig04_01_공통일_히트맵",
            "20 ETF × 2021–2025 정책 A. 네 후보 창(20/30/60/120)의 공통 PURE 유효일 수; 검정력 지표가 아니다.",
            "validity.csv",
            "공통일 = 연중 순번 t≥119 이고 네 창의 T 가 모두 유한한 날 · 2020·2026 은 주 분석에서 제외 ("
            + YEAR_NOTE
            + ")",
        )
    )

    d = alarms.query(
        "year >= 2021 and year <= 2025 and policy == 'A' and threshold_type == 'pipeline_garch_annual_max' and sample_type == 'common'"
    )
    d = d.merge(meta[["ticker", "category"]], on="ticker", validate="many_to_one")
    d["category"] = d.category.map(CATEGORY_KO)
    ag = d.groupby(["category", "w"], observed=True).episodes_per_252_valid_days.mean().unstack("w")
    n_etf = d.groupby("category").ticker.nunique().reindex(ag.index)
    fig, ax = plt.subplots(figsize=(10.5, 5.4))
    x = np.arange(len(ag.index))
    for j, w in enumerate(ag.columns):
        ax.bar(x + (j - 1.5) * 0.2, ag[w], width=0.18, label=f"w={w} 거래일")
    ax.set(
        xticks=x,
        xticklabels=[f"{c}\n(n={n})" for c, n in n_etf.items()],
        ylabel="252 유효일당 에피소드 (ETF·연도 평균)",
        ylim=(0, float(np.nanmax(ag.to_numpy())) * 1.25),
        title="그림 04-2. 자산군별 관측 경보 부담 (2021–2025 · 정책 A · 연간 보정 임계값)",
    )
    ax.legend(ncol=4, fontsize=8, loc="upper right", framealpha=0.95)
    rows.append(
        _save(
            fig,
            out,
            "fig04_02_자산군_경보",
            "20 ETF × 2021–2025·정책 A·공통 PURE. 자산군 평균 에피소드; 참양성/오탐률 아님.",
            "alarm_metrics.csv + reference_close_sha256.csv",
            "n = 자산군 ETF 수 (불균등) · 같은 날 공통 충격을 공유해 자산군 차이를 독립 표본 차이로 읽지 않음 · 경보는 실제 변화 정답이 아님",
        )
    )

    y = alarms.query(
        "policy == 'A' and threshold_type == 'pipeline_garch_annual_max' and sample_type == 'common'"
    )
    share = y.groupby(["year", "w"]).any_alarm.mean().unstack("w")
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.axvspan(2019.5, 2020.5, color="#BBBBBB", alpha=0.35, label="2020 파일럿")
    ax.axvspan(2025.5, 2026.5, color="#F2C14E", alpha=0.35, label="2026 부분·비블라인드")
    for w in share.columns:
        (line,) = ax.plot(share.index, share[w], marker="o", label=f"w={w} 거래일")
        if null_any_alarm and w in null_any_alarm:
            ax.axhline(null_any_alarm[w], color=line.get_color(), linestyle=":", linewidth=1)
    ax.set(
        xlabel="검정연도",
        ylabel="경보 있는 ETF 비율 (20종 중)",
        xticks=share.index,
        ylim=(0, 1),
        title="그림 04-3. 연도별 '경보 있는 ETF' 비율 (정책 A · 연간 보정 임계값)",
    )
    ax.legend(fontsize=8, ncol=3, loc="upper right", framealpha=0.95)
    rows.append(
        _save(
            fig,
            out,
            "fig04_03_연도별_경보비율",
            "20 ETF × 2020–2026·정책 A·공통 PURE. 연도별 경보 있는 ETF 비율; 연도 차이를 시장 구조로 귀속하지 않는다.",
            "alarm_metrics.csv",
            "점선 = 같은 임계값의 합성 GARCH 귀무 기대 비율 (03 정책 A any_alarm) · ETF 노출이 겹쳐 독립 20회 시행이 아님 · "
            + YEAR_NOTE,
        )
    )
    return pd.DataFrame(rows)

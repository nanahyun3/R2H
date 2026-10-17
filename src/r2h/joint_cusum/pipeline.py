"""수익률 패널 → 연간 SVR 재적합 → 정책별 잔차 → 연도 안 이동창 CUSUM (계약 §5.1, §9).

관측 자료와 모든 합성 반복이 **같은 함수**를 지난다. T12 원 함수(``fit_annual``·``forecast_year``·
``baseline_variance``·``standardize``)와 W1 원 함수(``rolling_cusum``)를 수정 없이 호출한다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from r2h.annual_expanding.fit import baseline_variance, fit_annual, forecast_year, standardize
from r2h.svrgarch_etf.rolling import rolling_cusum

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = REPO_ROOT / "configs" / "t15_joint_cusum_w3_v2.json"
POLICIES: tuple[str, ...] = ("A", "B", "base")


def load_cfg(path: Path | None = None) -> dict:
    """동결 설정 JSON 만 읽는다."""
    return json.loads((path or CONFIG_PATH).read_text(encoding="utf-8"))


def all_windows(cfg: dict) -> list[int]:
    """CUSUM 창 순서: 주 창 4개 다음 단기 적격성 창 3개 (배열 축 순서 고정)."""
    return list(cfg["pipeline"]["windows_primary"]) + list(cfg["pipeline"]["windows_short_eligibility"])


def load_returns(cfg: dict, raw_dir: Path) -> pd.DataFrame:
    """원자료 6종 종가 → 공통 거래일 % 로그수익률 (2019-01-03..2025-12-30)."""
    tickers = cfg["universe"]["tickers"]
    close = {}
    for t in tickers:
        frame = pd.read_csv(raw_dir / f"{t}.csv", dtype={"Date": str})
        close[t] = pd.Series(frame["Close"].astype(float).to_numpy(), index=pd.to_datetime(frame["Date"]))
    px = pd.DataFrame(close).sort_index().dropna()
    if (px <= 0).to_numpy().any():
        raise ValueError("비양수 종가")
    r = 100.0 * np.log(px).diff()
    s = cfg["sample"]
    r = r.loc[s["returns_start"] : s["returns_end"]]
    if r.isna().to_numpy().any():
        raise AssertionError("6종 공통 거래일에 결측 수익률이 있다")
    return r[tickers]


@dataclass(frozen=True)
class PipelineOut:
    """평가 구간(2021–2025) 배열. 축: (ETF, 정책, 창, 일) — 창 순서는 ``all_windows``."""

    eval_dates: pd.DatetimeIndex
    year_of_day: np.ndarray  # 평가일의 연도
    pos_in_year: np.ndarray  # 연중 0-기반 위치
    e: np.ndarray  # (n_etf, 3, n_day) 표준화 잔차
    vhat: np.ndarray  # (n_etf, 3, n_day) 예측분산 (정책 base 는 직전 60일 표본분산)
    T: np.ndarray  # (n_etf, 3, n_win, n_day) CUSUM 통계량, NOT_AVAILABLE = NaN
    fit_params: list[dict]  # ETF·연도별 SVR 선택 파라미터


def run_pipeline(returns: pd.DataFrame, cfg: dict) -> PipelineOut:
    """한 수익률 패널(관측 또는 합성)을 T12·W1 규약 그대로 처리한다."""
    years = cfg["sample"]["evaluation_years"]
    wins = all_windows(cfg)
    idx = pd.DatetimeIndex(returns.index)
    ev = np.asarray(
        (idx >= pd.Timestamp(f"{years[0]}-01-01")) & (idx < pd.Timestamp(f"{years[-1] + 1}-01-01"))
    )
    eval_dates = idx[ev]
    yod = eval_dates.year.to_numpy()
    pos = np.zeros(len(eval_dates), dtype=int)
    for y in years:
        m = yod == y
        pos[m] = np.arange(int(m.sum()))
    n_etf, n_day = returns.shape[1], len(eval_dates)
    e = np.full((n_etf, 3, n_day), np.nan)
    vh = np.full((n_etf, 3, n_day), np.nan)
    T = np.full((n_etf, 3, len(wins), n_day), np.nan)
    fits: list[dict] = []
    bwin, bmin = cfg["pipeline"]["baseline_window"], cfg["pipeline"]["baseline_min_periods"]
    for i, tk in enumerate(returns.columns):
        r_all = returns[tk]
        rc = r_all.to_numpy(float)
        # 기준선 분산: 직전 60일 표본분산 (연도 경계를 넘는 rolling, T12 와 동일)
        base_var = baseline_variance(r_all, bwin, bmin).to_numpy(float)
        for y in years:
            ys, ye = pd.Timestamp(f"{y}-01-01"), pd.Timestamp(f"{y + 1}-01-01")
            pre = np.asarray(idx < ys)
            tm = np.asarray((idx >= ys) & (idx < ye))
            ctx, test = rc[pre], rc[tm]
            # T12 inner_split: 학습 이력의 70% 를 내부 학습, 나머지를 검증 (round)
            af = fit_annual(ctx, round(0.7 * ctx.size))
            var = {
                "A": forecast_year(af.fit, ctx, test, "A"),
                "B": forecast_year(af.fit, ctx, test, "B"),
                "base": base_var[tm],
            }
            dm = yod == y
            for p_i, p in enumerate(POLICIES):
                ey = standardize(test, var[p])
                e[i, p_i, dm] = ey
                vh[i, p_i, dm] = var[p]
                for w_i, w in enumerate(wins):
                    # 그해 잔차 안에서만 이동창 CUSUM (첫 유효 위치 = w−1)
                    T[i, p_i, w_i, dm] = rolling_cusum(ey, w)
            fits.append(
                {"ticker": tk, "year": y, "C": af.params[0], "gamma2": af.params[1], "eps": af.params[2]}
            )
    return PipelineOut(eval_dates, yod, pos, e, vh, T, fits)


def run_pipeline_years(paths: dict[int, pd.DataFrame], cfg: dict) -> PipelineOut:
    """평가연도별 경로 (lock-2 §10): 연도 y 는 paths[y] (y 이전 자료로 적합한 귀무에서 모의한 2019..y 경로) 로만 평가한다.

    연도마다 ``run_pipeline`` 을 그해만 평가하도록 호출하고 날짜 축으로 이어 붙인다 (SVR 적합 수는 단일 경로와 같다).
    """
    parts = []
    for y in cfg["sample"]["evaluation_years"]:
        sub = {**cfg, "sample": {**cfg["sample"], "evaluation_years": [y]}}
        parts.append(run_pipeline(paths[y], sub))
    return PipelineOut(
        eval_dates=pd.DatetimeIndex(np.concatenate([p.eval_dates.to_numpy() for p in parts])),
        year_of_day=np.concatenate([p.year_of_day for p in parts]),
        pos_in_year=np.concatenate([p.pos_in_year for p in parts]),
        e=np.concatenate([p.e for p in parts], axis=-1),
        vhat=np.concatenate([p.vhat for p in parts], axis=-1),
        T=np.concatenate([p.T for p in parts], axis=-1),
        fit_params=[f for p in parts for f in p.fit_params],
    )

"""Rolling 상관과 지속성(hysteresis) 부호 국면 — 선택 feature.

원본: SA_ETF Track A ``src/r2h/research_a/rolling_correlation.py`` (``rolling_corr``, ``RegimeRule``,
``sign_regimes``) 를 옮겼다. 변경점 (수치 동치, 원본과의 parity 는 docs/provenance/PARITY.md):
(1) 빈 창에서 ``nanmean`` 이 내는 RuntimeWarning 을 피하려고 평균·제곱합을 마스크 합으로 계산,
(2) ``confirm_lag_days`` 를 행 위치 차이로 직접 계산, (3) 타입 힌트·입력 검사 추가.

**연구 결론 (Track A, SA_ETF ``codex/r2h-track-a``)**: 상관 부호 전환과 가격 급등·급락의 근접은 같은 날 큰 수익률의
기계적 이중계산을 빼면 우연 수준과 구분되지 않았다. 이 모듈은 국면 *기술(description)* 용이며, 급등 정답이나
조기 경보로 쓸 근거는 없다 (research/cross_asset_track_a.md).

시점 규약: ρ_t 는 [t−w+1, t] 수익률만 사용 → t 종가 이후 관측 가능. 지속성으로 확정한 국면 전환의
``candidate_at`` 은 ``confirmed_at`` 시점에야 알 수 있다 — 실시간 비교에는 ``confirmed_at`` 만 쓴다.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view
from scipy.stats import rankdata

RANK_DECIMALS = 12


def _win(a: np.ndarray, w: int) -> np.ndarray:
    """행 t = t 에서 끝나는 길이 w 창. 앞쪽 w−1 행은 NaN 으로 채워 index 를 원 시계열과 맞춘다."""
    return sliding_window_view(np.concatenate([np.full(w - 1, np.nan), a]), w)


def rolling_corr(
    x: pd.Series,
    y: pd.Series,
    window: int,
    method: str = "pearson",
    min_periods: int | None = None,
    rank_round: bool = True,
) -> pd.DataFrame:
    """반환 (index = x.index): ``rho``, ``n_eff`` (창 안 쌍 관측 수), ``const`` (분산 0 창).

    NaN 은 pairwise-complete 로 제외. n_eff < min_periods 또는 분산 0 이면 ρ = NaN.
    spearman 은 각 창 *안에서* 순위를 매긴다 (전체표본 순위는 미래 정보를 섞는다).
    """
    if not x.index.equals(y.index):
        raise ValueError("x, y index must be identical (align before calling)")
    if window < 2:
        raise ValueError("window must be >= 2")
    mp = window if min_periods is None else min_periods
    xa, ya = x.to_numpy(float), y.to_numpy(float)
    if method == "spearman" and rank_round:
        xa, ya = np.round(xa, RANK_DECIMALS), np.round(ya, RANK_DECIMALS)
    X, Y = _win(xa, window).copy(), _win(ya, window).copy()
    valid = ~np.isnan(X) & ~np.isnan(Y)
    X[~valid] = np.nan
    Y[~valid] = np.nan
    n = valid.sum(axis=1)
    if method == "spearman":
        X = rankdata(X, axis=1, nan_policy="omit")
        Y = rankdata(Y, axis=1, nan_policy="omit")
        X[~valid] = np.nan
        Y[~valid] = np.nan
    elif method != "pearson":
        raise ValueError(method)
    with np.errstate(invalid="ignore", divide="ignore"):
        empty = n == 0
        Xs, Ys = np.where(valid, X, 0.0), np.where(valid, Y, 0.0)
        cnt = np.where(empty, 1, n)[:, None]
        xm = np.where(valid, X - Xs.sum(axis=1, keepdims=True) / cnt, 0.0)
        ym = np.where(valid, Y - Ys.sum(axis=1, keepdims=True) / cnt, 0.0)
        sxx, syy = (xm * xm).sum(axis=1), (ym * ym).sum(axis=1)
        rho = (xm * ym).sum(axis=1) / np.sqrt(sxx * syy)
    const = (sxx == 0) | (syy == 0)
    rho[(n < mp) | const] = np.nan
    return pd.DataFrame({"rho": np.clip(rho, -1, 1), "n_eff": n, "const": const & (n >= mp)}, index=x.index)


def null_band(window: int, z: float = 1.96) -> float:
    """독립·정규 가정의 근사 표본 오차대 ±z/√w (겹치는 창·두꺼운 꼬리에서는 과소평가될 수 있다)."""
    return float(z / np.sqrt(window))


@dataclass(frozen=True)
class RegimeRule:
    band: float  # |ρ| 가 이 값을 넘어야 부호 상태로 인정 (0 이면 순수 부호)
    persist: int  # band 밖 같은 부호가 연속 이 일수 이상이면 확정

    @property
    def id(self) -> str:
        return f"b{self.band:.3f}_k{self.persist}"


REGIME_COLUMNS = [
    "candidate_at",
    "zero_cross_at",
    "confirmed_at",
    "from_sign",
    "to_sign",
    "prev_peak_abs",
    "state_since",
    "is_initial",
    "confirm_lag_days",
]


def sign_regimes(rho: pd.Series, rule: RegimeRule) -> pd.DataFrame:
    """히스테리시스 상태기계. ρ 가 ±band 밖에서 persist 일 연속 같은 부호면 그 부호로 확정.

    candidate_at  새 부호 run 의 첫날 · confirmed_at  persist 번째 날 (이 날 종가에 비로소 확정)
    confirm_lag_days = confirmed_at − candidate_at (거래일 = 행 수) = persist − 1.
    첫 확정은 초기 상태이므로 ``is_initial=True`` 로 구분한다 (사건이 아님).
    """
    if rule.persist < 1 or rule.band < 0:
        raise ValueError("persist must be >= 1 and band >= 0")
    v = rho.to_numpy(float)
    idx = rho.index
    state, run_sign, run_len, run_start, run_start_pos = 0, 0, 0, None, -1
    last_cross, prev_val = None, np.nan
    state_since, peak = None, 0.0
    ev = []
    for i, x in enumerate(v):
        if np.isnan(x):
            run_sign, run_len = 0, 0
            continue
        if (
            not np.isnan(prev_val)
            and np.sign(x) != 0
            and np.sign(prev_val) != 0
            and np.sign(x) != np.sign(prev_val)
        ):
            last_cross = idx[i]
        prev_val = x
        if state != 0 and np.sign(x) == state:
            peak = max(peak, abs(x))
        sg = int(np.sign(x)) if abs(x) > rule.band else 0
        if sg != 0 and sg == run_sign:
            run_len += 1
        elif sg != 0:
            run_sign, run_len, run_start, run_start_pos = sg, 1, idx[i], i
        else:
            run_sign, run_len = 0, 0
        if run_len == rule.persist and run_sign != state:
            ev.append(
                {
                    "candidate_at": run_start,
                    "zero_cross_at": last_cross if state != 0 else pd.NaT,
                    "confirmed_at": idx[i],
                    "from_sign": state,
                    "to_sign": run_sign,
                    "prev_peak_abs": peak if state != 0 else np.nan,
                    "state_since": state_since,
                    "is_initial": state == 0,
                    "confirm_lag_days": i - run_start_pos,
                }
            )
            state, state_since, peak = run_sign, idx[i], abs(x)
    return pd.DataFrame(ev, columns=REGIME_COLUMNS)

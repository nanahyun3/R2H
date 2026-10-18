"""합성 경로 — 2019 로만 적합한 GARCH(1,1)-t 를 실제 달력에 모의하고 시나리오 변화를 주입 (계약 §7, 설정 synthetic).

같은 rep 은 모든 시나리오에서 같은 기저 혁신을 쓴다 (대응 비교). 변화는 GARCH 재귀 밖의 배수 √m_t 로 넣는다.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from r2h.joint_cusum.dcc import GarchT, fit_garch_t

BURN = 500
SCENARIOS: tuple[str, ...] = (
    "S00_null",
    "S01_var_x1.5",
    "S02_var_x2",
    "S03_var_x3",
    "S04_short_shock",
    "S05_long_persistent",
    "S06_gradual",
    "S07_mean_shift",
    "S08_one_day_extreme",
    "S09_up_then_down",
    "S10_repeated",
    "S11_year_boundary",
    "S12_var_x0.5",
)


def fit_dgp(r_2019: np.ndarray) -> GarchT:
    """2019 수익률만으로 적합 (평가 구간 정보 없음)."""
    return fit_garch_t(np.asarray(r_2019, float))


def base_innovations(g: GarchT, n: int, rng: np.random.Generator) -> np.ndarray:
    """GARCH(1,1)-t 의 ε (평균 제외) 길이 n — 앞 BURN 일 버림. 표준화 t: Var=1."""
    N = n + BURN
    z = rng.standard_t(g.nu, size=N) * np.sqrt((g.nu - 2.0) / g.nu)
    eps = np.empty(N)
    h = g.uncond_var
    for t in range(N):
        eps[t] = np.sqrt(h) * z[t]
        h = g.omega + g.alpha * eps[t] ** 2 + g.beta * h
    return eps[BURN:]


@dataclass(frozen=True)
class Change:
    """주입한 변화. taus = 알려진 변화일 (전체 위치), kind 는 시나리오 이름."""

    kind: str
    taus: tuple[int, ...]
    mult: np.ndarray  # 분산 배수 m_t
    mean_add: np.ndarray  # 평균 가산


def draw_tau(rng: np.random.Generator, dates: pd.DatetimeIndex, lo: str, hi: str) -> int:
    ok = np.flatnonzero((dates >= pd.Timestamp(lo)) & (dates <= pd.Timestamp(hi)))
    return int(rng.choice(ok))


def boundary_tau(rng: np.random.Generator, dates: pd.DatetimeIndex, years: list[int]) -> int:
    """무작위 연도 y 의 마지막 거래일 5 거래일 전."""
    y = int(rng.choice(years))
    last = int(np.flatnonzero(dates.year == y)[-1])
    return last - 5


def make_change(kind: str, n: int, tau: int, tau_b: int, sd: float) -> Change:
    m = np.ones(n)
    mu = np.zeros(n)
    taus: tuple[int, ...] = (tau,)
    if kind == "S00_null":
        taus = ()
    elif kind == "S01_var_x1.5":
        m[tau:] = 1.5
    elif kind == "S02_var_x2":
        m[tau:] = 2.0
    elif kind == "S03_var_x3":
        m[tau:] = 3.0
    elif kind == "S04_short_shock":
        m[tau : tau + 5] = 3.0
    elif kind == "S05_long_persistent":
        m[tau : tau + 120] = 2.0
    elif kind == "S06_gradual":
        ramp = np.linspace(1.0, 3.0, 61)[1:]
        k = min(60, n - tau)
        m[tau : tau + k] = ramp[:k]
        m[tau + k :] = 3.0
    elif kind == "S07_mean_shift":
        mu[tau : tau + 60] = 0.5 * sd
    elif kind == "S08_one_day_extreme":
        mu[tau] = -8.0 * sd
        m[tau] = 0.0  # 그날은 극단값 하나로 대체
    elif kind == "S09_up_then_down":
        m[tau : tau + 40] = 3.0
        taus = (tau, tau + 40)
    elif kind == "S10_repeated":
        for j, v in enumerate((2.0, 1.0, 2.0, 1.0)):
            m[tau + 60 * j :] = v
        taus = tuple(tau + 60 * j for j in range(4))
    elif kind == "S11_year_boundary":
        m[tau_b:] = 2.0
        taus = (tau_b,)
    elif kind == "S12_var_x0.5":
        m[tau:] = 0.5
    else:
        raise ValueError(kind)
    return Change(kind, taus, m, mu)


def synth_returns(g: GarchT, eps: np.ndarray, ch: Change) -> np.ndarray:
    """r_t = μ + mean_add_t + √m_t · ε_t."""
    return g.mu + ch.mean_add + np.sqrt(ch.mult) * eps

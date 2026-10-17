"""귀무 꼬리점수 Q 와 공동 통계량 (계약 §5.2–5.3).

배열 축 규약: Q 는 (ETF, 정책, 창, 일). 창 축은 주 창 4개(20·30·60·120)만 쓴다.
관측과 모든 귀무 반복이 같은 함수를 지난다 — 시차 탐색·E 재생성도 반복마다 다시 한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import numpy as np

LAGS: tuple[int, ...] = (-2, -1, 0, 1, 2)


# ── 꼬리표 ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class TailTable:
    """(ETF, 정책, 창) 칸마다 정렬 표본을 K 개 순서통계량으로 줄인 표와 원 풀 크기."""

    table: np.ndarray  # (n_etf, n_pol, n_win, K) 오름차순
    n_pool: np.ndarray  # (n_etf, n_pol, n_win)


def build_tail_table(pool: np.ndarray, K: int) -> TailTable:
    """pool: (reps, n_etf, n_pol, n_win, n_day) 보정 반복의 T. NaN 은 풀에서 뺀다."""
    _, ne, npol, nw, _ = pool.shape
    tab = np.empty((ne, npol, nw, K))
    npool = np.zeros((ne, npol, nw), dtype=np.int64)
    for i in range(ne):
        for p in range(npol):
            for w in range(nw):
                v = pool[:, i, p, w, :].ravel()
                v = np.sort(v[np.isfinite(v)])
                n = v.size
                ranks = np.round(np.linspace(0, n - 1, K)).astype(np.int64)
                tab[i, p, w] = v[ranks]
                npool[i, p, w] = n
    return TailTable(tab, npool)


def tail_u(T: np.ndarray, tt: TailTable) -> np.ndarray:
    """u = (1 + #{T_cal ≥ T}) / (N+1). 순서통계량 표로 계수를 근사하고, 풀 최대값 초과는 1/(N+1) (외삽 없음)."""
    ne, npol, nw, K = tt.table.shape
    u = np.full(T.shape, np.nan)
    for i in range(ne):
        for p in range(npol):
            for w in range(nw):
                x = T[i, p, w]
                ok = np.isfinite(x)
                n = int(tt.n_pool[i, p, w])
                pos = np.searchsorted(
                    tt.table[i, p, w], x[ok], side="left"
                )  # 표에서 x 보다 작은 순서통계량 수
                # 표 위치 → 원 풀 순위: rank = pos·(n−1)/(K−1) (pos=K 이면 모든 값보다 큼)
                below = np.where(pos >= K, n, np.round(pos * (n - 1) / (K - 1)))
                count_ge = n - below
                u[i, p, w, ok] = (1.0 + count_ge) / (n + 1.0)
    return u


def q_score(T: np.ndarray, tt: TailTable) -> np.ndarray:
    """Q = −log u. T 가 NaN (NOT_AVAILABLE) 이면 Q 도 NaN — 0 으로 바꾸지 않는다."""
    return -np.log(tail_u(T, tt))


# ── 시차 ───────────────────────────────────────────────────────────


def lag_max(Q: np.ndarray, lags: tuple[int, ...] = LAGS) -> tuple[np.ndarray, np.ndarray]:
    """마지막 축(일)에 대해 max_l Q(t+l). 범위 밖·NaN 은 무시, 모두 NaN 이면 NaN. 반환 (값, 고른 시차)."""
    shifted = []
    for lag in lags:
        s = np.full(Q.shape, np.nan)
        if lag > 0:
            s[..., :-lag] = Q[..., lag:]
        elif lag < 0:
            s[..., -lag:] = Q[..., :lag]
        else:
            s[...] = Q
        shifted.append(s)
    S = np.stack(shifted, axis=0)
    allnan = np.isnan(S).all(axis=0)
    filled = np.where(np.isnan(S), -np.inf, S)
    arg = filled.argmax(axis=0)
    val = np.take_along_axis(filled, arg[None], axis=0)[0]
    val[allnan] = np.nan
    lag_used = np.asarray(lags)[arg].astype(float)
    lag_used[allnan] = np.nan
    return val, lag_used


# ── 집합·공동 통계량 ────────────────────────────────────────────────


def all_subsets(tickers: list[str]) -> list[tuple[str, ...]]:
    """크기 2 이상 모든 부분집합 (고정 순서 유지)."""
    return [c for k in range(2, len(tickers) + 1) for c in combinations(tickers, k)]


def anchor_of(subset: tuple[str, ...], tickers: list[str]) -> str:
    """069500 이 있으면 069500, 없으면 고정 순서상 첫 구성원."""
    return "069500" if "069500" in subset else min(subset, key=tickers.index)


def member_stack(Q: np.ndarray, Qlag: np.ndarray, subset: tuple[str, ...], tickers: list[str]) -> np.ndarray:
    """(m, 정책, 창, 일): 기준 ETF 는 시차 없음, 나머지는 시차 최대값."""
    a = anchor_of(subset, tickers)
    rows = [Q[tickers.index(a)]] + [Qlag[tickers.index(t)] for t in subset if t != a]
    return np.stack(rows, axis=0)


def j_all(stack: np.ndarray) -> np.ndarray:
    """구성원 최소값. 하나라도 NaN 이면 NaN (np.min 은 NaN 을 전파)."""
    return stack.min(axis=0)


def j_k(stack: np.ndarray, k: int = 2) -> np.ndarray:
    """k 번째로 큰 값 (비결측 k 개 이상 필요)."""
    filled = np.where(np.isnan(stack), -np.inf, stack)
    srt = np.sort(filled, axis=0)
    out = srt[-k]
    out[np.isfinite(stack).sum(axis=0) < k] = np.nan
    return out


def nanmax_or_nan(x: np.ndarray) -> float:
    return float(np.nanmax(x)) if np.isfinite(x).any() else float("nan")


@dataclass(frozen=True)
class StageCond:
    """S_k 신규 ETF 조건부 참여 (계약 §5.3)."""

    stat: float  # C_Sk (NaN = NOT_ESTIMABLE)
    cell_mean: np.ndarray  # (정책, 창) mean Qlag_new over E (|E|<min_E → NaN)
    cell_n: np.ndarray  # (정책, 창) |E ∩ 신규 유효|


def stage_conditional(
    Q: np.ndarray,
    Qlag: np.ndarray,
    prev: tuple[str, ...],
    new: str,
    tickers: list[str],
    c_E: float,
    min_E: int,
) -> StageCond:
    """E_{k−1}(p,w) = {t : J_2(S_{k−1}) ≥ c_E} 를 **이 자료에서** 다시 만들고 신규 ETF 의 평균 시차 Q 를 잰다."""
    j2 = j_k(member_stack(Q, Qlag, prev, tickers), 2)
    qn = Qlag[tickers.index(new)]
    with np.errstate(invalid="ignore"):
        E = (j2 >= c_E) & np.isfinite(qn)
    n = E.sum(axis=-1)
    tot = np.where(E, qn, 0.0).sum(axis=-1)
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = tot / n
    mean = np.where(n >= min_E, mean, np.nan)
    return StageCond(nanmax_or_nan(mean), mean, n)


def run_lengths(flag: np.ndarray) -> list[tuple[int, int]]:
    """연속 True 구간 [시작, 끝] (병합 없음)."""
    out: list[tuple[int, int]] = []
    start = None
    for i, f in enumerate(flag):
        if f and start is None:
            start = i
        elif not f and start is not None:
            out.append((start, i - 1))
            start = None
    if start is not None:
        out.append((start, len(flag) - 1))
    return out


def max_cumulative_excess(jmax: np.ndarray, c0: float) -> tuple[float, int]:
    """J_max ≥ c0 연속 구간의 누적 초과량 최대값과 최장 길이 (구간 수준 귀무 통계량)."""
    with np.errstate(invalid="ignore"):
        flag = np.isfinite(jmax) & (jmax >= c0)
    best, longest = 0.0, 0
    for s, e in run_lengths(flag):
        best = max(best, float((jmax[s : e + 1] - c0).sum()))
        longest = max(longest, e - s + 1)
    return best, longest


@dataclass(frozen=True)
class RepStats:
    """반복 1회 (또는 관측) 의 검정 통계량 모음."""

    M_subset: np.ndarray  # (57,) max J_all
    M2_subset: np.ndarray  # (57,) max J_2 (기술용)
    C_stage: np.ndarray  # (4,) S2..S5 조건부 참여 통계량
    M2_stage: np.ndarray  # (5,) S1..S5 J_2 최대 (기술용)
    cum_excess: np.ndarray  # (57,) 구간 누적 초과량 최대
    longest_run: np.ndarray  # (57,) 최장 연속 J_max ≥ c0


def rep_statistics(Q: np.ndarray, cfg: dict) -> RepStats:
    """Q (ETF, 정책, 주 창, 일) → 모든 검정 통계량. 관측·귀무 공통."""
    tickers = list(cfg["universe"]["tickers"])
    jc = cfg["joint"]["primary_test_statistics"]
    c_E, min_E = float(jc["c_E"]), int(jc["min_E"])
    c0 = float(cfg["episodes"]["episode_level_threshold_c0"])
    Qlag, _ = lag_max(Q)
    subs = all_subsets(tickers)
    M = np.empty(len(subs))
    M2 = np.empty(len(subs))
    ce = np.empty(len(subs))
    lr = np.empty(len(subs))
    for s_i, s in enumerate(subs):
        st = member_stack(Q, Qlag, s, tickers)
        ja = j_all(st)
        M[s_i] = nanmax_or_nan(ja)
        M2[s_i] = nanmax_or_nan(j_k(st, 2))
        jmax = np.where(np.isfinite(ja), ja, -np.inf).max(axis=(0, 1))
        jmax[~np.isfinite(jmax)] = np.nan
        ce[s_i], lr[s_i] = max_cumulative_excess(jmax, c0)
    stages = cfg["universe"]["stages"]
    names = ["S1", "S2", "S3", "S4", "S5"]
    C = np.empty(4)
    for k in range(1, 5):
        prev = tuple(stages[names[k - 1]])
        new = cfg["universe"]["stage_new_ticker"][names[k]]
        C[k - 1] = stage_conditional(Q, Qlag, prev, new, tickers, c_E, min_E).stat
    M2s = np.array([nanmax_or_nan(j_k(member_stack(Q, Qlag, tuple(stages[n]), tickers), 2)) for n in names])
    return RepStats(M, M2, C, M2s, ce, lr)

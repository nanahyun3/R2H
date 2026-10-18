"""E4 변화점 규칙 (계약 §4 · 설정 ``changepoints_E4``): 가격 기울기 P · 변동성 V · 이동평균 M · 첨도 K.

정보 규약:
- 시점 t 의 점수는 t 종가까지의 ``close``·``r`` 만 쓴다 (모든 창은 [.., t] 로 끝난다).
- 임계값은 그 규칙 자신의 강도 점수 중 **t 보다 엄격히 이전** 유한값들의 확장형 분위 q
  (``np.quantile(..., method="linear")``). 이전 유한 점수 수 < ``min_prior`` (120) 이면 NaN → 트리거 불가.
- 초과 상태 진입 에지에서만 트리거, 불응기 gap 이내 진입 에지는 무시. t 종가 확정 → 효과일 t+1.

창 안에 NaN 이 하나라도 있거나 데이터가 부족하면 점수는 NaN. 분산 0 등으로 비유한 값이 나와도 NaN.
"""

from __future__ import annotations

import bisect

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

P_LENGTHS = (5, 10, 20)
V_LENGTHS = (5, 20, 60)
V_VARIANTS = ("two", "up", "down")  # two_sided |s| · expansion s · contraction −s
M_PAIRS = ((5, 20), (10, 60), (20, 60))
K_LENGTHS = (60, 120)
QUANTILES = (0.95, 0.99)
GAPS = (0, 10, 20)
MIN_PRIOR = 120


def rule_ids() -> list[str]:
    """강도 계열 17개 이름 (P3 + V9 + M3 + K2). q 는 별도 인자이므로 규칙 = 계열 × q = 34 (``rule_grid``)."""
    out = [f"P{L}" for L in P_LENGTHS]
    out += [f"V{L}_{v}" for L in V_LENGTHS for v in V_VARIANTS]
    out += [f"M{s}_{l}" for s, l in M_PAIRS]
    out += [f"K{L}" for L in K_LENGTHS]
    return out


def rule_grid(qs: tuple[float, ...] = QUANTILES) -> list[tuple[str, float]]:
    """(계열, q) 34 규칙. gap 은 트리거 단계의 별도 인자."""
    return [(rid, q) for rid in rule_ids() for q in qs]


# ---------------------------------------------------------------------------
# 창 도우미 — 끝점 t 에 정렬된 길이 n 배열을 돌려준다 (창이 부족한 앞부분은 NaN)
# ---------------------------------------------------------------------------


def _end_aligned(x: np.ndarray, L: int, fn) -> np.ndarray:
    """x 의 길이 L 창 [t−L+1, t] 마다 fn(창 행렬 (m, L)) → (m,) 를 계산해 t 에 놓는다. NaN 포함 창은 NaN."""
    n = x.size
    out = np.full(n, np.nan)
    if n < L:
        return out
    W = sliding_window_view(x, L)  # 행 j = x[j..j+L−1] → 끝점 t = j+L−1
    ok = np.isfinite(W).all(axis=1)
    vals = np.full(W.shape[0], np.nan)
    if ok.any():
        with np.errstate(all="ignore"):
            vals[ok] = fn(W[ok])
    out[L - 1 :] = vals
    out[~np.isfinite(out)] = np.nan
    return out


def _lag(x: np.ndarray, k: int) -> np.ndarray:
    """x_{t−k} (앞 k 개는 NaN)."""
    out = np.full(x.size, np.nan)
    if k < x.size:
        out[k:] = x[: x.size - k]
    return out


def _ols_slope(W: np.ndarray) -> np.ndarray:
    """각 행을 x=0..L−1 에 회귀한 OLS 기울기."""
    L = W.shape[1]
    xc = np.arange(L, dtype=float) - (L - 1) / 2.0
    return (W - W.mean(axis=1, keepdims=True)) @ xc / float(xc @ xc)


def _excess_kurtosis(W: np.ndarray) -> np.ndarray:
    """Fisher 초과첨도, bias=True (``scipy.stats.kurtosis`` 기본과 같은 정의): m4/m2² − 3. m2=0 이면 NaN."""
    d = W - W.mean(axis=1, keepdims=True)
    m2 = (d**2).mean(axis=1)
    m4 = (d**4).mean(axis=1)
    out = np.full(W.shape[0], np.nan)
    pos = m2 > 0
    out[pos] = m4[pos] / m2[pos] ** 2 - 3.0
    return out


def _winsor_kurtosis(W: np.ndarray) -> np.ndarray:
    """창 내부 1/99 분위(linear)로 잘라낸 뒤 초과첨도. 분위는 그 창 자신의 값만 쓴다 (전체 표본 통계 금지)."""
    lo, hi = np.quantile(W, [0.01, 0.99], axis=1, method="linear")
    return _excess_kurtosis(np.clip(W, lo[:, None], hi[:, None]))


def _diff_halves(x: np.ndarray, L: int, fn) -> np.ndarray:
    """fn([t−L+1,t]) − fn([t−2L+1,t−L])."""
    cur = _end_aligned(x, L, fn)
    return cur - _lag(cur, L)


# ---------------------------------------------------------------------------
# 점수
# ---------------------------------------------------------------------------


def compute_scores(close: np.ndarray, r: np.ndarray) -> pd.DataFrame:
    """종가·수익률(100·Δlog, 같은 날짜축) → 위치 0..n−1 index 의 점수 표.

    열 (계열 id = ``rule_ids()``):
    - ``{id}_score`` 부호 있는 원점수, ``{id}_strength`` 임계 비교에 쓰는 강도, ``{id}_dir`` 방향 (sign(score)).
    - V 변형 셋은 같은 원점수 s 를 공유한다: two → |s|, up → s, down → −s (음수도 과거 분위 풀에 들어간다).
    - M: ``{id}_gap`` = ln(MA_s/MA_l), ``{id}_cross`` (bool) = sign(gap_t) ≠ sign(gap_{t−1}) (어느 쪽이든 NaN 이면 False).
    - K: ``{id}_w_score`` / ``{id}_w_strength`` 창 내부 1/99 winsorize 변형, ``{id}_n_cur`` / ``{id}_n_prev`` 창 내 유효 표본 수.
    """
    close = np.asarray(close, dtype=float)
    r = np.asarray(r, dtype=float)
    if close.shape != r.shape or close.ndim != 1:
        raise ValueError("close 와 r 은 같은 길이의 1차원 배열이어야 한다")
    n = close.size
    cols: dict[str, np.ndarray] = {}

    with np.errstate(all="ignore"):
        logp = np.where(close > 0, np.log(close), np.nan)

    # P_L: 로그가격 OLS 기울기 차
    for L in P_LENGTHS:
        s = _diff_halves(logp, L, _ols_slope)
        cols[f"P{L}_score"] = s
        cols[f"P{L}_strength"] = np.abs(s)
        cols[f"P{L}_dir"] = np.sign(s)

    # V_L: ln(var 현재 / var 직전), ddof=1
    for L in V_LENGTHS:
        var = _end_aligned(r, L, lambda W: W.var(axis=1, ddof=1))
        var[~(var > 0)] = np.nan  # 분산 0 → 로그비 ±inf 방지
        with np.errstate(all="ignore"):
            s = np.log(var / _lag(var, L))
        s[~np.isfinite(s)] = np.nan
        for v, st in (("two", np.abs(s)), ("up", s.copy()), ("down", -s)):
            cols[f"V{L}_{v}_score"] = s
            cols[f"V{L}_{v}_strength"] = st
            cols[f"V{L}_{v}_dir"] = np.sign(s)

    # M_(s,l): gap = ln(MA_s/MA_l), change = gap_t − gap_{t−s}
    for sh, lg in M_PAIRS:
        ma_s = _end_aligned(close, sh, lambda W: W.mean(axis=1))
        ma_l = _end_aligned(close, lg, lambda W: W.mean(axis=1))
        with np.errstate(all="ignore"):
            gap = np.log(ma_s / ma_l)
        gap[~np.isfinite(gap)] = np.nan
        ch = gap - _lag(gap, sh)
        prev = _lag(gap, 1)
        both = np.isfinite(gap) & np.isfinite(prev)
        cross = np.zeros(n, dtype=bool)
        cross[both] = np.sign(gap[both]) != np.sign(prev[both])
        rid = f"M{sh}_{lg}"
        cols[f"{rid}_score"] = ch
        cols[f"{rid}_strength"] = np.abs(ch)
        cols[f"{rid}_dir"] = np.sign(ch)
        cols[f"{rid}_gap"] = gap
        cols[f"{rid}_cross"] = cross

    # K_L: 초과첨도 차 (+ winsorize 변형 · 유효 표본 수)
    for L in K_LENGTHS:
        s = _diff_halves(r, L, _excess_kurtosis)
        sw = _diff_halves(r, L, _winsor_kurtosis)
        fin = np.isfinite(r).astype(float)
        n_cur = np.full(n, np.nan)
        if n >= L:
            n_cur[L - 1 :] = sliding_window_view(fin, L).sum(axis=1)
        rid = f"K{L}"
        cols[f"{rid}_score"] = s
        cols[f"{rid}_strength"] = np.abs(s)
        cols[f"{rid}_dir"] = np.sign(s)
        cols[f"{rid}_w_score"] = sw
        cols[f"{rid}_w_strength"] = np.abs(sw)
        cols[f"{rid}_n_cur"] = n_cur
        cols[f"{rid}_n_prev"] = _lag(n_cur, L)

    return pd.DataFrame(cols, index=pd.RangeIndex(n))


# ---------------------------------------------------------------------------
# 임계값 · 트리거
# ---------------------------------------------------------------------------


def expanding_threshold(
    strength: np.ndarray, qs: tuple[float, ...] = QUANTILES, min_prior: int = MIN_PRIOR
) -> tuple[dict[float, np.ndarray], np.ndarray]:
    """t 보다 엄격히 이전 유한 강도들의 분위 {q: thr} 와 과거 백분위 pctile_t = #{과거 < s_t} / #과거.

    과거 유한 수 < min_prior 이면 thr·pctile 모두 NaN. s_t 가 NaN 이면 pctile NaN. NaN 은 과거 수에 세지 않는다.
    """
    s = np.asarray(strength, dtype=float)
    n = s.size
    thr = {q: np.full(n, np.nan) for q in qs}
    pct = np.full(n, np.nan)
    past: list[float] = []  # 정렬 유지 (bisect.insort)
    qarr = np.asarray(qs, dtype=float)
    for t in range(n):
        m = len(past)
        if m >= min_prior:
            vals = np.quantile(np.asarray(past), qarr, method="linear")
            for q, v in zip(qs, vals):
                thr[q][t] = v
            if np.isfinite(s[t]):
                pct[t] = bisect.bisect_left(past, s[t]) / m
        if np.isfinite(s[t]):
            bisect.insort(past, float(s[t]))
    return thr, pct


def _edge_refractory(exceed: np.ndarray, gap: int) -> np.ndarray:
    """진입 에지 (exceed_t ∧ ¬exceed_{t−1}, 원 초과 상태 기준) 중 직전 채택 트리거로부터 gap 일 이내(t−t_last ≤ gap)는 무시.

    무시된 에지의 초과 구간이 불응기 뒤까지 이어져도 새 진입 에지가 아니므로 트리거되지 않는다.
    t_last 는 채택된 트리거에서만 갱신.
    """
    prev = np.concatenate(([False], exceed[:-1]))
    edges = np.flatnonzero(exceed & ~prev)
    out: list[int] = []
    t_last = None
    for t in edges:
        if t_last is not None and gap > 0 and t - t_last <= gap:
            continue
        out.append(int(t))
        t_last = int(t)
    return np.asarray(out, dtype=np.int64)


def _trigger_from_thr(s: np.ndarray, thr: np.ndarray, pct: np.ndarray, gap: int) -> dict:
    with np.errstate(invalid="ignore"):
        exceed = np.isfinite(s) & np.isfinite(thr) & (s > thr)
    trig = _edge_refractory(exceed, gap)
    eff = trig + 1
    eff = eff[eff < s.size]
    return {"thr": thr, "exceed": exceed, "trigger_idx": trig, "effect_idx": eff, "pctile": pct}


def triggers(strength: np.ndarray, q: float, gap: int, min_prior: int = MIN_PRIOR) -> dict:
    """강도 계열 하나 × q × gap → {thr, exceed, trigger_idx (확정일 t), effect_idx (t+1, n 이상은 제외), pctile}."""
    s = np.asarray(strength, dtype=float)
    thr, pct = expanding_threshold(s, (q,), min_prior)
    return _trigger_from_thr(s, thr[q], pct, gap)


def all_triggers(
    scores: pd.DataFrame,
    gaps: tuple[int, ...] = GAPS,
    qs: tuple[float, ...] = QUANTILES,
    min_prior: int = MIN_PRIOR,
) -> pd.DataFrame:
    """모든 계열 × q × gap 의 트리거 long 표.

    열: rule, q, gap, trigger_pos, effect_pos (Int64, t+1 ≥ n 이면 <NA>), strength, thr, pctile, direction.
    thr·pctile 은 (계열) 마다 한 번 계산해 q·gap 에 재사용한다.
    """
    rows: list[pd.DataFrame] = []
    n = len(scores)
    for rid in rule_ids():
        s = scores[f"{rid}_strength"].to_numpy(dtype=float)
        d = scores[f"{rid}_dir"].to_numpy(dtype=float)
        thr_all, pct = expanding_threshold(s, tuple(qs), min_prior)
        for q in qs:
            for g in gaps:
                res = _trigger_from_thr(s, thr_all[q], pct, g)
                t = res["trigger_idx"]
                eff = pd.array(np.where(t + 1 < n, t + 1, -1), dtype="Int64")
                eff[t + 1 >= n] = pd.NA
                rows.append(
                    pd.DataFrame(
                        {
                            "rule": rid,
                            "q": q,
                            "gap": g,
                            "trigger_pos": t,
                            "effect_pos": eff,
                            "strength": s[t],
                            "thr": thr_all[q][t],
                            "pctile": pct[t],
                            "direction": d[t],
                        }
                    )
                )
    cols = ["rule", "q", "gap", "trigger_pos", "effect_pos", "strength", "thr", "pctile", "direction"]
    if not rows:
        return pd.DataFrame(columns=cols)
    out = pd.concat(rows, ignore_index=True)[cols]
    out["trigger_pos"] = out["trigger_pos"].astype(np.int64)
    out["effect_pos"] = out["effect_pos"].astype("Int64")
    return out

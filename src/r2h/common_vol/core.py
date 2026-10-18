"""10번 공통 고변동성 후보 규칙 — 일별 판정·연속 구간·구간 특성 (계약 10-lock-1 §2–§6).

입력은 09(W4)의 그룹 A 상태(1/0/NA)뿐이다. 이 모듈은 상태를 다시 계산하지 않는다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def rule_id(q: int, k: int) -> str:
    return f"q{q}_k{k}"


def candidate_flag(n_a: np.ndarray, n_eval: np.ndarray, k: int, n_groups: int) -> np.ndarray:
    """C(k,q,t): 17개 그룹이 모두 평가 가능한 날만 1[N_A ≥ k], 아니면 NA (0 으로 대체하지 않는다)."""
    n_a = np.asarray(n_a, float)
    n_eval = np.asarray(n_eval, float)
    out = np.where(n_a >= k, 1.0, 0.0)
    out[n_eval < n_groups] = np.nan
    return out


def _state(x: float) -> str:
    return "NA" if np.isnan(x) else str(int(x))


def extract_intervals(flag: np.ndarray, in_period: np.ndarray) -> list[dict]:
    """기간 마스크 안에서 1 의 연속 구간을 찾는다. 갭 병합·최소 길이 없음, NA 는 끊는 경계.

    flag 와 in_period 는 전체 달력(2019–2026) 길이다. 기간은 연속 블록이어야 한다.
    검열: 기간 첫날(마지막 날)이 1 이면 전체 달력의 직전(직후) 거래일 상태로 판정한다
    (1 → True, NA 또는 달력 끝 → 'UNKNOWN', 0 → False). 직전·직후 날은 구간에 넣지 않는다.
    """
    f = np.asarray(flag, float)
    idx = np.flatnonzero(in_period)
    if idx.size == 0:
        return []
    lo, hi = int(idx[0]), int(idx[-1])
    if idx.size != hi - lo + 1:
        raise ValueError("기간 마스크가 연속 블록이 아니다")
    n = f.size
    rows: list[dict] = []
    t = lo
    while t <= hi:
        if f[t] != 1:
            t += 1
            continue
        s = t
        while t + 1 <= hi and f[t + 1] == 1:
            t += 1
        e = t
        if s == lo:
            left = "UNKNOWN" if s == 0 or np.isnan(f[s - 1]) else bool(f[s - 1] == 1)
            entry = "PERIOD_START"
        else:
            left = False
            entry = "AFTER_NA" if np.isnan(f[s - 1]) else "AFTER_0"
        if e == hi:
            right = "UNKNOWN" if e == n - 1 or np.isnan(f[e + 1]) else bool(f[e + 1] == 1)
            exit_reason = "PERIOD_END"
        else:
            right = False
            exit_reason = "NA_BOUNDARY" if np.isnan(f[e + 1]) else "CONDITION_EXITED"
        rows.append({
            "i0": s, "i1": e, "left_censored": left, "right_censored": right,
            "entry_after": entry, "exit_reason": exit_reason,
            "state_before": _state(f[s - 1]) if s > 0 else "START",
            "state_after": _state(f[e + 1]) if e + 1 < n else "END",
        })
        t = e + 1
    return rows


def jaccard(a: set, b: set) -> float:
    u = a | b
    return float("nan") if not u else len(a & b) / len(u)


def interval_profile(i0: int, i1: int, a: np.ndarray, b: np.ndarray, ab: np.ndarray,
                     groups: list[str], dates: pd.DatetimeIndex) -> dict:
    """구간 [i0, i1] 의 참여 특성. a/b/ab 는 (날짜 × 그룹) 1/0/NaN 배열.

    '같은 날 동시 참여'(N_A 최대) 와 '구간 중 한 번이라도 참여'(ever) 를 따로 센다.
    """
    sa = a[i0:i1 + 1]
    on = sa == 1
    n_a = on.sum(axis=1)
    mx = int(n_a.max())
    at_max = np.flatnonzero(n_a == mx)
    first_max = int(at_max[0])
    ever = on.any(axis=0)
    always = on.all(axis=0)
    sets = [frozenset(np.flatnonzero(r)) for r in on]
    jac = [jaccard(set(x), set(y)) for x, y in zip(sets[:-1], sets[1:])]
    nb = (b[i0:i1 + 1] == 1).sum(axis=1)
    nab = (ab[i0:i1 + 1] == 1).sum(axis=1)
    g = np.asarray(groups)
    return {
        "max_n_A": mx,
        "max_n_A_first_date": dates[i0 + first_max].date(),
        "n_days_at_max": int(at_max.size),
        "mean_n_A": float(n_a.mean()),
        "median_n_A": float(np.median(n_a)),
        "start_n_A": int(n_a[0]),
        "end_n_A": int(n_a[-1]),
        "groups_at_max_first_day": "|".join(g[on[first_max]]),
        "groups_always": "|".join(g[always]),
        "groups_ever": "|".join(g[ever]),
        "groups_never": "|".join(g[~ever]),
        "n_groups_always": int(always.sum()),
        "n_groups_ever": int(ever.sum()),
        "n_groups_never": int((~ever).sum()),
        "stability_consecutive_jaccard": float(np.mean(jac)) if jac else float("nan"),
        "core_share": float(always.sum() / ever.sum()) if ever.any() else float("nan"),
        "max_n_B": int(nb.max()),
        "max_n_AB": int(nab.max()),
        "mean_n_B": float(nb.mean()),
        "mean_n_AB": float(nab.mean()),
        "n_groups_B_ever": int((b[i0:i1 + 1] == 1).any(axis=0).sum()),
        "n_groups_AB_ever": int((ab[i0:i1 + 1] == 1).any(axis=0).sum()),
        "evaluable_share": float(np.isfinite(sa).all(axis=1).mean()),
    }


def containment_map(strict: pd.DataFrame, loose: pd.DataFrame) -> pd.Series:
    """엄격 규칙 구간마다 그것을 포함하는 완화 규칙 구간 ID (정확히 하나여야 한다)."""
    out = {}
    for _, r in strict.iterrows():
        hit = loose[(loose["i0"] <= r["i0"]) & (loose["i1"] >= r["i1"])]
        if len(hit) != 1:
            raise AssertionError(f"포함 구간 {len(hit)}개: {r['interval_id']}")
        out[r["interval_id"]] = hit["interval_id"].iloc[0]
    return pd.Series(out, dtype=object)

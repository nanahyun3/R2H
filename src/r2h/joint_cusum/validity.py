"""귀무 적합도 게이트 N3·N4 와 통계량별 H0-B 유효성 (계약 §6.3–6.4). N5 는 진단만 한다."""

from __future__ import annotations

from itertools import combinations

import numpy as np

ENV_LO, ENV_HI = 0.005, 0.995
ZERO_SHARE_PASS = 0.02
N3_STATS = ("kurt", "acf_r2", "var", "zero_share")
N4_STATS = ("corr", "coexceed", "rollcorr_sd")


def envelope(null: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """보정 반복 (C, k) → 0.5%·99.5% 경계."""
    return np.nanquantile(null, ENV_LO, axis=0), np.nanquantile(null, ENV_HI, axis=0)


def n3_table(obs: dict[str, np.ndarray], cal: dict[str, np.ndarray], tickers: list[str]) -> list[dict]:
    """ETF 별 N3 판정 행. 정확 0 비율은 관측 ≤ 2% 이면 호가 단위 효과로 통과."""
    rows = []
    for j, tk in enumerate(tickers):
        row: dict = {"ticker": tk}
        ok_all = True
        for s in N3_STATS:
            lo, hi = envelope(cal[f"diag_{s}"])
            v = float(obs[s][j])
            ok = bool(lo[j] <= v <= hi[j])
            if s == "zero_share" and v <= ZERO_SHARE_PASS:
                ok = True
            row.update({f"{s}_obs": v, f"{s}_lo": float(lo[j]), f"{s}_hi": float(hi[j]), f"{s}_ok": ok})
            ok_all &= ok
        row["N3_pass"] = ok_all
        rows.append(row)
    return rows


def n4_table(obs: dict[str, np.ndarray], cal: dict[str, np.ndarray], tickers: list[str]) -> list[dict]:
    """쌍별 N4 판정. 3개 중 2개 이상 벗어나면 그 쌍은 부적합."""
    pairs = list(combinations(range(len(tickers)), 2))
    rows = []
    for p_i, (i, j) in enumerate(pairs):
        row: dict = {"pair": f"{tickers[i]}+{tickers[j]}"}
        fails = 0
        for s in N4_STATS:
            lo, hi = envelope(cal[f"diag_{s}"])
            v = float(obs[s][p_i])
            ok = bool(lo[p_i] <= v <= hi[p_i])
            fails += not ok
            row.update({f"{s}_obs": v, f"{s}_lo": float(lo[p_i]), f"{s}_hi": float(hi[p_i]), f"{s}_ok": ok})
        row["N4_fail_count"] = fails
        row["N4_pass"] = fails < 2
        rows.append(row)
    return rows


def statistic_valid(members: tuple[str, ...], n1_ok: bool, n3: list[dict], n4: list[dict]) -> bool:
    """구성원 전원 N3 통과 · 구성원 쌍 전원 N4 통과 · N1 통과일 때만 H0-B 유효."""
    if not n1_ok:
        return False
    etf_ok = {r["ticker"]: r["N3_pass"] for r in n3}
    pair_ok = {r["pair"]: r["N4_pass"] for r in n4}
    if not all(etf_ok[t] for t in members):
        return False
    for a, b in combinations(members, 2):
        key = f"{a}+{b}" if f"{a}+{b}" in pair_ok else f"{b}+{a}"
        if not pair_ok[key]:
            return False
    return True

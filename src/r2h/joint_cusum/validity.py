# ruff: noqa: E501  — 한국어 설명·표 머리 문자열
"""귀무 적합도 게이트 (계약 W3-lock-2 §6.3–6.4, 승인서 §10 진단).

연도 모형 y (y 이전 자료로 적합) 마다 관측 통계(자료 < y) 를 모의 경로의 같은 구간 통계 envelope 와 비교한다.
한 통계는 5개 연도 중 2개 이상에서 벗어날 때 탈락한다 (연도별 1% 우연 탈락이 누적되는 것을 막는 사전 규칙).
N5 (주변 CUSUM 본체) 는 진단만 하고 게이트로 쓰지 않는다.
"""

from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd

ENV_LO, ENV_HI = 0.005, 0.995
ZERO_SHARE_PASS = 0.02
MIN_YEARS_FAIL = 2
LB_P_MIN = 0.01
N3_STATS = ("kurt", "acf_r2", "var", "zero_share")
N4_STATS = ("corr", "coexceed", "rollcorr_sd")


def _outside(obs: np.ndarray, cal: np.ndarray) -> np.ndarray:
    """obs (연도, k), cal (반복, 연도, k) → 연도·항목별 envelope 밖 여부."""
    lo = np.nanquantile(cal, ENV_LO, axis=0)
    hi = np.nanquantile(cal, ENV_HI, axis=0)
    return (obs < lo) | (obs > hi), lo, hi


def n1_tables(n1: pd.DataFrame, n_etf: int) -> tuple[np.ndarray, bool]:
    """N1 (DCC, 모든 연도): ETF 별 주변 통과 여부와 결합(a, b, ν, Q̄) 통과 여부."""
    d = n1[n1.model.eq("DCC")]
    etf_ok = np.array([bool(d[d.check.str.startswith(f"margin{j}_")].ok.all()) for j in range(n_etf)])
    joint_ok = bool(d[~d.check.str.startswith("margin")].ok.all())
    return etf_ok, joint_ok


def n3_table(
    obs: dict[str, np.ndarray],
    cal: dict[str, np.ndarray],
    lb: pd.DataFrame,
    n1_etf_ok: np.ndarray,
    tickers: list[str],
    years: list[int],
) -> list[dict]:
    """ETF 별 N3: 4개 통계 (연도 2개 이상 이탈 시 탈락, 정확 0 비율은 관측 ≤ 2% 인 연도 통과) + Ljung–Box(z, z²) + N1 주변."""
    rows = []
    for j, tk in enumerate(tickers):
        row: dict = {"ticker": tk}
        ok_all = bool(n1_etf_ok[j])
        row["N1_margin_ok_all_years"] = ok_all
        for s in N3_STATS:
            out, lo, hi = _outside(obs[s], cal[f"diag_{s}"])
            o = out[:, j].copy()
            if s == "zero_share":
                o &= obs[s][:, j] > ZERO_SHARE_PASS
            bad_years = [y for y, b in zip(years, o, strict=True) if b]
            fail = len(bad_years) >= MIN_YEARS_FAIL
            row.update(
                {
                    f"{s}_years_outside": ",".join(map(str, bad_years)) or "-",
                    f"{s}_ok": not fail,
                    f"{s}_obs_last": float(obs[s][-1, j]),
                    f"{s}_lo_last": float(lo[-1, j]),
                    f"{s}_hi_last": float(hi[-1, j]),
                }
            )
            ok_all &= not fail
        g = lb[lb.ticker.eq(tk)]
        for c in ("lb10_z_p", "lb10_z2_p"):
            bad = g[g[c] < LB_P_MIN].year.tolist()
            fail = len(bad) >= MIN_YEARS_FAIL
            row.update({f"{c}_years_below_0.01": ",".join(map(str, bad)) or "-", f"{c}_ok": not fail})
            ok_all &= not fail
        row["N3_pass"] = ok_all
        rows.append(row)
    return rows


def n4_table(
    obs: dict[str, np.ndarray], cal: dict[str, np.ndarray], tickers: list[str], years: list[int]
) -> list[dict]:
    """쌍별 N4: 통계마다 연도 2개 이상 이탈 시 탈락, 3개 중 2개 이상 탈락하면 그 쌍 부적합."""
    pairs = list(combinations(range(len(tickers)), 2))
    rows = []
    for p_i, (i, j) in enumerate(pairs):
        row: dict = {"pair": f"{tickers[i]}+{tickers[j]}"}
        fails = 0
        for s in N4_STATS:
            out, _, _ = _outside(obs[s], cal[f"diag_{s}"])
            bad_years = [y for y, b in zip(years, out[:, p_i], strict=True) if b]
            fail = len(bad_years) >= MIN_YEARS_FAIL
            fails += fail
            row.update(
                {
                    f"{s}_years_outside": ",".join(map(str, bad_years)) or "-",
                    f"{s}_ok": not fail,
                    f"{s}_obs_last": float(obs[s][-1, p_i]),
                }
            )
        row["N4_fail_count"] = fails
        row["N4_pass"] = fails < 2
        rows.append(row)
    return rows


def statistic_valid(members: tuple[str, ...], joint_ok: bool, n3: list[dict], n4: list[dict]) -> bool:
    """결합 N1 통과 · 구성원 전원 N3 통과 · 구성원 쌍 전원 N4 통과일 때만 H0-B 유효."""
    if not joint_ok:
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

"""W4 Peer 상대 변동성 급변 상태 — 연환산 변동성·과거 분위·A·B·그룹·17/17·구간 (계약 W4-lock-1 §3–§8).

모든 함수는 순수 계산이며 파일을 읽지 않는다. 시점 규칙:
날짜 t 의 σ 는 t 종가까지의 수익률만 쓰고, 분위의 기준집합은 t 보다 엄밀히 앞선 날짜의 유효값이다.
3값 논리는 float 배열로 표현한다: 1.0 = 참, 0.0 = 거짓, NaN = 판정 불가(NA).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from r2h.multihorizon.core import midrank_past

L_STATUS = ("OK", "ZERO_VOL_NUMERATOR", "ZERO_VOL_DENOMINATOR", "PEER_INSUFFICIENT_ON_DATE", "VOL_MISSING")


def percent_log_returns_gap(close: pd.Series, scale: float = 100.0) -> pd.Series:
    """r_t = scale·log(C_t/C_{t−1}). 달력상 직전 거래일 종가가 결측이면 r_t 도 결측 (전일값 채우기 없음)."""
    c = close.astype(float)
    if (c <= 0).any():
        raise ValueError("종가에 비양수가 있습니다")
    return scale * np.log(c / c.shift(1))


def annualized_vol(r: np.ndarray, q: int, ann: int = 252, ddof: int = 1) -> np.ndarray:
    """σ_t = √ann · std(r_{t−q+1..t}, ddof). 창 안에 결측이 하나라도 있으면 NaN."""
    s = pd.Series(np.asarray(r, float))
    return np.sqrt(ann) * s.rolling(q, min_periods=q).std(ddof=ddof).to_numpy()


def and3(*xs: np.ndarray) -> np.ndarray:
    """3값 AND: 하나라도 0 → 0, 모두 1 → 1, 그 외 NA."""
    m = np.vstack([np.asarray(x, float) for x in xs])
    out = np.full(m.shape[1], np.nan)
    out[(m == 0).any(axis=0)] = 0.0
    out[(m == 1).all(axis=0)] = 1.0
    return out


def or3(*xs: np.ndarray) -> np.ndarray:
    """3값 OR: 하나라도 1 → 1, 모두 0 → 0, 그 외 NA."""
    m = np.vstack([np.asarray(x, float) for x in xs])
    out = np.full(m.shape[1], np.nan)
    out[(m == 0).all(axis=0)] = 0.0
    out[(m == 1).any(axis=0)] = 1.0
    return out


def upper_flag(u: np.ndarray, thr: float) -> np.ndarray:
    """1[u ≥ thr], u 가 NaN 이면 NA."""
    u = np.asarray(u, float)
    return np.where(np.isfinite(u), (u >= thr).astype(float), np.nan)


def lower_flag(u: np.ndarray, thr: float) -> np.ndarray:
    """1[u ≤ thr], u 가 NaN 이면 NA."""
    u = np.asarray(u, float)
    return np.where(np.isfinite(u), (u <= thr).astype(float), np.nan)


def peer_log_ratio(
    own_adj: np.ndarray, peers_adj: np.ndarray, min_valid: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """L = log(σ_adj(i) / median_j σ_adj(j)). peers_adj 는 (n_dates, n_peer).

    반환 (L, peer_median, n_valid, status). 영분산은 epsilon 없이 NaN + 사유.
    """
    own = np.asarray(own_adj, float)
    p = np.asarray(peers_adj, float).reshape(own.size, -1)
    n_valid = np.isfinite(p).sum(axis=1)
    med = np.full(own.size, np.nan)
    has = n_valid > 0
    med[has] = np.nanmedian(p[has], axis=1)
    status = np.full(own.size, "OK", dtype=object)
    status[~np.isfinite(own)] = "VOL_MISSING"
    status[np.isfinite(own) & (n_valid < min_valid)] = "PEER_INSUFFICIENT_ON_DATE"
    ok = status == "OK"
    status[ok & (own == 0)] = "ZERO_VOL_NUMERATOR"
    ok = status == "OK"
    status[ok & (med == 0)] = "ZERO_VOL_DENOMINATOR"
    ok = status == "OK"
    L = np.full(own.size, np.nan)
    L[ok] = np.log(own[ok] / med[ok])
    return L, med, n_valid, status


def etf_state_table(
    dates: pd.DatetimeIndex,
    sigma: dict[str, dict[int, np.ndarray]],
    ticker: str,
    peers: list[str],
    min_valid: int,
    mult: dict[str, float],
    q_list: list[int],
    p: dict,
) -> pd.DataFrame:
    """한 평가 ETF 의 (date, q) 긴 표: σ, σ_adj, U_A, A, Peer 중앙값, L, U_B, B_UP/B_DOWN/B, AB.

    p: A_upper, B_lower, B_upper, min_ref, max_ref(None=확장형).
    """
    frames = []
    for q in q_list:
        s = sigma[ticker][q]
        s_adj = s / abs(mult.get(ticker, 1.0))
        pa = np.column_stack([sigma[j][q] / abs(mult.get(j, 1.0)) for j in peers])
        ua, nra, ta = midrank_past(s, p["min_ref"], p.get("max_ref"))
        L, med, nv, st = peer_log_ratio(s_adj, pa, min_valid)
        ub, nrb, tb = midrank_past(L, p["min_ref"], p.get("max_ref"))
        a = upper_flag(ua, p["A_upper"])
        bu = upper_flag(ub, p["B_upper"])
        bd = lower_flag(ub, p["B_lower"])
        b = or3(bu, bd)
        frames.append(
            pd.DataFrame(
                {
                    "date": dates,
                    "ticker": ticker,
                    "q": q,
                    "sigma": s,
                    "sigma_adj": s_adj,
                    "U_A": ua,
                    "n_ref_A": nra,
                    "ties_A": ta,
                    "A": a,
                    "peer_median_adj": med,
                    "n_peer_valid": nv,
                    "L": L,
                    "L_status": st.astype(str),
                    "U_B": ub,
                    "n_ref_B": nrb,
                    "ties_B": tb,
                    "B_UP": bu,
                    "B_DOWN": bd,
                    "B": b,
                    "AB": and3(a, b),
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def pair_ratio_state(s1: np.ndarray, s2: np.ndarray, p: dict) -> pd.DataFrame:
    """Core Pair 비율 L = log(σ1/σ2) 의 과거 양측 꼬리 (KOSPI200 그룹 B)."""
    L, med, nv, st = peer_log_ratio(np.asarray(s1, float), np.asarray(s2, float).reshape(-1, 1), 1)
    u, nr, ti = midrank_past(L, p["min_ref"], p.get("max_ref"))
    bu = upper_flag(u, p["B_upper"])
    bd = lower_flag(u, p["B_lower"])
    return pd.DataFrame({"L": L, "L_status": st.astype(str), "U_B": u, "n_ref_B": nr,
                         "B_UP": bu, "B_DOWN": bd, "B": or3(bu, bd)})


def group_states(
    etf: pd.DataFrame,
    groups: dict[str, list[str]],
    k200_group: str,
    core_pair: tuple[str, str],
    core_ratio: dict[int, pd.DataFrame],
    q_list: list[int],
    k200_mode: str = "core",
    aux: tuple[str, ...] = (),
) -> pd.DataFrame:
    """17개 노출 그룹의 GROUP_A/B/AB (date, q, group) 긴 표.

    KOSPI200: k200_mode='core' → A = A(core1)∧A(core2), B = Core Pair 비율 꼬리.
              k200_mode='four' (민감도) → A = 4종 A 의 AND, B = Core Pair B ∨ aux 의 B (배율 정규화 Peer 비교).
    단일 ETF 그룹: 해당 ETF 의 A·B. 각 그룹은 한 번만 센다.
    """
    out = []
    for q in q_list:
        e = etf[etf["q"] == q]
        by = {t: d.reset_index(drop=True) for t, d in e.groupby("ticker", sort=False)}
        dates = by[core_pair[0]]["date"]
        for g, members in groups.items():
            if g == k200_group:
                a_list = [by[t]["A"].to_numpy() for t in core_pair]
                b_list = [core_ratio[q]["B"].to_numpy()]
                bu = core_ratio[q]["B_UP"].to_numpy()
                bd = core_ratio[q]["B_DOWN"].to_numpy()
                if k200_mode == "four":
                    a_list += [by[t]["A"].to_numpy() for t in aux]
                    b_list += [by[t]["B"].to_numpy() for t in aux]
                    bu = or3(bu, *[by[t]["B_UP"].to_numpy() for t in aux])
                    bd = or3(bd, *[by[t]["B_DOWN"].to_numpy() for t in aux])
                ga = and3(*a_list)
                gb = or3(*b_list)
            else:
                (t,) = members
                ga = by[t]["A"].to_numpy()
                gb = by[t]["B"].to_numpy()
                bu = by[t]["B_UP"].to_numpy()
                bd = by[t]["B_DOWN"].to_numpy()
            out.append(pd.DataFrame({"date": dates, "q": q, "group": g, "GROUP_A": ga, "GROUP_B": gb,
                                     "GROUP_B_UP": bu, "GROUP_B_DOWN": bd, "GROUP_AB": and3(ga, gb)}))
    return pd.concat(out, ignore_index=True)


def global_states(gs: pd.DataFrame, n_groups: int) -> pd.DataFrame:
    """날짜·q 별 GLOBAL_A/B/AB (17/17, 3값) 와 참여·평가 가능 그룹 수."""
    rows = []
    for (q, d), x in gs.groupby(["q", "date"], sort=True):
        if len(x) != n_groups:
            raise AssertionError(f"그룹 수 {len(x)} ≠ {n_groups}")
        rec = {"date": d, "q": q}
        for k in ("A", "B", "AB"):
            v = x[f"GROUP_{k}"].to_numpy()
            rec[f"GLOBAL_{k}"] = and3(*[np.array([z]) for z in v])[0]
            rec[f"n_{k}"] = int((v == 1).sum())
            rec[f"n_eval_{k}"] = int(np.isfinite(v).sum())
        rec["n_B_UP"] = int((x["GROUP_B_UP"].to_numpy() == 1).sum())
        rec["n_B_DOWN"] = int((x["GROUP_B_DOWN"].to_numpy() == 1).sum())
        rows.append(rec)
    return pd.DataFrame(rows)


def final_labels(gl: pd.DataFrame, q_list: list[int]) -> pd.DataFrame:
    """FINAL_SHOCK = GLOBAL_AB(20) ∨ GLOBAL_AB(60) 와 보조 라벨 (3값)."""
    w = {q: gl[gl["q"] == q].set_index("date") for q in q_list}
    q1, q2 = q_list
    idx = w[q1].index
    ab1, ab2 = w[q1]["GLOBAL_AB"].to_numpy(), w[q2]["GLOBAL_AB"].reindex(idx).to_numpy()
    f = pd.DataFrame(index=idx)
    f["GLOBAL_AB_q%d" % q1] = ab1
    f["GLOBAL_AB_q%d" % q2] = ab2
    f["FINAL_SHOCK"] = or3(ab1, ab2)
    f["GLOBAL_A_ANY_HORIZON"] = or3(w[q1]["GLOBAL_A"].to_numpy(), w[q2]["GLOBAL_A"].reindex(idx).to_numpy())
    f["GLOBAL_B_ANY_HORIZON"] = or3(w[q1]["GLOBAL_B"].to_numpy(), w[q2]["GLOBAL_B"].reindex(idx).to_numpy())
    f["GLOBAL_AB_BOTH_HORIZONS"] = and3(ab1, ab2)
    f["GLOBAL_AB_%d_ONLY" % q1] = and3(ab1, 1 - ab2)
    f["GLOBAL_AB_%d_ONLY" % q2] = and3(ab2, 1 - ab1)
    return f.reset_index().rename(columns={"index": "date"})


def intervals(dates: pd.Series, flag: np.ndarray, gs_ab_count: np.ndarray | None = None) -> pd.DataFrame:
    """FINAL=1 연속일 → 구간. 갭 병합·완충 없음. NA 는 연속성을 끊는 경계.

    종료 사유: 다음 날 0 → GLOBAL_CONDITION_EXITED (+ 그날 AB 그룹 0 이면 ALL_GROUPS_NORMALIZED), NA → NOT_EVALUABLE.
    """
    f = np.asarray(flag, float)
    d = pd.to_datetime(pd.Series(dates)).reset_index(drop=True)
    n = f.size
    rows, t = [], 0
    while t < n:
        if f[t] == 1:
            s = t
            while t + 1 < n and f[t + 1] == 1:
                t += 1
            e = t
            if e + 1 >= n:
                exit_reason = "RIGHT_CENSORED"
            elif np.isnan(f[e + 1]):
                exit_reason = "NOT_EVALUABLE"
            else:
                exit_reason = "GLOBAL_CONDITION_EXITED"
                if gs_ab_count is not None and gs_ab_count[e + 1] == 0:
                    exit_reason += "|ALL_GROUPS_NORMALIZED"
            rows.append({"interval_id": len(rows) + 1, "start": d[s].date(), "end": d[e].date(),
                         "duration_trading_days": e - s + 1,
                         "left_censored": s == 0, "right_censored": e == n - 1,
                         "entry_after": "START" if s == 0 else ("NA" if np.isnan(f[s - 1]) else "0"),
                         "exit_reason": exit_reason})
        t += 1
    cols = ["interval_id", "start", "end", "duration_trading_days", "left_censored", "right_censored",
            "entry_after", "exit_reason"]
    return pd.DataFrame(rows, columns=cols)


def year_status(year: int, cfg: dict) -> str:
    if year in cfg["core_years"]:
        return "PRIMARY"
    if year == cfg["pilot_year"]:
        return "PILOT"
    if year == cfg["partial_year"]:
        return "PARTIAL_NON_BLIND"
    return "REFERENCE_ONLY"


def verdict(final: pd.DataFrame, cfg: dict, min_evaluable_share: float = 0.5) -> dict:
    """계약 §10 판정. 주 분석기간(2021–2025)만 본다."""
    yr = pd.to_datetime(final["date"]).dt.year
    prim = final[yr.isin(cfg["core_years"])]
    f = prim["FINAL_SHOCK"].to_numpy()
    n = int(f.size)
    n_eval = int(np.isfinite(f).sum())
    n_true = int((f == 1).sum())
    share = n_eval / n if n else 0.0
    if n_true > 0:
        v = "LABELS_GENERATED"
    elif share >= min_evaluable_share:
        v = "VALID_ZERO_INTERVALS"
    else:
        v = "INSUFFICIENT_PEER_COVERAGE"
    return {"verdict": v, "primary_days": n, "primary_evaluable_days": n_eval,
            "primary_evaluable_share": share, "primary_final_true_days": n_true}

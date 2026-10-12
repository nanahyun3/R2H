"""다축 evidence profile (PROTOCOL_LOCK L7) — 사전 고정 규칙만 적용한다. 원인 판정을 하지 않는다.

입력은 병합된 결과표. 출력 ``diagnostic_profile.csv`` 의 각 행은 (ticker, year, policy) 의 V/M/N/C/H 플래그와
보수적 종합 상태, 근거 행 참조, 미해결 질문을 담는다.
"""

from __future__ import annotations

from typing import Any, cast

import numpy as np
import pandas as pd


def _flags(items: list[tuple[bool, str]]) -> str:
    return "|".join(name for cond, name in items if cond)


def build_profile(t: dict[str, pd.DataFrame], cfg: dict) -> pd.DataFrame:
    fr = cfg["flag_rules"]
    vol: Any = t["annual_vol_diagnostics"].set_index(["ticker", "year"])
    fc: Any = t["annual_forecast_diagnostics"].set_index(["ticker", "year", "policy"])
    rs: Any = t["annual_residual_diagnostics"].set_index(["ticker", "year", "policy"])
    ph: Any = t["annual_posthoc"].set_index(["ticker", "year", "policy", "calibration_method"])
    cu = t["annual_cusum_diagnostics"]
    ab = t["annual_history_ablation"]
    rows = []
    f: Any
    for key, f in fc.iterrows():
        tk, yr, pol = cast(tuple[str, int, str], key)
        v: Any = vol.loc[(tk, yr)]
        r: Any = rs.loc[(tk, yr, pol)]
        V = _flags(
            [
                (v.rv_ratio >= fr["rv_up_ratio"], "RV_UP"),
                (v.rv_ratio <= fr["rv_down_ratio"], "RV_DOWN"),
                (v.rv_prior_quantile >= fr["rv_high_prior_quantile"], "RV_HIGH_VS_HISTORY"),
            ]
        )
        base_q = fc.loc[(tk, yr, "base"), "oos_qlike"]
        M = _flags(
            [
                (f.mean_sq_standardized_residual >= fr["calib_under_mean_e2"], "VAR_UNDERPREDICTED"),
                (f.mean_sq_standardized_residual <= fr["calib_over_mean_e2"], "VAR_OVERPREDICTED"),
                (pol != "base" and f.oos_qlike > base_q, "QLIKE_WORSE_THAN_BASE"),
                (f.coverage < fr["low_coverage"], "LOW_COVERAGE"),
            ]
        )
        N = _flags(
            [
                (bool(r.get("ljungbox_e2_q", np.nan) < cfg["diagnostics"]["bh_alpha"]), "E2_DEPENDENCE"),
                (bool(r.get("archlm_q", np.nan) < cfg["diagnostics"]["bh_alpha"]), "ARCH_EFFECT"),
                (bool(r.get("excess_kurtosis", np.nan) > fr["heavy_tail_excess_kurtosis"]), "HEAVY_TAIL"),
            ]
        )
        T = float(ph.loc[(tk, yr, pol, "asymptotic"), "annual_T"])
        rej = {
            m: ph.loc[(tk, yr, pol, m), "annual_reject"]
            for m in ("asymptotic", "iid_insample", "iid_prequential")
        }
        rej_known = {
            m: bool(x) for m, x in rej.items() if isinstance(x, (bool, np.bool_)) or x in (True, False)
        }
        flip_cal = len(set(rej_known.values())) > 1
        sel = cu[
            (cu.ticker == tk)
            & (cu.year == yr)
            & (cu.policy == pol)
            & (cu.calibration_method == "iid_insample")
        ]
        pure = sel[sel.boundary_mode == "YEAR_CONTAINED"].set_index("window")
        carry = sel[sel.boundary_mode == "CARRY"].set_index("window")
        eps_by_w: dict[Any, Any] = pure["rolling_episodes"].to_dict()
        win_any = {
            w: bool(eps_by_w[w] > 0) for w in (20, 30, 60, 120) if w in eps_by_w and pd.notna(eps_by_w[w])
        }
        flip_win = len(set(win_any.values())) > 1
        p60: Any = pure.loc[60] if 60 in pure.index else None
        c60: Any = carry.loc[60] if 60 in carry.index else None
        flip_bnd = (
            p60 is not None
            and c60 is not None
            and pd.notna(p60.rolling_episodes)
            and (p60.rolling_episodes > 0) != (c60.rolling_episodes > 0)
        )
        exceed = (
            p60 is not None
            and pd.notna(p60.rolling_episodes)
            and pd.notna(p60.expected_null_episodes)
            and p60.rolling_episodes
            >= fr["alarms_exceed_null_ratio"] * max(p60.expected_null_episodes, 1e-12)
            and p60.rolling_episodes > 0
        )
        C = _flags(
            [
                (bool(rej["asymptotic"]), "ANNUAL_REJECT_ASYM"),
                (flip_cal, "VERDICT_FLIPS_CALIBRATION"),
                (flip_win, "VERDICT_FLIPS_WINDOW"),
                (bool(flip_bnd), "VERDICT_FLIPS_BOUNDARY"),
                (bool(exceed), "ALARMS_EXCEED_NULL"),
            ]
        )
        H = ""
        h_state = "NOT_APPLICABLE_BASELINE"
        if pol != "base":
            a = ab[(ab.ticker == tk) & (ab.year == yr) & (ab.policy == pol)].set_index("history_strategy")
            comp = a[a.h_status == "COMPUTED"]
            others = comp.drop(index="expanding", errors="ignore")
            if others.empty:
                h_state = (
                    "NO_REAL_CONTRAST("
                    + ",".join(f"{s}:{a.loc[s, 'h_status']}" for s in a.index if s != "expanding")
                    + ")"
                )
            else:
                h_state = "CONTRAST:" + ",".join(others.index)
                ref: Any = comp.loc["expanding"]
                H = _flags(
                    [
                        (
                            bool((others.annual_reject_asymptotic != ref.annual_reject_asymptotic).any()),
                            "H_VERDICT_DIFFERS",
                        ),
                        (bool((others.d_qlike_vs_expanding.abs() > fr["h_qlike_gap"]).any()), "H_QLIKE_GAP"),
                    ]
                )
        signal = bool(rej["asymptotic"]) or (
            p60 is not None and pd.notna(p60.rolling_episodes) and p60.rolling_episodes > 0
        )
        axes = [n for n, s in (("V", V), ("M", M), ("N", N), ("H", H)) if s]
        if not signal:
            status = "NO_SIGNAL_DESCRIPTIVE"
        elif len(axes) >= 2:
            status = "MULTIFACTOR"
        elif len(axes) == 1:
            status = "DESCRIPTIVE_EVIDENCE"
        else:
            status = "UNRESOLVED"
        sens = (
            "SENSITIVITY_CONFIRMED"
            if (flip_cal or flip_win or flip_bnd)
            else "STABLE_ACROSS_CHECKED_SETTINGS"
        )
        q = []
        if signal and not axes:
            q.append("signal without any pre-registered V/M/N/H flag")
        if signal and len(axes) >= 2:
            q.append("co-occurring axes cannot be separated on one realized path: " + "+".join(axes))
        if v.year_status != "PRIMARY":
            q.append(str(v.year_status))
        if pol != "base" and h_state.startswith("NO_REAL_CONTRAST"):
            q.append("history effect not identifiable this year")
        rows.append(
            {
                "ticker": tk,
                "year": yr,
                "policy": pol,
                "history_strategy": "expanding" if pol != "base" else "none",
                "year_status": v.year_status,
                "annual_T": T,
                "annual_reject_asym": bool(rej["asymptotic"]),
                "w60_pure_episodes_iid_insample": p60.rolling_episodes if p60 is not None else np.nan,
                "V_flags": V,
                "M_flags": M,
                "N_flags": N,
                "C_flags": C,
                "H_flags": H,
                "h_contrast_state": h_state,
                "signal_present": signal,
                "flagged_axes": "+".join(axes),
                "multi_factor_status": status,
                "sensitivity_status": sens,
                "evidence_refs": (
                    f"vol[{tk},{yr}];forecast[{tk},{yr},{pol}];resid[{tk},{yr},{pol}];"
                    f"posthoc[{tk},{yr},{pol},*];cusum[{tk},{yr},{pol},w*,*];ablation[{tk},{yr},{pol},*]"
                ),
                "unresolved_questions": "; ".join(q),
            }
        )
    return pd.DataFrame(rows)

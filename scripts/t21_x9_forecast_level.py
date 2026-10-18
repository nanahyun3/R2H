"""X9 (EXPLORATORY_EXTENSION, X-D9): 잔차 대신 SVR 예측분산 수준의 변화를 보는 탐지기.

정책 A 는 새 분산 수준을 v̂ 에 빠르게 흡수한다 → 잔차 e 는 변화를 잃지만 v̂ 는 그 변화를 담는다는 가설.
S_t = log v̂_t − mean(log v̂ over [t−252, t−61]) (유효 ≥ 120, 과거만). 상방 S, 하방 −S, 양방향 |S|.
임계 = 귀무(N1 보정 1000 경로) 연 블록 최대의 (1−α) 분위, 크기 = 홀드아웃 500, 검출 = 시나리오 13 × 200 (B1 파이프라인).
v̂ 는 저장 잔차와 같은 시드로 다시 만든 수익률에서 (r/e)^2 로 복원한다 (e=r/√v̂ 이므로 정확히 같다, e=0 인 날은 NaN).
사용: hongik .venv/bin/python scripts/t21_x9_forecast_level.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from r2h.k200_controlled import calib as K  # noqa: E402
from r2h.k200_controlled import core as C  # noqa: E402
from r2h.k200_controlled import mc as MC  # noqa: E402
from r2h.k200_controlled import nullcal as N  # noqa: E402
from r2h.k200_controlled import synth as S  # noqa: E402


def level_stat(logv: np.ndarray, lo: int = 61, hi: int = 252, min_valid: int = 120) -> np.ndarray:
    """(경로, 일) log v̂ → 과거 기준 대비 상대 수준 S (과거 [t−hi, t−lo] 평균)."""
    X = np.atleast_2d(logv)
    ok = np.isfinite(X)
    cs = np.concatenate([np.zeros((X.shape[0], 1)), np.cumsum(np.where(ok, X, 0.0), axis=1)], axis=1)
    cn = np.concatenate([np.zeros((X.shape[0], 1)), np.cumsum(ok, axis=1)], axis=1)
    n = X.shape[1]
    t = np.arange(n)
    a, b = np.clip(t - hi, 0, n), np.clip(t - lo + 1, 0, n)
    m = np.where((cn[:, b] - cn[:, a]) >= min_valid, (cs[:, b] - cs[:, a]) / np.maximum(cn[:, b] - cn[:, a], 1), np.nan)
    return X - m


def logv_of(st: N.MCSet, set_name: str, sc: str, cfg, g, m) -> np.ndarray:
    common = (cfg["seed"], g, m.dates, m.eval_start, "2021-03-02", "2025-09-30", [2020, 2021, 2022, 2023, 2024])
    R = np.stack([MC.regen_returns((set_name, int(rp), sc, *common)) for rp in st.meta["rep"]])
    E = st.E["B1"]
    with np.errstate(divide="ignore", invalid="ignore"):
        v = (R / E) ** 2
    v[~np.isfinite(v) | (v <= 0)] = np.nan
    return np.log(v)


def main() -> None:
    cfg = C.load_cfg(ROOT / "configs" / "t21_k200_cusum_controlled_v1.json")
    m = C.load_market(cfg, ROOT)
    g = S.dgp_for(m, cfg)
    bid = N.block_ids(m)
    blocks = [bid == j for j in range(len(N.YEARS))]
    nd, sd = ROOT / "outputs/t21/mc/n1_null", ROOT / "outputs/t21/mc/n1_scen"
    cal, hold = N.load_set(nd, "null_cal", "S00_null"), N.load_set(nd, "null_hold", "S00_null")
    Sc = level_stat(logv_of(cal, "null_cal", "S00_null", cfg, g, m))
    Sh = level_stat(logv_of(hold, "null_hold", "S00_null", cfg, g, m))
    variants = {"up": lambda x: x, "down": lambda x: -x, "two": np.abs}
    crit, rows = {}, []
    for vn, f in variants.items():
        for al in N.ALPHAS:
            c = C.crit_block_alpha(f(Sc), blocks, al)
            crit[(vn, al)] = c
            A = np.nan_to_num(f(Sh), nan=-np.inf) >= c
            r = C.block_alarm_rate(A, blocks)
            lo, hi = K.cluster_bootstrap_ci(A, blocks, seed=cfg["seed"])
            rows.append({"scenario": "HOLDOUT_SIZE", "variant": vn, "alpha": al, "crit": c, "detection_rate": r, "det_ci_lo": lo, "det_ci_hi": hi})
    for sc in S.SCENARIOS[1:]:
        st = N.load_set(sd, "scen", sc)
        taus = K.parse_taus(st.meta)
        Ss = level_stat(logv_of(st, "scen", sc, cfg, g, m))
        for vn, f in variants.items():
            for al in N.ALPHAS:
                A = np.nan_to_num(f(Ss), nan=-np.inf) >= crit[(vn, al)]
                rec = K.detection_table(A, taus, cfg["synthetic"]["detection_horizon_days"])
                rows.append({"scenario": sc, "variant": vn, "alpha": al, "crit": crit[(vn, al)], **rec})
    df = pd.DataFrame(rows)
    # 관측 자료 (서술용): B1 의 log v̂ 로 같은 통계량과 경보
    from r2h.k200_controlled.policies import run_policies

    paths, _, _ = run_policies(m, ("B1",))
    So = level_stat(np.log(np.where(paths["B1"].vhat > 0, paths["B1"].vhat, np.nan)))[0]
    ed = m.eval_dates
    obs = []
    for vn, f in variants.items():
        for al in N.ALPHAS:
            a = np.nan_to_num(f(So), nan=-np.inf) >= crit[(vn, al)]
            yr = ed.year.to_numpy()
            obs.append({"variant": vn, "alpha": al, "crit": crit[(vn, al)], "valid_days": int(np.isfinite(So).sum()),
                        **{f"alarm_days_{y}": int(a[yr == y].sum()) for y in range(2020, 2026)}})
    res = ROOT / "research/k200_cusum_controlled_12/results"
    df.to_csv(res / "x9_forecast_level_synthetic.csv", index=False, float_format="%.10g", lineterminator="\n")
    pd.DataFrame(obs).to_csv(res / "x9_forecast_level_observed.csv", index=False, float_format="%.10g", lineterminator="\n")
    np.save(ROOT / "outputs/t21/x9_observed_S.npy", So)
    pd.set_option("display.width", 220)
    print(df.pivot_table(index=["variant", "alpha"], columns="scenario", values="detection_rate").round(2).to_string())
    print(pd.DataFrame(obs).to_string(index=False))


if __name__ == "__main__":
    main()

"""크기 검증 진단 (X-D5, 감사 요청 1·2 후속): 보정 표본오차만으로 홀드아웃 경보율이 얼마나 퍼지는가.

보정 경로 1000 개를 복원추출해 임계값을 다시 정하고 같은 홀드아웃 500 경로에 적용한다 (B=300).
또 보정·홀드아웃 역할을 바꿔(홀드아웃으로 보정 → 보정 집합에 적용) 방향을 확인한다. 대표 설정 4개.
사용: hongik .venv/bin/python scripts/t21_size_uncertainty.py
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
from r2h.k200_controlled import nullcal as N  # noqa: E402


def main() -> None:
    cfg = C.load_cfg(ROOT / "configs" / "t21_k200_cusum_controlled_v1.json")
    m = C.load_market(cfg, ROOT)
    bid = N.block_ids(m)
    blocks = [bid == j for j in range(len(N.YEARS))]
    eng = N.Engine()
    nd = ROOT / "outputs/t21/mc/n1_null"
    cal, hold = N.load_set(nd, "null_cal", "S00_null"), N.load_set(nd, "null_hold", "S00_null")
    rng = np.random.default_rng([cfg["seed"], 55])
    rows = []
    for w in (20, 60, 252):
        Tc, Th = eng.rolling(cal.E["B1"], w, None), eng.rolling(hold.E["B1"], w, None)
        bmc = C.block_max(Tc, blocks)  # (1000, 5)
        bmh = C.block_max(Th, blocks)
        for al in N.ALPHAS:
            crit = float(np.quantile(bmc[np.isfinite(bmc)], 1 - al))
            obs = float(np.mean(bmh >= crit))
            boot = []
            for _ in range(300):
                idx = rng.integers(0, bmc.shape[0], bmc.shape[0])
                v = bmc[idx].ravel()
                c = float(np.quantile(v[np.isfinite(v)], 1 - al))
                boot.append(np.mean(bmh >= c))
            swap_c = float(np.quantile(bmh[np.isfinite(bmh)], 1 - al))
            rows.append({"detector": f"rolling_cos_w{w}", "svr": "B1", "alpha": al, "crit_cal": crit, "holdout_rate": obs,
                         "calib_uncert_q025": float(np.quantile(boot, 0.025)), "calib_uncert_q975": float(np.quantile(boot, 0.975)),
                         "consistent_with_calib_noise": bool(np.quantile(boot, 0.025) <= al <= np.quantile(boot, 0.975)),
                         "swap_crit_from_hold": swap_c, "swap_rate_on_cal": float(np.mean(bmc >= swap_c))})
    df = pd.DataFrame(rows)
    out = ROOT / "research/k200_cusum_controlled_12/results/size_calibration_uncertainty.csv"
    df.to_csv(out, index=False, float_format="%.10g", lineterminator="\n")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()

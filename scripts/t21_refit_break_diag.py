"""X-D6 진단 (EXPLORATORY_EXTENSION): 재적합 경계 전후 잔차 척도 단절과, 재적합일 동기 CUSUM 초기화의 효과.

각 SVR 파이프라인의 재적합일마다 직전·직후 40 거래일 평균 e² 비 (log2) 를 재고,
E9 유예 정책에서 2021-01-04 전후 경보가 '두 모형 잔차가 한 창에 섞인 결과' 인지 보려고
재적합일마다 이동 CoS 창을 끊은 변형(재적합 동기 초기화)의 경보를 같은 임계값으로 센다 (서술용).
사용: R2H .venv/bin/python scripts/t21_refit_break_diag.py
"""

from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from r2h.k200_controlled import core as C  # noqa: E402
from r2h.k200_controlled import observed as O  # noqa: E402

H = 40


def main() -> None:
    ob = O.compute(ROOT)
    ed = ob.m.eval_dates
    cal = pickle.load(open(ROOT / "outputs/t21/calib_n1/null_calibration.pkl", "rb"))
    rows, alarm_rows = [], []
    for pl, p in ob.paths.items():
        e2 = p.e**2
        for k, s in enumerate(p.refit_pos[1:], 1):
            pre, post = e2[max(0, s - H) : s], e2[s : s + H]
            rows.append({"pipeline": pl, "refit_date": str(ed[s].date()), "fit_k": k,
                         "pre_mean_e2": float(np.nanmean(pre)), "post_mean_e2": float(np.nanmean(post)),
                         "log2_ratio": float(np.log2(np.nanmean(post) / np.nanmean(pre))),
                         "eps_before": p.fits[k - 1]["eps"], "eps_after": p.fits[k]["eps"],
                         "C_before": p.fits[k - 1]["C"], "C_after": p.fits[k]["C"]})
        crit = cal["res"][(pl, "rolling_cos", "60", "none")]["crit"][0.05]
        T0 = C.rolling_segmented(p.e, 60, [])
        T1 = C.rolling_segmented(p.e, 60, p.refit_pos[1:])
        for lab, T in (("no_reset", T0), ("refit_synced_reset", T1)):
            al = np.nan_to_num(T, nan=-np.inf) >= crit
            yr = ed.year.to_numpy()
            alarm_rows.append({"pipeline": pl, "variant": lab, "crit_a05_B_cfg": crit, "valid_days": int(np.isfinite(T).sum()),
                               "alarm_days_2020": int(al[yr == 2020].sum()), "alarm_days_2021_2025": int(al[yr >= 2021].sum()),
                               "alarm_days_2021_JanFeb": int(al[(ed >= "2021-01-01") & (ed < "2021-03-01")].sum())})
    res = ROOT / "research/k200_cusum_controlled_12/results"
    br, al = pd.DataFrame(rows), pd.DataFrame(alarm_rows)
    br.to_csv(res / "refit_boundary_breaks.csv", index=False, float_format="%.10g", lineterminator="\n")
    al.to_csv(res / "refit_synced_reset_alarms.csv", index=False, float_format="%.10g", lineterminator="\n")
    pd.set_option("display.width", 220)
    print(br[br.refit_date.str.startswith(("2020-0", "2021-01"))].round(3).to_string(index=False))
    print(al.to_string(index=False))


if __name__ == "__main__":
    main()

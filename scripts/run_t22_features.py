"""12B P05 — 증분 정보 (원시 변동성 + SVR 예측으로 설명되지 않는 CUSUM 정보, G9).

출력: results/feature_incremental_information.csv
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from r2h.k200_overlay import align as A  # noqa: E402
from r2h.k200_overlay import features as F  # noqa: E402

BASE = ROOT / "research/k200_cusum_overlay_12b"
OUT = ROOT / "outputs/t22"


def main() -> int:
    al = pd.read_parquet(OUT / "policy_market_aligned.parquet")
    ma = pd.read_parquet(OUT / "market_daily_master.parquet")
    x1 = pd.read_csv(BASE / "results/x1_real_daily.csv", parse_dates=["date"])
    assert (x1["date"].to_numpy() == ma["date"].to_numpy()).all()
    extra = {}
    for k in ("X1w_up", "X1w_down"):
        extra[f"{k}_raw"] = x1[k].to_numpy(float)
        extra[f"{k}_pastpct"] = A.past_scores(x1[k].to_numpy(float))[0]
    # 시장 자체 후보 (비교 기준): 변동성 변화율
    with np.errstate(divide="ignore", invalid="ignore"):
        la = np.log(ma["annualized_vol_20"].to_numpy(float))
    extra["market_d20_raw"] = la - np.r_[np.full(20, np.nan), la[:-20]]
    extra["market_absret_raw"] = ma["abs_return"].to_numpy(float)
    out = F.run_all(al, ma, extra)
    out.to_csv(BASE / "results/feature_incremental_information.csv", index=False)
    # 대표 후보 공통 유효일 변형
    rep = ["B1", "E2_w20", "E2_w120", "E2_w252", "B0", "E3_page_up", "E3_page_down", "E3_page_two", "X1_page_up_sn", "X1_page_down_sn", "X1_page_two_sn", "E3_raw_rolling_cos", "E7_refit21", "E7_refit63", "E6_win252"]
    rep = [r for r in rep if r in set(al["experiment_id"])]
    piv = al[al["experiment_id"].isin(rep)].pivot(index="date", columns="experiment_id", values="T_past_pct").reindex(ma["date"])
    feats = {r: piv[r].to_numpy(float) for r in rep}
    feats.update({k: v for k, v in extra.items() if k.endswith("pastpct")})
    y = F.future_target(ma["daily_log_return_pct"].to_numpy(float))
    cv = F.common_day_variant(y, F.base_matrix(ma), feats, ma["date"].dt.year.to_numpy())
    cv.to_csv(BASE / "results/feature_incremental_information_common_days.csv", index=False)
    print("공통일 변형 대표:", rep)
    print(cv[["feature", "exclude_2020_train", "n_common", "gain_pooled", "rel_mse_gain_pooled", "years_positive"]].round(4).to_string())
    ok = out[(out["scale"] == "past_pct") & (out["coverage_status"] == "OK")]
    s = ok.groupby(["exclude_2020_train", "detector_type"])["rel_mse_gain_pooled"].describe()[["count", "mean", "50%", "max"]]
    print(s.round(4).to_string())
    print(out[out["coverage_status"] == "OK"].sort_values("rel_mse_gain_pooled", ascending=False).head(15)[["experiment_id", "scale", "exclude_2020_train", "n_common", "gain_pooled", "rel_mse_gain_pooled", "years_positive"]].round(4).to_string())
    print(out["coverage_status"].value_counts().to_dict())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

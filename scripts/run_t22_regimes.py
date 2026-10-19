"""12B P01b — 연환산변동성 국면(앵커 20·60·120) · 이벤트 A/B · 창 이탈일 (12B-lock-1 사전 등록 정의).

출력: outputs/t22/volatility_regime_daily.parquet · results/{volatility_regime_summary,events_table,window_exits}.csv
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from r2h.k200_overlay import align as A  # noqa: E402
from r2h.k200_overlay import regimes as R  # noqa: E402

OUT = ROOT / "outputs/t22"
RES = ROOT / "research/k200_cusum_overlay_12b/results"


def main() -> int:
    cfg = A.load_cfg()
    ma, full = A.market_master(cfg)
    tabs = [R.regime_table(full, ma["date"].iloc[0], cfg, w) for w in (20, 60, 120)]
    rg = pd.concat(tabs, ignore_index=True)
    if not all((t["date"].to_numpy() == ma["date"].to_numpy()).all() for t in tabs):
        raise AssertionError("국면 날짜축 불일치")
    rg.to_parquet(OUT / "volatility_regime_daily.parquet", index=False)
    s = rg.groupby(["anchor_w", "level_past", "change_past"]).size().rename("days").reset_index()
    s.to_csv(RES / "volatility_regime_summary.csv", index=False)
    ea = R.events_A(ROOT / cfg["frozen_inputs"]["events_11"], ma["date"])
    eb = R.events_B(tabs[0])
    cols = ["interval_id", "event_set", "period", "shock_type", "start", "end", "i_start", "i_end"]
    ev = pd.concat([ea[cols + ["peak_date", "duration"]], eb[cols]], ignore_index=True)
    ev.to_csv(RES / "events_table.csv", index=False)
    R.window_exits(ma).to_csv(RES / "window_exits.csv", index=False)
    print(s.to_string())
    print(ev.to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""합성 데이터 end-to-end 예제 (실제 시세 없음, 네트워크 없음).

실행:  python examples/synthetic_demo.py --out outputs/synthetic_demo.json
같은 config·seed 로 두 번 실행하면 출력 JSON 이 바이트 단위로 같아야 한다 (시각·경로를 출력에 넣지 않는다).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path

import numpy as np
import pandas as pd
import scipy

from r2h import CONTRACT_VERSION, __version__
from r2h.detection import PageCUSUM, VolScaledThreshold
from r2h.evaluation import MatchConfig, event_metrics, match_alarms, validate_ground_truth
from r2h.synthetic import InjectedSurge, ground_truth_from_injections, surge_series

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=ROOT / "configs" / "synthetic_demo.json")
    ap.add_argument("--out", type=Path, default=ROOT / "outputs" / "synthetic_demo.json")
    a = ap.parse_args()
    raw = a.config.read_bytes()
    cfg = json.loads(raw)
    surges = [InjectedSurge(*s) for s in cfg["surges"]]

    returns, gts, data_hash = {}, [], hashlib.sha256()
    for k, t in enumerate(cfg["tickers"]):
        r, cal = surge_series(cfg["n_days"], surges, sigma=cfg["sigma"], seed=cfg["seed"] + k)
        returns[t] = r
        gts.append(ground_truth_from_injections(cal, surges, ticker=t))
        data_hash.update(t.encode() + r.to_numpy().tobytes())
    gt = validate_ground_truth(pd.concat(gts, ignore_index=True))
    dv = data_hash.hexdigest()[:16]

    detectors = [
        VolScaledThreshold(**cfg["detectors"]["vol_scaled_threshold"]),
        PageCUSUM(**cfg["detectors"]["page_cusum_reference"]),
    ]
    mc = MatchConfig(**cfg["match"])
    ticker_years = len(cfg["tickers"]) * cfg["n_days"] / 252
    results = []
    for det in detectors:
        sig = pd.concat(
            [det.run(returns[t], ticker=t, data_version=dv) for t in cfg["tickers"]], ignore_index=True
        )
        alarms, events = match_alarms(sig, gt, cal, mc)
        m = event_metrics(alarms, events, ticker_years)
        results.append(
            {
                "method_id": det.method_id,
                "params_hash": sig["params_hash"].iat[0],
                "n_alarms": int(sig["is_alarm"].sum()),
                "metrics": {
                    k: (
                        None
                        if isinstance(v, float) and np.isnan(v)
                        else round(v, 10)
                        if isinstance(v, float)
                        else v
                    )
                    for k, v in m.as_dict().items()
                },
                "detected_event_ids": sorted(events.loc[events["detected"], "event_id"].tolist()),
            }
        )
        print(
            f"{det.method_id:24s} recall={m.recall:.3f} FP/ticker-yr={m.fp_per_ticker_year:.2f} "
            f"delay_mean={m.delay_mean:.2f} missed={m.n_missed}"
        )

    out = {
        "experiment_id": cfg["experiment_id"],
        "contract_version": CONTRACT_VERSION,
        "r2h_version": __version__,
        "config_sha256": hashlib.sha256(raw).hexdigest(),
        "data_version": dv,
        "seed": cfg["seed"],
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scipy": scipy.__version__,
        },
        "results": results,
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()

"""합성·귀무 Monte Carlo 작업자 — 경로 하나 = 수익률 모의 → 변화점 규칙 전부 → SVR 파이프라인 → 잔차 저장.

CUSUM 계열 탐지기와 임계값 보정은 저장된 잔차 배열에서 따로 한다 (CPU 참조 / GPU 배치). 시드는 (study seed, 집합, rep) 키.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pandas as pd

from . import changepoints as CP
from . import synth as S
from .core import Market, market_from_returns
from .policies import PIPELINES_ALL, PIPELINES_SCENARIO, run_policies

SETS = {
    "null_cal": {"rep0": 0, "scenarios": ("S00_null",), "pipelines": PIPELINES_ALL},
    "null_hold": {"rep0": 100_000, "scenarios": ("S00_null",), "pipelines": PIPELINES_ALL},
    "scen": {"rep0": 200_000, "scenarios": S.SCENARIOS, "pipelines": PIPELINES_SCENARIO},
}


def rep_rng(seed: int, base: int, rep: int, salt: int) -> np.random.Generator:
    return np.random.default_rng([seed, base + rep, salt])


def run_path(args: tuple) -> dict:
    """args = (set_name, rep, scenario, seed, g, dates, eval_start, tau_lo, tau_hi, boundary_years)."""
    set_name, rep, scen, seed, g, dates, es, lo, hi, byears = args
    t0 = time.perf_counter()
    base = SETS[set_name]["rep0"]
    eps = S.base_innovations(g, len(dates), rep_rng(seed, base, rep, 0))
    trng = rep_rng(seed, base, rep, 1)
    tau = S.draw_tau(trng, dates, lo, hi)
    tau_b = S.boundary_tau(trng, dates, byears)
    sd = float(np.sqrt(g.uncond_var))
    ch = S.make_change(scen, len(dates), tau, tau_b, sd)
    r = S.synth_returns(g, eps, ch)
    m: Market = market_from_returns(r, dates, es)
    scores = CP.compute_scores(m.close, m.r)
    trig = CP.all_triggers(scores)
    # 평가 구간 효과일만 (평가 상대 위치) — 저장 용량 절약
    eff = trig["effect_pos"].astype("float64") - es
    trig = trig.assign(effect_rel=eff)[(eff >= 1) & (eff < len(dates) - es)]
    trig = trig[["rule", "q", "gap", "effect_rel", "pctile"]].astype({"effect_rel": "int32"})
    paths, _, nfit = run_policies(m, SETS[set_name]["pipelines"], scores)
    return {
        "set": set_name,
        "rep": rep,
        "scenario": scen,
        "taus_rel": [t - es for t in ch.taus if t < len(dates)],
        "e": {k: p.e for k, p in paths.items()},
        "refits": {k: p.refit_pos for k, p in paths.items()},
        "triggers": trig.assign(set=set_name, rep=rep, scenario=scen),
        "n_fits": nfit,
        "seconds": time.perf_counter() - t0,
    }


def save_results(results: list[dict], out: Path) -> None:
    """(집합, 시나리오, 파이프라인) 별 e 배열 (rep 오름차순) · 트리거 parquet · 메타."""
    out.mkdir(parents=True, exist_ok=True)
    results = sorted(results, key=lambda d: (d["set"], d["scenario"], d["rep"]))
    groups: dict[tuple[str, str], list[dict]] = {}
    for d in results:
        groups.setdefault((d["set"], d["scenario"]), []).append(d)
    meta = []
    for (st, sc), rows in groups.items():
        for pl in rows[0]["e"]:
            np.save(out / f"e__{st}__{sc}__{pl}.npy", np.stack([d["e"][pl] for d in rows]))
        for d in rows:
            meta.append(
                {
                    "set": st,
                    "scenario": sc,
                    "rep": d["rep"],
                    "taus_rel": ";".join(map(str, d["taus_rel"])),
                    "n_fits": d["n_fits"],
                    "seconds": round(d["seconds"], 4),
                    **{f"nrefit_{k}": len(v) for k, v in d["refits"].items()},
                }
            )
    pd.DataFrame(meta).to_csv(out / "meta.csv", index=False)
    trig = pd.concat([d["triggers"] for d in results], ignore_index=True)
    trig.to_parquet(out / "triggers.parquet", index=False)

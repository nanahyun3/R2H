"""실제 069500 — 등록부 실험 전부의 원시 통계량 경로 · 변화점 · SVR 적합 기록 · 사건 반응 (임계값 이전 단계).

임계값·경보·p 값은 MC 귀무가 끝난 뒤 ``calib_observed`` 에서 붙인다. 이 단계의 모든 값은 평가일 t 의 종가까지로 계산된다
(사후 통계량 ``posthoc_full`` 과 11번 사건 구간은 POSTHOC_ONLY).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from . import changepoints as CP
from . import core as C
from . import detectors as D
from . import registry as RG
from .policies import PIPELINES_ALL, run_policies


@dataclass
class Observed:
    m: C.Market
    scores: pd.DataFrame
    trig: pd.DataFrame  # 평가 상대 effect_rel 포함
    cp_effect: dict
    paths: dict
    reg: pd.DataFrame
    raw: dict  # experiment_id → {"T": ..., (page) "code"/"S_up"/"S_dn"}
    resets: dict  # experiment_id → 초기화 위치 목록
    posthoc: dict
    events: pd.DataFrame
    n_fits: int


def cp_effects(trig: pd.DataFrame, es: int, n_eval: int) -> tuple[pd.DataFrame, dict]:
    t = trig.copy()
    t["effect_rel"] = t["effect_pos"].astype("float64") - es
    ok = (t["effect_rel"] >= 1) & (t["effect_rel"] < n_eval)
    t["in_eval"] = ok
    eff = {}
    for (rule, q, g), sub in t[ok].groupby(["rule", "q", "gap"]):
        eff[(rule, float(q), int(g))] = sub["effect_rel"].astype(int).to_numpy()
    for rule in CP.rule_ids():
        for q in CP.QUANTILES:
            for g in CP.GAPS:
                eff.setdefault((rule, float(q), int(g)), np.array([], int))
    return t, eff


def load_events(root: Path, m: C.Market) -> pd.DataFrame:
    """11번 069500 q20 급변 구간 (2020–2025, 평가 상대 위치). 서술용 참조 — 실현변동성 기반이라 라벨이 아니다."""
    iv = pd.read_csv(root / "research/etf_shock_bottomup_11/results/intervals.csv", dtype={"ticker": str})
    iv = iv[(iv["ticker"] == "069500") & (iv["q"] == 20)].copy()
    ed = m.eval_dates
    iv["start"] = pd.to_datetime(iv["start"])
    iv["end"] = pd.to_datetime(iv["end"])
    iv = iv[(iv["start"] >= ed[0]) & (iv["start"] <= ed[-1])]
    iv["i0"] = np.searchsorted(ed, iv["start"])
    iv["i1"] = np.searchsorted(ed, iv["end"])
    return iv[["interval_id", "start", "end", "duration", "period", "shock_type", "peak_date", "i0", "i1"]].reset_index(drop=True)


def compute(root: Path = C.REPO_ROOT) -> Observed:
    cfg = C.load_cfg(root / "configs" / "t21_k200_cusum_controlled_v1.json")
    m = C.load_market(cfg, root)
    es, n_eval = m.eval_start, m.n - m.eval_start
    scores = CP.compute_scores(m.close, m.r)
    trig, eff = cp_effects(CP.all_triggers(scores), es, n_eval)
    paths, _, nfit = run_policies(m, PIPELINES_ALL, scores)
    reg = RG.build()
    r_eval = m.r[es:]
    raw, resets = {}, {}
    for row in reg.itertuples(index=False):
        if row.detector == "posthoc_full":
            continue
        rs = D.reset_positions(m, row.reset, eff)
        e = paths[row.svr].e if row.svr != "NA" else None
        raw[row.experiment_id] = D.raw_statistic(row.detector, e, r_eval, row.w, rs)
        resets[row.experiment_id] = rs
    ph = {}
    for name, p in paths.items():
        full = C.posthoc_full(p.e)
        yr = m.eval_dates.year.to_numpy()
        by_year = {}
        for y in sorted(set(yr)):
            sub = np.where(yr == y, p.e, np.nan)
            by_year[int(y)] = C.posthoc_full(sub)
        ph[name] = {"full": full, "year": by_year}
    return Observed(m, scores, trig, eff, paths, reg, raw, resets, ph, load_events(root, m), nfit)


def event_mask(ev: pd.DataFrame, n: int) -> np.ndarray:
    msk = np.zeros(n, bool)
    for a, b in zip(ev["i0"], ev["i1"]):
        msk[int(a) : int(b) + 1] = True
    return msk


def own_percentile(T: np.ndarray) -> np.ndarray:
    """경로 자신의 유효값 분포에서의 백분위 (척도 무관 비교용, 사후 서술)."""
    out = np.full(T.shape, np.nan)
    ok = np.isfinite(T)
    if ok.sum() < 2:
        return out
    v = T[ok]
    out[ok] = (pd.Series(v).rank(method="average").to_numpy() - 0.5) / v.size
    return out


def raw_summary(ob: Observed) -> pd.DataFrame:
    """실험별 커버리지 · 원시 통계량 분포 · 11번 사건 안/밖 반응 (서술용, 임계값 무관)."""
    n = ob.m.n - ob.m.eval_start
    evm = event_mask(ob.events, n)
    yr = ob.m.eval_dates.year.to_numpy()
    rows = []
    for row in ob.reg.itertuples(index=False):
        eid = row.experiment_id
        if eid not in ob.raw:
            continue
        T = ob.raw[eid]["T"]
        ok = np.isfinite(T)
        pc = own_percentile(T)
        rows.append(
            {
                "experiment_id": eid,
                "valid_days": int(ok.sum()),
                "na_days": int((~ok).sum()),
                "valid_days_2021_2025": int((ok & (yr >= 2021)).sum()),
                "n_resets": len(ob.resets[eid]),
                "T_max": float(np.nanmax(T)) if ok.any() else np.nan,
                "T_mean": float(np.nanmean(T)) if ok.any() else np.nan,
                "T_p95": float(np.nanquantile(T, 0.95)) if ok.any() else np.nan,
                "event_valid_days": int((ok & evm).sum()),
                "event_mean_pctile": float(np.nanmean(pc[evm])) if (ok & evm).any() else np.nan,
                "nonevent_mean_pctile": float(np.nanmean(pc[~evm])) if (ok & ~evm).any() else np.nan,
            }
        )
    return pd.DataFrame(rows)

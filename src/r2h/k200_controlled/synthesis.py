"""합성 대응 비교 — 같은 rep(같은 기저 혁신)에서 부모 대비 검출 차이 · 대응 부트스트랩 95% 구간 · 효과 라벨 (계약 §7–8).

검출 = [τ, τ+60] 안 첫 경보 (경로별 지연 배열, −1 = 미검출). 지연은 검출된 경로만으로 요약한다.
라벨 규칙 (계약 §8, 사전 등록):
- DETECTION_POWER_GAIN: 같은 α 에서 검출률 차이의 대응 95% 구간 하한 > 0
- (반대로 상한 < 0 이면 DETECTION_POWER_LOSS)
- 부모가 크기 수준(검출률 ≤ α 의 Wilson 상한)이고 자식도 그렇다면 LOW_POWER_INCONCLUSIVE
- 초기화 비교의 경우 RESET_TRIGGER_GAIN 은 변화점 초기화가 같은 횟수 무작위 위약보다 높을 때만
"""

from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np
import pandas as pd

from .calib import wilson

PRIMARY = "cp:V20_two:0.99:20"
REPS = 2000


def _rate(d: np.ndarray) -> float:
    return float(np.mean(d >= 0))


def paired(child: np.ndarray, parent: np.ndarray, rng: np.random.Generator) -> tuple[float, float, float]:
    """검출 지시 차이의 대응 부트스트랩 (경로 복원추출)."""
    a, b = (child >= 0).astype(float), (parent >= 0).astype(float)
    diff = a - b
    idx = rng.integers(0, diff.size, size=(REPS, diff.size))
    boot = diff[idx].mean(axis=1)
    return float(diff.mean()), float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))


def comparisons() -> list[dict]:
    """사전 정의한 비교 목록 (부모, 자식, 바꾼 변수, 기대 라벨 종류)."""
    out = []
    for det, w in (("rolling_cos", "60"), ("page_up", "NA"), ("page_down", "NA"), ("page_two", "NA")):
        par = ("B1", det, w, "none")
        for s in ("refit63", "refit21", "win252", "refitV20_g0"):
            out.append({"family": "SVR", "changed": "svr", "parent": par, "child": (s, det, w, "none"), "label_kind": "SVR_REFIT_GAIN"})
        out.append({"family": "E1", "changed": "reset", "parent": par, "child": ("B1", det, w, "annual"), "label_kind": "COVERAGE"})
        out.append({"family": "E5", "changed": "reset", "parent": par, "child": ("B1", det, w, PRIMARY), "label_kind": "RESET"})
        out.append({"family": "E5_placebo", "changed": "reset(cp vs placebo)", "parent": ("B1", det, w, "placebo_random"), "child": ("B1", det, w, PRIMARY), "label_kind": "RESET_TRIGGER_GAIN"})
        out.append({"family": "E8", "changed": "svr+reset", "parent": par, "child": ("refitV20_g0", det, w, PRIMARY), "label_kind": "INTERACTION"})
        out.append({"family": "E8", "changed": "svr", "parent": ("B1", det, w, PRIMARY), "child": ("refitV20_g0", det, w, PRIMARY), "label_kind": "SVR_REFIT_GAIN"})
    for w in ("20", "30", "120", "252"):
        out.append({"family": "E2", "changed": "w", "parent": ("B1", "rolling_cos", "60", "none"), "child": ("B1", "rolling_cos", w, "none"), "label_kind": "WINDOW"})
    for det in ("page_up", "page_down", "page_two"):
        out.append({"family": "E3", "changed": "detector", "parent": ("B1", "rolling_cos", "60", "none"), "child": ("B1", det, "NA", "none"), "label_kind": "STATISTIC"})
        out.append({"family": "X1", "changed": "detector", "parent": ("B1", det, "NA", "none"), "child": ("B1", det + "_sn", "NA", "none"), "label_kind": "EXPLORATORY_EXTENSION"})
    for w in ("20", "60", "120"):
        out.append({"family": "E3_raw", "changed": "detector", "parent": ("B1", "rolling_cos", w, "none"), "child": ("NA", "raw_rolling_cos", w, "none"), "label_kind": "STATISTIC"})
    return out


def effects(calib_dir: Path, seed: int) -> pd.DataFrame:
    delays = pickle.load(open(calib_dir / "synthetic_delays.pkl", "rb"))
    scen = sorted({k[0] for k in delays})
    rng = np.random.default_rng([seed, 77])
    rows = []
    for c in comparisons():
        for sc in scen:
            for al in (0.05, 0.20):
                kp, kc = (sc, *c["parent"], al), (sc, *c["child"], al)
                if kp not in delays or kc not in delays:
                    continue
                dp, dc = delays[kp], delays[kc]
                m, lo, hi = paired(dc, dp, rng)
                rp, rc = _rate(dp), _rate(dc)
                size_hi = wilson(int(round(al * dp.size)), dp.size)[1]
                if lo > 0:
                    lab = "DETECTION_POWER_GAIN"
                    if c["label_kind"] == "RESET_TRIGGER_GAIN":
                        lab = "RESET_TRIGGER_GAIN"
                    elif c["label_kind"] == "SVR_REFIT_GAIN":
                        lab = "SVR_REFIT_GAIN"
                elif hi < 0:
                    lab = "DETECTION_POWER_LOSS"
                elif rp <= size_hi and rc <= size_hi:
                    lab = "LOW_POWER_INCONCLUSIVE"
                else:
                    lab = "NO_EFFECT"
                rows.append({"family": c["family"], "changed_variable": c["changed"], "scenario": sc, "alpha": al,
                             "parent": "|".join(c["parent"]), "child": "|".join(c["child"]),
                             "parent_rate": rp, "child_rate": rc, "diff": m, "ci_lo": lo, "ci_hi": hi,
                             "parent_delay_median": float(np.median(dp[dp >= 0])) if (dp >= 0).any() else np.nan,
                             "child_delay_median": float(np.median(dc[dc >= 0])) if (dc >= 0).any() else np.nan,
                             "label": lab})
    return pd.DataFrame(rows)


def power_summary(det: pd.DataFrame) -> pd.DataFrame:
    """시나리오 × 탐지기(B1·none) 검출률을 크기 대비로 판정: 검출률 Wilson 하한 > α 이면 POWER_ABOVE_SIZE."""
    d = det[(det["reset"] == "none") & det["svr"].isin(["B1", "NA"]) & det["detection_rate"].notna()].copy()
    d["det_lo_gt_alpha"] = d["det_ci_lo"] > d["alpha"]
    d["verdict"] = np.where(d["det_lo_gt_alpha"], "POWER_ABOVE_SIZE", "LOW_POWER_INCONCLUSIVE")
    return d

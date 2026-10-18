"""SVR 정책 10종 정의 (E6–E10) — 변화점 트리거 → 재적합 위치 변환 포함.

관측 자료와 합성 경로가 같은 함수를 지난다. 트리거는 경로 자신의 가격·수익률로만 계산한다.
"""

from __future__ import annotations

import numpy as np

from . import changepoints as CP
from .core import FitCache, Market, SVRPath, SVRPolicy, svr_path

PRIMARY_RULE = ("V20_two", 0.99, 20)  # E8·E9 주 규칙 (계약 고정)
ADAPTIVE_RULE = ("V20_two", 0.95, 20)  # E10
ADAPTIVE_BANDS = ((0.995, 252), (0.99, 504), (0.95, 756))

PIPELINES_ALL: tuple[str, ...] = (
    "B1",
    "win252",
    "win504",
    "win756",
    "refit63",
    "refit21",
    "refitV20_g0",
    "refitV20_g20",
    "refitV20_g60",
    "adaptiveV20",
)
PIPELINES_SCENARIO: tuple[str, ...] = ("B1", "refit63", "refit21", "win252", "refitV20_g0")


def rule_trigger(m: Market, scores, rule: str, q: float, gap: int) -> dict:
    """규칙 트리거 (전체 위치) → 평가 상대 효과일. 평가 시작일(0) 이하와 범위 밖은 제외."""
    tr = CP.triggers(scores[f"{rule}_strength"].to_numpy(float), q, gap)
    t_all = np.asarray(tr["trigger_idx"], int)
    eff = t_all + 1 - m.eval_start  # 확정일 t → 효과일 t+1 (평가 상대)
    keep = (eff >= 1) & (eff < m.n - m.eval_start)
    conf = t_all[keep]
    return {"effect_rel": eff[keep], "trigger_full": conf, "pctile": np.asarray(tr["pctile"], float)[conf]}


def build_policy(name: str, m: Market, scores) -> SVRPolicy:
    if name == "B1":
        return SVRPolicy(label=name)
    if name.startswith("win"):
        return SVRPolicy(window=int(name[3:]), label=name)
    if name.startswith("refit") and name[5:].isdigit():
        return SVRPolicy(schedule=int(name[5:]), label=name)
    if name.startswith("refitV20_g"):
        g = int(name.split("_g")[1])
        t = rule_trigger(m, scores, *PRIMARY_RULE)
        pos = tuple(int(p) + g for p in t["effect_rel"])
        return SVRPolicy(extra_refits=pos, label=name)
    if name == "adaptiveV20":
        t = rule_trigger(m, scores, *ADAPTIVE_RULE)
        pos, wins = [], []
        for p, pc in zip(t["effect_rel"], t["pctile"]):
            for lo, win in ADAPTIVE_BANDS:
                if pc >= lo:
                    pos.append(int(p))
                    wins.append((int(p), win))
                    break
        return SVRPolicy(extra_refits=tuple(pos), window_at=tuple(wins), label=name)
    raise ValueError(name)


def run_policies(m: Market, names: tuple[str, ...], scores=None) -> tuple[dict[str, SVRPath], dict[str, SVRPolicy], int]:
    """같은 FitCache 를 공유해 같은 이력의 적합은 한 번만 한다."""
    scores = CP.compute_scores(m.close, m.r) if scores is None else scores
    cache = FitCache()
    pols = {n: build_policy(n, m, scores) for n in names}
    paths = {n: svr_path(m, p, cache) for n, p in pols.items()}
    return paths, pols, cache.n_fits

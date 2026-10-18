"""MC 잔차 배열 → 탐지기별 귀무 임계값 · 홀드아웃 크기 · 시나리오 검출률/지연 (계약 §6–7, E11).

백엔드: 이동 CoS 와 Page 경보는 ``Backend`` 로 주입한다 (CPU numpy 참조 / GPU torch). 같은 입력이면 경보가 같아야 한다 (G4).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from . import core as C


@dataclass
class Backend:
    name: str
    rolling: Callable[[np.ndarray, int, np.ndarray | None], np.ndarray]  # (E, w, reset_mask) → T
    page_alarm: Callable[[np.ndarray, float, float, np.ndarray | None], np.ndarray]


def _cpu_rolling(E: np.ndarray, w: int, mask: np.ndarray | None) -> np.ndarray:
    out = np.empty_like(E)
    for i in range(E.shape[0]):
        rs = [] if mask is None else np.flatnonzero(mask[i]).tolist()
        out[i] = C.rolling_segmented(E[i], w, rs)
    return out


CPU = Backend("cpu_numpy_float64", _cpu_rolling, C.page_alarm_batch)


def load_e(mc_dir: Path, st: str, sc: str, pl: str) -> np.ndarray:
    return np.load(mc_dir / f"e__{st}__{sc}__{pl}.npy")


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def placebo_random(n: int, count: int, gap: int, rng: np.random.Generator, lo: int = 1) -> list[int]:
    """같은 횟수 · 같은 불응기를 지키는 무작위 초기화 위치 (거절 표집)."""
    for _ in range(1000):
        cand = np.sort(rng.choice(np.arange(lo, n), size=count, replace=False)) if count else np.array([], int)
        if count <= 1 or np.all(np.diff(cand) > gap):
            return cand.tolist()
    # 매우 촘촘하면 등간격으로 대체 (기록용 플래그는 호출자가 남긴다)
    return np.linspace(lo, n - 1, count).astype(int).tolist()


def placebo_shift(effects: list[int], n: int, rng: np.random.Generator, lo: int = 1) -> list[int]:
    """트리거 간격을 보존한 원형 이동 (평가 구간 [lo, n) 안)."""
    if not effects:
        return []
    L = n - lo
    off = int(rng.integers(1, L))
    return sorted(int(lo + (p - lo + off) % L) for p in effects)


def placebo_calendar(n: int, count: int, lo: int = 1) -> list[int]:
    if count == 0:
        return []
    return np.linspace(lo, n - 1, count + 2)[1:-1].round().astype(int).tolist()


def rolling_crit(Tnull: np.ndarray, blocks: list[np.ndarray], alpha: float) -> float:
    return C.crit_block_alpha(Tnull, blocks, alpha)


def first_alarm_after(alarm: np.ndarray, tau: int, horizon: int) -> int | None:
    seg = np.flatnonzero(alarm[tau : tau + horizon + 1])
    return int(seg[0]) if seg.size else None


def detection_table(alarm: np.ndarray, taus: list[list[int]], horizon: int, blocks_pre: bool = True) -> dict:
    """경로별 첫 변화 τ 기준 검출·지연 + τ 이전 경보. 지연은 검출된 경로만."""
    det, delays, pre = [], [], []
    for i, ts in enumerate(taus):
        if not ts:
            continue
        t0 = ts[0]
        d = first_alarm_after(alarm[i], t0, horizon)
        det.append(d is not None)
        if d is not None:
            delays.append(d)
        pre.append(bool(alarm[i, :t0].any()))
    n = len(det)
    k = int(np.sum(det))
    lo, hi = wilson(k, n)
    return {
        "n_paths": n,
        "detected": k,
        "detection_rate": k / n if n else np.nan,
        "det_ci_lo": lo,
        "det_ci_hi": hi,
        "delay_median": float(np.median(delays)) if delays else np.nan,
        "delay_mean": float(np.mean(delays)) if delays else np.nan,
        "pre_tau_alarm_rate": float(np.mean(pre)) if pre else np.nan,
    }


def all_change_detection(alarm: np.ndarray, taus: list[list[int]], horizon: int) -> dict:
    """반복 변화(S09·S10)용: 모든 알려진 변화일 각각의 검출률."""
    hits, tot = 0, 0
    for i, ts in enumerate(taus):
        for t in ts:
            if t >= alarm.shape[1]:
                continue
            tot += 1
            hits += first_alarm_after(alarm[i], t, horizon) is not None
    return {"n_changes": tot, "all_change_detection_rate": hits / tot if tot else np.nan}


def parse_taus(meta: pd.DataFrame) -> list[list[int]]:
    return [[int(x) for x in str(s).split(";") if x not in ("", "nan")] for s in meta["taus_rel"]]


def mask_crossing(T: np.ndarray, reset_mask: np.ndarray, w: int) -> np.ndarray:
    """경로별 초기화: 창 (t−w+1, t] 안에 초기화 위치가 있으면 NaN. 창이 초기화일에서 시작하는 것은 허용.

    분할 계산(``core.rolling_segmented``)과 같다 — 초기화를 넘지 않는 창은 내용이 같기 때문이다.
    """
    T = np.array(T, float, copy=True)
    c = np.cumsum(reset_mask, axis=1)
    lag = np.zeros_like(c)
    lag[:, w - 1 :] = c[:, : c.shape[1] - w + 1]
    T[(c - lag) > 0] = np.nan
    return T

"""등록부 설정 → 탐지기 원시 경로 (관측·합성 공통).

초기화 이름 → 평가 상대 위치, 그리고 (잔차, 설정) → 원시 통계량. 경보·임계값은 보정 단계에서 붙인다.
"""

from __future__ import annotations

import numpy as np

from . import core as C
from .core import Market


def reset_positions(m: Market, reset: str, cp_effect: dict[tuple[str, float, int], np.ndarray] | None = None) -> list[int]:
    """초기화 일정 (E1·E5). cp:<rule>:<q>:<gap> 는 경로 자신의 트리거 효과일 (평가 상대)."""
    ed = m.eval_dates
    n = len(ed)
    yr = ed.year.to_numpy()
    mo = ed.month.to_numpy()
    starts_y = [int(i) for i in np.flatnonzero(np.diff(yr) != 0) + 1]
    if reset in ("none", "NA"):
        return []
    if reset == "annual":
        return starts_y
    if reset == "half_year":
        h = (mo >= 7).astype(int) + 2 * (yr - yr[0])
        return [int(i) for i in np.flatnonzero(np.diff(h) != 0) + 1]
    if reset == "two_year":
        return [p for p in starts_y if (yr[p] - yr[0]) % 2 == 0]
    if reset == "three_year":
        return [p for p in starts_y if (yr[p] - yr[0]) % 3 == 0]
    if reset.startswith("every_"):
        k = int(reset.split("_")[1])
        return list(range(k, n, k))
    if reset.startswith("annual_shift"):
        k = int(reset.replace("annual_shift", ""))
        return [p + k for p in starts_y if p + k < n]
    if reset.startswith("cp:"):
        _, rule, q, g = reset.split(":")
        assert cp_effect is not None
        return [int(p) for p in cp_effect[(rule, float(q), int(g))]]
    raise ValueError(reset)


def raw_statistic(detector: str, e: np.ndarray, r_eval: np.ndarray, w, resets: list[int]) -> dict[str, np.ndarray]:
    """원시 경로. rolling → T, page → S (경보 후 재설정 없는 자유 상태) 와 상태코드."""
    if detector == "rolling_cos":
        return {"T": C.rolling_segmented(e, int(w), resets)}
    if detector == "raw_rolling_cos":
        return {"T": C.rolling_segmented(r_eval, int(w), resets)}
    if detector == "page_up":
        S, code = C.page_free(e, 2.0, resets)
        return {"T": S, "code": code}
    if detector == "page_down":
        S, code = C.page_free(e, 0.5, resets)
        return {"T": S, "code": code}
    if detector == "page_two":
        Su, cu = C.page_free(e, 2.0, resets)
        Sd, cd = C.page_free(e, 0.5, resets)
        return {"T": np.fmax(Su, Sd), "S_up": Su, "S_dn": Sd, "code": np.maximum(cu, cd)}
    raise ValueError(detector)


def reset_mask(n_paths: int, n: int, resets_per_path: list[list[int]]) -> np.ndarray:
    """경로별 초기화 위치 → (경로, 일) bool."""
    M = np.zeros((n_paths, n), dtype=bool)
    for i, rs in enumerate(resets_per_path):
        rs = [p for p in rs if 0 < p < n]
        M[i, rs] = True
    return M

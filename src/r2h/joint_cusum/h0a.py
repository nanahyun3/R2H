"""H0-A 시간 정렬 귀무 (계약 §6.5): ETF·연도마다 변환 하나를 뽑아 그 ETF-연도의 모든 (정책, w) 유효 구간에 적용.

두 방법: 원형 이동(``circular_shift``) · 원형 블록 재표집(``circular_block``, 블록 20). 관측 Q 경로만 재배열하므로
연간 SVR 재적합이 필요 없다. 방법 간 결과를 합산하지 않는다.
"""

from __future__ import annotations

import numpy as np


def transform_Q(
    Q: np.ndarray,
    year_of_day: np.ndarray,
    windows: list[int],
    method: str,
    rng: np.random.Generator,
    block: int = 20,
) -> tuple[np.ndarray, int]:
    """Q (ETF, 정책, 창, 일) → 재배열본과 접합부 인접 유효 칸 수 (진단용).

    변환은 [0,1) 균등 난수로 정의해 창마다 다른 유효 구간 길이 L_w = n_y − (w−1) 에 같은 비율로 적용한다.
    """
    out = np.full_like(Q, np.nan)
    junction = 0
    years = np.unique(year_of_day)
    for i in range(Q.shape[0]):
        for y in years:
            idx = np.flatnonzero(year_of_day == y)
            n_y = idx.size
            if method == "circular_shift":
                frac = rng.random()
                fracs = None
            elif method == "circular_block":
                n_blocks = int(np.ceil(n_y / block))
                fracs = rng.random(n_blocks)
                frac = 0.0
            else:
                raise ValueError(method)
            for w_i, w in enumerate(windows):
                seg = idx[w - 1 :]
                L = seg.size
                if L <= 0:
                    continue
                if fracs is None:
                    o = int(frac * L)
                    src = (np.arange(L) + o) % L
                    junction += 1 if o else 0
                else:
                    starts = (fracs * L).astype(int)
                    src = np.concatenate([(s + np.arange(block)) % L for s in starts])[:L]
                    junction += int(np.sum(np.diff(src) != 1))
                # 고급 색인 축 순서: 양쪽 모두 (L, 정책) 모양
                out[i, :, w_i, seg] = Q[i, :, w_i, seg[src]]
    return out, junction

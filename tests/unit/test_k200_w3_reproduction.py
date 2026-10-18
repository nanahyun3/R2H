"""G0 — 12번 B0 가 08 W3 ``run_pipeline`` 의 069500 정책 A (2021–2025) 와 바이트 동일한지 (원자료가 있을 때만)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(not (ROOT / "data/raw/069500.csv").exists(), reason="원자료 없음 (Git 제외)")


def test_b0_byte_identical_to_w3() -> None:
    from r2h.joint_cusum import pipeline as JP
    from r2h.k200_controlled import core as C
    from r2h.k200_controlled import detectors as D

    cfg = C.load_cfg(ROOT / "configs/t21_k200_cusum_controlled_v1.json")
    m = C.load_market(cfg, ROOT)
    p = C.svr_path(m, C.SVRPolicy())
    T0 = C.rolling_segmented(p.e, 60, D.reset_positions(m, "annual"))
    w3 = JP.load_cfg(ROOT / "configs/t15_joint_cusum_w3_v2.json")
    out = JP.run_pipeline(JP.load_returns(w3, ROOT / "data/raw")[["069500"]], w3)
    msk = np.asarray(m.eval_dates.year >= 2021)
    assert np.array_equal(p.e[msk], out.e[0, 0], equal_nan=True)
    assert np.array_equal(p.vhat[msk], out.vhat[0, 0], equal_nan=True)
    assert np.array_equal(T0[msk], out.T[0, 0, JP.all_windows(w3).index(60)], equal_nan=True)
    ref = pd.read_csv(ROOT / "research/joint_cusum_w3/results/08/individual_cusum_summary.csv", dtype={"ticker": str})
    ref = ref[(ref.ticker == "069500") & (ref.policy == "A") & (ref.w == 60)].iloc[0]
    assert int(np.isfinite(T0[msk]).sum()) == ref.valid_days == 930
    assert int(np.isnan(T0[msk]).sum()) == ref.not_available_days == 295
    assert np.nanmax(T0[msk]) == pytest.approx(ref.max_T, abs=1e-8)

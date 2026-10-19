"""12B 정렬·척도·국면 단위 시험 — G5 (과거 전용 척도는 t 이후 값에 의존하지 않음) · G7 (NA 보존)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from r2h.k200_overlay import align as A
from r2h.k200_overlay import regimes as R
from r2h.k200_overlay import x1 as X
from r2h.k200_controlled import core as C


def test_past_scores_perturbation_g5():
    rng = np.random.default_rng(7)
    x = rng.gamma(2.0, 1.0, 700)
    x[50:80] = np.nan
    k = 400
    p0, r0, c0 = A.past_scores(x)
    y = x.copy()
    y[k:] = rng.normal(100, 50, y.size - k)  # t ≥ k 이후 값만 바꾼다
    p1, r1, c1 = A.past_scores(y)
    assert np.array_equal(p0[:k], p1[:k], equal_nan=True)
    assert np.array_equal(r0[:k], r1[:k], equal_nan=True)
    assert np.array_equal(c0[:k], c1[:k])


def test_past_scores_na_and_min_history_g7():
    x = np.arange(300, dtype=float)
    x[200] = np.nan
    p, rb, code = A.past_scores(x, 252, 120)
    assert np.isnan(p[:120]).all() and (code[:120] == 1).all()  # 과거 유효 120 미만
    assert np.isnan(p[200]) and code[200] == 3  # T 결측은 결측 그대로
    assert p[150] == 1.0  # 단조 증가 → 과거 전부보다 큼


def test_regime_quantiles_past_only():
    rng = np.random.default_rng(3)
    a = rng.lognormal(3, 0.3, 600)
    q0 = R.past_expanding_quantiles(a, (0.5,), 252)
    b = a.copy()
    b[400:] *= 10
    q1 = R.past_expanding_quantiles(b, (0.5,), 252)
    assert np.array_equal(q0[:, :401], q1[:, :401], equal_nan=True)  # t=400 은 a[:400] 만 사용
    assert np.isnan(q0[0, 251]) and np.isfinite(q0[0, 252])


def test_m_hat_matches_selfnorm():
    rng = np.random.default_rng(11)
    e = rng.standard_t(6, 600)
    e[10:20] = np.nan
    m = X.m_hat(e)
    sn = C.selfnorm(e)
    ok = np.isfinite(m) & np.isfinite(e)
    assert np.allclose(sn[ok], e[ok] / np.sqrt(m[ok]), rtol=0, atol=1e-14)
    assert np.array_equal(np.isfinite(sn), np.isfinite(m) & np.isfinite(e))


def test_phase_of():
    assert R.phase_of(-5, 10) == "pre" and R.phase_of(3, 10) == "onset"
    assert R.phase_of(8, 10) == "during" and R.phase_of(30, 10) == "normalization" and R.phase_of(80, 10) == "outside"


def test_posthoc_percentile_keeps_na():
    x = np.array([np.nan, 1.0, 3.0, 2.0])
    p = A.posthoc_percentile(x)
    assert np.isnan(p[0]) and np.allclose(p[1:], [1 / 3, 1.0, 2 / 3])
    assert isinstance(pd.Series(p), pd.Series)

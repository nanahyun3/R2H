"""12번 GPU 커널 단위 시험: CPU 참조와 float64 일치 (NaN 패턴 포함) · Page 경보 완전 일치 · 블록 집계 · OOM 절반 재시도.

torch 가 없는 인터프리터에서는 건너뛴다. GPU 가 없으면 torch CPU 장치로 같은 커널을 시험한다.
"""

from __future__ import annotations

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from r2h.k200_controlled import core as C  # noqa: E402
from r2h.k200_controlled import gpu as G  # noqa: E402
from r2h.svrgarch_etf.rolling import MIN_VALID_FRAC, rolling_cusum  # noqa: E402

DEV = G.default_device()


def _data(R: int = 24, n: int = 400, seed: int = 3) -> np.ndarray:
    """t5 + 랜덤 NaN · 긴 NaN 구간 · ±1 행 (τ̂²=0) · 전부 NaN 행."""
    rng = np.random.default_rng(seed)
    E = rng.standard_t(5, (R, n))
    E[rng.random((R, n)) < 0.04] = np.nan
    E[0, 100:130] = np.nan
    E[1] = np.where(rng.random(n) < 0.5, -1.0, 1.0)
    E[2] = np.nan
    return E


def test_min_valid_frac_matches_reference():
    assert G.MIN_VALID_FRAC == MIN_VALID_FRAC


@pytest.mark.parametrize("w", [20, 60, 252])
def test_rolling_matches_cpu_float64(w):
    E = _data()
    cpu = np.stack([rolling_cusum(e, w) for e in E])
    g = G.rolling_cos_batch(E, w, device=DEV).cpu().numpy()
    assert np.array_equal(np.isnan(cpu), np.isnan(g))
    assert np.allclose(cpu, g, rtol=1e-12, atol=1e-12, equal_nan=True)
    assert np.isnan(g[:, : w - 1]).all() and np.isnan(g[1:3]).all()  # 앞 w−1 · τ̂²=0 · 전부 NaN


def test_rolling_short_series_all_nan():
    g = G.rolling_cos_batch(np.ones((3, 10)), 20, device=DEV).cpu().numpy()
    assert g.shape == (3, 10) and np.isnan(g).all()


def test_rolling_segmented_matches_cpu():
    E, resets = _data(), [150, 260]
    cpu = np.stack([C.rolling_segmented(e, 20, resets) for e in E])
    g = G.rolling_segmented_batch(E, 20, resets, device=DEV).cpu().numpy()
    assert np.allclose(cpu, g, rtol=1e-12, atol=1e-12, equal_nan=True)


def test_page_grid_exact_with_reset_and_nan():
    E = _data()
    rm = np.random.default_rng(5).random(E.shape) < 0.02
    H = np.linspace(0.5, 12.0, 9)
    g = G.page_alarm_grid(E, 2.0, H, rm, device=DEV).cpu().numpy()
    cpu = np.stack([C.page_alarm_batch(E, 2.0, h, rm) for h in H], axis=1)
    assert g.shape == (E.shape[0], H.size, E.shape[1]) and cpu.sum() > 0
    assert np.array_equal(cpu, g)


def test_page_increment_bit_equal():
    E = _data()
    g = G.page_increment_t(torch.as_tensor(E, device=DEV), 1.7).cpu().numpy()
    assert np.array_equal(C.page_increment(E, 1.7), g, equal_nan=True)


def test_page_block_hits_and_block_max():
    E, n_blocks = _data(), 4
    bid = np.minimum(np.arange(E.shape[1]) // 100, n_blocks - 1)
    bid[:7] = -1
    H = np.array([1.0, 4.0, 9.0])
    al = np.stack([C.page_alarm_batch(E, 2.0, h) for h in H], axis=1)
    ref = np.stack([al[:, :, bid == b].any(axis=2) for b in range(n_blocks)], axis=2)
    assert np.array_equal(G.page_block_hits(E, 2.0, H, None, bid, n_blocks, device=DEV).cpu().numpy(), ref)
    T = np.stack([rolling_cusum(e, 20) for e in E])
    bm = G.block_max(torch.as_tensor(T, device=DEV), bid, n_blocks).cpu().numpy()
    assert np.array_equal(C.block_max(T, [bid == b for b in range(n_blocks)]), bm, equal_nan=True)


def test_oom_halves_chunk_and_keeps_result(monkeypatch):
    E = _data(R=40)
    ref = G.rolling_cos_batch(E, 20, device=DEV).cpu().numpy()
    orig = G._rolling_chunk

    def flaky(X, w, mv):  # 실제 OOM 없이 큰 chunk 에서만 실패
        if X.shape[0] > 10:
            raise torch.cuda.OutOfMemoryError("simulated")
        return orig(X, w, mv)

    monkeypatch.setattr(G, "_rolling_chunk", flaky)
    got = G.rolling_cos_batch(E, 20, device=DEV, chunk=40).cpu().numpy()
    assert np.array_equal(ref, got, equal_nan=True)
    assert G.LAST_RUN["oom_retries"] == 2 and G.LAST_RUN["chunk"] == 10


def test_oom_at_chunk_one_raises(monkeypatch):
    def always(X, w, mv):
        raise torch.cuda.OutOfMemoryError("simulated")

    monkeypatch.setattr(G, "_rolling_chunk", always)
    with pytest.raises(torch.cuda.OutOfMemoryError):
        G.rolling_cos_batch(_data(R=4), 20, device=DEV, chunk=4)

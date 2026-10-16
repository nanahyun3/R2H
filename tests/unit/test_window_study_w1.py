"""W1 창·경계·난수·원본 대조의 작은 독립 검증."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from r2h.svrgarch_etf.rolling import episodes, rolling_cusum, window_khat
from r2h.window_study.empirical import frozen_root, verify_frozen
from r2h.window_study.simulation import _assess, _rng, load_cfg

ROOT = Path(__file__).resolve().parents[2]


def test_w252_pure_structurally_unavailable() -> None:
    cfg = load_cfg(ROOT)
    x = np.random.default_rng(7).normal(size=245)
    assert cfg["windows_primary"] == [20, 30, 60, 120]
    assert np.isnan(rolling_cusum(x, 252)).all()
    assert 245 - 252 + 1 < 0


def test_common_days_and_original_window_function() -> None:
    cfg = load_cfg(ROOT)
    x = np.random.default_rng(9).normal(size=245)
    mask = np.arange(len(x)) >= cfg["common_start_zero_based"]
    for w in cfg["windows_primary"]:
        stat = rolling_cusum(x, w)
        assert np.isfinite(stat[mask]).all()
        assert np.isnan(stat[: w - 1]).all()
    assert mask.sum() == 126


def test_episode_gap_and_alarm_at_not_argmax() -> None:
    cfg = load_cfg(ROOT)
    alarm = np.zeros(25, bool)
    alarm[[1, 7, 15]] = True
    assert episodes(alarm, gap=5) == [(1, 7), (15, 15)]
    x = np.random.default_rng(3).normal(size=25)
    assert window_khat(x, 20, 20) is not None
    fake = np.zeros(245)
    fake[122] = 2.0
    one = _assess(fake, 1.0, cfg, break_pos=122)
    assert one["detected_60d"] == 1 and one["delay"] == 0


def test_yearly_max_threshold_exceeds_point_statistic_quantile() -> None:
    x = np.random.default_rng(17).normal(size=(80, 245))
    s = np.array([rolling_cusum(row, 120) for row in x])
    q_max = np.quantile(np.nanmax(s[:, 119:], axis=1), 0.95)
    q_point = np.quantile(s[:, 119], 0.95)
    assert q_max >= q_point
    assert q_max != 1.3397  # 원문 표기값을 자동으로 연중 5%라고 쓰지 않는다.


def test_sha_seed_repeated_and_stage_separated() -> None:
    cfg = load_cfg(ROOT)
    a = _rng(cfg, "detector", "cal", "stable_low_variance_no_change", 0).normal(size=8)
    b = _rng(cfg, "detector", "cal", "stable_low_variance_no_change", 0).normal(size=8)
    c = _rng(cfg, "detector", "eval", "stable_low_variance_no_change", 0).normal(size=8)
    assert np.array_equal(a, b)
    assert not np.array_equal(a, c)


def test_t12_frozen_hashes_and_daily_cache() -> None:
    cfg = load_cfg(ROOT)
    source = frozen_root(ROOT)
    if not source.exists():
        return  # 외부 CI에는 비공개 일별 캐시가 없으므로 로컬 full gate에서 별도 검증.
    report = verify_frozen(ROOT, source, cfg)
    assert report["notebook_count"] == 3
    assert report["raw_sha_count"] == 22
    assert report["daily_ticker_count"] == 20

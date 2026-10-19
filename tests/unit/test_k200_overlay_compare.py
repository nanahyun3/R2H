"""12B 정책 비교 (r2h.k200_overlay.compare) 단위 시험 — 합성 배열."""

from __future__ import annotations

import numpy as np
from scipy.stats import spearmanr

from r2h.k200_overlay import compare as C


def test_valid_state_counting():
    # 부모·자식 유효 패턴 → 네 상태 개수
    vp = np.array([True, True, False, False, True])
    vc = np.array([True, False, True, False, True])
    assert C.count_states(vp, vc) == {"BOTH": 2, "PARENT_ONLY": 1, "CHILD_ONLY": 1, "NEITHER": 1}
    assert list(C.valid_state(vp, vc)) == ["BOTH", "PARENT_ONLY", "CHILD_ONLY", "NEITHER", "BOTH"]


def test_ofat_mapping():
    base = {"policy_id": "B1", "detector_type": "rolling_cos", "window_w": "60", "reset_rule": "none"}
    # 조합 changed_variable → 기대 열
    assert C.expected_cols("svr+reset") == ("policy_id", "reset_rule")
    assert C.expected_cols("calibration") == ()
    # reset 만 바뀐 OFAT
    r = C.ofat_check("reset", base, {**base, "reset_rule": "annual"})
    assert r["ofat_observed"] == "reset_rule" and r["ofat_consistent"]
    # calibration: 네 열 불변 → 일관
    assert C.ofat_check("calibration", base, dict(base))["ofat_consistent"]
    # detector 변경 + window_w 60→NA: 엄격 불일치, 구조적(NA) 보조 판정은 일관
    r = C.ofat_check("detector", base, {**base, "detector_type": "page_up", "window_w": "NA"})
    assert r["ofat_observed"] == "detector_type;window_w"
    assert not r["ofat_consistent"] and r["ofat_consistent_structural"]


def test_spearman_exact_matches_scipy_with_ties_and_nan():
    rng = np.random.default_rng(0)
    T = np.round(rng.normal(size=(4, 400)), 1)  # 반올림으로 동순위 생성
    T[0, :30] = np.nan
    T[1, 50:90] = np.nan
    T[2, ::7] = np.nan
    A = rng.random((4, 400)) < 0.05
    ag = C.pairwise_agreement(T, A, min_n=250)
    for a in range(4):
        for b in range(a + 1, 4):
            m = np.isfinite(T[a]) & np.isfinite(T[b])
            ref = spearmanr(T[a, m], T[b, m]).statistic
            assert abs(ag["spearman_raw"][a, b] - ref) < 1e-10
            assert abs(C.spearman_exact(T[a], T[b])[0] - ref) < 1e-10
            assert ag["n_common"][a, b] == m.sum()
    # 공통일 < min_n → NaN (0 으로 채우지 않음)
    assert np.isnan(C.pairwise_agreement(T, A, min_n=1000)["spearman_raw"][0, 1])


def test_event_phase_precedence():
    import pandas as pd
    ev = pd.DataFrame({"i_start": [2, 10], "i_end": [9, 10]})  # 두 번째 이벤트 onset 이 첫 이벤트 정상화와 겹침
    lab = C.event_phase_labels(ev, 30)
    assert list(lab[2:8]) == ["onset"] * 6 and list(lab[8:10]) == ["during"] * 2
    assert list(lab[10:16]) == ["onset"] * 6  # onset 우선
    assert lab[16] == "normalization" and lab[1] == ""

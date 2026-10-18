"""실험 등록부 — 설정 dict · 부모 · 바꾼 변수 하나 자동 검사 (계약 §4, 게이트 G3).

설정 키: svr · detector · w · reset · calibration. 탐지기에 해당 없는 키는 ``"NA"`` 이며, 부모와의 차이는
양쪽 모두 해당 있는 키 + detector 키로 센다. 차이가 정확히 하나가 아니면 ``CONFOUNDED_COMPARISON``
(``INTERACTION_EXPERIMENT`` 로 등록한 행은 예외).
"""

from __future__ import annotations

import pandas as pd

from .changepoints import rule_ids
from .core import sha16

ROLLING = ("rolling_cos", "raw_rolling_cos")
PAGE = ("page_up", "page_down", "page_two")
PAGE_SN = ("page_up_sn", "page_down_sn", "page_two_sn")
RESET_SCHEDULES = (
    "annual",
    "half_year",
    "two_year",
    "three_year",
    "every_252",
    "every_504",
    "annual_shift21",
    "annual_shift63",
    "annual_shift126",
)
PRIMARY_RESET = "cp:V20_two:0.99:20"
KEYS = ("svr", "detector", "w", "reset", "calibration")


def cfg(svr: str = "B1", detector: str = "rolling_cos", w: int | str = 60, reset: str = "none",
        calibration: str = "garch_t_N1") -> dict:
    if detector in PAGE or detector in PAGE_SN or detector == "posthoc_full":
        w = "NA"
    if detector == "raw_rolling_cos":
        svr = "NA"
    if detector == "posthoc_full":
        reset = "NA"
    return {"svr": svr, "detector": detector, "w": w, "reset": reset, "calibration": calibration}


def diff_keys(a: dict, b: dict) -> list[str]:
    out = []
    for k in KEYS:
        if k == "detector":
            if a[k] != b[k]:
                out.append(k)
        elif a[k] != "NA" and b[k] != "NA" and a[k] != b[k]:
            out.append(k)
    return out


def build() -> pd.DataFrame:
    rows: list[dict] = []

    def add(eid: str, family: str, c: dict, parent: str | None, interaction: bool = False, note: str = "") -> None:
        rows.append({"experiment_id": eid, "family": family, "parent_experiment_id": parent,
                     "interaction": interaction, "note": note, **c})

    add("B1", "BASE", cfg(), None, note="연도 관통 이동창 (앵커)")
    add("B0", "BASE", cfg(reset="annual"), "B1", note="기존 연초 초기화")
    for s in RESET_SCHEDULES[1:]:
        add(f"E1_{s}", "E1_time_split", cfg(reset=s), "B1")
    for w in (20, 30, 120, 252):
        add(f"E2_w{w}", "E2_window", cfg(w=w), "B1")
    for d in (*PAGE, "posthoc_full", "raw_rolling_cos"):
        add(f"E3_{d}", "E3_statistic", cfg(detector=d), "B1")
    for d in PAGE:
        add(f"E1_{d}_annual", "E1_time_split", cfg(detector=d, reset="annual"), f"E3_{d}")
    for rule in rule_ids():
        for q in (0.95, 0.99):
            for g in (0, 10, 20):
                r = f"cp:{rule}:{q}:{g}"
                add(f"E5_rolling_{rule}_q{q}_g{g}", "E5_cp_reset", cfg(reset=r), "B1")
                for d in PAGE:
                    add(f"E5_{d}_{rule}_q{q}_g{g}", "E5_cp_reset", cfg(detector=d, reset=r), f"E3_{d}")
    for s in ("win252", "win504", "win756"):
        add(f"E6_{s}", "E6_train_window", cfg(svr=s), "B1")
        add(f"E6_{s}_page_two", "E6_train_window", cfg(svr=s, detector="page_two"), "E3_page_two")
    for s in ("refit63", "refit21"):
        add(f"E7_{s}", "E7_refit_freq", cfg(svr=s), "B1")
        add(f"E7_{s}_page_two", "E7_refit_freq", cfg(svr=s, detector="page_two"), "E3_page_two")
    add("E8_reset_only", "E8_change_response", cfg(reset=PRIMARY_RESET), "B1")
    add("E8_refit_only", "E8_change_response", cfg(svr="refitV20_g0"), "B1")
    add("E8_reset_and_refit", "E8_change_response", cfg(svr="refitV20_g0", reset=PRIMARY_RESET), "B1", True)
    for d in PAGE:
        add(f"E8_{d}_reset_only", "E8_change_response", cfg(detector=d, reset=PRIMARY_RESET), f"E3_{d}")
        add(f"E8_{d}_refit_only", "E8_change_response", cfg(svr="refitV20_g0", detector=d), f"E3_{d}")
        add(f"E8_{d}_reset_and_refit", "E8_change_response",
            cfg(svr="refitV20_g0", detector=d, reset=PRIMARY_RESET), f"E3_{d}", True)
    for g in (20, 60):
        add(f"E9_grace{g}", "E9_refit_grace", cfg(svr=f"refitV20_g{g}"), "E8_refit_only")
    add("E10_adaptive", "E10_adaptive_window", cfg(svr="adaptiveV20"), "B1")
    for cal in ("asymptotic", "normal_mc", "iid_bootstrap_presample", "block_bootstrap_presample"):
        add(f"E11_{cal}", "E11_calibration", cfg(calibration=cal), "B1")
    add("X_w20_reset", "X_interaction", cfg(w=20, reset=PRIMARY_RESET), "B1", True)
    add("X_refit21_page_two", "X_interaction", cfg(svr="refit21", detector="page_two"), "B1", True)

    for d in PAGE_SN:  # 능동 발견 X1 (DISCOVERY_LOG) — 결과를 본 뒤 추가한 사후 확장
        add(f"X1_{d}", "EXPLORATORY_EXTENSION", cfg(detector=d), f"E3_{d[:-3]}", note="EXPLORATORY_EXTENSION")
    df = pd.DataFrame(rows)
    by_id = {r["experiment_id"]: r for r in rows}
    checks, changed, before, after, hashes, fixed_hash = [], [], [], [], [], []
    for r in rows:
        c = {k: r[k] for k in KEYS}
        hashes.append(sha16(c))
        p = r["parent_experiment_id"]
        if p is None:
            checks.append("ROOT")
            changed.append("")
            before.append("")
            after.append("")
            fixed_hash.append(sha16(c))
            continue
        pc = {k: by_id[p][k] for k in KEYS}
        dk = diff_keys(pc, c)
        if r["interaction"]:
            checks.append("INTERACTION_EXPERIMENT")
        elif len(dk) == 1:
            checks.append("OFAT_OK")
        else:
            checks.append("CONFOUNDED_COMPARISON")
        changed.append("+".join(dk))
        before.append("+".join(str(pc[k]) for k in dk))
        after.append("+".join(str(c[k]) for k in dk))
        fixed_hash.append(sha16({k: c[k] for k in KEYS if k not in dk}))
    df["ofat_check"] = checks
    df["changed_variable"] = changed
    df["value_before"] = before
    df["value_after"] = after
    df["config_hash"] = hashes
    df["fixed_vars_hash"] = fixed_hash
    return df

"""X1 자기정규화 Page — 실데이터 해부 (사용자 요청, 12B D-03). 재적합 없이 저장된 B1 잔차에서 다시 계산해 원장과 대조한다.

X1  : ẽ_t = e_t / √m̂_t, m̂_t = 평가 구간 B1 잔차 e² 의 [t−252, t−61] 평균 (유효 120 미만 NA) → 2020-09-21 부터 값.
X1w : 같은 식이지만 기준창에 2019 fit 0 의 표본내 표준화 잔차를 허용 (2020-01-02 시점에 이미 알려진 정보).
      EXPLORATORY_EXTENSION — 원시 상태만, 보정된 h 없음 (X1 h 는 참조선).
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

from r2h.annual_expanding.fit import fit_annual, insample_variance, standardize
from r2h.k200_controlled import core as C

ROOT = Path(__file__).resolve().parents[3]
LAM_UP, LAM_DN = 2.0, 0.5


def m_hat(e: np.ndarray, lo: int = 61, hi: int = 252, min_valid: int = 120) -> np.ndarray:
    """selfnorm 의 분모 m̂_t (같은 누적합 산식). 유효 < min_valid 이면 NaN."""
    E = np.asarray(e, float)
    sq = np.where(np.isfinite(E), E**2, 0.0)
    ok = np.isfinite(E).astype(float)
    cs = np.r_[0.0, np.cumsum(sq)]
    cn = np.r_[0.0, np.cumsum(ok)]
    t = np.arange(E.size)
    a = np.clip(t - hi, 0, E.size)
    b = np.clip(t - lo + 1, 0, E.size)
    c = cn[b] - cn[a]
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(c >= min_valid, (cs[b] - cs[a]) / c, np.nan)


def fit0_insample(cfg21: dict, expected_hash: str) -> tuple[np.ndarray, pd.DatetimeIndex, str, float]:
    """2019 학습 표본으로 fit 0 를 다시 적합 → 표본내 표준화 잔차 (model_hash 대조) + 먼 입력에서의 예측 (커널 소실 상수)."""
    m = C.load_market(cfg21, ROOT)
    hist = m.r[: m.eval_start]
    af = fit_annual(hist, round(0.7 * hist.size))
    if af.model_hash != expected_hash:
        raise AssertionError(f"fit 0 model_hash 불일치 {af.model_hash} != {expected_hash}")
    e19 = standardize(hist, insample_variance(af.fit, hist))
    # 학습 범위에서 아주 먼 입력 → RBF 커널 기여가 0 이 되어 절편(역변환)만 남는다
    est = af.fit.model.estimator
    far = None
    for dim in (2, 3, 4, 6):
        try:
            far = float(np.ravel(est.predict(np.full((1, dim), 1e6)))[0])
            break
        except ValueError:
            continue
    return e19, m.dates[: m.eval_start], af.model_hash, far


def page_states(e: np.ndarray) -> dict[str, np.ndarray]:
    """자유 상태(경보 후 재설정 없음) 상·하방."""
    su, _ = C.page_free(e, LAM_UP)
    sd, _ = C.page_free(e, LAM_DN)
    return {"up": su, "down": sd}


def alarms(e: np.ndarray, h_up: float, h_dn: float, h_two: tuple[float, float]) -> dict[str, np.ndarray]:
    """경보 경로 (경보 다음날 0). 단측 h 와 양방향 (h_up, h_down) 은 따로 보정된 값. *_path = 경보 후 재설정 상태."""
    su, au = C.page_alarm(e, LAM_UP, h_up)
    sd, ad = C.page_alarm(e, LAM_DN, h_dn)
    return {"up": au, "down": ad, "two": C.page_alarm(e, LAM_UP, h_two[0])[1] | C.page_alarm(e, LAM_DN, h_two[1])[1],
            "up_path": su, "down_path": sd}


def build(cfg: dict, aligned: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """X1 일별 해부표와 검증 기록."""
    cfg21 = json.loads((ROOT / cfg["frozen_inputs"]["t21_config"]).read_text(encoding="utf-8"))
    cal = pickle.load(open(ROOT / cfg["frozen_inputs"]["null_calibration"], "rb"))["res"]
    g = {eid: d.set_index("date") for eid, d in aligned[aligned["experiment_id"].isin(
        ["B1", "E3_page_up", "E3_page_down", "E3_page_two", "X1_page_up_sn", "X1_page_down_sn", "X1_page_two_sn"])].groupby("experiment_id")}
    dates = g["B1"].index
    e = g["B1"]["residual_std"].to_numpy(float)
    fits = pd.read_csv(ROOT / cfg["frozen_inputs"]["refit_boundary_breaks"].replace("refit_boundary_breaks", "svr_fits"))
    h0 = fits[(fits["pipeline"] == "B1") & (fits["fit_k"] == 0)]["model_hash"].iloc[0]
    e19, d19, mh, far = fit0_insample(cfg21, h0)
    mh_x1 = m_hat(e)
    sn = C.selfnorm(e)
    full = np.r_[e19, e]
    mh_w = m_hat(full)[e19.size :]
    snw = C.selfnorm(full)[e19.size :]
    st, stw, st0 = page_states(sn), page_states(snw), page_states(e)
    crit = {k: cal[("B1", k, "NA", "none")]["crit"] for k in ("page_up", "page_down", "page_two", "page_up_sn", "page_down_sn", "page_two_sn")}
    a05 = {lvl: alarms(sn, crit["page_up_sn"][lvl], crit["page_down_sn"][lvl], crit["page_two_sn"][lvl]) for lvl in (0.05, 0.2)}
    w05 = {lvl: alarms(snw, crit["page_up_sn"][lvl], crit["page_down_sn"][lvl], crit["page_two_sn"][lvl]) for lvl in (0.05, 0.2)}
    o05 = {lvl: alarms(e, crit["page_up"][lvl], crit["page_down"][lvl], crit["page_two"][lvl]) for lvl in (0.05, 0.2)}
    df = pd.DataFrame({
        "date": dates, "e_B1": e, "e2_B1": e**2, "m_hat_X1": mh_x1, "m_hat_X1w": mh_w, "e_sn_X1": sn, "e_sn_X1w": snw,
        "E3_up": st0["up"], "E3_down": st0["down"], "X1_up": st["up"], "X1_down": st["down"], "X1w_up": stw["up"], "X1w_down": stw["down"],
    })
    for lvl, tag in ((0.05, "a05"), (0.2, "a20")):
        for k in ("up", "down", "two"):
            df[f"E3_{k}_alarm_{tag}"] = o05[lvl][k]
            df[f"X1_{k}_alarm_{tag}"] = a05[lvl][k]
            df[f"X1w_{k}_alarm_{tag}_REFERENCE"] = w05[lvl][k]
        for k in ("up", "down"):
            df[f"E3_{k}_path_{tag}"] = o05[lvl][f"{k}_path"]
            df[f"X1_{k}_path_{tag}"] = a05[lvl][f"{k}_path"]
            df[f"X1w_{k}_path_{tag}_REFERENCE"] = w05[lvl][f"{k}_path"]
    # 원장 대조 (G6 — X1·E3 원시 상태와 경보)
    chk = {}
    for eid, col in (("E3_page_up", "E3_up"), ("E3_page_down", "E3_down"), ("X1_page_up_sn", "X1_up"), ("X1_page_down_sn", "X1_down")):
        chk[f"{eid}_raw_equal"] = bool(np.array_equal(g[eid]["cusum_raw_T"].to_numpy(), df[col].to_numpy(), equal_nan=True))
        k = col.split("_")[1]
        chk[f"{eid}_alarm_equal"] = bool(np.array_equal(g[eid]["cusum_alarm_a05"].to_numpy(bool), df[f"{col.split('_')[0]}_{k}_alarm_a05"].to_numpy()))
    for eid, pre in (("E3_page_two", "E3"), ("X1_page_two_sn", "X1")):
        chk[f"{eid}_upper_equal"] = bool(np.array_equal(g[eid]["cusum_upper_state"].to_numpy(), df[f"{pre}_up"].to_numpy(), equal_nan=True))
        chk[f"{eid}_lower_equal"] = bool(np.array_equal(g[eid]["cusum_lower_state"].to_numpy(), df[f"{pre}_down"].to_numpy(), equal_nan=True))
        chk[f"{eid}_alarm_equal"] = bool(np.array_equal(g[eid]["cusum_alarm_a05"].to_numpy(bool), df[f"{pre}_two_alarm_a05"].to_numpy()))
    after = df["m_hat_X1"].notna()
    chk.update({
        "fit0_model_hash": mh, "fit0_insample_days": int(e19.size), "fit0_insample_valid": int(np.isfinite(e19).sum()),
        "fit0_insample_mean_e2": float(np.nanmean(e19**2)),
        "fit0_far_input_prediction": far,
        "fit0_max_vhat_2020": float(np.nanmax(g["B1"]["predicted_variance"].to_numpy()[dates.year == 2020])),
        "x1_first_valid": str(dates[np.flatnonzero(after.to_numpy())[0]].date()), "x1_na_days": int((~after).sum()),
        "x1w_first_valid": str(dates[np.flatnonzero(df["m_hat_X1w"].notna().to_numpy())[0]].date()), "x1w_na_days": int(df["m_hat_X1w"].isna().sum()),
        "x1_vs_x1w_state_equal_from": _equal_from(df["X1_up"].to_numpy(), df["X1w_up"].to_numpy(), dates),
        "crit": {k: v for k, v in crit.items()},
    })
    return df, chk


def _equal_from(a: np.ndarray, b: np.ndarray, dates: pd.DatetimeIndex) -> str:
    """두 경로가 그 날 이후로 끝까지 같은 첫 날짜."""
    same = np.isclose(a, b, rtol=0, atol=1e-12) & np.isfinite(a) & np.isfinite(b)
    bad = np.flatnonzero(~same)
    if not bad.size:
        return str(dates[0].date())
    return str(dates[bad[-1] + 1].date()) if bad[-1] + 1 < len(dates) else "NEVER"


def event_table(df: pd.DataFrame, events: pd.DataFrame, crit: dict) -> pd.DataFrame:
    """사건별 [시작, 끝+20] 안 상태의 최대 h 비율 (상·하방) 과 첫 경보일 — 서술용."""
    rows = []
    hu, hd = crit["page_up"][0.05], crit["page_down"][0.05]
    su, sd = crit["page_up_sn"][0.05], crit["page_down_sn"][0.05]
    for _, ev in events.iterrows():
        a, b = int(ev["i_start"]), min(int(ev["i_end"]) + 20, len(df) - 1)
        w = df.iloc[a : b + 1]
        row = {"interval_id": ev["interval_id"], "event_set": ev["event_set"], "shock_type": ev["shock_type"], "period": ev["period"],
               "start": ev["start"], "end": ev["end"]}
        for pre, h_up, h_dn in (("E3", hu, hd), ("X1", su, sd), ("X1w", su, sd)):
            sfx = "_REFERENCE" if pre == "X1w" else ""
            # 자유 상태(2020 누적 이월 포함)와 경보 경로(경보 후 0) 를 따로 본다
            for kind, col_u, col_d in (("free", f"{pre}_up", f"{pre}_down"), ("path", f"{pre}_up_path_a05{sfx}", f"{pre}_down_path_a05{sfx}")):
                row[f"{pre}_up_{kind}_max_over_h"] = float(np.nanmax(w[col_u]) / h_up) if w[col_u].notna().any() else np.nan
                row[f"{pre}_down_{kind}_max_over_h"] = float(np.nanmax(w[col_d]) / h_dn) if w[col_d].notna().any() else np.nan
            col = f"{pre}_up_alarm_a05" if pre != "X1w" else "X1w_up_alarm_a05_REFERENCE"
            hit = np.flatnonzero(w[col].to_numpy())
            row[f"{pre}_up_first_alarm_a05"] = str(w["date"].iloc[hit[0]].date()) if hit.size else ""
            row[f"{pre}_valid_share"] = float(w[f"{pre}_up"].notna().mean())
        rows.append(row)
    return pd.DataFrame(rows)


def forecast_ceiling(svr: pd.DataFrame, min_repeat: int = 5, atol: float = 1e-9) -> pd.DataFrame:
    """적합별로 같은 예측분산이 정확히 min_repeat 일 이상 반복되는 날 = 예측 상수 고정 (커널 소실).

    입력(지연 r²·대용치)이 학습 범위를 벗어나면 RBF 커널 기여가 0 이 되어 예측이 절편 상수에 고정된다
    (fit 0: 먼 입력 예측 = 고정값, ``x1_checks.json``). '상한'이 아니다 — 같은 적합의 최대 v^ 는 더 크다.
    열 이름 ``forecast_ceiling`` 은 호환을 위해 유지 (D-11).
    """
    out = svr[["date", "policy_id", "model_fit_id", "predicted_variance"]].copy()
    out["forecast_ceiling"] = False
    for _, g in out.groupby(["policy_id", "model_fit_id"]):
        v = g["predicted_variance"].round(9)
        vc = v.value_counts()
        for val in vc[vc >= min_repeat].index:
            out.loc[g.index[np.isclose(g["predicted_variance"], val, rtol=0, atol=atol)], "forecast_ceiling"] = True
    return out

"""시장 마스터 · 463 정책 전수 정렬 · 네 가지 척도 (12B-lock-1 §3–§4).

원장(681,999행)을 날짜 m:1 로 시장 마스터에, 실험 m:1 로 등록부에 붙인다. 원장 값은 바꾸지 않고 열을 더하기만 한다.
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

from r2h.k200_controlled import core as C

ROOT = Path(__file__).resolve().parents[3]
CFG12B = ROOT / "configs/t22_k200_overlay_v1.json"
CFG21 = ROOT / "configs/t21_k200_cusum_controlled_v1.json"
ANN = np.sqrt(252.0)
VOL_W = (5, 20, 60, 120, 252)


def load_cfg() -> dict:
    return json.loads(CFG12B.read_text(encoding="utf-8"))


def fs_path(cfg: dict, name: str) -> Path:
    return ROOT / cfg["frozen_inputs"]["feature_store"] / f"{name}.parquet"


def market_master(cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(평가 1,473일 마스터, 2019 포함 전체 수익률 표). 이동 SD 는 전체 수익률에서 계산 후 절단."""
    m = C.load_market(json.loads(CFG21.read_text(encoding="utf-8")), ROOT)
    raw = pd.read_csv(ROOT / cfg["frozen_inputs"]["raw_csv"], dtype={"Date": str})
    px = pd.Series(raw["Close"].astype(float).to_numpy(), index=pd.to_datetime(raw["Date"])).sort_index()
    r = pd.Series(m.r, index=m.dates)
    full = pd.DataFrame({"date": m.dates, "close": m.close, "daily_log_return_pct": m.r})
    for w in VOL_W:
        full[f"rolling_vol_{w}"] = r.rolling(w).std(ddof=1).to_numpy()
        full[f"annualized_vol_{w}"] = ANN * full[f"rolling_vol_{w}"]
    base_date = pd.Timestamp(cfg["market"]["index_base_date"].split()[0])
    c_base = float(px.loc[base_date])
    prev = px.shift(1).reindex(m.dates).to_numpy()
    full["daily_simple_return_pct"] = 100.0 * (full["close"].to_numpy() / prev - 1.0)
    ev = full.iloc[m.eval_start :].reset_index(drop=True)
    ev.insert(0, "ticker", "069500")
    ev["abs_return"] = ev["daily_log_return_pct"].abs()
    ev["squared_return"] = ev["daily_log_return_pct"] ** 2
    ev["daily_realized_variance_proxy"] = ev["squared_return"]
    ev["cumulative_log_return"] = 100.0 * np.log(ev["close"] / c_base)
    ev["indexed_close"] = 100.0 * ev["close"] / c_base
    ev["index_base_date"] = base_date
    # SVR 예측 (B1): v̂ ≤ 0 은 NA
    s = pd.read_parquet(fs_path(cfg, "daily_svr_predictions"))
    b1 = s[s.policy_id == "B1"].set_index("date")["predicted_variance"].reindex(ev["date"]).to_numpy()
    pos = b1 > 0
    ev["predicted_variance_B1"] = b1
    ev["predicted_vol_B1"] = np.where(pos, np.sqrt(np.where(pos, b1, 1.0)), np.nan)
    ev["predicted_vol_annualized_B1"] = ANN * ev["predicted_vol_B1"]
    ev["predicted_vol_status"] = np.where(pos, "OK", "NONPOSITIVE_FORECAST")
    ev["calendar_year"] = ev["date"].dt.year
    return ev, full


# ── 척도 ─────────────────────────────────────────────────────────────


def posthoc_percentile(x: np.ndarray) -> np.ndarray:
    """같은 실험 유효값 안 평균 순위 / n (POSTHOC_DESCRIPTIVE)."""
    out = np.full(x.size, np.nan)
    ok = np.isfinite(x)
    if ok.any():
        out[ok] = pd.Series(x[ok]).rank(method="average").to_numpy() / ok.sum()
    return out


def past_scores(x: np.ndarray, win: int = 252, min_valid: int = 120) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """과거 전용 (t′ ∈ [t−win, t−1]) 백분위 · 로버스트 점수 · 상태코드 (0 OK, 1 INSUFFICIENT_PAST, 2 DEGENERATE, 3 T 결측)."""
    n = x.size
    pad = np.concatenate([np.full(win, np.nan), x])
    W = sliding_window_view(pad, win)[:n]  # W[t] = x[t−win .. t−1]
    ok = np.isfinite(W)
    cnt = ok.sum(axis=1)
    xt = x[:, None]
    with np.errstate(invalid="ignore"):
        less = np.sum(ok & (W < xt), axis=1)
        eq = np.sum(ok & (W == xt), axis=1)
    pct = (less + 0.5 * eq) / np.maximum(cnt, 1)
    q = np.nanquantile(np.where(ok, W, np.nan), [0.25, 0.5, 0.75], axis=1) if n else np.zeros((3, 0))
    iqr = q[2] - q[0]
    code = np.zeros(n, dtype=np.int8)
    code[cnt < min_valid] = 1
    code[(code == 0) & ~(iqr > 1e-12)] = 2
    code[~np.isfinite(x)] = 3
    pct = np.where((cnt >= min_valid) & np.isfinite(x), pct, np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        rob = np.where(code == 0, (x - q[1]) / iqr, np.nan)
    return pct, rob, code


PAST_CODE = {0: "OK", 1: "INSUFFICIENT_PAST", 2: "DEGENERATE_PAST_SCALE", 3: "T_MISSING"}


def h_pairs(cfg: dict) -> dict:
    """(policy, detector, w, reset) → {0.05: h 또는 (h_up, h_down)}."""
    d = pickle.load(open(ROOT / cfg["frozen_inputs"]["null_calibration"], "rb"))["res"]
    return {k: v["crit"] for k, v in d.items() if "crit" in v}


def aligned(cfg: dict, master: pd.DataFrame) -> pd.DataFrame:
    """원장 ⋈ 시장 ⋈ 등록부 + 척도 열. 행 수 = 원장 행 수를 강제."""
    led = pd.read_parquet(fs_path(cfg, "daily_cusum_features"))
    n0 = len(led)
    if led.duplicated(["date", "experiment_id"]).any():
        raise AssertionError("원장 (date, experiment_id) 중복")
    reg = pd.read_csv(ROOT / cfg["frozen_inputs"]["registry"], keep_default_na=False, dtype=str)
    reg = reg[["experiment_id", "parent_experiment_id", "family", "changed_variable", "value_before", "value_after"]]
    mk = master[["date", "close", "indexed_close", "daily_log_return_pct", "cumulative_log_return"] + [f"annualized_vol_{w}" for w in VOL_W]]
    # 원장에도 return_log_pct 가 있으니 시장 열은 이름이 겹치지 않는다
    out = led.merge(mk, on="date", how="left", validate="m:1").merge(reg, on="experiment_id", how="left", validate="m:1")
    if len(out) != n0 or out["close"].isna().any() or out["family"].isna().any():
        raise AssertionError("결합 후 행 수·키 불일치")
    out = out.sort_values(["experiment_id", "date"], kind="mergesort").reset_index(drop=True)
    crit = h_pairs(cfg)
    cols = {k: np.full(len(out), np.nan) for k in ("h_a05", "h_up_a05", "h_down_a05", "T_over_h", "upper_over_h_up", "lower_over_h_down", "T_posthoc_pct", "T_past_pct", "T_past_robust")}
    pcode = np.full(len(out), "", dtype=object)
    for eid, idx in out.groupby("experiment_id", sort=False).indices.items():
        g = out.iloc[idx[0]]
        key = (g["policy_id"], g["detector_type"], str(g["window_w"]), g["reset_rule"])
        T = out["cusum_raw_T"].to_numpy()[idx]
        h = crit.get(key, {}).get(0.05, np.nan)
        if isinstance(h, tuple):
            hu, hd = h
            cols["h_up_a05"][idx], cols["h_down_a05"][idx] = hu, hd
            cols["upper_over_h_up"][idx] = out["cusum_upper_state"].to_numpy()[idx] / hu
            cols["lower_over_h_down"][idx] = out["cusum_lower_state"].to_numpy()[idx] / hd
        else:
            # 단측은 원장 값이 기준 (E11 은 대체 귀무 보정이라 pkl 의 N1 키와 다르다)
            h = float(out["cusum_critical_value_a05"].to_numpy()[idx[0]])
            cols["h_a05"][idx] = h
            cols["T_over_h"][idx] = T / h
        cols["T_posthoc_pct"][idx] = posthoc_percentile(T)
        p, rb, cd = past_scores(T, cfg["scales"]["D_past"]["past_window"], cfg["scales"]["D_past"]["min_past_valid"])
        cols["T_past_pct"][idx], cols["T_past_robust"][idx] = p, rb
        pcode[idx] = [PAST_CODE[int(c)] for c in cd]
    for k, v in cols.items():
        out[k] = v
    out["T_past_status"] = pcode
    out["ratio_label"] = "DESCRIPTIVE_CALIBRATION_REFERENCE"
    out["posthoc_label"] = "POSTHOC_DESCRIPTIVE"
    return out


def check_h_match(al: pd.DataFrame) -> dict:
    """양방향 Page: 12번 원장 h = pkl h_up 인지. 단측은 원장 h 를 그대로 쓰므로 h 없는 실험만 확인."""
    one = al["h_a05"].notna()
    two = al["h_up_a05"].notna()
    a = np.abs(al.loc[one, "h_a05"] - al.loc[one, "cusum_critical_value_a05"]).max()
    b = np.abs(al.loc[two, "h_up_a05"] - al.loc[two, "cusum_critical_value_a05"]).max()
    miss = al.loc[~one & ~two & al["detector_type"].ne("posthoc"), "experiment_id"].unique().tolist()
    return {"max_abs_diff_one_sided": float(a), "max_abs_diff_two_sided_vs_h_up": float(b), "experiments_without_h": miss}

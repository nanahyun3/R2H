"""A-2 Q3·Q5·Q6 — 일별 잔차로 연간·이동창 통계량을 독립 재계산하고, 경보 과소/과다의 기전을 분해한다.

입력: a_seq_1 일별 (`daily.csv.gz`: window=0 행의 r·vhat·e, window=w 행의 T) · 결과표 (seq_golden 사본).

1. (Q3) 연간 T·n·k̂ 를 독립 구현으로 다시 계산해 annual_posthoc (asymptotic 행) 420개와 대조한다
2. (Q3) e = r/√vhat, r = 원자료 독립 수익률 과 대조한다
3. (Q3) w60 PURE 날의 이동창 T 를 그해 e 만으로 다시 계산한다 (PURE 창은 그해 안이라 사전 연도 문맥이 필요 없다).
   결과표의 iid_insample 점별 임계값으로 에피소드를 다시 세어 YEAR_CONTAINED 행과 대조한다
4. (Q5·Q6, EXPLORATORY) 연내 순열: 그해 e 의 순서만 섞는다 (주변분포 보존, 200회).
   관측 vs 순열의 w60 PURE 에피소드 수를 비교해, 경보 수가 귀무 기대와 다른 이유가 순서 의존(군집/역군집)인지 본다.
   이 순열은 사전 등록된 검정이 아니다. 기전 확인용이며 판정에 쓰지 않는다.
   seed: np.random.default_rng([20261016, ticker, year, policy_id])

실행: PYTHONPATH=src <R2H>/.venv/bin/python -I docs/annual_assurance/scripts/a2_dependence.py
"""

from __future__ import annotations

import gzip
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tests" / "assurance"))
from _real import RESULTS, returns_panel, tickers  # noqa: E402

WORK = ROOT / "outputs" / "t12" / "work" / "a_seq_1"
OUT = ROOT / "docs" / "annual_assurance" / "out"
W, GAP, PERMS = 60, 5, 200
POL = ("A", "B", "base")


def cusum_1d(x: np.ndarray) -> tuple[float, int]:
    n = x.size
    s = x**2
    path = np.cumsum(s) - (np.arange(1, n + 1) / n) * s.sum()
    tau2 = np.mean(x**4) - np.mean(s) ** 2
    k = int(np.argmax(np.abs(path)))
    return float(np.abs(path).max() / (np.sqrt(n) * np.sqrt(tau2))), k


def window_T(e: np.ndarray, w: int) -> np.ndarray:
    """PURE 날 (i ≥ w−1) 의 창 통계량. NaN 은 건너뛴 것과 같다. 유효 < ⌈0.9w⌉ → NaN."""
    out = np.full(e.size, np.nan)
    need = int(np.ceil(0.9 * w))
    for i in range(w - 1, e.size):
        seg = e[i - w + 1 : i + 1]
        seg = seg[np.isfinite(seg)]
        if seg.size < need:
            continue
        s = seg**2
        n = seg.size
        path = np.cumsum(s) - (np.arange(1, n + 1) / n) * s.sum()
        tau2 = np.mean(seg**4) - np.mean(s) ** 2
        if tau2 > 0:
            out[i] = np.abs(path).max() / (np.sqrt(n) * np.sqrt(tau2))
    return out


def window_T_finite(x: np.ndarray, w: int) -> np.ndarray:
    """결측 없는 배열의 창 통계량 (벡터화). 길이 n−w+1."""
    from numpy.lib.stride_tricks import sliding_window_view

    if x.size < w:
        return np.empty(0)
    win = sliding_window_view(x, w)
    s = win**2
    path = np.cumsum(s, axis=1) - (np.arange(1, w + 1) / w) * s.sum(axis=1, keepdims=True)
    tau2 = (win**4).mean(axis=1) - s.mean(axis=1) ** 2
    return np.abs(path).max(axis=1) / (np.sqrt(w) * np.sqrt(tau2))


def n_episodes(alarm: np.ndarray, gap: int = GAP) -> int:
    pos = np.flatnonzero(alarm)
    if pos.size == 0:
        return 0
    return int(1 + np.sum(np.diff(pos) > gap + 1))


def main() -> None:
    r = returns_panel()
    ph = pd.read_csv(RESULTS / "annual_posthoc.csv", dtype={"ticker": str})
    ph = ph[ph.calibration_method == "asymptotic"].set_index(["ticker", "year", "policy"])
    cu = pd.read_csv(RESULTS / "annual_cusum_diagnostics.csv", dtype={"ticker": str})
    cu = cu[(cu.window == W) & (cu.boundary_mode == "YEAR_CONTAINED")]
    cu = cu.set_index(["ticker", "year", "policy", "calibration_method"])
    rows = []
    worst = {"T_rel": 0.0, "e_rel": 0.0, "r_abs": 0.0, "Troll_abs": 0.0}
    mism = {"n": 0, "khat": 0, "episodes": 0}
    for t in tickers():
        with gzip.open(WORK / t / "daily.csv.gz", "rt") as fh:
            d = pd.read_csv(fh, dtype={"ticker": str})
        d["date"] = pd.to_datetime(d.date)
        for (y, p), g in d[d.window == 0].groupby(["year", "policy"]):
            g = g.sort_values("date")
            e, rr, vh = g.e.to_numpy(float), g.r.to_numpy(float), g.vhat.to_numpy(float)
            r_ind = r[t].reindex(g.date).to_numpy(float)
            ok_r = np.isfinite(r_ind)
            worst["r_abs"] = max(worst["r_abs"], float(np.nanmax(np.abs(rr[ok_r] - r_ind[ok_r]))))
            okv = np.isfinite(vh) & (vh > 0) & ok_r
            e_ind = np.full(e.size, np.nan)
            e_ind[okv] = r_ind[okv] / np.sqrt(vh[okv])
            fin = np.isfinite(e)
            assert np.array_equal(fin, np.isfinite(e_ind)), (t, y, p)
            worst["e_rel"] = max(worst["e_rel"], float(np.max(np.abs(e[fin] - e_ind[fin]) / np.abs(e[fin]).clip(1e-12))))
            keep = np.flatnonzero(fin)
            T, k = cusum_1d(e[keep])
            ref = ph.loc[(t, int(y), p)]
            worst["T_rel"] = max(worst["T_rel"], abs(T - float(ref.annual_T)) / float(ref.annual_T))
            mism["n"] += int(keep.size != int(ref.n_test_residuals))
            mism["khat"] += int(str(g.date.iloc[keep[k]].date()) != str(ref.khat_argmax_date))
            # 이동창 PURE 재계산 vs 일별 T
            tw = window_T(e, W)
            dT = d[(d.window == W) & (d.year == y) & (d.policy == p)].sort_values("date")["T"].to_numpy(float)
            pure = np.arange(e.size) >= W - 1
            both = pure & np.isfinite(tw) & np.isfinite(dT)
            assert np.array_equal(np.isfinite(tw[pure]), np.isfinite(dT[pure])), (t, y, p)
            if both.any():
                worst["Troll_abs"] = max(worst["Troll_abs"], float(np.max(np.abs(tw[both] - dT[both]))))
            crit = float(cu.loc[(t, int(y), p, "iid_insample"), "pointwise_null_quantile"])
            row_cu = cu.loc[(t, int(y), p, "iid_insample")]
            ep = n_episodes(pure & np.isfinite(tw) & (np.nan_to_num(tw, nan=-np.inf) >= crit))
            mism["episodes"] += int(ep != int(row_cu.rolling_episodes))
            # 순열 (EXPLORATORY)
            rng = np.random.default_rng([20261016, int(t), int(y), POL.index(p)])
            ev = e[keep]
            perm_ep, perm_T = [], []
            for _ in range(PERMS):
                pe = rng.permutation(ev)
                twp = window_T_finite(pe, W)
                perm_ep.append(n_episodes(twp >= crit))
                perm_T.append(cusum_1d(pe)[0])
            perm_T = np.asarray(perm_T)
            rows.append({
                "ticker": t, "year": int(y), "policy": p, "n": int(keep.size), "annual_T": T,
                "obs_w60_pure_episodes": ep, "null_expected_iid_pool": float(row_cu.expected_null_episodes),
                "perm_mean_episodes": float(np.mean(perm_ep)),
                "perm_p_annual_T": float((1 + np.sum(perm_T >= T)) / (PERMS + 1)),
                "acf_e2_lag1": float(np.corrcoef(ev[1:] ** 2, ev[:-1] ** 2)[0, 1]),
            })
        print(t, "done", flush=True)
    df = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / "a2_dependence.csv", index=False, float_format="%.6g")
    print("cells", len(df))
    print("worst", {k: f"{v:.2e}" for k, v in worst.items()})
    print("mismatch counts", mism)
    g = df.groupby(["policy"])
    print(g[["obs_w60_pure_episodes", "null_expected_iid_pool", "perm_mean_episodes"]].sum().round(1).to_string())
    print(g.acf_e2_lag1.median().round(3).to_string())
    print("by year/policy (obs episodes · iid-pool null · within-year permutation null)")
    print(df.groupby(["year", "policy"])[["obs_w60_pure_episodes", "null_expected_iid_pool", "perm_mean_episodes"]]
          .sum().round(1).unstack().to_string())
    print("permutation p<0.05 count (annual T, EXPLORATORY) by year/policy")
    print((df.assign(sig=df.perm_p_annual_T < 0.05).groupby(["year", "policy"]).sig.sum().unstack()).to_string())


if __name__ == "__main__":
    main()

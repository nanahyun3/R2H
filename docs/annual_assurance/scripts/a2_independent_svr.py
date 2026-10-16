"""A-2 Q2·Q3·Q5 — SVR–GARCH 연초 적합과 정책 A/B 예측분산을 r2h 코드 없이 다시 구현해 140 fold 를 대조한다.

r2h 의 함수(proxy·lag 설계·select_and_refit·forecast_test_variance) 를 호출하지 않는다. sklearn 추정기만 같다
(그것이 방법의 정의다: RBF ε-SVR, X·y StandardScaler, gamma = 1/(2γ²)).

대조 대상
- fit_summary (expanding): C, γ², ε, val_mae
- a_seq_1 일별 vhat (A, B) — %.10g 저장이므로 상대오차 ≤ 1e-8 을 일치로 본다
부산물 (Q5): 사전 연도 in-sample 보정 풀 vs 그해 OOS 잔차의 초과첨도 · ACF(e²,1)

실행: PYTHONPATH=src <R2H>/.venv/bin/python -I docs/annual_assurance/scripts/a2_independent_svr.py
"""

from __future__ import annotations

import gzip
import itertools
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.compose import TransformedTargetRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tests" / "assurance"))
from _real import RESULTS, returns_panel, tickers  # noqa: E402

WORK = ROOT / "outputs" / "t12" / "work" / "a_seq_1"
OUT = ROOT / "docs" / "annual_assurance" / "out"
GRID = list(itertools.product((1.0, 10.0, 100.0), (0.1, 0.5, 1.0), (0.1, 0.5, 1.0)))
M = 5


MODE = {"proxy": "prefix"}


def proxy(x: np.ndarray, hist: np.ndarray | None = None) -> np.ndarray:
    """σ̃²_t = mean(x²_{t−4..t}); hist 가 있으면 앞에 이어 붙인다 (CARRY).

    mode "prefix": 누적합 차 / 개수 (수학적으로 같은 식, r2h 와 같은 부동소수 연산 순서)
    mode "direct": 창 안의 x² 를 직접 평균 (같은 식, 연산 순서만 다름 → ULP 수준 차이) — 수치 민감도 대조용
    """
    h = np.empty(0) if hist is None else hist
    j = np.concatenate([h, x]) ** 2
    pre = np.concatenate(([0.0], np.cumsum(j, dtype=float)))
    out = np.empty(x.size)
    for i in range(x.size):
        g = h.size + i
        lo = max(0, g - M + 1)
        out[i] = (pre[g + 1] - pre[lo]) / (g - lo + 1) if MODE["proxy"] == "prefix" else j[lo : g + 1].mean()
    return out


def cusum_T(x: np.ndarray) -> float:
    n = x.size
    s = x**2
    path = np.cumsum(s) - (np.arange(1, n + 1) / n) * s.sum()
    return float(np.abs(path).max() / (np.sqrt(n) * np.sqrt(np.mean(x**4) - np.mean(s) ** 2)))


def design(y_all: np.ndarray, p_all: np.ndarray, start: int) -> tuple[np.ndarray, np.ndarray]:
    """y_all[start:] 의 각 t 에 대해 X=(y²_{t−1}, σ̃²_{t−1}), 목표 σ̃²_t (t ≥ 1)."""
    idx = np.arange(max(start, 1), y_all.size)
    return np.column_stack([y_all[idx - 1] ** 2, p_all[idx - 1]]), p_all[idx]


def model(C: float, g2: float, eps: float) -> TransformedTargetRegressor:
    svr = SVR(kernel="rbf", C=C, gamma=1.0 / (2.0 * g2), epsilon=eps, tol=1e-3, shrinking=True, cache_size=200.0)
    return TransformedTargetRegressor(regressor=Pipeline([("x", StandardScaler()), ("svr", svr)]),
                                      transformer=StandardScaler())


def fit_select(h: np.ndarray, n_tr: int):
    tr, va = h[:n_tr], h[n_tr:]
    p_tr = proxy(tr)
    Xtr, ytr = design(tr, p_tr, 0)
    p_va = proxy(va, tr)  # CARRY
    Xva, yva = design(np.concatenate([tr, va]), np.concatenate([p_tr, p_va]), n_tr)
    maes = []
    for C, g2, eps in GRID:
        mdl = model(C, g2, eps).fit(Xtr, ytr)
        maes.append(float(np.mean(np.abs(mdl.predict(Xva) - yva))))
    k = int(np.flatnonzero(np.asarray(maes) == min(maes))[0])
    p_h = proxy(h)  # RESET 전체
    Xh, yh = design(h, p_h, 0)
    final = model(*GRID[k]).fit(Xh, yh)
    return GRID[k], maes[k], final, p_h


def forecast(final, ctx: np.ndarray, p_ctx: np.ndarray, test: np.ndarray, policy: str) -> np.ndarray:
    if policy == "A":
        p_te = proxy(test, ctx)
        X, _ = design(np.concatenate([ctx, test]), np.concatenate([p_ctx, p_te]), ctx.size)
        return final.predict(X)
    yh, vh, out = list(ctx), list(p_ctx), []
    for obs in test:
        v = float(final.predict(np.array([[yh[-1] ** 2, vh[-1]]]))[0])
        out.append(v)
        yh.append(float(obs))
        vh.append(v)
    return np.asarray(out)


def acf1(x: np.ndarray) -> float:
    d = x - x.mean()
    return float(np.dot(d[1:], d[:-1]) / np.dot(d, d))


def main() -> None:
    for mode in ("prefix", "direct"):
        MODE["proxy"] = mode
        run(mode)


def run(mode: str) -> None:
    t0 = time.time()
    print(f"=== proxy mode: {mode} ===")
    r = returns_panel()
    phr = pd.read_csv(RESULTS / "annual_posthoc.csv", dtype={"ticker": str})
    phr = phr[phr.calibration_method == "asymptotic"].set_index(["ticker", "year", "policy"])
    fs = pd.read_csv(RESULTS / "fit_summary.csv", dtype={"ticker": str})
    fs = fs[fs.history_strategy == "expanding"].set_index(["ticker", "year"])
    rows = []
    for t in tickers():
        with gzip.open(WORK / t / "daily.csv.gz", "rt") as fh:
            d = pd.read_csv(fh, dtype={"ticker": str})
        d = d[d.window == 0]
        v = r[t].dropna()
        dates = pd.DatetimeIndex(v.index)
        x = v.to_numpy(float)
        for y in range(2020, 2027):
            pre = dates < pd.Timestamp(f"{y}-01-01")
            te = (dates >= pd.Timestamp(f"{y}-01-01")) & (dates < pd.Timestamp(f"{y + 1}-01-01"))
            h, test = x[pre], x[te]
            n_tr = round(0.7 * h.size)
            (C, g2, eps), mae, final, p_h = fit_select(h, n_tr)
            ref = fs.loc[(t, y)]
            row = {
                "ticker": t, "year": y,
                "params_match": (C, g2, eps) == (float(ref.C), float(ref.gamma_squared), float(ref.epsilon)),
                "val_mae_rel": abs(mae - float(ref.val_mae)) / float(ref.val_mae),
            }
            for pol in ("A", "B"):
                mine = forecast(final, h, p_h, test, pol)
                dd = d[(d.year == y) & (d.policy == pol)]
                dd = dd.set_index(pd.to_datetime(dd.date)).reindex(dates[te])
                theirs = dd.vhat.to_numpy(float)
                row[f"vhat_{pol}_maxrel"] = float(np.nanmax(np.abs(mine - theirs) / np.abs(theirs)))
                row[f"nonpos_{pol}"] = int((mine <= 0).sum())
                okp = mine > 0
                Tm = cusum_T(test[okp] / np.sqrt(mine[okp]))
                Tr = float(phr.loc[(t, y, pol), "annual_T"])
                row[f"T_{pol}"] = Tm
                row[f"T_{pol}_ref"] = Tr
                row[f"flip_{pol}"] = bool((Tm >= 1.3397) != (Tr >= 1.3397))
            # Q5: in-sample 풀 (RESET, 모형 y 를 학습 이력 전체에 적용) vs OOS A 잔차
            Xh, _ = design(h, p_h, 0)
            vin = final.predict(Xh)
            ok = vin > 0
            pool = h[1:][ok] / np.sqrt(vin[ok])
            va = forecast(final, h, p_h, test, "A")
            e = test[va > 0] / np.sqrt(va[va > 0])
            row.update(
                pool_n=int(pool.size), pool_exkurt=float(stats.kurtosis(pool)), pool_acf_e2_1=acf1(pool**2),
                oos_exkurt=float(stats.kurtosis(e)), oos_acf_e2_1=acf1(e**2),
                pool_mean_e2=float(np.mean(pool**2)), oos_mean_e2=float(np.mean(e**2)),
            )
            rows.append(row)
        print(f"{t} done {time.time() - t0:.0f}s", flush=True)  # noqa: T201
    df = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / f"a2_independent_svr_{mode}.csv", index=False, float_format="%.6g")
    print("folds", len(df))
    print("params_match", int(df.params_match.sum()), "/", len(df))
    print("val_mae max rel diff", f"{df.val_mae_rel.max():.2e}")
    for pol in ("A", "B"):
        c = f"vhat_{pol}_maxrel"
        print(f"vhat_{pol}: folds with max rel diff ≤1e-8: {int((df[c] <= 1e-8).sum())}/{len(df)} · worst {df[c].max():.2e}")
    print("nonpos A/B total", int(df.nonpos_A.sum()), int(df.nonpos_B.sum()))
    for pol in ("A", "B"):
        rel = (df[f"T_{pol}"] - df[f"T_{pol}_ref"]).abs() / df[f"T_{pol}_ref"]
        print(f"annual T {pol}: max rel diff {rel.max():.2e} · verdict flips at 1.3397: {int(df[f'flip_{pol}'].sum())}/140")
    q = df[["pool_exkurt", "oos_exkurt", "pool_acf_e2_1", "oos_acf_e2_1", "pool_mean_e2", "oos_mean_e2"]]
    print(q.describe(percentiles=[0.25, 0.5, 0.75]).round(3).to_string())
    print("share OOS ACF(e²,1) < 0:", f"{(df.oos_acf_e2_1 < 0).mean():.3f}", "· pool < 0:", f"{(df.pool_acf_e2_1 < 0).mean():.3f}")


if __name__ == "__main__":
    main()

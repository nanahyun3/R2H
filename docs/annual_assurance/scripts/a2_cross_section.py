"""A-2 Q7 — ETF 간 상관(노출 중복)이 '기각 수 / 20' 해석에 주는 제한의 정량화.

입력: 원자료에서 독립 재계산한 수익률 (tests/assurance/_real.py). 있으면 a_seq_1 일별 잔차 e (A·base).
결과표: research/t12_annual_expanding_v2/results/annual_posthoc.csv (asymptotic 기각).

1. 상관행렬: r, r² (CUSUM-of-squares 는 제곱에 반응하므로 r² 가 관련 척도), e²(A), e²(base)
2. 유효 독립 검정 수 M_eff (Li & Ji 2005: Σ f(|λ|), f(x)=1[x≥1]+(x−⌊x⌋)) — 연도별
3. 군집: 평균 연결, 거리 1 − corr(r²) (2019-2026 전체), 절단 0.5 (사전 지정) · 민감도 0.3 / 0.7
4. 횡단면 상관만 있는 귀무 (시간 iid 정규, 연도별 corr(r) 공유) 에서 '20종 중 기각 수' 의 분포 — 2,000회
   seed: np.random.default_rng([20261016, year]) · 독립 이항 대조
이 귀무는 변동성 군집을 넣지 않는다. 즉 상관 효과만 분리한다.

실행: PYTHONPATH=src <R2H>/.venv/bin/python -I docs/annual_assurance/scripts/a2_cross_section.py
"""

from __future__ import annotations

import gzip
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform
from scipy.stats import binom

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tests" / "assurance"))
from _real import RESULTS, returns_panel, tickers  # noqa: E402

WORK = ROOT / "outputs" / "t12" / "work" / "a_seq_1"
C = 1.3397
YEARS = list(range(2020, 2027))


def cusum_T(x: np.ndarray) -> np.ndarray:
    n = x.shape[-1]
    s = x**2
    path = np.cumsum(s, axis=-1) - (np.arange(1, n + 1) / n) * s.sum(axis=-1, keepdims=True)
    tau2 = (x**4).mean(axis=-1) - s.mean(axis=-1) ** 2
    return np.abs(path).max(axis=-1) / (np.sqrt(n) * np.sqrt(tau2))


def m_eff(corr: np.ndarray) -> float:
    lam = np.abs(np.linalg.eigvalsh(corr))
    return float(np.sum((lam >= 1).astype(float) + (lam - np.floor(lam))))


def daily_e(policy: str) -> pd.DataFrame | None:
    if not WORK.exists():
        return None
    cols = {}
    for t in tickers():
        p = WORK / t / "daily.csv.gz"
        if not p.exists():
            return None
        with gzip.open(p, "rt") as fh:
            d = pd.read_csv(fh, dtype={"ticker": str})
        d = d[(d.window == 0) & (d.policy == policy)]
        cols[t] = pd.Series(d.e.to_numpy(float), index=pd.to_datetime(d.date))
    return pd.DataFrame(cols)


def main() -> None:
    r = returns_panel()
    tk = tickers()
    print("## 1. 전체기간 상관 (2019-01-03 ~ 2026-10-02)")
    cr = r.corr().to_numpy()
    cr2 = (r**2).corr().to_numpy()
    iu = np.triu_indices(20, 1)
    print(f"corr(r): median |ρ| {np.median(np.abs(cr[iu])):.3f}, max {np.max(np.abs(cr[iu])):.3f}")
    print(f"corr(r²): median {np.median(cr2[iu]):.3f}, max {np.max(cr2[iu]):.3f}")
    print(f"M_eff(r) {m_eff(np.nan_to_num(cr)):.2f} · M_eff(r²) {m_eff(np.nan_to_num(cr2)):.2f} (of 20)")
    pairs = [("069500", "102110"), ("069500", "122630"), ("069500", "114800"), ("122630", "114800"),
             ("069500", "229200"), ("219480", "133690"), ("069500", "261240")]
    for a, b in pairs:
        i, j = tk.index(a), tk.index(b)
        print(f"  {a}-{b}: ρ(r) {cr[i, j]:+.3f} · ρ(r²) {cr2[i, j]:+.3f}")

    dist = 1 - np.clip(np.nan_to_num(cr2), -1, 1)
    np.fill_diagonal(dist, 0)
    Z = linkage(squareform(dist, checks=False), "average")
    clusters = {}
    for cut in (0.3, 0.5, 0.7):
        lab = fcluster(Z, t=cut, criterion="distance")
        clusters[cut] = dict(zip(tk, lab, strict=True))
        groups = {}
        for t, g in clusters[cut].items():
            groups.setdefault(g, []).append(t)
        multi = [v for v in groups.values() if len(v) > 1]
        print(f"군집 절단 {cut}: 군집 수 {len(groups)} · 2종 이상 군집 {multi}")
    cl = clusters[0.5]

    eA, eB = daily_e("A"), daily_e("base")
    print("\n## 2. 연도별 M_eff (Li–Ji) — r · r² · e²(A) · e²(base)")
    for y in YEARS:
        m = r.index.year == y
        out = [m_eff(np.nan_to_num(r[m].corr().to_numpy())), m_eff(np.nan_to_num((r[m] ** 2).corr().to_numpy()))]
        for e in (eA, eB):
            if e is not None:
                me = e.index.year == y
                out.append(m_eff(np.nan_to_num((e[me] ** 2).corr().to_numpy())))
        print(y, " ".join(f"{v:.2f}" for v in out))

    ph = pd.read_csv(RESULTS / "annual_posthoc.csv", dtype={"ticker": str})
    ph = ph[ph.calibration_method == "asymptotic"]
    print("\n## 3. 횡단면 상관 귀무 (시간 iid 정규, 연도별 corr(r)) 에서 기각 수 분포 · 2,000회")
    print("year n E[count] sd P(count>=1) P(count>=3) | 관측(A,B,base) → P_corr(≥obs) / P_binom(≥obs) | 기각 군집 수(A,B,base)/군집")
    for y in YEARS:
        m = r.index.year == y
        n = int(m.sum())
        Sig = np.nan_to_num(r[m].corr().to_numpy())
        np.fill_diagonal(Sig, 1.0)
        L = np.linalg.cholesky(Sig + 1e-10 * np.eye(20))
        rng = np.random.default_rng([20261016, y])
        reps = 2000
        z = rng.standard_normal((reps, n, 20)) @ L.T
        T = cusum_T(np.transpose(z, (0, 2, 1)))  # (reps, 20)
        cnt = (T >= C).sum(axis=1)
        p1 = float((T >= C).mean())
        obs = {p: int(ph[(ph.year == y) & (ph.policy == p)].annual_reject.astype(bool).sum()) for p in ("A", "B", "base")}
        pc = {p: float((cnt >= k).mean()) for p, k in obs.items()}
        pb = {p: float(binom.sf(k - 1, 20, p1)) for p, k in obs.items()}
        ncl = len(set(cl.values()))
        rej_cl = {
            p: len({cl[t] for t in ph[(ph.year == y) & (ph.policy == p) & ph.annual_reject.astype(bool)].ticker})
            for p in ("A", "B", "base")
        }
        print(
            f"{y} {n} {cnt.mean():.2f} {cnt.std():.2f} {(cnt >= 1).mean():.3f} {(cnt >= 3).mean():.3f} | "
            + " ".join(f"{p}={obs[p]}→{pc[p]:.4f}/{pb[p]:.2e}" for p in obs)
            + " | "
            + ",".join(str(rej_cl[p]) for p in ("A", "B", "base"))
            + f"/{ncl}"
        )
    print("\n## 4. 군집 (절단 0.5) 소속")
    groups = {}
    for t, g in cl.items():
        groups.setdefault(g, []).append(t)
    for g, v in sorted(groups.items()):
        print(g, v)


if __name__ == "__main__":
    main()

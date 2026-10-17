# ruff: noqa: E501  — 한국어 설명·표 머리 문자열
"""전체 재적합 Monte Carlo 반복 (계약 W3-lock-2 §9–§11, D15).

반복 1회 = 평가연도 y 마다 y 이전 자료로 적합한 귀무(model_y)에서 2019..y 경로 모의 → 실제 날짜 index →
``run_pipeline_years`` (연간 SVR 재적합·A/B/base·7개 창 CUSUM) → (평가 단계) 위치 구간별 꼬리점수 Q → ``rep_statistics``.
시드는 (study_id, seed, 영역, rep) 의 sha256 → 실행 순서·프로세스와 무관. DCC 와 CCC 평가는 같은 시드(공통 난수)를 쓴다.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from r2h.annual_expanding.config import rng_for
from r2h.multihorizon.core import log_variance_ratio, midrank_past, realized_variance

from .dcc import MultiT, Shock, nearest_correlation, simulate
from .pipeline import run_pipeline_years
from .scores import (
    TailTable,
    all_subsets,
    j_all,
    lag_max,
    member_stack,
    q_score,
    rep_statistics,
    run_lengths,
)

N_PRIMARY_WIN = 4
YEAR_STATS_N3 = ("kurt", "acf_r2", "var", "zero_share")
YEAR_STATS_N4 = ("corr", "coexceed", "rollcorr_sd")


def rep_rng(cfg: dict, domain: str, rep: int) -> np.random.Generator:
    return rng_for(cfg["study_id"], cfg["seed"], domain, rep)


def simulate_year_paths(
    models: dict[int, MultiT],
    dates: pd.DatetimeIndex,
    tickers: list[str],
    rng: np.random.Generator,
    shocks: dict[int, Shock] | None = None,
    burn: int = 500,
) -> dict[int, pd.DataFrame]:
    """평가연도 y 마다 model_y 에서 2019-01-03..y-12-31 경로 (같은 rng 를 연도 순서대로 소비 → 결정적)."""
    out = {}
    for y in sorted(models):
        d = dates[dates < pd.Timestamp(f"{y + 1}-01-01")]
        r, _ = simulate(models[y], len(d), rng, burn=burn, shock=None if shocks is None else shocks.get(y))
        out[y] = pd.DataFrame(r, index=d, columns=tickers)
    return out


# ── 수익률 수준 진단 통계 (N3·N4) ───────────────────────────────────


def return_diagnostics(R: np.ndarray) -> dict[str, np.ndarray]:
    """N3 (ETF별 첨도·r² 자기상관·분산·정확 0 비율) 와 N4 (쌍별 상관·하위 5% 동시 초과·60일 rolling 상관 sd)."""
    N = R.shape[1]
    x = R - R.mean(axis=0)
    var = x.var(axis=0)
    kurt = (x**4).mean(axis=0) / var**2 - 3.0
    r2 = R**2 - (R**2).mean(axis=0)
    acf = np.array(
        [
            np.mean([np.sum(r2[k:, j] * r2[:-k, j]) / np.sum(r2[:, j] ** 2) for k in range(1, 6)])
            for j in range(N)
        ]
    )
    zero = (R == 0).mean(axis=0)
    corr = np.corrcoef(R.T)
    q05 = np.quantile(R, 0.05, axis=0)
    low = R <= q05
    pairs = [(i, j) for i in range(N) for j in range(i + 1, N)]
    co = np.array([np.mean(low[:, i] & low[:, j]) for i, j in pairs])
    rc = pd.DataFrame(R)
    roll_sd = np.array([rc[i].rolling(60).corr(rc[j]).std() for i, j in pairs])
    return {
        "var": var,
        "kurt": kurt,
        "acf_r2": acf,
        "zero_share": zero,
        "corr": np.array([corr[i, j] for i, j in pairs]),
        "coexceed": co,
        "rollcorr_sd": roll_sd,
    }


# ── 잔차 에너지 E(h) (탐색 후보) ────────────────────────────────────


def energy(e: np.ndarray, year_of_day: np.ndarray, hs: list[int]) -> np.ndarray:
    """E(h)_t = log(mean e²[t−h+1..t] / mean e²[t−h−59..t−h]) — 그해 잔차 안에서만, 분모 0·결측이면 NaN.

    e: (..., 일). 반환 (..., len(hs), 일).
    """
    out = np.full((*e.shape[:-1], len(hs), e.shape[-1]), np.nan)
    e2 = e**2
    for y in np.unique(year_of_day):
        m = np.flatnonzero(year_of_day == y)
        seg = e2[..., m]
        n = seg.shape[-1]
        cs = np.concatenate([np.zeros((*seg.shape[:-1], 1)), np.nancumsum(seg, axis=-1)], axis=-1)
        cn = np.concatenate([np.zeros((*seg.shape[:-1], 1)), np.cumsum(np.isfinite(seg), axis=-1)], axis=-1)
        for h_i, h in enumerate(hs):
            for t in range(h + 59, n):
                num_s = cs[..., t + 1] - cs[..., t + 1 - h]
                num_n = cn[..., t + 1] - cn[..., t + 1 - h]
                den_s = cs[..., t + 1 - h] - cs[..., t + 1 - h - 60]
                den_n = cn[..., t + 1 - h] - cn[..., t + 1 - h - 60]
                with np.errstate(invalid="ignore", divide="ignore"):
                    val = np.log((num_s / num_n) / (den_s / den_n))
                ok = (num_n == h) & (den_n == 60) & (den_s > 0) & (num_s > 0)
                out[..., h_i, m[t]] = np.where(ok, val, np.nan)
    return out


# ── 영역별 반복 ─────────────────────────────────────────────────────


def year_diagnostics(paths: dict[int, pd.DataFrame]) -> dict[str, np.ndarray]:
    """연도 모형별 적합도 재료: 경로의 y 이전 구간(= model_y 의 적합 표본에 대응) 수익률 진단. 키 diag_<stat> (연도, k)."""
    per = {
        y: return_diagnostics(p[p.index < pd.Timestamp(f"{y}-01-01")].to_numpy())
        for y, p in sorted(paths.items())
    }
    ys = sorted(per)
    return {f"diag_{k}": np.stack([per[y][k] for y in ys]) for k in per[ys[0]]}


def annual_max_own(T: np.ndarray, year_of_day: np.ndarray, pos: np.ndarray, windows: list[int]) -> np.ndarray:
    """(ETF, 정책, 창, 연도) 연중 own-valid 일(위치 ≥ w−1) 최대 T — W3 개별 신호 임계값의 재료 (lock-2 §6)."""
    years = np.unique(year_of_day)
    out = np.full((*T.shape[:-1], len(years)), np.nan)
    for w_i, w in enumerate(windows):
        for y_i, y in enumerate(years):
            m = (year_of_day == y) & (pos >= w - 1)
            seg = T[..., w_i, :][..., m]
            fin = np.isfinite(seg).any(axis=-1)
            mx = np.where(np.isfinite(seg), seg, -np.inf).max(axis=-1)
            out[..., w_i, y_i] = np.where(fin, mx, np.nan)
    return out


def calibration_rep(
    models: dict[int, MultiT], dates: pd.DatetimeIndex, cfg: dict, rep: int
) -> dict[str, np.ndarray]:
    """H0_CALIBRATION: T (7개 창), E(h), 연도별 수익률 진단, own-valid 연간 최대."""
    tickers = list(cfg["universe"]["tickers"])
    paths = simulate_year_paths(models, dates, tickers, rep_rng(cfg, "H0_CALIBRATION", rep))
    out = run_pipeline_years(paths, cfg)
    wins = list(cfg["pipeline"]["windows_primary"]) + list(cfg["pipeline"]["windows_short_eligibility"])
    return {
        "T": out.T.astype(np.float32),
        "E": energy(out.e, out.year_of_day, [1, 3, 7, 14]).astype(np.float32),
        "annual_max_own": annual_max_own(out.T, out.year_of_day, out.pos_in_year, wins),
        **year_diagnostics(paths),
    }


def eval_rep(
    models: dict[int, MultiT],
    dates: pd.DatetimeIndex,
    cfg: dict,
    tt: TailTable,
    domain: str,
    rep: int,
    holdout_extra: bool = False,
    burn: int = 500,
) -> dict[str, np.ndarray]:
    """H0_EVALUATION (DCC·CCC 공통 시드)·holdout·ROBUSTNESS 반복: 모든 검정 통계량 (+ holdout 은 단기 창 연간 최대·q 신호 빈도)."""
    tickers = list(cfg["universe"]["tickers"])
    paths = simulate_year_paths(models, dates, tickers, rep_rng(cfg, domain, rep), burn=burn)
    out = run_pipeline_years(paths, cfg)
    Q = q_score(out.T[:, :, :N_PRIMARY_WIN], tt, out.pos_in_year)
    st = rep_statistics(Q, cfg)
    res = {
        "M_subset": st.M_subset,
        "M2_subset": st.M2_subset,
        "C_stage": st.C_stage,
        "M2_stage": st.M2_stage,
        "cum_excess": st.cum_excess,
        "longest_run": st.longest_run,
    }
    if holdout_extra:
        wins = list(cfg["pipeline"]["windows_primary"]) + list(cfg["pipeline"]["windows_short_eligibility"])
        res["annual_max_own"] = annual_max_own(out.T, out.year_of_day, out.pos_in_year, wins)
        res["q_signal_rate"] = q_signal_rates(paths, out.eval_dates)
    return res


def q_signal_rates(paths: dict[int, pd.DataFrame], eval_dates: pd.DatetimeIndex) -> np.ndarray:
    """귀무에서 단기 q (3·7·14) EXPANSION / HIGH_LEVEL 후보일 비율 (ETF, q, 채널) — 분위 후보가 보정 경보가 아님을 보이는 기준."""
    qs = [3, 7, 14]
    first = next(iter(paths.values()))
    out = np.zeros((first.shape[1], len(qs), 2))
    cnt = np.zeros_like(out)
    for y, R in paths.items():
        ev = np.asarray(R.index.year == y)
        for i, tk in enumerate(R.columns):
            r = R[tk].to_numpy(float)
            for q_i, q in enumerate(qs):
                v = realized_variance(r, q)
                d, _, _ = log_variance_ratio(v, q)
                ud, _, _ = midrank_past(d, 252)
                uv, _, _ = midrank_past(v, 252)
                for c, u in ((0, ud), (1, uv)):
                    x = u[ev]
                    ok = np.isfinite(x)
                    out[i, q_i, c] += np.sum(x[ok] >= 0.9)
                    cnt[i, q_i, c] += ok.sum()
    return out / np.maximum(cnt, 1)


# ── 대립 시나리오 (H1_POWER) ───────────────────────────────────────


@dataclass(frozen=True)
class AltDesign:
    year: int
    tau: int  # 평가일 index (변화 시작)
    end: int  # 평가일 index (변화 끝, 포함) = 그해 마지막 평가일
    affected: tuple[str, ...]
    shock: Shock  # 그해 경로(2019..y) 기준 위치


def alt_design(
    models: dict[int, MultiT],
    dates: pd.DatetimeIndex,
    eval_dates: pd.DatetimeIndex,
    cfg: dict,
    name: str,
    rng: np.random.Generator,
) -> AltDesign:
    """시나리오 → 변화 연도·위치(설정 범위 균등)·조작. 연도·위치 추출을 경로 모의보다 먼저 한다."""
    a = cfg["alternatives"]
    tickers = list(cfg["universe"]["tickers"])
    years = cfg["sample"]["evaluation_years"]
    y = int(rng.choice(years))
    lo, hi = a["change_index_in_year"]
    k = int(rng.integers(lo, hi + 1))
    ymask = np.flatnonzero(eval_dates.year == y)
    tau, end = int(ymask[k]), int(ymask[-1])
    pdates = dates[dates < pd.Timestamp(f"{y + 1}-01-01")]
    tau_f = int(pdates.get_loc(eval_dates[tau]))
    end_f = len(pdates) - 1
    spec = a["scenarios"][name]
    n, N = len(pdates), len(tickers)
    vm = np.ones((n, N))
    affected: list[str] = []
    for t in spec.get("up", []):
        vm[tau_f : end_f + 1, tickers.index(t)] = a["variance_up"]
        affected.append(t)
    for t in spec.get("down", []):
        vm[tau_f : end_f + 1, tickers.index(t)] = a["variance_down"]
        affected.append(t)
    for t, d in spec.get("delayed_up", {}).items():
        vm[tau_f + d : end_f + 1, tickers.index(t)] = a["variance_up"]
        affected.append(t)
    shock = Shock(var_mult=vm)
    model = models[y]
    if "correlation_only" in spec:
        Ralt = nearest_correlation(np.maximum(model.qbar, 0.7) * (1 - np.eye(N)) + np.eye(N))
        shock = Shock(corr_override=Ralt, corr_start=tau_f, corr_end=end_f + 1)
        affected = list(tickers)
    if "normal_common_shock" in spec:
        sgn = np.sign(model.qbar[:, tickers.index("069500")])
        sgn[sgn == 0] = 1.0
        shock = Shock(z_override={tau_f: -6.0 * sgn})
        affected = []
    return AltDesign(y, tau, end, tuple(affected), shock)


def _first_at_or_after(flag: np.ndarray, start: int) -> int:
    idx = np.flatnonzero(flag[start:])
    return int(start + idx[0]) if idx.size else -1


def alt_rep(
    models: dict[int, MultiT],
    dates: pd.DatetimeIndex,
    cfg: dict,
    tt: TailTable,
    crit: dict[str, float],
    pipe_crit: dict[tuple[str, int], float],
    name: str,
    rep: int,
) -> dict[str, object]:
    """대립 반복: 경로 수준 통계량 + 변화 후 유의일 검출·지연·참여·구간 경계 + 단기 q 신호 대비 개별 CUSUM 지연."""
    tickers = list(cfg["universe"]["tickers"])
    rng = rep_rng(cfg, f"H1_POWER:{name}", rep)
    years = cfg["sample"]["evaluation_years"]
    eval_dates = dates[
        (dates >= pd.Timestamp(f"{years[0]}-01-01")) & (dates < pd.Timestamp(f"{years[-1] + 1}-01-01"))
    ]
    des = alt_design(models, dates, eval_dates, cfg, name, rng)
    paths = simulate_year_paths(models, dates, tickers, rng, shocks={des.year: des.shock})
    out = run_pipeline_years(paths, cfg)
    Q = q_score(out.T[:, :, :N_PRIMARY_WIN], tt, out.pos_in_year)
    st = rep_statistics(Q, cfg)
    Qlag, _ = lag_max(Q)
    c_E = float(cfg["joint"]["primary_test_statistics"]["c_E"])
    H = max(cfg["alternatives"]["detection_horizon_days"])
    win = np.zeros(Q.shape[-1], bool)
    win[des.tau : min(des.tau + H, Q.shape[-1])] = True
    res: dict[str, object] = {
        "scenario": name,
        "rep": rep,
        "tau": des.tau,
        "end": des.end,
        "year": des.year,
        "C_stage": st.C_stage,
        "M_subset": st.M_subset,
    }
    subs = all_subsets(tickers)
    for fam, ckey in cfg["alternatives"]["targets_resolved"][name]:
        s = tuple(ckey)
        ja = j_all(member_stack(Q, Qlag, s, tickers))
        jmax = np.where(np.isfinite(ja), ja, -np.inf).max(axis=(0, 1))
        sig = jmax >= crit[f"day:{'+'.join(s)}"]
        first = _first_at_or_after(sig, des.tau)
        det = 0 <= first < des.tau + H
        res[f"{fam}:detected_60"] = bool(det)
        res[f"{fam}:delay"] = (first - des.tau) if det else np.nan
        res[f"{fam}:any_sig_before_tau"] = bool(sig[: des.tau].any())
        if det:
            runs = [r for r in run_lengths(sig) if r[0] <= first <= r[1]]
            res[f"{fam}:ep_start_err"] = runs[0][0] - des.tau
            res[f"{fam}:ep_end_err"] = runs[0][1] - des.end
        res[f"{fam}:subset_index"] = subs.index(s)
    part = np.where(np.isfinite(Qlag), Qlag, -np.inf).max(axis=(1, 2)) >= c_E  # (ETF, 일)
    res["participated"] = part[:, win].any(axis=1)
    res["affected_mask"] = np.array([t in des.affected for t in tickers])
    # 영향 ETF 별 첫 반응 지연: 단기 q 확대(W2 규칙) · 개별 CUSUM (W3 own-valid 보정 임계값 · W1 참고 · Q≥c_E)
    wins_all = list(cfg["pipeline"]["windows_primary"]) + list(cfg["pipeline"]["windows_short_eligibility"])
    py = paths[des.year]
    yev = np.asarray(py.index.year == des.year)
    ystart = int(np.flatnonzero(out.year_of_day == des.year)[0])
    delays = {}
    for tk in des.affected:
        i = tickers.index(tk)
        r = py[tk].to_numpy(float)
        rec = {}
        for q in (3, 7, 14):
            d, _, _ = log_variance_ratio(realized_variance(r, q), q)
            ud, _, _ = midrank_past(d, 252)
            flag = np.zeros(Q.shape[-1], bool)
            flag[ystart : ystart + int(yev.sum())] = ud[yev] >= 0.9
            f = _first_at_or_after(flag, des.tau)
            rec[f"q{q}_EXP"] = (f - des.tau) if 0 <= f < des.tau + H else np.nan
        for p_i, p in enumerate(("A", "B", "base")):
            for w_i, w in enumerate(wins_all):
                Tw = out.T[i, p_i, w_i]
                cw = crit.get(f"w3:{tk}:{p}:{w}", np.inf)
                fa = _first_at_or_after(np.isfinite(Tw) & (Tw >= cw), des.tau)
                rec[f"cusum_w3crit_{p}_w{w}"] = (fa - des.tau) if 0 <= fa < des.tau + H else np.nan
                if w_i < N_PRIMARY_WIN:
                    f1 = _first_at_or_after(np.isfinite(Tw) & (Tw >= pipe_crit[p, w]), des.tau)
                    rec[f"cusum_w1crit_{p}_w{w}"] = (f1 - des.tau) if 0 <= f1 < des.tau + H else np.nan
                    qq = Q[i, p_i, w_i]
                    fq = _first_at_or_after(np.isfinite(qq) & (qq >= c_E), des.tau)
                    rec[f"cusum_Q_{p}_w{w}"] = (fq - des.tau) if 0 <= fq < des.tau + H else np.nan
        delays[tk] = rec
    res["delays"] = delays
    return res

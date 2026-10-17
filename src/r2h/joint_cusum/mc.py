"""전체 재적합 Monte Carlo 반복 (계약 §9, D15).

반복 1회 = 귀무(또는 대립) 다변량 경로 → 실제 날짜 index → ``run_pipeline`` (연간 SVR 재적합·A/B/base·7개 창 CUSUM)
→ (평가 단계) 꼬리점수 Q → ``rep_statistics``. 시드는 (study_id, seed, 영역, rep) 의 sha256 → 실행 순서·프로세스와 무관.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from r2h.annual_expanding.config import rng_for
from r2h.multihorizon.core import log_variance_ratio, midrank_past, realized_variance

from .dcc import MultiT, Shock, nearest_correlation, simulate
from .pipeline import run_pipeline
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


def rep_rng(cfg: dict, domain: str, rep: int) -> np.random.Generator:
    return rng_for(cfg["study_id"], cfg["seed"], domain, rep)


def simulate_panel(
    model: MultiT,
    dates: pd.DatetimeIndex,
    tickers: list[str],
    rng: np.random.Generator,
    shock: Shock | None = None,
) -> pd.DataFrame:
    """모의 수익률을 관측과 같은 날짜 index 에 얹는다 (연도 경계·연초 결측·base rolling 일치)."""
    r, _ = simulate(model, len(dates), rng, shock=shock)
    return pd.DataFrame(r, index=dates, columns=tickers)


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


def calibration_rep(model: MultiT, dates: pd.DatetimeIndex, cfg: dict, rep: int) -> dict[str, np.ndarray]:
    """보정 반복: T (7개 창), E(h), 수익률 진단. Q 표·단기 창 임계값·적합도 envelope 의 재료."""
    tickers = list(cfg["universe"]["tickers"])
    R = simulate_panel(model, dates, tickers, rep_rng(cfg, "calibration", rep))
    out = run_pipeline(R, cfg)
    hs = [1, 3, 7, 14]
    return {
        "T": out.T.astype(np.float32),
        "E": energy(out.e, out.year_of_day, hs).astype(np.float32),
        **{f"diag_{k}": v for k, v in return_diagnostics(R.to_numpy()).items()},
    }


def annual_max_common(
    T: np.ndarray, year_of_day: np.ndarray, pos: np.ndarray, start: int = 119
) -> np.ndarray:
    """(ETF, 정책, 창, 연도) 연중 공통일(위치 ≥ 119) 최대 T — W1 연간 최대 규약."""
    years = np.unique(year_of_day)
    out = np.full((*T.shape[:-1], len(years)), np.nan)
    for y_i, y in enumerate(years):
        m = (year_of_day == y) & (pos >= start)
        seg = T[..., m]
        fin = np.isfinite(seg).any(axis=-1)
        out[..., y_i] = np.where(fin, np.nanmax(np.where(np.isfinite(seg), seg, -np.inf), axis=-1), np.nan)
    return out


def eval_rep(
    model: MultiT,
    dates: pd.DatetimeIndex,
    cfg: dict,
    tt: TailTable,
    domain: str,
    rep: int,
    holdout_extra: bool = False,
) -> dict[str, np.ndarray]:
    """귀무 평가·holdout 반복: 검정 통계량 전부 (+ holdout 은 단기 창 연간 최대와 q 신호 빈도)."""
    tickers = list(cfg["universe"]["tickers"])
    R = simulate_panel(model, dates, tickers, rep_rng(cfg, domain, rep))
    out = run_pipeline(R, cfg)
    Q = q_score(out.T[:, :, :N_PRIMARY_WIN], tt)
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
        res["annual_max"] = annual_max_common(out.T, out.year_of_day, out.pos_in_year)
        res["q_signal_rate"] = q_signal_rates(R, out.eval_dates, cfg)
    return res


def q_signal_rates(R: pd.DataFrame, eval_dates: pd.DatetimeIndex, cfg: dict) -> np.ndarray:
    """귀무에서 단기 q (3·7·14) EXPANSION / HIGH_LEVEL 후보일 비율 (ETF, q, 채널) — 분위 후보가 경보가 아님을 보이는 기준."""
    qs = [3, 7, 14]
    ev = np.asarray(R.index.isin(eval_dates))
    out = np.full((R.shape[1], len(qs), 2), np.nan)
    for i, tk in enumerate(R.columns):
        r = R[tk].to_numpy(float)
        for q_i, q in enumerate(qs):
            v = realized_variance(r, q)
            d, _, _ = log_variance_ratio(v, q)
            ud, _, _ = midrank_past(d, 252)
            uv, _, _ = midrank_past(v, 252)
            out[i, q_i, 0] = np.nanmean(ud[ev] >= 0.9)
            out[i, q_i, 1] = np.nanmean(uv[ev] >= 0.9)
    return out


# ── 대립 시나리오 ───────────────────────────────────────────────────


@dataclass(frozen=True)
class AltDesign:
    tau: int  # 평가일 index (변화 시작)
    end: int  # 평가일 index (변화 끝, 포함) = 그해 마지막 평가일
    tau_full: int  # 전체 날짜 index
    end_full: int
    affected: tuple[str, ...]
    shock: Shock


def alt_design(
    model: MultiT,
    dates: pd.DatetimeIndex,
    eval_dates: pd.DatetimeIndex,
    cfg: dict,
    name: str,
    rng: np.random.Generator,
) -> AltDesign:
    """시나리오 이름 → 변화 연도·위치(설정 범위에서 균등)와 조작. 연도·위치 추출은 시나리오 시드 영역에서 먼저 한다."""
    a = cfg["alternatives"]
    tickers = list(cfg["universe"]["tickers"])
    years = cfg["sample"]["evaluation_years"]
    y = int(rng.choice(years))
    lo, hi = a["change_index_in_year"]
    k = int(rng.integers(lo, hi + 1))
    ymask = np.flatnonzero(eval_dates.year == y)
    tau, end = int(ymask[k]), int(ymask[-1])
    tau_full = int(dates.get_loc(eval_dates[tau]))
    end_full = int(dates.get_loc(eval_dates[end]))
    spec = a["scenarios"][name]
    n, N = len(dates), len(tickers)
    vm = np.ones((n, N))
    affected: list[str] = []
    for t in spec.get("up", []):
        vm[tau_full : end_full + 1, tickers.index(t)] = a["variance_up"]
        affected.append(t)
    for t in spec.get("down", []):
        vm[tau_full : end_full + 1, tickers.index(t)] = a["variance_down"]
        affected.append(t)
    for t, d in spec.get("delayed_up", {}).items():
        vm[tau_full + d : end_full + 1, tickers.index(t)] = a["variance_up"]
        affected.append(t)
    shock = Shock(var_mult=vm)
    if "correlation_only" in spec:
        Ralt = nearest_correlation(np.maximum(model.qbar, 0.7) * (1 - np.eye(N)) + np.eye(N))
        shock = Shock(corr_override=Ralt, corr_start=tau_full, corr_end=end_full + 1)
        affected = list(tickers)
    if "normal_common_shock" in spec:
        sgn = np.sign(model.qbar[:, tickers.index("069500")])
        sgn[sgn == 0] = 1.0
        shock = Shock(z_override={tau_full: -6.0 * sgn})
        affected = []
    return AltDesign(tau, end, tau_full, end_full, tuple(affected), shock)


def _first_at_or_after(flag: np.ndarray, start: int) -> int:
    idx = np.flatnonzero(flag[start:])
    return int(start + idx[0]) if idx.size else -1


def alt_rep(
    model: MultiT,
    dates: pd.DatetimeIndex,
    cfg: dict,
    tt: TailTable,
    crit: dict[str, float],
    pipe_crit: dict[tuple[str, int], float],
    name: str,
    rep: int,
) -> dict[str, object]:
    """대립 반복: 경로 수준 통계량 + 변화 후 검출·지연·참여·구간 경계 + 단기 q 신호 대비 CUSUM 지연."""
    tickers = list(cfg["universe"]["tickers"])
    rng = rep_rng(cfg, f"alt:{name}", rep)
    years = cfg["sample"]["evaluation_years"]
    ev_mask = (dates >= pd.Timestamp(f"{years[0]}-01-01")) & (dates < pd.Timestamp(f"{years[-1] + 1}-01-01"))
    eval_dates = dates[ev_mask]
    des = alt_design(model, dates, eval_dates, cfg, name, rng)
    R = simulate_panel(model, dates, tickers, rng, shock=des.shock)
    out = run_pipeline(R, cfg)
    Q = q_score(out.T[:, :, :N_PRIMARY_WIN], tt)
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
        "year": int(eval_dates[des.tau].year),
        "C_stage": st.C_stage,
        "M_subset": st.M_subset,
    }
    subs = all_subsets(tickers)
    for fam, ckey in cfg["alternatives"]["targets_resolved"][name]:
        s = tuple(ckey)
        st_ = member_stack(Q, Qlag, s, tickers)
        ja = j_all(st_)
        jmax = np.where(np.isfinite(ja), ja, -np.inf).max(axis=(0, 1))
        c = crit[f"day:{'+'.join(s)}"]
        sig = jmax >= c
        first = _first_at_or_after(sig, des.tau)
        det = first >= 0 and first < des.tau + H
        res[f"{fam}:detected_60"] = bool(det)
        res[f"{fam}:delay"] = (first - des.tau) if det else np.nan
        res[f"{fam}:any_sig_before_tau"] = bool(sig[: des.tau].any())
        if det:
            runs = [r for r in run_lengths(sig) if r[0] <= first <= r[1]]
            res[f"{fam}:ep_start_err"] = runs[0][0] - des.tau
            res[f"{fam}:ep_end_err"] = runs[0][1] - des.end
        res[f"{fam}:subset_index"] = subs.index(s)
    # 참여: 변화 후 H 일 안에 어떤 ETF 의 시차 Q 가 c_E 이상인 날이 있는가 (정책·창 최대)
    part = np.where(np.isfinite(Qlag), Qlag, -np.inf).max(axis=(1, 2)) >= c_E  # (ETF, 일)
    res["participated"] = part[:, win].any(axis=1)
    res["affected_mask"] = np.array([t in des.affected for t in tickers])
    # 단기 q EXPANSION (W2 규칙) 과 CUSUM (W1 동결 임계값·Q≥c_E) 의 첫 반응 지연 — 영향 ETF 별
    delays = {}
    for tk in des.affected:
        i = tickers.index(tk)
        r = R[tk].to_numpy(float)
        rec = {}
        for q in (3, 7, 14):
            d, _, _ = log_variance_ratio(realized_variance(r, q), q)
            ud, _, _ = midrank_past(d, 252)
            flag = ud[ev_mask] >= 0.9
            f = _first_at_or_after(flag, des.tau)
            rec[f"q{q}_EXP"] = (f - des.tau) if 0 <= f < des.tau + H else np.nan
        for p_i, p in enumerate(("A", "B", "base")):
            for w_i, w in enumerate(cfg["pipeline"]["windows_primary"]):
                Tw = out.T[i, p_i, w_i]
                fa = _first_at_or_after(np.isfinite(Tw) & (Tw >= pipe_crit[p, w]), des.tau)
                rec[f"cusum_w1crit_{p}_w{w}"] = (fa - des.tau) if 0 <= fa < des.tau + H else np.nan
                fq = _first_at_or_after(np.isfinite(Q[i, p_i, w_i]) & (Q[i, p_i, w_i] >= c_E), des.tau)
                rec[f"cusum_Q_{p}_w{w}"] = (fq - des.tau) if 0 <= fq < des.tau + H else np.nan
        # 단기 적격성 창 (3·7·14) — 보정 연간 최대 임계값 대비 첫 경보 (W1 규약)
        for w_i, w in enumerate(cfg["pipeline"]["windows_short_eligibility"]):
            for p_i, p in enumerate(("A", "B", "base")):
                Tw = out.T[i, p_i, N_PRIMARY_WIN + w_i]
                cs = crit.get(f"short:{tk}:{p}:{w}", np.inf)
                fa = _first_at_or_after(np.isfinite(Tw) & (Tw >= cs) & (out.pos_in_year >= 119), des.tau)
                rec[f"short_{p}_w{w}"] = (fa - des.tau) if 0 <= fa < des.tau + H else np.nan
        delays[tk] = rec
    res["delays"] = delays
    return res

"""정책 비교 (12B-lock-1 POLICY_COMPARISON_METHOD.md · 설정 `agreement`). 모두 관측 서술 — 유의성은 거르지 않는다.

- OFAT 쌍: 등록부 (parent → child) 마다 원장 열 대조(G4) · 공통/단독 유효일 · 원시·과거 백분위 차이 · 국면·이벤트 단계별 차이.
- 합의: 463개 실험 전 쌍의 Spearman ρ(공통 유효일, 정확값) · 결측 Jaccard · 경보 Jaccard · 평균 연결 군집.
NaN 은 NaN 으로 둔다 (0 대체 금지).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform
from scipy.stats import rankdata

LEDGER_KEYS = ("policy_id", "detector_type", "window_w", "reset_rule")
# changed_variable 토큰 → 바뀌어야 하는 원장 열 (calibration 은 h 만 바뀜 → 네 열 모두 불변)
VAR_TO_COL = {"reset": ("reset_rule",), "w": ("window_w",), "svr": ("policy_id",),
              "detector": ("detector_type",), "calibration": ()}
VERDICT = "NULL_MODEL_INVALID_DESCRIPTIVE"
MIN_COMMON = 250
STATES = ("BOTH", "PARENT_ONLY", "CHILD_ONLY", "NEITHER")


# ---------------------------------------------------------------- OFAT 대조 (G4)
def expected_cols(changed_variable: str) -> tuple[str, ...]:
    """changed_variable ('svr+reset' 같은 조합 포함) → 바뀌어야 할 원장 열 (LEDGER_KEYS 순서)."""
    want: set[str] = set()
    for tok in str(changed_variable).split("+"):
        tok = tok.strip()
        if tok not in VAR_TO_COL:
            raise KeyError(f"알 수 없는 changed_variable 토큰: {tok!r}")
        want.update(VAR_TO_COL[tok])
    return tuple(c for c in LEDGER_KEYS if c in want)


def ofat_observed(parent_keys: dict, child_keys: dict) -> tuple[str, ...]:
    """부모·자식 원장 열 중 실제로 다른 열 (문자열 그대로 비교, 'NA' 도 하나의 값)."""
    return tuple(c for c in LEDGER_KEYS if str(parent_keys[c]) != str(child_keys[c]))


def ofat_check(changed_variable: str, parent_keys: dict, child_keys: dict) -> dict:
    """엄격 판정(관측 집합 == 기대 집합) + 보조 설명(값이 'NA'=해당 없음으로 바뀐 열)."""
    obs = ofat_observed(parent_keys, child_keys)
    exp = expected_cols(changed_variable)
    extra = [c for c in obs if c not in exp]
    missing = [c for c in exp if c not in obs]
    na_extra = [c for c in extra if "NA" in (str(parent_keys[c]), str(child_keys[c]))]
    note = ";".join([f"{c}:{parent_keys[c]}->{child_keys[c]}" for c in extra] + [f"missing:{c}" for c in missing])
    return {"ofat_expected": ";".join(exp), "ofat_observed": ";".join(obs), "ofat_consistent": obs == exp,
            "ofat_extra_cols": ";".join(extra), "ofat_note": note,
            # 보조: 추가로 바뀐 열이 전부 'NA'(구조상 해당 없음) 로의 변화이고 기대 열은 모두 바뀐 경우
            "ofat_consistent_structural": (not missing) and len(na_extra) == len(extra)}


# ---------------------------------------------------------------- 기본 집계
def valid_state(vp: np.ndarray, vc: np.ndarray) -> np.ndarray:
    """부모·자식 유효 여부 → BOTH / PARENT_ONLY / CHILD_ONLY / NEITHER."""
    out = np.full(vp.size, "NEITHER", dtype=object)
    out[vp & vc] = "BOTH"
    out[vp & ~vc] = "PARENT_ONLY"
    out[~vp & vc] = "CHILD_ONLY"
    return out


def count_states(vp: np.ndarray, vc: np.ndarray) -> dict:
    s = valid_state(vp, vc)
    return {k: int((s == k).sum()) for k in STATES}


def spearman_exact(x: np.ndarray, y: np.ndarray, min_n: int = MIN_COMMON) -> tuple[float, int]:
    """공통 유효일 부분집합에서 평균 순위를 다시 매긴 Pearson (= scipy spearmanr). n < min_n → NaN."""
    m = np.isfinite(x) & np.isfinite(y)
    n = int(m.sum())
    if n < min_n:
        return np.nan, n
    rx, ry = rankdata(x[m]), rankdata(y[m])
    rx, ry = rx - rx.mean(), ry - ry.mean()
    den = np.sqrt((rx * rx).sum() * (ry * ry).sum())
    return (float((rx * ry).sum() / den) if den > 0 else np.nan), n


def jaccard(a: np.ndarray, b: np.ndarray) -> float:
    """불리언 집합 Jaccard. 합집합이 비면 NaN."""
    u = int((a | b).sum())
    return float((a & b).sum() / u) if u else np.nan


def nanmean_or_nan(x: np.ndarray) -> float:
    x = x[np.isfinite(x)]
    return float(x.mean()) if x.size else np.nan


# ---------------------------------------------------------------- 이벤트 단계
def event_phase_labels(events: pd.DataFrame, n_days: int) -> np.ndarray:
    """A_t20 구간 → 일별 단계 (onset [0,5] > during [6,dur] > normalization [dur+1,dur+40]). 여러 이벤트에 걸쳐도
    우선순위는 전역 적용, 축 밖(>n_days-1)은 잘라낸다. 해당 없음 = ''."""
    pri = {"onset": 3, "during": 2, "normalization": 1}
    lab = np.full(n_days, "", dtype=object)
    rank = np.zeros(n_days, dtype=int)
    for _, e in events.iterrows():
        s, dur = int(e["i_start"]), int(e["i_end"]) - int(e["i_start"])
        for ph, lo, hi in (("onset", 0, 5), ("during", 6, dur), ("normalization", dur + 1, dur + 40)):
            idx = np.arange(s + lo, s + hi + 1)
            idx = idx[(idx >= 0) & (idx < n_days)]
            upd = idx[rank[idx] < pri[ph]]
            lab[upd], rank[upd] = ph, pri[ph]
    return lab


# ---------------------------------------------------------------- 넓은 배열
def wide(df: pd.DataFrame, exp_ids: list[str], dates: np.ndarray, col: str) -> np.ndarray:
    """(experiment_id, date) 정렬 원장 → (실험, 날짜) 배열. 날짜축 일치를 먼저 확인."""
    n_e, n_d = len(exp_ids), dates.size
    assert len(df) == n_e * n_d
    assert (df["experiment_id"].to_numpy().reshape(n_e, n_d)[:, 0] == np.asarray(exp_ids, dtype=object)).all()
    assert (df["date"].to_numpy().reshape(n_e, n_d) == dates[None, :]).all()
    return df[col].to_numpy().reshape(n_e, n_d)


# ---------------------------------------------------------------- OFAT 쌍 비교
def compare_pair(i_p: int, i_c: int, T: np.ndarray, P: np.ndarray, A: np.ndarray, raw_ok: bool,
                 change: np.ndarray, phase: np.ndarray) -> tuple[dict, dict]:
    """한 쌍의 요약 지표와 일별 배열. T=원시 T, P=과거 전용 백분위, A=α 0.05 경보 (모두 (실험, 날짜))."""
    tp, tc, pp, pc = T[i_p], T[i_c], P[i_p], P[i_c]
    vp, vc = np.isfinite(tp), np.isfinite(tc)
    st = count_states(vp, vc)
    both = vp & vc
    d_raw = np.where(both, tc - tp, np.nan) if raw_ok else np.full(tp.size, np.nan)
    d_pct = np.where(np.isfinite(pp) & np.isfinite(pc), pc - pp, np.nan)
    rho, _ = spearman_exact(tp, tc)
    dr = d_raw[np.isfinite(d_raw)]
    dp = d_pct[np.isfinite(d_pct)]
    row = {"common_valid_days": st["BOTH"], "parent_only_days": st["PARENT_ONLY"], "child_only_days": st["CHILD_ONLY"],
           "both_na_days": st["NEITHER"], "raw_comparable": raw_ok,
           "raw_label": "COMPARABLE" if raw_ok else "RAW_NOT_COMPARABLE",
           "raw_diff_median": float(np.median(dr)) if dr.size else np.nan,
           "raw_diff_max_abs": float(np.abs(dr).max()) if dr.size else np.nan,
           "raw_spearman": rho, "pct_common_days": int(dp.size),
           "pct_diff_median": float(np.median(dp)) if dp.size else np.nan}
    for k in ("EXPANDING", "CONTRACTING", "STABLE"):
        row[f"pct_diff_mean_{k.lower()}"] = nanmean_or_nan(d_pct[change == k])
        row[f"pct_n_{k.lower()}"] = int(np.isfinite(d_pct[change == k]).sum())
    for k in ("onset", "during", "normalization"):
        row[f"pct_diff_mean_event_{k}"] = nanmean_or_nan(d_pct[phase == k])
        row[f"pct_n_event_{k}"] = int(np.isfinite(d_pct[phase == k]).sum())
    ap, ac = A[i_p], A[i_c]
    row.update({"alarm_days_parent": int(ap.sum()), "alarm_days_child": int(ac.sum()),
                "alarm_jaccard": jaccard(ap, ac), "added_na_days": st["PARENT_ONLY"], "verdict_label": VERDICT})
    daily = {"T_parent": tp, "T_child": tc, "diff_raw": d_raw, "pct_parent": pp, "pct_child": pc,
             "diff_pct": d_pct, "valid_state": valid_state(vp, vc)}
    return row, daily


# ---------------------------------------------------------------- 전 쌍 합의
def pairwise_agreement(T: np.ndarray, A: np.ndarray, min_n: int = MIN_COMMON) -> dict[str, np.ndarray]:
    """전 쌍 (상삼각 포함 정방행렬): n_common · 정확 Spearman · 결측 Jaccard · 경보 Jaccard.
    결측 Jaccard 는 두 NA 집합이 모두 비면(결측 패턴 동일) 1.0 으로 두고 missing_both_empty 로 표시한다.
    Spearman 은 행 a 마다 비공통일을 +inf 로 바꿔 axis=1 평균 순위 → 공통 부분집합의 정확 순위(inf 는 최상위로 밀림)."""
    V = np.isfinite(T)
    Vi, Ni, Ai = V.astype(np.int64), (~V).astype(np.int64), A.astype(np.int64)
    n_common = Vi @ Vi.T
    na_int = Ni @ Ni.T
    na_cnt = Ni.sum(1)
    na_uni = na_cnt[:, None] + na_cnt[None, :] - na_int
    al_int = Ai @ Ai.T
    al_cnt = Ai.sum(1)
    al_uni = al_cnt[:, None] + al_cnt[None, :] - al_int
    with np.errstate(invalid="ignore", divide="ignore"):
        miss_j = np.where(na_uni > 0, na_int / na_uni, 1.0)  # 둘 다 결측 없음 = 패턴 동일
        alarm_j = np.where(al_uni > 0, al_int / al_uni, np.nan)
    n_e = T.shape[0]
    rho = np.full((n_e, n_e), np.nan)
    for a in range(n_e - 1):
        b = np.arange(a + 1, n_e)
        M = V[a][None, :] & V[b]
        X = np.where(M, T[a][None, :], np.inf)
        Y = np.where(M, T[b], np.inf)
        RX = np.where(M, rankdata(X, axis=1), 0.0)
        RY = np.where(M, rankdata(Y, axis=1), 0.0)
        n = M.sum(1)
        with np.errstate(invalid="ignore", divide="ignore"):
            mx = RX.sum(1) / n
            my = RY.sum(1) / n
            cx = np.where(M, RX - mx[:, None], 0.0)
            cy = np.where(M, RY - my[:, None], 0.0)
            den = np.sqrt((cx * cx).sum(1) * (cy * cy).sum(1))
            r = np.where(den > 0, (cx * cy).sum(1) / den, np.nan)
        r[n < min_n] = np.nan
        rho[a, b] = r
        rho[b, a] = r
    np.fill_diagonal(rho, 1.0)
    return {"n_common": n_common, "spearman_raw": rho, "missing_jaccard": miss_j, "alarm_jaccard": alarm_j,
            "missing_both_empty": na_uni == 0}


def agreement_long(ids: list[str], ag: dict[str, np.ndarray]) -> pd.DataFrame:
    """정방행렬 → 상삼각 (exp_a < exp_b 인덱스 순) 긴 표."""
    ia, ib = np.triu_indices(len(ids), k=1)
    ids_a = np.asarray(ids, dtype=object)
    return pd.DataFrame({"exp_a": ids_a[ia], "exp_b": ids_a[ib], "n_common": ag["n_common"][ia, ib],
                         "spearman_raw": ag["spearman_raw"][ia, ib], "missing_jaccard": ag["missing_jaccard"][ia, ib],
                         "missing_both_empty": ag["missing_both_empty"][ia, ib],
                         "alarm_jaccard": ag["alarm_jaccard"][ia, ib]})


# ---------------------------------------------------------------- 군집
def cluster_labels(sim: np.ndarray, ids: list[str], cut: float = 0.1) -> tuple[np.ndarray, int]:
    """거리 1 − sim (NaN → 1.0) 평균 연결 → 거리 cut 에서 절단. 라벨은 (크기 내림차순, 첫 구성원 id) 로 재부여.
    반환 (1부터 시작하는 라벨, NaN 거리 개수(상삼각))."""
    D = 1.0 - sim
    iu = np.triu_indices(len(ids), k=1)
    n_nan = int(np.isnan(D[iu]).sum())
    D = np.where(np.isnan(D), 1.0, D)
    D = (D + D.T) / 2
    np.fill_diagonal(D, 0.0)
    Z = linkage(squareform(D, checks=False), method="average")
    raw = fcluster(Z, t=cut, criterion="distance")
    groups: dict[int, list[int]] = {}
    for i, g in enumerate(raw):
        groups.setdefault(int(g), []).append(i)
    order = sorted(groups.values(), key=lambda m: (-len(m), min(ids[i] for i in m)))
    lab = np.zeros(len(ids), dtype=int)
    for k, mem in enumerate(order, start=1):
        lab[mem] = k
    return lab, n_nan


def cluster_summary(lab: np.ndarray, sim: np.ndarray, ids: list[str], fam: list[str], kind: str) -> pd.DataFrame:
    """군집별 크기 · 구성 family 수 · 대표(다른 구성원과의 평균 유사도 최대) · 군집 내 평균 유사도."""
    rows = []
    for k in np.unique(lab):
        mem = np.flatnonzero(lab == k)
        fc = pd.Series([fam[i] for i in mem]).value_counts()
        fstr = ";".join(f"{f}:{n}" for f, n in sorted(fc.items(), key=lambda t: (-t[1], t[0])))
        if mem.size == 1:
            rep, within = ids[mem[0]], np.nan
        else:
            S = sim[np.ix_(mem, mem)].astype(float).copy()
            np.fill_diagonal(S, np.nan)
            with np.errstate(invalid="ignore"):
                mrow = np.nanmean(np.where(np.isfinite(S), S, np.nan), axis=1)
            best = np.where(np.isfinite(mrow), mrow, -np.inf)
            rep = min((ids[mem[j]] for j in np.flatnonzero(best == best.max())))
            iu = np.triu_indices(mem.size, k=1)
            within = nanmean_or_nan(S[iu])
        rows.append({"cluster_kind": kind, "cluster_id": int(k), "size": int(mem.size), "member_families": fstr,
                     "representative": rep, "mean_within_similarity": within})
    return pd.DataFrame(rows)

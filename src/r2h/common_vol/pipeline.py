"""10번 파이프라인 — 09(W4) 그룹 A 상태 승계 검증 → 12개 규칙 일별 판정 → 구간 → 비교·사례 (계약 10-lock-1).

09 파이프라인은 호출하지 않는다. W4 results/ 는 읽기만 한다. 결과는 research/common_volatility_candidates_10/results/.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from r2h.common_vol.core import (
    candidate_flag,
    containment_map,
    extract_intervals,
    interval_profile,
    jaccard,
    rule_id,
)

OUT_DIR = "research/common_volatility_candidates_10"
CFG_PATH = "configs/t19_common_vol_candidates_v1.json"


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load_cfg(root: Path) -> dict:
    return json.loads((root / CFG_PATH).read_text(encoding="utf-8"))


def write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, lineterminator="\n", float_format="%.6g")


# ── 1. 승계 게이트 ─────────────────────────────────────────────────────────
def verify_w4(root: Path, cfg: dict) -> dict:
    """09 산출물 지문·집계가 기록과 같은지 확인한다. 하나라도 다르면 AssertionError."""
    man = json.loads((root / cfg["w4_manifest"]).read_text(encoding="utf-8"))
    # 매니페스트 작성 뒤 W4 최종 커밋 172cbb3 이 문서 한 줄(검증 파일 수 89→91)만 고쳤다. 그 파일만 새 지문으로 대조한다.
    post = cfg["w4_post_manifest_edits"]
    bad = [p for p, h in man["files"].items() if sha(root / p) != post.get(p, {}).get("sha256", h)]
    nb = man["notebook"]
    assert sha(root / nb["path"]) == nb["sha256"], "09 노트북 변경"
    assert not bad, f"W4 산출물 변경: {bad}"
    w4 = root / cfg["w4_dir"]
    for line in (w4 / "CONTRACT_FREEZE_SHA256.txt").read_text().splitlines():
        d, name = line.split(maxsplit=1)
        assert sha(root / name) == d, f"W4 동결 파일 변경: {name}"
    inp = cfg["w4_inputs"]
    gs = pd.read_csv(root / inp["group_daily_states"], parse_dates=["date"])
    gc = pd.read_csv(root / inp["global_daily_counts"], parse_dates=["date"])
    agg = gs.assign(on=(gs["GROUP_A"] == 1).astype(int), ev=gs["GROUP_A"].notna().astype(int)).groupby(
        ["date", "q"], as_index=False).agg(n_A=("on", "sum"), n_eval_A=("ev", "sum"), n=("group", "size"))
    m = gc.merge(agg, on=["date", "q"], suffixes=("", "_re"), validate="one_to_one")
    assert len(m) == len(gc) == len(agg), "날짜·q 행 수 불일치"
    assert (agg["n"] == cfg["n_groups"]).all(), "그룹 수 ≠ 17"
    assert (m["n_A"] == m["n_A_re"]).all() and (m["n_eval_A"] == m["n_eval_A_re"]).all(), "N_A 재집계 불일치"
    gbp = pd.read_csv(root / inp["global_by_period"])
    m["period"] = period_of(m["date"], cfg)
    rows = []
    for (per, q), x in m.groupby(["period", "q"]):
        rec = gbp[(gbp["period"] == per) & (gbp["q"] == q)].iloc[0]
        full = x[x["n_eval_A_re"] == cfg["n_groups"]]
        mx = int(x["n_A_re"].max())
        d17 = int((full["n_A_re"] == cfg["n_groups"]).sum())
        na = int((x["n_eval_A_re"] < cfg["n_groups"]).sum())
        assert mx == rec["max_n_A"] and d17 == rec["days17_A"] and na == rec["na_A"], (per, q)
        rows.append({"period": per, "q": q, "days": len(x), "max_n_A": mx, "days17_A": d17, "na_A": na,
                     "w4_max_n_A": int(rec["max_n_A"]), "w4_days17_A": int(rec["days17_A"]), "w4_na_A": int(rec["na_A"])})
    si = pd.read_csv(root / inp["shock_intervals"])
    fin = json.loads((root / inp["w4_final"]).read_text(encoding="utf-8"))
    assert len(si) == 0 and fin["verdict"]["verdict"] == "VALID_ZERO_INTERVALS", "W4 판정 변경"
    return {"n_manifest_files": len(man["files"]), "post_manifest_edits": post, "notebook_sha256": nb["sha256"], "period_check": pd.DataFrame(rows),
            "w4_verdict": fin["verdict"]["verdict"], "w4_intervals": len(si), "rows_checked": len(m)}


def period_of(dates: pd.Series, cfg: dict) -> pd.Series:
    y = pd.to_datetime(pd.Series(dates)).dt.year.to_numpy()
    out = np.full(y.size, "", dtype=object)
    for name, (a, b) in cfg["periods"].items():
        out[(y >= a) & (y <= b)] = name
    return pd.Series(out, index=pd.Series(dates).index)


# ── 2. 입력 정리 ───────────────────────────────────────────────────────────
def load_states(root: Path, cfg: dict) -> dict:
    gs = pd.read_csv(root / cfg["w4_inputs"]["group_daily_states"], parse_dates=["date"])
    eg = pd.read_csv(root / cfg["w2_exposure_groups"], dtype={"ticker": str})
    groups = list(dict.fromkeys(eg["exposure_group"]))
    assert len(groups) == cfg["n_groups"] and set(groups) == set(gs["group"])
    names = dict(zip(eg["ticker"], eg["name"]))
    label = {g: ("KOSPI200 동일노출(Core Pair)" if g not in names else f"{g} {names[g]}") for g in groups}
    dates = pd.DatetimeIndex(sorted(gs["date"].unique()))
    mats = {}
    for q in cfg["q_list"]:
        x = gs[gs["q"] == q]
        mats[q] = {k: x.pivot(index="date", columns="group", values=f"GROUP_{k}").reindex(index=dates, columns=groups).to_numpy(float)
                   for k in ("A", "B", "AB")}
    return {"dates": dates, "groups": groups, "label": label, "mats": mats, "eg": eg}


def rules(cfg: dict) -> pd.DataFrame:
    main = {(v["q"], v["k"]): c for c, v in cfg["main_candidates"].items()}
    rows = []
    for q in cfg["q_list"]:
        for k in cfg["k_grid"]:
            rid = rule_id(q, k)
            role = cfg["rule_roles"][rid]
            rows.append({"rule": rid, "q": q, "k": k, "role": role, "candidate": main.get((q, k), ""),
                         "label": main.get((q, k), "") or {"REFERENCE_W2": "W2 참고", "REFERENCE_W4": "W4 연결 참고",
                                                           "DIAGNOSTIC": "진단", "HORIZON_CONTROL": "기간 통제"}[role]})
    return pd.DataFrame(rows)


def daily_table(st: dict, cfg: dict, rl: pd.DataFrame) -> pd.DataFrame:
    n = cfg["n_groups"]
    out = pd.DataFrame({"date": st["dates"]})
    out["period"] = period_of(out["date"], cfg).to_numpy()
    for q in cfg["q_list"]:
        a = st["mats"][q]["A"]
        out[f"n_A_q{q}"] = (a == 1).sum(axis=1)
        out[f"n_eval_A_q{q}"] = np.isfinite(a).sum(axis=1)
        out[f"P_A_q{q}"] = np.where(out[f"n_eval_A_q{q}"] == n, out[f"n_A_q{q}"] / n, np.nan)
        out[f"n_B_q{q}"] = (st["mats"][q]["B"] == 1).sum(axis=1)
        out[f"n_AB_q{q}"] = (st["mats"][q]["AB"] == 1).sum(axis=1)
    for _, r in rl.iterrows():
        out[r["rule"]] = candidate_flag(out[f"n_A_q{r['q']}"], out[f"n_eval_A_q{r['q']}"], r["k"], n)
    return out


# ── 3. 구간 ────────────────────────────────────────────────────────────────
def all_intervals(daily: pd.DataFrame, st: dict, cfg: dict, rl: pd.DataFrame) -> pd.DataFrame:
    rows = []
    dates = st["dates"]
    for _, r in rl.iterrows():
        m = st["mats"][r["q"]]
        for per in cfg["periods"]:
            mask = (daily["period"] == per).to_numpy()
            for j, iv in enumerate(extract_intervals(daily[r["rule"]].to_numpy(), mask), start=1):
                prof = interval_profile(iv["i0"], iv["i1"], m["A"], m["B"], m["AB"], st["groups"], dates)
                rows.append({
                    "interval_id": f"{r['rule']}_{per[:3]}_{j:03d}", "rule": r["rule"], "candidate": r["candidate"],
                    "role": r["role"], "q": r["q"], "k": r["k"], "period": per,
                    "start": dates[iv["i0"]].date(), "end": dates[iv["i1"]].date(),
                    "duration_trading_days": iv["i1"] - iv["i0"] + 1, **prof,
                    "left_censored": iv["left_censored"], "right_censored": iv["right_censored"],
                    "entry_after": iv["entry_after"], "exit_reason": iv["exit_reason"],
                    "state_before": iv["state_before"], "state_after": iv["state_after"],
                    "i0": iv["i0"], "i1": iv["i1"],
                })
    return pd.DataFrame(rows)


def check_intervals(iv: pd.DataFrame, daily: pd.DataFrame, cfg: dict, rl: pd.DataFrame) -> pd.DataFrame:
    """구간 무결성: 중복 없음, 후보일 수 = 지속일 합, 최대 N_A = 일별 원자료, 같은 q 의 날짜 포함관계."""
    rows = []
    for _, r in rl.iterrows():
        for per in cfg["periods"]:
            d = daily[daily["period"] == per]
            x = iv[(iv["rule"] == r["rule"]) & (iv["period"] == per)]
            cover = np.concatenate([np.arange(a, b + 1) for a, b in zip(x["i0"], x["i1"])]) if len(x) else np.array([], int)
            assert np.unique(cover).size == cover.size, "같은 날짜가 두 구간에 포함"
            days = int((d[r["rule"]] == 1).sum())
            assert days == int(x["duration_trading_days"].sum()) == cover.size, "후보일 수 ≠ 지속일 합"
            assert set(cover) == set(d.index[d[r["rule"]] == 1]), "구간 날짜 ≠ 후보일"
            na_inside = int(daily.loc[cover, r["rule"]].isna().sum()) if cover.size else 0
            assert na_inside == 0
            for _, y in x.iterrows():
                seg = daily.loc[y["i0"]:y["i1"], f"n_A_q{r['q']}"]
                assert int(seg.max()) == y["max_n_A"] and int(seg.min()) >= r["k"]
                assert y["n_groups_always"] <= y["max_n_A"] <= y["n_groups_ever"]
            rows.append({"rule": r["rule"], "period": per, "candidate_days": days, "n_intervals": len(x),
                         "na_days": int(d[r["rule"]].isna().sum())})
    # 같은 q: k 가 커지면 날짜 집합이 줄어드는 포함관계 (전체 달력)
    for q in cfg["q_list"]:
        ks = sorted(cfg["k_grid"])
        for k1, k2 in zip(ks[:-1], ks[1:]):
            loose, strict = daily[rule_id(q, k1)] == 1, daily[rule_id(q, k2)] == 1
            assert not (strict & ~loose).any(), f"포함관계 위반 q{q} k{k1}→{k2}"
    return pd.DataFrame(rows)


# ── 4. 비교 ────────────────────────────────────────────────────────────────
def rule_summary(iv: pd.DataFrame, daily: pd.DataFrame, cfg: dict, rl: pd.DataFrame, period: str = "PRIMARY") -> pd.DataFrame:
    d = daily[daily["period"] == period]
    rows = []
    for _, r in rl.iterrows():
        x = iv[(iv["rule"] == r["rule"]) & (iv["period"] == period)]
        obs_max = int(d[f"n_A_q{r['q']}"].max())
        dur = x["duration_trading_days"]
        top = x.sort_values(["duration_trading_days", "start"], ascending=[False, True]).head(5)
        rows.append({
            "rule": r["rule"], "candidate": r["candidate"], "label": r["label"], "role": r["role"], "q": r["q"], "k": r["k"],
            "period": period, "days_in_period": len(d), "evaluable_days": int(d[r["rule"]].notna().sum()),
            "n_intervals": len(x), "candidate_days": int((d[r["rule"]] == 1).sum()),
            "candidate_share": float((d[r["rule"]] == 1).mean()),
            "n_one_day": int((dur == 1).sum()),
            "duration_mean": float(dur.mean()) if len(x) else np.nan,
            "duration_median": float(dur.median()) if len(x) else np.nan,
            "duration_max": int(dur.max()) if len(x) else 0,
            "observed_max_n_A": obs_max, "gap_k_minus_max": max(r["k"] - obs_max, 0),
            "mean_n_A_on_candidate_days": float(d.loc[d[r["rule"]] == 1, f"n_A_q{r['q']}"].mean()) if len(x) else np.nan,
            "mean_stability_jaccard": float(x["stability_consecutive_jaccard"].mean()) if len(x) else np.nan,
            "mean_core_share": float(x["core_share"].mean()) if len(x) else np.nan,
            "max_n_groups_ever": int(x["n_groups_ever"].max()) if len(x) else 0,
            "first_start": str(x["start"].min()) if len(x) else "",
            "last_end": str(x["end"].max()) if len(x) else "",
            "top5_longest": "; ".join(f"{a}~{b} ({c}일)" for a, b, c in zip(top["start"], top["end"], top["duration_trading_days"])),
            "censored_intervals": int(((x["left_censored"] != False) | (x["right_censored"] != False)).sum()),  # noqa: E712
        })
    return pd.DataFrame(rows)


def yearly(iv: pd.DataFrame, daily: pd.DataFrame, rl: pd.DataFrame) -> pd.DataFrame:
    rows = []
    y = daily["date"].dt.year
    for _, r in rl.iterrows():
        for yr in sorted(y.unique()):
            d = daily[y == yr]
            x = iv[(iv["rule"] == r["rule"]) & (pd.to_datetime(iv["start"]).dt.year == yr)]
            rows.append({"rule": r["rule"], "candidate": r["candidate"], "q": r["q"], "k": r["k"], "year": int(yr),
                         "period": d["period"].iloc[0], "candidate_days": int((d[r["rule"]] == 1).sum()),
                         "intervals_started": len(x), "na_days": int(d[r["rule"]].isna().sum())})
    return pd.DataFrame(rows)


def jaccard_matrix(daily: pd.DataFrame, rl: pd.DataFrame, period: str = "PRIMARY") -> pd.DataFrame:
    d = daily[daily["period"] == period]
    sets = {r: set(d.index[d[r] == 1]) for r in rl["rule"]}
    rows = []
    for a in rl["rule"]:
        for b in rl["rule"]:
            rows.append({"rule_a": a, "rule_b": b, "jaccard": jaccard(sets[a], sets[b]),
                         "n_a": len(sets[a]), "n_b": len(sets[b]), "n_both": len(sets[a] & sets[b]),
                         "a_subset_of_b": sets[a] <= sets[b]})
    return pd.DataFrame(rows)


def split_map(iv: pd.DataFrame, cfg: dict, period: str = "PRIMARY") -> tuple[pd.DataFrame, pd.DataFrame]:
    """같은 q 에서 인접 k 쌍: 엄격 구간 → 포함 완화 구간, 완화 구간별 자식 수 (0 소멸 · 1 유지/축소 · ≥2 분할)."""
    links, kids = [], []
    for q in cfg["q_list"]:
        ks = sorted(cfg["k_grid"])
        for k1, k2 in zip(ks[:-1], ks[1:]):
            lo = iv[(iv["rule"] == rule_id(q, k1)) & (iv["period"] == period)]
            hi = iv[(iv["rule"] == rule_id(q, k2)) & (iv["period"] == period)]
            mp = containment_map(hi, lo) if len(hi) else pd.Series(dtype=object)
            for sid, pid in mp.items():
                links.append({"q": q, "k_loose": k1, "k_strict": k2, "strict_id": sid, "loose_id": pid})
            cnt = mp.value_counts()
            for _, r in lo.iterrows():
                c = int(cnt.get(r["interval_id"], 0))
                kept = int(hi[hi["interval_id"].isin(mp.index[mp == r["interval_id"]])]["duration_trading_days"].sum())
                kids.append({"q": q, "k_loose": k1, "k_strict": k2, "loose_id": r["interval_id"], "start": r["start"], "end": r["end"],
                             "loose_days": r["duration_trading_days"], "n_children": c, "strict_days_kept": kept,
                             "relation": "소멸" if c == 0 else ("유지·축소" if c == 1 else "분할")})
    return pd.DataFrame(links), pd.DataFrame(kids)


def horizon_compare(iv: pd.DataFrame, daily: pd.DataFrame, cfg: dict, period: str = "PRIMARY") -> pd.DataFrame:
    """같은 k 에서 q=20 vs q=60: 날짜 겹침, Jaccard, 서로 겹치는 구간 수."""
    d = daily[daily["period"] == period]
    rows = []
    for k in cfg["k_grid"]:
        a, b = rule_id(20, k), rule_id(60, k)
        sa, sb = set(d.index[d[a] == 1]), set(d.index[d[b] == 1])
        xa = iv[(iv["rule"] == a) & (iv["period"] == period)]
        xb = iv[(iv["rule"] == b) & (iv["period"] == period)]
        pairs = sum(1 for _, u in xa.iterrows() for _, v in xb.iterrows() if u["i0"] <= v["i1"] and v["i0"] <= u["i1"])
        a_hit = sum(1 for _, u in xa.iterrows() if ((xb["i0"] <= u["i1"]) & (xb["i1"] >= u["i0"])).any())
        rows.append({"k": k, "q20_days": len(sa), "q60_days": len(sb), "both_days": len(sa & sb),
                     "q20_only_days": len(sa - sb), "q60_only_days": len(sb - sa), "jaccard": jaccard(sa, sb),
                     "q20_intervals": len(xa), "q60_intervals": len(xb), "overlapping_pairs": pairs,
                     "q20_intervals_touching_q60": a_hit,
                     "q20_max": int(d["n_A_q20"].max()), "q60_max": int(d["n_A_q60"].max())})
    return pd.DataFrame(rows)


def group_participation(daily: pd.DataFrame, st: dict, cfg: dict, period: str = "PRIMARY") -> pd.DataFrame:
    """주 후보별 후보일 중 각 그룹이 A 인 비율 (참여 기여) + 주분석 전체 A 비율."""
    d = daily[daily["period"] == period]
    rows = []
    for c, v in cfg["main_candidates"].items():
        a = st["mats"][v["q"]]["A"]
        on = d.index[d[rule_id(v["q"], v["k"])] == 1]
        for j, g in enumerate(st["groups"]):
            rows.append({"candidate": c, "q": v["q"], "k": v["k"], "group": g, "label": st["label"][g],
                         "share_on_candidate_days": float((a[on, j] == 1).mean()) if len(on) else np.nan,
                         "share_all_primary_days": float((a[d.index, j] == 1).mean()),
                         "candidate_days": len(on)})
    return pd.DataFrame(rows)


def b_ab_inside_outside(daily: pd.DataFrame, cfg: dict, period: str = "PRIMARY") -> pd.DataFrame:
    d = daily[daily["period"] == period]
    rows = []
    for c, v in cfg["main_candidates"].items():
        f = d[rule_id(v["q"], v["k"])] == 1
        for side, m in (("후보일", f), ("비후보일", ~f)):
            x = d[m]
            rows.append({"candidate": c, "q": v["q"], "k": v["k"], "side": side, "days": len(x),
                         "mean_n_B": float(x[f"n_B_q{v['q']}"].mean()) if len(x) else np.nan,
                         "max_n_B": int(x[f"n_B_q{v['q']}"].max()) if len(x) else 0,
                         "mean_n_AB": float(x[f"n_AB_q{v['q']}"].mean()) if len(x) else np.nan,
                         "max_n_AB": int(x[f"n_AB_q{v['q']}"].max()) if len(x) else 0,
                         "share_days_AB_ge1": float((x[f"n_AB_q{v['q']}"] >= 1).mean()) if len(x) else np.nan})
    return pd.DataFrame(rows)


def event_table(iv: pd.DataFrame, daily: pd.DataFrame, st: dict, cfg: dict, rl: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for ev, e in cfg["events"].items():
        s, en = map(pd.Timestamp, e["window"])
        w = daily[(daily["date"] >= s) & (daily["date"] <= en)]
        ws, we = map(pd.Timestamp, e["w2_ref"])
        for _, r in rl.iterrows():
            x = iv[(iv["rule"] == r["rule"]) & (pd.to_datetime(iv["end"]) >= s) & (pd.to_datetime(iv["start"]) <= en)]
            col = f"n_A_q{r['q']}"
            i = w[col].idxmax()
            cand = w[w[r["rule"]] == 1]
            in_ref = cand[(cand["date"] >= ws) & (cand["date"] <= we)]
            rows.append({"event": ev, "rule": r["rule"], "candidate": r["candidate"], "q": r["q"], "k": r["k"],
                         "window": f"{s.date()}~{en.date()}", "candidate_days": len(cand),
                         "candidate_days_in_w2_ref": len(in_ref), "w2_ref_days": int(((w["date"] >= ws) & (w["date"] <= we)).sum()),
                         "n_intervals": len(x),
                         "intervals": "; ".join(f"{a}~{b} ({c}일, 최대 {m})" for a, b, c, m in zip(x["start"], x["end"], x["duration_trading_days"], x["max_n_A"])),
                         "window_max_n_A": int(w[col].max()), "window_max_first_date": str(w.loc[i, "date"].date()),
                         "first_candidate_day": str(cand["date"].min().date()) if len(cand) else "",
                         "last_candidate_day": str(cand["date"].max().date()) if len(cand) else ""})
    return pd.DataFrame(rows)


def event_dropped_days(daily: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """사례 창 안에서 C1(q20 k9) 후보일 중 k=10·12 에서 사라지는 날짜와 그날 N_A, q60 상태."""
    rows = []
    for ev, e in cfg["events"].items():
        s, en = map(pd.Timestamp, e["window"])
        w = daily[(daily["date"] >= s) & (daily["date"] <= en) & (daily["q20_k9"] == 1)]
        for _, r in w.iterrows():
            rows.append({"event": ev, "date": r["date"].date(), "n_A_q20": int(r["n_A_q20"]), "n_A_q60": int(r["n_A_q60"]),
                         "in_C2": bool(r["q20_k10"] == 1), "in_C3": bool(r["q20_k12"] == 1), "in_C4": bool(r["q60_k6"] == 1),
                         "n_B_q20": int(r["n_B_q20"]), "n_AB_q20": int(r["n_AB_q20"])})
    return pd.DataFrame(rows)


def compare_w2_w3(root: Path, iv: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """주 후보 구간이 W2 교차 그룹 구간(HIGH_LEVEL·EXPANSION) 과 W3 공동 에피소드와 겹치는지 (비교만)."""
    w2 = pd.read_csv(root / cfg["w2_cross_intervals_group"], parse_dates=["interval_start", "interval_end"])
    w2 = w2[(w2["year_status"] == "PRIMARY") & w2["channel"].isin(["HIGH_LEVEL", "EXPANSION"])]
    w3 = pd.read_csv(root / cfg["w3_joint_episodes"], parse_dates=["episode_start_at", "episode_end_at"])
    w3 = w3[(w3["episode_start_at"].dt.year >= 2021) & (w3["episode_start_at"].dt.year <= 2025)]
    rows = []
    for c in cfg["main_candidates"]:
        x = iv[(iv["candidate"] == c) & (iv["period"] == "PRIMARY")]
        for _, r in x.iterrows():
            s, e = pd.Timestamp(r["start"]), pd.Timestamp(r["end"])
            h = w2[(w2["interval_end"] >= s) & (w2["interval_start"] <= e)]
            j = w3[(w3["episode_end_at"] >= s) & (w3["episode_start_at"] <= e)]
            rows.append({"candidate": c, "interval_id": r["interval_id"], "start": r["start"], "end": r["end"],
                         "duration": r["duration_trading_days"], "max_n_A": r["max_n_A"],
                         "w2_overlap_n": len(h),
                         "w2_overlap": "; ".join(f"{ch} {a.date()}~{b.date()} (최대 {m}그룹)" for ch, a, b, m in zip(h["channel"], h["interval_start"], h["interval_end"], h["max_n_group"])),
                         "w3_joint_episode_overlap_n": len(j)})
    return pd.DataFrame(rows)


def run(root: Path) -> dict:
    cfg = load_cfg(root)
    for line in (root / OUT_DIR / "CONTRACT_FREEZE_SHA256.txt").read_text().splitlines():
        d, name = line.split(maxsplit=1)
        assert sha(root / name) == d, f"10 동결 파일 변경: {name}"
    ver = verify_w4(root, cfg)
    st = load_states(root, cfg)
    rl = rules(cfg)
    daily = daily_table(st, cfg, rl)
    iv = all_intervals(daily, st, cfg, rl)
    integ = check_intervals(iv, daily, cfg, rl)
    summ = rule_summary(iv, daily, cfg, rl)
    links, kids = split_map(iv, cfg)
    out = {
        "cfg": cfg, "verify": ver, "states": st, "rules": rl, "daily": daily, "intervals": iv, "integrity": integ,
        "summary": summ, "summary_pilot": rule_summary(iv, daily, cfg, rl, "PILOT"),
        "summary_2026": rule_summary(iv, daily, cfg, rl, "PARTIAL_NON_BLIND"),
        "yearly": yearly(iv, daily, rl), "jaccard": jaccard_matrix(daily, rl), "split_links": links, "split_kids": kids,
        "horizon": horizon_compare(iv, daily, cfg), "participation": group_participation(daily, st, cfg),
        "b_ab": b_ab_inside_outside(daily, cfg), "events": event_table(iv, daily, st, cfg, rl),
        "event_days": event_dropped_days(daily, cfg), "w2w3": compare_w2_w3(root, iv, cfg),
    }
    res = root / OUT_DIR / "results"
    for name in ("daily", "intervals", "integrity", "summary", "summary_pilot", "summary_2026", "yearly", "jaccard",
                 "split_links", "split_kids", "horizon", "participation", "b_ab", "events", "event_days", "w2w3"):
        df = out[name].copy()
        if name == "daily":
            df["date"] = df["date"].dt.date
        write_csv(df, res / f"{name}.csv")
    write_csv(ver["period_check"], res / "w4_inheritance_check.csv")
    return out


def results_digest(root: Path) -> dict[str, str]:
    return {p.name: sha(p) for p in sorted((root / OUT_DIR / "results").glob("*.csv"))}


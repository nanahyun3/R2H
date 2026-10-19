"""12B P04 — 정책 비교: 등록부 OFAT 쌍 대조(G4) · 전 쌍 합의(Spearman/결측/경보 Jaccard) · 평균 연결 군집.

출력: outputs/t22/policy_parent_child_daily.parquet ·
results/{ofat_pair_comparison,ofat_pairs_skipped,policy_agreement,agreement_clusters,agreement_cluster_summary}.csv
모두 관측 서술 (NULL_MODEL_INVALID_DESCRIPTIVE). CPU, 난수 없음 (검증 표본만 고정 시드).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from r2h.k200_overlay import compare as C  # noqa: E402

OUT = ROOT / "outputs/t22"
RES = ROOT / "research/k200_cusum_overlay_12b/results"
REG = ROOT / "research/k200_cusum_controlled_12/EXPERIMENT_REGISTRY.csv"
SEED = 20261019
COLS = ["experiment_id", "date", *C.LEDGER_KEYS, "cusum_raw_T", "T_past_pct", "cusum_alarm_a05"]


def main() -> int:
    t0 = time.time()
    df = pd.read_parquet(OUT / "policy_market_aligned.parquet", columns=COLS)
    df = df.sort_values(["experiment_id", "date"], kind="mergesort").reset_index(drop=True)
    ids = list(pd.unique(df["experiment_id"]))
    dates = df.loc[df["experiment_id"] == ids[0], "date"].to_numpy()
    n_e, n_d = len(ids), dates.size
    T = C.wide(df, ids, dates, "cusum_raw_T").astype(float)
    P = C.wide(df, ids, dates, "T_past_pct").astype(float)
    A = C.wide(df, ids, dates, "cusum_alarm_a05").astype(bool)
    keys = {e: {k: str(v) for k, v in r.items()} for e, r in
            df.drop_duplicates("experiment_id").set_index("experiment_id")[list(C.LEDGER_KEYS)].iterrows()}
    pos = {e: i for i, e in enumerate(ids)}
    reg = pd.read_csv(REG, keep_default_na=False, dtype=str)

    # 국면(앵커 20) · 이벤트 단계 (A_t20) — 날짜축 확인
    vr = pd.read_parquet(OUT / "volatility_regime_daily.parquet")
    vr = vr[vr["anchor_w"] == 20].sort_values("date").reset_index(drop=True)
    assert (vr["date"].to_numpy() == dates).all(), "국면 날짜축 불일치"
    change = vr["change_past"].astype(str).to_numpy(dtype=object)
    ev = pd.read_csv(RES / "events_table.csv", keep_default_na=False, dtype={"interval_id": str})
    ev = ev[ev["event_set"] == "A_t20"].reset_index(drop=True)
    assert len(ev) == 11
    ds = pd.to_datetime(pd.Series(dates)).dt.strftime("%Y-%m-%d").to_numpy()
    assert (ds[ev["i_start"].astype(int)] == ev["start"].to_numpy()).all() and \
           (ds[ev["i_end"].astype(int)] == ev["end"].to_numpy()).all(), "이벤트 위치-날짜 불일치"
    phase = C.event_phase_labels(ev, n_d)

    # 원장 vs 등록부 정합 (수정하지 않고 보고만)
    regi = reg.set_index("experiment_id")
    mism_comp = [e for e in ids if regi.loc[e, "computable_days"] != "" and
                 int(float(regi.loc[e, "computable_days"])) != int(np.isfinite(T[pos[e]]).sum())]
    mism_alarm = [e for e in ids if regi.loc[e, "observed_alarm_days_a05"] != "" and
                  int(float(regi.loc[e, "observed_alarm_days_a05"])) != int(A[pos[e]].sum())]

    # ---------------- OFAT 쌍
    rows, skipped, daily = [], [], []
    for _, r in reg.iterrows():
        par, chi = r["parent_experiment_id"], r["experiment_id"]
        if par == "":
            continue
        miss = [x for x in (par, chi) if x not in pos]
        if miss:
            skipped.append({"parent": par, "child": chi, "family": r["family"], "changed_variable": r["changed_variable"],
                            "reason": "NO_DAILY_SERIES:" + ";".join(miss)})
            continue
        chk = C.ofat_check(r["changed_variable"], keys[par], keys[chi])
        raw_ok = keys[par]["detector_type"] == keys[chi]["detector_type"]
        m, d = C.compare_pair(pos[par], pos[chi], T, P, A, raw_ok, change, phase)
        pid = f"{par}__{chi}"
        rows.append({"pair_id": pid, "parent": par, "child": chi, "family": r["family"],
                     "changed_variable": r["changed_variable"], "value_before": r["value_before"],
                     "value_after": r["value_after"], "registry_ofat_check": r["ofat_check"], **chk, **m})
        daily.append(pd.DataFrame({"pair_id": pid, "parent": par, "child": chi, "date": dates, **d}))
    oc = pd.DataFrame(rows)
    oc.to_csv(RES / "ofat_pair_comparison.csv", index=False)
    pd.DataFrame(skipped, columns=["parent", "child", "family", "changed_variable", "reason"]).to_csv(
        RES / "ofat_pairs_skipped.csv", index=False)
    pd.concat(daily, ignore_index=True).to_parquet(OUT / "policy_parent_child_daily.parquet", index=False)
    t1 = time.time()

    # ---------------- 전 쌍 합의
    ag = C.pairwise_agreement(T, A)
    al = C.agreement_long(ids, ag)
    al.to_csv(RES / "policy_agreement.csv", index=False)
    t2 = time.time()

    # Spearman 정확성 검증: 고정 시드 20쌍 (n_common ≥ 250) + 서로 다른 detector 쌍 포함
    rng = np.random.default_rng(SEED)
    ok = al[al["n_common"] >= C.MIN_COMMON]
    det = {e: keys[e]["detector_type"] for e in ids}
    cross = ok[[det[a] != det[b] for a, b in zip(ok["exp_a"], ok["exp_b"])]]
    pick = pd.concat([ok.iloc[rng.choice(len(ok), 14, replace=False)], cross.iloc[rng.choice(len(cross), 6, replace=False)]])
    diffs = []
    for a, b, rr in zip(pick["exp_a"], pick["exp_b"], pick["spearman_raw"]):
        x, y = T[pos[a]], T[pos[b]]
        mk = np.isfinite(x) & np.isfinite(y)
        diffs.append(abs(spearmanr(x[mk], y[mk]).statistic - rr))
    sp_max = float(np.max(diffs))
    # OFAT 표 raw_spearman ↔ 합의 행렬 일치
    rho = ag["spearman_raw"]
    ofat_vs_ag = np.array([rho[pos[p], pos[c]] for p, c in zip(oc["parent"], oc["child"])])
    agree_ok = np.allclose(oc["raw_spearman"].to_numpy(float), ofat_vs_ag, atol=1e-12, equal_nan=True)

    # ---------------- 군집
    fam = [regi.loc[e, "family"] for e in ids]
    vlab, v_nan = C.cluster_labels(rho, ids)
    mlab, m_nan = C.cluster_labels(ag["missing_jaccard"], ids)
    vsize = pd.Series(vlab).map(pd.Series(vlab).value_counts())
    cl = pd.DataFrame({"experiment_id": ids, "value_cluster": vlab, "value_cluster_size": vsize.to_numpy(),
                       "missing_cluster": mlab, "family": fam,
                       **{k: [keys[e][k] for e in ids] for k in ("detector_type", "window_w", "policy_id", "reset_rule")}})
    cl.to_csv(RES / "agreement_clusters.csv", index=False)
    cs = pd.concat([C.cluster_summary(vlab, rho, ids, fam, "value_spearman"),
                    C.cluster_summary(mlab, ag["missing_jaccard"], ids, fam, "missingness_jaccard")], ignore_index=True)
    cs.to_csv(RES / "agreement_cluster_summary.csv", index=False)
    t3 = time.time()

    # ---------------- 요약
    bad = oc[~oc["ofat_consistent"]]
    cal = oc[oc["changed_variable"] == "calibration"]
    vc = cs[cs["cluster_kind"] == "value_spearman"]
    print(f"[정합] 원장 유효일≠등록부 computable_days: {len(mism_comp)} {mism_comp[:5]} · 경보일≠observed_alarm_days_a05: "
          f"{len(mism_alarm)} {mism_alarm[:5]}")
    print(f"[OFAT] 비교 {len(oc)} 쌍 · 제외 {len(skipped)} {[s['child'] + ':' + s['reason'] for s in skipped]}")
    print(f"[G4 엄격] ofat_consistent=False {len(bad)} 쌍 (구조적 NA 만 추가: "
          f"{int(bad['ofat_consistent_structural'].sum())})")
    for _, b in bad.iterrows():
        print(f"   {b['parent']} -> {b['child']} [{b['changed_variable']}] expected={b['ofat_expected']} "
              f"observed={b['ofat_observed']} note={b['ofat_note']}")
    print(f"[RAW] RAW_NOT_COMPARABLE {int((~oc['raw_comparable']).sum())} 쌍 · calibration 쌍 raw_diff_max_abs "
          f"{cal['raw_diff_max_abs'].tolist()} raw_spearman {cal['raw_spearman'].tolist()}")
    print(f"[합의] {len(al)} 쌍 · spearman NaN(n_common<250 등) {int(al['spearman_raw'].isna().sum())} · "
          f"Spearman scipy 검증 20쌍 max|diff|={sp_max:.3e} · OFAT↔합의 일치 {agree_ok}")
    print(f"[군집] value: {len(vc)} 군집 · 단일 {int((vc['size'] == 1).sum())} · NaN 거리 {v_nan} → 1.0 · "
          f"missing: {int(mlab.max())} 군집 · NaN 거리 {m_nan} · 결측 0 쌍(J=1.0) {int(al['missing_both_empty'].sum())}")
    mc = cs[cs["cluster_kind"] == "missingness_jaccard"]
    for _, c in mc.head(3).iterrows():
        print(f"   M{c['cluster_id']} n={c['size']} {c['member_families'][:100]}")
    for _, c in vc.head(6).iterrows():
        print(f"   V{c['cluster_id']} n={c['size']} rep={c['representative']} within={c['mean_within_similarity']:.3f} "
              f"{c['member_families'][:120]}")
    print(f"[시간] OFAT {t1 - t0:.1f}s · 합의 {t2 - t1:.1f}s · 군집 {t3 - t2:.1f}s · 계 {t3 - t0:.1f}s")
    return 0 if sp_max < 1e-10 and agree_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

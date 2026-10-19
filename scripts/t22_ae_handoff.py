"""12B → Autoencoder 인계 피처표 — 후보마다 근거 수치를 결과표에서 모아 판정(KEEP·CONDITIONAL·MASK·DROP)과 함께 저장.

판정 규칙(사전에 적은 AUTOENCODER_FEATURE_ALIGNMENT.md 를 표로 옮긴 것, 수치는 모두 결과 파일에서 읽는다):
- KEEP: 독립 값 군집의 대표 또는 SVR 비의존 기준, 관측 시점 t 에 계산 가능
- CONDITIONAL: EXPLORATORY 통계량 (X1) — 2026 이후·다른 ETF 사전 등록 검증 뒤 사용
- MASK: 연속 신호가 아니라 공백·경계·창 잔존을 알리는 보조 열
- DROP: 대표와 같은 군집(중복)이거나 표류·귀무 부적합으로 의미가 없는 것
출력: research/k200_cusum_overlay_12b/results/ae_handoff_features.csv
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "research/k200_cusum_overlay_12b/results"
OUT = ROOT / "outputs/t22"

ROWS = [
    # (피처 이름, 실험 ID, 그룹, 시간 규모, 형태, 판정, 근거 한 줄)
    ("cusum_cos_w20", "E2_w20", "SVR 잔차 이동 CoS", "20일", "원시 T + 과거 백분위", "KEEP", "w60 과 ρ 0.07 — 짧은 기억 · 증분은 거의 0 (+0.2%, 공통일 +0.7%) · 시간 규모로 유지"),
    ("cusum_cos_w60", "B1", "SVR 잔차 이동 CoS", "60일", "원시 T + 과거 백분위", "KEEP", "117개 CoS 군집 대표 — 증분은 음수(−1.6%) · 기준 시간 규모로만 유지"),
    ("cusum_cos_w120", "E2_w120", "SVR 잔차 이동 CoS", "120일", "원시 T + 과거 백분위", "KEEP", "독립 군집 · 증분 불안정 (전체 +2.4%, 공통일 −2.9%)"),
    ("cusum_cos_w252", "E2_w252", "SVR 잔차 이동 CoS", "252일", "원시 T + 과거 백분위", "KEEP", "긴 기억(창 이월) · CoS 중 증분 최대 (+3.9%, 공통일 +5.7%)"),
    ("cusum_raw_cos_w60", "E3_raw_rolling_cos", "원수익률 이동 CoS", "60일", "원시 T", "KEEP", "SVR 비의존 기준 · 확대 반응 최대(+0.27) · 증분은 음수(−1.1%)"),
    ("cusum_page_down", "E3_page_down", "Page 하방", "누적", "자유 상태 + 과거 백분위", "KEEP", "107개 하방 군집 대표 · 증분 +3.5% (4/5년, 공통일 +2.2%)"),
    ("cusum_x1_down", "X1_page_down_sn", "X1 자기정규화 Page", "누적 · 기준 [t−252, t−61]", "방향별 상태", "CONDITIONAL", "탐색 통계량 · 증분 +3.8% (공통일 +4.5%) · 2020-09-21 전 NA"),
    ("cusum_x1_two", "X1_page_two_sn", "X1 자기정규화 Page", "누적 · 기준 [t−252, t−61]", "상·하방 상태 분리", "CONDITIONAL", "증분 +8.1% (공통일 +2.7%) · 단일 군집 · 2020-09-21 전 NA"),
    ("cusum_page_up", "E3_page_up", "Page 상방", "누적", "자유 상태", "DROP", "잔차 척도 표류 (e² > 1.386 에서 저절로 누적) · 전체 +2.0% 이나 공통일 −8.6%"),
    ("cusum_x1_up", "X1_page_up_sn", "X1 자기정규화 Page", "누적", "상태", "DROP", "증분 음수 (−1.1%) · 실데이터 2021–2025 경보 0"),
    ("cusum_cos_w60_cp_reset", "E8_reset_only", "초기화 변형", "60일", "원시 T", "DROP", "B1 과 공통일 ρ 1.00 — 결측만 추가"),
    ("cusum_cos_w60_annual_reset", "B0", "초기화 변형", "60일", "원시 T", "DROP", "B1 과 같은 값 · NA 295일 추가"),
    ("cusum_cos_w60_refit21", "E7_refit21", "SVR 재학습 변형", "60일", "원시 T", "DROP", "B1 과 ρ 0.89 · 증분 음수 (−1.7%)"),
]
MASKS = [
    ("svr_forecast_constant_flag", "SVR 예측분산 상수 고정일 (커널 소실)", "1일", "0/1", "MASK", "고정일 잔차 ≈ 원수익률 · B1 32일"),
    ("predicted_variance_B1", "SVR 정책 A 예측분산 v^", "1일", "연속", "KEEP", "CUSUM 잔차의 분모 · 기준 변동성"),
    ("days_since_reset", "초기화 후 경과일", "—", "정수", "MASK", "초기화 직후 w−1일 NA 구분"),
    ("days_since_refit", "SVR 재학습 후 경과일", "—", "정수", "MASK", "재적합 경계 척도 단절 식별"),
    ("window_exit_flag_w", "큰 충격의 창 이탈일 (d + w)", "w별", "0/1", "MASK", "단일 충격 잔존 vs 장기 고변동 구별"),
    ("feature_eligibility", "결측 사유·상태 코드", "—", "범주", "MASK", "NA 를 0 으로 채우지 않는다"),
]


def main() -> int:
    al = pd.read_parquet(OUT / "policy_market_aligned.parquet", columns=["experiment_id", "date", "cusum_raw_T"])
    fi = pd.read_csv(RES / "feature_incremental_information.csv")
    fi = fi[(fi["scale"] == "past_pct") & (~fi["exclude_2020_train"].astype(bool))].set_index("experiment_id")
    fc = pd.read_csv(RES / "feature_incremental_information_common_days.csv")
    fc = fc[~fc["exclude_2020_train"].astype(bool)].set_index("feature")
    vr = pd.read_csv(RES / "annualized_volatility_response.csv").set_index("experiment_id")
    ll = pd.read_csv(RES / "lead_lag_peak.csv").set_index("experiment_id")
    cl = pd.read_csv(RES / "agreement_clusters.csv").set_index("experiment_id")
    rows = []
    for name, eid, grp, scale, form, verdict, why in ROWS:
        g = al[al["experiment_id"] == eid].sort_values("date")
        ok = g["cusum_raw_T"].notna()
        rows.append({
            "feature": name, "experiment_id": eid, "group": grp, "time_scale": scale, "form": form, "verdict": verdict, "reason": why,
            "valid_days": int(ok.sum()), "na_days": int((~ok).sum()), "first_valid": str(g.loc[ok, "date"].min().date()),
            "value_cluster": int(cl.loc[eid, "value_cluster"]), "cluster_size": int(cl.loc[eid, "value_cluster_size"]),
            "rho_vol20_level": float(vr.loc[eid, "rho_vol20"]), "contrast_expanding": float(vr.loc[eid, "contrast_EXPANDING_minus_STABLE"]),
            "contrast_contracting": float(vr.loc[eid, "contrast_CONTRACTING_minus_STABLE"]),
            "contrast_high_persist": float(vr.loc[eid, "contrast_HIGHEXT_STABLE_minus_LOWMID_STABLE"]),
            "rho_lag0": float(ll.loc[eid, "rho_lag0"]),
            "rel_mse_gain": float(fi.loc[eid, "rel_mse_gain_pooled"]), "years_positive": int(fi.loc[eid, "years_positive"]),
            "rel_mse_gain_common846": float(fc.loc[eid, "rel_mse_gain_pooled"]) if eid in fc.index else np.nan,
            "kind": "CUSUM",
        })
    for name, desc, scale, form, verdict, why in MASKS:
        rows.append({"feature": name, "experiment_id": "", "group": desc, "time_scale": scale, "form": form, "verdict": verdict, "reason": why, "kind": "SUPPORT"})
    out = pd.DataFrame(rows)
    out["label"] = "DESCRIPTIVE — 관측 귀무 부적합, 경보·p값 미인계"
    out.to_csv(RES / "ae_handoff_features.csv", index=False)
    print(out[["feature", "verdict", "valid_days", "first_valid", "cluster_size", "rel_mse_gain", "years_positive", "rel_mse_gain_common846"]].round(3).to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""12B 상호작용 탐색 HTML (그림 A 의 Plotly 판). hongik .venv(plotly 6.8)로 동결 Parquet 만 읽는다 (D-01).

사용: /home/sieg/projects-wsl/hongik_univ_26_2/.venv/bin/python scripts/t22_interactive.py
출력: research/k200_cusum_overlay_12b/interactive/12B_시장_CUSUM_탐색기.html (plotly.js 는 CDN)
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/t22"
DST = ROOT / "research/k200_cusum_overlay_12b/interactive"

GROUPS = {
    "CoS 창 길이 (w20·30·60·120·252)": ["E2_w20", "E2_w30", "B1", "E2_w120", "E2_w252"],
    "Page · X1 자기정규화": ["E3_page_up", "E3_page_down", "X1_page_up_sn", "X1_page_down_sn", "X1_page_two_sn"],
    "SVR 학습·재학습 (w60 CoS)": ["B1", "E6_win252", "E6_win504", "E6_win756", "E7_refit63", "E7_refit21", "E10_adaptive"],
    "초기화 (w60 CoS)": ["B1", "B0", "E1_half_year", "E8_reset_only", "E5_rolling_V20_two_q0.99_g20", "E8_reset_and_refit"],
    "공식 (SVR 잔차 vs 원수익률)": ["B1", "E3_raw_rolling_cos", "E3_page_up", "E3_page_down"],
}
SCALES = {"T_past_pct": "과거 전용 백분위", "cusum_raw_T": "원시 T", "T_over_h": "T / h(α=0.05, 단측)"}
COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]


def main() -> int:
    ma = pd.read_parquet(OUT / "market_daily_master.parquet")
    al = pd.read_parquet(OUT / "policy_market_aligned.parquet", columns=["experiment_id", "date", *SCALES, "computation_status"])
    ev = pd.read_csv(ROOT / "research/k200_cusum_overlay_12b/results/events_table.csv", parse_dates=["start", "end"])
    ids = sorted({e for g in GROUPS.values() for e in g})
    missing = sorted(set(ids) - set(al["experiment_id"]))
    if missing:
        raise SystemExit(f"없는 실험: {missing}")
    d = ma["date"]
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.025, row_heights=[0.22, 0.14, 0.22, 0.42],
                        subplot_titles=("가격지수 (2019-12-30 = 100)", "일 로그수익률 (%)", "연환산 변동성 (%/년)", "CUSUM (그룹·척도 선택)"))
    fig.add_trace(go.Scatter(x=d, y=ma["indexed_close"], name="가격지수", line={"color": "#0b0b0b", "width": 1},
                             customdata=np.c_[ma["close"]], hovertemplate="%{y:.1f} (종가 %{customdata[0]:,.0f})"), 1, 1)
    fig.add_trace(go.Bar(x=d, y=ma["daily_log_return_pct"], name="수익률", marker_color=np.where(ma["daily_log_return_pct"] >= 0, "#2a78d6", "#eb6834")), 2, 1)
    for w, c in ((20, "#eb6834"), (60, "#2a78d6"), (120, "#1baf7a")):
        fig.add_trace(go.Scatter(x=d, y=ma[f"annualized_vol_{w}"], name=f"연환산 {w}일", line={"color": c, "width": 1.2}), 3, 1)
    fig.add_trace(go.Scatter(x=d, y=ma["predicted_vol_annualized_B1"], name="SVR 예측 연환산 (B1)", line={"color": "#6250d6", "width": 1, "dash": "dash"}), 3, 1)
    n_fixed = len(fig.data)
    combos = []
    for g, eids in GROUPS.items():
        for sc, scl in SCALES.items():
            idx0 = len(fig.data)
            for k, eid in enumerate(eids):
                s = al[al["experiment_id"] == eid].set_index("date").reindex(d)
                # 용량을 줄이려 float32 (표시 정밀도 3자리), NA 는 선이 끊긴다
                fig.add_trace(go.Scatter(x=d, y=s[sc].to_numpy(np.float32), name=eid, visible=False, line={"color": COLORS[k % len(COLORS)], "width": 1.1},
                                         hovertemplate=f"{eid} {scl}: %{{y:.3f}}<extra></extra>"), 4, 1)
            combos.append((f"{g} · {scl}", list(range(idx0, len(fig.data)))))
    total = len(fig.data)
    buttons = []
    for label, tr in combos:
        vis = [True] * n_fixed + [False] * (total - n_fixed)
        for i in tr:
            vis[i] = True
        buttons.append({"label": label, "method": "update", "args": [{"visible": vis}]})
    for i in combos[0][1]:
        fig.data[i].visible = True
    for _, e in ev[ev["event_set"] == "A_t20"].iterrows():
        fig.add_vrect(x0=e["start"], x1=e["end"] + pd.Timedelta(days=1), fillcolor="#e34948", opacity=0.10, line_width=0)
    fig.update_layout(height=1100, hovermode="x unified", template="plotly_white", font={"family": "Pretendard, NanumGothic, sans-serif", "size": 12},
                      title={"text": "R2H 12B — KODEX 200 시장 경로 × CUSUM 정책 탐색기 (관측 서술, N1 귀무 부적합 → 확증 아님)", "x": 0.01},
                      updatemenus=[{"buttons": buttons, "direction": "down", "x": 0.0, "xanchor": "left", "y": 1.06, "yanchor": "bottom", "showactive": True}],
                      legend={"orientation": "h", "y": -0.05}, bargap=0)
    fig.update_xaxes(rangeslider={"visible": False}, rangeselector={"buttons": [{"count": 1, "label": "1년", "step": "year", "stepmode": "backward"}, {"step": "all", "label": "전체"}]}, row=1, col=1)
    DST.mkdir(parents=True, exist_ok=True)
    path = DST / "12B_시장_CUSUM_탐색기.html"
    fig.write_html(path, include_plotlyjs="cdn", full_html=True, config={"displaylogo": False})
    meta = {"groups": GROUPS, "scales": SCALES, "traces": total, "bytes": path.stat().st_size}
    (DST / "explorer_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False)[:400])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

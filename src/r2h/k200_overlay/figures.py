# ruff: noqa: E501  — 한국어 그림 제목·각주 문자열.
"""12B 그림 — 시장 지도 · X1 실데이터 · SVR 예측 상한 · 부모–자식 중첩 · 연도별 · 국면 · 이벤트 · 선행후행 · 전체 히트맵 · 합의 · 피처.

모든 수치는 정렬 원장(policy_market_aligned)과 결과표에서 읽는다. 그림마다 그린 배열을 ``self.drawn`` 에 남겨 G6(원장 값 일치)를 검사한다.
저장: PNG 320dpi + SVG (12번과 같은 ``save``). 로그 축 눈금은 일반 숫자 (NanumGothic 에 U+2212 없음).
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

from r2h.multihorizon.figures import CAT, DIV, INK, INK2, MUTED, SEQ, footnote, save, style
from r2h.peer_shock.figures import setup_font

EV = "#e34948"
NA_SHADE = "#d9d8d2"
CEIL = "#6250d6"
NOTE = "관측 서술 — N1 귀무가 관측 잔차에 부적합(NULL_MODEL_INVALID)하므로 h·경보는 보정 참조선일 뿐 확증 결과가 아니다."

# 그림 B 대표 부모–자식 쌍 (부모, 자식, 바꾼 것)
PAIRS = [
    ("B1", "B0", "연초 초기화 없음 → 연초 초기화 (B1 → B0)"),
    ("B1", "E2_w20", "CoS 창 w60 → w20"),
    ("B1", "E2_w120", "CoS 창 w60 → w120"),
    ("B1", "E2_w252", "CoS 창 w60 → w252"),
    ("B1", "E8_reset_only", "초기화 없음 → 변화점 초기화 (V20 양방향 q0.99 gap20)"),
    ("B1", "E6_win252", "SVR 학습 확장형 → 직전 252일"),
    ("B1", "E7_refit21", "SVR 연간 재학습 → 21일 재학습"),
    ("E8_reset_only", "E8_reset_and_refit", "변화점 초기화 → 변화점 초기화 + SVR 재학습 (유도 쌍)"),
    ("E3_page_up", "X1_page_up_sn", "Page 상방 → X1 자기정규화 상방"),
    ("E3_page_down", "X1_page_down_sn", "Page 하방 → X1 자기정규화 하방"),
]
REP = ["B1", "E2_w20", "E2_w120", "E2_w252", "E3_raw_rolling_cos", "E3_page_up", "E3_page_down", "X1_page_up_sn", "X1_page_down_sn", "E7_refit21", "E6_win252", "E8_reset_only"]
REP_LABEL = {
    "B1": "CoS w60 (B1)", "E2_w20": "CoS w20", "E2_w120": "CoS w120", "E2_w252": "CoS w252", "E3_raw_rolling_cos": "원수익률 CoS w60",
    "E3_page_up": "Page 상방", "E3_page_down": "Page 하방", "X1_page_up_sn": "X1 상방", "X1_page_down_sn": "X1 하방",
    "E7_refit21": "CoS w60 · refit21", "E6_win252": "CoS w60 · win252", "E8_reset_only": "CoS w60 · 변화점 초기화", "B0": "CoS w60 · 연초 초기화",
}


def _years(ax):
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))


def _plainlog(ax):
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:g}"))
    ax.yaxis.set_minor_formatter(mticker.NullFormatter())


def _spans(ax, mask: np.ndarray, dates: pd.Series, color: str, alpha: float, label: str | None = None):
    """연속 True 구간을 음영으로."""
    m = np.r_[False, np.asarray(mask, bool), False]
    d = np.diff(m.astype(int))
    st, en = np.flatnonzero(d == 1), np.flatnonzero(d == -1) - 1
    dd = pd.to_datetime(dates).reset_index(drop=True)
    for k, (a, b) in enumerate(zip(st, en, strict=True)):
        ax.axvspan(dd[a], dd[b] + pd.Timedelta(days=1), color=color, alpha=alpha, lw=0, zorder=0, label=label if k == 0 else None)


class Figures12B:
    def __init__(self, root: Path, data: dict):
        setup_font()
        plt.rcParams["svg.hashsalt"] = "t22_k200_overlay_12b"
        self.root = root
        self.out = root / "research/k200_cusum_overlay_12b/figures"
        self.d = data
        self.ma: pd.DataFrame = data["master"]
        self.al: pd.DataFrame = data["aligned"]
        self.dates = self.ma["date"]
        self.ev: pd.DataFrame = data["events"]
        self.caps: dict[str, dict] = {}
        self.drawn: dict[str, dict[str, np.ndarray]] = {}
        self._piv: dict[str, pd.DataFrame] = {}

    # ── 공통 ──
    def piv(self, col: str) -> pd.DataFrame:
        if col not in self._piv:
            self._piv[col] = self.al.pivot(index="date", columns="experiment_id", values=col).reindex(self.dates)
        return self._piv[col]

    def series(self, eid: str, col: str) -> np.ndarray:
        return self.piv(col)[eid].to_numpy(float)

    def _events(self, ax, sets=("A_t20",), alpha=0.10):
        e = self.ev[self.ev["event_set"].isin(sets)]
        for a, b in zip(e["start"], e["end"], strict=True):
            ax.axvspan(a, b + pd.Timedelta(days=1), color=EV, alpha=alpha, lw=0, zorder=0)

    def _save(self, fig, name: str, cap: dict):
        save(fig, self.out, name)
        self.caps[name] = cap
        return cap

    # ── G01 6년 시장–CUSUM 정렬 지도 (그림 A) ──
    def g01_market_map(self):
        ma = self.ma
        d = self.dates
        fig, ax = plt.subplots(6, 1, figsize=(15, 17), sharex=True, gridspec_kw={"height_ratios": [1.1, 0.8, 1.1, 2.6, 0.9, 0.7]})
        ax[0].plot(d, ma["indexed_close"], color=INK, lw=1.0)
        ax[0].set_ylabel("가격지수\n(2019-12-30 = 100)")
        ax[0].set_title("그림 A — KODEX 200 (069500) 2020–2025 시장 경로와 CUSUM 정책 연속값 (같은 날짜축)", loc="left", fontsize=13)
        r = ma["daily_log_return_pct"].to_numpy()
        ax[1].bar(d, r, color=np.where(r >= 0, CAT[0], CAT[1]), width=1.6)
        ax[1].set_ylabel("일 로그수익률 (%)")
        for w, c in ((20, CAT[1]), (60, CAT[0]), (120, CAT[2])):
            ax[2].plot(d, ma[f"annualized_vol_{w}"], color=c, lw=1.1, label=f"연환산 관측 변동성 {w}일")
        ax[2].plot(d, ma["predicted_vol_annualized_B1"], color=CEIL, lw=0.9, ls="--", label="SVR 예측 연환산 (B1, √(252·v̂))")
        ax[2].set_ylabel("연환산 변동성 (%/년)")
        ax[2].legend(fontsize=8, ncol=4, loc="upper right", frameon=False)
        # CUSUM 연속값: 정책별 띠 (과거 전용 백분위 0–1), 결측은 회색
        reps = REP
        P = self.piv("T_past_pct")
        for k, eid in enumerate(reps):
            y = P[eid].to_numpy(float)
            base = len(reps) - 1 - k
            ax[3].fill_between(d, base, base + np.nan_to_num(y, nan=0) * 0.9, color=CAT[k % len(CAT)], alpha=0.55, lw=0, step="mid")
            _na = ~np.isfinite(y)
            ax[3].fill_between(d, base, base + 0.9, where=_na, color=NA_SHADE, alpha=0.8, lw=0, step="mid")
            ax[3].text(d.iloc[0] - pd.Timedelta(days=8), base + 0.45, REP_LABEL.get(eid, eid), ha="right", va="center", fontsize=8)
            self.drawn.setdefault("g01", {})[eid] = y
        ax[3].set_yticks([])
        ax[3].set_ylabel("CUSUM 과거 전용 백분위 (띠 높이 0–1)\n회색 = 통계량 없음 (NA)", labelpad=95)
        # 변화점·초기화·재학습·예측 상한
        tr = self.d["triggers"]
        pr = tr[(tr["rule"] == "V20_two") & (tr["q"] == 0.99) & (tr["gap"] == 20) & tr["in_eval"]]
        ax[4].vlines(pr["effect_date"], 3.1, 3.9, color=CAT[1], lw=1.2, label="변화점 트리거 효과일 (V20 양방향 q0.99 gap20)")
        rs = self.d["resets"]
        b0 = rs[rs["experiment_id"] == "B0"]["reset_applied_at"]
        ax[4].vlines(b0, 2.1, 2.9, color=CAT[2], lw=1.6, label="연초 초기화 (B0)")
        svr = self.d["svr"]
        rf = svr[(svr["policy_id"] == "E7_refit21".replace("E7_", ""))].drop_duplicates("svr_refit_at")["svr_refit_at"]
        ax[4].vlines(rf, 1.1, 1.9, color=CAT[6], lw=0.6, label="SVR 재학습 (refit21)")
        ce = self.d["ceiling"]
        cb = ce[(ce["policy_id"] == "B1") & ce["forecast_ceiling"]]["date"]
        ax[4].vlines(cb, 0.1, 0.9, color=CEIL, lw=1.0, label="SVR 예측 상한 고정일 (B1)")
        ax[4].set_yticks([0.5, 1.5, 2.5, 3.5], ["예측 상한", "재학습", "연초 초기화", "변화점"], fontsize=8)
        ax[4].legend(fontsize=7, ncol=2, loc="upper right", frameon=False)
        lv = self.d["regime"]
        lv = lv[lv["anchor_w"] == 20].set_index("date").reindex(d)
        cm = {"LOW": "#cde2fb", "MID": "#86b6ef", "HIGH": "#3987e5", "EXTREME": "#0d366b"}
        for lab, c in cm.items():
            _spans(ax[5], (lv["level_past"] == lab).to_numpy(), d, c, 1.0, label=f"수준 {lab}")
        _spans(ax[5], (lv["change_past"] == "EXPANDING").to_numpy(), d, CAT[1], 0.0)
        ex = (lv["change_past"] == "EXPANDING").to_numpy()
        ax[5].scatter(d[ex], np.full(ex.sum(), 1.15), s=3, color=CAT[1], label="변화 EXPANDING")
        cx = (lv["change_past"] == "CONTRACTING").to_numpy()
        ax[5].scatter(d[cx], np.full(cx.sum(), -0.15), s=3, color=CAT[2], label="변화 CONTRACTING")
        ax[5].set_ylim(-0.4, 1.4)
        ax[5].set_yticks([])
        ax[5].set_ylabel("연환산 20일\n과거 전용 국면")
        ax[5].legend(fontsize=7, ncol=6, loc="lower center", bbox_to_anchor=(0.5, -0.9), frameon=False)
        for a in ax[:5]:
            self._events(a)
            style(a)
        _years(ax[5])
        footnote(fig, "붉은 음영 = 11번 급변 구간 (CUSUM 과 독립 정의). " + NOTE)
        n_na = {eid: int((~np.isfinite(P[eid])).sum()) for eid in reps}
        return self._save(fig, "G01_6년_시장_CUSUM_정렬지도", {"policies": reps, "na_days": n_na, "cp_triggers_primary": int(len(pr)), "ceiling_days_B1": int(len(cb))})

    # ── G02 X1 자기정규화 Page 실데이터 ──
    def g02_x1_real(self):
        x = self.d["x1"]
        d = x["date"]
        crit = self.d["x1_crit"]
        fig, ax = plt.subplots(6, 1, figsize=(15, 18), sharex=True, gridspec_kw={"height_ratios": [0.9, 1.2, 1.0, 1.4, 1.4, 1.0]})
        r = x["daily_log_return_pct"].to_numpy()
        ax[0].bar(d, r, color=np.where(r >= 0, CAT[0], CAT[1]), width=1.6)
        ax[0].set_ylabel("일 수익률 (%)")
        ax[0].set_title("X1 자기정규화 Page — 실데이터 해부 (B1 잔차 e = r/√v̂ 를 과거 [t−252, t−61] 평균 e² 로 다시 나눈다)", loc="left", fontsize=13)
        ax[1].plot(d, x["e2_B1"], color=MUTED, lw=0.5, label="e² (B1 잔차)")
        ax[1].plot(d, x["m_hat_X1"], color=CAT[0], lw=1.8, label="m̂ X1 (평가 구간 잔차만, 유효 120일 필요)")
        ax[1].plot(d, x["m_hat_X1w"], color=CAT[1], lw=1.2, ls="--", label="m̂ X1w (2019 표본내 잔차로 시작)")
        ax[1].axhline(1, color=INK2, lw=0.7, ls=":")
        ax[1].set_yscale("log")
        _plainlog(ax[1])
        ax[1].set_ylabel("e² · 분모 m̂ (로그)")
        ax[1].legend(fontsize=8, loc="upper right", frameon=False)
        ax[2].plot(d, x["annualized_vol_20"], color=CAT[1], lw=1, label="연환산 관측 20일")
        ax[2].plot(d, np.sqrt(252 * x["predicted_variance_B1"]), color=CEIL, lw=1, ls="--", label="SVR 예측 연환산 (B1)")
        ax[2].set_ylabel("연환산 (%/년)")
        ax[2].legend(fontsize=8, frameon=False)
        hu, hd = crit["page_up"]["0.05"], crit["page_down"]["0.05"]
        su, sd = crit["page_up_sn"]["0.05"], crit["page_down_sn"]["0.05"]
        ax[3].plot(d, x["E3_up_path_a05"] / hu, color=MUTED, lw=1, label=f"원래 Page 상방 경보 경로 / h ({hu:.1f})")
        ax[3].plot(d, x["X1_up_path_a05"] / su, color=CAT[0], lw=1.4, label=f"X1 상방 / h ({su:.1f})")
        ax[3].plot(d, x["X1w_up_path_a05_REFERENCE"] / su, color=CAT[1], lw=1, ls="--", label="X1w 상방 / X1 h (참조)")
        ax[3].axhline(1, color=EV, lw=0.8)
        ax[3].set_ylabel("상방 상태 / h(α=0.05)")
        ax[3].legend(fontsize=8, frameon=False, loc="upper right")
        ax[4].plot(d, x["E3_down_path_a05"] / hd, color=MUTED, lw=1, label=f"원래 Page 하방 / h ({hd:.2f})")
        ax[4].plot(d, x["X1_down_path_a05"] / sd, color=CAT[0], lw=1.4, label=f"X1 하방 / h ({sd:.2f})")
        ax[4].plot(d, x["X1w_down_path_a05_REFERENCE"] / sd, color=CAT[1], lw=1, ls="--", label="X1w 하방 / X1 h (참조)")
        ax[4].axhline(1, color=EV, lw=0.8)
        ax[4].set_ylabel("하방 상태 / h(α=0.05)")
        ax[4].legend(fontsize=8, frameon=False, loc="upper right")
        rows = [("E3_up_alarm_a05", "Page 상방"), ("X1_up_alarm_a05", "X1 상방"), ("X1w_up_alarm_a05_REFERENCE", "X1w 상방(참조)"),
                ("E3_down_alarm_a05", "Page 하방"), ("X1_down_alarm_a05", "X1 하방"), ("X1w_down_alarm_a05_REFERENCE", "X1w 하방(참조)")]
        for k, (c, lab) in enumerate(rows):
            dd = d[x[c].to_numpy(bool)]
            ax[5].scatter(dd, np.full(len(dd), len(rows) - k), marker="|", s=160, color=CAT[k % 3] if k < 3 else CAT[2 + k % 3])
            ax[5].text(d.iloc[0] - pd.Timedelta(days=8), len(rows) - k, f"{lab} {len(dd)}", ha="right", va="center", fontsize=8)
        _spans(ax[5], ~np.isfinite(x["m_hat_X1"].to_numpy()), d, NA_SHADE, 0.7, label="X1 값 없음 (INSUFFICIENT_HISTORY 180일)")
        ax[5].set_yticks([])
        ax[5].set_ylim(0.3, len(rows) + 0.7)
        ax[5].set_ylabel("α=0.05 경보일", labelpad=80)
        ax[5].legend(fontsize=8, frameon=False, loc="lower right")
        for a in ax:
            self._events(a)
            style(a)
        _years(ax[5])
        footnote(fig, "X1w 는 12B 탐색 확장(EXPLORATORY_EXTENSION): 2020 기준창에 fit 0 의 2019 표본내 잔차를 허용, h 는 X1 보정값을 참조로만 사용. " + NOTE)
        self.drawn["g02"] = {"X1_up": x["X1_up_path_a05"].to_numpy(), "X1_down": x["X1_down_path_a05"].to_numpy()}
        cap = {c: int(x[c].sum()) for c, _ in rows}
        cap.update({"h_up": hu, "h_down": hd, "h_up_sn": su, "h_down_sn": sd})
        return self._save(fig, "G02_X1_자기정규화Page_실데이터", cap)

    # ── G03 X1 사건 확대 (COVID · 2024-08 · 2025-04) ──
    def g03_x1_zoom(self):
        x = self.d["x1"].set_index("date")
        crit = self.d["x1_crit"]
        wins = [("2020-02-01", "2020-07-31", "2020 COVID"), ("2024-07-15", "2024-10-15", "2024-08 하루 −9.63%"), ("2025-03-15", "2025-06-15", "2025-04 관세 충격")]
        fig, ax = plt.subplots(4, 3, figsize=(16, 12), sharex="col")
        for j, (a, b, lab) in enumerate(wins):
            w = x.loc[a:b]
            ax[0, j].bar(w.index, w["daily_log_return_pct"], color=np.where(w["daily_log_return_pct"] >= 0, CAT[0], CAT[1]), width=0.8)
            ax[0, j].set_title(lab, loc="left", fontsize=11)
            ax[1, j].plot(w.index, w["e2_B1"], color=MUTED, lw=0.8, marker=".", ms=3, label="e²")
            ax[1, j].plot(w.index, w["e_sn_X1w"] ** 2, color=CAT[1], lw=0.8, label="ẽ² (X1w)")
            ax[1, j].plot(w.index, w["e_sn_X1"] ** 2, color=CAT[0], lw=1.0, label="ẽ² (X1)")
            ax[1, j].set_yscale("symlog", linthresh=1)
            ax[1, j].yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:g}"))
            ax[2, j].plot(w.index, w["predicted_variance_B1"], color=CEIL, lw=1.2, label="v̂ (B1)")
            ax[2, j].plot(w.index, (w["annualized_vol_20"] / np.sqrt(252)) ** 2, color=CAT[1], lw=1, label="관측 rv20²")
            ax[3, j].plot(w.index, w["E3_up_path_a05"] / crit["page_up"]["0.05"], color=MUTED, lw=1, label="Page 상방/h")
            ax[3, j].plot(w.index, w["X1_up_path_a05"] / crit["page_up_sn"]["0.05"], color=CAT[0], lw=1.4, label="X1 상방/h")
            ax[3, j].plot(w.index, w["X1w_up_path_a05_REFERENCE"] / crit["page_up_sn"]["0.05"], color=CAT[1], lw=1, ls="--", label="X1w 상방/h (참조)")
            ax[3, j].axhline(1, color=EV, lw=0.8)
            ax[3, j].xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
            for i in range(4):
                style(ax[i, j])
        ax[0, 0].set_ylabel("수익률 (%)")
        ax[1, 0].set_ylabel("잔차² (symlog)")
        ax[2, 0].set_ylabel("일 분산 (%²)")
        ax[3, 0].set_ylabel("상방 상태 / h")
        for i in (1, 2, 3):
            ax[i, 0].legend(fontsize=7, frameon=False)
        fig.suptitle("X1 사건 확대 — 같은 충격이라도 SVR 예측분산 v̂ 가 이미 커져 있으면 e² 가 작아 Page 가 쌓이지 않는다", x=0.01, ha="left", fontsize=13)
        footnote(fig, "2020-02-25~ B1 v̂ 는 1.127 에 고정(예측 상한)되어 잔차가 사실상 원수익률 / 1.06 이 된다. " + NOTE)
        v = x.loc["2024-08-05"]
        return self._save(fig, "G03_X1_사건확대", {"2024-08-05": {"r": float(v["daily_log_return_pct"]), "v_hat": float(v["predicted_variance_B1"]), "e": float(v["e_B1"]), "e_sn": float(v["e_sn_X1"]), "X1_up_over_h": float(v["X1_up_path_a05"] / crit["page_up_sn"]["0.05"])}})

    # ── G04 SVR 예측 상한 고정 ──
    def g04_forecast_ceiling(self):
        ce = self.d["ceiling"]
        pols = ["B1", "refit63", "refit21", "refitV20_g0", "win252", "adaptiveV20"]
        wins = [("2020-02-01", "2020-09-30", "2020 COVID"), ("2024-07-20", "2024-09-10", "2024-08")]
        fig, ax = plt.subplots(len(pols), 2, figsize=(15, 2.1 * len(pols) + 1), sharex="col")
        for i, p in enumerate(pols):
            g = ce[ce["policy_id"] == p].set_index("date")
            for j, (a, b, lab) in enumerate(wins):
                w = g.loc[a:b]
                ax[i, j].plot(w.index, w["rolling_vol_20"] ** 2, color=CAT[1], lw=1, label="관측 rv20² (%²)")
                ax[i, j].plot(w.index, w["predicted_variance"], color=INK, lw=1.1, label="SVR v̂")
                c = w["forecast_ceiling"].to_numpy(bool)
                ax[i, j].scatter(w.index[c], w["predicted_variance"][c], color=CEIL, s=14, zorder=3, label="상한 고정일")
                ax[i, j].set_yscale("log")
                _plainlog(ax[i, j])
                ax[i, j].xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
                style(ax[i, j])
                if i == 0:
                    ax[i, j].set_title(lab, loc="left", fontsize=11)
            ax[i, 0].set_ylabel(p, fontsize=9)
        ax[0, 0].legend(fontsize=7, frameon=False, ncol=3)
        fig.suptitle("SVR 예측 상한 고정 — 같은 예측분산이 소수점 9자리까지 5일 이상 반복 (입력이 학습 범위를 벗어난 날)", x=0.01, ha="left", fontsize=13)
        footnote(fig, "해석 가설: 지연 r²·대용치 입력이 학습 범위를 벗어나면 RBF 커널 기여가 0 에 가까워져 예측이 한 값으로 고정된다. 이 기간의 CUSUM 잔차는 원수익률을 상수로 나눈 값에 가깝다.")
        days = ce.groupby("policy_id")["forecast_ceiling"].sum().astype(int).to_dict()
        return self._save(fig, "G04_SVR_예측상한고정", {"ceiling_days": days})

    # ── G05 부모–자식 중첩 (그림 B) ──
    def g05_pair(self, parent: str, child: str, label: str, idx: int, scale: str = "auto"):
        ma = self.ma
        d = self.dates
        det_p = self.al.loc[self.al["experiment_id"] == parent, "detector_type"].iloc[0]
        det_c = self.al.loc[self.al["experiment_id"] == child, "detector_type"].iloc[0]
        comparable = det_p == det_c
        col = "cusum_raw_T" if (scale == "raw" or (scale == "auto" and comparable)) else "T_past_pct"
        tp, tc = self.series(parent, col), self.series(child, col)
        pp, pc = self.series(parent, "T_past_pct"), self.series(child, "T_past_pct")
        fig, ax = plt.subplots(6, 1, figsize=(15, 15), sharex=True, gridspec_kw={"height_ratios": [0.9, 0.7, 0.9, 1.5, 1.0, 0.8]})
        ax[0].plot(d, ma["indexed_close"], color=INK, lw=1)
        ax[0].set_ylabel("가격지수")
        ax[0].set_title(f"그림 B{idx:02d} — {label}\n부모 {parent} vs 자식 {child} · 척도 {'원시 T' if col == 'cusum_raw_T' else '과거 전용 백분위 (공식이 달라 원시 비교 불가)'}", loc="left", fontsize=12)
        r = ma["daily_log_return_pct"].to_numpy()
        ax[1].bar(d, r, color=np.where(r >= 0, CAT[0], CAT[1]), width=1.6)
        ax[1].set_ylabel("수익률 (%)")
        ax[2].plot(d, ma["annualized_vol_20"], color=CAT[1], lw=1, label="연환산 20일")
        ax[2].plot(d, ma["annualized_vol_60"], color=CAT[0], lw=1, label="연환산 60일")
        ax[2].set_ylabel("연환산 (%/년)")
        ax[2].legend(fontsize=8, frameon=False)
        ax[3].plot(d, tp, color=INK2, lw=1.1, label=f"부모 {parent}")
        ax[3].plot(d, tc, color=CAT[1], lw=1.1, alpha=0.85, label=f"자식 {child}")
        if col == "cusum_raw_T":
            for eid, c in ((parent, INK2), (child, CAT[1])):
                h = self.series(eid, "h_a05")
                if np.isfinite(h).any():
                    ax[3].axhline(np.nanmax(h), color=c, lw=0.8, ls=":")
        ax[3].set_ylabel("CUSUM " + ("원시 T" if col == "cusum_raw_T" else "과거 백분위"))
        ax[3].legend(fontsize=8, frameon=False, loc="upper right")
        both = np.isfinite(tp) & np.isfinite(tc)
        diff = np.where(both, tc - tp, np.nan)
        dpct = np.where(np.isfinite(pp) & np.isfinite(pc), pc - pp, np.nan)
        ax[4].plot(d, diff, color=CAT[6], lw=0.9, label="자식 − 부모 (" + ("원시" if col == "cusum_raw_T" else "백분위") + ")")
        if col == "cusum_raw_T":
            ax4b = ax[4].twinx()
            ax4b.plot(d, dpct, color=CAT[2], lw=0.6, alpha=0.7, label="자식 − 부모 (과거 백분위, 오른쪽 축)")
            ax4b.set_ylim(-1.05, 1.05)
            ax4b.legend(fontsize=7, frameon=False, loc="lower right")
        ax[4].axhline(0, color=INK2, lw=0.6)
        ax[4].set_ylabel("차이")
        ax[4].legend(fontsize=8, frameon=False, loc="upper left")
        vp, vc = np.isfinite(tp), np.isfinite(tc)
        _spans(ax[5], vp & ~vc, d, CAT[1], 0.5, label="부모만 유효")
        _spans(ax[5], ~vp & vc, d, CAT[0], 0.5, label="자식만 유효")
        _spans(ax[5], ~vp & ~vc, d, NA_SHADE, 0.9, label="둘 다 NA")
        rs = self.d["resets"]
        for k, (eid, c) in enumerate(((parent, INK2), (child, CAT[1]))):
            rr = rs[rs["experiment_id"] == eid]["reset_applied_at"]
            ax[5].vlines(rr, 0.55 + 0.2 * k, 0.7 + 0.2 * k, color=c, lw=1.2)
            pol = self.al.loc[self.al["experiment_id"] == eid, "policy_id"].iloc[0]
            rf = self.d["svr"][self.d["svr"]["policy_id"] == pol].drop_duplicates("svr_refit_at")["svr_refit_at"]
            ax[5].vlines(rf, 0.05 + 0.2 * k, 0.2 + 0.2 * k, color=c, lw=0.7)
        ax[5].set_yticks([0.2, 0.7], ["SVR 재학습 (아래 부모·위 자식)", "CUSUM 초기화"], fontsize=8)
        ax[5].set_ylim(0, 1)
        ax[5].legend(fontsize=7, ncol=3, frameon=False, loc="upper right")
        for a in ax:
            self._events(a)
            style(a)
        _years(ax[5])
        footnote(fig, NOTE)
        name = f"G05_{idx:02d}_부모자식_{parent}_vs_{child}"
        self.drawn[name] = {"parent": tp, "child": tc, "col": np.array([col])}
        cap = {"parent": parent, "child": child, "scale": col, "common_valid": int(both.sum()), "parent_only": int((vp & ~vc).sum()),
               "child_only": int((~vp & vc).sum()), "both_na": int((~vp & ~vc).sum()),
               "median_diff": float(np.nanmedian(diff)) if both.any() else None, "median_pct_diff": float(np.nanmedian(dpct)) if np.isfinite(dpct).any() else None}
        return self._save(fig, name, cap)

    # ── G06 연도별 뷰 ──
    def g06_yearly(self):
        ma = self.ma.set_index("date")
        P = self.piv("T_past_pct")
        reps = ["B1", "E2_w20", "E2_w252", "E3_page_down", "X1_page_up_sn", "X1_page_down_sn"]
        fig, ax = plt.subplots(6, 2, figsize=(16, 17), gridspec_kw={"width_ratios": [1, 1]})
        for i, y in enumerate(range(2020, 2026)):
            a = ax[i, 0]
            m = ma.loc[str(y)]
            a.plot(m.index, m["annualized_vol_20"], color=CAT[1], lw=1, label="연환산 20일")
            a.plot(m.index, m["annualized_vol_120"], color=CAT[2], lw=1, label="연환산 120일")
            a2 = a.twinx()
            a2.plot(m.index, m["indexed_close"], color=INK, lw=0.7, alpha=0.5)
            a2.set_ylabel("가격지수", fontsize=7)
            a.set_ylabel(f"{y}\n연환산 (%/년)")
            b = ax[i, 1]
            pp = P.loc[str(y)]
            for k, eid in enumerate(reps):
                b.plot(pp.index, pp[eid], lw=0.9, color=CAT[k], label=REP_LABEL.get(eid, eid))
            b.set_ylim(-0.02, 1.02)
            b.set_ylabel("과거 백분위")
            for z in (a, b):
                z.xaxis.set_major_formatter(mdates.DateFormatter("%m"))
                style(z)
                e = self.ev[self.ev["event_set"] == "A_t20"]
                for s, t in zip(e["start"], e["end"], strict=True):
                    if s.year == y or t.year == y:
                        z.axvspan(s, t + pd.Timedelta(days=1), color=EV, alpha=0.12, lw=0)
        ax[0, 0].legend(fontsize=8, frameon=False)
        ax[0, 1].legend(fontsize=7, frameon=False, ncol=3)
        fig.suptitle("연도별 뷰 — 왼쪽 시장(연환산 20·120일, 가격지수), 오른쪽 대표 CUSUM 과거 전용 백분위", x=0.01, ha="left", fontsize=13)
        footnote(fig, NOTE)
        return self._save(fig, "G06_연도별_시장_CUSUM", {"policies": reps})

    # ── G07 창 이탈 효과 ──
    def g07_window_exit(self):
        d = self.dates
        ma = self.ma
        wx = self.d["window_exits"]
        fig, ax = plt.subplots(3, 1, figsize=(15, 10), sharex=True, gridspec_kw={"height_ratios": [1, 1.6, 0.8]})
        for w, c in ((20, CAT[1]), (60, CAT[0]), (120, CAT[2]), (252, CAT[6])):
            ax[0].plot(d, ma[f"annualized_vol_{w}"], color=c, lw=1, label=f"연환산 {w}일")
        ax[0].set_ylabel("연환산 (%/년)")
        ax[0].legend(fontsize=8, frameon=False, ncol=4)
        ax[0].set_title("창 이탈 — 큰 하루 충격이 이동창에서 빠지는 날(d + w)에 창 통계량이 계단식으로 떨어진다", loc="left", fontsize=12)
        for eid, c in (("E2_w20", CAT[1]), ("B1", CAT[0]), ("E2_w120", CAT[2]), ("E2_w252", CAT[6])):
            ax[1].plot(d, self.series(eid, "T_over_h"), color=c, lw=0.9, label=f"{REP_LABEL[eid]} T/h")
        ax[1].axhline(1, color=EV, lw=0.8)
        ax[1].set_yscale("log")
        _plainlog(ax[1])
        ax[1].set_ylabel("CoS T / h(α=0.05) (로그)")
        ax[1].legend(fontsize=8, frameon=False, ncol=4)
        for w, c in ((20, CAT[1]), (60, CAT[0]), (120, CAT[2]), (252, CAT[6])):
            e = wx[wx["w"] == w]
            ax[2].vlines(e["exit_date"].dropna(), {20: 3, 60: 2, 120: 1, 252: 0}[w], {20: 3.8, 60: 2.8, 120: 1.8, 252: 0.8}[w], color=c, lw=1)
        ax[2].vlines(wx["shock_date"].unique(), -0.2, 4, color=EV, lw=0.6, alpha=0.6)
        ax[2].set_yticks([0.4, 1.4, 2.4, 3.4], ["w252 이탈", "w120 이탈", "w60 이탈", "w20 이탈"], fontsize=8)
        for a in ax:
            style(a)
        _years(ax[2])
        footnote(fig, "|r| 상위 10일(붉은 선)과 각 창 길이의 이탈일. " + NOTE)
        return self._save(fig, "G07_창이탈_효과", {"shock_days": [str(x.date()) for x in wx["shock_date"].unique()]})

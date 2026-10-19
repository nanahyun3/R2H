# ruff: noqa: E501  — 한국어 그림 제목·각주 문자열.
"""12B 그림 — 시장 지도 · X1 실데이터 · SVR 예측 상수 고정 · 부모–자식 중첩 · 연도별 · 국면 · 이벤트 · 선행후행 · 전체 히트맵 · 합의 · 피처.

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
    ("B1", "E3_raw_rolling_cos", "SVR 잔차 CoS → 원수익률 CoS (공식·입력 변경)"),
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
        ax[2].plot(d, ma["predicted_vol_annualized_B1"], color=CEIL, lw=0.9, ls="--", label="SVR 예측 연환산 (B1, √(252·v^))")
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
        # 변화점·초기화·재학습·예측 상수 고정
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
        ax[4].vlines(cb, 0.1, 0.9, color=CEIL, lw=1.0, label="SVR 예측 상수 고정일 (B1)")
        ax[4].set_yticks([0.5, 1.5, 2.5, 3.5], ["예측 상수 고정", "재학습", "연초 초기화", "변화점"], fontsize=8)
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
        ax[0].set_title("X1 자기정규화 Page — 실데이터 해부 (B1 잔차 e = r/√v^ 를 과거 [t-252, t-61] 평균 e^2 로 다시 나눈다)", loc="left", fontsize=13)
        ax[1].plot(d, x["e2_B1"], color=MUTED, lw=0.5, label="e^2 (B1 잔차)")
        ax[1].plot(d, x["m_hat_X1"], color=CAT[0], lw=1.8, label="m^ X1 (평가 구간 잔차만, 유효 120일 필요)")
        ax[1].plot(d, x["m_hat_X1w"], color=CAT[1], lw=1.2, ls="--", label="m^ X1w (2019 표본내 잔차로 시작)")
        ax[1].axhline(1, color=INK2, lw=0.7, ls=":")
        ax[1].set_yscale("log")
        _plainlog(ax[1])
        ax[1].set_ylabel("e^2 · 분모 m^ (로그)")
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
        wins = [("2020-02-01", "2020-07-31", "2020 COVID"), ("2024-07-15", "2024-10-15", "2024-08 하루 -9.63%"), ("2025-03-15", "2025-06-15", "2025-04 관세 충격")]
        fig, ax = plt.subplots(4, 3, figsize=(16, 12), sharex="col")
        for j, (a, b, lab) in enumerate(wins):
            w = x.loc[a:b]
            ax[0, j].bar(w.index, w["daily_log_return_pct"], color=np.where(w["daily_log_return_pct"] >= 0, CAT[0], CAT[1]), width=0.8)
            ax[0, j].set_title(lab, loc="left", fontsize=11)
            ax[1, j].plot(w.index, w["e2_B1"], color=MUTED, lw=0.8, marker=".", ms=3, label="e^2")
            ax[1, j].plot(w.index, w["e_sn_X1w"] ** 2, color=CAT[1], lw=0.8, label="e~^2 (X1w)")
            ax[1, j].plot(w.index, w["e_sn_X1"] ** 2, color=CAT[0], lw=1.0, label="e~^2 (X1)")
            ax[1, j].set_yscale("symlog", linthresh=1)
            ax[1, j].yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:g}"))
            ax[2, j].plot(w.index, w["predicted_variance_B1"], color=CEIL, lw=1.2, label="v^ (B1)")
            ax[2, j].plot(w.index, (w["annualized_vol_20"] / np.sqrt(252)) ** 2, color=CAT[1], lw=1, label="관측 rv20^2")
            ax[3, j].plot(w.index, w["E3_up_path_a05"] / crit["page_up"]["0.05"], color=MUTED, lw=1, label="Page 상방/h")
            ax[3, j].plot(w.index, w["X1_up_path_a05"] / crit["page_up_sn"]["0.05"], color=CAT[0], lw=1.4, label="X1 상방/h")
            ax[3, j].plot(w.index, w["X1w_up_path_a05_REFERENCE"] / crit["page_up_sn"]["0.05"], color=CAT[1], lw=1, ls="--", label="X1w 상방/h (참조)")
            ax[3, j].axhline(1, color=EV, lw=0.8)
            ax[3, j].xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
            for i in range(4):
                style(ax[i, j])
        ax[0, 0].set_ylabel("수익률 (%)")
        ax[1, 0].set_ylabel("잔차^2 (symlog)")
        ax[2, 0].set_ylabel("일 분산 (%^2)")
        ax[3, 0].set_ylabel("상방 상태 / h")
        for i in (1, 2, 3):
            ax[i, 0].legend(fontsize=7, frameon=False)
        fig.suptitle("X1 사건 확대 — 같은 충격이라도 SVR 예측분산 v^ 가 이미 커져 있으면 e^2 가 작아 Page 가 쌓이지 않는다", x=0.01, ha="left", fontsize=13)
        footnote(fig, "2020-02-25~ B1 v^ 는 1.127 에 고정(예측 상수 고정)되어 잔차가 사실상 원수익률 / 1.06 이 된다. " + NOTE)
        v = x.loc["2024-08-05"]
        return self._save(fig, "G03_X1_사건확대", {"2024-08-05": {"r": float(v["daily_log_return_pct"]), "v_hat": float(v["predicted_variance_B1"]), "e": float(v["e_B1"]), "e_sn": float(v["e_sn_X1"]), "X1_up_over_h": float(v["X1_up_path_a05"] / crit["page_up_sn"]["0.05"])}})

    # ── G04 SVR 예측 상수 고정 ──
    def g04_forecast_ceiling(self):
        ce = self.d["ceiling"]
        pols = ["B1", "refit63", "refit21", "refitV20_g0", "win252", "adaptiveV20"]
        wins = [("2020-02-01", "2020-09-30", "2020 COVID"), ("2024-07-20", "2024-09-10", "2024-08")]
        fig, ax = plt.subplots(len(pols), 2, figsize=(15, 2.1 * len(pols) + 1), sharex="col")
        for i, p in enumerate(pols):
            g = ce[ce["policy_id"] == p].set_index("date")
            for j, (a, b, lab) in enumerate(wins):
                w = g.loc[a:b]
                ax[i, j].plot(w.index, w["rolling_vol_20"] ** 2, color=CAT[1], lw=1, label="관측 rv20^2 (%^2)")
                ax[i, j].plot(w.index, w["predicted_variance"], color=INK, lw=1.1, label="SVR v^")
                c = w["forecast_ceiling"].to_numpy(bool)
                ax[i, j].scatter(w.index[c], w["predicted_variance"][c], color=CEIL, s=14, zorder=3, label="상수 고정일")
                ax[i, j].set_yscale("log")
                _plainlog(ax[i, j])
                ax[i, j].xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
                style(ax[i, j])
                if i == 0:
                    ax[i, j].set_title(lab, loc="left", fontsize=11)
            ax[i, 0].set_ylabel(p, fontsize=9)
        ax[0, 0].legend(fontsize=7, frameon=False, ncol=3)
        fig.suptitle("SVR 예측 상수 고정 — 같은 예측분산이 소수점 9자리까지 5일 이상 반복 (입력이 학습 범위를 벗어난 날)", x=0.01, ha="left", fontsize=13)
        footnote(fig, "해석 가설: 지연 r^2·대용치 입력이 학습 범위를 벗어나면 RBF 커널 기여가 0 에 가까워져 예측이 한 값으로 고정된다. 이 기간의 CUSUM 잔차는 원수익률을 상수로 나눈 값에 가깝다.")
        days = ce.groupby("policy_id")["forecast_ceiling"].sum().astype(int).to_dict()
        return self._save(fig, "G04_SVR_예측상수고정", {"ceiling_days": days})

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
        ax[4].plot(d, diff, color=CAT[6], lw=0.9, label="자식 - 부모 (" + ("원시" if col == "cusum_raw_T" else "백분위") + ")")
        if col == "cusum_raw_T":
            ax4b = ax[4].twinx()
            ax4b.plot(d, dpct, color=CAT[2], lw=0.6, alpha=0.7, label="자식 - 부모 (과거 백분위, 오른쪽 축)")
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


    # ── G08 국면별 반응 히트맵 ──
    def g08_regime_heatmap(self):
        m = self.d["regime_matrix"]
        m = m[(m["anchor_w"] == 20) & (m["regime_variant"] == "PAST") & (m["cell_type"] == "level|change")]
        cells = [f"{lv}|{ch}" for lv in ("LOW", "MID", "HIGH", "EXTREME") for ch in ("CONTRACTING", "STABLE", "EXPANDING")]
        reps = REP + ["B0", "E6_win252_page_two", "X1_page_two_sn", "E3_page_two"]
        M = m.pivot(index="experiment_id", columns="cell", values="mean_T_past_pct").reindex(index=reps, columns=cells)
        N = m.pivot(index="experiment_id", columns="cell", values="n_valid").reindex(index=reps, columns=cells)
        fig, ax = plt.subplots(1, 2, figsize=(17, 8.5), gridspec_kw={"width_ratios": [2.4, 1]})
        im = ax[0].imshow(M.to_numpy(float), cmap=DIV, vmin=0, vmax=1, aspect="auto")
        for i in range(M.shape[0]):
            for j in range(M.shape[1]):
                v, n = M.iat[i, j], N.iat[i, j]
                small = not np.isfinite(n) or n < 20
                if small:  # 유효일 20 미만 칸은 흐리게 (해석 제외)
                    ax[0].add_patch(plt.Rectangle((j - 0.5, i - 0.5), 1, 1, color="white", alpha=0.65, lw=0))
                ax[0].text(j, i, "NA" if not np.isfinite(v) else f"{v:.2f}\n{int(n)}", ha="center", va="center", fontsize=6.5, color=MUTED if small else INK)
        ax[0].set_xticks(range(len(cells)), [c.replace("|", "\n") for c in cells], fontsize=7)
        ax[0].set_yticks(range(len(reps)), [REP_LABEL.get(r, r) for r in reps], fontsize=8)
        ax[0].set_title("국면(연환산 20일, 과거 전용) × 정책 — 평균 과거 백분위 (칸 아래 숫자 = 유효일)", loc="left", fontsize=11)
        fig.colorbar(im, ax=ax[0], fraction=0.025)
        r = self.d["vol_response"]
        g = r.groupby("detector_type")[["contrast_EXPANDING_minus_STABLE", "contrast_CONTRACTING_minus_STABLE", "contrast_HIGHEXT_STABLE_minus_LOWMID_STABLE"]].median()
        y = np.arange(len(g))
        for k, (c, lab) in enumerate((("contrast_EXPANDING_minus_STABLE", "확대 - 안정"), ("contrast_CONTRACTING_minus_STABLE", "감소 - 안정"), ("contrast_HIGHEXT_STABLE_minus_LOWMID_STABLE", "높은 수준 유지 - 낮은 수준"))):
            ax[1].barh(y + (k - 1) * 0.27, g[c], height=0.26, color=CAT[k], label=lab)
        ax[1].axvline(0, color=INK2, lw=0.7)
        ax[1].set_yticks(y, g.index, fontsize=8)
        ax[1].set_title("탐지기 종류별 반응 대비 (중앙값, 과거 백분위 차)", loc="left", fontsize=11)
        ax[1].legend(fontsize=8, frameon=False)
        style(ax[1])
        footnote(fig, "흐린 칸 = 유효일 20 미만 (해석 제외). " + NOTE)
        return self._save(fig, "G08_국면별_정책반응", {"detector_medians": g.round(3).to_dict()})

    # ── G09 이벤트 정렬 ──
    def g09_event_aligned(self):
        e = self.d["event_aligned"]
        e = e[(e["event_set"] == "A_t20") & (e["period"] == "PRIMARY")]
        reps = ["B1", "E2_w20", "E2_w252", "E3_raw_rolling_cos", "E3_page_up", "E3_page_down", "X1_page_up_sn", "X1_page_down_sn"]
        types = ["누적형", "단일 충격형"]
        fig, ax = plt.subplots(2, 2, figsize=(16, 10), sharex=True, gridspec_kw={"height_ratios": [0.8, 2]})
        cap = {}
        for j, st in enumerate(types):
            g = e[e["shock_type"] == st]
            v = g[g["experiment_id"] == "B1"].groupby("rel")["annualized_vol_20"].mean()
            ax[0, j].plot(v.index, v.values, color=CAT[1], lw=1.4)
            ax[0, j].set_title(f"{st} (2021–2025, {g['event_id'].nunique()}개 사건) — 시작일 기준 정렬", loc="left", fontsize=11)
            ax[0, j].set_ylabel("평균 연환산 20일 (%/년)")
            for k, eid in enumerate(reps):
                m = g[g["experiment_id"] == eid].groupby("rel")["T_past_pct"].mean()
                ax[1, j].plot(m.index, m.values, color=CAT[k], lw=1.2, label=REP_LABEL.get(eid, eid))
                cap[f"{st}|{eid}|rel0_10"] = float(m.loc[0:10].mean()) if len(m) else None
            for a in (ax[0, j], ax[1, j]):
                a.axvline(0, color=EV, lw=0.8)
                style(a)
            ax[1, j].set_ylim(0, 1)
            ax[1, j].set_ylabel("평균 과거 백분위")
            ax[1, j].set_xlabel("사건 시작일 기준 거래일")
        ax[1, 0].legend(fontsize=8, frameon=False, ncol=2)
        fig.suptitle("사건 정렬 반응 — 11번 급변 구간(CUSUM 과 독립 정의) 시작일 전후 -60 ~ +120일", x=0.01, ha="left", fontsize=13)
        footnote(fig, "사건 수가 적어(누적형 4 · 단일 충격형 3) 평균 곡선은 사건 하나에 크게 좌우된다. " + NOTE)
        return self._save(fig, "G09_사건정렬_반응", cap)

    # ── G10 선행·후행 ──
    def g10_lead_lag(self):
        ll = self.d["lead_lag"]
        reps = ["E2_w20", "B1", "E2_w120", "E2_w252", "E3_raw_rolling_cos", "E3_page_up", "E3_page_down", "X1_page_up_sn", "X1_page_down_sn"]
        fig, ax = plt.subplots(1, 2, figsize=(16, 6.5), gridspec_kw={"width_ratios": [1.6, 1]})
        for k, eid in enumerate(reps):
            g = ll[ll["experiment_id"] == eid].sort_values("lag_k")
            ax[0].plot(g["lag_k"], g["rho"], color=CAT[k % len(CAT)], lw=1.3, label=REP_LABEL.get(eid, eid), ls="-" if k < 8 else "--")
        ax[0].axhline(0, color=INK2, lw=0.6)
        ax[0].axvline(0, color=EV, lw=0.6)
        ax[0].set_xlabel("시차 k (양수 = 정책이 시장보다 늦게 반응)")
        ax[0].set_ylabel("Spearman ρ (Δ 과거 백분위_{t+k}, Δ ln 연환산20_t)")
        ax[0].set_title("선행·후행 — 일 변화끼리의 시차 상관", loc="left", fontsize=11)
        ax[0].legend(fontsize=8, frameon=False, ncol=2)
        style(ax[0])
        pk = self.d["lead_peak"]
        h = pk.groupby("detector_type")["peak_lag"].describe()[["50%", "25%", "75%", "count"]]
        y = np.arange(len(h))
        ax[1].barh(y, h["50%"], color=CAT[0], height=0.5)
        ax[1].errorbar(h["50%"], y, xerr=[h["50%"] - h["25%"], h["75%"] - h["50%"]], fmt="none", color=INK2, lw=0.8)
        ax[1].set_yticks(y, [f"{i} ({int(c)})" for i, c in zip(h.index, h["count"], strict=True)], fontsize=8)
        ax[1].set_title("|ρ| 최대 시차 — 탐지기별 중앙값 (사분위)", loc="left", fontsize=11)
        ax[1].axvline(0, color=EV, lw=0.6)
        style(ax[1])
        footnote(fig, "k = -20 근처의 음(-)/양(+) 메아리는 연환산 20일 앵커에서 20일 전 충격이 빠지는 날의 효과다 (D-10). 서술용 — 계열 상관이 있어 추론하지 않는다.")
        return self._save(fig, "G10_선행후행", {"peak_lag_median": h["50%"].to_dict()})

    # ── G11 전체 정책 히트맵 ──
    def g11_all_policy_heatmap(self):
        cl = self.d["clusters"].sort_values(["value_cluster", "family", "experiment_id"])
        order = cl["experiment_id"].tolist()
        P = self.piv("T_past_pct")[order].to_numpy(float).T
        fig, ax = plt.subplots(2, 1, figsize=(16, 14), sharex=True, gridspec_kw={"height_ratios": [0.6, 5]})
        d = self.dates
        ax[0].plot(d, self.ma["annualized_vol_20"], color=CAT[1], lw=1)
        ax[0].set_ylabel("연환산 20일")
        ax[0].set_title(f"전체 {len(order)}개 일별 정책 × 1,473 거래일 — 과거 전용 백분위 (값 군집 순 정렬, 회색 = NA)", loc="left", fontsize=12)
        style(ax[0])
        cmap = SEQ.copy()
        cmap.set_bad(NA_SHADE)
        x0, x1 = mdates.date2num(d.iloc[0]), mdates.date2num(d.iloc[-1])
        ax[1].imshow(np.ma.masked_invalid(P), aspect="auto", cmap=cmap, vmin=0, vmax=1, interpolation="nearest", extent=[x0, x1, len(order), 0])
        bounds = np.flatnonzero(np.diff(cl["value_cluster"].astype(str).map({c: i for i, c in enumerate(dict.fromkeys(cl["value_cluster"].astype(str)))}).to_numpy())) + 1
        for b in bounds:
            ax[1].axhline(b, color="white", lw=0.4)
        big = cl.groupby("value_cluster").agg(n=("experiment_id", "size"), det=("detector_type", lambda x: x.value_counts().index[0])).sort_values("n", ascending=False).head(6)
        pos = {c: np.mean(np.flatnonzero(cl["value_cluster"].to_numpy() == c)) for c in big.index}
        for c, yy in pos.items():
            ax[1].text(x1 + 8, yy, f"{c}: {big.loc[c, 'n']}개 · {big.loc[c, 'det']}", fontsize=8, va="center")
        ax[1].set_ylabel("정책 (군집 순)")
        _years(ax[1])
        ax[1].xaxis_date()
        footnote(fig, "군집 = 공통 유효일 원시 T 의 Spearman ρ ≥ 0.9 (평균 연결). " + NOTE)
        self.drawn["g11"] = {"matrix": P}
        return self._save(fig, "G11_전체정책_히트맵", {"n_policies": len(order), "n_value_clusters": int(cl["value_cluster"].nunique()), "na_share": float(np.mean(~np.isfinite(P)))})

    # ── G12 정책 간 합의·중복성 ──
    def g12_agreement(self):
        ag = self.d["agreement"]
        cl = self.d["clusters"].sort_values(["value_cluster", "family", "experiment_id"])
        order = cl["experiment_id"].tolist()
        ix = {e: i for i, e in enumerate(order)}
        n = len(order)
        R = np.full((n, n), np.nan)
        J = np.full((n, n), np.nan)
        a, b = ag["exp_a"].map(ix).to_numpy(), ag["exp_b"].map(ix).to_numpy()
        R[a, b] = R[b, a] = ag["spearman_raw"].to_numpy()
        J[a, b] = J[b, a] = ag["missing_jaccard"].to_numpy()
        np.fill_diagonal(R, 1)
        np.fill_diagonal(J, 1)
        fig, ax = plt.subplots(1, 3, figsize=(19, 7), gridspec_kw={"width_ratios": [1, 1, 0.9]})
        cm = DIV.copy()
        cm.set_bad(NA_SHADE)
        im = ax[0].imshow(np.ma.masked_invalid(R), cmap=cm, vmin=-1, vmax=1, interpolation="nearest")
        ax[0].set_title("값 합의: 원시 T Spearman ρ (공통 유효일)", loc="left", fontsize=11)
        fig.colorbar(im, ax=ax[0], fraction=0.04)
        im2 = ax[1].imshow(J, cmap=SEQ, vmin=0, vmax=1, interpolation="nearest")
        ax[1].set_title("결측 패턴 Jaccard (같은 순서)", loc="left", fontsize=11)
        fig.colorbar(im2, ax=ax[1], fraction=0.04)
        for z in ax[:2]:
            z.set_xticks([])
            z.set_yticks([])
        sz = cl.groupby("value_cluster").size().sort_values(ascending=False)
        top = sz.head(12)
        comp = cl[cl["value_cluster"].isin(top.index)].groupby(["value_cluster", "detector_type"]).size().unstack(fill_value=0).reindex(top.index)
        left = np.zeros(len(comp))
        for k, c in enumerate(comp.columns):
            ax[2].barh(range(len(comp)), comp[c], left=left, color=CAT[k % len(CAT)], label=c)
            left += comp[c].to_numpy()
        ax[2].set_yticks(range(len(comp)), comp.index.astype(str), fontsize=8)
        ax[2].invert_yaxis()
        ax[2].set_title(f"상위 12개 값 군집 구성 (전체 {sz.size}개 · 단일 {int((sz == 1).sum())}개)", loc="left", fontsize=11)
        ax[2].legend(fontsize=7, frameon=False)
        style(ax[2])
        footnote(fig, "결측 패턴이 같은 정책끼리 값도 같다고 보지 않도록 두 행렬을 따로 그린다 (초기화 변형 408개는 대부분 결측 패턴만 다르다).")
        return self._save(fig, "G12_정책합의_중복성", {"n_clusters": int(sz.size), "singletons": int((sz == 1).sum()), "top_sizes": top.astype(int).to_dict()})

    # ── G13 초기화: 관측 공백 vs 정보 변화 ──
    def g13_reset_gaps(self):
        o = self.d["ofat"]
        o = o[o["changed_variable"].isin(["reset"])].copy()
        fig, ax = plt.subplots(1, 2, figsize=(16, 6.5))
        for k, det in enumerate(sorted(o["detector_type"].unique()) if "detector_type" in o else []):
            pass
        det = self.al.groupby("experiment_id")["detector_type"].first()
        o["det"] = o["child"].map(det)
        for k, (dt, g) in enumerate(o.groupby("det")):
            ax[0].scatter(g["added_na_days"], g["pct_diff_median"].abs(), s=14, color=CAT[k % len(CAT)], alpha=0.7, label=f"{dt} ({len(g)})")
        ax[0].set_xlabel("초기화로 추가된 NA 일수 (부모 유효 · 자식 NA)")
        ax[0].set_ylabel("|공통일 과거 백분위 차 중앙값|")
        ax[0].set_title("초기화 쌍 — 관측 공백 추가 vs 통계량 변화", loc="left", fontsize=11)
        ax[0].legend(fontsize=8, frameon=False)
        style(ax[0])
        o["fam"] = np.where(o["family"].str.startswith("E5"), "E5 변화점 초기화", np.where(o["family"].str.startswith("E1") | (o["child"] == "B0"), "E1 달력 초기화", o["family"]))
        g = o.groupby(["fam", "det"]).agg(added=("added_na_days", "median"), common=("common_valid_days", "median"), rho=("raw_spearman", "median")).reset_index()
        lab = g["fam"] + " · " + g["det"]
        y = np.arange(len(g))
        ax[1].barh(y, g["common"], color=CAT[0], label="공통 유효일 (중앙값)")
        ax[1].barh(y, g["added"], left=g["common"], color=CAT[1], label="추가 NA 일 (중앙값)")
        for i, rr in enumerate(g["rho"]):
            ax[1].text(g["common"].iat[i] + g["added"].iat[i] + 10, i, f"ρ {rr:.2f}", va="center", fontsize=8)
        ax[1].set_yticks(y, lab, fontsize=8)
        ax[1].set_title("초기화 계열별 — 공통일 ρ 가 높으면 '정보 변화' 보다 '공백 추가'", loc="left", fontsize=11)
        ax[1].legend(fontsize=8, frameon=False, loc="lower right")
        style(ax[1])
        footnote(fig, "12번 위약 비교: 변화점 초기화가 같은 횟수 무작위 위약보다 나은 경우 102개 규칙 중 9·8개 (우연 수준). " + NOTE)
        share = float(np.mean((o["raw_spearman"] >= 0.9) & (o["added_na_days"] > 0)))
        return self._save(fig, "G13_초기화_관측공백", {"n_reset_pairs": int(len(o)), "share_rho_ge_0.9_with_added_na": share, "by_family": g.round(3).to_dict("records")})

    # ── G14 SVR 학습·재학습 정책 ──
    def g14_svr_policies(self):
        svr = self.d["svr"]
        pols = ["B1", "win252", "win504", "win756", "refit63", "refit21", "refitV20_g0", "refitV20_g20", "refitV20_g60", "adaptiveV20"]
        d = self.dates
        fig, ax = plt.subplots(3, 1, figsize=(15, 12), sharex=True, gridspec_kw={"height_ratios": [1.3, 1.3, 1]})
        ax[0].plot(d, self.ma["rolling_vol_20"] ** 2, color=CAT[1], lw=1.2, label="관측 rv20^2")
        for k, p in enumerate(pols):
            g = svr[svr["policy_id"] == p].set_index("date").reindex(d)
            ax[0].plot(d, g["predicted_variance"], lw=0.7, color=CAT[k % len(CAT)] if k < 8 else INK2, alpha=0.8, label=p)
        ax[0].set_yscale("log")
        _plainlog(ax[0])
        ax[0].set_ylabel("일 분산 (%^2, 로그)")
        ax[0].legend(fontsize=7, ncol=6, frameon=False)
        ax[0].set_title("SVR 학습·재학습 정책 10종 — 예측분산과 그 결과인 CUSUM (w60 CoS)", loc="left", fontsize=12)
        ids = {"B1": "B1", "win252": "E6_win252", "win504": "E6_win504", "win756": "E6_win756", "refit63": "E7_refit63", "refit21": "E7_refit21", "refitV20_g0": "E8_refit_only", "refitV20_g20": "E9_grace20", "refitV20_g60": "E9_grace60", "adaptiveV20": "E10_adaptive"}
        for k, (p, eid) in enumerate(ids.items()):
            ax[1].plot(d, self.series(eid, "T_over_h"), lw=0.7, color=CAT[k % len(CAT)] if k < 8 else INK2, label=eid)
        ax[1].axhline(1, color=EV, lw=0.8)
        ax[1].set_yscale("log")
        _plainlog(ax[1])
        ax[1].set_ylabel("CoS w60 T / h")
        ax[1].legend(fontsize=7, ncol=5, frameon=False)
        br = self.d["refit_breaks"]
        for k, p in enumerate(pols):
            rf = svr[svr["policy_id"] == p].drop_duplicates("svr_refit_at")["svr_refit_at"]
            ax[2].vlines(rf, k + 0.1, k + 0.9, color=CAT[k % len(CAT)] if k < 8 else INK2, lw=0.6)
            ce = self.d["ceiling"]
            cc = ce[(ce["policy_id"] == p) & ce["forecast_ceiling"]]["date"]
            ax[2].scatter(cc, np.full(len(cc), k + 0.5), s=6, color=CEIL, zorder=3)
        ax[2].set_yticks(np.arange(len(pols)) + 0.5, pols, fontsize=8)
        ax[2].set_ylabel("재학습(선) · 예측 상수 고정(점)")
        for a in ax:
            self._events(a)
            style(a)
        _years(ax[2])
        footnote(fig, "12번 X-D6: 유예 재학습(grace) 경계에서 잔차 척도가 튀어 2021 초 경보 27·26일. " + NOTE)
        return self._save(fig, "G14_SVR정책_비교", {"refit_breaks_rows": int(len(br))})

    # ── G15 단일 충격형 vs 누적형 ──
    def g15_shock_type(self):
        s = self.d["shock_type"]
        s = s[s["scope"] == s["scope"].unique()[0]] if "PRIMARY" not in set(s["scope"]) else s[s["scope"] == "PRIMARY"]
        reps = REP + ["X1_page_two_sn", "B0"]
        g = s.set_index("experiment_id").reindex(reps)
        y = np.arange(len(reps))
        fig, ax = plt.subplots(1, 2, figsize=(15, 7), gridspec_kw={"width_ratios": [1.3, 1]})
        ax[0].barh(y - 0.2, g["mean_T_past_pct_cumulative"], height=0.38, color=CAT[0], label="누적형 (onset+during)")
        ax[0].barh(y + 0.2, g["mean_T_past_pct_single"], height=0.38, color=CAT[1], label="단일 충격형")
        ax[0].set_yticks(y, [REP_LABEL.get(r, r) for r in reps], fontsize=8)
        ax[0].invert_yaxis()
        ax[0].set_xlim(0, 1)
        ax[0].set_xlabel("평균 과거 백분위")
        ax[0].set_title("사건 유형별 반응 (2021–2025 PRIMARY)", loc="left", fontsize=11)
        ax[0].legend(fontsize=8, frameon=False)
        style(ax[0])
        h = s.merge(self.al.groupby("experiment_id")["detector_type"].first().rename("det"), left_on="experiment_id", right_index=True)
        dd = [h.loc[h["det"] == k, "diff_cumulative_minus_single"].dropna().to_numpy() for k in sorted(h["det"].unique())]
        ax[1].boxplot(dd, vert=False, tick_labels=sorted(h["det"].unique()), showfliers=False)
        ax[1].axvline(0, color=EV, lw=0.7)
        ax[1].set_title("누적형 - 단일 충격형 (탐지기별 분포)", loc="left", fontsize=11)
        style(ax[1])
        footnote(fig, "사건이 누적형 4개 · 단일 충격형 3개뿐이라 일반화하지 않는다. " + NOTE)
        return self._save(fig, "G15_단일vs누적_충격", {"median_diff": float(np.nanmedian(s["diff_cumulative_minus_single"]))})

    # ── G16 AE 피처 증분 정보 ──
    def g16_feature_value(self):
        f = self.d["features"]
        f = f[(f["scale"] == "past_pct") & (f["coverage_status"] == "OK") & (f["family"] != "12B_EXTRA")]
        cv = self.d["features_common"]
        fig, ax = plt.subplots(1, 2, figsize=(16, 7), gridspec_kw={"width_ratios": [1, 1.2]})
        dets = sorted(f["detector_type"].unique())
        for k, ex in enumerate((False, True)):
            data = [f[(f["detector_type"] == dt) & (f["exclude_2020_train"] == ex)]["rel_mse_gain_pooled"].to_numpy() for dt in dets]
            bp = ax[0].boxplot(data, positions=np.arange(len(dets)) + (k - 0.5) * 0.35, widths=0.3, vert=False, showfliers=False, patch_artist=True)
            for b in bp["boxes"]:
                b.set_facecolor(CAT[k])
                b.set_alpha(0.5)
        ax[0].set_yticks(range(len(dets)), dets, fontsize=8)
        ax[0].axvline(0, color=EV, lw=0.7)
        ax[0].set_xlabel("표본외 상대 MSE 개선 (미래 20일 실현변동성, 기준 = 관측·예측 변동성)")
        ax[0].set_title("정책 전체 — 탐지기별 증분 정보 (파랑 2020 학습 포함 · 주황 제외)", loc="left", fontsize=11)
        style(ax[0])
        c = cv[~cv["exclude_2020_train"]].sort_values("rel_mse_gain_pooled")
        ax[1].barh(range(len(c)), c["rel_mse_gain_pooled"], color=[CAT[2] if v > 0 else CAT[1] for v in c["rel_mse_gain_pooled"]])
        for i, (v, yp) in enumerate(zip(c["rel_mse_gain_pooled"], c["years_positive"], strict=True)):
            ax[1].text(v + (0.002 if v >= 0 else -0.002), i, f"{int(yp)}/5년", va="center", ha="left" if v >= 0 else "right", fontsize=7)
        ax[1].set_yticks(range(len(c)), [REP_LABEL.get(x, x) for x in c["feature"]], fontsize=8)
        ax[1].axvline(0, color=INK2, lw=0.7)
        ax[1].set_title(f"대표 후보 — 공통 유효일 {int(c['n_common'].iloc[0])}일에서 같은 비교 (연도 제외 교차검증)", loc="left", fontsize=11)
        style(ax[1])
        footnote(fig, "목표 = ln SD(r_{t+1..t+20}) (미래, 겹치는 목표 → 서술용). 숫자 = 시험연도 5개 중 개선된 해 수.")
        return self._save(fig, "G16_AE피처_증분정보", {"common_days": c.set_index("feature")["rel_mse_gain_pooled"].round(4).to_dict()})

    # ── G17 연도 안정성 ──
    def g17_yearly_stability(self):
        y = self.d["yearly"]
        reps = REP + ["X1_page_two_sn", "E6_win252_page_two"]
        M = y[y["experiment_id"].isin(reps)].pivot(index="experiment_id", columns="calendar_year", values="rho_vol20_level").reindex(reps)
        fig, ax = plt.subplots(figsize=(11, 7.5))
        im = ax.imshow(M.to_numpy(float), cmap=DIV, vmin=-1, vmax=1, aspect="auto")
        for i in range(M.shape[0]):
            for j in range(M.shape[1]):
                v = M.iat[i, j]
                ax.text(j, i, "NA" if not np.isfinite(v) else f"{v:.2f}", ha="center", va="center", fontsize=8)
        ax.set_xticks(range(M.shape[1]), M.columns)
        ax.set_yticks(range(len(reps)), [REP_LABEL.get(r, r) for r in reps], fontsize=8)
        ax.set_title("연도별 안정성 — ρ(과거 백분위, 연환산 20일 수준)", loc="left", fontsize=12)
        fig.colorbar(im, ax=ax, fraction=0.03)
        footnote(fig, "2020 은 과거 유효값 120개 조건 때문에 대부분 NA. " + NOTE)
        return self._save(fig, "G17_연도별_안정성", {"rho": M.round(3).to_dict()})

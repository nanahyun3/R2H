# ruff: noqa: E501  — 한국어 그림 캡션·각주 문자열.
"""12번 그림 — 관측 타임라인 · B0/B1 · 창 · Page · 변화점 · 위약 · SVR · 합성 검출 · AE 중복성 · 사건 확대.

각 함수는 캡션 수치 dict 를 돌려준다. 저장: PNG 320dpi + SVG (W2 ``save``). 모든 수치는 결과표/원장에서 읽는다.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

from r2h.multihorizon.figures import CAT, INK, INK2, MUTED, SEQ, DIV, footnote, save, style
from r2h.peer_shock.figures import setup_font

from . import observed as O

EV_COLOR = "#e34948"
NA_SHADE = "#d9d8d2"


def _plainlog(ax):
    """로그 축 눈금을 mathtext 없이 (NanumGothic 에 U+2212 가 없어 10^-1 표기가 깨진다)."""
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:g}"))
    ax.yaxis.set_minor_formatter(mticker.NullFormatter())


def _years(ax):
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))


class Figures12:
    def __init__(self, res: dict, root: Path):
        setup_font()
        plt.rcParams["svg.hashsalt"] = "t21_k200_cusum_12"
        self.r = res
        self.ob: O.Observed = res["ob"]
        self.ed = self.ob.m.eval_dates
        self.t = res["tables"]
        self.f = res["feats"]
        self.out = root / "research/k200_cusum_controlled_12/figures"
        self.caps: dict[str, dict] = {}
        self.root = root

    def _save(self, fig, name, cap):
        save(fig, self.out, name)
        plt.close(fig)
        self.caps[name] = cap
        return cap

    def _events(self, ax, alpha=0.12):
        for a, b in zip(self.ob.events["start"], self.ob.events["end"]):
            ax.axvspan(a, b + pd.Timedelta(days=1), color=EV_COLOR, alpha=alpha, lw=0, zorder=0)

    def _crit(self, eid, alpha=0.05):
        s = self.t["experiment_summary.csv"]
        return float(s.loc[s.experiment_id == eid, "crit_a05"].iloc[0])

    # F01 관측 타임라인
    def f01_timeline(self):
        m = self.ob.m
        es = m.eval_start
        p = self.ob.paths["B1"]
        fig, ax = plt.subplots(4, 1, figsize=(13, 10), sharex=True, gridspec_kw={"height_ratios": [1.2, 1, 1, 1]})
        ax[0].plot(self.ed, m.close[es:], color=INK, lw=1)
        ax[0].set_ylabel("종가 (원)")
        ax[0].set_title("KODEX 200 (069500) 2020–2025 — 가격 · 수익률 · SVR 정책 A 예측분산 · 표준화 잔차^2", loc="left", fontsize=12)
        ax[1].bar(self.ed, m.r[es:], color=np.where(m.r[es:] >= 0, CAT[0], CAT[1]), width=1.5)
        ax[1].set_ylabel("일 수익률 (%)")
        ax[2].plot(self.ed, m.r[es:] ** 2, color=MUTED, lw=0.6, label="r^2")
        ax[2].plot(self.ed, p.vhat, color=CAT[2], lw=1.1, label="예측분산 v_hat (B1)")
        ax[2].set_yscale("log")
        _plainlog(ax[2])
        ax[2].legend(loc="upper right", fontsize=8, frameon=False)
        ax[2].set_ylabel("분산 (로그)")
        e2 = p.e**2
        ax[3].plot(self.ed, e2, color=CAT[6], lw=0.6)
        ax[3].axhline(1.0, color=INK2, lw=0.8, ls="--")
        yr = self.ed.year.to_numpy()
        means = {}
        for y in sorted(set(yr)):
            mm = float(np.nanmean(e2[yr == y]))
            means[int(y)] = mm
            seg = self.ed[yr == y]
            ax[3].plot([seg[0], seg[-1]], [mm, mm], color=EV_COLOR, lw=2)
            ax[3].text(seg[len(seg) // 2], mm * 1.5, f"{mm:.2f}", ha="center", fontsize=8, color=EV_COLOR)
        ax[3].set_yscale("log")
        _plainlog(ax[3])
        ax[3].set_ylabel("e^2 (로그) · 빨강 = 연평균")
        for a in ax:
            self._events(a)
            style(a)
        for s in p.refit_pos:
            for a in ax[2:]:
                a.axvline(self.ed[s], color=INK2, lw=0.5, ls=":")
        _years(ax[-1])
        footnote(fig, "빨간 띠 = 11번 069500 q20 급변 구간 (실현변동성 기반, 서술용). 점선 = SVR 재적합일 (연초). 표준화 잔차 e = r/sqrt v_hat 의 연평균 e^2 가 1 이 아니면 척도가 맞지 않는다는 뜻이다.")
        return self._save(fig, "F01_관측_타임라인", {"mean_e2_by_year": means, "n_events": len(self.ob.events)})

    # F02 B0 vs B1
    def f02_b0_b1(self):
        T0, T1 = self.ob.raw["B0"]["T"], self.ob.raw["B1"]["T"]
        c0, c1 = self._crit("B0"), self._crit("B1")
        fig, ax = plt.subplots(2, 1, figsize=(13, 6.5), sharex=True)
        for a, T, c, lab in ((ax[0], T0, c0, "B0 연초 초기화"), (ax[1], T1, c1, "B1 연도 관통")):
            a.plot(self.ed, T, color=CAT[0], lw=0.9)
            a.axhline(c, color=EV_COLOR, lw=1, ls="--", label=f"임계 α=0.05 ({c:.3f})")
            na = ~np.isfinite(T)
            a.fill_between(self.ed, 0, 1, where=na, transform=a.get_xaxis_transform(), color=NA_SHADE, alpha=0.6, lw=0, label="NA (창 미충족)")
            a.set_ylabel("이동 CoS T (w=60)")
            a.set_title(f"{lab} — 유효 {int(np.isfinite(T).sum())}일 · NA {int(na.sum())}일", loc="left", fontsize=11)
            self._events(a)
            style(a)
            a.legend(loc="upper right", fontsize=8, frameon=False)
        _years(ax[-1])
        both = np.isfinite(T0) & np.isfinite(T1)
        same = bool(np.array_equal(T0[both], T1[both]))
        footnote(fig, f"둘 다 유효한 {int(both.sum())}일에서 T 가 정확히 같다 ({same}) — 연초 초기화는 매년 첫 59일을 비울 뿐 통계량을 바꾸지 않는다. 임계값은 각자의 귀무 보정.")
        return self._save(fig, "F02_B0_B1_연초초기화", {"both_valid": int(both.sum()), "identical": same, "crit_B0": c0, "crit_B1": c1,
                                                    "na_B0": int((~np.isfinite(T0)).sum()), "na_B1": int((~np.isfinite(T1)).sum())})

    # F03 창 길이
    def f03_windows(self):
        ws = (20, 30, 60, 120, 252)
        fig, ax = plt.subplots(len(ws), 1, figsize=(13, 11), sharex=True)
        cap = {}
        for a, w in zip(ax, ws):
            eid = "B1" if w == 60 else f"E2_w{w}"
            T, c = self.ob.raw[eid]["T"], self._crit(eid)
            a.plot(self.ed, T / c, color=CAT[0], lw=0.8)
            a.axhline(1.0, color=EV_COLOR, lw=1, ls="--")
            al = np.nan_to_num(T, nan=-np.inf) >= c
            a.scatter(self.ed[al], (T / c)[al], s=5, color=EV_COLOR, zorder=3)
            a.set_ylabel(f"w={w}\nT/임계")
            self._events(a)
            style(a)
            cap[w] = {"alarm_days_a05": int(al.sum()), "crit": c}
        ax[0].set_title("E2 창 길이 — T / 임계(α=0.05), B1 잔차 · 같은 오경보 부담", loc="left", fontsize=12)
        _years(ax[-1])
        footnote(fig, "1 을 넘는 점 = 경보일. 짧은 창은 날카롭지만 잦은 요동, 긴 창은 한 번 넘으면 오래 머문다 (창 길이만큼 지속).")
        return self._save(fig, "F03_창길이_비교", cap)

    # F04 Page
    def f04_page(self):
        fig, ax = plt.subplots(3, 1, figsize=(13, 8.5), sharex=True)
        rows = [("E3_page_up", "Page 상방 (λ=2) 자유 상태"), ("E3_page_down", "Page 하방 (λ=0.5) 자유 상태"), ("X1_page_up_sn", "X1 자기정규화 Page 상방 (탐색)")]
        cap = {}
        for a, (eid, lab) in zip(ax, rows):
            T = self.ob.raw[eid]["T"]
            c = self._crit(eid)
            a.plot(self.ed, T, color=CAT[3] if "down" in eid else CAT[1], lw=0.9)
            a.axhline(c, color=EV_COLOR, ls="--", lw=1, label=f"h α=0.05 = {c:.2f}")
            a.set_title(lab, loc="left", fontsize=11)
            self._events(a)
            style(a)
            a.legend(loc="upper right", fontsize=8, frameon=False)
            cap[eid] = {"max": float(np.nanmax(T)), "h": c}
        _years(ax[-1])
        footnote(fig, "자유 상태 = 경보 후 재설정 없이 쌓인 Page 통계량 (피처로 보존). 경보 판정은 경보 다음날 0 으로 되돌리는 경로로 한다. 잔차 척도가 1 보다 크면 상방 상태는 계속 쌓인다.")
        return self._save(fig, "F04_Page_CUSUM", cap)

    # F05 변화점 래스터
    def f05_changepoints(self):
        cp = self.t["change_point_summary.csv"]
        sub = cp[(cp["q"] == 0.99) & (cp["gap"] == 20)].sort_values(["family", "rule"])
        fig, ax = plt.subplots(1, 2, figsize=(15, 7), gridspec_kw={"width_ratios": [3, 1]})
        for i, rule in enumerate(sub["rule"]):
            eff = self.ob.cp_effect[(rule, 0.99, 20)]
            ax[0].scatter(self.ed[eff], np.full(len(eff), i), s=10, color=CAT["PVMK".index(rule[0])], marker="|")
        ax[0].set_yticks(range(len(sub)), sub["rule"])
        self._events(ax[0])
        style(ax[0])
        _years(ax[0])
        ax[0].set_title("E4 변화점 트리거 (q=0.99, 불응기 20일) — 효과일 t+1", loc="left", fontsize=12)
        yrs = [c for c in sub.columns if c.startswith("n_20")]
        im = ax[1].imshow(sub[yrs].to_numpy(), aspect="auto", cmap=SEQ)
        ax[1].set_xticks(range(len(yrs)), [c[2:] for c in yrs], rotation=45)
        ax[1].set_yticks(range(len(sub)), sub["rule"])
        for (i, j), v in np.ndenumerate(sub[yrs].to_numpy()):
            ax[1].text(j, i, int(v), ha="center", va="center", fontsize=7, color=INK if v < sub[yrs].to_numpy().max() * 0.6 else "white")
        ax[1].set_title("연도별 트리거 수", fontsize=11)
        footnote(fig, "P=가격 기울기 · V=변동성 로그비 · M=이동평균 격차 · K=초과첨도. 모든 점수는 t 종가까지, 임계는 t 이전 자기 점수의 확장형 분위.")
        return self._save(fig, "F05_변화점_트리거", {"n_rules": len(sub), "total_triggers": int(sub["n_triggers"].sum()),
                                                  "max_year_share_median": float(sub["max_year_share"].median())})

    # F06 위약
    def f06_placebo(self):
        pl = self.t["placebo_comparison.csv"]
        sub = pl[(pl["metric"] == "event_mean_pctile") & (pl["q"] == 0.99) & (pl["gap"] == 20)]
        fig, ax = plt.subplots(1, 2, figsize=(14, 6.5), sharey=True)
        cap = {}
        for a, det in zip(ax, ("rolling_cos", "page_two")):
            d = sub[sub["detector"] == det].sort_values("rule")
            y = np.arange(len(d))
            a.hlines(y, d["random_mean"] - 0.0, d["random_q95"], color=MUTED, lw=4, alpha=0.5, label="무작위 위약 평균→95%")
            a.scatter(d["random_mean"], y, color=MUTED, s=15)
            a.scatter(d["shift_q95"], y, color=CAT[3], marker="x", s=25, label="이동 위약 95%")
            a.scatter(d["real"], y, color=EV_COLOR, s=30, zorder=3, label="실제 변화점 초기화")
            a.set_yticks(y, d["rule"])
            a.set_title(f"{'이동 CoS w60' if det == 'rolling_cos' else 'Page 양방향'} — 사건일 평균 백분위", loc="left", fontsize=11)
            style(a)
            cap[det] = {"real_gt_random_q95": int((d["real"] > d["random_q95"]).sum()), "n": len(d)}
        fig.legend(*ax[0].get_legend_handles_labels(), fontsize=8, frameon=False, loc="upper center", ncol=3, bbox_to_anchor=(0.5, 1.03))
        footnote(fig, "같은 횟수·같은 불응기의 무작위 초기화 200회와 트리거 간격을 보존한 원형 이동 200회. 빨강이 회색 막대 오른쪽 끝을 넘어야 변화점 시점 자체의 효과(RESET_TRIGGER_GAIN 후보)다. 사건 구간은 실현변동성 기반이라 서술용.")
        return self._save(fig, "F06_변화점초기화_위약", cap)

    # F07 SVR
    def f07_svr(self):
        s = self.t["svr_training_summary.csv"]
        fig, ax = plt.subplots(1, 3, figsize=(16, 5.5))
        yrs = [y for y in s["year"].unique() if y != "all"]
        piv = s[s["year"] != "all"].pivot(index="pipeline", columns="year", values="mean_e2").loc[list(self.ob.paths)]
        im = ax[0].imshow(np.log2(piv.to_numpy(float)), cmap=DIV, vmin=-1.5, vmax=1.5, aspect="auto")
        ax[0].set_xticks(range(len(yrs)), yrs, rotation=45)
        ax[0].set_yticks(range(len(piv)), piv.index)
        for (i, j), v in np.ndenumerate(piv.to_numpy(float)):
            ax[0].text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=7)
        ax[0].set_title("연도별 평균 e^2 (1 = 척도 일치)", fontsize=11)
        al = s[s["year"] == "all"].set_index("pipeline").loc[list(self.ob.paths)]
        ax[1].barh(al.index, al["qlike"], color=CAT[0])
        ax[1].set_xlim(al["qlike"].min() - 0.05, al["qlike"].max() + 0.05)
        ax[1].set_title("QLIKE (2020–2025, 낮을수록 좋음)", fontsize=11)
        ax[1].invert_yaxis()
        ax[2].barh(al.index, al["refit_jump_ratio"], color=CAT[1])
        ax[2].axvline(1, color=INK2, ls="--")
        ax[2].set_title("재적합일 |Δlog v_hat| / 평상시 (단절)", fontsize=11)
        ax[2].invert_yaxis()
        for a in ax[1:]:
            style(a)
        footnote(fig, "E6 학습창 · E7 재적합 빈도 · E8 변화점 재적합 · E9 유예 · E10 적응형. 단절비 > 1 이면 재적합 경계에서 예측분산이 평소보다 크게 뛴다.")
        return self._save(fig, "F07_SVR_정책", {"qlike": al["qlike"].round(4).to_dict(), "jump_ratio": al["refit_jump_ratio"].round(3).to_dict()})

    # F08 합성 검출
    def f08_synthetic(self):
        if "synthetic_size_power.csv" not in self.t:
            return None
        d = self.t["synthetic_size_power.csv"]
        d = d[(d["alpha"] == 0.05) & (d["reset"] == "none") & (d["calibration"] == "garch_t_N1")]
        d = d[d["svr"].isin(["B1", "NA"])]
        d["det"] = d["detector"] + np.where(d["detector"].str.contains("rolling"), "_w" + d["w"].astype(str).str.replace(".0", "", regex=False), "")
        piv = d[d["scenario"] != "S00_null"].pivot_table(index="det", columns="scenario", values="detection_rate")
        fig, ax = plt.subplots(figsize=(15, 6.5))
        im = ax.imshow(piv.to_numpy(float), cmap=SEQ, vmin=0, vmax=1, aspect="auto")
        ax.set_xticks(range(piv.shape[1]), [c.split("_", 1)[1] for c in piv.columns], rotation=40, ha="right")
        ax.set_yticks(range(piv.shape[0]), piv.index)
        for (i, j), v in np.ndenumerate(piv.to_numpy(float)):
            ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=7, color="white" if v > 0.6 else INK)
        fig.colorbar(im, ax=ax, fraction=0.02)
        ax.set_title("합성 검출률 — 변화 후 60일 안 첫 경보, 같은 오경보 부담 α=0.05 (연 블록), B1 잔차 / 원수익률", loc="left", fontsize=12)
        footnote(fig, "시나리오당 200 경로 (같은 기저 혁신 대응). 관측 자료 판정과 별개다.")
        return self._save(fig, "F08_합성_검출률", {"max_rate": float(np.nanmax(piv.to_numpy(float))), "n_cells": int(piv.size)})

    # F09 AE 중복성
    def f09_ae(self):
        red = self.t["ae_redundancy.csv"].set_index("feature")
        corr = self.t["ae_spearman.csv"].set_index("feature")
        fig, ax = plt.subplots(1, 2, figsize=(17, 8), gridspec_kw={"width_ratios": [1.3, 1]})
        im = ax[0].imshow(corr.to_numpy(float), cmap=DIV, vmin=-1, vmax=1)
        ax[0].set_xticks(range(len(corr)), corr.columns, rotation=90, fontsize=7)
        ax[0].set_yticks(range(len(corr)), corr.index, fontsize=7)
        fig.colorbar(im, ax=ax[0], fraction=0.03)
        ax[0].set_title("후보 피처 Spearman 상관", fontsize=11)
        r = red.sort_values("incremental_r2_future_rv20_over_rv20")
        ax[1].barh(r.index, r["incremental_r2_future_rv20_over_rv20"], color=CAT[2])
        ax[1].set_title("미래 RV20 증분 R^2 (현재 RV20 통제, 사후 서술)", fontsize=11)
        ax[1].tick_params(axis="y", labelsize=7)
        style(ax[1])
        footnote(fig, "증분 R^2 는 log 미래 20일 실현변동성을 log 현재 RV20 에 회귀한 뒤 피처 하나를 더했을 때의 증가분 (평가 전용, AE 입력 아님).")
        return self._save(fig, "F09_AE_피처_중복성", {"top_increment": r["incremental_r2_future_rv20_over_rv20"].tail(3).round(4).to_dict()})

    # F10 사건 확대
    def f10_events(self):
        ev = self.ob.events.sort_values("duration", ascending=False).head(3).sort_values("start")
        fig, ax = plt.subplots(3, len(ev), figsize=(16, 9), sharey="row")
        cap = {}
        m = self.ob.m
        es = m.eval_start
        for j, e in enumerate(ev.itertuples()):
            a0, a1 = max(0, int(e.i0) - 60), min(len(self.ed) - 1, int(e.i1) + 60)
            x = self.ed[a0 : a1 + 1]
            ax[0, j].plot(x, m.close[es + a0 : es + a1 + 1], color=INK)
            ax[0, j].set_title(f"{e.interval_id} {e.start.date()}~{e.end.date()} ({e.shock_type})", fontsize=9, loc="left")
            ax[1, j].plot(x, (self.ob.paths["B1"].e ** 2)[a0 : a1 + 1], color=CAT[6], lw=0.8)
            ax[1, j].set_yscale("log")
            _plainlog(ax[1, j])
            for eid, col, lab in (("E2_w20", CAT[1], "w20"), ("B1", CAT[0], "w60"), ("E3_raw_rolling_cos", CAT[2], "원수익률 w60")):
                T = self.ob.raw[eid]["T"][a0 : a1 + 1]
                ax[2, j].plot(x, T / self._crit(eid), color=col, lw=1, label=lab)
            ax[2, j].axhline(1, color=EV_COLOR, ls="--", lw=0.8)
            for i in range(3):
                ax[i, j].axvspan(e.start, e.end, color=EV_COLOR, alpha=0.12, lw=0)
                style(ax[i, j])
                ax[i, j].xaxis.set_major_formatter(mdates.DateFormatter("%y-%m"))
            cap[e.interval_id] = {"maxT_over_crit_w60": float(np.nanmax(self.ob.raw["B1"]["T"][int(e.i0) : int(e.i1) + 1] / self._crit("B1")))}
        ax[0, 0].set_ylabel("종가")
        ax[1, 0].set_ylabel("e^2 (로그)")
        ax[2, 0].set_ylabel("T / 임계")
        ax[2, 0].legend(fontsize=7, frameon=False)
        footnote(fig, "11번 069500 q20 구간 중 가장 긴 세 구간 ±60 거래일. 잔차 CoS 와 원수익률 CoS 의 반응을 같은 오경보 부담(α=0.05)에서 비교.")
        return self._save(fig, "F10_사건_확대", cap)

    # F11 재적합 경계 단절 (X-D6)
    def f11_refit_break(self, root: Path):
        br = pd.read_csv(root / "research/k200_cusum_controlled_12/results/refit_boundary_breaks.csv")
        al = pd.read_csv(root / "research/k200_cusum_controlled_12/results/refit_synced_reset_alarms.csv")
        fig = plt.figure(figsize=(16, 9))
        gs = fig.add_gridspec(2, 3, height_ratios=[1.1, 1])
        a0 = fig.add_subplot(gs[0, :])
        for pl, col in (("B1", CAT[0]), ("refitV20_g20", CAT[1]), ("refitV20_g60", CAT[3])):
            e2 = pd.Series(self.ob.paths[pl].e ** 2, index=self.ed).rolling(20, min_periods=10).mean()
            a0.plot(self.ed, e2, color=col, lw=1.1, label=f"{pl} 20일 평균 e^2")
            for s_ in self.ob.paths[pl].refit_pos[1:]:
                a0.axvline(self.ed[s_], color=col, lw=0.6, ls=":")
        a0.axhline(1, color=INK2, ls="--", lw=0.8)
        a0.set_yscale("log")
        _plainlog(a0)
        a0.set_xlim(pd.Timestamp("2020-01-01"), pd.Timestamp("2021-06-30"))
        a0.legend(fontsize=8, frameon=False, loc="upper right")
        a0.set_title("X-D6 재적합 경계 단절 — 2020 하반기 ε=1.0 적합이 분산을 과대추정 → 2021-01-04 새 적합에서 e^2 척도 점프", loc="left", fontsize=11)
        self._events(a0)
        style(a0)
        a1 = fig.add_subplot(gs[1, 0:2])
        b = br.copy()
        b["label"] = b["pipeline"] + " " + b["refit_date"]
        b = b[(b["refit_date"] < "2021-02-01") & b["pipeline"].isin(["B1", "refit63", "refitV20_g0", "refitV20_g20", "refitV20_g60", "adaptiveV20"])]
        a1.barh(b["label"], b["log2_ratio"], color=np.where(b["log2_ratio"] > 0, CAT[1], CAT[0]))
        a1.axvline(0, color=INK2)
        a1.set_xlabel("log2(재적합 후 40일 e^2 / 전 40일 e^2)")
        a1.tick_params(axis="y", labelsize=7)
        a1.invert_yaxis()
        style(a1)
        a2 = fig.add_subplot(gs[1, 2])
        sub = al[al["pipeline"].isin(["B1", "refitV20_g0", "refitV20_g20", "refitV20_g60"])]
        piv = sub.pivot(index="pipeline", columns="variant", values="alarm_days_2021_JanFeb")
        x = np.arange(len(piv))
        a2.bar(x - 0.2, piv["no_reset"], 0.4, color=CAT[1], label="초기화 없음")
        a2.bar(x + 0.2, piv["refit_synced_reset"], 0.4, color=CAT[2], label="재적합일 동기 초기화")
        a2.set_xticks(x, piv.index, rotation=20, fontsize=8)
        a2.set_title("2021-01~02 경보일 (α=0.05)", fontsize=10)
        a2.legend(fontsize=8, frameon=False)
        style(a2)
        footnote(fig, "유예(E9) 정책의 2021 초 경보는 두 모형 잔차가 한 60일 창에 섞여 생긴 구현 기원 경보다 (시장 변화 아님). 재적합일에 창을 끊으면 사라지지만 커버리지가 줄어든다.")
        g20 = br[(br.pipeline == "refitV20_g20") & (br.refit_date == "2021-01-04")].iloc[0]
        return self._save(fig, "F11_재적합경계_단절", {"g20_log2_ratio_2021": float(g20.log2_ratio),
                                                       "g20_pre_mean_e2": float(g20.pre_mean_e2),
                                                       "alarms_JanFeb": piv.to_dict()})

    # F12 긴 창 이월 (X-D7)
    def f12_carry(self):
        fig, ax = plt.subplots(2, 1, figsize=(14, 7.5), sharex=True, gridspec_kw={"height_ratios": [1, 1.3]})
        r = self.ob.m.r[self.ob.m.eval_start :]
        ax[0].bar(self.ed, r, color=np.where(r >= 0, CAT[0], CAT[1]), width=1.5)
        ax[0].set_ylabel("일 수익률 (%)")
        ax[0].set_title("X-D7 연도 관통 긴 창의 과거 충격 이월 — 2020 COVID 가 w 일 동안 창에 남는다", loc="left", fontsize=11)
        cap = {}
        for w, col in ((60, CAT[0]), (120, CAT[3]), (252, CAT[6])):
            eid = "B1" if w == 60 else f"E2_w{w}"
            T, c = self.ob.raw[eid]["T"], self._crit(eid)
            ax[1].plot(self.ed, T / c, color=col, lw=1.1, label=f"w={w}")
            al = np.nan_to_num(T, nan=-np.inf) >= c
            last = self.ed[al][-1] if al.any() else None
            cap[w] = {"last_alarm": str(last.date()) if last is not None else None, "alarm_days": int(al.sum())}
        ax[1].axhline(1, color=EV_COLOR, ls="--", lw=0.9)
        covid = (pd.Timestamp("2020-02-20"), pd.Timestamp("2020-04-10"))
        for a in ax:
            a.axvspan(*covid, color=EV_COLOR, alpha=0.15, lw=0)
            style(a)
        for w, col in ((120, CAT[3]), (252, CAT[6])):
            i = int(np.searchsorted(self.ed, covid[1]))
            if i + w < len(self.ed):
                ax[1].axvline(self.ed[i + w], color=col, ls=":", lw=1)
                ax[1].text(self.ed[i + w], ax[1].get_ylim()[1] * 0.95, f"COVID 끝+{w}일", color=col, fontsize=8, ha="center")
        ax[1].set_ylabel("T / 임계 (α=0.05)")
        ax[1].legend(fontsize=8, frameon=False)
        ax[1].set_xlim(pd.Timestamp("2020-01-01"), pd.Timestamp("2022-03-31"))
        _years(ax[1])
        footnote(fig, "점선 = 2020-04-10 (COVID 급락 구간 끝) 로부터 w 거래일 뒤. w252 의 2021-01~04 경보는 COVID 이월, 2021-06~11 경보는 2020 하반기 고잔차 → 2021 저잔차 전환(분산 감소)에 대한 반응이다. 긴 창의 경보는 '최근 w 일 안 어딘가' 의 변화를 말한다.")
        return self._save(fig, "F12_긴창_과거충격_이월", cap)

    def make_all(self) -> dict:
        for fn in (self.f01_timeline, self.f02_b0_b1, self.f03_windows, self.f04_page, self.f05_changepoints,
                   self.f06_placebo, self.f07_svr, self.f08_synthetic, self.f09_ae, self.f10_events, self.f12_carry):
            fn()
        self.f11_refit_break(self.root)
        return self.caps

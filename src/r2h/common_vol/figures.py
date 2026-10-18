# ruff: noqa: E501  — 한국어 그림 캡션·각주 문자열.
"""10번 그림 G01–G16 — pipeline.run() 결과만 그린다. 각 함수는 캡션 수치를 dict 로 돌려준다.

저장: PNG 320dpi + SVG (W2 ``save`` 재사용). '동시 참여(같은 날 N_A)' 와 '구간 중 한 번이라도 참여(ever)' 를 그림마다 구분해 표기한다.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch

from r2h.multihorizon.figures import CAT, INK, INK2, MUTED, SEQ, footnote, save, style
from r2h.peer_shock.figures import NA_COLOR, setup_font

PRIMARY = (pd.Timestamp("2021-01-04"), pd.Timestamp("2025-12-30"))
CAND_COLOR = {"C1": CAT[0], "C2": CAT[1], "C3": CAT[7], "C4": CAT[2]}
CAND_ORDER = ["C1", "C2", "C3", "C4"]
STATE = ListedColormap(["#f0efec", "#2a78d6"])


def _months(ax, fmt="%y-%m"):
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter(fmt))


def _years(ax):
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))


def _img(ax, mat, dates, labels, cmap=STATE, vmin=0, vmax=1, fs=6.5):
    """행 = 항목, 열 = 거래일. 각 열은 그 거래일부터 다음 거래일 직전까지 (선 그래프 steps-post 와 정렬). NaN = NA 회색."""
    m = np.ma.masked_invalid(np.asarray(mat, float))
    cm = cmap.copy()
    cm.set_bad(NA_COLOR)
    d = pd.DatetimeIndex(dates)
    edges = mdates.date2num(list(d) + [d[-1] + pd.Timedelta(days=1)])
    ax.pcolormesh(edges, np.arange(len(labels) + 1) - 0.5, m, cmap=cm, vmin=vmin, vmax=vmax, shading="flat", rasterized=True)
    ax.set_ylim(len(labels) - 0.5, -0.5)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=fs)
    ax.xaxis_date()
    ax.tick_params(colors=INK2, labelsize=7)


class Figures10:
    def __init__(self, res: dict, root: Path):
        setup_font()
        plt.rcParams["svg.hashsalt"] = "t19_common_vol_10"
        self.r = res
        self.cfg = res["cfg"]
        self.st = res["states"]
        self.d = res["daily"]
        self.iv = res["intervals"]
        self.sm = res["summary"].set_index("rule")
        self.out = root / "research/common_volatility_candidates_10/figures"
        self.root = root
        self.groups = self.st["groups"]
        self.lab = [self.st["label"][g] for g in self.groups]
        self.main = self.cfg["main_candidates"]
        self.caps: dict[str, dict] = {}

    def _save(self, fig, name, cap):
        save(fig, self.out, name)
        plt.close(fig)
        self.caps[name] = cap
        return cap

    def _prim(self):
        return self.d[self.d["period"] == "PRIMARY"]

    def _civ(self, c, period="PRIMARY"):
        return self.iv[(self.iv["candidate"] == c) & (self.iv["period"] == period)]

    def _rid(self, c):
        v = self.main[c]
        return f"q{v['q']}_k{v['k']}"

    def _shade(self, ax, c, period="PRIMARY", alpha=0.25, ymin=0, ymax=1):
        for _, r in self._civ(c, period).iterrows():
            ax.axvspan(pd.Timestamp(r["start"]), pd.Timestamp(r["end"]) + pd.Timedelta(days=1), ymin=ymin, ymax=ymax,
                       color=CAND_COLOR[c], alpha=alpha, lw=0)

    # G01 — 17 그룹 A 상태 지도 (q20·q60) + N_A
    def g01_state_maps(self):
        p = self._prim()
        dts = pd.DatetimeIndex(p["date"])
        fig, axes = plt.subplots(4, 1, figsize=(15, 13), gridspec_kw={"height_ratios": [3, 1.2, 3, 1.2]}, sharex=True)
        cap = {}
        for row, q in ((0, 20), (2, 60)):
            a = self.st["mats"][q]["A"][p.index]
            _img(axes[row], a.T, dts, self.lab)
            axes[row].set_title(f"q={q} 거래일 σ 의 그룹 A 상태 (파랑 = 자기 과거 90분위 이상)", loc="left", fontsize=10)
            ax = axes[row + 1]
            ax.fill_between(dts, p[f"n_A_q{q}"], step="post", color=CAT[0] if q == 20 else CAT[2], lw=0, alpha=0.85)
            for k in ((9, 10, 12) if q == 20 else (6,)):
                ax.axhline(k, color=INK, lw=0.7, ls="--")
                ax.text(dts[-1], k + 0.2, f"k={k}", fontsize=7, ha="right", color=INK2)
            ax.set_ylim(0, 17)
            ax.set_ylabel("N_A (같은 날)", fontsize=8)
            style(ax)
            cap[f"q{q}_max"] = int(p[f"n_A_q{q}"].max())
            cap[f"q{q}_mean"] = round(float(p[f"n_A_q{q}"].mean()), 3)
            cap[f"q{q}_median"] = float(p[f"n_A_q{q}"].median())
        _years(axes[-1])
        fig.suptitle(f"G01 · 17개 노출 그룹의 고변동성(A) 상태와 같은 날 참여 그룹 수 N_A — 주분석 2021–2025 (최대 q20 {cap['q20_max']} · q60 {cap['q60_max']})", fontsize=12)
        footnote(fig, "A 는 09(W4) 의 그룹 상태 그대로다 (KOSPI200 4종은 한 그룹, Core Pair 둘 다 A 일 때만 1). N_A 는 같은 날 동시에 A 인 그룹 수다. 점선은 C1–C4 임계값 k.")
        fig.tight_layout(rect=(0, 0.02, 1, 0.97))
        return self._save(fig, "G01_group_A_state_maps", cap)

    # G02 — N_A 시계열과 C1–C4 구간 음영
    def g02_count_with_intervals(self):
        p = self._prim()
        fig, axes = plt.subplots(2, 1, figsize=(15, 8), sharex=True)
        cap = {}
        for ax, q, cs in ((axes[0], 20, ("C1", "C2", "C3")), (axes[1], 60, ("C4",))):
            for c in cs:
                v = self.main[c]
                self._shade(ax, c, alpha=0.18 + 0.12 * cs.index(c))
                ax.axhline(v["k"], color=CAND_COLOR[c], lw=1, ls="--")
                ax.text(p["date"].iloc[5], v["k"] + 0.25, f"{c} k={v['k']} · {self.sm.loc[self._rid(c), 'n_intervals']}구간 {self.sm.loc[self._rid(c), 'candidate_days']}일",
                        fontsize=8, color=INK)
                cap[c] = {"n_intervals": int(self.sm.loc[self._rid(c), "n_intervals"]), "days": int(self.sm.loc[self._rid(c), "candidate_days"])}
            ax.plot(p["date"], p[f"n_A_q{q}"], color=INK2, lw=0.7, drawstyle="steps-post")
            ax.set_ylim(0, 17.5)
            ax.set_ylabel(f"q={q} N_A", fontsize=9)
            style(ax)
            ax.set_xlim(PRIMARY[0], PRIMARY[1])
        _years(axes[1])
        fig.suptitle("G02 · 같은 날 A 참여 그룹 수와 후보 구간 (C1 ⊇ C2 ⊇ C3 는 q=20, C4 는 q=60)", fontsize=12)
        footnote(fig, f"음영 = 조건 충족 연속 거래일 (갭 병합·최소 길이 없음). 짙을수록 엄격한 k. 주분석 관측 최대 N_A: q20 {int(p['n_A_q20'].max())} · q60 {int(p['n_A_q60'].max())} (17/17 미도달).")
        fig.tight_layout(rect=(0, 0.03, 1, 0.96))
        return self._save(fig, "G02_count_and_candidate_intervals", cap)

    # G03 — k 에 따른 생존곡선: 후보일 수·구간 수
    def g03_k_curve(self):
        p = self._prim()
        ks = np.arange(1, 18)
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        cap = {}
        for q, c in ((20, CAT[0]), (60, CAT[2])):
            days = [(p[f"n_A_q{q}"] >= k).sum() for k in ks]
            ints = []
            for k in ks:
                f = (p[f"n_A_q{q}"] >= k).to_numpy().astype(int)
                ints.append(int(((f[1:] == 1) & (f[:-1] == 0)).sum() + f[0]))
            axes[0].plot(ks, days, marker="o", ms=4, color=c, lw=2, label=f"q={q}")
            axes[1].plot(ks, ints, marker="o", ms=4, color=c, lw=2, label=f"q={q}")
            cap[f"q{q}_days"] = dict(zip(map(int, ks), map(int, days)))
            cap[f"q{q}_intervals"] = dict(zip(map(int, ks), ints))
        for c in CAND_ORDER:
            v = self.main[c]
            y = cap[f"q{v['q']}_days"][v["k"]]
            axes[0].annotate(c, (v["k"], y), xytext=(6, 6), textcoords="offset points", fontsize=9, color=INK)
            axes[1].annotate(c, (v["k"], cap[f"q{v['q']}_intervals"][v["k"]]), xytext=(6, 6), textcoords="offset points", fontsize=9, color=INK)
        axes[0].set_yscale("symlog", linthresh=10)
        axes[0].set_title("N_A ≥ k 인 거래일 수 (주분석 1,225일)", loc="left", fontsize=10)
        axes[1].set_title("N_A ≥ k 연속 구간 수 — 단조 감소가 아니다", loc="left", fontsize=10)
        for ax in axes:
            ax.set_xlabel("최소 동시 참여 그룹 수 k")
            ax.set_xticks(ks)
            ax.legend(fontsize=8)
            style(ax)
        fig.suptitle("G03 · 임계값 k 를 올리면 후보일은 줄지만 구간 수는 늘 수도 있다 (긴 구간이 쪼개짐)", fontsize=12)
        footnote(fig, "주 격자 밖의 k(1–17 전체)는 곡선 모양을 보이기 위한 진단이며 후보로 쓰지 않는다. 구간 수는 주분석 안 연속 블록 수(경계 검열 표기 없음, 표 summary.csv 와 격자 k 에서 일치).")
        fig.tight_layout(rect=(0, 0.04, 1, 0.94))
        return self._save(fig, "G03_k_survival_curves", cap)

    # G04 — 규칙 격자 리본 (12 규칙 × 날짜)
    def g04_rule_ribbons(self):
        p = self._prim()
        rl = self.r["rules"]
        lab = [f"{r.rule}  {r.label}" for r in rl.itertuples()]
        mat = np.vstack([p[r].to_numpy(float) for r in rl["rule"]])
        fig, ax = plt.subplots(figsize=(15, 5))
        _img(ax, mat, pd.DatetimeIndex(p["date"]), lab, fs=8)
        _years(ax)
        ax.axhline(5.5, color=INK, lw=1)
        for i, r in enumerate(rl["rule"]):
            ax.text(mdates.date2num(PRIMARY[1]) + 8, i, f"{int(self.sm.loc[r, 'candidate_days'])}일 / {int(self.sm.loc[r, 'n_intervals'])}구간", fontsize=7, va="center", color=INK2)
        fig.suptitle("G04 · 12개 규칙의 일별 후보 상태 — 같은 q 안에서 위(완화) → 아래(엄격)로 포함관계", fontsize=12)
        zero = [r for r in rl["rule"] if self.sm.loc[r, "candidate_days"] == 0]
        footnote(fig, f"파랑 = 1 (N_A ≥ k), 회색 = 0. 주분석 NA {int(p[list(rl['rule'])].isna().sum().sum())}칸. 0일 규칙: {', '.join(zero)} (관측 최대 q20 {int(p['n_A_q20'].max())} · q60 {int(p['n_A_q60'].max())}).")
        fig.tight_layout(rect=(0, 0.04, 0.93, 0.94))
        return self._save(fig, "G04_rule_ribbons", {r: int(self.sm.loc[r, "candidate_days"]) for r in rl["rule"]})

    # G05 — C1–C4 구간 간트 + 최대·평균 N_A
    def g05_gantt(self):
        rows = pd.concat([self._civ(c).assign(c=c) for c in CAND_ORDER], ignore_index=True)
        fig, ax = plt.subplots(figsize=(15, 6.5))
        y = 0
        ticks, labs = [], []
        for c in CAND_ORDER:
            x = rows[rows["c"] == c]
            for _, r in x.iterrows():
                s, e = pd.Timestamp(r["start"]), pd.Timestamp(r["end"]) + pd.Timedelta(days=1)
                ax.barh(y, (e - s).days, left=s, height=0.6, color=CAND_COLOR[c])
                ax.text(e + pd.Timedelta(days=6), y, f"{r['start']}~{r['end']} · {r['duration_trading_days']}일 · 동시 최대 {r['max_n_A']} / ever {r['n_groups_ever']} / 매일 {r['n_groups_always']}",
                        va="center", fontsize=7.5, color=INK)
                ticks.append(y)
                labs.append(f"{c} {r['interval_id'][-3:]}")
                y += 1
            y += 0.6
        ax.set_yticks(ticks)
        ax.set_yticklabels(labs, fontsize=8)
        ax.invert_yaxis()
        ax.set_xlim(PRIMARY[0], pd.Timestamp("2027-06-30"))
        _years(ax)
        style(ax)
        fig.suptitle(f"G05 · 주 후보 C1–C4 의 실제 구간 {len(rows)}개 (2021–2025)", fontsize=12)
        footnote(fig, "'동시 최대' = 어느 하루에 동시에 A 인 그룹 수의 최댓값. 'ever' = 구간 중 하루라도 A 였던 그룹 수. '매일' = 구간 모든 날 A 인 그룹 수. ever 를 동시 급변 그룹 수로 읽으면 안 된다.")
        fig.tight_layout(rect=(0, 0.04, 1, 0.95))
        return self._save(fig, "G05_candidate_gantt", {"n": len(rows)})

    # G06 — k 효과 / q 효과 비교 막대
    def g06_effects(self):
        s = self.r["summary"]
        fig, axes = plt.subplots(2, 3, figsize=(15, 8))
        metrics = (("n_intervals", "구간 수"), ("candidate_days", "후보일 수"), ("duration_max", "최장 구간 (거래일)"))
        ks = self.cfg["k_grid"]
        for j, (m, t) in enumerate(metrics):
            ax = axes[0, j]
            for qi, (q, c) in enumerate(((20, CAT[0]), (60, CAT[2]))):
                v = [int(s[(s.q == q) & (s.k == k)][m].iloc[0]) for k in ks]
                xs = np.arange(len(ks)) + (qi - 0.5) * 0.38
                ax.bar(xs, v, width=0.36, color=c, label=f"q={q}")
                for xx, vv in zip(xs, v):
                    ax.text(xx, vv, str(vv), ha="center", va="bottom", fontsize=7, color=INK)
            ax.set_xticks(range(len(ks)))
            ax.set_xticklabels([f"k={k}" for k in ks], fontsize=8)
            ax.set_title(f"{t} — k 고정 시 q 비교", loc="left", fontsize=9.5)
            ax.legend(fontsize=7)
            style(ax)
        x = self.iv[(self.iv["period"] == "PRIMARY") & self.iv["candidate"].isin(CAND_ORDER)]
        for j, (m, t) in enumerate((("duration_trading_days", "구간 지속 (거래일)"), ("max_n_A", "구간 동시 최대 N_A"), ("n_groups_ever", "구간 ever 참여 그룹 수"))):
            ax = axes[1, j]
            for i, c in enumerate(CAND_ORDER):
                v = x[x["candidate"] == c][m].to_numpy()
                ax.scatter(np.full(v.size, i) + np.linspace(-0.12, 0.12, v.size), v, s=40, color=CAND_COLOR[c], edgecolor="white", lw=1.5, zorder=3)
                if v.size:
                    ax.hlines(np.median(v), i - 0.25, i + 0.25, color=INK, lw=1.5)
            ax.set_xticks(range(4))
            ax.set_xticklabels([f"{c}\nq{self.main[c]['q']} k{self.main[c]['k']}" for c in CAND_ORDER], fontsize=8)
            ax.set_title(f"{t} — 주 후보 (가로선 = 중앙값)", loc="left", fontsize=9.5)
            style(ax)
        fig.suptitle("G06 · 임계값 k 효과(위, 같은 q) 와 기간 q 효과(위, 같은 k) · 주 후보의 구간 특성(아래)", fontsize=12)
        q60max = int(self._prim()["n_A_q60"].max())
        footnote(fig, f"q=60 의 관측 최대 N_A 가 {q60max} 이므로 k>{q60max} 의 q60 막대는 0 이다 (0 도 유효 결과, 임계값을 바꾸지 않음). C4(k=6) 는 C1(k=9) 보다 완화된 기준이라 C1 vs C4 차이를 q 효과로만 읽지 않는다.")
        fig.tight_layout(rect=(0, 0.04, 1, 0.95))
        return self._save(fig, "G06_k_and_q_effects", {})

    # G07 — 규칙 간 날짜 Jaccard
    def g07_jaccard(self):
        j = self.r["jaccard"]
        rl = [r for r in self.r["rules"]["rule"] if self.sm.loc[r, "candidate_days"] > 0]
        m = j.pivot(index="rule_a", columns="rule_b", values="jaccard").reindex(index=rl, columns=rl)
        fig, ax = plt.subplots(figsize=(9, 7.5))
        cm = SEQ.copy()
        cm.set_bad(NA_COLOR)
        im = ax.imshow(m.to_numpy(float), cmap=cm, vmin=0, vmax=1)
        names = {r.rule: f"{r.rule} {r.label}" for r in self.r["rules"].itertuples()}
        ax.set_xticks(range(len(rl)))
        ax.set_xticklabels([names[r] for r in rl], rotation=45, ha="right", fontsize=8)
        ax.set_yticks(range(len(rl)))
        ax.set_yticklabels([names[r] for r in rl], fontsize=8)
        for a in range(len(rl)):
            for b in range(len(rl)):
                v = m.iloc[a, b]
                ax.text(b, a, f"{v:.2f}", ha="center", va="center", fontsize=7.5, color="white" if v > 0.55 else INK)
        fig.colorbar(im, ax=ax, shrink=0.8, label="날짜 Jaccard")
        fig.suptitle("G07 · 후보 규칙 간 주분석 날짜 집합 Jaccard (0일 규칙 제외)", fontsize=12)
        hz = self.r["horizon"].set_index("k")
        footnote(fig, f"k=6 에서 q20 {int(hz.loc[6, 'q20_days'])}일 · q60 {int(hz.loc[6, 'q60_days'])}일 중 공유 날짜 {int(hz.loc[6, 'both_days'])}일 (Jaccard {hz.loc[6, 'jaccard']:.2f}). 같은 q 안의 값은 포함관계 때문에 |엄격| / |완화| 와 같다.")
        fig.tight_layout(rect=(0, 0.04, 1, 0.95))
        return self._save(fig, "G07_rule_jaccard", {"C1_C2": round(float(m.loc["q20_k9", "q20_k10"]), 4), "C1_C4": round(float(m.loc["q20_k9", "q60_k6"]), 4)})

    # G08 — 분할·소멸 지도 (k 6→9→10→12, q20)
    def g08_split(self):
        p = self._prim()
        ks = [6, 9, 10, 12]
        fig, ax = plt.subplots(figsize=(15, 4.8))
        cap = {}
        for i, k in enumerate(ks):
            x = self.iv[(self.iv["rule"] == f"q20_k{k}") & (self.iv["period"] == "PRIMARY")]
            for _, r in x.iterrows():
                s, e = pd.Timestamp(r["start"]), pd.Timestamp(r["end"]) + pd.Timedelta(days=1)
                ax.barh(i, (e - s).days, left=s, height=0.55, color=[MUTED, CAND_COLOR["C1"], CAND_COLOR["C2"], CAND_COLOR["C3"]][i], edgecolor="white", lw=0.5)
            cap[k] = len(x)
            ax.text(PRIMARY[0] - pd.Timedelta(days=10), i, f"k={k}: {len(x)}구간 · {int((p[f'q20_k{k}'] == 1).sum())}일", ha="right", va="center", fontsize=8.5)
        ax.set_yticks([])
        ax.invert_yaxis()
        ax.set_xlim(PRIMARY[0] - pd.Timedelta(days=330), PRIMARY[1])
        _years(ax)
        style(ax)
        fig.suptitle("G08 · q=20 에서 k 를 올릴 때 구간이 소멸·축소·분할되는 모습 (k=6 진단 → C1 → C2 → C3)", fontsize=12)
        k = self.r["split_kids"]
        rel = k[(k.q == 20) & (k.k_loose.isin(ks))].groupby(["k_loose", "relation"]).size().to_dict()
        sp = k[(k.q == 20) & (k.k_loose == 9) & (k.n_children >= 2)]
        txt = " · ".join(f"C1 {a}~{b} ({d}일) → C2 {n}조각" for a, b, d, n in zip(sp["start"], sp["end"], sp["loose_days"], sp["n_children"]))
        footnote(fig, f"{txt}. 날짜 집합은 포함관계지만 구간 수는 C1 {cap[9]} → C2 {cap[10]}. 관계 집계: " + ", ".join(f"k{a}→ {b} {v}" for (a, b), v in rel.items()))
        fig.tight_layout(rect=(0, 0.06, 1, 0.94))
        return self._save(fig, "G08_split_and_vanish", cap)

    # G09–G11 — 사례 심층
    def g_event(self, ev: str, num: str):
        e = self.cfg["events"][ev]
        s, en = map(pd.Timestamp, e["window"])
        w = self.d[(self.d["date"] >= s) & (self.d["date"] <= en)]
        dts = pd.DatetimeIndex(w["date"])
        fig, axes = plt.subplots(5, 1, figsize=(15, 15), gridspec_kw={"height_ratios": [1.6, 3, 3, 1.4, 1.2]}, sharex=True)
        ax = axes[0]
        ws, we = map(pd.Timestamp, e["w2_ref"])
        ax.axvspan(ws, we + pd.Timedelta(days=1), color="#f2e6c9", alpha=0.6, lw=0, label="W2 참고 구간 (비교용, 경계 복사 아님)")
        for q, c in ((20, CAT[0]), (60, CAT[2])):
            ax.plot(dts, w[f"n_A_q{q}"], color=c, lw=1.6, drawstyle="steps-post", label=f"N_A q={q}")
        for k in (6, 9, 10, 12):
            ax.axhline(k, color=MUTED, lw=0.6, ls="--")
        ax.set_ylim(0, 17)
        ax.legend(fontsize=7.5, ncol=3, loc="upper left")
        ax.set_title("같은 날 A 참여 그룹 수 (점선 k = 6·9·10·12)", loc="left", fontsize=10)
        style(ax)
        for row, q in ((1, 20), (2, 60)):
            _img(axes[row], self.st["mats"][q]["A"][w.index].T, dts, self.lab)
            axes[row].set_title(f"q={q} 그룹 A 상태", loc="left", fontsize=10)
        rl = ["q20_k6", "q20_k9", "q20_k10", "q20_k12", "q60_k6"]
        nm = {"q20_k6": "q20 k6 진단", "q20_k9": "C1", "q20_k10": "C2", "q20_k12": "C3", "q60_k6": "C4"}
        _img(axes[3], np.vstack([w[r].to_numpy(float) for r in rl]), dts, [nm[r] for r in rl], fs=8)
        axes[3].set_title("후보 규칙 일별 상태", loc="left", fontsize=10)
        ax = axes[4]
        ax.plot(dts, w["n_B_q20"], color=CAT[3], lw=1.2, drawstyle="steps-post", label="N_B q20")
        ax.plot(dts, w["n_AB_q20"], color=CAT[6], lw=1.2, drawstyle="steps-post", label="N_AB q20")
        ax.set_ylim(0, 17)
        ax.legend(fontsize=7.5, ncol=2, loc="upper left")
        ax.set_title("보조: Peer 상대 괴리 B·A∩B 참여 그룹 수 (진입 조건 아님)", loc="left", fontsize=10)
        style(ax)
        span = (en - s).days
        for a in axes:
            a.set_xlim(s, en + pd.Timedelta(days=1))
            if span > 200:
                a.xaxis.set_major_locator(mdates.MonthLocator())
                a.xaxis.set_major_formatter(mdates.DateFormatter("%y-%m"))
            else:
                a.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=0, interval=2))
                a.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
        et = self.r["events"]
        et = et[et["event"] == ev].set_index("rule")
        cap = {c: {"days": int(et.loc[self._rid(c), "candidate_days"]), "intervals": et.loc[self._rid(c), "intervals"]} for c in CAND_ORDER}
        cap["max_q20"] = int(et.loc["q20_k9", "window_max_n_A"])
        cap["max_q20_date"] = et.loc["q20_k9", "window_max_first_date"]
        cap["max_q60"] = int(et.loc["q60_k6", "window_max_n_A"])
        cap["max_q60_date"] = et.loc["q60_k6", "window_max_first_date"]
        fig.suptitle(f"G{num} · {e['title']} — q20 최대 {cap['max_q20']}/17 ({cap['max_q20_date']}), q60 최대 {cap['max_q60']}/17 ({cap['max_q60_date']}) · C1 {cap['C1']['days']}일 · C2 {cap['C2']['days']}일 · C3 {cap['C3']['days']}일 · C4 {cap['C4']['days']}일", fontsize=11)
        footnote(fig, f"창 {s.date()} ~ {en.date()} (09 와 같은 사례 창). W2 참고 {ws.date()}~{we.date()} 는 W2 정의(mean(r²)·3그룹 교차)의 구간으로 비교만 한다.")
        fig.tight_layout(rect=(0, 0.02, 1, 0.97))
        return self._save(fig, f"G{num}_event_{ev}", cap)

    # G12 — 주 후보별 그룹 참여 기여
    def g12_participation(self):
        pt = self.r["participation"]
        fig, axes = plt.subplots(1, 4, figsize=(16, 7), sharey=True)
        order = list(range(len(self.groups)))
        cap = {}
        for ax, c in zip(axes, CAND_ORDER):
            x = pt[pt["candidate"] == c].set_index("group").reindex(self.groups)
            ax.barh(order, x["share_on_candidate_days"], color=CAND_COLOR[c], height=0.7, label="후보일 중 A 비율")
            ax.scatter(x["share_all_primary_days"], order, marker="|", s=80, color=INK, label="주분석 전체 A 비율", zorder=3)
            ax.set_xlim(0, 1.05)
            ax.set_title(f"{c} (q{self.main[c]['q']} k{self.main[c]['k']}, {int(x['candidate_days'].iloc[0])}일)", fontsize=10)
            style(ax)
            cap[c] = {g: round(float(v), 3) for g, v in x["share_on_candidate_days"].items()}
        axes[0].set_yticks(order)
        axes[0].set_yticklabels(self.lab, fontsize=8)
        axes[0].invert_yaxis()
        axes[0].legend(fontsize=7, loc="lower right")
        fig.suptitle("G12 · 후보일에 어떤 그룹이 고변동성이었나 — 그룹별 참여 비율 (막대) vs 평소 비율 (세로 눈금)", fontsize=12)
        footnote(fig, f"막대 1.0 = 그 후보의 모든 후보일에 A. 평소 비율은 90분위 기준이라 0.10 근처지만 확장형 기준이라 그룹마다 다르다. C1 후보일 중 국고채10년·단기채권 참여 비율 {cap['C1']['148070']:.2f}·{cap['C1']['153130']:.2f}.")
        fig.tight_layout(rect=(0, 0.04, 1, 0.95))
        return self._save(fig, "G12_group_participation", cap)

    # G13 — 구간별 동시 최대 vs ever vs 매일
    def g13_simul_vs_ever(self):
        x = pd.concat([self._civ(c) for c in CAND_ORDER], ignore_index=True)
        fig, ax = plt.subplots(figsize=(14, 5.5))
        xs = np.arange(len(x))
        ax.bar(xs - 0.27, x["n_groups_always"], width=0.27, color=CAT[6], label="매일 참여")
        ax.bar(xs, x["max_n_A"], width=0.27, color=CAT[0], label="같은 날 동시 최대 (N_A 최대)")
        ax.bar(xs + 0.27, x["n_groups_ever"], width=0.27, color=CAT[3], label="한 번이라도 참여 (ever)")
        for i, r in x.iterrows():
            ax.hlines(r["k"], i - 0.45, i + 0.45, color=INK, lw=1.2)
        ax.set_xticks(xs)
        ax.set_xticklabels([f"{r.candidate}\n{r.start}\n~{r.end}" for r in x.itertuples()], fontsize=7)
        ax.set_ylim(0, 17)
        ax.set_ylabel("그룹 수 (0–17)")
        ax.legend(fontsize=8)
        style(ax)
        fig.suptitle("G13 · 구간별 '매일 · 동시 최대 · 한 번이라도' 참여 그룹 수 (검은 선 = k)", fontsize=12)
        footnote(fig, "ever 가 동시 최대보다 크면, 그 차이만큼의 그룹은 구간 중 서로 다른 날에 번갈아 참여한 것이다. 동시 급변 그룹 수는 가운데 막대로만 말한다.")
        fig.tight_layout(rect=(0, 0.04, 1, 0.95))
        return self._save(fig, "G13_simultaneous_vs_ever", {"max_gap_ever_minus_max": int((x["n_groups_ever"] - x["max_n_A"]).max())})

    # G14 — B·AB 보조 해석
    def g14_b_ab(self):
        b = self.r["b_ab"]
        fig, axes = plt.subplots(1, 2, figsize=(13, 4.8))
        for ax, m, t in ((axes[0], "mean_n_B", "평균 N_B"), (axes[1], "mean_n_AB", "평균 N_AB")):
            for i, c in enumerate(CAND_ORDER):
                x = b[b["candidate"] == c].set_index("side")
                ax.bar(i - 0.18, x.loc["후보일", m], width=0.34, color=CAND_COLOR[c])
                ax.bar(i + 0.18, x.loc["비후보일", m], width=0.34, color="#d9d8d2")
                ax.text(i - 0.18, x.loc["후보일", m], f"{x.loc['후보일', m]:.2f}", ha="center", va="bottom", fontsize=7.5)
                ax.text(i + 0.18, x.loc["비후보일", m], f"{x.loc['비후보일', m]:.2f}", ha="center", va="bottom", fontsize=7.5)
            ax.set_xticks(range(4))
            ax.set_xticklabels(CAND_ORDER)
            ax.set_title(f"{t} — 색 = 후보일, 회색 = 비후보일", loc="left", fontsize=10)
            style(ax)
        fig.suptitle("G14 · 후보일 안팎의 Peer 상대 괴리 B 와 A∩B 참여 그룹 수 (사후 특성 기술, 진입 조건 아님)", fontsize=12)
        footnote(fig, "같은 q 의 N_B·N_AB. A 는 AB 의 필요조건이라 후보일에 N_AB 가 높아지는 것은 부분적으로 기계적이다.")
        fig.tight_layout(rect=(0, 0.05, 1, 0.93))
        return self._save(fig, "G14_B_AB_inside_outside", b.to_dict("records"))

    # G15 — 연도별 후보일
    def g15_yearly(self):
        y = self.r["yearly"]
        fig, ax = plt.subplots(figsize=(13, 4.8))
        yrs = list(range(2021, 2026))
        for i, c in enumerate(CAND_ORDER):
            v = [int(y[(y["candidate"] == c) & (y["year"] == yr)]["candidate_days"].iloc[0]) for yr in yrs]
            xs = np.arange(len(yrs)) + (i - 1.5) * 0.2
            ax.bar(xs, v, width=0.19, color=CAND_COLOR[c], label=c)
            for xx, vv in zip(xs, v):
                if vv:
                    ax.text(xx, vv, str(vv), ha="center", va="bottom", fontsize=7.5)
        ax.set_xticks(range(len(yrs)))
        ax.set_xticklabels(yrs)
        ax.set_ylabel("후보일 수")
        ax.legend(fontsize=8)
        style(ax)
        zero = [yr for yr in yrs if int(y[(y["year"] == yr) & y["candidate"].isin(CAND_ORDER)]["candidate_days"].sum()) == 0]
        fig.suptitle(f"G15 · 연도별 후보일 수 — 네 후보 모두 0일인 해: {', '.join(map(str, zero)) or '없음'}", fontsize=12)
        footnote(fig, "주분석 2021–2025 만. 2020 파일럿과 2026 부분 연도는 G16 에서 따로 본다.")
        fig.tight_layout(rect=(0, 0.04, 1, 0.94))
        return self._save(fig, "G15_yearly_candidate_days", {})

    # G16 — 2020 파일럿 · 2026 별도
    def g16_pilot_2026(self):
        fig, axes = plt.subplots(2, 1, figsize=(15, 7.5))
        cap = {}
        for ax, per, yr in ((axes[0], "PILOT", 2020), (axes[1], "PARTIAL_NON_BLIND", 2026)):
            w = self.d[self.d["period"] == per]
            for q, c in ((20, CAT[0]), (60, CAT[2])):
                ax.plot(w["date"], w[f"n_A_q{q}"].where(w[f"n_eval_A_q{q}"] == 17), color=c, lw=1.3, drawstyle="steps-post", label=f"N_A q={q} (17 그룹 평가 가능일만)")
            for c in CAND_ORDER:
                self._shade(ax, c, per, alpha=0.15)
            na = w[w["n_eval_A_q60"] < 17]
            if len(na):
                ax.axvspan(na["date"].iloc[0], na["date"].iloc[-1], color=NA_COLOR, alpha=0.35, lw=0, label="q60 NA (기준 이력 부족)")
            ax.axhline(17, color=INK, lw=0.8, ls="--")
            ax.set_ylim(0, 17.8)
            ax.legend(fontsize=7.5, ncol=3, loc="upper right")
            ax.set_title(f"{yr} — {'파일럿 (성공 근거 아님)' if yr == 2020 else '부분 연도 (주분석 제외)'}", loc="left", fontsize=10)
            _months(ax)
            style(ax)
            s = self.r["summary_pilot" if yr == 2020 else "summary_2026"].set_index("rule")
            cap[yr] = {c: int(s.loc[self._rid(c), "candidate_days"]) for c in CAND_ORDER} | {"k17_q20": int(s.loc["q20_k17", "candidate_days"])}
        handles = [Patch(color=CAND_COLOR[c], alpha=0.4, label=c) for c in CAND_ORDER]
        fig.legend(handles=handles, loc="upper center", ncol=4, fontsize=8, bbox_to_anchor=(0.5, 0.955))
        fig.suptitle(f"G16 · 2020 파일럿 (q20 17/17 {cap[2020]['k17_q20']}일) 과 2026 부분 연도 — 주분석과 섞지 않는다", fontsize=12)
        c26 = self.iv[(self.iv["period"] == "PARTIAL_NON_BLIND") & self.iv["candidate"].isin(CAND_ORDER)]
        cen = c26[(c26["left_censored"] != False) | (c26["right_censored"] != False)]["interval_id"].tolist()  # noqa: E712
        footnote(fig, f"음영 = 같은 규칙의 해당 기간 구간. 2026 은 2026-10-02 까지 관측. 2026 주 후보 구간 중 검열 구간: {', '.join(cen) if cen else '없음'}. 두 기간 모두 후보 정의의 성능 검증 근거가 아니다.")
        fig.tight_layout(rect=(0, 0.04, 1, 0.93))
        return self._save(fig, "G16_pilot2020_and_2026", cap)

    def make_all(self) -> dict:
        self.g01_state_maps()
        self.g02_count_with_intervals()
        self.g03_k_curve()
        self.g04_rule_ribbons()
        self.g05_gantt()
        self.g06_effects()
        self.g07_jaccard()
        self.g08_split()
        self.g_event("E1_2022_bond", "09")
        self.g_event("E2_2024_08", "10")
        self.g_event("E3_2025_04", "11")
        self.g12_participation()
        self.g13_simul_vs_ever()
        self.g14_b_ab()
        self.g15_yearly()
        self.g16_pilot_2026()
        return self.caps

"""보고서 자동 섹션 — ``<!-- AUTO:이름 -->`` 지시문을 결과표에서 직접 만든 Markdown 표·그림으로 펼친다.

자동 표는 결과표를 그대로 옮긴 것이므로, 표 하나마다 근거 행(표 · 필터)을 SOURCE_EVIDENCE_MATRIX 에 남긴다.
ETF 서술 문단은 ``etf_profiles.md`` 의 ``## <ticker>`` 절에서 가져온다 (사람이 ETF 별 수치를 보고 쓴 문단 + 토큰).
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

YEARS = list(range(2020, 2027))
REF = Path(__file__).resolve().parents[3] / "research/svr_garch_cusum_etf/reference_close_sha256.csv"
CAT_KO = {
    "broad_market": "시장 대표",
    "leveraged_inverse": "레버리지·인버스",
    "sector": "섹터",
    "theme": "테마",
    "strategy": "전략",
    "rates": "금리(국채)",
    "money_market": "단기채",
    "commodity": "원자재",
    "currency": "통화(달러선물)",
}
YS = {2020: "20ᴾ", 2026: "26ᴾᴺ"}


def ylab(y: int) -> str:
    return YS.get(y, str(y)[2:])


def f(v, fmt="{:.2f}"):
    if v is None or (isinstance(v, float) and not np.isfinite(v)) or (not isinstance(v, str) and pd.isna(v)):
        return "n/e"
    return fmt.format(v)


def md_table(head: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


def ref() -> pd.DataFrame:
    return pd.read_csv(REF, dtype=str)


def universe_table(R) -> str:
    v = R.t["vol"]
    r = ref()
    rows = []
    for i, row in enumerate(r.itertuples(), 1):
        b = v[v.ticker == row.ticker].rv_2019_ann_pct.iloc[0]
        rows.append([str(i), row.ticker, row.name, CAT_KO.get(row.category, row.category), f(b, "{:.1f}")])
    R.evidence.append(_ev("AUTO:universe", "annual_vol_diagnostics.csv + reference_close_sha256.csv", "rv_2019_ann_pct"))
    return md_table(["#", "ticker", "이름", "자산군", "2019 RV %"], rows)


def _ev(section: str, table: str, cols: str, keys: str = "all") -> dict:
    return {"claim_id": "AUTO", "section": section, "table": table, "keys": keys, "column": cols, "raw_value": "table", "rendered": "auto table"}


def year_table(R) -> str:
    sy = R.t["sy"]
    rows = []
    for y in YEARS:
        a = sy[(sy.year == y) & (sy.policy == "A")].iloc[0]
        b = sy[(sy.year == y) & (sy.policy == "B")].iloc[0]
        c = sy[(sy.year == y) & (sy.policy == "base")].iloc[0]
        rows.append(
            [
                ylab(y),
                f(a.median_rv, "{:.1f}"),
                f(a.n_rv_up, "{:d}"),
                f"{int(a.n_reject_asym)} / {int(a.n_reject_iid_insample)} / "
                + (f"{int(a.n_reject_iid_prequential)}" if a.n_prequential_estimable else "n/e"),
                f"{int(b.n_reject_asym)} / {int(b.n_reject_iid_insample)}",
                f"{int(c.n_reject_asym)} / {int(c.n_reject_iid_insample)}",
                f(a.median_T),
                f"{int(a.w60_pure_episodes_total)} / {a.w60_null_expected_total:.1f}",
                f"{int(c.w60_pure_episodes_total)} / {c.w60_null_expected_total:.1f}",
                f(a.median_qlike_minus_base, "{:+.3f}"),
                f(a.median_mean_e2),
                f"{int(a.n_multifactor)}/{int(a.n_descriptive)}/{int(a.n_unresolved)}/{int(a.n_no_signal)}",
            ]
        )
    R.evidence.append(_ev("AUTO:year_table", "summary_by_year_policy.csv", "all"))
    return md_table(
        [
            "연도",
            "RV 중앙값 %",
            "RV↑ ETF",
            "A 기각 점근/iid/preq",
            "B 기각 점근/iid",
            "base 기각 점근/iid",
            "A T 중앙값",
            "A w60 에피소드 관측/귀무",
            "base w60 관측/귀무",
            "QLIKE A−base 중앙값",
            "A mean e² 중앙값",
            "A 상태 MF/DE/UR/NS",
        ],
        rows,
    )


def synthetic_table(R) -> str:
    s = R.t["syn"]
    keep = [
        ("annual_posthoc", "asymptotic_1.3397", "연간 점근"),
        ("annual_posthoc", "iid_history_bootstrap", "연간 iid"),
        ("annual_posthoc", "block_history_bootstrap(L=10, different null)", "연간 block"),
        ("rolling_w60_PURE_any_episode_in_year", "iid_history_bootstrap_pointwise95", "w60 PURE ≥1"),
        ("rolling_w60_CARRY_warm_days_any_episode", "iid_history_bootstrap_pointwise95", "w60 warm ≥1"),
    ]
    rows = []
    for d in dict.fromkeys(s.dgp_name):
        x = s[s.dgp_name == d]
        r = [f"`{d}`", x.level.iloc[0], x.dgp_kind.iloc[0]]
        for tst, cal, _ in keep:
            z = x[(x.test == tst) & (x.calibration == cal)].iloc[0]
            r.append(f"{z.rate:.3f} [{z.rate_ci_low:.2f},{z.rate_ci_high:.2f}]")
        dl = x[x.test == "rolling_w60_PURE_any_episode_in_year"].delay_distribution.iloc[0]
        r.append(re.sub(r";q25=(\d+);q75=(\d+);n=\d+", r" (\1–\2)", str(dl)).replace("median=", "") if isinstance(dl, str) and dl else "—")
        r.append(str(int(x.mc_reps.iloc[0])))
        rows.append(r)
    R.evidence.append(_ev("AUTO:synthetic", "null_dgp_validation.csv", "rate,rate_ci_low,rate_ci_high,delay_distribution"))
    return md_table(["DGP", "층", "정답", *[k[2] for k in keep], "지연 중앙값 (IQR)", "반복"], rows)


def parallel_table(R) -> str:
    p = R.t.get("par")
    if p is None:
        return "`parallel_reproducibility.csv` NOT_RUN"
    rows = [
        [r.run_id, r.mode, str(r.aggregate_hash)[:16], str(r.hash_match), f"{r.numeric_max_diff:g}", f"{r.runtime_seconds:.0f}", r.status]
        for r in p.itertuples()
    ]
    R.evidence.append(_ev("AUTO:parallel", "parallel_reproducibility.csv", "all"))
    return md_table(["run", "모드", "aggregate sha256 (앞 16)", "해시 일치", "수치 최대 차이", "실행 s", "판정"], rows)


def etf_table(R, tk: str) -> str:
    v = R.t["vol"].query("ticker == @tk").set_index("year")
    fc = R.t["fc"].query("ticker == @tk")
    rd = R.t["res"].query("ticker == @tk")
    ph = R.t["ph"].query("ticker == @tk")
    cu = R.t["cu"].query("ticker == @tk")
    pr = R.t["pr"].query("ticker == @tk")
    ab = R.t["ab"].query("ticker == @tk")
    rows = []

    def g(df, y, pol, col, **kw):
        x = df[(df.year == y) & (df.policy == pol)]
        for k, val in kw.items():
            x = x[x[k] == val]
        return x[col].iloc[0] if len(x) else np.nan

    for y in YEARS:
        rej = []
        for m in ("asymptotic", "iid_insample", "iid_prequential"):
            r_ = g(ph, y, "A", "annual_reject", calibration_method=m)
            rej.append("–" if pd.isna(r_) else ("●" if str(r_) == "True" else "○"))
        e60 = g(cu, y, "A", "rolling_episodes", window=60, boundary_mode="YEAR_CONTAINED", calibration_method="iid_insample")
        n60 = g(cu, y, "A", "expected_null_episodes", window=60, boundary_mode="YEAR_CONTAINED", calibration_method="iid_insample")
        dq = []
        for s in ("trailing_2y", "frozen_2019"):
            x = ab[(ab.year == y) & (ab.policy == "A") & (ab.history_strategy == s)]
            st = x.h_status.iloc[0]
            dq.append(f(x.d_qlike_vs_expanding.iloc[0], "{:+.2f}") if st == "COMPUTED" else ("=" if st == "IDENTICAL_TO_EXPANDING" else "skip"))
        rows.append(
            [
                ylab(y),
                f(v.loc[y, "rv_ann_pct"], "{:.1f}"),
                f(v.loc[y, "rv_ratio"]),
                f(g(fc, y, "A", "oos_qlike")) + " / " + f(g(fc, y, "B", "oos_qlike")) + " / " + f(g(fc, y, "base", "oos_qlike")),
                f(g(fc, y, "A", "mean_sq_standardized_residual")),
                f(g(rd, y, "A", "excess_kurtosis"), "{:.1f}"),
                f(g(rd, y, "A", "ljungbox_e2_q"), "{:.3f}"),
                f(g(ph, y, "A", "annual_T", calibration_method="asymptotic"))
                + " / "
                + f(g(ph, y, "B", "annual_T", calibration_method="asymptotic"))
                + " / "
                + f(g(ph, y, "base", "annual_T", calibration_method="asymptotic")),
                "".join(rej),
                f"{f(e60, '{:.0f}')}/{f(n60, '{:.1f}')}",
                " ".join(dq),
                str(g(pr, y, "A", "multi_factor_status")).replace("_DESCRIPTIVE", "").replace("DESCRIPTIVE_EVIDENCE", "DESC"),
                str(g(pr, y, "A", "flagged_axes")) if pd.notna(g(pr, y, "A", "flagged_axes")) else "",
            ]
        )
    R.evidence.append(_ev(f"AUTO:etf_table:{tk}", "vol;fc;res;ph;cu;ab;pr", "see table header", f"ticker={tk}"))
    return md_table(
        ["연도", "RV%", "RV비", "QLIKE A/B/base", "A e²", "A 첨도", "A LB(e²) q", "T A/B/base", "A 기각 점/iid/pq", "A w60 관/귀", "ΔQLIKE tr/fr", "A 상태", "축"],
        rows,
    )


def profiles(R, figs: Path, prof_path: Path) -> str:
    text = prof_path.read_text(encoding="utf-8") if prof_path.exists() else ""
    parts = {m.group(1): m.group(2).strip() for m in re.finditer(r"(?ms)^## (\d{6})\s*\n(.*?)(?=^## \d{6}|\Z)", text)}
    r = ref()
    out = []
    for i, row in enumerate(r.itertuples(), 1):
        tk = row.ticker
        out.append(f"### III.{i} {tk} {row.name} — {CAT_KO.get(row.category, row.category)}")
        out.append(f"![그림 E{i} · {tk} 연간 진단 요약 — (a) 사후 RV, (b) OOS QLIKE, (c) 연간 사후 T, (d) 정책 A w60 일별 통계량](figures/ETF_{tk}.png)")
        out.append(etf_table(R, tk))
        out.append(
            "표 기호: ●=기각, ○=비기각, –=추정 불가 (점근 1.3397 / iid in-sample / prequential OOS). "
            "w60 관/귀 = PURE 창 에피소드 관측/귀무 기대. ΔQLIKE tr/fr = trailing_2y / frozen_2019 − expanding (같은 날짜; `=` 는 expanding 과 동일 모형, skip 은 이력 부족). "
            "20ᴾ = 2020 파일럿, 26ᴾᴺ = 2026 부분·비블라인드."
        )
        body = parts.get(tk)
        out.append(body if body else "**해석 문단 NOT_WRITTEN** — 이 ETF 의 서술은 아직 작성되지 않았다.")
        out.append("<!-- pagebreak -->")
    return "\n\n".join(out)


def expand_directives(tmpl: str, R, results: Path, figs: Path, prof_path: Path) -> str:
    fns = {
        "universe_table": lambda: universe_table(R),
        "year_table": lambda: year_table(R),
        "synthetic_table": lambda: synthetic_table(R),
        "parallel_table": lambda: parallel_table(R),
        "etf_profiles": lambda: profiles(R, figs, prof_path),
    }
    return re.sub(r"<!-- AUTO:([a-z_]+) -->", lambda m: fns[m.group(1)](), tmpl)

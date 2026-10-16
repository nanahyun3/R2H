"""T12 Semantic Result Fingerprint — 실행 메타데이터(provenance)만 뺀 결과표 내용 해시와 run 간 비교.

    python scripts/t12_semantic_fingerprint.py --ref DIR --runs DIR [DIR ...] [--labels ...] [--out-csv F] [--out-json F]
    python scripts/t12_semantic_fingerprint.py --show DIR        # 한 폴더의 표별 지문만 출력

정의 (ANNUAL_STATE_PACKET §5, 이 파일이 구현 기준):

- **Byte Hash**: 저장된 파일 그대로의 sha256.
- **Semantic Fingerprint**: 표마다
  1. ``pd.read_csv(dtype={"ticker": str}, keep_default_na=True, float_precision="round_trip")`` 로 읽는다
     (파이프라인의 ``pipeline._read`` 와 같은 dtype 규칙 + 정확 반올림 파서).
  2. ``PROVENANCE_COLUMNS`` 열을 뺀다.
  3. 키 열(``TABLE_KEYS``; 없으면 전체 열)을 문자열로 바꿔 안정(mergesort) 정렬하고, 키 중복이 없음을 확인한다.
  4. 열을 이름순으로 놓고 ``열이름 · dtype · 모든 값`` 을 직렬화해 sha256 을 낸다. 실수는 ``float.hex()`` (반올림 없음,
     파싱된 float64 의 모든 비트), NaN 은 ``nan``, 결측(None/NA)은 ``<NA>``, 나머지는 ``str``.
  결과표는 ``%.10g`` 로 저장되므로 (worker.py:39) "전체 정밀도" 는 저장된 10 유효숫자 문자열이 나타내는 float64 다.
  저장 단계에서 잘린 정밀도는 Byte·Semantic 어느 쪽으로도 복원할 수 없다.
- **Verdict Fingerprint**: ``is_verdict_column`` 에 해당하는 판정 열만으로 같은 방식의 해시. 판정이 바뀌면 FAIL.
- ``run_manifest.json`` 은 지문에 넣지 않는다. 대신 ``MANIFEST_SEMANTIC_FIELDS`` 를 따로 비교한다
  (``MANIFEST_PROVENANCE_FIELDS`` 는 실행마다 달라도 된다).

제외 열을 정한 근거 (코드 확인):
- ``git_sha`` — pipeline.py:65 ``git_sha()`` 가 실행 시작 시 HEAD + ``+dirty`` 로 만든다 (pipeline.py:179) →
  ``fold_manifest`` (worker.py:227). 결과 계산에는 쓰이지 않는다. 결과표 중 이 열만 실행 환경에서 온다.
- 아래 열은 이름이 메타데이터처럼 보여도 **입력에서 결정되므로 남긴다**: ``data_version``(종가 해시) ·
  ``config_hash``(설정 해시) · ``history_hash``/``model_hash``(학습 표본·선택 파라미터 해시) · ``protocol_version`` ·
  ``known_at``/``available_at``/``calibration_cutoff``(데이터 날짜) · ``evidence_refs``(키 문자열). 이들을 빼면 실제 변화가 숨는다.
- 실행 메타데이터 이름(``run_id``, ``n_workers``, ``runtime_*``)은 현재 결과표에 없지만, 생기면 자동 제외되도록 목록에 둔다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# 실행마다 달라질 수 있는 provenance 열 — 결과표에 있으면 지문에서 뺀다
PROVENANCE_COLUMNS: tuple[str, ...] = (
    "git_sha",
    "run_id",
    "n_workers",
    "runtime_seconds",
    "runtime_seconds_excluded_from_hash",
    "runtime_s",
)

# 결과표 키 (pipeline.PK 와 같음 + 파생/보조 표). 키 중복이 있으면 지문을 만들지 않는다
TABLE_KEYS: dict[str, tuple[str, ...]] = {
    "fold_manifest": ("ticker", "year", "history_strategy"),
    "fit_summary": ("ticker", "year", "history_strategy"),
    "annual_vol_diagnostics": ("ticker", "year"),
    "annual_forecast_diagnostics": ("ticker", "year", "policy"),
    "annual_residual_diagnostics": ("ticker", "year", "policy"),
    "annual_posthoc": ("ticker", "year", "policy", "calibration_method"),
    "annual_cusum_diagnostics": ("ticker", "year", "policy", "window", "boundary_mode", "calibration_method"),
    "annual_history_ablation": ("ticker", "year", "policy", "history_strategy"),
    "diagnostic_profile": ("ticker", "year", "policy"),
    "integrity": ("table",),
    "summary_by_year_policy": ("year", "policy"),
    "aggregates": ("name",),
    "null_dgp_validation": ("dgp_name", "level", "test", "calibration"),
}

# 파이프라인 핵심 산출물 (pipeline.TABLES + diagnostic_profile + integrity) — 집계 지문의 범위
CORE_TABLES: tuple[str, ...] = (
    "fold_manifest",
    "fit_summary",
    "annual_vol_diagnostics",
    "annual_forecast_diagnostics",
    "annual_residual_diagnostics",
    "annual_posthoc",
    "annual_cusum_diagnostics",
    "annual_history_ablation",
    "diagnostic_profile",
    "integrity",
)

# 판정 열: 기각·경보 수·상태·플래그 — 이 값이 바뀌면 수치 차이가 작아도 FAIL
VERDICT_EXACT = {
    "rolling_episodes",
    "rolling_alarm_days",
    "n_rolling_episodes_w60_pure",
    "w60_pure_episodes_iid_insample",
    "first_alarm_date",
    "signal_present",
    "flagged_axes",
    "h_contrast_state",
    "status",
    "leak_check_train_end_lt_test_start",
    # 파생 요약표의 기각·경보 수
    "n_reject_asym",
    "n_reject_iid_insample",
    "n_reject_iid_prequential",
    "w60_pure_episodes_total",
    "n_etf_with_w60_episode",
    "n_multifactor",
    "n_descriptive",
    "n_unresolved",
    "n_no_signal",
    "n_sensitivity_confirmed",
}
VERDICT_PATTERN = re.compile(r"^(annual_reject.*|.*_status|.*_flags)$")

# run_manifest.json 에서 결과의 정체성에 해당하는 필드 (같아야 함) / 실행마다 달라도 되는 필드
MANIFEST_SEMANTIC_FIELDS: tuple[str, ...] = (
    "study_id",
    "protocol_version",
    "tickers",
    "config_hash",
    "data_version",
    "close_hash_ok",
    "input_sha_per_ticker",
    "code_sha",
    "t11_reference_sha",
    "integrity_pass",
)
MANIFEST_PROVENANCE_FIELDS: tuple[str, ...] = (
    "run_id",
    "n_workers",
    "git_sha",
    "environment",
    "outputs_sha256",
    "aggregate_hash",
    "runtime_seconds_excluded_from_hash",
)


def is_verdict_column(col: str) -> bool:
    """판정 열 여부 — 정확 목록 또는 이름 패턴(annual_reject*, *_status, *_flags)."""
    return col in VERDICT_EXACT or bool(VERDICT_PATTERN.match(col))


def byte_hash(path: Path) -> str:
    """파일 바이트 그대로의 sha256."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_table(path: Path) -> pd.DataFrame:
    """결과표 읽기 — ticker 는 문자열(앞자리 0 보존), 실수는 정확 반올림 파서."""
    return pd.read_csv(path, dtype={"ticker": str}, keep_default_na=True, float_precision="round_trip")


def _cell(v: Any) -> str:
    """값 하나를 반올림 없이 문자열로."""
    if v is None or v is pd.NA or v is pd.NaT:
        return "<NA>"
    if isinstance(v, (float, np.floating)):
        f = float(v)
        return "nan" if math.isnan(f) else f.hex()
    if isinstance(v, (bool, np.bool_)):
        return "True" if bool(v) else "False"
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    try:
        if pd.isna(v):
            return "<NA>"
    except (TypeError, ValueError):
        pass
    return str(v)


def canonical(df: pd.DataFrame, name: str) -> pd.DataFrame:
    """provenance 열 제거 → 키 안정 정렬 → 열 이름순. 키 중복이면 ValueError."""
    keep = [c for c in df.columns if c not in PROVENANCE_COLUMNS]
    out = df[keep]
    keys = [k for k in TABLE_KEYS.get(name, ()) if k in out.columns] or sorted(out.columns)
    if not out.empty and out.duplicated(keys).any():
        raise ValueError(f"{name}: duplicate keys {keys}")
    tmp = out.assign(**{f"__k{i}": out[k].astype(str) for i, k in enumerate(keys)})
    tmp = tmp.sort_values([f"__k{i}" for i in range(len(keys))], kind="mergesort")
    tmp = tmp.drop(columns=[f"__k{i}" for i in range(len(keys))]).reset_index(drop=True)
    return tmp[sorted(tmp.columns)]


def frame_digest(df: pd.DataFrame) -> str:
    """열 이름 · dtype · 모든 값의 직렬화 sha256 (df 는 canonical 결과)."""
    h = hashlib.sha256()
    h.update(f"shape={df.shape[0]}x{df.shape[1]}\n".encode())
    for c in df.columns:
        h.update(f"col={c}|dtype={df[c].dtype}\n".encode())
        h.update("\x1f".join(_cell(v) for v in df[c].tolist()).encode())
        h.update(b"\n")
    return h.hexdigest()


def table_fingerprint(path: Path, name: str | None = None) -> dict[str, Any]:
    """한 표의 Byte / Semantic / Verdict 해시."""
    path = Path(path)
    name = name or path.stem
    df = canonical(read_table(path), name)
    vcols = [c for c in df.columns if is_verdict_column(c)]
    return {
        "table": name,
        "rows": int(df.shape[0]),
        "semantic_cols": int(df.shape[1]),
        "byte_sha256": byte_hash(path),
        "semantic_sha256": frame_digest(df),
        "verdict_cols": ";".join(vcols),
        "verdict_sha256": frame_digest(df[vcols]) if vcols else "",
        "excluded_cols": ";".join(c for c in read_table(path).columns if c in PROVENANCE_COLUMNS),
    }


def fingerprint_dir(d: Path, tables: tuple[str, ...] = CORE_TABLES) -> dict[str, Any]:
    """폴더의 표별 지문 + 집계 지문 (표 이름순 'name:hash' 연결의 sha256)."""
    d = Path(d)
    per = {t: table_fingerprint(d / f"{t}.csv", t) for t in tables if (d / f"{t}.csv").exists()}
    missing = [t for t in tables if t not in per]

    def agg(key: str) -> str:
        """표 이름순 연결 해시."""
        return hashlib.sha256("".join(f"{t}:{per[t][key]}\n" for t in sorted(per)).encode()).hexdigest()

    return {
        "dir": str(d),
        "tables": per,
        "missing": missing,
        "aggregate_byte": agg("byte_sha256"),
        "aggregate_semantic": agg("semantic_sha256"),
        "aggregate_verdict": agg("verdict_sha256"),
    }


def _diff_table(a: Path, b: Path, name: str) -> dict[str, Any]:
    """두 표의 열별 차이 — 수치 최대 절대 차이, 판정 셀 변화 수, 다른 열 목록."""
    x, y = canonical(read_table(a), name), canonical(read_table(b), name)
    out: dict[str, Any] = {"diff_cols": "", "numeric_max_abs_diff": 0.0, "verdict_cells_changed": 0, "note": ""}
    if list(x.columns) != list(y.columns) or x.shape != y.shape:
        out.update(numeric_max_abs_diff=float("inf"), note=f"shape/cols differ {x.shape} vs {y.shape}")
        out["diff_cols"] = ";".join(sorted(set(x.columns) ^ set(y.columns)))
        return out
    keys = [k for k in TABLE_KEYS.get(name, ()) if k in x.columns]
    if keys and not x[keys].astype(str).equals(y[keys].astype(str)):
        out.update(numeric_max_abs_diff=float("inf"), note="key sets differ")
        return out
    diff_cols, worst, vchg = [], 0.0, 0
    for c in x.columns:
        xs = pd.Series([_cell(v) for v in x[c].tolist()])
        ys = pd.Series([_cell(v) for v in y[c].tolist()])
        neq = xs.ne(ys)
        if str(x[c].dtype) != str(y[c].dtype) or neq.any():
            diff_cols.append(c)
            if is_verdict_column(c):
                vchg += int(neq.sum())
            if pd.api.types.is_numeric_dtype(x[c]) and pd.api.types.is_numeric_dtype(y[c]):
                d = np.abs(x[c].to_numpy(float) - y[c].to_numpy(float))
                both_nan = np.isnan(x[c].to_numpy(float)) & np.isnan(y[c].to_numpy(float))
                d = np.where(both_nan, 0.0, d)
                d = np.where(np.isnan(d), np.inf, d)  # 한쪽만 NaN 이면 무한대 차이
                worst = max(worst, float(np.max(d, initial=0.0)))
            # 문자열 열의 차이는 numeric_max_abs_diff 에 넣지 않고 diff_cols 로만 보고한다
    out.update(diff_cols=";".join(diff_cols), numeric_max_abs_diff=worst, verdict_cells_changed=vchg)
    return out


def manifest_context(d: Path) -> dict[str, Any]:
    """run_manifest.json 의 의미 필드만."""
    p = Path(d) / "run_manifest.json"
    if not p.exists():
        return {}
    m = json.loads(p.read_text())
    return {k: m.get(k) for k in MANIFEST_SEMANTIC_FIELDS}


def compare_dirs(ref: Path, other: Path, label: str = "", tables: tuple[str, ...] = CORE_TABLES) -> pd.DataFrame:
    """ref 대비 other 의 표별 판정 행 (Byte / Semantic / Verdict + 원인 열)."""
    fa, fb = fingerprint_dir(ref, tables), fingerprint_dir(other, tables)
    rows = []
    for t in tables:
        if t not in fa["tables"] or t not in fb["tables"]:
            rows.append({"run": label or str(other), "table": t, "byte": "MISSING", "semantic": "MISSING", "verdict": "MISSING"})
            continue
        a, b = fa["tables"][t], fb["tables"][t]
        byte_ok = a["byte_sha256"] == b["byte_sha256"]
        sem_ok = a["semantic_sha256"] == b["semantic_sha256"]
        ver_ok = a["verdict_sha256"] == b["verdict_sha256"]
        row = {
            "run": label or str(other),
            "table": t,
            "rows": b["rows"],
            "byte": "PASS" if byte_ok else "FAIL",
            "semantic": "PASS" if sem_ok else "FAIL",
            "verdict": "PASS" if ver_ok else "FAIL",
            "excluded_cols": b["excluded_cols"],
            "semantic_sha256": b["semantic_sha256"],
            "byte_sha256": b["byte_sha256"],
        }
        # 바이트가 다르면 provenance 열 포함 원본 열 단위로 어디가 다른지 적는다
        if not byte_ok:
            raw_a, raw_b = read_table(ref / f"{t}.csv"), read_table(other / f"{t}.csv")
            prov_diff = [
                c for c in PROVENANCE_COLUMNS
                if c in raw_a.columns and c in raw_b.columns and set(raw_a[c].astype(str)) != set(raw_b[c].astype(str))
            ]
            row["byte_diff_provenance_cols"] = ";".join(prov_diff)
        if not sem_ok:
            row.update(_diff_table(ref / f"{t}.csv", other / f"{t}.csv", t))
        rows.append(row)
    ma, mb = manifest_context(ref), manifest_context(other)
    if ma or mb:
        bad = [k for k in MANIFEST_SEMANTIC_FIELDS if ma.get(k) != mb.get(k)]
        rows.append(
            {
                "run": label or str(other),
                "table": "run_manifest.json(semantic fields)",
                "byte": "PASS" if (ref / "run_manifest.json").exists() and byte_hash(ref / "run_manifest.json") == byte_hash(other / "run_manifest.json") else "FAIL",
                "semantic": "PASS" if not bad else "FAIL",
                "verdict": "PASS" if ma.get("integrity_pass") == mb.get("integrity_pass") else "FAIL",
                "diff_cols": ";".join(bad),
            }
        )
    return pd.DataFrame(rows)


def overall(df: pd.DataFrame) -> dict[str, str]:
    """표별 판정 → run 단위 판정. Semantic/Verdict 하나라도 FAIL 이면 FAIL."""
    return {
        "byte": "PASS" if (df.byte == "PASS").all() else "FAIL",
        "semantic": "PASS" if (df.semantic == "PASS").all() else "FAIL",
        "verdict": "PASS" if (df.verdict == "PASS").all() else "FAIL",
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="T12 semantic result fingerprint")
    ap.add_argument("--ref", default=None)
    ap.add_argument("--runs", nargs="*", default=[])
    ap.add_argument("--labels", nargs="*", default=None)
    ap.add_argument("--show", default=None)
    ap.add_argument("--out-csv", default=None)
    ap.add_argument("--out-json", default=None)
    a = ap.parse_args()
    if a.show:
        fp = fingerprint_dir(Path(a.show))
        for t, r in fp["tables"].items():
            print(f"{t:32s} rows={r['rows']:6d} byte={r['byte_sha256'][:16]} semantic={r['semantic_sha256'][:16]} verdict={r['verdict_sha256'][:16]} excluded={r['excluded_cols']}")
        print(f"aggregate_byte={fp['aggregate_byte']}\naggregate_semantic={fp['aggregate_semantic']}\naggregate_verdict={fp['aggregate_verdict']}")
        if a.out_json:
            Path(a.out_json).write_text(json.dumps(fp, indent=1) + "\n")
        raise SystemExit(0)
    if not a.ref or not a.runs:
        ap.error("--ref and --runs are required (or --show DIR)")
    labels = a.labels or [Path(r).parent.name if Path(r).name == "merged" else Path(r).name for r in a.runs]
    res = pd.concat([compare_dirs(Path(a.ref), Path(r), lab) for r, lab in zip(a.runs, labels, strict=True)], ignore_index=True)
    cols = [c for c in ("run", "table", "rows", "byte", "semantic", "verdict", "byte_diff_provenance_cols", "diff_cols", "numeric_max_abs_diff", "verdict_cells_changed") if c in res.columns]
    print(res[cols].to_string(index=False))
    summary = {lab: overall(res[res.run == lab]) for lab in labels}
    print(json.dumps(summary, indent=1))
    if a.out_csv:
        res.to_csv(a.out_csv, index=False, lineterminator="\n")
    if a.out_json:
        Path(a.out_json).write_text(
            json.dumps({"ref": a.ref, "ref_fingerprint": fingerprint_dir(Path(a.ref)), "summary": summary}, indent=1) + "\n"
        )
